import os
import json
import logging
import hashlib
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Tuple

# Optional imports for audio processing
try:
    import soundfile as sf
except ImportError:
    sf = None

try:
    from pydub import AudioSegment
except ImportError:
    AudioSegment = None

# Database helpers
from fastapi_service.database import execute_query, execute_single

# Resilience helpers
from fastapi_service.pipeline.resilience import CircuitBreaker, resilient_call

logger = logging.getLogger(__name__)

# 1. TTS Provider Interface (ABC)
class TTSProvider(ABC):
    @abstractmethod
    def generate_speech(self, text: str, voice_id: str, delivery_note: str, output_path: str) -> float:
        """
        Generates audio file from text. Returns the exact measured duration in seconds.
        """
        pass

# Instantiate circuit breakers for TTS services
elevenlabs_breaker = CircuitBreaker(name="ElevenLabsTTS", threshold=3, recovery_timeout=5.0)
openai_breaker = CircuitBreaker(name="OpenAITTS", threshold=3, recovery_timeout=5.0)

class ElevenLabsProvider(TTSProvider):
    def __init__(self, api_key: str):
        self.api_key = api_key

    @resilient_call(elevenlabs_breaker, max_retries=3, base_delay=0.1)
    def generate_speech(self, text: str, voice_id: str, delivery_note: str, output_path: str) -> float:
        import httpx
        logger.info(f"Calling ElevenLabs TTS for voice {voice_id}")
        
        # ElevenLabs delivery note mapping (parameter adjustments)
        stability = 0.5
        similarity_boost = 0.75
        style = 0.0
        
        note = delivery_note.lower()
        if "shout" in note or "scream" in note or "loudly" in note:
            stability = 0.30 # More expressive
            style = 0.25
        elif "whisper" in note or "softly" in note or "quietly" in note:
            stability = 0.65 # More flat / controlled
            style = 0.0
            
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": self.api_key
        }
        data = {
            "text": text,
            "model_id": "eleven_monolingual_v1",
            "voice_settings": {
                "stability": stability,
                "similarity_boost": similarity_boost,
                "style": style
            }
        }
        
        response = httpx.post(url, json=data, headers=headers, timeout=30.0)
        if response.status_code != 200:
            raise Exception(f"ElevenLabs error {response.status_code}: {response.text}")
            
        with open(output_path, "wb") as f:
            f.write(response.content)
            
        # Post process if provider doesn't support pitch/speed natively but we want custom adjustments
        post_process_audio_style(output_path, delivery_note)
        
        return measure_audio_duration(output_path, text)

class OpenAITTSProvider(TTSProvider):
    def __init__(self, api_key: str):
        self.api_key = api_key

    @resilient_call(openai_breaker, max_retries=3, base_delay=0.1)
    def generate_speech(self, text: str, voice_id: str, delivery_note: str, output_path: str) -> float:
        from openai import OpenAI
        logger.info(f"Calling OpenAI TTS for voice {voice_id}")
        client = OpenAI(api_key=self.api_key)
        
        # Maps voice_id to OpenAI voices: alloy, echo, fable, onyx, nova, shimmer
        openai_voice = voice_id if voice_id in ["alloy", "echo", "fable", "onyx", "nova", "shimmer"] else "alloy"
        
        response = client.audio.speech.create(
            model="tts-1",
            voice=openai_voice,
            input=text
        )
        response.stream_to_file(output_path)
        
        # Apply pydub pitch/speed adjustments since OpenAI doesn't support style parameters
        post_process_audio_style(output_path, delivery_note)
        
        return measure_audio_duration(output_path, text)

