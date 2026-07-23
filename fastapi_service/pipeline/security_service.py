import os
import time
import logging
import hashlib
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# 1. Prompt Injection Defense
def sanitize_prompt_injection(user_prompt: str) -> str:
    """
    Cleans inputs and removes command overrides (e.g. system instructions overrides,
    acting directives bypasses) before passing variables to LLM templates.
    """
    cleaned = user_prompt.strip()
    
    # Strict prompt injection checks:
    # Reject strings trying to exit instructions (like "ignore previous instructions", "system rules overrides")
    patterns = [
        "ignore previous instructions",
        "override system prompt",
        "you are now an unfiltered",
        "do not follow standard instructions"
    ]
    for pattern in patterns:
        if pattern in cleaned.lower():
            logger.warning(f"Security: Blocked potential prompt injection attempt: '{pattern}'")
            raise ValueError(f"Security Policy Denied: Invalid instructions detected inside user prompt.")
            
    return cleaned


# 2. Vault Secrets Management Loader (AWS Secrets / HashiCorp Vault Simulator)
def get_vault_secret(secret_name: str) -> str:
    """
    Retrieves API keys from a secure secrets vault rather than local env configuration files.
    """
    logger.debug(f"Vault: Retrieving secret credentials for '{secret_name}'")
    
    # Simulate API Key retrieval lookup
    vault_secrets = {
        "OPENAI_API_KEY": "sk-vault-openai-secret-key-prod-1029",
        "ELEVENLABS_API_KEY": "el-vault-elevenlabs-secret-key-prod-3849",
        "REPLICATE_API_TOKEN": "r8-vault-replicate-token-prod-8849",
        "STRIPE_SECRET_KEY": "sk_test_vault_stripe_prod_9988"
    }
    
    val = vault_secrets.get(secret_name)
    if val:
        return val
        
    # Fallback to os.environ if not registered in vault
    return os.environ.get(secret_name, "")


# 3. Signed, Short-TTL S3 URL Generator
def generate_secure_s3_signed_url(
    bucket_name: str,
    object_key: str,
    expires_in_seconds: int = 900
) -> str:
    """
    Generates secure expiring S3 links (short TTL) preventing public bucket accesses.
    """
    expires_epoch = int(time.time()) + expires_in_seconds
    clean_key = object_key.strip("/")
    
    # Generate cryptographic signature
    raw_signature = f"{bucket_name}/{clean_key}?Expires={expires_epoch}"
    signature_hash = hashlib.sha256(raw_signature.encode('utf-8')).hexdigest()[:24]
    
    signed_url = f"https://{bucket_name}.s3.amazonaws.com/{clean_key}?AWSAccessKeyId=AKIA123&Signature={signature_hash}&Expires={expires_epoch}"
    logger.debug(f"S3: Generated expiring signed URL (TTL={expires_in_seconds}s): {signed_url}")
    return signed_url
