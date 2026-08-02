"""
Single-flight memoisation.

`functools.lru_cache` is thread-safe for its *dict*, but it deliberately does not hold
that lock across the wrapped call — so N threads that miss on the same key each execute
the function. That is fine for cheap functions and actively harmful for ours: FastAPI
runs sync `def` handlers in a threadpool, the Dashboard opens with ~12 concurrent
requests, and on a cold process every one of them independently parsed 12 MB of CSV and
rebuilt the same 20,000-row case view — serialised by the GIL onto a single worker.

`cached` is a drop-in replacement that holds a **per-key** lock across the computation,
so the first caller computes and the rest wait for its result. Per-key, not global: the
warm-up in app/warmup.py runs steps back to back, and a global lock would serialise
unrelated caches behind each other.

Deliberately not `lru_cache(maxsize=1)` + a module-level lock at each call site: there
are 15 such caches across firdata/datastore/routers, and one shared helper is the only
version that stays correct when someone adds the sixteenth.

Usage mirrors lru_cache::

    @cached()               # unbounded — for the fixed process-lifetime views
    def cases(): ...

    @cached(maxsize=32)     # bounded — keys include user-supplied query params
    def _cached_clusters(sub_head, eps_km, min_samples): ...
"""
from __future__ import annotations

import functools
import inspect
import threading
from collections import Counter, OrderedDict
from typing import Any, Callable


def cached(maxsize: int | None = None) -> Callable:
    """Memoise `fn`, collapsing concurrent misses on the same key into one computation.

    maxsize=None keeps every entry (the process-lifetime views: their keyspace is fixed
    and tiny). maxsize=N evicts least-recently-used — required wherever the key contains
    request-supplied values, so a caller can't grow the cache without bound.
    """

    def decorator(fn: Callable) -> Callable:
        signature = inspect.signature(fn)
        store: OrderedDict[Any, Any] = OrderedDict()
        locks: dict[Any, threading.Lock] = {}
        inflight: Counter = Counter()
        guard = threading.Lock()          # protects store/locks/inflight ONLY — never
        stats = {"hits": 0, "misses": 0}  # held across a call to fn

        def make_key(args: tuple, kwargs: dict) -> Any:
            """Normalise so cases(None) and cases(sub_head=None) share one entry."""
            bound = signature.bind(*args, **kwargs)
            bound.apply_defaults()
            return tuple(bound.arguments.items())

        def _lookup(key: Any) -> tuple[bool, Any]:
            """Caller must hold `guard`. Returns (found, value) and refreshes LRU order."""
            if key in store:
                stats["hits"] += 1
                store.move_to_end(key)
                return True, store[key]
            return False, None

        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            key = make_key(args, kwargs)

            with guard:
                found, value = _lookup(key)
                if found:
                    return value
                lock = locks.get(key)
                if lock is None:
                    lock = locks[key] = threading.Lock()
                inflight[key] += 1

            try:
                with lock:
                    # Re-check: another thread may have filled it while we queued here.
                    with guard:
                        found, value = _lookup(key)
                    if found:
                        return value

                    # fn runs OUTSIDE `guard` so other keys stay servable, and INSIDE
                    # `lock` so same-key callers wait instead of duplicating the work.
                    # An exception propagates without caching, and the lock is released
                    # — a failed warm step must not poison the cache or wedge callers.
                    value = fn(*args, **kwargs)

                    with guard:
                        stats["misses"] += 1
                        store[key] = value
                        store.move_to_end(key)
                        if maxsize is not None and len(store) > maxsize:
                            evicted, _ = store.popitem(last=False)
                            if not inflight[evicted]:
                                locks.pop(evicted, None)
                    return value
            finally:
                with guard:
                    inflight[key] -= 1
                    if inflight[key] <= 0:
                        del inflight[key]
                        if key not in store:
                            locks.pop(key, None)

        def cache_clear() -> None:
            with guard:
                store.clear()
                stats["hits"] = stats["misses"] = 0
                for key in [k for k in locks if not inflight[k]]:
                    locks.pop(key, None)

        def cache_info() -> dict[str, int]:
            with guard:
                return {"hits": stats["hits"], "misses": stats["misses"], "size": len(store)}

        def is_warm() -> bool:
            """True once anything has been computed — used by /health and /warm."""
            with guard:
                return bool(store)

        wrapper.cache_clear = cache_clear      # type: ignore[attr-defined]
        wrapper.cache_info = cache_info        # type: ignore[attr-defined]
        wrapper.is_warm = is_warm              # type: ignore[attr-defined]
        return wrapper

    return decorator
