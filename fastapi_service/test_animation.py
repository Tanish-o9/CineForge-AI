import os
import sys
import json
import logging
from unittest.mock import MagicMock, patch
from PIL import Image

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TestAnimation")

# Mock database module to prevent dependency exception
mock_db = MagicMock()
sys.modules['fastapi_service.database'] = mock_db

# Import targets
from fastapi_service.pipeline.animation import animate_shot, animate_parallax_shot, run_animation_agent

# Dummy state container
class DummyState:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

def run_animation_tests():
    logger.info("=== STARTING ANIMATION AGENT UNIT TESTS ===")
    
    # Setup dummy directory structure
    dummy_dir = "storage/movies/1/clips"
    os.makedirs(dummy_dir, exist_ok=True)
    
    # Create dummy storyboard images (flat scene + character fg layer)
    bg_img_path = "storage/movies/1/scene_1_shot_1.png"
    fg_char_path = "storage/movies/1/char_alex_fg.png"
    
    # Create flat 1920x1080 background
    bg_img = Image.new("RGB", (1920, 1080), "#1C1C1C")
    bg_img.save(bg_img_path)
    
    # Create 800x800 foreground character (e.g. transparent blue silhouette)
    fg_img = Image.new("RGBA", (800, 800), (0, 120, 255, 255))
    fg_img.save(fg_char_path)

    # 1. Test Flat Shot Animations (Static / Zoom / Panning)
    logger.info("Step A: Testing Flat Shot Panning Animation")
    output_1 = animate_shot(
        image_path=bg_img_path,
        camera_movement="PAN-LEFT",
        duration_seconds=5.0
    )
    logger.info(f"Animated Panning output ready at: {output_1}")
    assert os.path.exists(output_1)

    # 2. Test Parallax Layers Compositing
    logger.info("\nStep B: Testing Parallax Overlay Compositing")
    output_parallax = os.path.join(dummy_dir, "scene_1_shot_1_parallax.mp4")
    output_2 = animate_parallax_shot(
        bg_path=bg_img_path,
        fg_path=fg_char_path,
        camera_movement="ZOOM-IN",
        duration_seconds=4.0,
        clip_path=output_parallax
    )
    logger.info(f"Animated Parallax output ready at: {output_2}")
    assert os.path.exists(output_2)

    # 3. Test Scene Syncing Loop
    logger.info("\nStep C: Testing Animation Syncing Loop against database assets")
    # Mocking database query responses
    # Mock 1: execute_single returns scene primary key
    mock_db.execute_single.return_value = {"id": 10}
    # Mock 2: execute_query returns 1 storyboard image asset
    mock_image_asset = {
        "file_path": bg_img_path,
        "meta_data": json.dumps({
            "shot_number": 1,
            "camera_movement": "ZOOM-OUT",
            "duration_seconds": 10.0, # estimated 10 seconds
            "character_overlay_path": fg_char_path
        })
    }
    # Mock 3: execute_query returns 1 measured dialogue vocal track
    mock_voice_asset = {
        "file_path": "storage/movies/1/dialogue/scene_1_line_0.wav",
        "meta_data": json.dumps({
            "duration": 3.75 # measured 3.75 seconds!
        })
    }
    
    # We configure query outputs
    mock_db.execute_query.side_effect = [
        [mock_image_asset], # first: image assets
        [mock_voice_asset], # second: voice assets
        None # third: insert query execution
    ]
    
    state = DummyState(
        movie_id=1,
        scenes=[{"scene_number": 1}],
        video_clips=[]
    )
    
    res_anim = run_animation_agent(state)
    logger.info("Animation Syncing Loop complete.")
    logger.info(f"Spliced Video Clips data: {res_anim['video_clips']}")
    
    # Verify that the shot's duration was synced from 10.0s down to 3.75s!
    assert res_anim['video_clips'][0]['clips'][0]['duration'] == 3.75
    logger.info("✔ Duration successfully synced to voice track asset.")

    # Cleanup dummy files
    for f in [bg_img_path, fg_char_path, output_1, output_2]:
        if os.path.exists(f):
            os.remove(f)
    for idx in [1]:
        f = f"storage/movies/1/clips/scene_1_shot_{idx}.mp4"
        if os.path.exists(f):
            os.remove(f)

    logger.info("=== ANIMATION AGENT UNIT TESTS COMPLETED SUCCESSFULLY ===")

if __name__ == '__main__':
    run_animation_tests()
