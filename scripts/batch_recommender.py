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
    
    # 探测 GMF 或 MLP 中的用户/电影 embedding 维度
    if 'embedding_user_mlp.weight' in state_dict:
        num_users = state_dict['embedding_user_mlp.weight'].shape[0]
        num_movies = state_dict['embedding_movie_mlp.weight'].shape[0]
        
        # 探测 num_genres (从 MLP 第一层权重推导)
        latent_dim = 64
        mlp_input_dim = state_dict['mlp_layers.0.weight'].shape[1]
        num_genres = mlp_input_dim - (latent_dim * 2)
        
        print(f"Model bounds loaded: Users={num_users}, Movies={num_movies}, Genres={num_genres}")
    
    model = NeuMF(num_users=num_users, num_movies=num_movies, latent_dim=latent_dim, num_genres=num_genres)
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
        
        # 3. 动态定义“活跃用户” (Active Users)
        # 通过分析 ratings 表，定义活跃用户为：最近参与过电影评分反馈的 Top N 个用户
        print(f"Identifying Top {target_users} Active Users based on recent rating activity...")
        cursor.execute(f"""
            SELECT user_id 
            FROM ratings 
            GROUP BY user_id 
            ORDER BY MAX(timestamp) DESC 
            LIMIT {target_users}
        """)
        active_users = [row[0] for row in cursor.fetchall()]
        
        # 安全过滤：剔除尚未参与本次模型训练（超出 Embedding 范围）的绝对新用户
        valid_active_users = [uid for uid in active_users if 0 <= uid < num_users]
        print(f"Found {len(active_users)} active users, {len(valid_active_users)} are valid within current model bounds.")
        
        print(f"Starting Offline Batch Inference for Active Users...")
        
        batch_mysql_data = []
        
        # 遍历有效活跃用户进行推断
        for uid in tqdm(valid_active_users, desc="Offline Inferring"):
            
            # 使用 PyTorch 矢量化一次性计算该用户对 1000 部流行电影的分数
            users_tensor = torch.full((num_candidates,), uid, dtype=torch.long).to(device)
            
            with torch.no_grad():
                scores = model(users_tensor, candidate_tensor)
            
            # 排序取前 20 首选
            top_k_scores, top_k_indices = torch.topk(scores, top_k)
            
            top_k_movie_ids = candidate_tensor[top_k_indices].cpu().numpy().tolist()
            top_k_scores_list = top_k_scores.cpu().numpy().tolist()
            
            # (A) 准备录入 Redis rec:offline:{userId} [使用 ZSET 以保留分数]
            redis_key = f"rec:offline:{uid}"
            pipe.delete(redis_key)
            # mapping 为 {movieId: score}
            mapping = {str(mid): float(sc) for mid, sc in zip(top_k_movie_ids, top_k_scores_list)}
            pipe.zadd(redis_key, mapping)
            
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
    
    # 执行离线批处理推荐
    # 此处 target_users 指代我们希望为多少个“最近最活跃”的用户提前算好推荐列表
    # 我们设置 3000 人，您可以根据实际服务器内存和算力进行调整
    batch_recommender(db_config, redis_args, model_path, target_users=3000, top_k=20)
