import os
import sys
import logging
from unittest.mock import MagicMock, patch

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TestSubtitle")

# Mock database module to prevent dependency exception
mock_db = MagicMock()
sys.modules['fastapi_service.database'] = mock_db

# Import targets
from fastapi_service.pipeline.subtitle_gen import (
    format_srt_timestamp,
    generate_cumulative_srt,
    burn_subtitles_ffmpeg,
    transcribe_audio_whisper
)

def run_subtitle_tests():
    logger.info("=== STARTING SUBTITLE AGENT UNIT TESTS ===")

    # 1. Test SRT Timestamp Formatter
    logger.info("Step A: Testing format_srt_timestamp formatter")
    t1 = format_srt_timestamp(0.0)
    t2 = format_srt_timestamp(61.523)
    t3 = format_srt_timestamp(3665.12)
    logger.info(f"0s formatted: {t1}")
    logger.info(f"61.523s formatted: {t2}")
    logger.info(f"3665.12s formatted: {t3}")
    
    assert t1 == "00:00:00,000"
    assert t2 == "00:01:01,523"
    assert t3 == "01:01:05,120"
    logger.info("✔ Timestamp formats verified.")

    # 2. Test Cumulative SRT Writer
    logger.info("\nStep B: Testing generate_cumulative_srt")
    # 2 scenes, each having transcripts. 
    # Title card delay = 3.0 seconds.
    # Scene 1: 10s duration. Dialogue ends at t=9s relative.
    # Scene 2: 12s duration.
    scenes_transcripts = [
        [
            {"start": 1.0, "end": 4.0, "text": "Hello Martian ridge."},
            {"start": 5.0, "end": 9.0, "text": "Copy that, Houston."}
        ],
        [
            {"start": 2.0, "end": 6.0, "text": "Hatch seal is locked."},
            {"start": 7.0, "end": 10.0, "text": "Atmosphere stable."}
        ]
    ]
    scene_durations = [10.0, 12.0]
    srt_out_path = "storage/movies/1/subtitles_test.srt"
    os.makedirs(os.path.dirname(srt_out_path), exist_ok=True)
    
    generate_cumulative_srt(scenes_transcripts, scene_durations, srt_out_path)
    
    # Assert srt content
    assert os.path.exists(srt_out_path)
    with open(srt_out_path, "r", encoding="utf-8") as f:
        content = f.read()
        print("\n" + "="*50)
        print("COMPILED CUMULATIVE SRT FILE:")
        print(content)
        print("="*50 + "\n")
        
        # Verify cumulative offsets added properly:
        # Scene 1 offset starts at 3.0s, so line 1 starts at 1.0+3.0 = 4.0s
        # Line 2 starts at 5.0+3.0 = 8.0s
        # Scene 2 offset starts at 3.0+10.0 = 13.0s, so line 3 starts at 2.0+13.0 = 15.0s
        # Line 4 starts at 7.0+13.0 = 20.0s
        assert "00:00:04,000 --> 00:00:07,000" in content
        assert "00:00:08,000 --> 00:00:12,000" in content
        assert "00:00:15,000 --> 00:00:19,000" in content
        assert "00:00:20,000 --> 00:00:23,000" in content
        
    logger.info("✔ Cumulative SRT generation compiled with mathematically accurate scene offsets.")

    # 3. Test FFmpeg Burn-In command mocking
    logger.info("\nStep C: Testing FFmpeg Subtitles burn-in command builder")
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        success = burn_subtitles_ffmpeg(
            input_video_path="storage/movies/1/temp_raw_assemble.mp4",
            srt_path=srt_out_path,
            output_video_path="storage/movies/1/final_movie_captioned.mp4"
        )
        assert success
        assert mock_run.call_count == 1
        args = mock_run.call_args[0][0]
        # Make sure -vf subtitles filter is included
        assert "-vf" in args
        assert "subtitles=" in args[args.index("-vf") + 1]
        logger.info("✔ FFmpeg Burn-In subtitle filter formatting verified.")

    # Cleanup
    if os.path.exists(srt_out_path):
        os.remove(srt_out_path)

    logger.info("=== SUBTITLE AGENT UNIT TESTS COMPLETED SUCCESSFULLY ===")

if __name__ == '__main__':
    run_subtitle_tests()
