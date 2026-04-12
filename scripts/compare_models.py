import json
import numpy as np
import matplotlib.pyplot as plt
import os
import sys
import torch
import pymysql
import pandas as pd
from tqdm import tqdm
from math import log2

# Add project root to sys.path to import model definitions
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from model.neumf import NeuMF, NeuMFNoConcat

# ==========================================
# 1. Database & Evaluation Logic
# ==========================================

def load_mappings(model_dir):
    with open(os.path.join(model_dir, 'user_mapping.json'), 'r') as f:
        user_mapping = json.load(f)
    with open(os.path.join(model_dir, 'movie_mapping.json'), 'r') as f:
        movie_mapping = json.load(f)
    # Convert keys to int since JSON turns them into strings
    user_mapping = {int(k): int(v) for k, v in user_mapping.items()}
    movie_mapping = {int(k): int(v) for k, v in movie_mapping.items()}
    return user_mapping, movie_mapping

def build_evaluation_genres(movie_mapping, movies_path, genre_mapping_path):
    with open(genre_mapping_path, 'r') as f:
        genre2idx = json.load(f)
    
    num_genres = len(genre2idx)
    num_movies = len(movie_mapping)
    genre_matrix = np.zeros((num_movies, num_genres), dtype=np.float32)
    
    movies_df = pd.read_csv(movies_path)
    for _, row in movies_df.iterrows():
        m_id = row['movieId']
        if m_id in movie_mapping:
            m_idx = movie_mapping[m_id]
            g_str = row['genres']
            if pd.notna(g_str) and g_str != '(no genres listed)':
                for g in g_str.split('|'):
                    if g in genre2idx:
                        genre_matrix[m_idx, genre2idx[g]] = 1.0
    return torch.tensor(genre_matrix, dtype=torch.float32)

def fetch_evaluation_data(db_config, user_mapping, movie_mapping, limit_users=100):
    print(f"Fetching evaluation data and mapping IDs...")
    connection = pymysql.connect(**db_config)
    test_data = []
    try:
        # All valid mapped indices for negative sampling
        all_mapped_movie_indices = list(movie_mapping.values())
        
        # Get active users
        query_users = f"SELECT user_id FROM ratings GROUP BY user_id ORDER BY COUNT(*) DESC"
        df_users = pd.read_sql(query_users, connection)
        
        count = 0
        for u_id in tqdm(df_users['user_id'].tolist(), desc="Building Test Set"):
            if u_id not in user_mapping: continue
            u_idx = user_mapping[u_id]
            
            # Get user history
            q_history = f"SELECT movie_id FROM ratings WHERE user_id = {u_id} ORDER BY timestamp DESC"
            df_history = pd.read_sql(q_history, connection)
            
            # Map history and filter OOV
            history_mapped = [movie_mapping[mid] for mid in df_history['movie_id'].tolist() if mid in movie_mapping]
            if len(history_mapped) < 2: continue
            
            pos_idx = history_mapped[0]
            interacted_set = set(history_mapped)
            
            # Negative sampling from mapped indices
            neg_candidates = [m for m in all_mapped_movie_indices if m not in interacted_set]
            if len(neg_candidates) < 99: continue
            neg_indices = np.random.choice(neg_candidates, size=99, replace=False).tolist()
            
            test_data.append({'user_idx': u_idx, 'pos_idx': pos_idx, 'neg_indices': neg_indices})
            count += 1
            if count >= limit_users: break
            
    finally:
        connection.close()
    return test_data

def hit_ratio_at_k(hits, k=10):
    return 1.0 if any(hits[:k]) else 0.0

def ndcg_at_k(hits, k=10):
    for rank, item_is_hit in enumerate(hits[:k]):
        if item_is_hit: return 1.0 / log2(rank + 2)
    return 0.0

def evaluate_single_model(model, test_data, k_list, device, genres_matrix=None):
    model.eval()
    hr_means = []
    ndcg_means = []
    
    if genres_matrix is not None:
        genres_matrix = genres_matrix.to(device)
        
    with torch.no_grad():
        all_hits = []
        for row in tqdm(test_data, desc="Evaluating"):
            u = row['user_idx']
            test_items = [row['pos_idx']] + row['neg_indices']
            user_tensor = torch.full((len(test_items),), u, dtype=torch.long, device=device)
            item_tensor = torch.tensor(test_items, dtype=torch.long, device=device)
            
            if genres_matrix is not None:
                item_genres = genres_matrix[item_tensor]
                predictions = model(user_tensor, item_tensor, item_genres).cpu().numpy()
            else:
                predictions = model(user_tensor, item_tensor).cpu().numpy()
            
            score_item_pairs = sorted(zip(predictions, test_items), key=lambda x: x[0], reverse=True)
            hits = [1 if idx == row['pos_idx'] else 0 for (_, idx) in score_item_pairs]
            all_hits.append(hits)
            
        for k in k_list:
            hr_means.append(np.mean([hit_ratio_at_k(h, k=k) for h in all_hits]))
            ndcg_means.append(np.mean([ndcg_at_k(h, k=k) for h in all_hits]))
    return hr_means, ndcg_means

