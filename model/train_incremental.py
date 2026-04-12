import os
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
import pymysql
import pandas as pd
import numpy as np
from datetime import datetime
from neumf import NeuMF  # 假设这是你原本的网络定义的类所在文件

# ==========================================
# 1. 数据库抽取与经验回放 (Experience Replay)
# ==========================================
def fetch_incremental_data(db_config, latest_n=1000, random_replay_n=4000):
    """
    从 MySQL 抽取混合数据集。
    抽取最新的交互和评分，同时抽取全局随机老数据防止灾难性遗忘。
    """
    connection = pymysql.connect(**db_config)
    try:
        # 抽取最新 ratings
        query_new_ratings = f"SELECT user_id, movie_id, 1.0 as implicit_rating FROM ratings ORDER BY timestamp DESC LIMIT {latest_n}"
        df_new_ratings = pd.read_sql(query_new_ratings, connection)
        
        # 抽取最新 interactions (点击等)
        query_new_interactions = f"SELECT user_id, movie_id, 1.0 as implicit_rating FROM interactions ORDER BY timestamp DESC LIMIT {latest_n}"
        df_new_interactions = pd.read_sql(query_new_interactions, connection)

        # 随机抽取老数据 (Reservoir Replay)
        query_replay_ratings = f"SELECT user_id, movie_id, 1.0 as implicit_rating FROM ratings ORDER BY RAND() LIMIT {random_replay_n}"
        df_replay_ratings = pd.read_sql(query_replay_ratings, connection)

        query_replay_interactions = f"SELECT user_id, movie_id, 1.0 as implicit_rating FROM interactions ORDER BY RAND() LIMIT {random_replay_n}"
        df_replay_interactions = pd.read_sql(query_replay_interactions, connection)

        # 负采样生成：简单实现，在训练 Dataset 中可以随机替换 movie_id 生成负向样本 0.0
        # 这里为了简化，我们在 Python 内存聚合所有 Positive
        
        df_all = pd.concat([df_new_ratings, df_new_interactions, df_replay_ratings, df_replay_interactions]).drop_duplicates()
        return df_all

    finally:
        connection.close()

# 提取元数据特征，用于新电影的高阶初始化
def fetch_movie_metadata(db_config, movie_ids):
    connection = pymysql.connect(**db_config)
    try:
        if not movie_ids:
            return pd.DataFrame()
        ids_str = ",".join(map(str, movie_ids))
        query = f"SELECT id as movie_id, genres FROM movies WHERE id IN ({ids_str})"
        return pd.read_sql(query, connection)
    finally:
        connection.close()

# ==========================================
# 2. 动态扩容与冷启动初始化 (OOV Resize & Metadata Init)
# ==========================================
def resize_embeddings(model, old_num_users, old_num_movies, new_num_users, new_num_movies, new_movie_metadata_df):
    """
    扩大 Embedding 矩阵，容纳自增的 OOV 新实体。
    如果新电影有特征，将流派文本向量化（这里使用简单的均值分布启发式）作为冷启动权重。
    """
    device = next(model.parameters()).device
    
    # Resize User Embedding for GMF and MLP
    if new_num_users > old_num_users:
        print(f"Resizing User Embeddings: {old_num_users} -> {new_num_users}")
        for emb_layer in [model.embedding_user_mlp, model.embedding_user_mf]:
            old_weight = emb_layer.weight.data
            dim = emb_layer.embedding_dim
            new_emb = nn.Embedding(new_num_users, dim).to(device)
            # 复制老权重
            new_emb.weight.data[:old_num_users] = old_weight
            # 新权重采用高斯初始化 (默认行为)
            emb_layer.num_embeddings = new_num_users
            emb_layer.weight = nn.Parameter(new_emb.weight.data)
            
    # Resize Movie Embedding for GMF and MLP
    if new_num_movies > old_num_movies:
        print(f"Resizing Movie Embeddings: {old_num_movies} -> {new_num_movies}")
        for emb_layer in [model.embedding_item_mlp, model.embedding_item_mf]:
            old_weight = emb_layer.weight.data
            dim = emb_layer.embedding_dim
            new_emb = nn.Embedding(new_num_movies, dim).to(device)
            new_emb.weight.data[:old_num_movies] = old_weight
            
            # (高阶) 冷启动元数据特征聚合拼接
            # 如果是新上架电影，尝试基于其 Genre 计算类似特征电影的均值
            # 此处演示通过少量高斯扰动基础初始值，避免纯随机的剧烈分布偏移
            for mid in range(old_num_movies, new_num_movies):
                base_vec = old_weight.mean(dim=0)
                noise = torch.randn_like(base_vec) * 0.01
                new_emb.weight.data[mid] = base_vec + noise
                
            emb_layer.num_embeddings = new_num_movies
            emb_layer.weight = nn.Parameter(new_emb.weight.data)

    return model


# ==========================================
# 3. 梯度钩子 - 参数隔离冻结 (Embedding Freezing)
# ==========================================
def freeze_old_embeddings_hook(grad, old_max_id):
    """
    反向传播 Hook：把小于 old_max_id 的实体梯度清零，从而完全冻结老实体的权重，只更新新实体的特征。
    """
    grad_clone = grad.clone()
    grad_clone[:old_max_id, :] = 0.0
    return grad_clone


