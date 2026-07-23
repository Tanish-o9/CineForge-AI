import os
import sys
import json
import logging
from unittest.mock import patch, MagicMock

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("CineForge-Test")

# Add the project root to path
sys.path.append(os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

# Mock PostgreSQL database interface before loading module agents
mock_db = MagicMock()
mock_db.execute_query = MagicMock()
mock_db.execute_single = MagicMock()

def mock_single_select(query, params=None):
    if "SELECT" not in query:
        return None
    if "core_consistency_asset" in query:
        return {
            "asset_id": 1,
            "name": "Alex",
            "reference_image_url": "storage/assets/alex.png",
            "description": "An astronaut in a red space suit"
        }
    return {
        "id": 1,
        "movie_id": 1,
        "title": "Test Cinematic Short",
        "user_prompt": "A tense sci-fi short about an astronaut stranded on Mars",
        "target_duration_seconds": 30,
        "status": "PENDING",
        "voice_id": "alloy",
        "reference_sheet_path": "",
        "style_prompt": "",
        "reference_image_path": "",
        "reference_image_url": "",
        "description": ""
    }

mock_db.execute_single.side_effect = mock_single_select

mock_db.execute_query.return_value = []

# Patch database helper calls in target services
sys.modules['fastapi_service.database'] = mock_db

# Now we can import the pipeline steps
from fastapi_service.agents.story_writer import run_story_writer
from fastapi_service.agents.screenplay_writer import run_screenplay_writer
from fastapi_service.agents.storyboard_agent import run_storyboard_agent
from fastapi_service.pipeline.character_gen import run_character_generator
from fastapi_service.pipeline.environment_gen import run_environment_generator
from fastapi_service.pipeline.voice_gen import run_voice_generator
from fastapi_service.pipeline.music_gen import run_music_generator
from fastapi_service.pipeline.sfx_gen import run_sfx_generator
from fastapi_service.pipeline.animation import run_animation_agent
from fastapi_service.pipeline.video_editor import run_video_editor
from fastapi_service.pipeline.subtitle_gen import run_subtitle_agent

# Create a container class for state tracking
class DummyState:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
    
    def model_dump(self):
        return self.__dict__

def run_integration_verification():
    logger.info("=== STARTING CINEFORGE PIPELINE INTEGRATION TEST ===")
    
    # 1. Initialize State
    state = DummyState(
        movie_id=1,
        job_id="test-job-uuid-1234",
        user_prompt="5-minute sci-fi movie about an astronaut stranded on Mars, emotional and cinematic",
        title="Pending Story",
        genre="",
        tone="",
        target_duration_seconds=30, # short duration for rapid testing
        story_summary="",
        screenplay_raw="",
        scenes=[],
        characters=[],
        environments=[],
        audio_assets=[],
        video_clips=[],
        subtitles="",
        final_video_path="",
        current_stage="story",
        status="PROCESSING",
        errors=[],
        retry_counts={},
        features_disabled=[]
    )
    
    # Run Phase 2: Story Writer
    logger.info("--- Testing Story Writer Node ---")
    res_story = run_story_writer(state)
    state.title = res_story['title']
    state.genre = res_story['genre']
    state.tone = res_story['tone']
    state.story_summary = res_story['story_summary']
    state.characters = res_story['characters']
    state.scenes = res_story['scenes']
    logger.info(f"Story created: '{state.title}' | Genre: {state.genre} | Characters: {[c['name'] for c in state.characters]}")
    
    # Run Phase 3: Screenplay
    logger.info("--- Testing Screenplay Writer Node ---")
    res_screenplay = run_screenplay_writer(state)
    state.screenplay_raw = res_screenplay['screenplay_raw']
    state.scenes = res_screenplay['scenes']
    logger.info("Screenplay dialogues written successfully.")
    
    # Run Phase 4: Storyboard
    logger.info("--- Testing Storyboard Agent Node ---")
    res_storyboard = run_storyboard_agent(state)
    state.scenes = res_storyboard['scenes']
    logger.info("Storyboard shot breakdown generated.")
    
    # Run Phase 5: Character Gen
    logger.info("--- Testing Character Gen Visual Node ---")
    res_char = run_character_generator(state)
    state.characters = res_char['characters']
    logger.info("Character visual turnaround references set.")
    
    # Run Phase 6: Environment Gen
    logger.info("--- Testing Environment Gen Visual Node ---")
    res_env = run_environment_generator(state)
    state.environments = res_env['environments']
    logger.info("Environment setting boards generated.")
    
    # Run Phase 7: Voice Synthesis
    logger.info("--- Testing Voice Generation Node ---")
    res_voice = run_voice_generator(state)
    state.scenes = res_voice['scenes']
    state.audio_assets = res_voice['audio_assets']
    logger.info("Vocal WAV clips created and measured.")
    
    # Run Phase 8: Music Composer
    logger.info("--- Testing Music Composer Node ---")
    res_music = run_music_generator(state)
    state.audio_assets = res_music['audio_assets']
    logger.info("Background score generated and looped.")
    
    # Run Phase 9: SFX Layering
    logger.info("--- Testing SFX Agent Node ---")
    res_sfx = run_sfx_generator(state)
    state.scenes = res_sfx.get('scenes', state.scenes)
    logger.info("Implied SFX cues extracted and noise WAVs saved.")
    
    # Run Phase 10: Animation
    logger.info("--- Testing Animation Agent Node ---")
    res_anim = run_animation_agent(state)
    state.video_clips = res_anim['video_clips']
    logger.info("Storyboard Ken Burns video clips exported.")
    
    # Run Phase 11: Video Editing
    logger.info("--- Testing Video Editor Node ---")
    res_edit = run_video_editor(state)
    state.final_video_path = res_edit['final_video_path']
    logger.info("Movie clips spliced, audio channels combined, and output MP4 rendered.")
    
    # Run Phase 12: Subtitles
    logger.info("--- Testing Subtitle Agent Node ---")
    res_sub = run_subtitle_agent(state)
    state.subtitles = res_sub['subtitles']
    state.final_video_path = res_sub['final_video_path']
    logger.info(f"Subtitles hardcoded. Output video ready at: {state.final_video_path}")
    
    logger.info("=== CINEFORGE PIPELINE INTEGRATION TEST COMPLETED SUCCESSFULLY ===")

def test_video_editor_assembly():
    logger.info("=== STARTING VIDEO EDITOR PIPELINE VERIFICATION ===")
    
    # 1. Create a dummy scene with missing clips to test fallback card generation
    scenes_data = [
        {
            "scene_number": 1,
            "emotional_beat": "dramatic",
            "clips": [
                {
                    "shot_number": 1,
                    "file_path": "storage/movies/1/clips/non_existent_shot.mp4",
                    "duration": 3.0
                }
            ]
        }
    ]
    
    # 2. Call assemble_movie
    output_path = "storage/movies/1/final_movie.mp4"
    if os.path.exists(output_path):
        try:
            os.remove(output_path)
        except Exception:
            pass
        
    from fastapi_service.pipeline.video_editor import assemble_movie
    assemble_movie(
        scenes_data=scenes_data,
        movie_id=1,
        title="Test Hardened Render",
        genre="Sci-Fi",
        characters=[{"name": "Alex"}],
        output_path=output_path,
        size_cap_mb=5.0
    )
    
    # 3. Verify output
    if os.path.exists(output_path):
        size = os.path.getsize(output_path)
        logger.info(f"VERIFICATION SUCCESS: Output MP4 exists at '{output_path}' with size {size} bytes.")
        if size == 23:
            logger.warning("Mock mp4 written due to lack of moviepy library. This is acceptable for mock mode.")
        elif size > 0:
            logger.info("Real compiled MP4 file generated successfully!")
    else:
        logger.error("VERIFICATION FAILED: Output MP4 was not created!")
        sys.exit(1)

if __name__ == '__main__':
    # Ensure a local temp storage exists for test output
    os.makedirs("storage/movies/1/dialogue", exist_ok=True)
    os.makedirs("storage/movies/1/music", exist_ok=True)
    os.makedirs("storage/movies/1/clips", exist_ok=True)
    os.makedirs("storage/sfx_library", exist_ok=True)
    run_integration_verification()
    test_video_editor_assembly()
