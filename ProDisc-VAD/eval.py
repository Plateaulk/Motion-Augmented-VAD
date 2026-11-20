import os
import pickle

from utils import anomap, evaluate_frames, read_test_videos


def eval_p(itr, dataset, predict_dict, logger, save_path, args, plot=False, zip=False, manual=False):
    label_files = {'shanghaitech': 'frame_label.pickle', 'ucf-crime': 'ucf_gt_upgate.pickle'}
    gt_dir = os.path.join(args.dataset_path, dataset, 'GT')
    with open(os.path.join(gt_dir, label_files[dataset]), 'rb') as stream:
        frame_labels = pickle.load(stream)
    with open(os.path.join(gt_dir, 'video_label_10crop.pickle'), 'rb') as stream:
        video_labels = pickle.load(stream)

    if any(not key.endswith('_0') for key in predict_dict):
        raise ValueError("Expected one ten-crop prediction per video, keyed by its first crop")
    predictions = {key[:-2]: segments for key, segments in predict_dict.items()}
    videos = list(predictions) if manual else read_test_videos(
        os.path.join(args.dataset_path, dataset, 'test_split_10crop.txt'))
    auc = evaluate_frames(predictions, frame_labels, videos, video_labels)["auc"]
    if manual:
        print(f'Manual subset, {len(videos)} videos. Frame-level ROC AUC: {auc}')
    else:
        print('Iteration: {} Area Under the Curve is {}'.format(itr, auc))
    save_root = './manul_test_result' if manual else './result'
    if plot:
        anomap(predict_dict, frame_labels, save_path, itr, save_root, zip, width=15, height=5)
    result_dir = os.path.join(save_root, save_path)
    os.makedirs(result_dir, exist_ok=True)
    with open(os.path.join(result_dir, 'result.txt'), 'a') as stream:
        stream.write(f'itration_{itr}_AUC is {auc}\n')
    return auc