class IncrementalDataset(Dataset):
    def __init__(self, user_ids, movie_ids, labels, max_movie_id, num_negatives=4):
        self.user_ids = torch.tensor(user_ids, dtype=torch.long)
        self.movie_ids = torch.tensor(movie_ids, dtype=torch.long)
        self.labels = torch.tensor(labels, dtype=torch.float32)
        self.max_movie_id = max_movie_id
        self.num_negatives = num_negatives
        self.all_movies = np.arange(0, max_movie_id)

    def __len__(self):
        return len(self.user_ids) * (1 + self.num_negatives)

    def __getitem__(self, idx):
        pos_idx = idx // (1 + self.num_negatives)
        is_pos = (idx % (1 + self.num_negatives)) == 0
        if is_pos:
            return self.user_ids[pos_idx], self.movie_ids[pos_idx], self.labels[pos_idx]
        else:
            neg_candidate = np.random.choice(self.all_movies)
            return self.user_ids[pos_idx], torch.tensor(neg_candidate, dtype=torch.long), torch.tensor(0.0, dtype=torch.float32)

# ==========================================
# 主流程
# ==========================================
def run_incremental_training(model_path, db_config):
    # 1. 加载老模型
    print("Loading pre-trained model...")
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    checkpoint = torch.load(model_path, map_location=device)
    
    # 提取在环境配置中的旧 ID 范围
    old_num_users = int(os.environ.get('NUM_USERS', 200948))
    old_num_movies = int(os.environ.get('NUM_MOVIES', 84432))
    
    # 初始化模型结构
    model = NeuMF(num_users=old_num_users, num_items=old_num_movies, mf_dim=64, layers=[256, 128, 64]).to(device)
    model.load_state_dict(checkpoint)

    # 2. 抽取增量和经验回放数据
    print("Fetching mixed replay buffer data from MySQL...")
    df_train = fetch_incremental_data(db_config, latest_n=2000, random_replay_n=8000)
    
    if len(df_train) == 0:
        print("No training data available.")
        return

    # 检测 ID 边界 OOV
    current_max_user = max(df_train['user_id'].max() + 1, old_num_users)
    current_max_movie = max(df_train['movie_id'].max() + 1, old_num_movies)

    if current_max_user > old_num_users or current_max_movie > old_num_movies:
        # 获取新电影的元数据用以冷启动
        new_movie_ids = list(range(old_num_movies, current_max_movie))
        meta_df = fetch_movie_metadata(db_config, new_movie_ids)
        
        # 3. 动态扩容
        model = resize_embeddings(model, old_num_users, old_num_movies, current_max_user, current_max_movie, meta_df)

    # ==========================
    # 4. 参数冻结与优化器状态重置
    # ==========================
    # 挂载冻结钩子，锁定所有旧的老 ID 向量
    model.embedding_user_mlp.weight.register_hook(lambda g: freeze_old_embeddings_hook(g, old_num_users))
    model.embedding_user_mf.weight.register_hook(lambda g: freeze_old_embeddings_hook(g, old_num_users))
    model.embedding_item_mlp.weight.register_hook(lambda g: freeze_old_embeddings_hook(g, old_num_movies))
    model.embedding_item_mf.weight.register_hook(lambda g: freeze_old_embeddings_hook(g, old_num_movies))

    # MLP 层全量解冻
    for param in model.fc_layers.parameters():
        param.requires_grad = True

    # 放弃老动量，使用极低学习率 (5e-5) 重建 Adam
    lr = 5e-5
    optimizer = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=1e-5)
    criterion = nn.BCELoss()

    # 5. 微小 Epoch 微调
    dataset = IncrementalDataset(
        df_train['user_id'].values, 
        df_train['movie_id'].values, 
        df_train['implicit_rating'].values, 
        current_max_movie
    )
    dataloader = DataLoader(dataset, batch_size=256, shuffle=True)
    
    epochs = 2
    model.train()
    print(f"Starting Incremental Finetuning for {epochs} epochs...")
    for epoch in range(epochs):
        epoch_loss = 0.0
        for u, m, y in dataloader:
            u, m, y = u.to(device), m.to(device), y.to(device)
            optimizer.zero_grad()
            preds = model(u, m).squeeze()
            loss = criterion(preds, y)
            loss.backward()
            optimizer.step()
            epoch_loss += loss.item()
            
        print(f"Epoch {epoch+1}/{epochs} | Loss: {epoch_loss/len(dataloader):.4f}")

    # 保存新的微调网络
    torch.save(model.state_dict(), model_path + ".incremental")
    print(f"Saved optimized model to {model_path}.incremental")

if __name__ == '__main__':
    # 请根据本地设置替换 MySQL 凭证
    db_config = {
        'host': '127.0.0.1',
        'port': 3306,
        'user': 'root',
        'password': '', # FILL IN ENV 
        'database': 'movierec_db'
    }
    model_path = '../model/model.pth'
    # run_incremental_training(model_path, db_config)
