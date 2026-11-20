import torch
import numpy as np
from test import test
from eval import eval_p
import os
import options

args = options.parser.parse_args()

def label_smoothing(labels, epsilon=1e-5):
    smooth_labels = (1 - epsilon) * labels + epsilon / labels.size(0)
    return smooth_labels

binary_CE_loss = torch.nn.BCELoss(reduction='mean')

def KMXMILL_individual(element_logits,
    seq_len,
    labels,
    device,
    loss_type='CE',
    args=args
    ):
    k = np.ceil(seq_len / args.k).astype('int32')

    instance_logits = torch.zeros(0).to(device)
    real_label = torch.zeros(0).to(device)
    real_size = int(element_logits.shape[0])
    for i in range(real_size):
        k[i] = min(k[i], seq_len[i])
        tmp, tmp_index = torch.topk(element_logits[i][:seq_len[i]], k=int(k[i]), dim=0)

        instance_logits = torch.cat((instance_logits, tmp), dim=0)
        if labels[i] == 1:
            real_label = torch.cat((real_label, torch.ones((int(k[i]), 1)).to(device)), dim=0)
        else:
            real_label = torch.cat((real_label, torch.zeros((int(k[i]), 1)).to(device)), dim=0)

    if loss_type == 'CE':
        real_label = label_smoothing(real_label)
        milloss = binary_CE_loss(input=instance_logits, target=real_label)
        return milloss


def train(max_iters, train_loader, all_test_loader, args, model, optimizer, logger, device, save_path):
    [test_loader] = all_test_loader
    itr = 0
    best_auc = None

    result_dir = os.path.join('./result', save_path)
    result_file = os.path.join(result_dir, 'result.txt')
    ckpt_save_path = os.path.join(args.ckpt_path, save_path)
    if os.path.exists(result_file) or os.path.exists(ckpt_save_path):
        raise FileExistsError(f'Run {save_path!r} already exists. Choose a new --run_id.')
    os.makedirs(ckpt_save_path)
    os.makedirs(result_dir, exist_ok=True)
    with open(result_file, mode='x') as f:
        for key, value in vars(args).items():
            f.write('%s:%s\n' % (key, value))

    # Load pretrained weights if specified
    if args.pretrained_ckpt:
        checkpoint = torch.load(args.pretrained_ckpt)
        model.load_state_dict(checkpoint)
        print(f'Model loaded weights from {args.pretrained_ckpt}')
    else:
        print('Model is trained from scratch')

    # Training loop - iteration based
    while itr < max_iters:
        model.train()
        for i, data in enumerate(train_loader):
            if itr >= max_iters:
                break
            itr += 1
            # Unpack data
            [anomaly_features_v, normaly_features_v], [anomaly_label, normaly_label]= data

            # Concatenate features and labels
            visual_features = torch.cat((anomaly_features_v.squeeze(0), normaly_features_v.squeeze(0)), dim=0)
            videolabels = torch.cat((anomaly_label.squeeze(0), normaly_label.squeeze(0)), dim=0)
            # text_features = torch.cat((anomaly_features_txts.squeeze(0), normal_features_txts.squeeze(0)), dim=0)

            # Prepare sequence lengths and move to device
            seq_len = torch.sum(torch.max(visual_features.abs(), dim=2)[0] > 0, dim=1).numpy()
            visual_features = visual_features[:, :np.max(seq_len), :].float().to(device)

            # Forward pass with the prototype loss
            final_features, element_logits, v_features, pide_loss = model(visual_features, seq_len)

            # Compute MIL loss
            ce_loss = KMXMILL_individual(element_logits, seq_len, videolabels, device, loss_type='CE')

            pide_weight = 5.0
            total_loss = 15*ce_loss + pide_weight * pide_loss

            optimizer.zero_grad()
            total_loss.backward()
            optimizer.step()

            # Periodic testing and logging
            if args.snapshot > 0 and itr % args.snapshot == 0 and not itr == 0 and itr >= args.snapshot_start:
                model.eval()  # Set to evaluation mode
                test_result_dict = test(test_loader, model, device, args)

                current_auc = eval_p(itr=itr, dataset=args.dataset_name, predict_dict=test_result_dict, logger=logger,
                    save_path=save_path, plot=args.plot, args=args)
                
                # Save best model
                if current_auc is not None and (best_auc is None or current_auc > best_auc):
                    best_auc = current_auc
                    torch.save(model.state_dict(), os.path.join(ckpt_save_path, 'best_model.pkl'))
                    print(f'Checkpoint selected at test ROC AUC {best_auc:.6f}')
                
                model.train()  # Return to training mode
    
    # Save final model
    torch.save(model.state_dict(), os.path.join(ckpt_save_path, 'final_model.pkl'))
    if best_auc is None:
        print('Training finished without a test evaluation.')
    else:
        print(f'Training finished. Peak test ROC AUC: {best_auc:.6f}')