from contextlib import contextmanager
from app import extensions

# Use "with get_cursor() as cur:" to write/read to postgres
@contextmanager
def get_cursor():
    conn = extensions.db_pool.getconn() # Finds avaliable slot to init connection
    try:
        cur = conn.cursor() # Create cursor instance
        yield cur
        conn.commit() # Commits Postgres write (won't do anything on reads)
    except Exception:
        conn.rollback() # Undo any writes if error
        raise
    finally:
        cur.close() 
        extensions.db_pool.putconn(conn) # Marks slot as free to use again
