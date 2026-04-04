import os
import torch
import pymysql
import pandas as pd
import numpy as np
from tqdm import tqdm
from math import log2
from neumf import NeuMF

# ==========================================
# 1. 评估数据抽取 (Leave-One-Out 留一法)
# ==========================================
def fetch_evaluation_data(db_config, limit_users=500):
    """
    从 MySQL 中抽取每个活跃用户的最后一条交互记录作为 Test Item，
    并随机拉取 99 个用户未交互过的电影作为 Negative Items（按标准留一法评测环境）。
    """
    print(f"Fetching evaluation data for top {limit_users} users...")
    connection = pymysql.connect(**db_config)
    test_data = [] # [[user_id, pos_item_id, [neg_item_ids...]], ...]
    
    try:
        # 提取活跃用户
        query_users = f"SELECT user_id FROM ratings GROUP BY user_id ORDER BY COUNT(*) DESC LIMIT {limit_users}"
        df_users = pd.read_sql(query_users, connection)
        user_ids = df_users['user_id'].tolist()
        
        # 提取全量电影ID用于负采样
        query_all_movies = "SELECT id FROM movies"
        df_all_movies = pd.read_sql(query_all_movies, connection)
        all_movie_ids = set(df_all_movies['id'].tolist())
        
        for u in tqdm(user_ids, desc="Building Test Set"):
            # 获取用户所有的交互
            q_user_history = f"SELECT movie_id FROM ratings WHERE user_id = {u} ORDER BY timestamp DESC"
            df_history = pd.read_sql(q_user_history, connection)
            if len(df_history) < 2:
                continue # 太少的数据无法做留一法
            
            history_items = df_history['movie_id'].tolist()
            pos_item = history_items[0] # 最新的一条作为正样本
            interacted_set = set(history_items)
            
            # 随机选取 99 个未交互的作为负样本
            uninteracted_items = list(all_movie_ids - interacted_set)
            if len(uninteracted_items) < 99:
                neg_items = uninteracted_items
            else:
                neg_items = np.random.choice(uninteracted_items, size=99, replace=False).tolist()
                
            test_data.append({
                'user': u,
                'pos_item': pos_item,
                'neg_items': neg_items
            })
            
    finally:
        connection.close()
        
    return test_data

# ==========================================
# 2. 指标计算公式定义 (HitRatio & NDCG)
# ==========================================
def hit_ratio_at_k(hits, k=10):
    """
    计算 HR@K:
    如果在 Top-K 中出现了正样本，计为 1，否则为 0
    hits 是布尔值数组，表示每一个排名位置上的物品是否为正样本（对于我们的设定，只会有一个 True）
    """
    for item_is_hit in hits[:k]:
        if item_is_hit:
            return 1.0
    return 0.0

def ndcg_at_k(hits, k=10):
    """
    计算 NDCG@K:
    如果在 top-K 中命中，NDCG = 1 / log2(rank + 1)
    """
    for rank, item_is_hit in enumerate(hits[:k]):
        if item_is_hit:
            return 1.0 / log2(rank + 2) # rank 是从0开始的，所以直接 rank+2（对应排名的 rank+1）
    return 0.0

import matplotlib.pyplot as plt

# ==========================================
# 3. 执行核心评测逻辑
# ==========================================
def evaluate_model(model_path, db_config, k_list=[5, 10, 15, 20]):
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Loading pre-trained model on {device}...")
    
    num_users = int(os.environ.get('NUM_USERS', 200948))
    num_movies = int(os.environ.get('NUM_MOVIES', 84432))
    
    model = NeuMF(num_users=num_users, num_movies=num_movies, mf_dim=64, layers=[256, 128, 64]).to(device)
    try:
        model.load_state_dict(torch.load(model_path, map_location=device))
        model.eval()
    except Exception as e:
        print(f"Failed to load model weights: {e}")
        return

    test_data = fetch_evaluation_data(db_config, limit_users=100)
    if not test_data:
        print("No evaluation data generated.")
        return

    # 存储不同 K 下的结果
    hr_means = []
    ndcg_means = []
    
    with torch.no_grad():
        # 我们先一次性跑完推理得分，再计算不同 K，提升效率
        all_hits = []
        for row in tqdm(test_data, desc="Inferencing"):
            u = row['user']
            test_items = [row['pos_item']] + row['neg_items']
            user_tensor = torch.full((len(test_items),), u, dtype=torch.long, device=device)
            item_tensor = torch.tensor(test_items, dtype=torch.long, device=device)
            predictions = model(user_tensor, item_tensor).cpu().numpy()
            
            score_item_pairs = list(zip(predictions, test_items))
            score_item_pairs.sort(key=lambda x: x[0], reverse=True)
            hits = [1 if item == row['pos_item'] else 0 for (score, item) in score_item_pairs]
            all_hits.append(hits)
            
        for k in k_list:
            hits_list = [hit_ratio_at_k(h, k=k) for h in all_hits]
            ndcg_list = [ndcg_at_k(h, k=k) for h in all_hits]
            hr_means.append(np.mean(hits_list))
            ndcg_means.append(np.mean(ndcg_list))

    print("\n" + "="*40)
    print("======  NeuMF Model Evaluation  ======")
    print("="*40)
    print(f"Test Users count: {len(test_data)}")
    print(f"Top-K\tHit Ratio\tNDCG")
    for i, k in enumerate(k_list):
        print(f"@{k}\t{hr_means[i]:.4f}\t\t{ndcg_means[i]:.4f}")
    print("="*40)

    # 生成图表用于毕设论文
    if not os.path.exists("../docs/MovieRec/charts"):
        os.makedirs("../docs/MovieRec/charts")
        
    plt.figure(figsize=(8, 5))
    plt.plot(k_list, hr_means, marker='o', label='Hit Ratio')
    plt.plot(k_list, ndcg_means, marker='s', label='NDCG')
    plt.xlabel('Top-K')
    plt.ylabel('Score')
    plt.title('NeuMF Model Performance Evaluation')
    plt.legend()
    plt.grid(True, linestyle='--', alpha=0.6)
    
    chart_path = "../docs/MovieRec/charts/model_performance_real.png"
    plt.savefig(chart_path)
    print(f"\nEvaluation chart saved to {chart_path}")

if __name__ == '__main__':
    db_config = {
        'host': '127.0.0.1',
        'port': 3306,
        'user': 'root',
        'password': '123456',
        'database': 'movierec_db'
    }
    model_path = '../model/model.pth'
    evaluate_model(model_path, db_config)
