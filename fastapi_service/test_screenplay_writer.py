import os
import sys
import json
import logging
from unittest.mock import MagicMock, patch

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TestScreenplayWriter")

# Setup dummy db for test script to prevent dependency exceptions
sys.modules['fastapi_service.database'] = MagicMock()

# Import target components
from fastapi_service.agents.screenplay_writer import (
    SceneScreenplay, 
    CustomDialogueLine, 
    validate_scene_characters, 
    validate_screenplay_word_count, 
    regenerate_scene,
    ScreenplayValidationError
)

def run_screenplay_tests():
    logger.info("=== STARTING SCREENPLAY AGENT UNIT TESTS ===")
    
    # Approved character roster
    valid_characters = ["Alex", "EVA"]
    
    # 1. Test Character Validation (PASS)
    logger.info("Testing Character Validation - Valid Case")
    valid_scene = SceneScreenplay(
        scene_number=1,
        scene_heading="INT. HABITAT CORE - NIGHT",
        action_lines=["Alex monitors the telemetry screen."],
        dialogue=[
            CustomDialogueLine(character="Alex", line="Is the oxygen stable?", delivery_note="(anxiously)"),
            CustomDialogueLine(character="EVA", line="Oxygen is at 85%.", delivery_note="(logical)")
        ],
        estimated_screen_time_seconds=20
    )
    try:
        validate_scene_characters(valid_scene, valid_characters)
        logger.info("✔ Valid characters validated successfully.")
    except Exception as e:
        logger.error(f"❌ Valid characters check failed: {e}")

    # 2. Test Character Validation (FAIL)
    logger.info("Testing Character Validation - Invalid Case (Unapproved Character)")
    invalid_scene = SceneScreenplay(
        scene_number=1,
        scene_heading="INT. HABITAT CORE - NIGHT",
        action_lines=["Alex monitors the screen."],
        dialogue=[
            CustomDialogueLine(character="Alex", line="Hello?", delivery_note="(whispering)"),
            # 'HAL' is not in ['Alex', 'EVA']
            CustomDialogueLine(character="HAL", line="I cannot do that.", delivery_note="(coldly)")
        ],
        estimated_screen_time_seconds=20
    )
    try:
        validate_scene_characters(invalid_scene, valid_characters)
        logger.error("❌ Unapproved character bypassed validation check!")
    except ScreenplayValidationError as sve:
        logger.info(f"✔ Invalid character caught correctly: {sve}")

    # 3. Test Word Count Validation (UNDER_FLOW)
    logger.info("Testing Word Count Validation - Underflow Case")
    # Target duration: 120s (~2 minutes).
    # Expected words = (120/60) * 130 = 260 words. Tolerance +-10% (234 - 286 words).
    # Only 5 words generated here!
    underflow_scenes = [valid_scene] # Has 8 words
    is_valid, msg = validate_screenplay_word_count(underflow_scenes, target_duration_seconds=120)
    if not is_valid and "UNDER_FLOW" in msg:
        logger.info(f"✔ Word count underflow caught correctly: {msg}")
    else:
        logger.error(f"❌ Underflow check failed to return correct feedback: {is_valid}, {msg}")

    # 4. Test Word Count Validation (OVER_FLOW)
    logger.info("Testing Word Count Validation - Overflow Case")
    # Target duration: 30s (~0.5 minutes).
    # Expected words = (30/60) * 130 = 65 words. Tolerance +-10% (58 - 71 words).
    # Has ~100 words here, exceeding maximum 71 words.
    verbose_dialogue = [
        CustomDialogueLine(character="Alex", line=" ".join(["word"] * 50), delivery_note="(rambling)"),
        CustomDialogueLine(character="EVA", line=" ".join(["word"] * 50), delivery_note="(monotone)")
    ]
    overflow_scene = SceneScreenplay(
        scene_number=1,
        scene_heading="INT. HABITAT CORE - NIGHT",
        action_lines=["Alex talks excessively."],
        dialogue=verbose_dialogue,
        estimated_screen_time_seconds=20
    )
    is_valid, msg = validate_screenplay_word_count([overflow_scene], target_duration_seconds=30)
    if not is_valid and "OVER_FLOW" in msg:
        logger.info(f"✔ Word count overflow caught correctly: {msg}")
    else:
        logger.error(f"❌ Overflow check failed to return correct feedback: {is_valid}, {msg}")

    # 5. Test Scene-level independent regeneration (Diff-friendly check)
    logger.info("Testing Per-Scene Regeneration Mock Call")
    # We simulate calling regenerate_scene to check fallback and wrapper pathways
    mock_beat = {"scene_number": 2, "location": "Martian Ridge", "time_of_day": "DAY", "description": "Alex walks", "estimated_duration": 15}
    mock_chars = [{"name": "Alex", "role": "Protagonist"}]
    
    # Since we don't have API keys active, it runs fallback or catches validation.
    # We mock the LLM generate function to test the retry logic.
    with patch("fastapi_service.agents.screenplay_writer.generate_single_scene_screenplay_raw") as mock_raw:
        # First call returns invalid character (raises exception), second call fixes it
        mock_raw.side_effect = [
            SceneScreenplay(
                scene_number=2, scene_heading="EXT. RIDGE - DAY", action_lines=["Alex walks."],
                dialogue=[CustomDialogueLine(character="Bob", line="Hello", delivery_note="")], # Bob is invalid
                estimated_screen_time_seconds=15
            ),
            SceneScreenplay(
                scene_number=2, scene_heading="EXT. RIDGE - DAY", action_lines=["Alex walks."],
                dialogue=[CustomDialogueLine(character="Alex", line="Hello", delivery_note="")], # Alex is valid
                estimated_screen_time_seconds=15
            )
        ]
        
        corrected_scene = regenerate_scene(
            movie_title="Mock Movie",
            characters=mock_chars,
            scene_beat=mock_beat,
            target_word_count=20,
            api_key="mock-key",
            feedback="Fix character Bob"
        )
        
        assert corrected_scene.dialogue[0].character == "Alex"
        logger.info("✔ Per-scene independent regeneration and validation retry completed successfully.")

    logger.info("=== SCREENPLAY AGENT UNIT TESTS COMPLETED SUCCESSFULLY ===")

if __name__ == '__main__':
    run_screenplay_tests()
