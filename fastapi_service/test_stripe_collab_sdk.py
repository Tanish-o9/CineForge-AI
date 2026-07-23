import os
import sys
import json
import logging
from unittest.mock import MagicMock, patch

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TestScaleEnterprise")

# Mock database module to prevent dependency exception
mock_db = MagicMock()
sys.modules['fastapi_service.database'] = mock_db

# Mock Celery to prevent host import exceptions
sys.modules['celery'] = MagicMock()
sys.modules['celery.exceptions'] = MagicMock()

# Import targets
from fastapi_service.pipeline.billing_service import enforce_org_usage_limits
from fastapi_service.pipeline.moderation_service import check_prompt_moderation, check_image_safety, add_to_moderation_queue
from fastapi_service.pipeline.region_service import route_job_to_closest_region, generate_cloudfront_signed_url
from fastapi_service.pipeline.developer_service import authenticate_api_key, deliver_webhook_event_with_retries, CineForgeSDK
from fastapi_service.pipeline.marketplace_service import execute_stripe_connect_split_purchase, verify_style_usage_rights

def run_enterprise_tests():
    logger.info("=== STARTING STRIPE, MODERATION, CDN, SDK, & CONNECT TESTS ===")

    # 1. Stripe Billing Limits
    logger.info("\nTask 6: Testing Stripe Subscriptions & Quota Enforcement")
    mock_db.execute_single.side_effect = [
        {"tier": "FREE", "status": "active"}, # enforce limits
        {"count": 1}, # movies generated this month (limit 2 -> OK)
        {"tier": "FREE", "status": "active"}, # enforce limits
        {"count": 3}  # movies generated this month (limit 2 -> Exceeded!)
    ]
    mock_db.execute_query.return_value = None
    
    # 1 movie used under free tier -> allowed
    enforce_org_usage_limits(org_id=1)
    
    # 3 movies used under free tier -> raises value error
    try:
        enforce_org_usage_limits(org_id=1)
        assert False
    except ValueError as ve:
        logger.info(f"Quota enforcement caught correctly: {ve}")
        
    logger.info("✔ Stripe subscriptions and billing quotas verified successfully.")

    # 2. Moderation checks
    logger.info("\nTask 7: Testing Prompt & Visual Moderation Filters")
    mock_db.execute_single.side_effect = None
    mock_db.execute_single.return_value = None
    
    # Safe prompt
    safe, r_safe = check_prompt_moderation("An astronaut exploring Mars silt.")
    assert safe is True
    
    # Unsafe prompt
    unsafe, r_unsafe = check_prompt_moderation("Exploding buildings and bombs in cities.")
    logger.info(f"Unsafe prompt flagged: {unsafe} (Reason: {r_unsafe})")
    assert unsafe is False
    
    # Visual check unsafe
    v_safe, r_v_safe = check_image_safety("/renders/shot_ok.png")
    assert v_safe is True
    
    v_unsafe, r_v_unsafe = check_image_safety("/renders/shot_unsafe_frame.png")
    logger.info(f"Visual frame safety flagged: {v_unsafe} (Reason: {r_v_unsafe})")
    assert v_unsafe is False
    
    # Check Review queue mapping
    add_to_moderation_queue(movie_id=10, flagged_stage="storyboard", reason="unsafe visual elements")
    assert mock_db.execute_query.call_count > 1
    logger.info("✔ Content moderation filters and audit logs verified successfully.")

    # 3. Multi-Region & CDN
    logger.info("\nTask 8: Testing Multi-Region Queue Placement & CloudFront")
    queue_loads = {"us-east": 8, "eu-west": 4, "ap-south": 12}
    
    # Route user in US (IP starting 192.168.1.) -> us-east (load 8 < 15)
    r_us = route_job_to_closest_region("192.168.1.55", queue_loads)
    logger.info(f"Routed US client to region: {r_us}")
    assert r_us == "us-east"
    
    # Route user in US if us-east saturated (e.g. load = 20)
    queue_loads["us-east"] = 20
    r_us_fallback = route_job_to_closest_region("192.168.1.55", queue_loads)
    logger.info(f"Routed US client with us-east saturated to: {r_us_fallback}")
    assert r_us_fallback == "eu-west" # next closest region!
    
    # CloudFront Signed URL
    url = generate_cloudfront_signed_url("s3://bucket/movies/10/final.mp4", ttl_seconds=600)
    logger.info(f"Signed CDN URL: {url}")
    assert "Expires=" in url and "Signature=" in url
    logger.info("✔ Multi-region routing and expiring CDN signed URLs verified successfully.")

    # 4. Developer API & SDK Client
    logger.info("\nTask 9: Testing Dev APIs Keys & Python SDK Clients")
    mock_db.execute_single.return_value = {"scopes": "read-only, generate", "org_id": 4}
    
    # Test api key authorization scopes
    assert authenticate_api_key("sk_key_abc", required_scope="generate") is True
    assert authenticate_api_key("sk_key_abc", required_scope="admin") is False
    
    # Webhook delivery backoff retries
    success = deliver_webhook_event_with_retries(
        target_url="https://dev.hook/fail_webhook",
        payload={"event": "movie.completed"},
        max_retries=2,
        base_delay=0.1
    )
    assert success is False # exhausted retries
    
    # SDK client calls
    sdk = CineForgeSDK(api_key="sk_pro_123")
    res_sdk = sdk.create_movie("Space opera prompt", target_duration_seconds=30)
    logger.info(f"SDK Client creation response: {res_sdk}")
    assert res_sdk["movie_id"] == 402
    logger.info("✔ Developer SDK classes and Webhook handlers verified successfully.")

    # 5. Testing Marketplace Connect Payouts
    logger.info("\nTask 10: Testing Marketplace Connect Split Payouts")
    mock_db.execute_single.side_effect = [
        {"creator_org_id": 5, "price": "100.00"}, # listing lookup
        {"org_id": 5}, # creator ownership verify (first check)
        {"org_id": 5}, # creator ownership verify (second check)
        {"id": 99} # purchase verify for org 12 (second check)
    ]
    
    # Stripe connect payout split
    payout = execute_stripe_connect_split_purchase(listing_id=45, buyer_org_id=12)
    logger.info(f"Stripe connect split payout calculations: {payout}")
    assert payout["platform_fee"] == 15.00
    assert payout["creator_payout"] == 85.00
    
    # Usage rights verification
    assert verify_style_usage_rights(org_id=5, style_lora_id=10) is True # creator has rights
    assert verify_style_usage_rights(org_id=12, style_lora_id=10) is True # purchaser has rights
    logger.info("✔ Marketplace billing splits and style usage rights verified successfully.")

    logger.info("=== ALL ENTERPRISE AND SCALE SAAS TESTS COMPLETED SUCCESSFULLY ===")

if __name__ == '__main__':
    run_enterprise_tests()
