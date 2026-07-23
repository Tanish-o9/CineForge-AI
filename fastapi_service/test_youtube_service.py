import os
import sys
import json
import logging
from unittest.mock import MagicMock, patch

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TestYouTube")

# Mock database module to prevent dependency exception
mock_db = MagicMock()
sys.modules['fastapi_service.database'] = mock_db

# Import targets
from fastapi_service.pipeline.youtube_service import (
    encrypt_refresh_token,
    decrypt_refresh_token,
    generate_youtube_metadata,
    upload_video_resumable,
    publish_movie_to_youtube,
    PublishRequest
)

def run_youtube_tests():
    logger.info("=== STARTING YOUTUBE PUBLISHING SERVICE TESTS ===")

    # 1. Test Fernet Encryption / Decryption
    logger.info("Step A: Testing refresh token symmetric encryption")
    secret_token = "rt_oauth_token_12345abcdef"
    encrypted = encrypt_refresh_token(secret_token)
    decrypted = decrypt_refresh_token(encrypted)
    logger.info(f"Original: {secret_token}")
    logger.info(f"Encrypted: {encrypted[:30]}...")
    logger.info(f"Decrypted: {decrypted}")
    
    assert decrypted == secret_token
    logger.info("✔ Fernet encryption and decryption match successfully.")

    # 2. Test LLM Metadata SEO Prompt
    logger.info("\nStep B: Testing YouTube SEO metadata generator prompt")
    meta = generate_youtube_metadata(
        title="Titan Horizon",
        genre="Sci-Fi",
        plot_summary="A crew contains a rogue colony AI on Titan.",
        api_key="" # Bypasses real LLM call to return fallback layout
    )
    logger.info(f"Generated SEO Title: {meta.title}")
    logger.info(f"Generated SEO Description: {meta.description}")
    logger.info(f"Generated SEO Tags: {meta.tags}")
    
    assert "Titan" in meta.title
    assert "sci-fi" in meta.tags
    logger.info("✔ YouTube metadata generator completed successfully.")

    # 3. Test Resumable Chunked Upload loop with Mock
    logger.info("\nStep C: Testing YouTube Data API v3 resumable chunked upload")
    
    # Setup mock request and status progress
    mock_request = MagicMock()
    mock_status_1 = MagicMock()
    mock_status_1.progress.return_value = 0.5
    
    # First chunk upload returns progress status, second chunk finishes
    mock_request.next_chunk.side_effect = [
        (mock_status_1, None),
        (None, {"id": "yt_video_id_999"})
    ]
    
    # Make sure mock video file exists
    dummy_video = "storage/movies/1/final_movie.mp4"
    os.makedirs(os.path.dirname(dummy_video), exist_ok=True)
    with open(dummy_video, "w") as f:
        f.write("mock movie content")
        
    # We patch the googleapiclient request builder
    with patch("fastapi_service.pipeline.youtube_service.google_apis_installed", True), \
         patch("fastapi_service.pipeline.youtube_service.build") as mock_build, \
         patch("fastapi_service.pipeline.youtube_service.MediaFileUpload") as mock_media:
         
         # Mock insert method call return
         mock_youtube_service = MagicMock()
         mock_youtube_service.videos().insert.return_value = mock_request
         mock_build.return_value = mock_youtube_service
         
         video_id = upload_video_resumable(
             credentials_obj="mock-credentials",
             video_path=dummy_video,
             meta=meta
         )
         
         logger.info(f"Returned YouTube Video ID: {video_id}")
         assert video_id == "yt_video_id_999"
         assert mock_request.next_chunk.call_count == 2
         logger.info("✔ Resumable chunked upload successfully completed progress tracking loops.")

    # 4. Test database status updates and endpoints
    logger.info("\nStep D: Testing Movie table updates and video publishing endpoint")
    mock_db.execute_single.side_effect = [
        # SELECT title, genre, story_summary, final_video_path
        {
            "title": "Titan Horizon",
            "genre": "Sci-Fi",
            "story_summary": "Summary",
            "final_video_path": dummy_video
        },
        # SELECT refresh_token (unconnected fallback)
        None
    ]
    mock_db.execute_query.return_value = None
    
    publish_res = publish_movie_to_youtube(PublishRequest(movie_id=101), user_id=1)
    logger.info(f"Publish Endpoint Response: {publish_res}")
    assert publish_res["status"] == "PUBLISHED"
    assert "mock_youtube_video_id" in publish_res["video_id"]
    logger.info("✔ Movie table status fields and publishing endpoint successfully verified.")

    # Cleanup
    if os.path.exists(dummy_video):
        os.remove(dummy_video)

    logger.info("=== YOUTUBE PUBLISHING SERVICE TESTS COMPLETED SUCCESSFULLY ===")

if __name__ == '__main__':
    run_youtube_tests()
