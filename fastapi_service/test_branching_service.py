import os
import sys
import json
import logging
from unittest.mock import MagicMock, patch

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TestBranching")

# Mock database module to prevent dependency exception
mock_db = MagicMock()
sys.modules['fastapi_service.database'] = mock_db

# Import targets
from fastapi_service.pipeline.branching_service import api_choose_narrative_branch, ChoiceSelection
from fastapi_service.agents.screenplay_writer import SceneScreenplay, CustomDialogueLine

def run_branching_tests():
    logger.info("=== STARTING BRANCHING NARRATIVE ENGINE TESTS ===")

    # Setup dummy directory structure
    dummy_dir = "storage/movies/1/clips"
    os.makedirs(dummy_dir, exist_ok=True)

    # 1. Test On-Demand Branch Generation Mock Call
    logger.info("Step A: Simulating Choose Narrative Branch callback")
    
    # Simple dynamic mock routing to support parallel query checks safely
    def dynamic_execute_single(query, params=None):
        q = query.lower()
        if "core_scene" in q:
            return {
                "id": 30,
                "location": "Martian Ridge",
                "time_of_day": "NIGHT",
                "description": "Alex enters the dark pod.",
                "emotional_beat": "tense",
                "screenplay_text": None # Cache miss!
            }
        if "core_movie" in q:
            return {
                "title": "Red Solitude",
                "screenplay_raw": json.dumps({
                    "characters": [{"name": "Alex", "role": "Protagonist"}],
                    "scenes": [
                        {
                            "scene_number": 3,
                            "branches": [
                                {"choice_text": "Proceed inside the shelter", "next_scene_number": 4},
                                {"choice_text": "Stay outside in storm", "next_scene_number": 5}
                            ]
                        }
                    ]
                })
            }
        return None

    mock_db.execute_single.side_effect = dynamic_execute_single
    
    # execute_query results:
    # Handles dynamic calls of migrations, insertions, and SELECT queries safely
    def dynamic_execute_query(query, params=None, *args, **kwargs):
        q = query.lower()
        if "select file_path" in q:
            return [
                {"file_path": "storage/movies/1/clips/scene_3_shot_1.mp4"},
                {"file_path": "storage/movies/1/clips/scene_3_shot_2.mp4"}
            ]
        return None

    mock_db.execute_query.side_effect = dynamic_execute_query

    # Patch screenplay generator and animation generator to prevent OpenAI API and MoviePy dependency exceptions
    with patch("fastapi_service.agents.screenplay_writer.generate_scene_with_retry") as mock_script, \
         patch("fastapi_service.pipeline.animation.animate_shot") as mock_anim:
         
         # Mock script generator return value
         mock_script.return_value = SceneScreenplay(
             scene_number=3,
             scene_heading="EXT. RIDGE - NIGHT",
             action_lines=["Alex opens the hatch door."],
             dialogue=[CustomDialogueLine(character="Alex", line="Is anyone here?", delivery_note="")],
             estimated_screen_time_seconds=10
         )
         
         mock_anim.return_value = "storage/movies/1/clips/scene_3_shot_1.mp4"
         
         # 2. Trigger choose endpoint
         res = api_choose_narrative_branch(movie_id=1, data=ChoiceSelection(next_scene_number=3))
         
         logger.info(f"API Choice Response: {res}")
         assert res["status"] == "SUCCESS"
         assert res["scene_number"] == 3
         assert len(res["clips"]) == 2
         assert len(res["choices"]) == 2
         logger.info("✔ On-demand branch compiling and routing completed successfully.")

    # Cleanup folders
    if os.path.exists("storage/movies/1/clips"):
        import shutil
        shutil.rmtree("storage/movies/1")

    logger.info("=== BRANCHING NARRATIVE ENGINE TESTS COMPLETED SUCCESSFULLY ===")

if __name__ == '__main__':
    run_branching_tests()