class MockTTSProvider(TTSProvider):
    def generate_speech(self, text: str, voice_id: str, delivery_note: str, output_path: str) -> float:
        logger.info(f"Generating mock speech WAV for '{text[:20]}...' [Voice: {voice_id}, Tone: {delivery_note}]")
        
        # Estimate duration based on word count
        word_count = len(text.split())
        duration = max(1.5, word_count / 2.1)
        
        # Write dummy wave content
        if sf:
            import numpy as np
            sample_rate = 22050
            num_samples = int(sample_rate * duration)
            t = np.linspace(0, duration, num_samples, endpoint=False)
            freq = 150.0 if voice_id in ["onyx", "echo"] else 250.0
            
            # Simple voice simulation beep
            audio_data = 0.4 * np.sin(2 * np.pi * freq * t)
            sf.write(output_path, audio_data, sample_rate)
        else:
            with open(output_path, "wb") as f:
                f.write(b"MOCK WAV AUDIO DATA")
                
        # Post process adjustments
        post_process_audio_style(output_path, delivery_note)
        
        return measure_audio_duration(output_path, text)

# Helper: Swappable Provider Selector
def get_tts_provider() -> TTSProvider:
    if os.environ.get("ELEVENLABS_API_KEY"):
        return ElevenLabsProvider(os.environ["ELEVENLABS_API_KEY"])
    elif os.environ.get("OPENAI_API_KEY"):
        return OpenAITTSProvider(os.environ["OPENAI_API_KEY"])
    return MockTTSProvider()

# Helper: Measure exact audio duration
def measure_audio_duration(file_path: str, text_fallback: str) -> float:
    """
    Measures the exact audio duration in seconds. Falls back to word-count calculation if soundfile fails.
    """
    if sf:
        try:
            with sf.SoundFile(file_path) as f:
                duration = len(f) / f.samplerate
            return duration
        except Exception as e:
            logger.error(f"Error measuring audio duration: {e}")
            
    # Fallback to word-count
    word_count = len(text_fallback.split())
    return max(1.5, word_count / 2.1)

# Helper: Pydub Speed / Pitch post-processing
def change_speed(audio_segment: AudioSegment, speed: float) -> AudioSegment:
    """
    Changes speed of audio segment while maintaining pitch.
    """
    return audio_segment._spawn(audio_segment.raw_data, overrides={
        "frame_rate": int(audio_segment.frame_rate * speed)
    }).set_frame_rate(audio_segment.frame_rate)

def post_process_audio_style(audio_path: str, delivery_note: str):
    """
    Modifies volume, speed, or tone based on the screenplay's delivery notes.
    """
    if not AudioSegment:
        logger.info("Pydub not installed on host. Skipping audio style post-processing.")
        return
        
    try:
        audio = AudioSegment.from_file(audio_path)
        note = delivery_note.lower()
        modified = False
        
        if "shout" in note or "scream" in note or "loudly" in note:
            logger.info("Applying Pydub post-processing: SHOUT (+6dB, fast speed)")
            # Boost volume, speed up slightly
            audio = audio + 6
            audio = change_speed(audio, 1.08)
            modified = True
        elif "whisper" in note or "softly" in note or "quietly" in note:
            logger.info("Applying Pydub post-processing: WHISPER (-10dB, slow speed)")
            # Duck volume significantly, slow down slightly
            audio = audio - 10
            audio = change_speed(audio, 0.92)
            modified = True
        elif "laugh" in note or "giggle" in note:
            logger.info("Applying Pydub post-processing: LAUGH (+3dB, fast speed)")
            audio = audio + 3
            audio = change_speed(audio, 1.05)
            modified = True
            
        if modified:
            audio.export(audio_path, format="wav")
    except Exception as e:
        logger.error(f"Failed to post-process audio styling: {e}")

# 2. Database Voice Assignment Logics
def initialize_voice_map_table():
    """
    Creates the character voice mapping database table.
    """
    query = """
    CREATE TABLE IF NOT EXISTS core_character_voice_map (
        character_name VARCHAR(100) PRIMARY KEY,
        voice_id VARCHAR(100) NOT NULL
    );
    """
    execute_query(query)

