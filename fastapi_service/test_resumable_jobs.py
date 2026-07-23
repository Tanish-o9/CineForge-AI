import os
import sys
import json
import logging
from unittest.mock import MagicMock

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TestResumable")

# Mock database module to prevent dependency exception
mock_db = MagicMock()
sys.modules['fastapi_service.database'] = mock_db

# Import targets
from fastapi_service.pipeline.resumable_service import (
    RedisDistributedLock,
    is_stage_already_completed,
    mark_stage_completed,
    move_to_dead_letter_queue
)
from fastapi_service.agents.orchestrator import run_stage_with_retry, MovieState

def run_resumable_tests():
    logger.info("=== STARTING SAFELY RESUMABLE & IDEMPOTENT JOBS TESTS ===")

    # 1. Test Redis Distributed locking
    logger.info("Step A: Testing RedisDistributedLock acquire and release")
    mock_redis = MagicMock()
    # Mock lock set NX EX returning True (success) then False (locked)
    mock_redis.set.side_effect = [True, False]
    
    lock_1 = RedisDistributedLock(mock_redis, movie_id=101, timeout_seconds=10)
    lock_2 = RedisDistributedLock(mock_redis, movie_id=101, timeout_seconds=10)
    
    assert lock_1.acquire() is True
    assert lock_2.acquire() is False # locked by lock_1!
    
    lock_1.release()
    assert mock_redis.eval.call_count == 1
    logger.info("✔ Redis Distributed Lock acquire/release verified successfully.")

    # 2. Test Idempotency Postgres history checks
    logger.info("\nStep B: Testing Idempotency Postgres history check")
    mock_db.execute_single.side_effect = [
        None, # Step A: table check
        {"id": 4} # Step B: Cache hit (already completed)
    ]
    mock_db.execute_query.return_value = None
    
    # Check for non-completed stage
    assert is_stage_already_completed(movie_id=1, stage_name="story") is False
    # Check for completed stage (Cache hit)
    assert is_stage_already_completed(movie_id=1, stage_name="storyboard") is True
    logger.info("✔ Idempotency checks correctly route database row flags.")

    # 3. Test DLQ DB migrator inserts
    logger.info("\nStep C: Testing Dead-Letter Queue (DLQ) Transfer inserts")
    mock_db.execute_single.side_effect = None
    mock_db.execute_single.return_value = None
    
    move_to_dead_letter_queue(
        movie_id=1,
        job_id="job_dlq_123",
        stage_name="animation",
        error_message="MoviePy rendering limits exceeded"
    )
    
    # Check that DLQ insert was called
    dlq_calls = [call[0][0] for call in mock_db.execute_query.call_args_list if "INSERT INTO core_dead_letter_queue" in call[0][0]]
    logger.info(f"DLQ SQL inserts count: {len(dlq_calls)}")
    assert len(dlq_calls) == 1
    logger.info("✔ Dead-letter queue successfully logs and registers failed jobs.")

    # 4. Test run_stage_with_retry Idempotency Skip
    logger.info("\nStep D: Testing orchestrator stage run idempotency bypass")
    
    # Mocking db calls:
    # 1. is_stage_already_completed returns True (cache hit)
    mock_db.execute_single.return_value = {"id": 1}
    
    state_dict = {
        "movie_id": 1,
        "job_id": "job_abc",
        "user_prompt": "Alex on Mars",
        "status": "PROCESSING",
        "scenes": [],
        "characters": []
    }
    
    mock_runner = MagicMock()
    
    # Execute stage run -> should skip run and complete instantly
    res = run_stage_with_retry(state_dict, "story", mock_runner, 10)
    logger.info(f"Bypassed node result status: {res.get('status')}")
    assert mock_runner.call_count == 0 # never called!
    logger.info("✔ Orchestration node bypassed runner functions on idempotent hit.")

    logger.info("=== SAFELY RESUMABLE & IDEMPOTENT JOBS TESTS COMPLETED SUCCESSFULLY ===")

if __name__ == '__main__':
    run_resumable_tests()
