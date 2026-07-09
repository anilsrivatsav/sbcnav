from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Iterable

from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import ValidationError

logger = logging.getLogger("rail_dashboard.api")


@dataclass
class Page:
    items: list[dict[str, Any]]
    total: int
    page: int
    page_size: int


def envelope(data: Any, message: str = "ok", success: bool = True) -> dict[str, Any]:
    return {"success": success, "message": message, "data": data}


def paginate(items: Iterable[dict[str, Any]], page: int, page_size: int) -> Page:
    items = list(items)
    total = len(items)
    start = (page - 1) * page_size
    end = start + page_size
    return Page(items=items[start:end], total=total, page=page, page_size=page_size)


def sort_items(items: list[dict[str, Any]], sort_by: str | None, sort_order: str) -> list[dict[str, Any]]:
    if not sort_by:
        return items
    reverse = sort_order.lower() == "desc"
    return sorted(items, key=lambda item: (item.get(sort_by) is None, item.get(sort_by)), reverse=reverse)


def filter_search(items: list[dict[str, Any]], search: str | None) -> list[dict[str, Any]]:
    if not search:
        return items
    q = search.lower().strip()
    return [item for item in items if any(q in str(value).lower() for value in item.values() if value is not None)]


def log_request(request: Request, response: JSONResponse) -> JSONResponse:
    logger.info("%s %s -> %s", request.method, request.url.path, response.status_code)
    return response


def http_error(status_code: int, message: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail=message)


def exception_response(exc: Exception) -> JSONResponse:
    logger.exception("Unhandled API error: %s", exc)
    return JSONResponse(status_code=500, content=envelope(None, "Internal server error", False))

