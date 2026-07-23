import os
import time
import json
import logging
from typing import Callable, Any, Dict, Optional

# Database helpers
from fastapi_service.database import execute_query, execute_single

logger = logging.getLogger(__name__)

# 1. Redis Distributed Lock Keyed by Movie ID
class RedisDistributedLock:
    def __init__(self, redis_client, movie_id: int, timeout_seconds: int = 300):
        self.redis = redis_client
        self.lock_key = f"movie_lock_{movie_id}"
        self.timeout = timeout_seconds
        self.token = str(time.time())
        
    def acquire(self) -> bool:
        """
        Attempts to acquire lock atomically using SET NX EX.
        """
        try:
            res = self.redis.set(self.lock_key, self.token, ex=self.timeout, nx=True)
            if res:
                logger.info(f"Redis Lock: Acquired lock for Movie #{self.lock_key}")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to acquire Redis lock: {e}")
            # Degrade gracefully by returning True to avoid blocking worker execution if Redis is down
            return True
            
    def release(self):
        """
        Releases the lock atomically using a Lua script to prevent releasing other workers' locks.
        """
        try:
            lua_script = """
                if redis.call("get", KEYS[1]) == ARGV[1] then
                    return redis.call("del", KEYS[1])
                else
                    return 0
               end
            """
            self.redis.eval(lua_script, 1, self.lock_key, self.token)
            logger.info(f"Redis Lock: Released lock for Movie #{self.lock_key}")
        except Exception as e:
            logger.error(f"Failed to release Redis lock: {e}")

# 2. Idempotency Check Helpers
def initialize_idempotency_table():
    try:
        execute_query("""
            CREATE TABLE IF NOT EXISTS core_stage_history (
                id SERIAL PRIMARY KEY,
                movie_id INTEGER NOT NULL,
                stage_name VARCHAR(50) NOT NULL,
                status VARCHAR(20) NOT NULL,
                completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(movie_id, stage_name)
            );
        """)
    except Exception as e:
        logger.error(f"Failed to initialize stage history table: {e}")

def is_stage_already_completed(movie_id: int, stage_name: str) -> bool:
    """
    Checks if a given pipeline stage has already been completed successfully in Postgres.
    """
    initialize_idempotency_table()
    try:
        row = execute_single(
            "SELECT id FROM core_stage_history WHERE movie_id = %s AND stage_name = %s AND status = 'COMPLETED'",
            (movie_id, stage_name)
        )
        return True if row else False
    except Exception as e:
        logger.error(f"Failed to query stage completion status: {e}")
        return False

def mark_stage_completed(movie_id: int, stage_name: str):
    """
    Marks a stage as completed successfully in the Postgres history ledger.
    """
    initialize_idempotency_table()
    try:
        execute_query("""
            INSERT INTO core_stage_history (movie_id, stage_name, status, completed_at)
            VALUES (%s, %s, 'COMPLETED', NOW())
            ON CONFLICT (movie_id, stage_name) DO UPDATE SET status = 'COMPLETED', completed_at = NOW()
        """, (movie_id, stage_name))
        logger.info(f"Idempotency: Stage '{stage_name}' marked COMPLETED for Movie #{movie_id}")
    except Exception as e:
        logger.error(f"Failed to record stage completion in Postgres: {e}")

# 3. Dead-Letter Queue (DLQ) Handler
def move_to_dead_letter_queue(movie_id: int, job_id: str, stage_name: str, error_message: str):
    """
    Moves failed pipeline jobs to a dead-letter queue table for manual operator review.
    Marks movie and render job status as NEEDS_REVIEW.
    """
    logger.error(f"DLQ TRIGGERED: Movie #{movie_id} failed stage '{stage_name}'. Error: {error_message}")
    
    try:
        execute_query("""
            CREATE TABLE IF NOT EXISTS core_dead_letter_queue (
                id SERIAL PRIMARY KEY,
                movie_id INTEGER NOT NULL,
                job_id VARCHAR(100) NOT NULL,
                failed_stage VARCHAR(50) NOT NULL,
                error_message TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        execute_query("""
            INSERT INTO core_dead_letter_queue (movie_id, job_id, failed_stage, error_message)
            VALUES (%s, %s, %s, %s)
        """, (movie_id, job_id, stage_name, error_message))
        
        # Update render status
        execute_query("UPDATE core_renderjob SET status = 'NEEDS_REVIEW' WHERE job_id = %s", (job_id,))
        execute_query("UPDATE core_movie SET status = 'NEEDS_REVIEW' WHERE id = %s", (movie_id,))
        
        logger.info(f"DLQ: Render Job {job_id} successfully transitioned to NEEDS_REVIEW.")
    except Exception as e:
        logger.error(f"Failed to move job to DLQ: {e}")
