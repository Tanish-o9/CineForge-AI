import os
import sys
import json
import time
import logging
from unittest.mock import MagicMock, patch

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TestGuardrails")

# Mock database module to prevent dependency exception
mock_db = MagicMock()
sys.modules['fastapi_service.database'] = mock_db

# Import targets
from fastapi_service.pipeline.guardrails import (
    check_and_decrement_quota,
    refund_quota,
    estimate_movie_generation_cost,
    run_movie_pipeline_with_timeout
)

def run_guardrails_tests():
    logger.info("=== STARTING PIPELINE GUARDRAILS TESTS ===")

    mock_redis = MagicMock()
    mock_db.execute_single.return_value = {"user_id": 5}
    mock_db.execute_query.return_value = None

    # 1. Test Redis Quotas
    logger.info("Step A: Testing Redis daily generation quota checks")
    # Quota available -> return True
    mock_redis.get.return_value = "3"
    assert check_and_decrement_quota(mock_redis, user_id=5) is True
    assert mock_redis.decr.call_count == 1
    
    # Quota exhausted -> return False
    mock_redis.get.return_value = "0"
    assert check_and_decrement_quota(mock_redis, user_id=5) is False
    
    # Refund quota
    mock_redis.exists.return_value = True
    refund_quota(mock_redis, user_id=5)
    assert mock_redis.incr.call_count == 1
    logger.info("✔ Redis daily quota checks and refunds verified successfully.")

    # 2. Test Pre-flight cost estimator
    logger.info("\nStep B: Testing pre-flight cost estimator limits")
    # Check within budget (1 minute duration, 2 characters -> cheap)
    is_ok_1, cost_1, msg_1 = estimate_movie_generation_cost(
        target_duration_seconds=60,
        num_characters=2,
        max_budget_dollars=0.50
    )
    logger.info(f"Estimate (60s): ok={is_ok_1}, cost=${cost_1:.3f}, msg={msg_1}")
    assert is_ok_1 is True
    
    # Check budget exceeded (10 minutes duration, 5 characters -> expensive)
    is_ok_2, cost_2, msg_2 = estimate_movie_generation_cost(
        target_duration_seconds=600,
        num_characters=5,
        max_budget_dollars=0.50 # limit 50 cents
    )
    logger.info(f"Estimate (600s): ok={is_ok_2}, cost=${cost_2:.3f}, msg={msg_2}")
    assert is_ok_2 is False
    assert "Cost Exceeded" in msg_2
    logger.info("✔ Pre-flight cost estimator constraints verified successfully.")

    # 3. Test ThreadPool Timeout Wrapper
    logger.info("\nStep C: Testing orchestrator ThreadPool execution timeout wrapper")
    
    # Mocking orchestrator graph invoke to take 0.5s
    mock_orchestrator = MagicMock()
    def slow_invoke(state):
        time.sleep(0.5)
        return {"status": "SUCCESS"}
    mock_orchestrator.invoke.side_effect = slow_invoke
    
    state_dict = {
        "movie_id": 10,
        "target_duration_seconds": 30,
        "characters": []
    }
    
    with patch("fastapi_service.agents.orchestrator.orchestrator_graph", mock_orchestrator):
        # Test case 1: runs to completion (timeout = 2.0s > 0.5s)
        res = run_movie_pipeline_with_timeout(
            movie_id=10,
            state_dict=state_dict,
            redis_client=mock_redis,
            timeout_seconds=2.0
        )
        logger.info(f"Completion run status: {res.get('status')}")
        assert res.get("status") == "SUCCESS"
        
        # Test case 2: triggers timeout (timeout = 0.1s < 0.5s)
        try:
            run_movie_pipeline_with_timeout(
                movie_id=10,
                state_dict=state_dict,
                redis_client=mock_redis,
                timeout_seconds=0.1
            )
            # Should not reach here
            assert False
        except TimeoutError as te:
            logger.info(f"Timeout caught successfully: {te}")
            
    # Check that quota was refunded after timeout
    assert mock_redis.incr.call_count == 2 # 1 from previous refund test, 1 from timeout refund!
    logger.info("✔ ThreadPool executor successfully timed out and refunded daily slots.")

    logger.info("=== PIPELINE GUARDRAILS TESTS COMPLETED SUCCESSFULLY ===")

if __name__ == '__main__':
    run_guardrails_tests()
