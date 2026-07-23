import os
import logging
from typing import List, Dict, Any
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

# 1. Comic Book Export Panel Layout (PDF Compiler)
def generate_comic_book_panels(
    storyboard_images: List[str],
    screenplay_lines: List[Dict[str, str]], # [{"character": "Alex", "dialogue": "Let's go!"}, ...]
    output_pdf_path: str
) -> str:
    """
    Takes storyboard shots and compiles them into a grid layout page.
    Draws text speech bubbles near characters positions. Saves as a PDF file.
    """
    logger.info(f"Comic: Compiling panels into PDF: {output_pdf_path}")
    
    # Create empty portrait canvas representing page (800x1200)
    page = Image.new("RGB", (800, 1200), "#FFFFFF")
    draw = ImageDraw.Draw(page)
    
    # 4 grid panel boundaries: [x1, y1, x2, y2]
    panels = [
        [40, 40, 380, 560],   # Panel 1 (Top Left)
        [420, 40, 760, 560],  # Panel 2 (Top Right)
        [40, 600, 380, 1120],  # Panel 3 (Bottom Left)
        [420, 600, 760, 1120]  # Panel 4 (Bottom Right)
    ]
    
    for i, bounds in enumerate(panels):
        # Draw frame boundary border
        draw.rectangle(bounds, outline="#000000", width=4)
        
        # Overlay storyboard image if available
        if i < len(storyboard_images) and os.path.exists(storyboard_images[i]):
            try:
                panel_img = Image.open(storyboard_images[i])
                panel_w = bounds[2] - bounds[0]
                panel_h = bounds[3] - bounds[1]
                panel_img = panel_img.resize((panel_w, panel_h))
                page.paste(panel_img, (bounds[0], bounds[1]))
            except Exception as e:
                logger.error(f"Comic: Panel overlay failed: {e}")
                
        # Draw speech bubble overlay if dialogue exists for this panel
        if i < len(screenplay_lines):
            line = screenplay_lines[i]
            char = line.get("character", "Narrator")
            dialogue = line.get("dialogue", "...")
            
            # Bubble position: top center of the panel
            bx = bounds[0] + 30
            by = bounds[1] + 30
            bw = bounds[2] - bounds[0] - 60
            bh = 80
            
            # White speech bubble rectangle
            draw.rectangle([bx, by, bx + bw, by + bh], fill="#FFFFFF", outline="#000000", width=2)
            # Text inside bubble
            draw.text((bx + 10, by + 10), f"{char}:", fill="#D4AF37") # gold character name tag
            draw.text((bx + 10, by + 35), dialogue[:40], fill="#000000") # black text
            
    page.save(output_pdf_path, "PDF")
    logger.info(f"Comic: Successfully rendered PDF comic page at {output_pdf_path}")
    return output_pdf_path


# 2. Audio-only Podcast/Audio-Drama mixdown function
def mix_audio_drama_track(
    dialogue_tracks: List[str],
    bg_music_track: str,
    sfx_tracks: List[str],
    output_audio_path: str
) -> str:
    """
    Mixes voice synthesizer, music and Foley sound effects together into a stereo track.
    Builds FFmpeg command string to combine files.
    """
    logger.info("Audio Drama: Mixing soundtrack tracks without video rendering")
    
    # Build inputs arguments list
    inputs = []
    filter_inputs = []
    
    idx = 0
    for v in dialogue_tracks:
        if os.path.exists(v):
            inputs.append(f"-i {v}")
            filter_inputs.append(f"[{idx}:a]")
            idx += 1
            
    if os.path.exists(bg_music_track):
        inputs.append(f"-i {bg_music_track}")
        filter_inputs.append(f"[{idx}:a]")
        idx += 1
        
    for s in sfx_tracks:
        if os.path.exists(s):
            inputs.append(f"-i {s}")
            filter_inputs.append(f"[{idx}:a]")
            idx += 1
            
    inputs_str = " ".join(inputs)
    amix_filters = "".join(filter_inputs)
    
    # amix filter compiles stereo outputs
    ffmpeg_cmd = f"ffmpeg {inputs_str} -filter_complex \"{amix_filters}amix=inputs={idx}:duration=longest[out]\" -map \"[out]\" -c:a aac {output_audio_path}"
    logger.info(f"Audio Drama Mixdown Command: {ffmpeg_cmd}")
    
    return ffmpeg_cmd
