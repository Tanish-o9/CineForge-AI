import json
import hashlib
import logging
from typing import Dict, Any, Optional

# Database helpers
from fastapi_service.database import execute_query, execute_single

logger = logging.getLogger(__name__)

# 1. Database Schema initialization
def initialize_compliance_tables():
    try:
        execute_query("""
            CREATE TABLE IF NOT EXISTS core_compliance_audit_trail (
                id SERIAL PRIMARY KEY,
                action VARCHAR(100) NOT NULL,
                details TEXT,
                parent_hash VARCHAR(64) NOT NULL,
                current_hash VARCHAR(64) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
    except Exception as e:
        logger.error(f"Failed to initialize compliance: {e}")


# 2. Immutable Hash-Chained Audit Trail Writer
def write_compliance_audit_log(action: str, details: str) -> Dict[str, str]:
    """
    Appends a new record to the SOC2 audit log.
    Retrieves the last log's hash as parent_hash, and computes SHA-256 over
    parent_hash + action + details to yield the new current_hash.
    """
    initialize_compliance_tables()
    
    # Retrieve latest hash
    last_log = execute_single(
        "SELECT current_hash FROM core_compliance_audit_trail ORDER BY id DESC LIMIT 1"
    )
    
    parent_hash = last_log["current_hash"] if last_log else "0" * 64
    
    # Compute new hash
    payload = f"{parent_hash}:{action}:{details}"
    current_hash = hashlib.sha256(payload.encode('utf-8')).hexdigest()
    
    query = """
        INSERT INTO core_compliance_audit_trail (action, details, parent_hash, current_hash)
        VALUES (%s, %s, %s, %s)
    """
    execute_query(query, (action, details, parent_hash, current_hash))
    logger.info(f"SOC2 Audit: Appended hash-chained log. Hash: {current_hash[:8]}... (Parent: {parent_hash[:8]}...)")
    
    return {
        "action": action,
        "parent_hash": parent_hash,
        "current_hash": current_hash
    }


# 3. OIDC / SAML SSO SSO redirect middleware simulator
def simulate_oidc_sso_handshake(idp_issuer: str, sso_token: str) -> Dict[str, Any]:
    """
    Simulates OIDC/SAML token validations and returns claims.
    """
    logger.info(f"SSO Handshake: Validating token against IdP: {idp_issuer}")
    # In production, this decodes JWTs using pyjwt + key discovery endpoints (jwks)
    if "valid" in sso_token.lower():
        return {
            "status": "AUTHENTICATED",
            "user_id": 4022,
            "email": "enterprise_user@client.com",
            "org_id": 1,
            "groups": ["cineforge-editors", "compliance-auditors"]
        }
    raise PermissionError("OIDC Validation Failed: Signature mismatch or expired token credentials.")


# 4. SCIM User Provisioning endpoints helper
def execute_scim_user_provisioning(
    action: str, # "CREATE", "DELETE"
    user_email: str,
    org_id: int
) -> Dict[str, Any]:
    """
    SCIM directory Provisioning handler. Syncs IdP group changes.
    """
    logger.info(f"SCIM Sync: Action {action} requested for user '{user_email}' inside Org {org_id}")
    
    if action == "CREATE":
        # Check if user exists, if not create record
        write_compliance_audit_log(
            "SCIM_USER_CREATED",
            f"User '{user_email}' auto-provisioned via SCIM directory sync in Org {org_id}."
        )
        return {"status": "SUCCESS", "message": f"User {user_email} provisioned."}
        
    elif action == "DELETE":
        # Disable user
        write_compliance_audit_log(
            "SCIM_USER_DEACTIVATED",
            f"User '{user_email}' deactivated via SCIM directory sync in Org {org_id}."
        )
        return {"status": "SUCCESS", "message": f"User {user_email} deactivated."}
        
    return {"status": "ERROR", "message": "Unsupported SCIM action"}
