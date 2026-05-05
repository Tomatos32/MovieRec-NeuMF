import json
import pandas as pd
import numpy as np
import torch
from torch.utils.data import Dataset
from collections import defaultdict
import random
import os
import gc
from tqdm import tqdm


class MovieLensProcessor:
    """
    数据特征管道：负责 MovieLens 原始数据的清洗、二值化及基于时间序列的留一法切分。
    针对 ML-32M (3200万条) + 16GB RAM 场景，做了严格的内存峰值管控。
    """
    def __init__(self, ratings_path: str, movies_path: str = '../data/movies.csv'):
        self.ratings_path = ratings_path
        self.movies_path = movies_path
        self.user_mapping = {}
        self.movie_mapping = {}
        self.user_interacted_movies = {}  # {user_idx: np.array (sorted)}
        self.all_movies_list = []
        self.genres_matrix = None
        
    def build_genres_matrix(self):
        """
        根据现有的 movie_mapping，从 movies.csv 加载流派数据，构造 Multi-hot 矩阵
        返回形状为 (num_movies, 18) 的张量
        """
        print("[Feature Pipeline] Building Genres Matrix...")
        if not os.path.exists(self.movies_path):
            print(f"Warning: Data file {self.movies_path} not found. Cannot build genres matrix.")
            return None
        
        movies_df = pd.read_csv(self.movies_path)
        
        # 提取所有包含的流派
        all_genres = set()
        for genres_str in movies_df['genres'].dropna():
            if genres_str != '(no genres listed)':
                all_genres.update(genres_str.split('|'))
        
        # 为了固定维度，我们可以强制指定 MovieLens 固定的 18 种流派，以保证兼容性
        fixed_genres = sorted(list(all_genres))
        # 确保最多选取 18 种 (或者直接使用固定的维度, NeuMF 要求固定的 num_genres)
        # 这里动态设定，但在脚本中我们可以把这个维度传给 NeuMF
        
        genre2idx = {g: i for i, g in enumerate(fixed_genres)}
        num_genres = len(fixed_genres)
        num_movies = len(self.movie_mapping)
        
        genre_matrix = np.zeros((num_movies, num_genres), dtype=np.float32)
        
        # 填充矩阵
        for _, row in movies_df.iterrows():
            m_id = row['movieId']
            if m_id in self.movie_mapping:
                m_idx = self.movie_mapping[m_id]
                g_str = row['genres']
                if pd.notna(g_str) and g_str != '(no genres listed)':
                    for g in g_str.split('|'):
                        if g in genre2idx:
                            genre_matrix[m_idx, genre2idx[g]] = 1.0
                            
        self.genres_matrix = genre_matrix
        print(f"[Feature Pipeline] Genres Matrix built: shape {genre_matrix.shape}")
        
        # 保存 genre.json 以备评估脚本使用
        mapping_dir = '../model'
        with open(os.path.join(mapping_dir, 'genre_mapping.json'), 'w') as f:
            json.dump(genre2idx, f)
            
        return torch.tensor(genre_matrix, dtype=torch.float32), num_genres
        
    def process(self):
        # 1. 内存优化的高效加载逻辑
        if not os.path.exists(self.ratings_path):
            print(f"Warning: Data file {self.ratings_path} not found.")
            return None, None, None

        print("[Feature Pipeline] Loading dataset via Pandas with memory optimization...")
        
        dtype_spec = {
            'user_id': np.int32,     
            'movie_id': np.int32,    
            'rating': np.float32,    
            'timestamp': np.int32    
        }
        
        with open(self.ratings_path, 'r') as f:
            first_line = f.readline()
            
        if '::' in first_line:
            df = pd.read_csv(self.ratings_path, sep='::', engine='python', 
                             names=['user_id', 'movie_id', 'rating', 'timestamp'],
                             dtype=dtype_spec)
        else:
            df = pd.read_csv(self.ratings_path, names=['user_id', 'movie_id', 'rating', 'timestamp'], 
                             engine='c', sep=',', header=0, 
                             dtype=dtype_spec)
        
        # 释放不再需要的评分列
        df.drop(columns=['rating'], inplace=True)
        
        # 2. 隐式反馈二值化
        df['implicit_rating'] = np.ones(len(df), dtype=np.float32)
        
        # 3. 特征映射
        print("[Feature Pipeline] Mapping IDs...")
        user_ids = df['user_id'].unique()
        movie_ids = df['movie_id'].unique()
        self.user_mapping = {uid: idx for idx, uid in enumerate(user_ids)}
        self.movie_mapping = {mid: idx for idx, mid in enumerate(movie_ids)}
        
        df['user_idx'] = df['user_id'].map(self.user_mapping).astype(np.int32)
        df['movie_idx'] = df['movie_id'].map(self.movie_mapping).astype(np.int32)
        
        # 清除原始ID列释放内存
        df.drop(columns=['user_id', 'movie_id'], inplace=True)
        gc.collect()
        
        self.all_movies_list = list(self.movie_mapping.values())
        
        # ============================================================
        # 关键调整: 先做时间切分, 释放大 DataFrame 后再构建负采样字典
        # 这样避免 df + dict 同时驻留内存导致 OOM
        # ============================================================
        
        # 4. 留一法划分验证与测试
        print("[Feature Pipeline] Sorting and splitting data temporally (Leave-One-Out)...")
        df.sort_values(by=['user_idx', 'timestamp'], inplace=True)
        df['rank_latest'] = df.groupby('user_idx')['timestamp'].rank(
            method='first', ascending=False
        ).astype(np.int16)
        
        # 释放 timestamp
        df.drop(columns=['timestamp'], inplace=True)
        gc.collect()
        
        train_df = df[df['rank_latest'] > 2].copy()
        valid_df = df[df['rank_latest'] == 2].copy()
        test_df = df[df['rank_latest'] == 1].copy()
        
        num_users = len(user_ids)
        num_movies = len(movie_ids)
        
        print(f"[Feature Pipeline] Mapped {num_users} Users, {num_movies} Movies.")
        print(f"[Feature Pipeline] Split: Train {len(train_df)}, Valid {len(valid_df)}, Test {len(test_df)}")
        
        # 彻底释放原始大表
        del df
        gc.collect()
        
        # 5. 从训练集构建负采样查找字典
        # 使用 numpy 排序数组代替 Python set, 内存效率提升 ~12x
        # Python set: 200K users × ~8KB/set ≈ 1.6GB
        # NumPy int32 array: 200K users × ~640B/arr ≈ 128MB
        print("[Feature Pipeline] Building negative sampling dictionary (numpy sorted arrays)...")
        self._build_interaction_dict(train_df)
        
        # 6. 保存映射文件
        mapping_dir = '../model'
        os.makedirs(mapping_dir, exist_ok=True)
        # Convert int32 to int for JSON serialization
        u_map = {int(k): int(v) for k, v in self.user_mapping.items()}
        m_map = {int(k): int(v) for k, v in self.movie_mapping.items()}
        with open(os.path.join(mapping_dir, 'user_mapping.json'), 'w') as f:
            json.dump(u_map, f)
        with open(os.path.join(mapping_dir, 'movie_mapping.json'), 'w') as f:
            json.dump(m_map, f)
        print("[Feature Pipeline] Exported user_mapping.json and movie_mapping.json to ../model/")
        
        return train_df, valid_df, test_df

    def _build_interaction_dict(self, train_df: pd.DataFrame):
        """
        用 numpy 排序数组构建用户交互字典, 内存远小于 Python set。
        查询时使用 np.searchsorted 实现 O(log n) 命中检测。
        """
        # 先按 (user_idx, movie_idx) 排序
        sorted_df = train_df[['user_idx', 'movie_idx']].sort_values(
            by=['user_idx', 'movie_idx']
        )
        
        user_arr = sorted_df['user_idx'].values
        movie_arr = sorted_df['movie_idx'].values
        del sorted_df
        gc.collect()
        
        # 找到每个用户的起止位置, 一次性切割
        change_points = np.where(np.diff(user_arr) != 0)[0] + 1
        starts = np.concatenate([[0], change_points])
        ends = np.concatenate([change_points, [len(user_arr)]])
        user_ids_at_starts = user_arr[starts]
        
        self.user_interacted_movies = {}
        for uid, s, e in zip(user_ids_at_starts, starts, ends):
            self.user_interacted_movies[int(uid)] = movie_arr[s:e].copy()
        
        del user_arr, movie_arr, change_points, starts, ends
        gc.collect()


