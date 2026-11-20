import argparse

DEFAULT_SYNTHETIC_RATIOS = {'shanghaitech': 0.5, 'ucf-crime': 0.05}


class TrainingParser(argparse.ArgumentParser):
    def parse_args(self, args=None, namespace=None):
        parsed = super().parse_args(args, namespace)
        if parsed.synthetic_ratio is None:
            parsed.synthetic_ratio = DEFAULT_SYNTHETIC_RATIOS[parsed.dataset_name]
        return parsed


parser = TrainingParser(description='ProDisc-VAD')

# Dataset
parser.add_argument('--dataset_name', default='shanghaitech', choices=['shanghaitech', 'ucf-crime'], help='dataset name: shanghaitech or ucf-crime')
parser.add_argument('--dataset_path', default='./dataset', help='path to dataset root')
parser.add_argument('--feature_size', type=int, default=512, help='feature dimension')
parser.add_argument('--max_seqlen', type=int, default=300, help='maximum sequence length')
parser.add_argument('--sample_size', type=int, default=30, help='number of crop entries per class bag')
parser.add_argument('--sample_step', type=int, default=1, help='sampling step for normal features')

# Training
parser.add_argument('--lr', type=float, default=0.0005, help='learning rate')
parser.add_argument('--batch_size', choices=[1], type=int, default=1, help='batch size')
parser.add_argument('--max_iters', type=int, default=600, help='maximum training iterations')
parser.add_argument('--seed', choices=[1], type=int, default=1, help='random seed')
parser.add_argument('--k', type=int, default=5, help='k for top-k MIL')

# Model
parser.add_argument('--ckpt_path', default='./ckpt', help='checkpoint output root')
parser.add_argument('--model_name', default='default_model', help='model save name')
parser.add_argument('--run_id', default=None, help='run identifier for save path')
parser.add_argument('--pretrained_ckpt', default=None, help='path to pretrained checkpoint')
parser.add_argument('--device', type=int, default=0, help='CUDA device index')

# Logging
parser.add_argument('--snapshot', type=int, default=1, help='test every N iterations')
parser.add_argument('--plot', type=int, default=0, help='save anomaly score plots (0 or 1)')

# Synthetic samples
parser.add_argument('--synthetic_samples', default=None, help='comma-separated synthetic sample IDs')
parser.add_argument('--synthetic_ratio', type=float, help='synthetic crop ratio (ShanghaiTech 0.5, UCF-Crime 0.05)')
parser.add_argument('--snapshot_start', type=int, default=0, help='iteration from which to start evaluating snapshots')