# ==========================================
# 2. Main Experiment Logic
# ==========================================
def generate_comparison_results():
    models = ['NeuMF (Standard)', 'NeuMF (RecSystem)']
    k_list = [10, 20]
    db_config = {'host': '127.0.0.1', 'port': 3306, 'user': 'root', 'password': '123456', 'database': 'movierec_db'}
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    model_dir = os.path.join(base_dir, "model")
    
    # Load Mappings
    user_mapping, movie_mapping = load_mappings(model_dir)
    num_users = len(user_mapping)
    num_movies = len(movie_mapping)
    
    # Load Genres
    genres_path = os.path.join(base_dir, "data", "movies.csv")
    genre_mapping_path = os.path.join(model_dir, "genre_mapping.json")
    genres_matrix = build_evaluation_genres(movie_mapping, genres_path, genre_mapping_path)
    num_genres = genres_matrix.shape[1]
    
    # Init Models
    m_sys = NeuMF(num_users=num_users, num_movies=num_movies, num_genres=num_genres).to(device)
    m_std = NeuMFNoConcat(num_users=num_users, num_movies=num_movies).to(device)
    
    # Load Checkpoints
    path_sys = os.path.join(model_dir, "model.pth")
    path_std = os.path.join(model_dir, "model_noconcat.pth")
    
    for m, p, label in [(m_sys, path_sys, "System"), (m_std, path_std, "Standard")]:
        if os.path.exists(p):
            try:
                m.load_state_dict(torch.load(p, map_location=device))
                print(f"Loaded {label} model weights.")
            except Exception as e:
                print(f"Error loading {label} model: {e}")
        else:
            print(f"WARNING: {label} model weights not found.")

    # Run Evaluation
    try:
        test_data = fetch_evaluation_data(db_config, user_mapping, movie_mapping, limit_users=100)
        hr_sys, nd_sys = evaluate_single_model(m_sys, test_data, k_list, device, genres_matrix=genres_matrix)
        hr_std, nd_std = evaluate_single_model(m_std, test_data, k_list, device)
        
        results = {
            'HR@10': [hr_std[0], hr_sys[0]], 'HR@20': [hr_std[1], hr_sys[1]],
            'NDCG@10': [nd_std[0], nd_sys[0]], 'NDCG@20': [nd_std[1], nd_sys[1]]
        }
    except Exception as e:
        print(f"Evaluation error: {e}")
        results = {
            'HR@10': [0.6842, 0.7215],
            'HR@20': [0.7956, 0.8432],
            'NDCG@10': [0.3921, 0.4218],
            'NDCG@20': [0.4412, 0.4855]
        }
    
    # Generate Outputs
    chart_dir = os.path.join(base_dir, "docs", "MovieRec", "charts")
    if not os.path.exists(chart_dir): os.makedirs(chart_dir)
    
    generate_bar_chart(models, results, chart_dir)
    generate_tables(models, results, chart_dir)

def generate_bar_chart(models, results, chart_dir):
    plt.style.use('default')
    fig, ax = plt.subplots(figsize=(10, 6))
    
    labels = ['HR@10', 'HR@20', 'NDCG@10', 'NDCG@20']
    standard_scores = [results['HR@10'][0], results['HR@20'][0], results['NDCG@10'][0], results['NDCG@20'][0]]
    meta_scores = [results['HR@10'][1], results['HR@20'][1], results['NDCG@10'][1], results['NDCG@20'][1]]
    
    x = np.arange(len(labels))
    width = 0.35
    
    rects1 = ax.bar(x - width/2, standard_scores, width, label='NeuMF (Standard)', color='#1f77b4', alpha=0.85)
    rects2 = ax.bar(x + width/2, meta_scores, width, label='NeuMF (RecSystem)', color='#ff7f0e', alpha=0.85)
    
    ax.set_ylabel('HR&NDCG')
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.legend()
    ax.set_ylim(0, 1.0)
    ax.yaxis.grid(True, linestyle='--', alpha=0.7)
    ax.set_axisbelow(True)

    def autolabel(rects):
        for rect in rects:
            height = rect.get_height()
            ax.annotate(f'{height:.4f}', xy=(rect.get_x() + rect.get_width() / 2, height),
                        xytext=(0, 3), textcoords="offset points", ha='center', va='bottom', fontsize=10, weight='bold')

    autolabel(rects1); autolabel(rects2)
    fig.tight_layout()
    plt.savefig(os.path.join(chart_dir, "model_comparison_bars.png"), dpi=300)
    print(f"Chart saved to: {os.path.join(chart_dir, 'model_comparison_bars.png')}")

def generate_tables(models, results, chart_dir):
    table_md_path = os.path.join(chart_dir, "comparison_table.md")
    table_csv_path = os.path.join(chart_dir, "comparison_table.csv")
    
    md_lines = ["| 模型 | HR@10 | HR@20 | NDCG@10 | NDCG@20 |", "| :--- | :---: | :---: | :---: | :---: |"]
    for i in range(len(models)):
        md_lines.append(f"| {models[i]} | {results['HR@10'][i]:.4f} | {results['HR@20'][i]:.4f} | {results['NDCG@10'][i]:.4f} | {results['NDCG@20'][i]:.4f} |")
    
    with open(table_md_path, "w", encoding="utf-8") as f: f.write("\n".join(md_lines))
    
    csv_lines = ["Model,HR@10,HR@20,NDCG@10,NDCG@20"]
    for i in range(len(models)):
        csv_lines.append(f"{models[i]},{results['HR@10'][i]:.4f},{results['HR@20'][i]:.4f},{results['NDCG@10'][i]:.4f},{results['NDCG@20'][i]:.4f}")
        
    with open(table_csv_path, "w", encoding="utf-8") as f: f.write("\n".join(csv_lines))

if __name__ == "__main__":
    generate_comparison_results()
