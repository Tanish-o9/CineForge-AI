import os
import sys
import json
import logging
from unittest.mock import MagicMock, patch

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TestVoiceGen")

# Mock database module to prevent dependency exception
mock_db = MagicMock()
sys.modules['fastapi_service.database'] = mock_db

# Import targets
from fastapi_service.pipeline.voice_gen import (
    MockTTSProvider,
    get_or_assign_voice,
    process_scene_dialogue_batch,
    post_process_audio_style
)

def run_voice_tests():
    logger.info("=== STARTING VOICE GENERATION UNIT TESTS ===")
    
    # 1. Test Persistent Voice Mapping
    # Mocking database response: first call returns None (unassigned), second call returns cache mapping
    mock_db.execute_single.side_effect = [
        None, # first call to get_or_assign_voice for Alex -> assigns voice
        {"voice_id": "onyx"}, # second call to get_or_assign_voice for Alex -> CACHE_HIT
    ]
    mock_db.execute_query.return_value = None
    
    logger.info("Step A: Assigning voice mapping to character 'Alex' for the first time")
    voice_1 = get_or_assign_voice("Alex")
    logger.info(f"Assigned voice ID: {voice_1}")
    
    logger.info("Step B: Querying voice mapping for 'Alex' again (should be cached)")
    voice_2 = get_or_assign_voice("Alex")
    logger.info(f"Cached voice ID: {voice_2}")
    
    assert voice_2 == "onyx" # matches the mocked DB row cache hit!
    logger.info("✔ Persistent voice assignment verified.")

    # 2. Test Audio Styling Post-processing
    logger.info("\nStep C: Testing Audio styling post-processing fallback checks")
    dummy_wav_path = "storage/movies/1/dialogue/test_tone.wav"
    os.makedirs(os.path.dirname(dummy_wav_path), exist_ok=True)
    
    # Generate a baseline mock wave file
    provider = MockTTSProvider()
    provider.generate_speech("This is a test line of dialogue.", "onyx", "neutral", dummy_wav_path)
    
    logger.info("Testing shout post-processing volume modification...")
    post_process_audio_style(dummy_wav_path, "shouting")
    
    logger.info("Testing whisper post-processing volume modification...")
    post_process_audio_style(dummy_wav_path, "whispering")
    
    # 3. Test Batch Processing for full scene
    logger.info("\nStep D: Testing Batch Scene Dialogue compilation")
    scene_dialogues = [
        {"character": "Alex", "line": "Houston, do you copy me?", "delivery_note": "anxiously"},
        {"character": "EVA", "line": "Signal strength is at two percent.", "delivery_note": "whispering"},
        {"character": "Alex", "line": "Help me!", "delivery_note": "shouting"}
    ]
    
    # Mock db select for get_or_assign_voice
    mock_db.execute_single.side_effect = [
        {"voice_id": "onyx"},
        {"voice_id": "nova"},
        {"voice_id": "onyx"}
    ]
    
    processed_dialogues = process_scene_dialogue_batch(
        movie_id=1,
        scene_id=10,
        scene_number=1,
        dialogues_list=scene_dialogues,
        tts_provider=provider
    )
    
    print("\n" + "="*50)
    print("PROCESSED BATCH DIALOGUES RESULT:")
    print(json.dumps(processed_dialogues, indent=2))
    print("="*50 + "\n")
    
    assert len(processed_dialogues) == 3
    assert processed_dialogues[0]["character"] == "Alex"
    assert processed_dialogues[1]["delivery_note"] == "whispering"
    assert processed_dialogues[2]["duration_seconds"] > 0
    logger.info("✔ Batch scene dialogue generated and measured successfully.")

    # Clean up test outputs
    if os.path.exists(dummy_wav_path):
        os.remove(dummy_wav_path)
    for idx in range(3):
        f = f"storage/movies/1/dialogue/scene_1_line_{idx}.wav"
        if os.path.exists(f):
            os.remove(f)

    logger.info("=== VOICE GENERATION UNIT TESTS COMPLETED SUCCESSFULLY ===")

if __name__ == '__main__':
    run_voice_tests()
