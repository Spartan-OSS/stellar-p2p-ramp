"""Structured error responses and centralized exception handlers for FastAPI."""

from __future__ import annotations

import logging
from typing import Any, Optional
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from stellar_p2p.domain import InvalidTransition

logger = logging.getLogger("stellar_p2p.errors")


class ErrorDetail(BaseModel):
    """Uniform structured error payload."""

    code: str = Field(..., description="Machine-readable error classification code")
    message: str = Field(..., description="Human-readable description of the error")
    details: Optional[Any] = Field(default=None, description="Optional diagnostic details or validation errors")


class ErrorResponse(BaseModel):
    """Top-level error response envelope."""

    error: ErrorDetail


def build_error_response(status_code: int, code: str, message: str, details: Optional[Any] = None) -> JSONResponse:
    """Helper to generate consistent JSON error responses."""
    payload = {
        "error": {
            "code": code,
            "message": message,
            "details": details,
        }
    }
    return JSONResponse(status_code=status_code, content=payload)


async def http_exception_handler(_request: Request, exc: HTTPException) -> JSONResponse:
    """Handle standard HTTPExceptions with structured JSON body."""
    code_mapping = {
        400: "bad_request",
        401: "unauthorized",
        403: "forbidden",
        404: "not_found",
        409: "conflict",
        422: "unprocessable_entity",
        500: "internal_server_error",
        503: "service_unavailable",
    }
    error_code = code_mapping.get(exc.status_code, f"http_{exc.status_code}")
    message = str(exc.detail) if isinstance(exc.detail, str) else "HTTP request error"
    details = exc.detail if isinstance(exc.detail, (dict, list)) else None
    return build_error_response(exc.status_code, error_code, message, details)


async def validation_exception_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
    """Format request validation errors consistently without internal traceback exposure."""
    formatted_errors = []
    for err in exc.errors():
        formatted_errors.append({
            "loc": [str(x) for x in err.get("loc", [])],
            "msg": err.get("msg", ""),
            "type": err.get("type", ""),
        })
    return build_error_response(
        status.HTTP_422_UNPROCESSABLE_ENTITY,
        "validation_error",
        "Request body or parameters failed schema validation.",
        details=formatted_errors,
    )


async def domain_invalid_transition_handler(_request: Request, exc: InvalidTransition) -> JSONResponse:
    """Map pure domain state transition conflicts to HTTP 409 Conflict."""
    logger.warning("Domain transition rejected: %s", exc)
    return build_error_response(
        status.HTTP_409_CONFLICT,
        "invalid_transition",
        str(exc),
    )


async def unhandled_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
    """Catch-all handler preventing internal exception leakage (CWE-209 mitigation)."""
    logger.error("Unhandled server exception: %s", exc, exc_info=True)
    return build_error_response(
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        "internal_server_error",
        "An unexpected internal error occurred. Please contact support or try again.",
    )


def register_error_handlers(app: FastAPI) -> None:
    """Attach standard structured error handlers to the FastAPI application instance."""
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(InvalidTransition, domain_invalid_transition_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
