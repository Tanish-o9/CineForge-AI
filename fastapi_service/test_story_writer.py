import os
import sys
import json
import logging

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TestStoryWriter")

# Setup dummy db for test script to prevent dependency exceptions
from unittest.mock import MagicMock
sys.modules['fastapi_service.database'] = MagicMock()

from fastapi_service.agents.story_writer import run_story_writer_with_retry, StoryOutput

PROMPTS = [
    {
        "type": "Sci-Fi Thriller",
        "prompt": "Create a 90-second tense sci-fi story about a rogue AI taking over a colony dome on Titan, high suspense, dark atmosphere."
    },
    {
        "type": "Comedy Ad",
        "prompt": "Create a 30-second funny commercial about a talking dog trying to sell luxury watches to cats, satirical and bright."
    },
    {
        "type": "Family Drama",
        "prompt": "Create a 120-second emotional drama about a father and daughter rebuilding a vintage sailboat to reconnect, warm and nostalgic."
    }
]

def run_tests():
    api_key = os.environ.get("OPENAI_API_KEY")
    
    if not api_key:
        logger.warning("OPENAI_API_KEY not found in environment. Testing with local fallback generator simulation.")
        # Perform client side simulation of validation rules
        logger.info("Running validation checks on valid and invalid StoryOutput structures...")
        
        # Test Case 1: Valid story output simulation
        valid_story = StoryOutput(
            title="Titan Horizon",
            genre="Sci-Fi",
            tone="Tense",
            target_duration_seconds=60,
            characters=[
                {"name": "Commander Miller", "age": "45", "role": "Protagonist", "personality": "Stressed", "physical_description": "Faded uniform"}
            ],
            plot_summary="A crew tries to contain a virus.",
            ending="They lock it out.",
            scene_list=[
                {"scene_number": 1, "location": "Dome Control", "time_of_day": "NIGHT", "description": "Miller runs", "emotional_beat": "tense"},
                {"scene_number": 2, "location": "Sub-level 3", "time_of_day": "NIGHT", "description": "AI shuts doors", "emotional_beat": "claustrophobic"}
            ]
        )
        
        from fastapi_service.agents.story_writer import validate_story_output
        try:
            validate_story_output(valid_story)
            logger.info("✔ Valid story simulation passed validation checks.")
        except Exception as e:
            logger.error(f"❌ Valid story failed: {e}")

        # Test Case 2: Invalid story (too many scenes)
        invalid_story = StoryOutput(
            title="Titan Horizon",
            genre="Sci-Fi",
            tone="Tense",
            target_duration_seconds=30, # Only 30s but has 4 scenes! (~7.5s per scene, fails < 15s limit)
            characters=[
                {"name": "Miller", "age": "45", "role": "Protagonist", "personality": "Stressed", "physical_description": "Suit"}
            ],
            plot_summary="AI virus.",
            ending="Out.",
            scene_list=[
                {"scene_number": 1, "location": "Control", "time_of_day": "NIGHT", "description": "Miller runs", "emotional_beat": "tense"},
                {"scene_number": 2, "location": "Control", "time_of_day": "NIGHT", "description": " Miller runs", "emotional_beat": "tense"},
                {"scene_number": 3, "location": "Control", "time_of_day": "NIGHT", "description": " Miller runs", "emotional_beat": "tense"},
                {"scene_number": 4, "location": "Control", "time_of_day": "NIGHT", "description": " Miller runs", "emotional_beat": "tense"}
            ]
        )
        
        try:
            validate_story_output(invalid_story)
            logger.error("❌ Invalid story (too many scenes) bypassed validation!")
        except ValueError as ve:
            logger.info(f"✔ Invalid story caught correctly: {ve}")
            
        logger.info("=== Mock validation test suite finished ===")
        return

    # Real API Testing
    logger.info("Engaging ChatOpenAI API keys for Structured Outputs")
    for test_item in PROMPTS:
        logger.info(f"\n--- Testing prompt type: {test_item['type']} ---")
        logger.info(f"Prompt: {test_item['prompt']}")
        
        try:
            story = run_story_writer_with_retry(test_item['prompt'], api_key)
            
            logger.info(f"Resulting Title: {story.title}")
            logger.info(f"Resulting Genre: {story.genre} | Tone: {story.tone}")
            logger.info(f"Duration: {story.target_duration_seconds}s | Scenes count: {len(story.scene_list)}")
            logger.info("Characters:")
            for char in story.characters:
                logger.info(f"  - {char.name} ({char.role}): {char.personality}")
            logger.info("Scene List:")
            for scene in story.scene_list:
                logger.info(f"  Scene #{scene.scene_number} @ {scene.location}: {scene.description[:60]}...")
            
            logger.info(f"✔ Successfully generated structured output for {test_item['type']}")
            
        except Exception as e:
            logger.error(f"❌ Failed both attempts for {test_item['type']}: {e}")

if __name__ == '__main__':
    run_tests()
