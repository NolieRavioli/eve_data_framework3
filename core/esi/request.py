"""Public ESI HTTP helpers.

Every outbound ESI call in the project **must** go through the functions
exported here — ``esi_get``, ``esi_post``, ``esi_request``.

Re-exports ``set_request_lane``, ``set_post_request_hook``,
``set_post_request_detail_hook``, and ``get_esi_rate_limiter`` from the
internal rate-engine so callers do not need to know about ``core.esi.rate``.
"""

import requests

from core.esi.rate import (
    get_esi_rate_limiter,
    set_post_request_detail_hook,
    set_post_request_hook,
    set_request_lane,
)

__all__ = [
    "esi_request",
    "esi_get",
    "esi_post",
    "set_request_lane",
    "set_post_request_hook",
    "set_post_request_detail_hook",
    "get_esi_rate_limiter",
]


def esi_request(method: str, url: str, **kwargs) -> requests.Response:
    """Execute an HTTP request routed through the shared ESI rate limiter."""
    limiter = get_esi_rate_limiter()
    return limiter.request(method, url, **kwargs)


def esi_get(url: str, **kwargs) -> requests.Response:
    return esi_request("GET", url, **kwargs)


def esi_post(url: str, **kwargs) -> requests.Response:
    return esi_request("POST", url, **kwargs)
