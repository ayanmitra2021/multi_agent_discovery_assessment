"""
MCP Tool Hook Chain — pre/post interceptors for every MCPClient.call_tool() invocation.

Execution order:
  PRE  1. PreAuditHook           — log tool_call_start to ctx.audit_log
  PRE  2. InputNormalizationHook — lowercase csp, strip whitespace, lowercase list items
  PRE  3. CSPGuardHook           — reject invalid csp with structured JSON error
  PRE  4. ArgBoundsHook          — cap limit <= 10, list args <= 5 items
  PRE  5. CallBudgetHook         — short-circuit duplicate (tool, args) with cached result
  [tool call]
  POST 1. ErrorNormalizationHook — normalize exceptions to structured JSON
  POST 2. EmptyResultHook        — enrich [] results with a corrective hint
  POST 3. SizeLimiterHook        — truncate oversized payloads (list-level, not byte-level)
  POST 4. MetaEnrichHook         — append _latency_ms, _result_count, _called_at
  POST 5. PostAuditHook          — log tool_call_complete to ctx.audit_log

Ordering invariants (must be preserved):
  - CSPGuardHook fires after InputNormalizationHook so 'AWS' is lowercased before validation.
  - ErrorNormalizationHook is the first post-hook; it normalizes errors before others run.
  - SizeLimiterHook truncates at the record list level, not raw bytes, to preserve valid JSON.
  - CallBudgetHook key: (tool_name, sorted frozen args) — different args always pass through.
"""
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from ..agents.base import AssessmentContext

_VALID_CSPS: frozenset[str] = frozenset({"aws", "azure", "gcp"})
_MAX_LIMIT: int = 10
_MAX_LIST_LEN: int = 5
_MAX_RESULT_CHARS: int = 6_000
# Budget reserved for the {"_truncated": ..., "data": [...]} wrapper (~80 chars)
# plus MetaEnrichHook additions (_latency_ms, _called_at, _result_count, ~90 chars).
_TRUNCATION_OVERHEAD: int = 300


# ---------------------------------------------------------------------------
# HookContext
# ---------------------------------------------------------------------------

@dataclass
class HookContext:
    """Mutable state bag threaded through the hook chain for a single tool call."""

    tool_name: str
    args: dict                              # pre-hooks may mutate this
    assessment_id: str
    result: Optional[str] = None            # pre-hook sets to short-circuit; post-hooks read/write
    latency_ms: Optional[float] = None      # set by MCPClient after the tool call returns
    error: Optional[Exception] = None       # set by MCPClient if the tool call raised
    budget_cache_key: Optional[Any] = None  # internal: CallBudgetHook → PostAuditHook


# ---------------------------------------------------------------------------
# Pre-hook implementations
# ---------------------------------------------------------------------------

class PreAuditHook:
    """Emit tool_call_start to ctx.audit_log before the tool executes."""

    def __call__(self, ctx: AssessmentContext, hctx: HookContext) -> None:
        ctx.audit_log.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent": "MCPClient",
            "event": "tool_call_start",
            "tool": hctx.tool_name,
            "args": dict(hctx.args),
        })


class InputNormalizationHook:
    """Lowercase the csp arg, strip leading/trailing whitespace from all string args,
    and lowercase each string item within list args."""

    def __call__(self, ctx: AssessmentContext, hctx: HookContext) -> None:
        for key, val in list(hctx.args.items()):
            if isinstance(val, str):
                stripped = val.strip()
                hctx.args[key] = stripped.lower() if key == "csp" else stripped
            elif isinstance(val, list):
                hctx.args[key] = [
                    item.strip().lower() if isinstance(item, str) else item
                    for item in val
                ]


class CSPGuardHook:
    """Reject invalid CSP values with a structured JSON error the LLM can self-correct.
    Must execute after InputNormalizationHook so 'AWS' is already lowercased to 'aws'."""

    def __call__(self, ctx: AssessmentContext, hctx: HookContext) -> None:
        csp = hctx.args.get("csp")
        if csp is not None and csp not in _VALID_CSPS:
            hctx.result = json.dumps({
                "_error": (
                    f"Invalid csp value '{csp}'. "
                    f"Accepted values: {sorted(_VALID_CSPS)}. "
                    "Correct the csp argument and retry."
                ),
                "tool": hctx.tool_name,
                "recoverable": True,
            })


