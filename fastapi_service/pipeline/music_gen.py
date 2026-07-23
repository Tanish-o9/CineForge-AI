import os
import json
import logging
import numpy as np
from abc import ABC, abstractmethod
try:
    import soundfile as sf
except ImportError:
    sf = None
try:
    from pydub import AudioSegment
except ImportError:
    AudioSegment = None
from typing import Dict, Any, List

# Database helpers
from fastapi_service.database import execute_query, execute_single

logger = logging.getLogger(__name__)

# Mood mapping dictionary
MOOD_MAP = {
    "isolated": "isolated_ambient_hum",
    "awe-inspiring": "grand_orchestral_pad",
    "claustrophobic": "tense_metallic_drone",
    "tense": "fast_pulsing_synth",
    "struggle": "heavy_percussion_beat",
    "desperation": "frantic_violin_tremolo",
    "emotional": "soft_piano_melody",
    "hopeful": "uplifting_acoustic_chords",
    "mysterious": "ethereal_synthesizer_bells",
    "somber": "slow_cello_pad",
    "triumphant": "bright_horn_fanfare"
}

def map_beat_to_mood(emotional_beat: str) -> str:
    """
    Maps scene's emotional beat text to a defined musical mood tag.
    """
    beat_lower = emotional_beat.lower()
    for key, mood in MOOD_MAP.items():
        if key in beat_lower:
            return mood
    return "atmospheric_ambient"

# Music Provider Interface
class MusicProvider(ABC):
    @abstractmethod
    def generate_music_track(self, mood: str, duration_seconds: float, output_path: str) -> str:
        """
        Generates or selects background music. Returns path to the generated file.
        """
        pass

class MockMusicProvider(MusicProvider):
    def generate_music_track(self, mood: str, duration_seconds: float, output_path: str) -> str:
        """
        Synthesizes a unique ambient audio track matching the mood using numpy and writes it to file.
        """
        logger.info(f"Synthesizing ambient track for mood '{mood}' (Duration: {duration_seconds}s)")
        sample_rate = 22050
        t = np.linspace(0, duration_seconds, int(sample_rate * duration_seconds), endpoint=False)
        
        # Synthesize sound waves based on mood
        if "hum" in mood or "drone" in mood or "isolated" in mood:
            # Low, resonant hums
            wave = 0.4 * np.sin(2 * np.pi * 80.0 * t) + 0.2 * np.sin(2 * np.pi * 120.0 * t)
        elif "synth" in mood or "pulse" in mood or "tense" in mood:
            # Tense pulsing alarm waves
            pulse = np.sin(2 * np.pi * 2.0 * t) # 2 Hz modulation
            wave = 0.3 * np.sin(2 * np.pi * 220.0 * t) * (0.5 + 0.5 * pulse)
        elif "piano" in mood or "melody" in mood or "hopeful" in mood:
            # Soothing slow arpeggios
            # Frequencies representing A-minor/C-major arpeggio notes
            notes = [220.0, 261.63, 329.63, 392.00]
            wave = np.zeros_like(t)
            # Cycle through notes every 2 seconds
            for i, note in enumerate(notes):
                # note volume envelopes
                env = np.maximum(0, np.sin(2 * np.pi * (1.0 / 8.0) * t - (i * np.pi / 2)))
                wave += 0.2 * np.sin(2 * np.pi * note * t) * env
        elif "heavy" in mood or "beat" in mood or "struggle" in mood:
            # Rhythmic pounding beat
            rhythm = np.abs(np.sin(2 * np.pi * 1.5 * t))**10
            wave = 0.5 * np.sin(2 * np.pi * 60.0 * t) * rhythm
        else:
            # General low string pads
            wave = 0.3 * np.sin(2 * np.pi * 110.0 * t) + 0.1 * np.sin(2 * np.pi * 165.0 * t)

        # Convert to 16-bit PCM WAV
        audio_ints = np.int16(wave * 32767)
        
        if sf:
            sf.write(output_path, audio_ints, sample_rate)
        else:
            with open(output_path, "wb") as f:
                f.write(b"MOCK MUSIC WAV")
        return output_path

# Swappable Selector
def get_music_provider() -> MusicProvider:
    # Placements for Suno / Udio / AudioCraft / Replicate APIs can go here
    return MockMusicProvider()

# Pydub post-processing utility
def match_track_to_duration(input_path: str, target_duration_seconds: float, output_path: str):
    """
    Loops, trims, and fades an audio file to match the target scene duration.
    """
    if not AudioSegment:
        logger.info("Pydub not installed on host. Falling back to copy operation.")
        if os.path.exists(input_path):
            with open(input_path, "rb") as fin:
                data = fin.read()
            with open(output_path, "wb") as fout:
                fout.write(data)
        else:
            with open(output_path, "wb") as fout:
                fout.write(b"MOCK MUSIC WAV DATA")
        return

    audio = AudioSegment.from_file(input_path)
    target_ms = int(target_duration_seconds * 1000)
    
    if len(audio) < target_ms:
        # Loop to fill duration
        loops_needed = (target_ms // len(audio)) + 1
        processed = audio * loops_needed
    else:
        processed = audio

    # Trim to exact length
    processed = processed[:target_ms]
    
    # Apply fade out (2 seconds or 10% of track length)
    fade_out_time = min(2000, int(target_ms * 0.1))
    processed = processed.fade_out(fade_out_time)
    
    # Save processed track
    processed.export(output_path, format="wav")

# Core LangGraph entrypoint
def run_music_generator(state: Any) -> Dict[str, Any]:
    """
    Executes the Music Composer Agent.
    Generates music files mapped to scenes, loops/trims them to match durations.
    """
    movie_id = state.movie_id
    scenes = state.scenes
    
    provider = get_music_provider()
    os.makedirs(f"storage/movies/{movie_id}/music", exist_ok=True)
    
    logger.info(f"Generating background music tracks for movie {movie_id}")
    audio_assets = []
    
    for sc in scenes:
        scene_number = sc.get('scene_number')
        scene_row = execute_single("SELECT id FROM core_scene WHERE movie_id = %s AND scene_number = %s", (movie_id, scene_number))
        if not scene_row:
            continue
        scene_id = scene_row['id']
        
        emotional_beat = sc.get('emotional_beat', 'neutral')
        duration = sc.get('estimated_duration', 20)
        
        mood = map_beat_to_mood(emotional_beat)
        
        raw_music_path = f"storage/movies/{movie_id}/music/scene_{scene_number}_raw.wav"
        final_music_path = f"storage/movies/{movie_id}/music/scene_{scene_number}_bg.wav"
        
        # 1. Generate base mood track
        provider.generate_music_track(mood, duration + 4.0, raw_music_path) # Generate slightly extra for safety
        
        # 2. Trim/Loop/Fade using pydub
        match_track_to_duration(raw_music_path, duration, final_music_path)
        
        # Cleanup raw temp file
        if os.path.exists(raw_music_path):
            os.remove(raw_music_path)
            
        # 3. Save as Asset in DB
        meta = {"mood": mood, "duration": duration, "beat": emotional_beat}
        insert_query = """
            INSERT INTO core_asset (movie_id, scene_id, asset_type, file_path, meta_data, created_at)
            VALUES (%s, %s, 'MUSIC', %s, %s, NOW())
        """
        execute_query(insert_query, (movie_id, scene_id, final_music_path, json.dumps(meta)))
        
        audio_assets.append({
            "scene_number": scene_number,
            "asset_type": "MUSIC",
            "file_path": final_music_path,
            "duration": duration
        })
        
    return {"audio_assets": state.audio_assets + audio_assets}
