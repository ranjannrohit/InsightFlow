"""
InsightFlow — Credit Service
Handles credit balance, daily reset enforcement, and atomic deduction.
All credit operations must go through this module — never manipulate
credits directly in route handlers.
"""

import os
import sys
import logging
from fastapi import HTTPException

backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

import database

logger = logging.getLogger("insightflow.credits")

# Credit costs per operation
CREDIT_COSTS = {
    "AI_CHAT": 1,
    "FORECAST": 1,
    "EXECUTIVE_REPORT": 1,
    "VISUALIZATION": 1,
    "EDA": 1,
    "CLEANING_AUDIT": 1,
    "ANOMALY_DETECTION": 1,
    "SEGMENTATION": 1,
    "RECOMMENDATIONS": 1,
    "AGENT_PLAN": 1,
    "ROOT_CAUSE": 1,
}


def get_balance(user_id: str) -> int:
    """
    Returns the current credit balance for the user.
    Automatically applies the daily reset if a new UTC day has started.
    """
    return database.get_user_credits(user_id)


def can_spend(user_id: str, operation: str = "GENERIC") -> bool:
    """
    Checks if the user has enough credits for the given operation.
    Applies daily reset check automatically.
    """
    balance = get_balance(user_id)
    cost = CREDIT_COSTS.get(operation, 1)
    return balance >= cost


def ensure_credits(user_id: str, operation: str = "GENERIC") -> None:
    """
    Checks credit balance and raises HTTP 429 if insufficient.
    Call this BEFORE performing the billable operation.
    """
    balance = get_balance(user_id)
    cost = CREDIT_COSTS.get(operation, 1)

    if balance < cost:
        logger.warning(f"User {user_id} has insufficient credits for {operation} (balance={balance})")
        raise HTTPException(
            status_code=429,
            detail={
                "code": "INSUFFICIENT_CREDITS",
                "message": "You have no credits remaining today. Credits reset daily at midnight UTC.",
                "balance": balance,
                "required": cost
            }
        )


def spend_credit(user_id: str, operation: str, resource_id: str = None) -> bool:
    """
    Atomically deducts 1 credit and records the transaction.
    Returns True if successful, False if insufficient credits.
    Should be called AFTER a successful operation to avoid double-charging on failure.

    Usage pattern:
        ensure_credits(user_id, "AI_CHAT")   # raises 429 if no credits
        result = do_expensive_operation()     # do the work
        spend_credit(user_id, "AI_CHAT", id) # deduct AFTER success
    """
    success = database.spend_credit(user_id, operation, resource_id)
    if success:
        logger.info(f"Credit spent: user={user_id} op={operation} resource={resource_id}")
    else:
        logger.warning(f"Credit deduction failed: user={user_id} op={operation} (race condition or 0 balance)")
    return success


def record_reset(user_id: str) -> None:
    """Manually triggers a credit reset (e.g., for admin/debug purposes)."""
    database.reset_daily_credits(user_id)
    logger.info(f"Credits manually reset for user={user_id}")
