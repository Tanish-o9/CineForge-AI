import os
import sys
import json
import logging
from unittest.mock import MagicMock, patch

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TestConsistency")

# Mock database module to prevent dependency exception
mock_db = MagicMock()
sys.modules['fastapi_service.database'] = mock_db

# Import target components
from fastapi_service.pipeline.consistency_service import get_or_create_asset, generate_conditioned_shot

def run_consistency_tests():
    logger.info("=== STARTING ASSET CONSISTENCY ENGINE TESTS ===")

    # 1. Test Case: Mocking database cache misses and hits
    # We will simulate a cache miss first, then a cache hit for a similar character description
    mock_db.execute_single.side_effect = [
        None, # First call: get_or_create_asset cache check returns None -> GENERATED
        {"asset_id": 1}, # First call RETURNING asset_id from insert
        
        # Second call: get_or_create_asset cache check returns a matching row -> CACHE_HIT
        {
            "asset_id": 1,
            "name": "Alex",
            "reference_image_url": "storage/consistency/character_alex_reference.png",
            "description": "Astronaut in a battered white spacesuit",
            "similarity": 0.98
        }
    ]
    mock_db.execute_query.return_value = None

    # Step A: Cache Miss Generation
    logger.info("Step A: Creating a new character 'Alex'")
    res1 = get_or_create_asset(
        asset_type="character",
        name="Alex",
        description="Astronaut in a battered white spacesuit with gold visor and scuff marks"
    )
    logger.info(f"Result A Status: {res1['status']} | Reference URL: {res1['reference_image_url']}")
    assert res1['status'] == "GENERATED"
    assert "character_alex_reference.png" in res1['reference_image_url']

    # Step B: Cache Hit Similarity Matching
    logger.info("\nStep B: Retrieving character 'Alex' with slightly modified description")
    res2 = get_or_create_asset(
        asset_type="character",
        name="Alex",
        description="Astronaut in a battered white spacesuit with golden visor" # slightly different text
    )
    logger.info(f"Result B Status: {res2['status']} | Matches original ID: {res2['asset_id']}")
    assert res2['status'] == "CACHE_HIT"
    assert res2['asset_id'] == 1

    # 2. Test Case: Conditioned Image Generation
    logger.info("\nStep C: Testing conditioned shot generation with reference visual image")
    # Make sure reference file exists to bypass check
    dummy_ref_path = "storage/consistency/character_alex_reference.png"
    os.makedirs(os.path.dirname(dummy_ref_path), exist_ok=True)
    with open(dummy_ref_path, "w") as f:
        f.write("mock reference image data")

    shot_prompt = "Alex stands on Martian Ridge, looking back at the dome."
    shot_path = generate_conditioned_shot(shot_prompt, dummy_ref_path)
    logger.info(f"Conditioned Shot generated at: {shot_path}")
    assert os.path.exists(shot_path)
    
    # Cleanup dummy files
    if os.path.exists(dummy_ref_path):
        os.remove(dummy_ref_path)
    if os.path.exists(shot_path):
        os.remove(shot_path)

    logger.info("=== ASSET CONSISTENCY ENGINE TESTS COMPLETED SUCCESSFULLY ===")

if __name__ == '__main__':
    run_consistency_tests()
