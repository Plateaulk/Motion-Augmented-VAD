import numpy as np 
import os 
import random
import matplotlib.pyplot as plt  
plt.switch_backend('agg')  
import zipfile  
import io  
import torch  
from sklearn.metrics import roc_auc_score, roc_curve


def set_seed(seed):
    """Seed the training RNGs and request deterministic PyTorch operations."""
    os.environ["CUBLAS_WORKSPACE_CONFIG"] = ":4096:8"
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False
    # Request deterministic operations and warn when one is unavailable.
    try:
        torch.use_deterministic_algorithms(True, warn_only=True)
    except Exception:
        pass


def worker_init_fn(worker_id, base_seed=None):
    """Initialize RNGs for the training data worker."""
    if base_seed is not None:
        np.random.seed(1)
        random.seed(1)
        torch.manual_seed(1)


def sample_mixed_bag(original, synthetic, size, ratio):
    """Sample crop entries without replacement, then shuffle real/synthetic order."""
    if size < 1 or not np.isfinite(ratio) or not 0 <= ratio <= 1:
        raise ValueError('sample_size must be positive and synthetic_ratio must be in [0, 1]')
    n_syn = min(int(size * ratio), len(synthetic))
    n_orig = size - n_syn
    if len(original) < n_orig:
        raise ValueError(f'Not enough original crop entries: need {n_orig}, found {len(original)}')
    samples = random.sample(synthetic, n_syn) + random.sample(original, n_orig)
    random.shuffle(samples)
    return samples


def validate_test_split(testlist):
    """Upstream evaluation averages each consecutive batch of ten crops."""
    names = [name.strip() for name in testlist]
    if not names or len(names) % 10 or len(names) != len(set(names)):
        raise ValueError('Test split must contain unique complete groups of ten crops')
    for offset in range(0, len(names), 10):
        base = names[offset].rsplit('_', 1)[0]
        if names[offset:offset + 10] != [f'{base}_{crop}' for crop in range(10)]:
            raise ValueError(f'Test crops must be consecutive and ordered 0-9: {base}')


def load_feature(path, feature_size=512):
    feature = np.load(path, allow_pickle=False)
    if (feature.ndim != 2 or feature.shape[0] == 0 or feature.shape[1] != feature_size
            or not np.issubdtype(feature.dtype, np.floating) or not np.isfinite(feature).all()):
        raise ValueError(f'Expected nonempty finite (T, {feature_size}) floating features: {path}')
    return feature


def random_extract(feat, t_max):
    r = np.random.randint(len(feat)-t_max)  
    return feat[r:r+t_max], r  


def random_extract_step(feat, t_max, step):
    if len(feat) - step * t_max > 0:
        r = np.random.randint(len(feat) - step * t_max) 
    else:
        r = np.random.randint(step)
    return feat[r:r+t_max:step], r  


def random_perturb(feat, length):
    samples = np.arange(length) * len(feat) / length  
    for i in range(length):
        if i < length - 1:
            if int(samples[i]) != int(samples[i + 1]):
                samples[i] = np.random.choice(range(int(samples[i]), int(samples[i + 1]) + 1))
            else:
                samples[i] = int(samples[i])
        else:
            if int(samples[i]) < length - 1:
                samples[i] = np.random.choice(range(int(samples[i]), length))
            else:
                samples[i] = int(samples[i])
    return feat[samples.astype('int')], samples.astype('int')  


def pad(feat, min_len):
    
    if np.shape(feat)[0] <= min_len:
        return np.pad(feat, ((0, min_len-np.shape(feat)[0]), (0, 0)), mode='constant', constant_values=0)
    else:
        return feat  


def process_feat(feat, length, step):
    if len(feat) > length:
        if step and step > 1:
            features, r = random_extract_step(feat, length, step)  
            return pad(features, length), r  
        else:
            features, r = random_extract(feat, length)  
            return features, r  
    else:
        return pad(feat, length), 0 


def process_feat_sample(feat, length):
    if len(feat) > length:
            features, samples = random_perturb(feat, length)  
            return features, samples  
    else:
        return pad(feat, length), 0 


def scorebinary(scores=None, threshold=0.5):
    scores_threshold = scores.copy()  
    scores_threshold[scores_threshold < threshold] = 0  
    scores_threshold[scores_threshold >= threshold] = 1  
    return scores_threshold  


def fill_context_mask(mask, sizes, v_mask, v_unmask):
    mask.fill_(v_unmask)  
    n_context = mask.size(2) 
    for i, size in enumerate(sizes):  
        if size < n_context: 
            mask[i, :, size:] = v_mask 
    return mask  