class ArgBoundsHook:
    """Cap the 'limit' argument to _MAX_LIMIT and truncate list args to _MAX_LIST_LEN."""

    def __call__(self, ctx: AssessmentContext, hctx: HookContext) -> None:
        if "limit" in hctx.args and isinstance(hctx.args["limit"], int):
            hctx.args["limit"] = min(hctx.args["limit"], _MAX_LIMIT)
        for key, val in list(hctx.args.items()):
            if isinstance(val, list) and len(val) > _MAX_LIST_LEN:
                hctx.args[key] = val[:_MAX_LIST_LEN]


class CallBudgetHook:
    """Short-circuit exact duplicate tool calls (same tool_name + same args) using a
    per-instance result cache. Different args to the same tool always pass through.

    Cache key: (tool_name, tuple of sorted (k, frozen_v) pairs).
    PostAuditHook stores the result in this cache after each successful first call.
    """

    def __init__(self) -> None:
        self._cache: dict[tuple, str] = {}

    def _make_key(self, tool_name: str, args: dict) -> tuple:
        def _freeze(v: Any) -> Any:
            if isinstance(v, list):
                return tuple(sorted(str(i) for i in v))
            return v

        frozen = tuple(sorted((k, _freeze(v)) for k, v in args.items()))
        return (tool_name, frozen)

    def __call__(self, ctx: AssessmentContext, hctx: HookContext) -> None:
        key = self._make_key(hctx.tool_name, hctx.args)
        cached = self._cache.get(key)
        if cached is not None:
            hctx.result = cached        # short-circuit: skip the actual tool call
        else:
            hctx.budget_cache_key = key  # signal PostAuditHook to store result on completion

    def store(self, key: tuple, result: str) -> None:
        """Called by PostAuditHook after a successful first call to populate the cache."""
        self._cache[key] = result


# ---------------------------------------------------------------------------
# Post-hook implementations
# ---------------------------------------------------------------------------

class ErrorNormalizationHook:
    """First post-hook. Converts any exception from the tool call into structured
    JSON so the LLM can reason about the failure rather than receiving a raw traceback."""

    def __call__(self, ctx: AssessmentContext, hctx: HookContext) -> None:
        if hctx.error is None:
            return
        recoverable = isinstance(hctx.error, (ConnectionError, OSError, TimeoutError))
        hctx.result = json.dumps({
            "_error": str(hctx.error),
            "tool": hctx.tool_name,
            "recoverable": recoverable,
        })


class EmptyResultHook:
    """Detect empty JSON arrays or objects and enrich with a corrective hint so the
    LLM knows to broaden filter parameters and retry rather than synthesizing nothing."""

    def __call__(self, ctx: AssessmentContext, hctx: HookContext) -> None:
        if not hctx.result:
            return
        try:
            parsed = json.loads(hctx.result)
        except (json.JSONDecodeError, ValueError):
            return
        if parsed == [] or parsed == {}:
            hctx.result = json.dumps({
                "_warning": (
                    f"Tool '{hctx.tool_name}' returned no results for the given filters. "
                    "Consider broadening or omitting optional filter parameters and retrying."
                ),
                "data": [],
            })


class SizeLimiterHook:
    """Truncate oversized result payloads. Truncation happens at the record list level —
    never by slicing raw bytes — to guarantee the output remains valid JSON.
    Uses binary search to find the largest N records that fit within _MAX_RESULT_CHARS."""

    def __call__(self, ctx: AssessmentContext, hctx: HookContext) -> None:
        if not hctx.result or len(hctx.result) <= _MAX_RESULT_CHARS:
            return
        try:
            records = json.loads(hctx.result)
        except (json.JSONDecodeError, ValueError):
            return
        if not isinstance(records, list):
            return

        total = len(records)
        # Use an effective limit that leaves room for the dict wrapper keys and
        # the metadata fields MetaEnrichHook appends after this hook runs.
        effective_limit = max(0, _MAX_RESULT_CHARS - _TRUNCATION_OVERHEAD)
        lo, hi = 0, total
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if len(json.dumps(records[:mid])) <= effective_limit:
                lo = mid
            else:
                hi = mid - 1

        hctx.result = json.dumps({
            "_truncated": True,
            "_total_records": total,
            "_returned_records": lo,
            "data": records[:lo],
        })


