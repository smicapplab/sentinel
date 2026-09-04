import atexit
import os
import psycopg
from psycopg_pool import ConnectionPool
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
# Read-only connection to the Birdseye database for sync extraction
SYNC_DB_URL = os.getenv("SYNC_DB_URL")

# Application Database Pool
db_pool = ConnectionPool(DATABASE_URL, min_size=1, max_size=10, open=False) if DATABASE_URL else None

# Sync Database Pool (strictly capped matching the DB role limit)
sync_pool = ConnectionPool(SYNC_DB_URL, min_size=1, max_size=4, open=False) if SYNC_DB_URL else None

def close_pools():
    if db_pool and not db_pool.closed:
        db_pool.close()
    if sync_pool and not sync_pool.closed:
        sync_pool.close()

atexit.register(close_pools)

def get_connection():
    """Returns a connection to the Sentinel PostgreSQL Data Warehouse."""
    if db_pool and db_pool.closed:
        db_pool.open()
    return db_pool.connection()

def get_sync_connection():
    """Returns a read-only connection to the Birdseye raw_records schema."""
    if sync_pool and sync_pool.closed:
        sync_pool.open()
    return sync_pool.connection()
