import time
import logging
import hashlib
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

# Regional mappings
REGION_PINGS = {
    "us-east": {"closest": ["us-east", "eu-west", "ap-south"], "ip_prefixes": ["192.168.1.", "10.0."]},
    "eu-west": {"closest": ["eu-west", "us-east", "ap-south"], "ip_prefixes": ["80.12.", "193."]},
    "ap-south": {"closest": ["ap-south", "eu-west", "us-east"], "ip_prefixes": ["202.1.", "115."]}
}

# 1. Multi-Region placement decision routing
def route_job_to_closest_region(user_ip: str, queue_depths: Dict[str, int], saturation_limit: int = 15) -> str:
    """
    Finds nearest worker region. If that region's queue depth exceeds the saturation_limit,
    automatically routes to the next closest region.
    """
    # Detect region from IP prefixes
    user_region = "us-east" # Default fallback
    for reg, data in REGION_PINGS.items():
        if any(user_ip.startswith(prefix) for prefix in data["ip_prefixes"]):
            user_region = reg
            break
            
    # Iterate through closest regions by priority
    priority_regions = REGION_PINGS[user_region]["closest"]
    for r in priority_regions:
        load = queue_depths.get(r, 0)
        if load < saturation_limit:
            logger.info(f"Region Routing: Routed user '{user_ip}' to region '{r}' (Load: {load})")
            return r
            
    # If all saturated, fallback to local region despite overload
    logger.warning(f"Region Routing: All regions saturated! Defaulting user '{user_ip}' to closest '{user_region}'")
    return user_region


# 2. CloudFront signed-URL generation (AWS signature simulator)
def generate_cloudfront_signed_url(s3_path: str, ttl_seconds: int = 900) -> str:
    """
    Generates a secure, expiring CDN URL for streaming videos and storyboard thumbnails.
    """
    clean_path = s3_path.replace("s3://", "").strip("/")
    cloudfront_domain = "https://d12345abcdef.cloudfront.net"
    
    expires_epoch = int(time.time()) + ttl_seconds
    
    # Generate cryptographic signature overlay
    raw_signature = f"{clean_path}?Expires={expires_epoch}&Key=APKA12345"
    signature_hash = hashlib.sha256(raw_signature.encode('utf-8')).hexdigest()[:16]
    
    signed_url = f"{cloudfront_domain}/{clean_path}?Expires={expires_epoch}&Signature={signature_hash}&Key-Pair-Id=APKA12345"
    logger.debug(f"CDN: Generated CloudFront signed URL with TTL={ttl_seconds}s: {signed_url}")
    return signed_url


# 3. Django Read Replica Database Router Setup
class ReadReplicaRouter:
    """
    Django DB router to route writes to 'default' database and reads to 'replica' instances.
    """
    def db_for_read(self, model, **hints) -> str:
        """
        Directs read queries (e.g. dashboards, history) to read replicas.
        """
        logger.debug(f"DB Routing: Directing read query for model '{model._meta.model_name}' to Replica database.")
        return 'read_replica'

    def db_for_write(self, model, **hints) -> str:
        """
        Guarantees write operations route to primary DB.
        """
        logger.debug(f"DB Routing: Directing write query for model '{model._meta.model_name}' to Primary database.")
        return 'default'

    def allow_relation(self, obj1, obj2, **hints) -> bool:
        return True

    def allow_migrate(self, db, app_label, model_name=None, **hints) -> bool:
        return True
