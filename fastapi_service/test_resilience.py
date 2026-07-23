import os
import sys
import time
import logging
from unittest.mock import MagicMock

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TestResilience")

# Mock database module to prevent dependency exception
mock_db = MagicMock()
sys.modules['fastapi_service.database'] = mock_db

# Import targets
from fastapi_service.pipeline.resilience import CircuitBreaker, resilient_call, CircuitBreakerOpenException
from fastapi_service.pipeline.voice_gen import ElevenLabsProvider

def run_resilience_tests():
    logger.info("=== STARTING RESILIENCE & CIRCUIT BREAKER TESTS ===")

    # Setup database mocks
    mock_db.execute_query.return_value = None

    # 1. Test Transient error retrying
    logger.info("Step A: Testing resilient_call transient error retry loop")
    breaker = CircuitBreaker(name="TestService", threshold=5, recovery_timeout=2.0)
    
    call_count = 0
    
    @resilient_call(breaker, max_retries=2, base_delay=0.05)
    def failing_transient_function():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise ValueError("Transient timeout error")
        return "SUCCESS"
        
    res = failing_transient_function()
    logger.info(f"Result after retries: {res} (Called {call_count} times)")
    assert res == "SUCCESS"
    assert call_count == 3
    logger.info("✔ Transient retries with delay completed successfully.")

    # 2. Test Non-transient error (Authentication bypass retry)
    logger.info("\nStep B: Testing non-transient authentication error bypass")
    breaker_auth = CircuitBreaker(name="AuthService", threshold=5)
    
    auth_calls = 0
    
    @resilient_call(breaker_auth, max_retries=3)
    def failing_auth_function():
        nonlocal auth_calls
        auth_calls += 1
        raise Exception("Unauthorized: Invalid API key")
        
    try:
        failing_auth_function()
    except Exception as e:
        logger.info(f"Auth error caught: {e} (Called {auth_calls} times)")
        # Should fail fast without retry
        assert auth_calls == 1
        
    logger.info("✔ Non-transient authentication errors bypassed retries successfully.")

    # 3. Test Circuit Breaker state transitions (CLOSED -> OPEN -> HALF-OPEN -> CLOSED)
    logger.info("\nStep C: Testing Circuit Breaker state machine transitions")
    # Low threshold of 3, short recovery timeout of 0.2s
    breaker_state = CircuitBreaker(name="StateBreaker", threshold=3, recovery_timeout=0.2)
    
    # CLOSED state
    assert breaker_state.state == "CLOSED"
    
    # Log 3 consecutive failures to trigger OPEN state
    breaker_state.record_failure("Error 1")
    breaker_state.record_failure("Error 2")
    breaker_state.record_failure("Error 3")
    
    logger.info(f"Circuit Breaker state after 3 failures: {breaker_state.state}")
    assert breaker_state.state == "OPEN"
    
    # Try calling a decorated function while circuit is open -> should raise CircuitBreakerOpenException
    @resilient_call(breaker_state, max_retries=0)
    def dummy_func():
        return "OK"
        
    try:
        dummy_func()
    except CircuitBreakerOpenException as cbe:
        logger.info(f"Fast-fail caught: {cbe}")
        
    # Wait for recovery timeout (0.2s) to transition to HALF-OPEN
    time.sleep(0.3)
    assert breaker_state.allow_request() is True
    logger.info(f"State after recovery timeout: {breaker_state.state}")
    assert breaker_state.state == "HALF-OPEN"
    
    # Record success to close circuit
    breaker_state.record_success()
    logger.info(f"State after recording success: {breaker_state.state}")
    assert breaker_state.state == "CLOSED"
    
    logger.info("✔ Circuit Breaker state transitions verified successfully.")

    # 4. Test database logging checks
    logger.info("\nStep D: Verify database execution calls for logging")
    # State changes and retries should trigger INSERT queries in core_reliability_log
    log_calls = [call[0][0] for call in mock_db.execute_query.call_args_list if "INSERT INTO core_reliability_log" in call[0][0]]
    logger.info(f"Database logging insert calls recorded: {len(log_calls)}")
    assert len(log_calls) > 0
    logger.info("✔ Reliability logs insertion commands successfully verified.")

    logger.info("=== RESILIENCE & CIRCUIT BREAKER TESTS COMPLETED SUCCESSFULLY ===")

if __name__ == '__main__':
    run_resilience_tests()
