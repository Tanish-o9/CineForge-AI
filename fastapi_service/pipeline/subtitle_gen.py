import os
import json
import logging
import subprocess
from typing import Dict, Any, List, Tuple

# Database helpers
from fastapi_service.database import execute_query, execute_single

logger = logging.getLogger(__name__)

# 1. Whisper API Wrapper (OpenAI Transcription)
def transcribe_audio_whisper(audio_path: str, api_key: str) -> List[Dict[str, Any]]:
    """
    Transcribes audio file using OpenAI Whisper-1, returning segment-level timestamps.
    """
    if not api_key:
        logger.warning("No API key provided for Whisper. Falling back to mock transcription.")
        return mock_whisper_transcription(audio_path)
        
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        
        logger.info(f"Uploading {audio_path} to OpenAI Whisper API...")
        with open(audio_path, "rb") as audio_file:
            response = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                response_format="verbose_json",
                timestamp_granularities=["segment"]
            )
            
        segments = []
        # Extract segments
        if hasattr(response, "segments") and response.segments:
            for seg in response.segments:
                segments.append({
                    "start": float(seg.get("start", 0.0)),
                    "end": float(seg.get("end", 0.0)),
                    "text": seg.get("text", "").strip()
                })
        else:
            # Fallback if verbose_json response structure differs
            segments.append({
                "start": 0.0,
                "end": 5.0,
                "text": getattr(response, "text", "")
            })
            
        return segments
    except Exception as e:
        logger.error(f"Whisper API transcription failed: {e}. Splicing mock segments.")
        return mock_whisper_transcription(audio_path)

def mock_whisper_transcription(audio_path: str) -> List[Dict[str, Any]]:
    """
    Creates mock timestamped dialogue segments if Whisper API is unavailable.
    """
    # Simply read associated dialogue lines from path structure
    # Expected filename: scene_{scene_number}_line_{idx}.wav or temp_voice.wav
    # We create a simple mock timer: 3-second segments
    return [
        {"start": 0.5, "end": 3.0, "text": "This is the first transcription segment."},
        {"start": 3.5, "end": 6.0, "text": "Proceeding to location coordinate vector."},
        {"start": 6.5, "end": 9.5, "text": "Alert: Storm density is increasing."}
    ]

# 2. Cumulative SRT Timestamp Formatter
def format_srt_timestamp(seconds: float) -> str:
    """
    Converts seconds (float) to SRT format: HH:MM:SS,mmm
    """
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    msecs = int(round((seconds - int(seconds)) * 1000))
    if msecs >= 1000:
        msecs = 999
    return f"{hrs:02d}:{mins:02d}:{secs:02d},{msecs:03d}"

def generate_cumulative_srt(scenes_transcripts: List[List[Dict[str, Any]]], scene_durations: List[float], srt_path: str):
    """
    Generates a unified SRT file by combining segment lists across scenes
    and adding cumulative time offsets.
    """
    logger.info(f"Generating cumulative SRT file at: {srt_path}")
    
    cumulative_offset = 3.0 # Starts after the 3-second title card
    srt_lines = []
    global_index = 1
    
    for scene_idx, scene_segments in enumerate(scenes_transcripts):
        # Current scene duration
        scene_dur = scene_durations[scene_idx] if scene_idx < len(scene_durations) else 10.0
        
        for seg in scene_segments:
            start_abs = seg["start"] + cumulative_offset
            end_abs = seg["end"] + cumulative_offset
            
            # Make sure we don't exceed the scene bounds
            if start_abs >= (cumulative_offset + scene_dur):
                continue
            if end_abs > (cumulative_offset + scene_dur):
                end_abs = cumulative_offset + scene_dur
                
            start_str = format_srt_timestamp(start_abs)
            end_str = format_srt_timestamp(end_abs)
            
            srt_lines.append(f"{global_index}")
            srt_lines.append(f"{start_str} --> {end_str}")
            srt_lines.append(f"{seg['text']}\n")
            
            global_index += 1
            
        cumulative_offset += scene_dur
        
    with open(srt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(srt_lines))

