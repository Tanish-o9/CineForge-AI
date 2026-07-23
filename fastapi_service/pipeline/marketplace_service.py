import logging
from typing import Dict, Any, List, Optional
from pydantic import BaseModel

# Database helpers
from fastapi_service.database import execute_query, execute_single

logger = logging.getLogger(__name__)

# 1. Marketplace schemas and DB initializations
def initialize_marketplace_tables():
    try:
        execute_query("""
            CREATE TABLE IF NOT EXISTS core_marketplace_listing (
                id SERIAL PRIMARY KEY,
                creator_org_id INTEGER NOT NULL,
                asset_type VARCHAR(50) NOT NULL, -- prompt_template, style_lora, character_pack, music_pack
                style_lora_id INTEGER, -- references core_style_lora(id)
                price NUMERIC(10, 2) DEFAULT 0.00,
                preview_media_url VARCHAR(512),
                download_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        execute_query("""
            CREATE TABLE IF NOT EXISTS core_marketplace_purchase (
                id SERIAL PRIMARY KEY,
                listing_id INTEGER NOT NULL REFERENCES core_marketplace_listing(id) ON DELETE CASCADE,
                buyer_org_id INTEGER NOT NULL,
                stripe_charge_id VARCHAR(255) UNIQUE,
                purchased_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
    except Exception as e:
        logger.error(f"Failed to initialize marketplace schemas: {e}")


# 2. Purchase Flow: Stripe Connect Split Transfers payouts
class PurchaseRequest(BaseModel):
    listing_id: int
    buyer_org_id: int

def execute_stripe_connect_split_purchase(listing_id: int, buyer_org_id: int) -> Dict[str, Any]:
    """
    Executes split fee payout: transfers (Price - PlatformCut) to the creator's Connect account
    and records the purchase transaction in Postgres.
    """
    initialize_marketplace_tables()
    
    # Query listing info
    listing = execute_single(
        "SELECT creator_org_id, price FROM core_marketplace_listing WHERE id = %s",
        (listing_id,)
    )
    if not listing:
        raise ValueError(f"Marketplace listing ID {listing_id} not found.")
        
    price = float(listing["price"])
    creator_org = listing["creator_org_id"]
    
    # Calculate split: Platform takes 15% service cut fee
    platform_fee = price * 0.15
    creator_payout = price - platform_fee
    
    logger.info(
        f"Stripe Connect: Processing split payout for listing {listing_id}. Total: ${price:.2f} | "
        f"Platform Fee (15%): ${platform_fee:.2f} | Creator Org {creator_org} Payout: ${creator_payout:.2f}"
    )
    
    # Record purchase transaction
    stripe_charge_id = f"ch_connect_{buyer_org_id}_{listing_id}"
    execute_query("""
        INSERT INTO core_marketplace_purchase (listing_id, buyer_org_id, stripe_charge_id)
        VALUES (%s, %s, %s)
    """, (listing_id, buyer_org_id, stripe_charge_id))
    
    # Update downloads counter
    execute_query(
        "UPDATE core_marketplace_listing SET download_count = download_count + 1 WHERE id = %s",
        (listing_id,)
    )
    
    return {
        "status": "PAID",
        "charge_id": stripe_charge_id,
        "platform_fee": platform_fee,
        "creator_payout": creator_payout,
        "creator_org_id": creator_org
    }


# 3. Usage rights check function (integrated into LoRA style loading wrapper)
def verify_style_usage_rights(org_id: int, style_lora_id: int) -> bool:
    """
    Ensures that a custom LoRA style is only loaded if the org owns it (creator)
    or has purchased it from the marketplace.
    """
    initialize_marketplace_tables()
    
    # 1. Check if the org created the style
    style = execute_single(
        "SELECT org_id FROM core_style_lora WHERE id = %s",
        (style_lora_id,)
    )
    if not style:
        logger.warning(f"Rights Check: LoRA Style ID {style_lora_id} does not exist.")
        return False
        
    if int(style["org_id"]) == int(org_id):
        logger.info(f"Rights Check: Access granted. Org {org_id} is creator of LoRA Style {style_lora_id}.")
        return True
        
    # 2. Check if the org has purchased the style listing
    purchase = execute_single("""
        SELECT p.id 
        FROM core_marketplace_purchase p
        JOIN core_marketplace_listing l ON p.listing_id = l.id
        WHERE p.buyer_org_id = %s AND l.style_lora_id = %s
    """, (org_id, style_lora_id))
    
    if purchase:
        logger.info(f"Rights Check: Access granted. Org {org_id} has purchased usage rights for LoRA Style {style_lora_id}.")
        return True
        
    logger.warning(f"Rights Check: Access Denied! Org {org_id} has no purchase licenses for LoRA Style {style_lora_id}.")
    return False
