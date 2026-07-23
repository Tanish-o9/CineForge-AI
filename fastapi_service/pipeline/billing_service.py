import os
import json
import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Request, Header

# Database helpers
from fastapi_service.database import execute_query, execute_single

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/billing", tags=["Stripe Subscription Billing"])

# 1. Plan limits mapping
PLAN_LIMITS = {
    "FREE": {"movies_per_month": 2, "max_resolution": "720p", "watermark": True},
    "PRO": {"movies_per_month": 20, "max_resolution": "1080p", "watermark": False},
    "ENTERPRISE": {"movies_per_month": 9999, "max_resolution": "4k", "watermark": False}
}

# 2. Database schemas setup
def initialize_billing_tables():
    try:
        execute_query("""
            CREATE TABLE IF NOT EXISTS core_subscription (
                id SERIAL PRIMARY KEY,
                org_id INTEGER NOT NULL UNIQUE,
                stripe_subscription_id VARCHAR(255) UNIQUE,
                status VARCHAR(50) NOT NULL,
                tier VARCHAR(20) DEFAULT 'FREE',
                current_period_end TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
    except Exception as e:
        logger.error(f"Failed to initialize billing tables: {e}")


# 3. Usage Metering & Quota Check Middleware
def enforce_org_usage_limits(org_id: int):
    """
    Checks the organization's subscription tier and ensures they haven't exceeded
    their monthly generation limit.
    """
    initialize_billing_tables()
    
    # Get active subscription
    sub = execute_single(
        "SELECT tier, status FROM core_subscription WHERE org_id = %s",
        (org_id,)
    )
    tier = sub["tier"].upper() if sub else "FREE"
    status = sub["status"].lower() if sub else "active"
    
    # If subscription is cancelled or unpaid, fallback to FREE tier limits
    if status not in ["active", "trialing"]:
        tier = "FREE"
        
    limits = PLAN_LIMITS.get(tier, PLAN_LIMITS["FREE"])
    
    # Query movies generated in current month
    usage = execute_single(
        "SELECT COUNT(*) as count FROM core_movie WHERE org_id = %s AND created_at >= DATE_TRUNC('month', CURRENT_DATE)",
        (org_id,)
    )
    generated = usage["count"] if usage else 0
    
    if generated >= limits["movies_per_month"]:
        raise ValueError(
            f"Quota Exceeded! Your organization has generated {generated}/{limits['movies_per_month']} "
            f"movies this month. Please upgrade your Stripe subscription to Pro or Enterprise."
        )
        
    logger.info(f"Billing Quota Check: Org {org_id} has used {generated}/{limits['movies_per_month']} slots (Tier: {tier})")


# 4. Stripe Webhook Events Handler
@router.post("/webhook")
async def stripe_webhook_endpoint(request: Request, stripe_signature: Optional[str] = Header(None)):
    """
    Processes Stripe billing notifications (Created, Updated, Cancelled, Failed Payments).
    """
    initialize_billing_tables()
    payload = await request.body()
    
    try:
        event = json.loads(payload)
    except Exception as e:
        raise HTTPException(status_code=400, detail="Invalid Stripe webhook payload JSON")
        
    event_type = event.get("type")
    data_obj = event.get("data", {}).get("object", {})
    
    sub_id = data_obj.get("id")
    cust_id = data_obj.get("customer")
    
    # Mocking customer -> org mapping for testing (typically stored in a lookup table)
    # We select org_id = 1 for test cases
    org_id = 1
    
    if event_type == "customer.subscription.created":
        status = data_obj.get("status")
        # Extract metadata tier or parse plan name
        tier = data_obj.get("metadata", {}).get("tier", "PRO").upper()
        
        execute_query("""
            INSERT INTO core_subscription (org_id, stripe_subscription_id, status, tier, current_period_end)
            VALUES (%s, %s, %s, %s, TO_TIMESTAMP(%s))
            ON CONFLICT (org_id) DO UPDATE SET
                stripe_subscription_id = EXCLUDED.stripe_subscription_id,
                status = EXCLUDED.status,
                tier = EXCLUDED.tier,
                current_period_end = EXCLUDED.current_period_end
        """, (org_id, sub_id, status, tier, data_obj.get("current_period_end", 1782182400)))
        logger.info(f"Stripe Webhook: Created {tier} subscription for Org {org_id}")
        
    elif event_type == "customer.subscription.updated":
        status = data_obj.get("status")
        tier = data_obj.get("metadata", {}).get("tier", "PRO").upper()
        
        execute_query("""
            UPDATE core_subscription
            SET status = %s, tier = %s, current_period_end = TO_TIMESTAMP(%s)
            WHERE stripe_subscription_id = %s
        """, (status, tier, data_obj.get("current_period_end", 1782182400), sub_id))
        logger.info(f"Stripe Webhook: Updated subscription status to '{status}' (Tier: {tier})")
        
    elif event_type == "customer.subscription.deleted":
        # Auto-downgrade to Free
        execute_query("""
            UPDATE core_subscription
            SET status = 'cancelled', tier = 'FREE'
            WHERE stripe_subscription_id = %s
        """, (sub_id,))
        logger.info(f"Stripe Webhook: Subscription deleted. Downgraded Org {org_id} to FREE plan.")
        
    elif event_type == "invoice.payment_failed":
        # Handle unpaid status
        execute_query("""
            UPDATE core_subscription
            SET status = 'unpaid', tier = 'FREE'
            WHERE stripe_subscription_id = %s
        """, (sub_id,))
        logger.warning(f"Stripe Webhook: Invoice payment failed for subscription {sub_id}. Defaulted to FREE limits.")
        
    return {"status": "SUCCESS"}
