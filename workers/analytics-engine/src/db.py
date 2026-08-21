import os
import psycopg
from psycopg_pool import ConnectionPool
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
# Read-only connection to the Birdseye database for sync extraction
SYNC_DB_URL = os.getenv("SYNC_DB_URL")

# Application Database Pool
db_pool = ConnectionPool(DATABASE_URL, min_size=1, max_size=10) if DATABASE_URL else None

# Sync Database Pool (strictly capped matching the DB role limit)
sync_pool = ConnectionPool(SYNC_DB_URL, min_size=1, max_size=4) if SYNC_DB_URL else None

def get_connection():
    """Returns a connection to the Sentinel PostgreSQL Data Warehouse."""
    return db_pool.connection()

def get_sync_connection():
    """Returns a read-only connection to the Birdseye raw_records schema."""
    return sync_pool.connection()
