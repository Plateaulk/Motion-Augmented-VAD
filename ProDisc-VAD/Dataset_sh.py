import numpy as np
from torch.utils.data import Dataset, DataLoader
import utils
import options
import os
import pickle
import random
import torch


class dataset(Dataset):
    def __init__(self, args, train=True, trainlist=None, testlist=None):
        self.args = args
        self.dataset_path = args.dataset_path
        self.dataset_name = args.dataset_name
        self.feature_path = os.path.join(self.dataset_path, self.dataset_name, "SH_clip_video_features")

        self.trainlist = self.txt2list(
            txtpath=os.path.join(self.dataset_path, self.dataset_name, 'train_split_10crop.txt'))
        self.testlist = self.txt2list(txtpath=os.path.join(self.dataset_path, self.dataset_name, 'test_split_10crop.txt'))
        self.video_label_dict = self.pickle_reader(
            file=os.path.join(self.dataset_path, self.dataset_name, 'GT', 'video_label_10crop.pickle'))

        self.synthetic_anomaly_train = []
        self.original_anomaly_train = []
        self.synthetic_ratio = getattr(args, 'synthetic_ratio', options.DEFAULT_SYNTHETIC_RATIOS[self.dataset_name])
        if hasattr(args, 'synthetic_samples') and args.synthetic_samples:
            syn_ids = [x.strip() for x in args.synthetic_samples.split(',') if x.strip()]
            if len(syn_ids) != len(set(syn_ids)):
                raise ValueError('Duplicate synthetic sample IDs')
            for syn_id in syn_ids:
                for crop_idx in range(10):
                    sample_name = f'{syn_id}_{crop_idx}'
                    if sample_name + '\n' not in self.trainlist:
                        self.trainlist.append(sample_name + '\n')
                    if sample_name in {x.strip() for x in self.testlist}:
                        raise ValueError(f'Synthetic sample overlaps test split: {sample_name}')
                    if sample_name in self.video_label_dict and self.video_label_dict[sample_name] != '[1.0]':
                        raise ValueError(f'Conflicting synthetic label: {sample_name}')
                    self.video_label_dict[sample_name] = '[1.0]'
                    self.synthetic_anomaly_train.append(sample_name)

        self.normal_video_train, self.anomaly_video_train = self.p_n_split_dataset(
            self.video_label_dict, self.trainlist)
        self.original_anomaly_train = [x for x in self.anomaly_video_train if x not in self.synthetic_anomaly_train]
        if len(self.trainlist) != len(set(self.trainlist)):
            raise ValueError('Duplicate entries in training split')
        if not train:
            utils.validate_test_split(self.testlist)
        self.train = train
        self.t_max = args.max_seqlen

    def txt2list(self, txtpath=''):
        with open(file=txtpath, mode='r') as f:
            return f.readlines()

    def pickle_reader(self, file=''):
        with open(file=file, mode='rb') as f:
            return pickle.load(f)

    def p_n_split_dataset(self, video_label_dict, trainlist):
        normal_video_train = []
        anomaly_video_train = []
        for t in trainlist:
            video_name = t.replace('\n', '').replace('Ped', 'ped')
            if video_name not in video_label_dict:
                raise ValueError(f'Missing training label: {video_name}')
            if video_label_dict[video_name] == '[1.0]':
                anomaly_video_train.append(video_name)
            else:
                normal_video_train.append(video_name)
        return normal_video_train, anomaly_video_train

    def __getitem__(self, index):
        if self.train:
            normaly_indexs = utils.sample_mixed_bag(self.normal_video_train, [], self.args.sample_size, 0)
            anomaly_indexs = utils.sample_mixed_bag(
                self.original_anomaly_train, self.synthetic_anomaly_train,
                self.args.sample_size, self.synthetic_ratio)

            anomaly_features = torch.zeros(0)
            normaly_features = torch.zeros(0)
            for a_i, n_i in zip(anomaly_indexs, normaly_indexs):
                anomaly_data_video_name = a_i.replace('\n', '')
                normaly_data_video_name = n_i.replace('\n', '')
                apath = os.path.join(self.feature_path, anomaly_data_video_name + '.npy')
                npath = os.path.join(self.feature_path, normaly_data_video_name + '.npy')
                for feature_path in (apath, npath):
                    if not os.path.isfile(feature_path):
                        raise FileNotFoundError(f'Missing training feature: {feature_path}')
                anomaly_feature = utils.load_feature(apath, self.args.feature_size)
                anomaly_feature, r = utils.process_feat_sample(anomaly_feature, self.t_max)
                anomaly_feature = torch.from_numpy(anomaly_feature).unsqueeze(0)
                normaly_feature = utils.load_feature(npath, self.args.feature_size)
                normaly_feature, r = utils.process_feat(normaly_feature, self.t_max, self.args.sample_step)
                normaly_feature = torch.from_numpy(normaly_feature).unsqueeze(0)
                anomaly_features = torch.cat((anomaly_features, anomaly_feature), dim=0)
                normaly_features = torch.cat((normaly_features, normaly_feature), dim=0)
            normaly_label = torch.zeros((self.args.sample_size, 1))
            anomaly_label = torch.ones((self.args.sample_size, 1))
            anomaly_features = anomaly_features.float()
            normaly_features = normaly_features.float()
            return [anomaly_features, normaly_features], [anomaly_label, normaly_label]
        else:
            data_video_name = self.testlist[index].replace('\n', '')
            fpath = os.path.join(self.feature_path, data_video_name + '.npy')
            self.feature = utils.load_feature(fpath, self.args.feature_size)
            self.feature = self.feature.astype(np.float32)
            return self.feature, data_video_name

    def __len__(self):
        return len(self.trainlist) if self.train else len(self.testlist)
