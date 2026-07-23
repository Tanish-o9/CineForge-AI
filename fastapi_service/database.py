import os
import psycopg
from psycopg.rows import dict_row

DATABASE_URL = os.environ.get('DATABASE_URL', 'postgres://postgres:postgrespassword@localhost:5432/cineforge')

def get_db_connection():
    """
    Returns a new PostgreSQL connection with dict_row row factory.
    """
    conn = psycopg.connect(DATABASE_URL, row_factory=dict_row)
    return conn

def execute_query(query, params=None, fetch=False):
    """
    Helper function to run single queries.
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params or ())
            if fetch:
                return cur.fetchall()
            conn.commit()
            return None

def execute_single(query, params=None):
    """
    Helper function to fetch a single row.
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params or ())
            return cur.fetchone()
