from contextlib import contextmanager
from app import extensions
from app.utils.logger import get_logger

logger = get_logger(__name__)


class _LoggingCursor:
    def __init__(self, cursor):
        self._cursor = cursor
        self.last_query = None
        self.last_operation = None

    def execute(self, query, params=None):
        self.last_query = query
        self.last_operation = "execute"
        if params is None:
            return self._cursor.execute(query)
        return self._cursor.execute(query, params)

    def executemany(self, query, params_seq):
        self.last_query = query
        self.last_operation = "executemany"
        return self._cursor.executemany(query, params_seq)

    def __getattr__(self, item):
        return getattr(self._cursor, item)


def _sanitize_query(query):
    if not query:
        return None
    query = " ".join(str(query).split())
    return query[:500]

# Use "with get_cursor() as cur:" to write/read to postgres
@contextmanager
def get_cursor():
    conn = None
    cur = None
    raw_cursor = None

    conn = extensions.db_pool.getconn() # Finds avaliable slot to init connection
    try:
        raw_cursor = conn.cursor() # Create cursor instance
        cur = _LoggingCursor(raw_cursor)
        yield cur
        conn.commit() # Commits Postgres write (won't do anything on reads)
    except Exception as exc:
        logger.exception(
            "Database operation failed",
            extra={
                "db_operation": getattr(cur, "last_operation", None),
                "query": _sanitize_query(getattr(cur, "last_query", None)),
                "error": str(exc),
            },
        )
        if conn and not conn.closed:
            conn.rollback() # Undo any writes if error
        raise
    finally:
        if raw_cursor is not None:
            raw_cursor.close()
        if conn is not None:
            extensions.db_pool.putconn(conn) # Marks slot as free to use again
