"""
Unit tests for services/cache.py — the single-flight cache.

Why this module exists at all is the thing worth testing: `functools.lru_cache` does
NOT hold its lock across the wrapped call, so N threads that miss on the same key each
run the function. On a cold container the Dashboard fires ~12 requests at once and every
one of them independently rebuilt the same 20,000-row case view. `test_lru_cache_...`
below pins that stdlib behaviour down so the reason for `cached` stays legible; the rest
assert that `cached` collapses those N computations into one.
"""
from __future__ import annotations

import threading
import time
from functools import lru_cache

from app.services.cache import cached

THREADS = 12
WORK_S = 0.2


def _counting(fn_cache):
    """Return (wrapped, calls) where `wrapped` sleeps and counts its real invocations."""
    calls = []
    lock = threading.Lock()

    @fn_cache
    def build(key: str = "x") -> str:
        with lock:
            calls.append(key)
        time.sleep(WORK_S)
        return f"built:{key}"

    return build, calls


def _hammer(fn, n=THREADS, *args):
    """Fire `n` threads at `fn` simultaneously (barrier-synchronised) and return results."""
    barrier = threading.Barrier(n)
    results: list = [None] * n

    def worker(i):
        barrier.wait()          # every thread arrives before any of them calls fn
        results[i] = fn(*args)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return results


# ------------------------------------------------- the behaviour we're replacing ----
def test_lru_cache_duplicates_work_under_concurrent_misses():
    """Documents the root cause. lru_cache releases its lock across the wrapped call,
    so simultaneous misses all compute. If CPython ever changes this, we want to know."""
    build, calls = _counting(lru_cache(maxsize=None))
    _hammer(build)
    assert len(calls) > 1, "expected lru_cache to duplicate work under concurrent misses"


# ------------------------------------------------------------------ single-flight ----
def test_concurrent_misses_compute_once():
    build, calls = _counting(cached())
    results = _hammer(build)
    assert len(calls) == 1, f"expected exactly 1 computation, got {len(calls)}"
    assert results == ["built:x"] * THREADS


def test_concurrent_misses_wait_rather_than_duplicate():
    """All 12 callers should finish in roughly ONE unit of work, not 12."""
    build, _ = _counting(cached())
    start = time.perf_counter()
    _hammer(build)
    elapsed = time.perf_counter() - start
    assert elapsed < WORK_S * 3, f"took {elapsed:.2f}s — callers are not sharing the result"


def test_distinct_keys_do_not_block_each_other():
    """The per-key lock must not be a global lock: two different keys computed at the
    same time must overlap, or warm-up would serialise every step behind every other."""
    build, calls = _counting(cached())
    start = time.perf_counter()
    threads = [threading.Thread(target=build, args=(k,)) for k in ("a", "b")]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    elapsed = time.perf_counter() - start
    assert sorted(calls) == ["a", "b"]
    assert elapsed < WORK_S * 2, f"took {elapsed:.2f}s — distinct keys are serialised"


def test_caches_per_argument():
    build, calls = _counting(cached())
    assert build("a") == "built:a"
    assert build("b") == "built:b"
    assert build("a") == "built:a"
    assert calls == ["a", "b"]


def test_zero_arg_function_is_cached():
    calls = []

    @cached()
    def view():
        calls.append(1)
        return {"rows": 3}

    assert view() is view()          # identity: same object, not a recomputed equal one
    assert len(calls) == 1


def test_kwargs_and_positional_share_a_key():
    """cases(sub_head=None) and cases(None) are the same call and must share one entry."""
    calls = []

    @cached()
    def build(a, b=2):
        calls.append((a, b))
        return a + b

    assert build(1) == 3
    assert build(1, 2) == 3
    assert build(a=1, b=2) == 3
    assert len(calls) == 1


# ------------------------------------------------------------------------ bounds ----
def test_maxsize_evicts_least_recently_used():
    """_cached_clusters is keyed on user-supplied eps/min_samples, so it must stay
    bounded or a caller can grow it without limit."""
    calls = []

    @cached(maxsize=2)
    def build(k):
        calls.append(k)
        return k

    build("a")
    build("b")
    build("a")        # refresh 'a' so 'b' is now the least-recently-used
    build("c")        # evicts 'b'
    assert build("a") == "a"
    assert len(calls) == 3, "'a' should still be cached"
    build("b")
    assert len(calls) == 4, "'b' should have been evicted"


def test_maxsize_none_is_unbounded():
    build, calls = _counting(cached())
    for i in range(50):
        build(str(i))
    assert len(calls) == 50
    assert build.cache_info()["size"] == 50


# -------------------------------------------------------------------- lifecycle ----
def test_exception_is_not_cached_and_releases_the_lock():
    """A failed warm step must not poison the cache or deadlock later callers."""
    state = {"fail": True}
    calls = []

    @cached()
    def build():
        calls.append(1)
        if state["fail"]:
            raise ValueError("boom")
        return "ok"

    try:
        build()
        raise AssertionError("expected ValueError")
    except ValueError:
        pass

    state["fail"] = False
    assert build() == "ok"           # would hang or return stale if the lock leaked
    assert len(calls) == 2


def test_cache_clear_resets():
    build, calls = _counting(cached())
    build()
    build.cache_clear()
    build()
    assert len(calls) == 2
    assert build.cache_info()["size"] == 1


def test_cache_info_counts_hits_and_misses():
    build, _ = _counting(cached())
    build("a")
    build("a")
    build("b")
    info = build.cache_info()
    assert info["misses"] == 2
    assert info["hits"] == 1
    assert info["size"] == 2


def test_preserves_function_metadata():
    @cached()
    def documented(x):
        """Docstring survives."""
        return x

    assert documented.__name__ == "documented"
    assert documented.__doc__ == "Docstring survives."


def test_works_on_methods():
    """LocalCsvStore.rows is a cached *method* — `self` becomes part of the key."""
    calls = []

    class Store:
        @cached()
        def rows(self, table):
            calls.append(table)
            return [table]

    a, b = Store(), Store()
    a.rows("CaseMaster")
    a.rows("CaseMaster")
    assert calls == ["CaseMaster"]
    b.rows("CaseMaster")             # different instance -> different key
    assert calls == ["CaseMaster", "CaseMaster"]
