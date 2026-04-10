"""In-memory buffer for market orders during region refreshes.

While a region is being refreshed from ESI, its orders accumulate here and
are immediately queryable via :func:`try_market_price`.  Once all pages for
a region arrive, :func:`finish_region` flushes the complete set to DuckDB
via ``replace_market_orders_for_region()`` (DELETE + vectorised INSERT) and
clears the buffer.

During the flush the buffer continues to serve reads — it is only cleared
after the DuckDB write commits successfully.

Thread safety
-------------
All access is serialised by a single ``threading.Lock``.  The lock is held
briefly during reads (~10–50 ms worst-case for a 400 k-order region scan)
and for O(1) mutations (begin / pop).

Memory
------
~150 bytes per order dict.  A large region (400 k orders) ≈ 60 MB.
Typically only 1–2 regions are buffered simultaneously → 10–40 MB.
"""

import logging
import threading

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_regions: dict[int, list[dict]] = {}  # region_id → accumulated ESI order dicts
_cache_hits: int = 0
_cache_misses: int = 0


def get_cache_stats() -> dict:
    """Return buffer cache hit/miss counters."""
    with _lock:
        return {"cache_hits": _cache_hits, "cache_misses": _cache_misses}


# ── Lifecycle ──────────────────────────────────────────────────────────────────

def begin_region(region_id: int) -> None:
    """Start buffering orders for *region_id*.  Clears any stale buffer."""
    with _lock:
        _regions[region_id] = []


def add_page(region_id: int, orders: list[dict]) -> None:
    """Append a page of ESI order dicts to the buffer."""
    with _lock:
        buf = _regions.get(region_id)
        if buf is not None:
            buf.extend(orders)


def finish_region(region_id: int) -> int:
    """Flush buffered orders to DuckDB and clear the buffer.

    The buffer remains readable during the DuckDB write so that concurrent
    queries still see fresh data.  The buffer entry is removed only after
    the write commits (or on failure, so stale data doesn't persist).

    Returns the number of rows written.
    """
    with _lock:
        rows = _regions.get(region_id)
        if rows is None:
            return 0
    from core.db.public import replace_market_orders_for_region
    try:
        count = replace_market_orders_for_region(region_id, rows)
    except Exception:
        with _lock:
            _regions.pop(region_id, None)
        raise
    with _lock:
        _regions.pop(region_id, None)
    logger.debug("[market_buffer] flushed %d orders for region %s", count, region_id)
    return count


def discard_region(region_id: int) -> None:
    """Drop buffered orders for *region_id* without flushing to disk."""
    with _lock:
        _regions.pop(region_id, None)


# ── Query helpers ──────────────────────────────────────────────────────────────

def is_buffered(region_id: int) -> bool:
    """Return True if *region_id* is currently being buffered."""
    with _lock:
        return region_id in _regions


def buffered_region_ids() -> set[int]:
    """Return the set of region IDs currently in the buffer."""
    with _lock:
        return set(_regions)


def try_market_price(
    type_id: int,
    region_id: int,
    buy: bool,
) -> tuple[bool, float | None]:
    """Look up a market price from the buffer.

    Returns ``(True, price)`` if the region is buffered (*price* may be
    ``None`` when no matching orders exist).  Returns ``(False, None)`` if
    the region is **not** buffered — the caller should fall through to DuckDB.
    """
    global _cache_hits, _cache_misses
    with _lock:
        buf = _regions.get(region_id)
        if buf is None:
            _cache_misses += 1
            return False, None
        _cache_hits += 1
        if buy:
            prices = [o["price"] for o in buf
                      if o.get("type_id") == type_id and o.get("is_buy_order")]
        else:
            prices = [o["price"] for o in buf
                      if o.get("type_id") == type_id and not o.get("is_buy_order")]
    if not prices:
        return True, None
    return True, max(prices) if buy else min(prices)


def query_orders(type_id: int, region_id: int = 0) -> tuple[bool, list[dict]]:
    """Query buffered orders matching *type_id* and optionally *region_id*.

    If *region_id* is non-zero and that region is buffered, returns
    ``(True, matching_orders)``.

    If *region_id* is ``0`` (universe) and **any** region is buffered,
    returns ``(True, matching_orders_across_all_buffered_regions)``.
    The caller must merge these with a DuckDB query that excludes the
    buffered region IDs.

    Returns ``(False, [])`` when no relevant region is buffered.
    """
    with _lock:
        if region_id:
            buf = _regions.get(region_id)
            if buf is None:
                return False, []
            matches = [o for o in buf if o.get("type_id") == type_id]
        else:
            if not _regions:
                return False, []
            matches = []
            for buf in _regions.values():
                matches.extend(o for o in buf if o.get("type_id") == type_id)
    # Normalise ESI dict keys to the shape _query_orders expects.
    out = []
    for o in matches:
        out.append({
            "order_id": o.get("order_id"),
            "is_buy_order": bool(o.get("is_buy_order")),
            "price": o.get("price"),
            "volume_remain": o.get("volume_remain"),
            "volume_total": o.get("volume_total"),
            "range": o.get("order_range") or o.get("range", ""),
            "location_id": o.get("location_id"),
            "issued": o.get("issued"),
            "duration": o.get("duration"),
            "min_volume": o.get("min_volume"),
            "location_name": str(o.get("location_id", "")),
        })
    return True, out
