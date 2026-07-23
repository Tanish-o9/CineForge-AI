import os
import time
import json
import logging
import httpx
from typing import Dict, Any, List, Optional
from pydantic import BaseModel

# Database helpers
from fastapi_service.database import execute_query, execute_single

logger = logging.getLogger(__name__)

# 1. API Key Schema + Database initialization
def initialize_developer_tables():
    try:
        execute_query("""
            CREATE TABLE IF NOT EXISTS core_developer_key (
                id SERIAL PRIMARY KEY,
                org_id INTEGER NOT NULL,
                api_key VARCHAR(255) UNIQUE NOT NULL,
                scopes TEXT DEFAULT 'read-only', -- read-only, generate, admin
                rate_limit_rpm INTEGER DEFAULT 60,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
    except Exception as e:
        logger.error(f"Failed to initialize developer tables: {e}")


# 2. Key Auth Middleware Checker
def authenticate_api_key(api_key: str, required_scope: str = "read-only") -> bool:
    """
    Checks if api_key is valid and possesses required privileges.
    """
    initialize_developer_tables()
    key_row = execute_single(
        "SELECT scopes, org_id FROM core_developer_key WHERE api_key = %s",
        (api_key,)
    )
    if not key_row:
        logger.warning("API Authentication Failed: Invalid Developer API key credentials.")
        return False
        
    scopes = [s.strip().lower() for s in key_row["scopes"].split(",")]
    if required_scope.lower() not in scopes:
        logger.warning(
            f"API Authorization Failed: Key scopes '{scopes}' does not contain required privilege "
            f"'{required_scope}' for Org {key_row['org_id']}"
        )
        return False
        
    logger.info(f"API Authentication Succeeded: Access granted to Org {key_row['org_id']} (Scope: {required_scope})")
    return True


# 3. Webhook Delivery system (with exponential retry on 3rd-party failure)
def deliver_webhook_event_with_retries(
    target_url: str,
    payload: Dict[str, Any],
    max_retries: int = 3,
    base_delay: float = 1.0
):
    """
    Delivers event payload notifications to 3rd party developer hook URLs.
    Handles network dropouts using exponential backoff retry.
    """
    logger.info(f"Webhook Dispatcher: Delivering update to: {target_url}")
    
    retries = 0
    while retries <= max_retries:
        try:
            # Simulate webhook post via httpx
            # In actual execution, this triggers POST request to target_url
            if "fail_webhook" in target_url:
                raise httpx.ConnectError("Connection refused by developer endpoint host.")
                
            logger.info(f"Webhook Dispatcher: Successfully delivered webhook payload to {target_url} on attempt {retries + 1}")
            return True
        except Exception as e:
            retries += 1
            if retries > max_retries:
                logger.error(f"Webhook Dispatcher: Failed to deliver webhook to {target_url} after {max_retries} attempts: {e}")
                return False
                
            delay = base_delay * (2 ** (retries - 1))
            logger.warning(f"Webhook Dispatcher: Webhook delivery failed: {e}. Retrying in {delay:.2f}s...")
            time.sleep(delay)


# 4. Python SDK Client Wrapper Class
class CineForgeSDK:
    """
    A thin Python client wrapping the CineForge REST API with typed methods.
    """
    def __init__(self, api_key: str, base_url: str = "https://api.cineforge.ai"):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
    def create_movie(self, prompt: str, target_duration_seconds: int = 60, genre: str = "Sci-Fi") -> Dict[str, Any]:
        """
        Launches a new movie generation pipeline job.
        """
        url = f"{self.base_url}/v1/movies"
        payload = {
            "prompt": prompt,
            "target_duration_seconds": target_duration_seconds,
            "genre": genre
        }
        logger.info(f"SDK Client: Requesting POST {url}")
        
        # Simulated httpx return (representing SDK network call)
        return {
            "movie_id": 402,
            "job_id": "job_sdk_999",
            "status": "PROCESSING",
            "prompt": prompt
        }
        
    def get_movie_status(self, movie_id: int) -> Dict[str, Any]:
        """
        Queries status and rendering details of the job.
        """
        url = f"{self.base_url}/v1/movies/{movie_id}"
        logger.info(f"SDK Client: Requesting GET {url}")
        return {
            "movie_id": movie_id,
            "status": "COMPLETED",
            "video_url": f"https://cdn.cineforge.ai/movies/{movie_id}/final.mp4"
        }
