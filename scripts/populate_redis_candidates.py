import pymysql
import redis
import math
from tqdm import tqdm
import os

def calculate_wilson_score(positive, total):
    """
    计算威尔逊置信区间下限（Wilson Score Lower Bound）
    参数：
    - positive: 好评数 (如 rating >= 4.0)
    - total: 总评价数
    """
    positive = float(positive)
    total = float(total)
    if total == 0:
        return 0.0
    # 常数 z = 1.96 对应 95% 置信度
    z = 1.96
    phat = 1.0 * positive / total
    return (phat + z*z/(2*total) - z * math.sqrt((phat*(1-phat)+z*z/(4*total))/total)) / (1+z*z/total)

def populate_redis_candidates(db_config, redis_host='localhost', redis_port=6379, max_users=1050):
    print("Connecting to MySQL and Redis...")
    connection = pymysql.connect(**db_config)
    cursor = connection.cursor()
    r = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)
    pipe = r.pipeline()
    
    try:
        # ==========================================
        # 1. 计算全局历史热门榜单 (Wilson Score)
        # ==========================================
        print("Calculating Global Popular Candidates (Wilson Score)...")
        # 这次查询算出所有电影的大于等于4星的评价次数，和总评价次数
        cursor.execute("""
            SELECT movie_id, 
                   SUM(CASE WHEN rating >= 4.0 THEN 1 ELSE 0 END) as pos_reviews, 
                   COUNT(*) as total_reviews
            FROM ratings 
            GROUP BY movie_id
        """)
        movies = cursor.fetchall()
        
        movie_scores = {}
        for mid, pos, total in movies:
            score = calculate_wilson_score(pos, total)
            movie_scores[mid] = score
            
        # 排序取前 200 个最权威的高分热门大片
        top_movies = sorted(movie_scores.items(), key=lambda x: x[1], reverse=True)[:200]
        
        # 写入 Redis ZSET 'rec:popular:topk'
        pipe.delete('rec:popular:topk') # 清理遗留
        for mid, score in top_movies:
            # redis-py ZADD format: {key: {member: score}} for older versions
            # But the newer format is: zadd(name, mapping)
            pipe.zadd('rec:popular:topk', {str(mid): float(score)})
        
        print(f"Top {len(top_movies)} popular movies injected into Redis ZSET.")

        # ==========================================
        # 2. 为压测用户群体填充【近期互动历史】
        # ==========================================
        print(f"Preloading recent history for UserID 1 ~ {max_users}...")
        
        # 为了高效，我们可以直接对那些活跃库拉取
        for uid in tqdm(range(1, max_users + 1), desc="Caching User Recent"):
            cursor.execute(f"""
                SELECT movie_id FROM ratings 
                WHERE user_id = {uid} 
                ORDER BY timestamp DESC 
                LIMIT 5
            """)
            recent_movies = cursor.fetchall()
            if recent_movies:
                # 倒转顺序变成最新在前的列表逻辑：Redis lpush 压栈
                movie_ids = [str(m[0]) for m in recent_movies]
                
                redis_list_key = f"user_recent:{uid}"
                pipe.delete(redis_list_key)
                
                # lpush 允许传入多个参数，把最新阅读的片子插入头部
                pipe.lpush(redis_list_key, *movie_ids)

        # 统一提交管道操作
        pipe.execute()
        print("Done! Candidate Pool Base Data loaded successfully. Pipeline is ready.")

    except Exception as e:
        print(f"Runtime Error: {e}")
    finally:
        cursor.close()
        connection.close()

if __name__ == '__main__':
    # MySQL 环境凭证
    db_config = {
        'host': '127.0.0.1',
        'port': 3306,
        'user': 'root',
        'password': '123456', # FILL IN YOUR DATABASE PASSWORD
        'database': 'movierec_db'
    }
    
    # 执行填充逻辑，主要服务压测群
    populate_redis_candidates(db_config, max_users=1050)
