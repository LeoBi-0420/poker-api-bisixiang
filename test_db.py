from db import get_conn

conn = get_conn()
print("Connected!")
conn.close()