class MovieLensDataset(Dataset):
    """
    高性能 PyTorch Dataset：在初始化时预计算全局负样本。
    1. 使用 Numpy 向量化操作进行批量随机采样。
    2. 将所有样本（正+负）预先展平为 PyTorch Tensor，消除 __getitem__ 的计算开销。
    3. 支持 num_workers > 0，因为 Tensor 内存已在父进程中分配完毕。
    """
    def __init__(self, df: pd.DataFrame, user_interacted_movies: dict, all_movies_list: list, 
                 num_negatives: int = 4, is_training: bool = True):
        self.is_training = is_training
        
        if not is_training:
            self.users = torch.tensor(df['user_idx'].values, dtype=torch.long)
            self.movies = torch.tensor(df['movie_idx'].values, dtype=torch.long)
            self.labels = torch.tensor(df['implicit_rating'].values, dtype=torch.float32)
        else:
            print(f"[Dataset] Pre-sampling {num_negatives}x negatives for {len(df)} positive samples...")
            pos_users = df['user_idx'].values
            pos_movies = df['movie_idx'].values
            num_pos = len(pos_users)
            
            # 1. 构造总数组空间
            total_size = num_pos * (1 + num_negatives)
            users_np = np.zeros(total_size, dtype=np.int32)
            movies_np = np.zeros(total_size, dtype=np.int32)
            labels_np = np.zeros(total_size, dtype=np.float32)
            
            # 2. 填充正样本 (每个 Block 的第 0 位)
            users_np[::1+num_negatives] = pos_users
            movies_np[::1+num_negatives] = pos_movies
            labels_np[::1+num_negatives] = 1.0
            
            # 3. 填充负样本 (批量随机采样)
            all_movies_np = np.array(all_movies_list, dtype=np.int32)
            
            # 填充其余位置
            for i in range(1, 1 + num_negatives):
                print(f"  - Sampling Negative Slot {i}/{num_negatives}...")
                # 随机抽取候选 (先一次性向量化抽取)
                neg_candidates = np.random.choice(all_movies_np, size=num_pos)
                
                # 校验碰撞：使用更快的逻辑
                # 对于 32M 数据，Python 循环依然是瓶颈，我们按块更新进度
                chunk_size = 1_000_000
                for start_j in tqdm(range(0, num_pos, chunk_size), desc=f"    Slot {i} Checking"):
                    end_j = min(start_j + chunk_size, num_pos)
                    for j in range(start_j, end_j):
                        u = pos_users[j]
                        m = neg_candidates[j]
                        interacted = user_interacted_movies.get(u)
                        
                        if interacted is not None:
                            # 极速版碰撞检测：利用 searchsorted
                            idx = np.searchsorted(interacted, m)
                            if idx < len(interacted) and interacted[idx] == m:
                                # 发生碰撞，重抽直到不碰撞
                                while True:
                                    m_new = random.choice(all_movies_list)
                                    idx_new = np.searchsorted(interacted, m_new)
                                    if not (idx_new < len(interacted) and interacted[idx_new] == m_new):
                                        neg_candidates[j] = m_new
                                        break
                
                users_np[i::1+num_negatives] = pos_users
                movies_np[i::1+num_negatives] = neg_candidates
                labels_np[i::1+num_negatives] = 0.0
            
            # 4. 转换为 Tensor 并释放临时内存
            # 使用 int32 存储索引，节省 50% 内存。PyTorch Embedding 层能自动处理 int32 索引。
            self.users = torch.from_numpy(users_np)
            self.movies = torch.from_numpy(movies_np)
            self.labels = torch.from_numpy(labels_np)
            
            del users_np, movies_np, labels_np
            print(f"[Dataset] Pre-sampling complete. Total samples: {len(self.users)}")
        
    def __len__(self):
        return len(self.users)
        
    def __getitem__(self, idx):
        # 显式转换为 long 确保 Embedding 层兼容性
        return self.users[idx].long(), self.movies[idx].long(), self.labels[idx]


if __name__ == '__main__':
    processor = MovieLensProcessor('../data/ratings.csv')
    train_df, valid_df, test_df = processor.process()
    if train_df is not None:
        train_dataset = MovieLensDataset(
            train_df, 
            processor.user_interacted_movies, 
            processor.all_movies_list, 
            num_negatives=4, 
            is_training=True
        )
        u, m, l = train_dataset[0]
        print(f"Sample 0 (Positive): User {u}, Movie {m}, Label {l}")
        u, m, l = train_dataset[1]
        print(f"Sample 1 (Negative): User {u}, Movie {m}, Label {l}")
