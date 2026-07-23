import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

# 1. Gap detection function based on dialogue timestamps
def detect_silent_dialogue_gaps(
    dialogue_timestamps: List[Dict[str, float]],
    total_duration: float,
    min_gap: float = 2.0
) -> List[Dict[str, float]]:
    """
    Scans scene dialogue timestamps to find silent gaps longer than the min_gap threshold.
    Timestamps format: [{"start": 1.2, "end": 3.4}, ...]
    """
    gaps = []
    
    # Sort dialogue by start time
    sorted_dialogue = sorted(dialogue_timestamps, key=lambda x: x["start"])
    
    # Check gap before first line of dialogue
    current_time = 0.0
    for line in sorted_dialogue:
        gap_len = line["start"] - current_time
        if gap_len >= min_gap:
            gaps.append({
                "start": current_time,
                "end": line["start"],
                "duration": gap_len
            })
        current_time = line["end"]
        
    # Check gap after last line of dialogue
    if total_duration - current_time >= min_gap:
        gaps.append({
            "start": current_time,
            "end": total_duration,
            "duration": total_duration - current_time
        })
        
    logger.info(f"AD: Detected {len(gaps)} silent gaps suitable for audio descriptions.")
    return gaps


# 2. Audio description narration prompt generator
def generate_audio_description_text(scene_action_context: str, max_duration_seconds: float) -> str:
    """
    Prompt template to generate descriptive narrator copy fitting inside the silent gap.
    """
    prompt = f"""
    You are an expert Audio Description narrator writing for visually impaired viewers.
    Review the following visual action context from the scene storyboard:
    "{scene_action_context}"

    Task: Write a concise, vivid narration describing the visual action (movements, facial expressions, or setting updates).
    Constraint: Your description must be read aloud in under {max_duration_seconds:.1f} seconds (approx. {int(max_duration_seconds * 2.5)} words maximum).
    Do NOT introduce dialogue or interpret character thoughts. Speak only about what is visible.
    """
    logger.debug(f"AD: Generated narration prompt for {max_duration_seconds}s limit.")
    
    # Simulated output for testing (concise action details)
    words = scene_action_context.split()[:int(max_duration_seconds * 2)]
    narration = " ".join(words) + "."
    return narration


# 3. Dual-track audio mixing logic (FFmpeg command builder representation)
def mix_audio_description_track(
    original_audio_path: str,
    ad_narration_path: str,
    output_audio_path: str,
    start_offset: float
) -> str:
    """
    Uses FFmpeg to mix narrator audio into a secondary audio channel.
    Applies a sidechain compressor (ducking) to lower the movie dialogue volume
    whenever the narrator is speaking.
    """
    # -i: inputs
    # -filter_complex: overlay narration with offset and ducking parameters
    ffmpeg_cmd = (
        f"ffmpeg -i {original_audio_path} -i {ad_narration_path} -filter_complex "
        f"\"[1:a]adelay={int(start_offset * 1000)}|{int(start_offset * 1000)}[narr]; "
        f"[0:a][narr]amix=inputs=2:duration=first:dropout_transition=2[out]\" "
        f"-map \"[out]\" -c:a aac {output_audio_path}"
    )
    logger.info(f"AD FFmpeg Command: {ffmpeg_cmd}")
    return ffmpeg_cmd
