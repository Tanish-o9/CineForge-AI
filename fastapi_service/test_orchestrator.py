import os
import sys
import json
import logging
from unittest.mock import MagicMock, patch

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TestOrchestrator")

# Mock database and redis modules
mock_db = MagicMock()
sys.modules['fastapi_service.database'] = mock_db

# Patch redis client before import to prevent connection exception on import
mock_redis = MagicMock()
with patch("redis.Redis.from_url", return_value=mock_redis):
    from fastapi_service.agents.orchestrator import (
        MovieState,
        check_job_status,
        resume_movie_checkpoint,
        run_stage_with_retry
    )

def run_orchestrator_tests():
    logger.info("=== STARTING ORCHESTRATION ENGINE TESTS ===")

    # 1. Test Resume Checkpoint from DB
    logger.info("Step A: Testing resume_movie_checkpoint")
    mock_db.execute_single.return_value = {
        "screenplay_raw": json.dumps({
            "movie_id": 1,
            "job_id": "job_123",
            "user_prompt": "sci-fi short",
            "current_stage": "story",
            "status": "PROCESSING"
        })
    }
    
    checkpoint = resume_movie_checkpoint(movie_id=1)
    logger.info(f"Loaded Checkpoint data: {checkpoint}")
    assert checkpoint is not None
    assert checkpoint["job_id"] == "job_123"
    logger.info("✔ Checkpoint loading verified.")

    # 2. Test Router edge decision (check_job_status)
    logger.info("\nStep B: Testing check_job_status routing logic")
    # Case A: status processing
    next_edge = check_job_status({"status": "PROCESSING"})
    logger.info(f"Normal Processing Route: {next_edge}")
    assert next_edge == "next"
    
    # Case B: status failed (graceful halt edge)
    halt_edge = check_job_status({"status": "FAILED"})
    logger.info(f"Graceful Halt Route: {halt_edge}")
    assert halt_edge == "__end__"
    logger.info("✔ Graceful edge routing verified.")

    # 3. Test stage failure retry loop with error context injection
    logger.info("\nStep C: Testing run_stage_with_retry with self-correcting error injection")
    
    # We setup a runner function that always fails to trigger the retry and failure logic
    call_count = 0
    def failing_runner(state):
        nonlocal call_count
        call_count += 1
        raise ValueError(f"Failing execution number {call_count}")

    # Setup database mocks for checkpointing
    mock_db.execute_query.return_value = None
    
    initial_state = {
        "movie_id": 1,
        "job_id": "job_123",
        "user_prompt": "Initial user prompt",
        "retry_counts": {},
        "status": "PROCESSING",
        "errors": []
    }
    
    # Execute node with retry wrapper
    final_state_dict = run_stage_with_retry(
        state=initial_state,
        stage_name="story",
        runner_func=failing_runner,
        progress_val=10
    )
    
    # Assertions
    # It should have run failing_runner exactly twice before halting
    assert call_count == 2
    assert final_state_dict["status"] == "FAILED"
    assert len(final_state_dict["errors"]) == 2
    assert "RETRY FEEDBACK" in final_state_dict["user_prompt"]
    logger.info("✔ Stage retry wrapper verified. Handled failures gracefully, injected error context, and terminated.")

    logger.info("=== ORCHESTRATION ENGINE TESTS COMPLETED SUCCESSFULLY ===")

if __name__ == '__main__':
    run_orchestrator_tests()
