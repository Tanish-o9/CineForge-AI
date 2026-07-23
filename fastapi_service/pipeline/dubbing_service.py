import logging
from typing import Dict, Any, Optional

# Database helpers
from fastapi_service.database import execute_query, execute_single

logger = logging.getLogger(__name__)

# 1. Dubbing Voice mapping table schema
def initialize_dubbing_tables():
    try:
        execute_query("""
            CREATE TABLE IF NOT EXISTS core_dubbing_voice (
                id SERIAL PRIMARY KEY,
                character_name VARCHAR(100) NOT NULL,
                language_code VARCHAR(10) NOT NULL, -- es, fr, de, jp
                voice_id VARCHAR(100) NOT NULL,
                UNIQUE(character_name, language_code)
            );
        """)
    except Exception as e:
        logger.error(f"Failed to initialize dubbing registries: {e}")


# 2. Dialogue Translation Chain
def generate_translation_prompt(
    original_line: str,
    target_lang: str,
    delivery_note: str = ""
) -> str:
    """
    Formulates prompt templates directing translation LLMs to preserve timing/acting intents.
    """
    prompt = f"""
    Translate the following movie screenplay dialogue line into '{target_lang}'.
    Original: "{original_line}"
    Delivery Tone/Acting Note: "{delivery_note}"

    Task Constraints:
    - Retain the exact emotional cadence and subtext.
    - Keep the translated sentence length (syllables) as close to the original as possible to preserve timing and lip-sync slots.
    Return ONLY the final translated text, no quotes or notes.
    """
    logger.debug(f"Dubbing: Formulated translation prompt for {target_lang}")
    return prompt


# 3. Audio Time-Stretch Fitting Function
def fit_audio_to_duration(
    pydub_segment: Any,
    target_duration_ms: int
) -> Any:
    """
    Speeds up or slows down a pydub AudioSegment to fit a exact target duration.
    Calculates stretching ratios and overrides playback frame rates.
    """
    current_duration_ms = len(pydub_segment)
    if current_duration_ms == 0 or target_duration_ms == 0:
        return pydub_segment
        
    speed_ratio = float(current_duration_ms) / float(target_duration_ms)
    
    # Clip extreme stretching bounds to preserve vocal pitch intelligibility
    speed_ratio = max(0.75, min(speed_ratio, 1.35))
    
    # Using pydub's speedup or modifying frame rate
    # For a high-fidelity time stretch, pydub has: pydub_segment.speedup(playback_speed=speed_ratio)
    try:
        # Check if speedup function is applicable (requires scipy)
        # Fallback modifies frame rate
        new_frame_rate = int(pydub_segment.frame_rate * speed_ratio)
        stretched_segment = pydub_segment._spawn(pydub_segment.raw_data, overrides={
            "frame_rate": new_frame_rate
        })
        # Set back to standard frame rate to enforce speed adjustment
        stretched_segment = stretched_segment.set_frame_rate(pydub_segment.frame_rate)
        
        logger.info(f"Dubbing Stretch: Adjusted audio segment speed by ratio {speed_ratio:.3f}x to fit {target_duration_ms}ms")
        return stretched_segment
    except Exception as e:
        logger.warning(f"Audio time-stretch failed: {e}. Returning original.")
        return pydub_segment
