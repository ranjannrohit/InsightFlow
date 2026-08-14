"""
InsightFlow — FastAPI Authentication Dependencies
Provides get_current_user() and get_optional_user() as FastAPI Depends.
"""

import os
import sys
import logging
from fastapi import Request, HTTPException

backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

import database

logger = logging.getLogger("insightflow.auth")


def get_current_user(request: Request) -> dict:
    """
    FastAPI dependency that extracts and validates the authenticated user
    from the Authorization: Bearer <token> header.

    Raises HTTP 401 if token is missing or invalid.
    Never trusts user_id / email / credits from the request body.
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail={
                "code": "AUTHENTICATION_REQUIRED",
                "message": "Authentication required. Please sign in to continue."
            }
        )

    token = auth_header[7:].strip()
    if not token:
        raise HTTPException(
            status_code=401,
            detail={
                "code": "INVALID_TOKEN",
                "message": "Invalid authentication token."
            }
        )

    user = database.get_user_by_token(token)
    if not user:
        raise HTTPException(
            status_code=401,
            detail={
                "code": "SESSION_EXPIRED",
                "message": "Session expired or invalid. Please sign in again."
            }
        )

    logger.debug(f"Authenticated user: {user.get('id')} ({user.get('email')})")
    return user


def get_optional_user(request: Request) -> dict | None:
    """
    FastAPI dependency that returns the user if authenticated, or None for guests.
    Use this for endpoints that work for both guests and authenticated users.
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None

    token = auth_header[7:].strip()
    if not token:
        return None

    return database.get_user_by_token(token)
