import pandas as pd
import numpy as np
import redis
import json
from sklearn.metrics import jaccard_score
from tqdm import tqdm
import os

# 配置
MOVIES_CSV = 'data/movies.csv'
REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
TOP_K = 20

def generate_i2i():
    print(f"Loading movies from {MOVIES_CSV}...")
    df = pd.read_csv(MOVIES_CSV)
    
    # 1. 提取所有流派并进行 One-Hot 编码
    print("Encoding genres...")
    genres_series = df['genres'].str.get_dummies(sep='|')
    movie_ids = df['movieId'].values
    genre_matrix = genres_series.values
    
    # 2. 计算 Jaccard 相似度 (由于数据量可能较大，采用分批计算或简化逻辑)
    # 对于 8万+ 电影，全量矩阵 O(N^2) 会 OOM
    # 优化策略：仅计算具有相同流派的候选集
    
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    pipe = r.pipeline()
    
    print("Calculating similarity and uploading to Redis...")
    # 由于是基于流派的粗颗粒度相似度，我们可以简单地通过流派重合度来排序
    # 这里采用一种内存友好的方式：
    
    for i in tqdm(range(len(df))):
        target_id = movie_ids[i]
        target_vector = genre_matrix[i]
        
        # 只计算与当前影片有至少一个共同流派的影片
        # 为了极速实现，我们这里简单计算逻辑：
        # 寻找与 target_vector 相似度最高的前 K 个
        
        # 计算所有影片与 target_vector 的 dot product (流派重合数)
        scores = np.dot(genre_matrix, target_vector)
        
        # 排除自身
        scores[i] = -1
        
        # 获取 Top K 索引
        top_indices = np.argpartition(scores, -TOP_K)[-TOP_K:]
        # 按分数降序排列
        top_indices = top_indices[np.argsort(scores[top_indices])][::-1]
        
        sim_movie_ids = movie_ids[top_indices].tolist()
        
        # 存储到 Redis: Key = movie_sim:{id}, Value = List
        pipe.delete(f"movie_sim:{target_id}")
        if sim_movie_ids:
            pipe.lpush(f"movie_sim:{target_id}", *sim_movie_ids)
        
        # 每 500 条提交一次 pipeline
        if i % 500 == 0:
            pipe.execute()
            
    pipe.execute()
    print("Done! I2I Similarity matrix uploaded to Redis.")

if __name__ == "__main__":
    try:
        generate_i2i()
    except Exception as e:
        print(f"Error: {e}")
