import os
import sys
import json
import logging
from unittest.mock import MagicMock, patch

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TestRecurringCharacters")

# Mock database module to prevent dependency exception
mock_db = MagicMock()
sys.modules['fastapi_service.database'] = mock_db

# Import targets
from fastapi_service.pipeline.consistency_service import check_recurring_character, api_list_recurring_characters
from fastapi_service.agents.story_writer import run_story_writer

class DummyState:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

def run_recurring_tests():
    logger.info("=== STARTING RECURRING CHARACTERS PERSISTENCE TESTS ===")

    # 1. Test schema alter migration execution
    # On first load, it runs initialize_consistency_table which alters database columns
    mock_db.execute_query.return_value = None
    mock_db.execute_single.return_value = None
    
    logger.info("Step A: Executing check_recurring_character (triggers table migrations)")
    check_recurring_character("Alex", 1)
    
    # Verify that ALTER statements were invoked
    alter_calls = [call[0][0] for call in mock_db.execute_query.call_args_list if "ALTER TABLE" in call[0][0]]
    assert len(alter_calls) >= 2
    logger.info("✔ Dynamic schema ALTER migrations executed successfully.")

    # 2. Test Story Writer Flow Reuse Matching
    logger.info("\nStep B: Testing Story Writer Character Reuse check")
    
    # Simple dynamic mock routing to support multiple parallel query checks safely
    def dynamic_execute_single(query, params=None):
        q = query.lower()
        if "core_movie" in q:
            return {"user_id": 5}
        if "is_recurring = true" in q:
            if params and len(params) > 1 and "Alex" in params[1]:
                return {
                    "asset_id": 10,
                    "name": "Alex",
                    "reference_image_url": "storage/consistency/character_alex_reference.png",
                    "description": "Battered spacesuit with gold visor (ORIGINAL SPECIFICATION)"
                }
        return None

    mock_db.execute_single.side_effect = dynamic_execute_single
    
    # We run the story writer agent with a prompt for Mars
    state = DummyState(
        movie_id=1,
        user_prompt="Alex walks on Mars"
    )
    
    # Temporarily disable OpenAI API key to run fallback generator
    with patch.dict(os.environ, {"OPENAI_API_KEY": ""}):
        res = run_story_writer(state)
        
    logger.info(f"Generated characters in story outline: {res['characters']}")
    
    # Check that Alex has the recurring visual description and sheet path inherited!
    alex_char = next(c for c in res["characters"] if c["name"] == "Alex")
    assert alex_char["physical_description"] == "Battered spacesuit with gold visor (ORIGINAL SPECIFICATION)"
    assert alex_char["reference_sheet_path"] == "storage/consistency/character_alex_reference.png"
    assert alex_char["is_recurring"] is True
    logger.info("✔ Story Writer successfully reused visual description and reference sheets for recurring character.")

    # 3. Test API list endpoint
    logger.info("\nStep C: Testing GET recurring characters API endpoint")
    mock_db.execute_query.side_effect = None
    mock_db.execute_query.return_value = [
        {"asset_id": 10, "name": "Alex", "reference_image_url": "storage/consistency/character_alex_reference.png", "description": "specs"}
    ]
    mock_db.execute_single.return_value = None
    
    list_res = api_list_recurring_characters(user_id=5)
    logger.info(f"User recurring characters: {list_res}")
    assert len(list_res) == 1
    assert list_res[0]["name"] == "Alex"
    logger.info("✔ GET List endpoint query successfully executed.")

    logger.info("=== RECURRING CHARACTERS PERSISTENCE TESTS COMPLETED SUCCESSFULLY ===")

if __name__ == '__main__':
    run_recurring_tests()
