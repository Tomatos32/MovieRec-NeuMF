import os
import sys
import torch
import pymysql
import redis
from tqdm import tqdm
from datetime import datetime

# 兼容引用 model.neumf
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    from model.neumf import NeuMF
except ImportError:
    pass

def create_mysql_table_if_not_exists(cursor):
    """建表：如果持久化表不存在则新建"""
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS offline_recommendations (
            user_id INT NOT NULL,
            movie_id INT NOT NULL,
            score FLOAT NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, movie_id),
            INDEX idx_user_score (user_id, score DESC)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """)

def batch_recommender(db_config, redis_args, model_path, target_users=3000, top_k=20):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device}")
    
    # 1. 动态加载模型并嗅探矩阵大小
    state_dict = torch.load(model_path, map_location=device)
    num_users = state_dict['embedding_user_mlp.weight'].shape[0]
    num_movies = state_dict['embedding_movie_mlp.weight'].shape[0]
    
    print(f"Model bounds loaded: Users={num_users}, Movies={num_movies}")
    
    model = NeuMF(num_users=num_users, num_movies=num_movies)
    model.load_state_dict(state_dict)
    model.to(device)
    model.eval()
    
    # 2. 数据库连接
    connection = pymysql.connect(**db_config)
    cursor = connection.cursor()
    create_mysql_table_if_not_exists(cursor)
    
    r = redis.Redis(**redis_args)
    pipe = r.pipeline()
    
    try:
        # 为了避免算力爆炸 (例如全库乘积为百亿次), 我们采用业界标准的双塔架构做法：
        # 先取全站前 1000 个比较主流或特征突出的商品作为 Offline Ranking 候选池进行精排。
        # 实际工业界由于物品上千万，都会先经过一层粗排系统。
        print("Fetching Top 1000 candidate movies from MySQL constraint...")
        cursor.execute("""
            SELECT movie_id FROM ratings 
            GROUP BY movie_id 
            ORDER BY COUNT(*) DESC 
            LIMIT 1000
        """)
        candidate_pool = [row[0] for row in cursor.fetchall()]
        
        # 过滤可能存在于 DB 但却越界了的 movieId
        valid_candidates = [mid for mid in candidate_pool if 0 <= mid < num_movies]
        candidate_tensor = torch.tensor(valid_candidates, dtype=torch.long).to(device)
        num_candidates = len(valid_candidates)
        
        print(f"Starting Offline Batch Inference for Top {target_users} Active Users...")
        
        # 我们限制执行前 target_users 人（也就是压测用户）
        batch_mysql_data = []
        
        # tqdm 显示计算进度
        for uid in tqdm(range(1, min(target_users + 1, num_users))):
            
            # 使用 PyTorch 矢量化一次性计算该用户对 1000 部流行电影的分数
            users_tensor = torch.full((num_candidates,), uid, dtype=torch.long).to(device)
            
            with torch.no_grad():
                scores = model(users_tensor, candidate_tensor)
            
            # 排序取前 20 首选
            top_k_scores, top_k_indices = torch.topk(scores, top_k)
            
            top_k_movie_ids = candidate_tensor[top_k_indices].cpu().numpy().tolist()
            top_k_scores_list = top_k_scores.cpu().numpy().tolist()
            
            # (A) 准备录入 Redis rec:offline:{userId} [使用 List 推送以极速读取]
            redis_key = f"rec:offline:{uid}"
            pipe.delete(redis_key)
            pipe.rpush(redis_key, *top_k_movie_ids) # 顺序排列从左到右
            
            # (B) 准备录入 MySQL
            for mid, score in zip(top_k_movie_ids, top_k_scores_list):
                batch_mysql_data.append((uid, mid, float(score)))
                
            # 每 500 个 User 递交一次
            if len(batch_mysql_data) >= 500 * top_k:
                cursor.executemany("""
                    REPLACE INTO offline_recommendations (user_id, movie_id, score) 
                    VALUES (%s, %s, %s)
                """, batch_mysql_data)
                connection.commit()
                batch_mysql_data.clear()
                pipe.execute() # 推送入 Redis
                
        # 收尾剩余的数据
        if batch_mysql_data:
            cursor.executemany("""
                REPLACE INTO offline_recommendations (user_id, movie_id, score) 
                VALUES (%s, %s, %s)
            """, batch_mysql_data)
            connection.commit()
            pipe.execute()

        print("⚡ Offline Inference Completed and Cached successfully to BOTH MySQL and Redis!")

    except Exception as e:
        connection.rollback()
        print(f"Error occurred: {e}")
    finally:
        cursor.close()
        connection.close()

if __name__ == '__main__':
    db_config = {
        'host': '127.0.0.1',
        'port': 3306,
        'user': 'root',
        'password': '123456', 
        'database': 'movierec_db'
    }
    redis_args = {
        'host': 'localhost',
        'port': 6379,
        'decode_responses': True
    }
    model_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'model', 'model.pth'))
    
    # 你的活跃用户数量定义为前 3000
    batch_recommender(db_config, redis_args, model_path, target_users=3000, top_k=20)
