import time
import random
import logging
from typing import Callable, Any, Dict

# Database helpers
from fastapi_service.database import execute_query

logger = logging.getLogger(__name__)

class CircuitBreakerOpenException(Exception):
    """
    Custom exception raised when the circuit breaker is open, failing fast.
    """
    pass

class CircuitBreaker:
    def __init__(self, name: str, threshold: int = 3, recovery_timeout: float = 10.0):
        self.name = name
        self.threshold = threshold
        self.recovery_timeout = recovery_timeout
        self.state = "CLOSED" # CLOSED, OPEN, HALF-OPEN
        self.failure_count = 0
        self.last_state_change = time.time()
        
    def record_success(self):
        if self.state != "CLOSED":
            logger.info(f"Circuit Breaker '{self.name}' transitioned from {self.state} to CLOSED")
            self.log_trip_event(self.state, "CLOSED")
            self.state = "CLOSED"
        self.failure_count = 0
        
    def record_failure(self, error_message: str):
        self.failure_count += 1
        logger.warning(f"Circuit Breaker '{self.name}' failure logged (Count: {self.failure_count}/{self.threshold})")
        if self.failure_count >= self.threshold and self.state != "OPEN":
            logger.error(f"Circuit Breaker '{self.name}' TRIP! Transitioned to OPEN.")
            self.log_trip_event(self.state, "OPEN", error_message)
            self.state = "OPEN"
            self.last_state_change = time.time()
            
    def allow_request(self) -> bool:
        if self.state == "OPEN":
            if time.time() - self.last_state_change > self.recovery_timeout:
                logger.info(f"Circuit Breaker '{self.name}' transitioned to HALF-OPEN for recovery check.")
                self.log_trip_event("OPEN", "HALF-OPEN")
                self.state = "HALF-OPEN"
                return True
            return False
        return True
        
    def log_trip_event(self, old_state: str, new_state: str, error_message: str = ""):
        """
        Logs circuit trip transitions into PostgreSQL for later telemetry audits.
        """
        try:
            execute_query("""
                CREATE TABLE IF NOT EXISTS core_reliability_log (
                    id SERIAL PRIMARY KEY,
                    service_name VARCHAR(100) NOT NULL,
                    event_type VARCHAR(50) NOT NULL,
                    old_state VARCHAR(20) NOT NULL,
                    new_state VARCHAR(20) NOT NULL,
                    error_message TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            execute_query(
                "INSERT INTO core_reliability_log (service_name, event_type, old_state, new_state, error_message, created_at) VALUES (%s, 'STATE_CHANGE', %s, %s, %s, NOW())",
                (self.name, old_state, new_state, error_message)
            )
        except Exception as e:
            logger.error(f"Failed to log circuit state change: {e}")

# Generic resilient call wrapper
def resilient_call(service_breaker: CircuitBreaker, max_retries: int = 3, base_delay: float = 1.0):
    from fastapi_service.pipeline.metrics import EXTERNAL_API_CALLS
    
    def decorator(fn: Callable[..., Any]):
        def wrapper(*args, **kwargs):
            if not service_breaker.allow_request():
                raise CircuitBreakerOpenException(f"Circuit Breaker '{service_breaker.name}' is OPEN. Failing fast.")
                
            retries = 0
            while True:
                try:
                    # Increment cost proxy metric
                    EXTERNAL_API_CALLS.labels(service_name=service_breaker.name).inc()
                    
                    result = fn(*args, **kwargs)
                    service_breaker.record_success()
                    return result
                except Exception as e:
                    error_str = str(e).lower()
                    
                    # Auth, validation, or 401/403 are non-transient, so we bypass retries
                    is_transient = True
                    if any(kw in error_str for kw in ["unauthorized", "auth", "credential", "invalid key", "401", "403"]):
                        is_transient = False
                        
                    service_breaker.record_failure(str(e))
                    
                    if not is_transient or retries >= max_retries:
                        raise e
                        
                    # Log retry event to Postgres
                    try:
                        execute_query("""
                            CREATE TABLE IF NOT EXISTS core_reliability_log (
                                id SERIAL PRIMARY KEY,
                                service_name VARCHAR(100) NOT NULL,
                                event_type VARCHAR(50) NOT NULL,
                                old_state VARCHAR(20) NOT NULL,
                                new_state VARCHAR(20) NOT NULL,
                                error_message TEXT,
                                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                            );
                        """)
                        execute_query(
                            "INSERT INTO core_reliability_log (service_name, event_type, old_state, new_state, error_message, created_at) VALUES (%s, 'RETRY', '', '', %s, NOW())",
                            (service_breaker.name, f"Retry attempt {retries + 1}/{max_retries}. Error: {str(e)}")
                        )
                    except Exception as le:
                        logger.error(f"Failed to log retry event: {le}")
                        
                    retries += 1
                    # Exponential backoff with full jitter
                    delay = (base_delay * (2 ** (retries - 1))) + random.uniform(0, 0.25)
                    logger.info(f"Transient error caught in '{service_breaker.name}'. Retrying in {delay:.2f}s...")
                    time.sleep(delay)
        return wrapper
    return decorator