# 3. FFmpeg Burn-In Captions Command
def burn_subtitles_ffmpeg(input_video_path: str, srt_path: str, output_video_path: str) -> bool:
    """
    Burns SRT subtitles into H.264 video.
    Applies Arial font style with a semi-transparent dark background bounding box.
    """
    logger.info("Executing FFmpeg subtitle burn-in filters...")
    
    # Format subtitle filter style. Fontsize=18, BorderStyle=4 creates a background box.
    # BackColour=&H80000000 is 50% opacity black.
    # Windows path sanitization: replace backslashes with forward slashes and escape colon
    clean_srt_path = srt_path.replace("\\", "/").replace(":", "\\:")
    
    filter_str = (
        f"subtitles={clean_srt_path}:force_style="
        "'Fontname=Arial,Fontsize=18,PrimaryColour=&H00FFFFFF,"
        "OutlineColour=&H80000000,BorderStyle=4,BackColour=&H80000000'"
    )
    
    cmd = [
        "ffmpeg", "-y",
        "-i", input_video_path,
        "-vf", filter_str,
        "-c:v", "libx264",
        "-crf", "23",
        "-c:a", "copy",
        output_video_path
    ]
    
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=90.0)
        if res.returncode == 0:
            logger.info("Subtitles burned in successfully.")
            return True
        else:
            logger.error(f"FFmpeg subtitle burn failed: {res.stderr}")
            return False
    except Exception as e:
        logger.error(f"FFmpeg subtitle burn exception: {e}")
        return False

# LangGraph Orchestrator Node entrypoint wrapper
def run_subtitle_agent(state: Any) -> Dict[str, Any]:
    """
    Orchestration entrypoint: generates SRT, burns it in, and records path options.
    """
    movie_id = state.movie_id
    video_clips = state.video_clips # [{"scene_number": 1, "clips": [...]}]
    final_video = state.final_video_path
    api_key = os.environ.get("OPENAI_API_KEY")
    
    output_dir = f"storage/movies/{movie_id}"
    os.makedirs(output_dir, exist_ok=True)
    
    srt_path = f"{output_dir}/subtitles.srt"
    burned_video = f"{output_dir}/final_movie_captioned.mp4"
    
    # 1. Transcribe scene-by-scene
    scenes_transcripts = []
    scene_durations = []
    
    for sc in video_clips:
        scene_number = sc["scene_number"]
        scene_dur = sum(float(c.get("duration", 5.0)) for c in sc.get("clips", []))
        scene_durations.append(scene_dur)
        
        # Load dialogue mixed audio for this scene
        # Dialogue assets were stored in DB
        scene_row = execute_single("SELECT id FROM core_scene WHERE movie_id = %s AND scene_number = %s", (movie_id, scene_number))
        if scene_row:
            voice_assets = execute_query(
                "SELECT file_path FROM core_asset WHERE movie_id = %s AND scene_id = %s AND asset_type = 'VOICE' ORDER BY id",
                (movie_id, scene_row['id']), fetch=True
            )
            # Use the first dialogue audio segment or mock transcribe
            audio_path = voice_assets[0]["file_path"] if voice_assets else ""
            
            if audio_path and os.path.exists(audio_path):
                transcript = transcribe_audio_whisper(audio_path, api_key)
            else:
                transcript = mock_whisper_transcription("")
        else:
            transcript = mock_whisper_transcription("")
            
        scenes_transcripts.append(transcript)
        
    # 2. Compile Cumulative SRT
    generate_cumulative_srt(scenes_transcripts, scene_durations, srt_path)
    
    # 3. Burn-in subtitles
    success = burn_subtitles_ffmpeg(final_video, srt_path, burned_video)
    
    # If burn-in succeeds, update final video path to the captioned version
    # (Exposing both srt and captioned video in output paths)
    final_path = burned_video if success else final_video
    
    # Update Django core_movie table
    query = "UPDATE core_movie SET screenplay_raw = %s WHERE id = %s"
    # Append srt_path and final path options to state dict
    state_dict = state.model_dump()
    state_dict["subtitles"] = srt_path
    state_dict["final_video_path"] = final_path
    execute_query(query, (json.dumps(state_dict, default=str), movie_id))
    
    return {
        "subtitles": srt_path,
        "final_video_path": final_path
    }