class MetaEnrichHook:
    """Append _latency_ms, _result_count, and _called_at to every successful response.
    Bare list results are wrapped in {"data": [...]} for consistency with truncated results."""

    def __call__(self, ctx: AssessmentContext, hctx: HookContext) -> None:
        if not hctx.result or hctx.error is not None:
            return
        try:
            parsed = json.loads(hctx.result)
        except (json.JSONDecodeError, ValueError):
            return

        meta: dict[str, Any] = {
            "_latency_ms": round(hctx.latency_ms, 2) if hctx.latency_ms is not None else None,
            "_called_at": datetime.now(timezone.utc).isoformat(),
        }

        if isinstance(parsed, list):
            meta["_result_count"] = len(parsed)
            hctx.result = json.dumps({"data": parsed, **meta})
        elif isinstance(parsed, dict):
            if "data" in parsed and isinstance(parsed["data"], list):
                meta["_result_count"] = len(parsed["data"])
            parsed.update(meta)
            hctx.result = json.dumps(parsed)


class PostAuditHook:
    """Emit tool_call_complete to ctx.audit_log with outcome, latency, and record count.
    Also populates the CallBudgetHook cache after the first successful call."""

    def __init__(self, budget_hook: Optional[CallBudgetHook] = None) -> None:
        self._budget_hook = budget_hook

    def __call__(self, ctx: AssessmentContext, hctx: HookContext) -> None:
        outcome = "error"
        record_count: Optional[int] = None

        if hctx.result:
            try:
                parsed = json.loads(hctx.result)
                if isinstance(parsed, list):
                    outcome = "success"
                    record_count = len(parsed)
                elif isinstance(parsed, dict):
                    if "_error" in parsed:
                        outcome = "error"
                    elif "_warning" in parsed:
                        outcome = "empty"
                    elif parsed.get("_truncated"):
                        outcome = "truncated"
                    else:
                        outcome = "success"
                    data = parsed.get("data")
                    if isinstance(data, list):
                        record_count = len(data)
            except (json.JSONDecodeError, ValueError):
                outcome = "success"
        elif hctx.error is None:
            outcome = "success"

        ctx.audit_log.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent": "MCPClient",
            "event": "tool_call_complete",
            "tool": hctx.tool_name,
            "outcome": outcome,
            "latency_ms": round(hctx.latency_ms, 2) if hctx.latency_ms is not None else None,
            "record_count": record_count,
        })

        if (
            self._budget_hook is not None
            and hctx.budget_cache_key is not None
            and outcome in ("success", "empty", "truncated")
            and hctx.result
        ):
            self._budget_hook.store(hctx.budget_cache_key, hctx.result)


# ---------------------------------------------------------------------------
# Hook chain
# ---------------------------------------------------------------------------

@dataclass
class HookChain:
    pre_hooks: list
    post_hooks: list

    def execute_pre(self, ctx: AssessmentContext, hctx: HookContext) -> bool:
        """Run pre-hooks in order. Returns False (short-circuited) if any hook sets hctx.result."""
        for hook in self.pre_hooks:
            hook(ctx, hctx)
            if hctx.result is not None:
                return False
        return True

    def execute_post(self, ctx: AssessmentContext, hctx: HookContext) -> None:
        """Run all post-hooks in order."""
        for hook in self.post_hooks:
            hook(ctx, hctx)


def build_default_hook_chain() -> HookChain:
    """Construct the production hook chain with all 10 hooks in the documented order."""
    budget_hook = CallBudgetHook()
    return HookChain(
        pre_hooks=[
            PreAuditHook(),
            InputNormalizationHook(),
            CSPGuardHook(),
            ArgBoundsHook(),
            budget_hook,
        ],
        post_hooks=[
            ErrorNormalizationHook(),
            EmptyResultHook(),
            SizeLimiterHook(),
            MetaEnrichHook(),
            PostAuditHook(budget_hook=budget_hook),
        ],
    )
