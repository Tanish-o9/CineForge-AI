import os
import json
import logging
import uuid
from typing import Dict, Any, List, Tuple
from PIL import Image

# Optional MoviePy import
try:
    from moviepy.editor import ImageClip, CompositeVideoClip
    moviepy_installed = True
except ImportError:
    ImageClip = None
    CompositeVideoClip = None
    moviepy_installed = False

# Database helpers
from fastapi_service.database import execute_query, execute_single

logger = logging.getLogger(__name__)

# Constants for HD composition
TARGET_WIDTH = 1920
TARGET_HEIGHT = 1080
OVERSIZED_WIDTH = 2304  # 1.2 * 1920 (for panning crop sliding)

# 1. Camera Movement to Transform Mapping Table & Function
def animate_shot(image_path: str, camera_movement: str, duration_seconds: float, clip_path: str = None) -> str:
    """
    Applies Ken Burns zoom and slide pan effects to a still image.
    Outputs a finished video file path.
    """
    if not clip_path:
        out_dir = os.path.dirname(image_path) if image_path else "storage"
        base_name = os.path.basename(image_path).replace(".png", "_animated.mp4") if image_path else f"animated_{uuid.uuid4().hex}.mp4"
        clip_path = os.path.join(out_dir, base_name)

    # Ensure output folder exists
    os.makedirs(os.path.dirname(clip_path), exist_ok=True)
    
    # Ensure image_path exists, or create a temporary solid color fallback image
    temp_img_created = False
    if not image_path or not os.path.exists(image_path):
        logger.warning(f"Input image path missing or invalid: {image_path}. Creating solid black fallback image.")
        fallback_dir = "storage/temp_fallback"
        os.makedirs(fallback_dir, exist_ok=True)
        image_path = os.path.join(fallback_dir, f"temp_fallback_{uuid.uuid4().hex}.png")
        img = Image.new("RGB", (TARGET_WIDTH, TARGET_HEIGHT), "#1A1A1A")
        img.save(image_path)
        temp_img_created = True

    if not moviepy_installed:
        logger.warning("MoviePy not installed on host. Emitting mock animated clip file.")
        with open(clip_path, "wb") as f:
            f.write(b"MOCK ANIMATED CLIP MP4")
        if temp_img_created and os.path.exists(image_path):
            os.remove(image_path)
        return clip_path

    logger.info(f"Animating: {os.path.basename(clip_path)} | Movement: {camera_movement} | Duration: {duration_seconds}s")
    movement = camera_movement.upper()

    try:
        # Base setup: target resolution is 1920x1080
        base_clip = ImageClip(image_path).set_duration(duration_seconds)
        
        # Mapping transformations
        if "ZOOM-IN" in movement:
            clip = base_clip.resize(lambda t: 1.0 + 0.15 * (t / duration_seconds))
            clip = clip.set_position(('center', 'center'))
        elif "ZOOM-OUT" in movement:
            clip = base_clip.resize(lambda t: 1.15 - 0.15 * (t / duration_seconds))
            clip = clip.set_position(('center', 'center'))
        elif "PAN-LEFT" in movement:
            clip = base_clip.resize(height=TARGET_HEIGHT)
            slide_limit = clip.size[0] - TARGET_WIDTH
            clip = clip.set_position(lambda t: (-int(slide_limit * (t / duration_seconds)), 'center'))
        elif "PAN-RIGHT" in movement:
            clip = base_clip.resize(height=TARGET_HEIGHT)
            slide_limit = clip.size[0] - TARGET_WIDTH
            clip = clip.set_position(lambda t: (-int(slide_limit * (1.0 - t / duration_seconds)), 'center'))
        else:
            clip = base_clip.resize(newsize=(TARGET_WIDTH, TARGET_HEIGHT))
            clip = clip.set_position(('center', 'center'))

        final_comp = CompositeVideoClip([clip], size=(TARGET_WIDTH, TARGET_HEIGHT)).set_duration(duration_seconds)
        final_comp.write_videofile(
            clip_path,
            fps=24,
            codec="libx264",
            audio=False,
            preset="ultrafast",
            logger=None
        )
        final_comp.close()
        clip.close()
        
    except Exception as e:
        logger.error(f"Failed Ken Burns transform: {e}. Outputting static fallback clip.")
        try:
            fallback = ImageClip(image_path).set_duration(duration_seconds).resize(newsize=(TARGET_WIDTH, TARGET_HEIGHT))
            fallback.write_videofile(clip_path, fps=24, codec="libx264", audio=False, preset="ultrafast", logger=None)
            fallback.close()
        except Exception as fe:
            logger.error(f"Double-fault static transform fallback: {fe}")
            with open(clip_path, "wb") as f:
                f.write(b"MOCK ANIMATED CLIP MP4")
        
    if temp_img_created and os.path.exists(image_path):
        os.remove(image_path)
        
    return clip_path

