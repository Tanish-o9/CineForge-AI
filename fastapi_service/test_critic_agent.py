import os
import sys
import json
import logging
from unittest.mock import MagicMock

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TestCriticAgent")

# Mock database module to prevent dependency exception
mock_db = MagicMock()
sys.modules['fastapi_service.database'] = mock_db

# Import targets
from fastapi_service.agents.critic_agent import (
    critic_check_story,
    critic_check_screenplay,
    critic_check_storyboard,
    critic_check_asset_gen,
    critic_check_video_edit,
    run_stage_critic,
    route_stage_critic_decision
)
from fastapi_service.agents.orchestrator import MovieState, orchestrator_graph

class DummyState:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

def run_critic_tests():
    logger.info("=== STARTING CRITIC AGENT TESTS ===")

    # 1. Test Story Validation (duration mismatch trigger)
    logger.info("Step A: Testing Story stage critic checks")
    # State has target_duration_seconds = 100 but only 1 scene (estimated duration = 25s, out of bounds)
    state = DummyState(
        movie_id=1,
        target_duration_seconds=100,
        characters=[{"name": "Alex"}],
        scenes=[{"description": "Alex walks on Mars"}]
    )
    
    is_ok, msg = critic_check_story(state)
    logger.info(f"Story Validation: ok={is_ok}, message={msg}")
    assert is_ok is False
    assert "tolerance margin" in msg
    
    # Add characters, adjust target duration so it matches
    state.target_duration_seconds = 25
    is_ok2, msg2 = critic_check_story(state)
    logger.info(f"Story Validation (Corrected): ok={is_ok2}, message={msg2}")
    assert is_ok2 is True
    logger.info("✔ Story stage critic validation verified.")

    # 2. Test Screenplay Validation (invalid character trigger)
    logger.info("\nStep B: Testing Screenplay stage critic checks")
    state = DummyState(
        movie_id=1,
        target_duration_seconds=60,
        characters=[{"name": "Alex"}],
        scenes=[
            {
                "scene_number": 1,
                "dialogue": [
                    {"character": "Bob", "line": "Who are you?"} # Bob is not in characters list!
                ]
            }
        ]
    )
    is_ok, msg = critic_check_screenplay(state)
    logger.info(f"Screenplay Validation: ok={is_ok}, message={msg}")
    assert is_ok is False
    assert "Bob" in msg
    logger.info("✔ Screenplay stage critic validation verified.")

    # 3. Test Asset similarity check with simulated fail
    logger.info("\nStep C: Testing Asset consistency similarity check")
    state = DummyState(
        characters=[{"name": "Alex", "physical_description": "fail_critic"}]
    )
    is_ok, msg = critic_check_asset_gen(state)
    logger.info(f"Asset similarity Validation (simulated fail): ok={is_ok}, message={msg}")
    assert is_ok is False
    assert "similarity check failed" in msg
    logger.info("✔ Asset consistency similarity check verified.")

    # 4. Test self-correcting loop and routing logic
    logger.info("\nStep D: Testing self-correcting loop retry and route decisions")
    
    # Setup state dictionary
    state_dict = {
        "movie_id": 1,
        "job_id": "job_abc",
        "user_prompt": "Alex on Mars",
        "target_duration_seconds": 100, # forces story critic fail
        "scenes": [{"description": "Alex walks on Mars"}],
        "characters": [{"name": "Alex"}],
        "status": "PROCESSING",
        "errors": [],
        "retry_counts": {}
    }
    
    # First critic check -> should trigger RETRY
    updated_1 = run_stage_critic(state_dict, "story")
    logger.info(f"Attempt 1 Status: {updated_1['status']} (Retry counts: {updated_1['retry_counts']})")
    assert updated_1["status"] == "RETRY"
    assert updated_1["retry_counts"]["critic_story"] == 1
    
    route_1 = route_stage_critic_decision(updated_1, next_node="screenplay", self_node="story")
    logger.info(f"Attempt 1 Edge routing decision: {route_1}")
    assert route_1 == "story" # loops back to self_node
    
    # Second critic check (simulate rerun still failing) -> should trigger DEGRADED and proceed
    updated_2 = run_stage_critic(updated_1, "story")
    logger.info(f"Attempt 2 Status: {updated_2['status']} (Retry counts: {updated_2['retry_counts']})")
    assert updated_2["status"] == "DEGRADED"
    assert updated_2["retry_counts"]["critic_story"] == 2
    
    route_2 = route_stage_critic_decision(updated_2, next_node="screenplay", self_node="story")
    logger.info(f"Attempt 2 Edge routing decision: {route_2}")
    assert route_2 == "screenplay" # proceeds to next_node in degraded state!
    
    logger.info("✔ Critic loopback controls and routing edges verified.")

    # 5. Verify orchestrator compilation
    logger.info("\nStep E: Verifying Graph Compilation")
    assert orchestrator_graph is not None
    logger.info("✔ Orchestration graph successfully compiled.")

    logger.info("=== CRITIC AGENT TESTS COMPLETED SUCCESSFULLY ===")

if __name__ == '__main__':
    run_critic_tests()
