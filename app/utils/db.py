from contextlib import contextmanager
from app.extensions import db_pool

# Use "with get_cursor() as cur:" to write/read to postgres
@contextmanager
def get_cursor():
    conn = db_pool.getconn() # Finds avaliable slot to init connection
    try:
        cur = conn.cursor() # Create cursor instance
        yield cur
        conn.commmit() # Commits Postgres write (won't do anything on reads)
    except Exception:
        conn.rollback() # Undo any writes if error
        raise
    finally:
        cur.close() 
        db_pool.putconn(conn) # Marks slot as free to use again