# Parallax compositing helper (stretch feature)
def animate_parallax_shot(
    bg_path: str,
    fg_path: str,
    camera_movement: str,
    duration_seconds: float,
    clip_path: str
) -> str:
    """
    Composites foreground character layers over background scenes with subtle parallax offsets.
    """
    if not fg_path or not os.path.exists(fg_path):
        # Fall back to single flat shot animation
        return animate_shot(bg_path, camera_movement, duration_seconds, clip_path)

    if not moviepy_installed:
        with open(clip_path, "wb") as f:
            f.write(b"MOCK PARALLAX MP4")
        return clip_path

    logger.info(f"Animating Parallax: {os.path.basename(clip_path)} | Movement: {camera_movement}")
    movement = camera_movement.upper()
    
    try:
        bg_base = ImageClip(bg_path).set_duration(duration_seconds)
        fg_base = ImageClip(fg_path).set_duration(duration_seconds)
        
        if "PAN-LEFT" in movement:
            bg_clip = bg_base.resize(height=TARGET_HEIGHT + 100)
            bg_clip = bg_clip.set_position(lambda t: (-int(200 * (t / duration_seconds)), 'center'))
            
            fg_clip = fg_base.resize(height=900)
            fg_clip = fg_clip.set_position(lambda t: (int(300 - 80 * (t / duration_seconds)), 'bottom'))
        elif "ZOOM-IN" in movement:
            bg_clip = bg_base.resize(lambda t: 1.0 + 0.15 * (t / duration_seconds)).set_position(('center', 'center'))
            fg_clip = fg_base.resize(lambda t: 1.0 + 0.06 * (t / duration_seconds)).set_position(('center', 'bottom'))
        else:
            bg_clip = bg_base.resize(newsize=(TARGET_WIDTH, TARGET_HEIGHT)).set_position(('center', 'center'))
            fg_clip = fg_base.resize(height=850).set_position(('center', 'bottom'))
            
        comp = CompositeVideoClip([bg_clip, fg_clip], size=(TARGET_WIDTH, TARGET_HEIGHT)).set_duration(duration_seconds)
        comp.write_videofile(clip_path, fps=24, codec="libx264", audio=False, preset="ultrafast", logger=None)
        comp.close()
        
    except Exception as e:
        logger.error(f"Parallax render failed: {e}. Falling back to flat shot animation.")
        animate_shot(bg_path, camera_movement, duration_seconds, clip_path)
        
    return clip_path

# 2. Syncing Loop processing every shot in a scene
def run_animation_agent(state: Any) -> Dict[str, Any]:
    """
    Pulls shot visuals, looks up measured dialogue durations, and executes animate_shot.
    """
    movie_id = state.movie_id
    scenes = state.scenes
    
    os.makedirs(f"storage/movies/{movie_id}/clips", exist_ok=True)
    video_clips = []
    
    for sc in scenes:
        scene_number = sc.get('scene_number')
        scene_row = execute_single("SELECT id FROM core_scene WHERE movie_id = %s AND scene_number = %s", (movie_id, scene_number))
        if not scene_row:
            continue
        scene_id = scene_row['id']
        
        # 1. Fetch visual image assets
        image_assets = execute_query(
            "SELECT id, file_path, meta_data FROM core_asset WHERE movie_id = %s AND scene_id = %s AND asset_type = 'IMAGE'",
            (movie_id, scene_id), fetch=True
        )
        
        # Sort by shot number
        shots = []
        for asset in image_assets:
            meta = asset['meta_data']
            if isinstance(meta, str):
                meta = json.loads(meta)
            shot_num = meta.get('shot_number', 1)
            shots.append((shot_num, asset['file_path'], meta))
        shots.sort(key=lambda x: x[0])
        
        # 2. Fetch measured voice dialogue assets
        voice_assets = execute_query(
            "SELECT id, file_path, meta_data FROM core_asset WHERE movie_id = %s AND scene_id = %s AND asset_type = 'VOICE' ORDER BY id",
            (movie_id, scene_id), fetch=True
        )
        
        scene_clips = []
        for idx, (shot_num, img_path, meta) in enumerate(shots):
            movement = meta.get('camera_movement', 'STATIC')
            
            # Default duration from storyboard
            dur = float(meta.get('duration_seconds', 5.0))
            
            # Sync to measured voice track duration if present
            if idx < len(voice_assets):
                v_meta = voice_assets[idx]['meta_data']
                if isinstance(v_meta, str):
                    v_meta = json.loads(v_meta)
                measured_dur = float(v_meta.get('duration', dur))
                logger.info(f"Syncing Scene {scene_number} Shot {shot_num} duration to voice track: {measured_dur}s (original est: {dur}s)")
                dur = measured_dur
                
            output_clip = f"storage/movies/{movie_id}/clips/scene_{scene_number}_shot_{shot_num}.mp4"
            
            # Parallax stretch check
            bg_layer = img_path
            fg_layer = meta.get('character_overlay_path', '')
            
            if fg_layer and os.path.exists(fg_layer):
                animate_parallax_shot(bg_layer, fg_layer, movement, dur, output_clip)
            else:
                animate_shot(bg_layer, movement, dur, output_clip)
                
            # Store in DB Asset table
            insert_meta = {"shot_number": shot_num, "duration": dur, "movement": movement}
            insert_query = """
                INSERT INTO core_asset (movie_id, scene_id, asset_type, file_path, meta_data, created_at)
                VALUES (%s, %s, 'VIDEO', %s, %s, NOW())
            """
            execute_query(insert_query, (movie_id, scene_id, output_clip, json.dumps(insert_meta)))
            
            scene_clips.append({
                "shot_number": shot_num,
                "file_path": output_clip,
                "duration": dur
            })
            
        video_clips.append({
            "scene_number": scene_number,
            "clips": scene_clips
        })
        
    return {"video_clips": state.video_clips + video_clips}
