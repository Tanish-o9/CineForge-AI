import os
import sys
import json
import logging
from unittest.mock import MagicMock

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TestStoryboard")

# Mock database module to prevent dependency exception
sys.modules['fastapi_service.database'] = MagicMock()

# Import targets
from fastapi_service.agents.storyboard_agent import StoryboardShot, build_image_prompt

def run_storyboard_tests():
    logger.info("=== STARTING STORYBOARD AGENT UNIT TESTS ===")

    # 1. Mars Storm Scene Specifications
    environment_style = "A howling Martian dust storm, reddish-orange dust clouds, giant rust canyons, low visibility, dark atmosphere"
    
    characters = [
        {
            "name": "Alex",
            "physical_description": "Astronaut in a battered white spacesuit with gold visor and scuff marks, dark hair, worried gaze"
        },
        {
            "name": "EVA",
            "physical_description": "A sleek, glowing blue holographic AI assistant panel hovering inside the suit HUD"
        }
    ]

    # 2. Construct StoryboardShot representing the scene
    shot = StoryboardShot(
        shot_number=1,
        shot_type="WIDE",
        camera_movement="PAN-LEFT",
        lighting_description="dim atmospheric light with orange storm clouds filtering sunlight",
        character_positions={
            "Alex": "center-left",
            "EVA": "top-right-background"
        },
        facial_expression={
            "Alex": "terrified",
            "EVA": "neutral"
        },
        mood="tense and cinematic",
        color_palette="rust red, dust orange, cyan terminal accents",
        duration_seconds=10,
        action_focus="Alex struggles to walk forward against heavy orange wind currents"
    )

    # 3. Compile prompts
    logger.info("Executing build_image_prompt on Mars-storm scene shot...")
    prompts = build_image_prompt(shot, characters, environment_style)
    
    # 4. Print results
    print("\n" + "="*50)
    print("STORYBOARD SHOT METADATA INPUT:")
    print(json.dumps(shot.model_dump(), indent=2))
    print("-"*50)
    print("GENERATED POSITIVE SDXL/FLUX PROMPT:")
    print(prompts["prompt"])
    print("-"*50)
    print("GENERATED NEGATIVE PROMPT:")
    print(prompts["negative_prompt"])
    print("="*50 + "\n")
    
    # Simple assertions
    assert "WIDE" in prompts["prompt"]
    assert "Alex" in prompts["prompt"]
    assert "battered white spacesuit" in prompts["prompt"]
    assert "Martian dust storm" in prompts["prompt"]
    logger.info("✔ Storyboard image prompt built successfully with all descriptions and framing metadata.")
    
    logger.info("=== STORYBOARD AGENT UNIT TESTS COMPLETED SUCCESSFULLY ===")

if __name__ == '__main__':
    run_storyboard_tests()
