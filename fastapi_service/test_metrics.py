import os
import sys
import logging
from unittest.mock import MagicMock

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TestMetrics")

# Mock database module to prevent dependency exceptions
mock_db = MagicMock()
sys.modules['fastapi_service.database'] = mock_db

# Mock Celery to prevent host import exceptions
sys.modules['celery'] = MagicMock()
sys.modules['celery.exceptions'] = MagicMock()

# Import targets
from fastapi.testclient import TestClient
from fastapi_service.main import app
from fastapi_service.pipeline.metrics import STAGE_STATUS, EXTERNAL_API_CALLS

def run_metrics_tests():
    logger.info("=== STARTING PIPELINE MONITORING & METRICS TESTS ===")

    # 1. Test metrics increment values
    logger.info("Step A: Simulating worker stage metrics increment")
    
    # Check current metric value
    assert STAGE_STATUS.labels(stage_name="story", status="success")._value.get() == 0.0
    STAGE_STATUS.labels(stage_name="story", status="success").inc()
    assert STAGE_STATUS.labels(stage_name="story", status="success")._value.get() == 1.0
    logger.info("✔ Prometheus status counters incremented successfully.")

    # 2. Test cost proxy api counts
    logger.info("\nStep B: Simulating external API cost counter increments")
    assert EXTERNAL_API_CALLS.labels(service_name="ElevenLabsTTS")._value.get() == 0.0
    EXTERNAL_API_CALLS.labels(service_name="ElevenLabsTTS").inc()
    assert EXTERNAL_API_CALLS.labels(service_name="ElevenLabsTTS")._value.get() == 1.0
    logger.info("✔ External API call counters incremented successfully.")

    # 3. Test metrics endpoint registration via TestClient
    logger.info("\nStep C: Calling FastAPI /metrics endpoint")
    client = TestClient(app)
    response = client.get("/metrics")
    
    logger.info(f"Response status: {response.status_code}")
    assert response.status_code == 200
    
    # Check if raw Prometheus registry names are in metrics text output
    metrics_text = response.text
    assert "cineforge_pipeline_stage_total" in metrics_text
    assert "cineforge_external_api_calls_total" in metrics_text
    logger.info("✔ /metrics ASGI app exposed correct Prometheus metrics formatting.")

    logger.info("=== PIPELINE MONITORING & METRICS TESTS COMPLETED SUCCESSFULLY ===")

if __name__ == '__main__':
    run_metrics_tests()