def median(attention_logits, args):
    attention_medians = torch.zeros(0).to(args.device)  
    batch_size = attention_logits.shape[0]  
    for i in range(batch_size):  
        attention_logit = attention_logits[i][attention_logits[i] > 0].unsqueeze(0)  
        attention_medians = torch.cat((attention_medians, attention_logit.median(1, keepdims=True)[0]), dim=0) 
    attention_medians = attention_medians.unsqueeze(1) 
    attention_logits_mask = attention_logits.clone()  
    attention_logits_mask[attention_logits <= attention_medians] = 0  
    attention_logits_mask[attention_logits > attention_medians] = 1  
    attention_logits = attention_logits * attention_logits_mask  
    attention_logits_sum = attention_logits.sum(dim=2, keepdim=True) 
    attention_logits = attention_logits / attention_logits_sum 
    return attention_logits 


def align_frame_scores(segments, frame_labels):
    """Score only frames covered by both the features and this video's annotations."""
    scores = np.repeat(np.asarray(segments).reshape(-1), 16)
    labels = np.asarray(frame_labels, dtype=np.float32).reshape(-1)
    covered = min(scores.size, labels.size)
    return scores[:covered], labels[:covered]


def read_test_videos(path):
    with open(path, encoding="utf-8") as stream:
        crops = [line.strip() for line in stream if line.strip()]
    validate_test_split(crops)
    return [crop[:-2] for crop in crops[::10]]


def evaluate_frames(predictions, frame_labels, video_ids, video_labels=None, with_roc=False):
    """Evaluate the declared videos using the upstream 16-frame alignment."""
    if not isinstance(predictions, dict) or not video_ids:
        raise ValueError("Missing test videos or predictions")
    expected = set(video_ids)
    missing = expected.difference(predictions)
    extra = predictions.keys() - expected
    if missing or extra:
        raise ValueError(f"Incomplete test coverage ({len(expected) - len(missing)}/{len(expected)} videos). "
                         f"Missing: {', '.join(sorted(missing)[:3]) or 'none'}. "
                         f"Unexpected: {', '.join(sorted(extra)[:3]) or 'none'}.")

    all_scores, all_labels = [], []
    annotated_frames = 0
    for name in video_ids:
        if video_labels is not None and video_labels.get(f"{name}_0") not in ("[0.0]", "[1.0]"):
            raise ValueError(f"Missing or invalid video label: {name}")
        if name not in frame_labels:
            raise ValueError(f"Missing frame labels: {name}")
        labels = np.asarray(frame_labels[name], dtype=np.float32).reshape(-1)
        segments = np.asarray(predictions[name], dtype=np.float32).reshape(-1)
        if not segments.size or not np.isfinite(segments).all():
            raise ValueError(f"Empty or non-finite scores: {name}")
        if not labels.size or not np.isin(labels, [0, 1]).all():
            raise ValueError(f"Empty or non-binary frame labels: {name}")
        scores, covered_labels = align_frame_scores(segments, labels)
        all_scores.append(scores)
        all_labels.append(covered_labels)
        annotated_frames += labels.size
    scores, labels = np.concatenate(all_scores), np.concatenate(all_labels)
    if labels.min() == labels.max():
        raise ValueError("Frame AUC requires both normal and anomalous annotated frames")
    result = {
        "auc": float(roc_auc_score(labels, scores)), "num_videos": len(all_scores),
        "expected_videos": len(expected), "num_frames": len(scores), "annotated_frames": annotated_frames,
    }
    if with_roc:
        fpr, tpr, _ = roc_curve(labels, scores)
        indices = np.unique(np.r_[np.arange(0, len(fpr), 10), len(fpr) - 1])
        result["roc_curve"] = {"fpr": fpr[indices].tolist(), "tpr": tpr[indices].tolist()}
    return result


def anomap(predict_dict, label_dict, save_path, itr, save_root, zip=False, width=15, height=5):

    if not os.path.exists(os.path.join(save_root, save_path, 'plot')): 
        os.makedirs(os.path.join(save_root, save_path, 'plot'))
    for k, v in predict_dict.items():  
        k = k.rsplit('_', 1)[0]
        predict_np, label_np = align_frame_scores(v, label_dict[k])
        x = np.arange(len(predict_np))
        plt.figure(figsize=(width, height))
        plt.plot(x, predict_np, color='b', label='predicted scores', linewidth=1)
        plt.fill_between(x, label_np, where=label_np > 0, facecolor="r", alpha=0.3)

        plt.yticks(np.arange(0, 1.1, step=0.1))  
        plt.xlabel('Frames') 
        plt.ylabel('Anomaly scores') 
        plt.grid(True, linestyle='-.') 
        plt.legend()  
        output_dir = os.path.join(save_root, save_path, 'plot', 'itr_{}'.format(itr))
        if not os.path.exists(output_dir): 
            os.makedirs(output_dir) 
        plt.savefig(os.path.join(output_dir, k + '.svg'), format='svg') 
        plt.close()


