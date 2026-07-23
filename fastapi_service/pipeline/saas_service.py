import os
import logging
import threading
from typing import Dict, Any, List, Optional
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Thread-local storage to securely store request tenant context
_tenant_context = threading.local()

def set_current_org_id(org_id: Optional[int]):
    """
    Sets active tenant org ID on active request thread context.
    """
    if org_id is not None:
        _tenant_context.org_id = int(org_id)
        logger.debug(f"SaaS Context: Thread assigned active Org ID {org_id}")
    else:
        if hasattr(_tenant_context, "org_id"):
            delattr(_tenant_context, "org_id")

def get_current_org_id() -> Optional[int]:
    """
    Retrieves active tenant org ID from request thread context.
    """
    return getattr(_tenant_context, "org_id", None)


# 1. Organization & Membership schemas
class OrganizationSchema(BaseModel):
    id: int
    name: str
    billing_plan: str # FREE, PRO, ENTERPRISE
    usage_quota_daily: int

class UserMembership(BaseModel):
    user_id: int
    org_id: int
    role: str # OWNER, EDITOR, VIEWER, COMMENTER


# 2. Database Schema Initialization & Query Isolation Mixin
def initialize_saas_tables():
    from fastapi_service.database import execute_query
    try:
        execute_query("""
            CREATE TABLE IF NOT EXISTS core_organization (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                billing_plan VARCHAR(50) DEFAULT 'FREE',
                usage_quota_daily INTEGER DEFAULT 5,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        execute_query("""
            CREATE TABLE IF NOT EXISTS core_membership (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                org_id INTEGER NOT NULL REFERENCES core_organization(id) ON DELETE CASCADE,
                role VARCHAR(20) DEFAULT 'VIEWER',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, org_id)
            );
        """)
        
        # Inject org_id to core_movie, core_character, core_asset and core_renderjob dynamically
        for table in ["core_movie", "core_character", "core_asset", "core_renderjob"]:
            execute_query(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS org_id INTEGER DEFAULT 1;")
            
        logger.info("SaaS: Multi-tenant schemas successfully initialized and migrated.")
    except Exception as e:
        logger.error(f"SaaS schema initialization failed: {e}")

def apply_row_level_tenant_scoping(query: str, params: tuple) -> tuple:
    """
    Overrides raw queries to always append thread-local org_id filter conditions.
    Protects database execution from client parameter manipulations.
    """
    org_id = get_current_org_id()
    if org_id is None:
        return query, params
        
    q_lower = query.lower()
    # Check if target table is tenant isolated
    isolated_tables = ["core_movie", "core_character", "core_asset", "core_renderjob"]
    target_table = None
    for table in isolated_tables:
        if table in q_lower:
            target_table = table
            break
            
    if not target_table:
        return query, params
        
    # Append tenant scoping
    if "where" in q_lower:
        # Inject AND condition right after WHERE
        parts = query.split("WHERE", 1)
        modified_query = f"{parts[0]}WHERE org_id = %s AND {parts[1]}"
    else:
        # Check if it has ORDER BY, LIMIT etc.
        # Simple suffix scoping
        if "order by" in q_lower:
            parts = query.split("ORDER BY", 1)
            modified_query = f"{parts[0]} WHERE org_id = %s ORDER BY {parts[1]}"
        elif "limit" in q_lower:
            parts = query.split("LIMIT", 1)
            modified_query = f"{parts[0]} WHERE org_id = %s LIMIT {parts[1]}"
        else:
            modified_query = f"{query} WHERE org_id = %s"
            
    modified_params = (org_id,) + params
    logger.debug(f"Tenant Scoping: Injected org_id={org_id} into query.")
    return modified_query, modified_params


# 3. S3 Bucket Folder Partitioning per Org
def get_isolated_s3_prefix(org_id: int, category: str, file_name: str) -> str:
    """
    Creates isolated S3 folder keys: org_id/category/file_name
    """
    clean_cat = category.strip("/").lower()
    return f"org_{org_id}/{clean_cat}/{file_name}"


# 4. JWT claims extraction and validation helper
def extract_jwt_tenant_claims(token_claims: Dict[str, Any]) -> int:
    """
    Parses active token credentials and sets active org id context.
    Raises PermissionError if active claims are missing.
    """
    active_org = token_claims.get("active_org_id")
    if not active_org:
        raise PermissionError("Access Denied: Missing active organization tenant claim.")
        
    # Overwrite thread locals
    set_current_org_id(active_org)
    return int(active_org)
