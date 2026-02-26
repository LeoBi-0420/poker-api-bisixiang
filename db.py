# db.py
import os
import psycopg
from dotenv import load_dotenv
load_dotenv()


def get_conn():
    """
    EN: Create and return a DB connection using DATABASE_URL env var.
    CN: 用环境变量 DATABASE_URL 创建并返回一个数据库连接。
    """
    db_url = os.getenv("DATABASE_URL")

    if not db_url:
        raise RuntimeError(
            "DATABASE_URL is not set.\n"
            "Example:\n"
            "export DATABASE_URL='postgresql://postgres:YOUR_PASSWORD@localhost:5432/postgres'"
        )

    # autocommit=True makes simple SELECTs easy (no manual commit needed)
    # autocommit=True 让查询更省事（先不讲事务）
    return psycopg.connect(db_url, autocommit=True)
