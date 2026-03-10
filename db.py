# db.py
import os
import psycopg
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from dotenv import load_dotenv
load_dotenv()


def _with_sslmode_if_needed(db_url: str) -> str:
    """
    Ensure remote connections have sslmode=require when not explicitly configured.
    """
    parsed = urlparse(db_url)
    host = (parsed.hostname or "").lower()
    is_local = host in {"localhost", "127.0.0.1"} or host.endswith(".local")

    if is_local:
        return db_url

    query_pairs = dict(parse_qsl(parsed.query, keep_blank_values=True))
    if "sslmode" in query_pairs:
        return db_url

    query_pairs["sslmode"] = "require"
    new_query = urlencode(query_pairs)
    return urlunparse(parsed._replace(query=new_query))


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

    # Render/external Postgres commonly requires SSL for client connections.
    # Render/外部 Postgres 常要求开启 SSL。
    db_url = _with_sslmode_if_needed(db_url)

    # autocommit=True makes simple SELECTs easy (no manual commit needed)
    # autocommit=True 让查询更省事（先不讲事务）
    return psycopg.connect(db_url, autocommit=True)
