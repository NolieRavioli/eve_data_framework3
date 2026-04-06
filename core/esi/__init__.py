"""ESI access — the only way to make ESI HTTP requests.

All outbound ESI communication goes through esi_get / esi_post / esi_request.
These functions handle rate limiting, caching, ETag revalidation, and error
classification automatically.

Internal modules (rate.py, cache.py) are not re-exported — they are
implementation details of the request pipeline.
"""

from core.esi.request import esi_get, esi_post, esi_request

__all__ = ["esi_get", "esi_post", "esi_request"]