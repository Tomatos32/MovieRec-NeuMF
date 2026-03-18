#!/usr/bin/env python3
"""
extract_genres.py
-----------------
遍历 MovieRec 数据库 movies 表中的 genres 列，
统计所有出现过的电影类型，并输出排序后的唯一类型列表。

用法:
  python extract_genres.py

依赖:
  pip install mysql-connector-python
  (或) pip install pymysql

配置: 修改下方 DB_CONFIG 中的连接参数以匹配你的环境。
"""

import os
import sys
from collections import Counter

# ---- 数据库连接配置 ----
DB_CONFIG = {
    "host":     os.getenv("DB_HOST",     "localhost"),
    "port":     int(os.getenv("DB_PORT", "3306")),
    "user":     os.getenv("DB_USER",     "root"),
    "password": os.getenv("DB_PASSWORD", "123456"),
    "database": os.getenv("DB_NAME",     "movierec_db"),
}

GENRE_SEPARATOR = "|"   # movies.genres 列中类型的分隔符，例如 "Action|Adventure|Sci-Fi"


def get_genres_from_db(config: dict) -> list[tuple[str, int]]:
    """
    连接 MySQL，查询 movies.genres 列，
    拆分管道符后统计每种类型出现次数，返回 (genre, count) 列表（按出现次数降序）。
    """
    try:
        import mysql.connector as mc
        conn = mc.connect(**config)
    except ImportError:
        # 回退到 pymysql
        try:
            import pymysql
            cfg = config.copy()
            conn = pymysql.connect(**cfg)
        except ImportError:
            sys.exit(
                "错误: 请先安装数据库驱动。\n"
                "  pip install mysql-connector-python\n"
                "  或\n"
                "  pip install pymysql"
            )

    counter: Counter = Counter()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT genres FROM movies WHERE genres IS NOT NULL AND genres != ''"
        )
        for (genres_str,) in cursor:
            for g in genres_str.split(GENRE_SEPARATOR):
                g = g.strip()
                if g:
                    counter[g] += 1
    finally:
        cursor.close()
        conn.close()

    return counter.most_common()


def main():
    print("=== MovieRec 电影类型提取脚本 ===\n")
    print(f"连接数据库: {DB_CONFIG['user']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}")
    print("-" * 48)

    genre_counts = get_genres_from_db(DB_CONFIG)

    if not genre_counts:
        print("未找到任何有效的类型数据，请确认数据库连接和数据导入情况。")
        return

    print(f"共发现 {len(genre_counts)} 种唯一类型:\n")
    print(f"{'类型':<30} {'出现次数':>8}")
    print("-" * 40)
    for genre, count in genre_counts:
        print(f"{genre:<30} {count:>8}")

    sorted_genres = sorted(g for g, _ in genre_counts)
    print("\n--- 按字母排序的唯一类型列表（可直接复制到前端）---")
    print(sorted_genres)

    # 同时写入 JSON 文件，方便前端静态引用
    import json
    output = {
        "genres": sorted_genres,
        "stats": {g: c for g, c in genre_counts}
    }
    out_path = os.path.join(os.path.dirname(__file__), "genres.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\n结果已保存到: {out_path}")


if __name__ == "__main__":
    main()
