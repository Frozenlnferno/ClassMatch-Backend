from contextlib import contextmanager
from app import extensions

@contextmanager
def db_conn():
    conn = extensions.db_pool.getconn()
    try:
        yield conn
    finally:
        extensions.db_pool.putconn(conn)
