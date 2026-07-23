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
logger = logging.getLogger("TestVideoEditor")

# Mock database module to prevent dependency exception
mock_db = MagicMock()
sys.modules['fastapi_service.database'] = mock_db

# Import targets
from fastapi_service.pipeline.video_editor import assemble_movie, create_text_card_image, duck_background_music

# Dummy state container
class DummyState:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

def run_editor_tests():
    logger.info("=== STARTING VIDEO EDITOR AGENT UNIT TESTS ===")
    
    # Setup dummy directory structure
    dummy_dir = "storage/movies/1"
    os.makedirs(dummy_dir, exist_ok=True)
    
    # 1. Create Mock Video Shot Clips and Audio Files
    clip_1 = f"storage/movies/1/scene_1_shot_1.mp4"
    clip_2 = f"storage/movies/1/scene_1_shot_2.mp4"
    
    # Write blank dummy video placeholders
    with open(clip_1, "wb") as f:
        f.write(b"MOCK SHOT 1 VIDEO DATA")
    with open(clip_2, "wb") as f:
        f.write(b"MOCK SHOT 2 VIDEO DATA")

    # 2. Create Dummy Audio segments (Dialogue & Music)
    dial_wav = f"storage/movies/1/dialogue_line.wav"
    music_wav = f"storage/movies/1/bg_music.wav"
    
    with open(dial_wav, "wb") as f:
        f.write(b"MOCK DIALOGUE AUDIO DATA")
    with open(music_wav, "wb") as f:
        f.write(b"MOCK MUSIC AUDIO DATA")

    # 3. Test Title Card Image Generation (Pillow)
    logger.info("Step A: Testing Pillow Card Image Renderer")
    title_path = f"storage/movies/1/title_card.png"
    create_text_card_image("Red Solitude", "Genre: Sci-Fi | A CineForge AI Film", title_path)
    assert os.path.exists(title_path)
    logger.info("✔ Title card PNG rendered successfully.")

    # 4. Mock FFmpeg subprocess runs to test size-cap CRF retry loop
    logger.info("\nStep B: Testing FFmpeg Export size-cap retry loop")
    
    # Setup mock subprocess response
    with patch("subprocess.run") as mock_run:
        # First call: returns success but size is over cap (e.g. mock getsize size = 25MB > 20MB)
        # Second call: returns success, size is under cap (e.g. mock getsize size = 15MB < 20MB)
        mock_run.return_value = MagicMock(returncode=0)
        
        # Patch os.path.getsize to simulate oversize first, then fits size limit
        with patch("os.path.getsize") as mock_getsize:
            mock_getsize.side_effect = [
                25 * 1024 * 1024, # Attempt 1: 25MB (CRF 23)
                15 * 1024 * 1024, # Attempt 2: 15MB (CRF 27)
                1 * 1024 * 1024   # Extra checks
            ]
            
            # Setup scene data sequence input
            scenes_data = [
                {
                    "scene_number": 1,
                    "emotional_beat": "tense",
                    "clips": [
                        {"shot_number": 1, "file_path": clip_1, "duration": 3.0},
                        {"shot_number": 2, "file_path": clip_2, "duration": 4.0}
                    ]
                }
            ]
            
            characters = [{"name": "Alex"}, {"name": "EVA"}]
            output_movie = f"storage/movies/1/final_movie.mp4"
            
            # Mock MoviePy timeline writer to bypass host exceptions
            with patch("fastapi_service.pipeline.video_editor.moviepy_installed", True):
                with patch("fastapi_service.pipeline.video_editor.VideoFileClip") as mock_clip, \
                     patch("fastapi_service.pipeline.video_editor.concatenate_videoclips") as mock_concat, \
                     patch("fastapi_service.pipeline.video_editor.ImageClip") as mock_img_clip:
                     
                     # Mock timeline exports
                     mock_concat.return_value = MagicMock()
                     
                     # Trigger assembly
                     assemble_movie(
                         scenes_data=scenes_data,
                         movie_id=1,
                         title="Red Solitude",
                         genre="Sci-Fi",
                         characters=characters,
                         output_path=output_movie,
                         size_cap_mb=20.0 # 20MB cap
                     )
            
            # Assertions: Subprocess should be called exactly twice because the first attempt exceeded the cap
            assert mock_run.call_count == 2
            logger.info("✔ FFmpeg CRF retry loop executed. Compresses and resubmits correctly.")

    # Cleanup test files
    for f in [clip_1, clip_2, dial_wav, music_wav, title_path, output_movie]:
        if os.path.exists(f):
            try:
                os.remove(f)
            except Exception:
                pass

    logger.info("=== VIDEO EDITOR AGENT UNIT TESTS COMPLETED SUCCESSFULLY ===")

if __name__ == '__main__':
    run_editor_tests()
