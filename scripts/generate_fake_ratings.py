import pymysql
import random
from datetime import datetime
import pandas as pd

def generate_fake_users_and_ratings(db_config, num_users=10, ratings_per_user=20):
    """
    批量生成带有特定偏好的虚假用户评分数据，用于测试系统的增量训练与个性化推荐功能。
    """
    connection = pymysql.connect(**db_config)
    cursor = connection.cursor()
    
    try:
        # 1. 提取所有喜剧电影和非喜剧电影 (作为示例偏好: 喜剧)
        print("Fetching movie pool from database...")
        cursor.execute("SELECT id, genres FROM movies")
        movies = cursor.fetchall() # ((id, 'Comedy|Romance'), ...)
        
        comedy_movies = [m[0] for m in movies if m[1] and 'Comedy' in m[1]]
        other_movies = [m[0] for m in movies if m[1] and 'Comedy' not in m[1]]
        
        if not comedy_movies:
            print("Error: No comedy movies found!")
            return
            
        print(f"Found {len(comedy_movies)} comedy and {len(other_movies)} other movies.")
        
        # 查找当前最大 user_id
        cursor.execute("SELECT MAX(id) FROM users")
        max_user_id = cursor.fetchone()[0]
        if max_user_id is None:
            max_user_id = 200948 # 如果为空则以 movielens 为基准
            
        new_users = []
        new_ratings = []
        timestamp = int(datetime.now().timestamp() * 1000)
        
        # 2. 生成新用户并注入到数据库
        for i in range(1, num_users + 1):
            new_uid = max_user_id + i
            username = f"test_comedy_fan_{new_uid}"
            
            # 插入用户表 (伪造哈希密码)
            cursor.execute(
                "INSERT INTO users (id, username, password_hash, email) VALUES (%s, %s, %s, %s)",
                (new_uid, username, "$10$s7dXebGpmFMUPvHLoq6bL.08i/UU4RjITetWoDiyAV0iYaTJzWJDK", f"{username}@test.com")
            )
            new_users.append(new_uid)
            
            # 生成打分：80% 给喜剧电影打 4.5~5分，20% 随机电影打 1~3分
            num_comedy = int(ratings_per_user * 0.8)
            num_other = ratings_per_user - num_comedy
            
            # 抽样
            sampled_comedy = random.sample(comedy_movies, num_comedy)
            sampled_other = random.sample(other_movies, num_other) if other_movies else []
            
            for mid in sampled_comedy:
                # 高分偏好
                rating = random.choice([4.0, 4.5, 5.0])
                new_ratings.append((new_uid, mid, rating, timestamp))
                
            for mid in sampled_other:
                # 随机甚至低分
                rating = random.choice([1.0, 2.0, 3.0, 3.5])
                new_ratings.append((new_uid, mid, rating, timestamp))
                
        # 3. 批量插入评分
        print(f"Inserting {len(new_users)} new users and {len(new_ratings)} ratings...")
        
        insert_rating_sql = "INSERT INTO ratings (user_id, movie_id, rating, timestamp) VALUES (%s, %s, %s, %s)"
        cursor.executemany(insert_rating_sql, new_ratings)
        
        # 提交事务
        connection.commit()
        print("Success! Data injected. Now you can run incremental training.")
        
    except Exception as e:
        connection.rollback()
        print(f"Database error: {e}")
    finally:
        cursor.close()
        connection.close()

if __name__ == '__main__':
    # 填入您的 MySQL 环境凭证
    db_config = {
        'host': '127.0.0.1',
        'port': 3306,
        'user': 'root',
        'password': '', # 数据库密码
        'database': 'movierec_db'
    }
    
    # 执行生成：10 个喜爱喜剧的新用户，每人打分 20 部电影
    generate_fake_users_and_ratings(db_config, num_users=10, ratings_per_user=20)
