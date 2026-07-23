import os
import sys
import json
import logging
from unittest.mock import MagicMock

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TestSFXGen")

# Mock database module to prevent dependency exception
mock_db = MagicMock()
sys.modules['fastapi_service.database'] = mock_db

# Import targets
from fastapi_service.pipeline.sfx_gen import find_closest_sfx, get_sfx_library_metadata, run_sfx_generator

# Dummy state container
class DummyState:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

def run_sfx_tests():
    logger.info("=== STARTING SOUND EFFECTS AGENT UNIT TESTS ===")

    # 1. Test SFX catalog metadata creation
    logger.info("Step A: Testing catalog metadata loading")
    catalog = get_sfx_library_metadata()
    assert os.path.exists("storage/sfx/metadata.json")
    assert "footsteps" in catalog
    assert "thunder" in catalog
    logger.info("✔ SFX catalog metadata initialized successfully.")

    # 2. Test Local Embedding Matching / Keyword Lookup
    logger.info("\nStep B: Testing find_closest_sfx library lookup")
    # Test footsteps matching
    path_1, dur_1 = find_closest_sfx("footsteps on sand", catalog)
    logger.info(f"Match for 'footsteps on sand' -> file: {path_1} (Duration: {dur_1}s)")
    assert "footsteps" in path_1
    
    # Test weather matching
    path_2, dur_2 = find_closest_sfx("gale force winds blowing", catalog)
    logger.info(f"Match for 'gale force winds blowing' -> file: {path_2} (Duration: {dur_2}s)")
    assert "wind" in path_2
    
    logger.info("✔ Local library lookup matched keywords/embeddings successfully.")

    # 3. Test Volume mapping logic and batch scene compilation
    logger.info("\nStep C: Testing run_sfx_generator batch process")
    # Mocking database query responses
    mock_db.execute_single.return_value = {"id": 10}
    mock_db.execute_query.return_value = None
    
    # Scene screenplay text has walk and storm -> should extract footsteps and wind
    scenes = [
        {
            "scene_number": 1,
            "screenplay_text": (
                "EXT. RED RIDGE - DAY\n"
                "Alex walks slowly across the dry silt, suit dragging.\n"
                "A heavy Martian dust storm blows in the distance."
            )
        }
      ]
      
    state = DummyState(
        movie_id=1,
        scenes=scenes
    )
    
    res = run_sfx_generator(state)
    logger.info("Batch generator complete.")
    logger.info(f"Spliced scene cues: {res['scenes'][0]['sfx_cues']}")
    
    cues = res['scenes'][0]['sfx_cues']
    assert len(cues) >= 2
    # Verify footsteps has volume_db = -6.0 (normal)
    # Wind has volume_db = -12.0 (subtle)
    assert any(c["event_name"] == "footsteps" and c["volume_db"] == -6.0 for c in cues)
    assert any(c["event_name"] == "wind" and c["volume_db"] == -12.0 for c in cues)
    logger.info("✔ Foley cue compilation and volume mapping verified.")

    # Cleanup metadata file
    if os.path.exists("storage/sfx/metadata.json"):
        os.remove("storage/sfx/metadata.json")

    logger.info("=== SOUND EFFECTS AGENT UNIT TESTS COMPLETED SUCCESSFULLY ===")

if __name__ == '__main__':
    run_sfx_tests()