def get_or_assign_voice(character_name: str) -> str:
    """
    Assigns a voice ID to a character once and persists it across all scenes/movies.
    """
    initialize_voice_map_table()
    
    clean_name = character_name.strip().upper()
    row = execute_single("SELECT voice_id FROM core_character_voice_map WHERE character_name = %s", (clean_name,))
    
    if row:
        logger.info(f"Persistent Voice Mapping Found: {clean_name} -> {row['voice_id']}")
        return row['voice_id']
        
    # Assign a new voice (OpenAI voices pool)
    openai_voices = ["onyx", "nova", "alloy", "shimmer", "echo", "fable"]
    h = int(hashlib.sha256(clean_name.encode('utf-8')).hexdigest()[:8], 16)
    assigned_voice = openai_voices[h % len(openai_voices)]
    
    # Store persistent mapping
    execute_query(
        "INSERT INTO core_character_voice_map (character_name, voice_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
        (clean_name, assigned_voice)
    )
    logger.info(f"Persistent Voice Mapping Created: {clean_name} -> {assigned_voice}")
    return assigned_voice

# 3. Batch Scene Dialogue Processing Function
def process_scene_dialogue_batch(
    movie_id: int,
    scene_id: int,
    scene_number: int,
    dialogues_list: List[Dict[str, Any]],
    tts_provider: TTSProvider
) -> List[Dict[str, Any]]:
    """
    Processes a full list of scene dialogue entries. Returns processed dialogue lists with path and duration.
    """
    os.makedirs(f"storage/movies/{movie_id}/dialogue", exist_ok=True)
    processed_dialogues = []
    
    for idx, line_item in enumerate(dialogues_list):
        # Format expected: {character, line, delivery_note}
        character_name = line_item.get('character', 'UNKNOWN').strip()
        text = line_item.get('line', line_item.get('text', ''))
        delivery = line_item.get('delivery_note', '')
        
        # Get persistent voice ID
        voice_id = get_or_assign_voice(character_name)
        
        output_file = f"storage/movies/{movie_id}/dialogue/scene_{scene_number}_line_{idx}.wav"
        
        try:
            # Generate speech and measure exact duration
            duration = tts_provider.generate_speech(
                text=text,
                voice_id=voice_id,
                delivery_note=delivery,
                output_path=output_file
            )
            
            line_data = {
                "character": character_name,
                "text": text,
                "delivery_note": delivery,
                "audio_path": output_file,
                "duration_seconds": duration
            }
            
            # Store in DB Asset table
            meta = {"duration": duration, "character": character_name, "text": text, "delivery": delivery}
            insert_query = """
                INSERT INTO core_asset (movie_id, scene_id, asset_type, file_path, meta_data, created_at)
                VALUES (%s, %s, 'VOICE', %s, %s, NOW())
            """
            execute_query(insert_query, (movie_id, scene_id, output_file, json.dumps(meta)))
            
            processed_dialogues.append(line_data)
        except Exception as e:
            logger.error(f"Failed to generate batch dialogue line for {character_name}: {e}")
            # Fallback
            processed_dialogues.append({
                "character": character_name,
                "text": text,
                "delivery_note": delivery,
                "audio_path": "",
                "duration_seconds": max(1.5, len(text.split()) / 2.1)
            })
            
    return processed_dialogues

# LangGraph Orchestrator Node Entrypoint
def run_voice_generator(state: Any) -> Dict[str, Any]:
    """
    Executes the Voice Generation node.
    """
    movie_id = state.movie_id
    scenes = state.scenes
    
    tts = get_tts_provider()
    audio_assets = []
    
    updated_scenes = []
    for sc in scenes:
        scene_number = sc.get('scene_number')
        scene_row = execute_single("SELECT id FROM core_scene WHERE movie_id = %s AND scene_number = %s", (movie_id, scene_number))
        if not scene_row:
            continue
        scene_id = scene_row['id']
        
        # Dialogue list extraction (handling format keys)
        dialogues = sc.get('dialogue', [])
        
        # Process scene dialogues
        processed = process_scene_dialogue_batch(movie_id, scene_id, scene_number, dialogues, tts)
        sc['dialogue'] = processed
        
        for idx, line in enumerate(processed):
            audio_assets.append({
                "scene_number": scene_number,
                "line_index": idx,
                "character": line['character'],
                "file_path": line['audio_path'],
                "duration": line['duration_seconds']
            })
            
        updated_scenes.append(sc)
        
    return {
        "scenes": updated_scenes,
        "audio_assets": state.audio_assets + audio_assets
    }
