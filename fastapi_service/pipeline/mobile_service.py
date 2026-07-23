import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

# 1. Simplified Prompt "Vibe" mapper templates
VIBE_TEMPLATES = {
    "funny": "with slapstick comedy elements, vibrant colors, warm lighting, humorous character expressions",
    "epic": "cinematic wide angles, dark atmospheric clouds, golden key light, dramatic orchestral tone, epic camera movements",
    "emotional": "close up shots, soft volumetric lighting, melancholy mood, slow panning cameras",
    "oddly-satisfying": "slow-motion loop, macro lens details, smooth fluid simulations, ambient synth sounds, glowing colors"
}

def map_mobile_prompt_to_schema(user_prompt: str, vibe: str) -> Dict[str, Any]:
    """
    Appends visual instructions based on the selected "vibe" override,
    and locks pipeline to portrait configurations.
    """
    vibe_context = VIBE_TEMPLATES.get(vibe.lower(), VIBE_TEMPLATES["epic"])
    compiled_prompt = f"{user_prompt}, {vibe_context}"
    
    logger.info(f"Mobile Mapping: Prompt compiled with vibe '{vibe}': {compiled_prompt[:60]}...")
    return {
        "user_prompt": compiled_prompt,
        "width": 1080,
        "height": 1920,
        "aspect_ratio": "9:16",
        "mobile_optimized": True
    }


# 2. Portrait Mode dimensions and presets
EXPORT_PRESETS = {
    "TikTok": {
        "codec": "libx264",
        "video_bitrate": "5M",
        "audio_codec": "aac",
        "audio_bitrate": "192k",
        "fps": 30,
        "max_duration_seconds": 60,
        "resolution": "1080x1920"
    },
    "Instagram Reels": {
        "codec": "libx264",
        "video_bitrate": "4M",
        "audio_codec": "aac",
        "audio_bitrate": "128k",
        "fps": 30,
        "max_duration_seconds": 90,
        "resolution": "1080x1920"
    },
    "YouTube Shorts": {
        "codec": "libx264",
        "video_bitrate": "6M",
        "audio_codec": "aac",
        "audio_bitrate": "256k",
        "fps": 30,
        "max_duration_seconds": 60,
        "resolution": "1080x1920"
    }
}

def get_platform_export_parameters(platform: str) -> Dict[str, Any]:
    """
    Retrieves bitrate, FPS, and format configurations for target social networks.
    """
    preset = EXPORT_PRESETS.get(platform, EXPORT_PRESETS["TikTok"])
    logger.info(f"Mobile Export: Selected platform preset: {platform}")
    return preset
