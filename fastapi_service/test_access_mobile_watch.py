import os
import sys
import json
import logging
from unittest.mock import MagicMock

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TestAccessMobileWatch")

# Mock database module to prevent dependency exception
mock_db = MagicMock()
sys.modules['fastapi_service.database'] = mock_db

# Mock Celery to prevent host import exceptions
sys.modules['celery'] = MagicMock()
sys.modules['celery.exceptions'] = MagicMock()

# Import targets
from fastapi_service.pipeline.accessibility_service import detect_silent_dialogue_gaps, generate_audio_description_text, mix_audio_description_track
from fastapi_service.pipeline.dubbing_service import generate_translation_prompt, fit_audio_to_duration
from fastapi_service.pipeline.mobile_service import map_mobile_prompt_to_schema, get_platform_export_parameters
from fastapi_service.pipeline.gallery_service import clone_movie_text_layer, get_movie_remix_attribution_details
from fastapi_service.pipeline.watchparty_service import (
    join_watch_party_room,
    sync_playback_state,
    broadcast_emoji_reaction,
    append_ephemeral_chat,
    PlaybackState,
    EmojiReaction
)

def run_accessibility_tests():
    logger.info("=== STARTING ACCESSIBILITY, DUBBING, MOBILE, REMIX, & WATCHPARTY TESTS ===")

    mock_db.execute_single.return_value = None
    mock_db.execute_query.return_value = None

    # 1. Audio Descriptions
    logger.info("\nTask 11: Testing Accessibility Audio Descriptions")
    dialogue = [
        {"start": 1.5, "end": 3.0}, # Line 1
        {"start": 6.5, "end": 8.0}  # Line 2 (gap of 3.5s between 3.0 and 6.5!)
    ]
    gaps = detect_silent_dialogue_gaps(dialogue, total_duration=10.0, min_gap=2.0)
    logger.info(f"AD detected gaps: {gaps}")
    assert len(gaps) == 2
    # Actually, let's look at counts:
    # 0.0 to 1.5 -> gap=1.5s (<2.0) -> skipped
    # 3.0 to 6.5 -> gap=3.5s (>=2.0) -> gaps.append (start=3.0, end=6.5)
    # 8.0 to 10.0 -> gap=2.0s (>=2.0) -> gaps.append (start=8.0, end=10.0)
    # So gaps should count 2! Let's assert count is 2.
    assert len(gaps) == 2
    
    # Narration prompt
    narr_text = generate_audio_description_text("Astronaut runs away from sand dunes.", max_duration_seconds=3.0)
    logger.info(f"Generated narration text: {narr_text}")
    assert "Astronaut" in narr_text
    
    # FFmpeg command
    cmd = mix_audio_description_track("dialogue.wav", "narrator.wav", "out.wav", start_offset=3.0)
    assert "amix" in cmd
    logger.info("✔ Audio descriptions and ducking mixers verified successfully.")

    # 2. Dubbing track
    logger.info("\nTask 12: Testing Multi-Language Dubbing Time-Stretching")
    t_prompt = generate_translation_prompt("Help me!", "es", "shouting in fear")
    assert "Translate" in t_prompt
    
    # Time-stretch speed adjustment (simulate using mock audio segment)
    mock_segment = MagicMock()
    mock_segment.frame_rate = 44100
    mock_segment.raw_data = b"1234"
    # mock len(mock_segment) to return 1000ms
    mock_segment.__len__.return_value = 1000
    
    fit_segment = fit_audio_to_duration(mock_segment, target_duration_ms=800)
    logger.info(f"Stretch fitting successfully spawned segment overrides: {fit_segment}")
    assert fit_segment is not None
    logger.info("✔ Dialogue dubbing translation prompts and speed stretch fitters verified successfully.")

    # 3. Mobile Shorts
    logger.info("\nTask 13: Testing Mobile-First 9:16 Video Presets")
    mobile_data = map_mobile_prompt_to_schema("A cat jumping", "funny")
    logger.info(f"Mobile prompt data: {mobile_data}")
    assert mobile_data["aspect_ratio"] == "9:16"
    assert "comedy" in mobile_data["user_prompt"]
    
    tiktok_preset = get_platform_export_parameters("TikTok")
    assert tiktok_preset["resolution"] == "1080x1920"
    logger.info("✔ Vertical mobile presets and vibe selector prompt layouts verified successfully.")

    # 4. Remix Gallery
    logger.info("\nTask 14: Testing Remix Public Gallery Cloners")
    mock_db.execute_single.side_effect = [
        # Cloner selects:
        {
            "title": "Star Wars", "user_prompt": "Space ship", "genre": "Sci-Fi",
            "tone": "Dark", "target_duration_seconds": 60, "story_summary": "summary", "screenplay_raw": "screenplay"
        },
        {"id": 405}, # Cloned movie ID return
        
        # Attribution lookup selects:
        {"remixed_from_id": 102, "parent_title": "Star Wars", "parent_creator": "George"}
    ]
    mock_db.execute_query.return_value = [
        {"scene_number": 1, "location": "Bridge", "time_of_day": "Day", "description": "details",
         "emotional_beat": "tense", "screenplay_text": "text", "estimated_duration": 10, "order_index": 0}
    ]
    
    cloned_id = clone_movie_text_layer(original_movie_id=102, new_owner_id=15)
    logger.info(f"Cloned Remix Movie ID: {cloned_id}")
    assert cloned_id == 405
    
    attribution = get_movie_remix_attribution_details(cloned_id)
    logger.info(f"Remix attribution details: {attribution}")
    assert attribution["is_remix"] is True
    assert "Star Wars" in attribution["attribution_label"]
    logger.info("✔ Text-only gallery remix cloners and attribution locks verified successfully.")

    # 5. Watch Parties
    logger.info("\nTask 15: Testing Watch Parties Websockets Sync")
    # Join room
    room_details = join_watch_party_room(room_id="party_room_1", movie_id=405, user_id=12)
    logger.info(f"Joined room details: {room_details}")
    assert room_details["room_id"] == "party_room_1"
    
    # Sync playback
    sync_msg = sync_playback_state("party_room_1", PlaybackState(
        movie_id=405,
        status="PLAY",
        timestamp_seconds=45.2,
        sender_id=12
    ))
    logger.info(f"Sync playback message: {sync_msg}")
    assert sync_msg["status"] == "PLAY"
    
    # Reactions
    burst = broadcast_emoji_reaction("party_room_1", EmojiReaction(
        user_id=12,
        emoji="🔥",
        timestamp_seconds=45.2
    ))
    logger.info(f"Emoji reaction broadcast message: {burst}")
    assert burst["emoji"] == "🔥"
    
    # Chat message
    chat = append_ephemeral_chat("party_room_1", user_id="12", message="Awesome scene!")
    logger.info(f"Chat broadcast message: {chat}")
    assert chat["chat"]["message"] == "Awesome scene!"
    logger.info("✔ WebSocket watch-party rooms, reactions, and ephemeral chats verified successfully.")

    logger.info("=== ALL ACCESSIBILITY AND ACCELERATION PIPELINE TESTS COMPLETED SUCCESSFULLY ===")

if __name__ == '__main__':
    run_accessibility_tests()
