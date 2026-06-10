"""
Unit tests for the MCP tool hook chain (app/mcp/hooks.py).

Each hook is tested in isolation with a minimal AssessmentContext and a
factory-built HookContext. A dedicated ordering test verifies that the
hook chain invokes hooks in the exact sequence documented in hooks.py.

No network, no subprocess, no LLM calls.
"""
import json
from unittest.mock import MagicMock

import pytest

from app.agents.base import AssessmentContext
from app.mcp.hooks import (
    ArgBoundsHook,
    CallBudgetHook,
    CSPGuardHook,
    EmptyResultHook,
    ErrorNormalizationHook,
    HookChain,
    HookContext,
    InputNormalizationHook,
    MetaEnrichHook,
    PostAuditHook,
    PreAuditHook,
    SizeLimiterHook,
    _MAX_LIMIT,
    _MAX_LIST_LEN,
    _MAX_RESULT_CHARS,
    _TRUNCATION_OVERHEAD,
    build_default_hook_chain,
)
from app.schemas.discovery import ParsedDocument
from app.schemas.enums import CSP


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def ctx() -> AssessmentContext:
    doc = ParsedDocument(
        filename="test.pdf",
        content_type="application/pdf",
        text_blocks=["test content"],
        table_blocks=[],
    )
    return AssessmentContext.create(
        document=doc,
        target_csp=CSP.aws,
        enable_multi_agent=True,
    )


def make_hctx(
    tool_name: str = "get_policies",
    args: dict | None = None,
    result: str | None = None,
    error: Exception | None = None,
    latency_ms: float | None = None,
) -> HookContext:
    return HookContext(
        tool_name=tool_name,
        args=args if args is not None else {"csp": "aws"},
        assessment_id="test-session-id",
        result=result,
        error=error,
        latency_ms=latency_ms,
    )


# ---------------------------------------------------------------------------
# PreAuditHook
# ---------------------------------------------------------------------------

class TestPreAuditHook:
    def test_appends_tool_call_start_event(self, ctx):
        hook = PreAuditHook()
        hctx = make_hctx(tool_name="get_policies", args={"csp": "aws"})
        hook(ctx, hctx)
        assert len(ctx.audit_log) == 1
        entry = ctx.audit_log[0]
        assert entry["event"] == "tool_call_start"
        assert entry["agent"] == "MCPClient"
        assert entry["tool"] == "get_policies"
        assert entry["args"] == {"csp": "aws"}

    def test_does_not_short_circuit(self, ctx):
        hook = PreAuditHook()
        hctx = make_hctx()
        hook(ctx, hctx)
        assert hctx.result is None

    def test_timestamp_is_present(self, ctx):
        hook = PreAuditHook()
        hctx = make_hctx()
        hook(ctx, hctx)
        assert "timestamp" in ctx.audit_log[0]


# ---------------------------------------------------------------------------
# InputNormalizationHook
# ---------------------------------------------------------------------------

class TestInputNormalizationHook:
    def test_lowercases_csp(self, ctx):
        hook = InputNormalizationHook()
        hctx = make_hctx(args={"csp": "AWS"})
        hook(ctx, hctx)
        assert hctx.args["csp"] == "aws"

    def test_strips_whitespace_from_csp(self, ctx):
        hook = InputNormalizationHook()
        hctx = make_hctx(args={"csp": "  aws  "})
        hook(ctx, hctx)
        assert hctx.args["csp"] == "aws"

    def test_strips_whitespace_from_string_arg(self, ctx):
        hook = InputNormalizationHook()
        hctx = make_hctx(args={"csp": "aws", "keywords": "  Oracle  "})
        hook(ctx, hctx)
        assert hctx.args["keywords"] == "Oracle"

    def test_does_not_lowercase_non_csp_string(self, ctx):
        hook = InputNormalizationHook()
        hctx = make_hctx(args={"csp": "aws", "keywords": "Oracle DB"})
        hook(ctx, hctx)
        assert hctx.args["keywords"] == "Oracle DB"

    def test_lowercases_list_items(self, ctx):
        hook = InputNormalizationHook()
        hctx = make_hctx(args={"csp": "aws", "categories": ["Security", "NETWORKING"]})
        hook(ctx, hctx)
        assert hctx.args["categories"] == ["security", "networking"]

    def test_strips_whitespace_in_list_items(self, ctx):
        hook = InputNormalizationHook()
        hctx = make_hctx(args={"csp": "aws", "capability_tags": [" containers ", "SERVERLESS"]})
        hook(ctx, hctx)
        assert hctx.args["capability_tags"] == ["containers", "serverless"]

    def test_does_not_short_circuit(self, ctx):
        hook = InputNormalizationHook()
        hctx = make_hctx(args={"csp": "AWS"})
        hook(ctx, hctx)
        assert hctx.result is None

    def test_non_string_list_items_passed_through(self, ctx):
        hook = InputNormalizationHook()
        hctx = make_hctx(args={"csp": "aws", "ids": [1, 2, 3]})
        hook(ctx, hctx)
        assert hctx.args["ids"] == [1, 2, 3]


# ---------------------------------------------------------------------------
# CSPGuardHook
# ---------------------------------------------------------------------------

class TestCSPGuardHook:
    def test_blocks_unknown_csp(self, ctx):
        hook = CSPGuardHook()
        hctx = make_hctx(args={"csp": "amazon"})
        hook(ctx, hctx)
        assert hctx.result is not None
        payload = json.loads(hctx.result)
        assert "_error" in payload
        assert payload["recoverable"] is True
        assert payload["tool"] == "get_policies"

    def test_error_message_names_invalid_value(self, ctx):
        hook = CSPGuardHook()
        hctx = make_hctx(args={"csp": "oracle-cloud"})
        hook(ctx, hctx)
        payload = json.loads(hctx.result)
        assert "oracle-cloud" in payload["_error"]

    def test_accepts_aws(self, ctx):
        hook = CSPGuardHook()
        hctx = make_hctx(args={"csp": "aws"})
        hook(ctx, hctx)
        assert hctx.result is None

    def test_accepts_azure(self, ctx):
        hook = CSPGuardHook()
        hctx = make_hctx(args={"csp": "azure"})
        hook(ctx, hctx)
        assert hctx.result is None

    def test_accepts_gcp(self, ctx):
        hook = CSPGuardHook()
        hctx = make_hctx(args={"csp": "gcp"})
        hook(ctx, hctx)
        assert hctx.result is None

    def test_no_csp_arg_passes_through(self, ctx):
        hook = CSPGuardHook()
        hctx = make_hctx(args={"jurisdiction": "EU"})
        hook(ctx, hctx)
        assert hctx.result is None

    def test_uppercase_rejected_confirming_must_run_after_normalization(self, ctx):
        hook = CSPGuardHook()
        hctx = make_hctx(args={"csp": "AWS"})   # not yet normalized
        hook(ctx, hctx)
        assert hctx.result is not None           # CSPGuardHook must see lowercase input

    def test_normalization_then_guard_accepts_uppercase(self, ctx):
        norm = InputNormalizationHook()
        guard = CSPGuardHook()
        hctx = make_hctx(args={"csp": "AWS"})
        norm(ctx, hctx)
        guard(ctx, hctx)
        assert hctx.result is None               # normalized first → guard accepts


# ---------------------------------------------------------------------------
# ArgBoundsHook
# ---------------------------------------------------------------------------

class TestArgBoundsHook:
    def test_caps_limit_at_max(self, ctx):
        hook = ArgBoundsHook()
        hctx = make_hctx(args={"csp": "aws", "limit": 100})
        hook(ctx, hctx)
        assert hctx.args["limit"] == _MAX_LIMIT

    def test_allows_limit_at_max(self, ctx):
        hook = ArgBoundsHook()
        hctx = make_hctx(args={"csp": "aws", "limit": _MAX_LIMIT})
        hook(ctx, hctx)
        assert hctx.args["limit"] == _MAX_LIMIT

    def test_allows_limit_below_max(self, ctx):
        hook = ArgBoundsHook()
        hctx = make_hctx(args={"csp": "aws", "limit": 3})
        hook(ctx, hctx)
        assert hctx.args["limit"] == 3

    def test_truncates_overlong_list_arg(self, ctx):
        hook = ArgBoundsHook()
        long_list = ["a", "b", "c", "d", "e", "f", "g"]
        hctx = make_hctx(args={"csp": "aws", "categories": long_list})
        hook(ctx, hctx)
        assert len(hctx.args["categories"]) == _MAX_LIST_LEN
        assert hctx.args["categories"] == long_list[:_MAX_LIST_LEN]

    def test_allows_list_at_max_length(self, ctx):
        hook = ArgBoundsHook()
        hctx = make_hctx(args={"csp": "aws", "categories": ["a"] * _MAX_LIST_LEN})
        hook(ctx, hctx)
        assert len(hctx.args["categories"]) == _MAX_LIST_LEN

    def test_no_limit_arg_passes_through(self, ctx):
        hook = ArgBoundsHook()
        hctx = make_hctx(args={"csp": "aws"})
        hook(ctx, hctx)
        assert "limit" not in hctx.args

    def test_does_not_short_circuit(self, ctx):
        hook = ArgBoundsHook()
        hctx = make_hctx(args={"csp": "aws", "limit": 999})
        hook(ctx, hctx)
        assert hctx.result is None


# ---------------------------------------------------------------------------
# CallBudgetHook
# ---------------------------------------------------------------------------

class TestCallBudgetHook:
    def test_first_call_passes_through(self, ctx):
        hook = CallBudgetHook()
        hctx = make_hctx(args={"csp": "aws"})
        hook(ctx, hctx)
        assert hctx.result is None
        assert hctx.budget_cache_key is not None

    def test_second_identical_call_short_circuits(self, ctx):
        hook = CallBudgetHook()
        cached_result = json.dumps([{"policy": "test"}])
        first = make_hctx(args={"csp": "aws"})
        hook(ctx, first)
        hook.store(first.budget_cache_key, cached_result)

        second = make_hctx(args={"csp": "aws"})
        hook(ctx, second)
        assert second.result == cached_result

    def test_different_args_pass_through(self, ctx):
        hook = CallBudgetHook()
        cached_result = json.dumps([{"policy": "test"}])
        first = make_hctx(args={"csp": "aws"})
        hook(ctx, first)
        hook.store(first.budget_cache_key, cached_result)

        second = make_hctx(args={"csp": "azure"})
        hook(ctx, second)
        assert second.result is None

    def test_same_tool_different_categories_passes_through(self, ctx):
        hook = CallBudgetHook()
        cached_result = json.dumps([{"policy": "test"}])
        first = make_hctx(args={"csp": "aws", "categories": ["security"]})
        hook(ctx, first)
        hook.store(first.budget_cache_key, cached_result)

        second = make_hctx(args={"csp": "aws", "categories": ["networking"]})
        hook(ctx, second)
        assert second.result is None

    def test_cache_key_set_on_miss(self, ctx):
        hook = CallBudgetHook()
        hctx = make_hctx(args={"csp": "aws", "limit": 5})
        hook(ctx, hctx)
        assert hctx.budget_cache_key is not None

    def test_budget_cache_key_none_on_hit(self, ctx):
        hook = CallBudgetHook()
        first = make_hctx(args={"csp": "aws"})
        hook(ctx, first)
        hook.store(first.budget_cache_key, '[]')

        second = make_hctx(args={"csp": "aws"})
        hook(ctx, second)
        assert second.budget_cache_key is None  # was not set because it was a cache hit


# ---------------------------------------------------------------------------
# ErrorNormalizationHook
# ---------------------------------------------------------------------------

class TestErrorNormalizationHook:
    def test_converts_exception_to_json(self, ctx):
        hook = ErrorNormalizationHook()
        hctx = make_hctx(error=RuntimeError("DB connection failed"))
        hook(ctx, hctx)
        payload = json.loads(hctx.result)
        assert "_error" in payload
        assert "DB connection failed" in payload["_error"]
        assert payload["tool"] == "get_policies"

    def test_connection_error_is_recoverable(self, ctx):
        hook = ErrorNormalizationHook()
        hctx = make_hctx(error=ConnectionError("timeout"))
        hook(ctx, hctx)
        assert json.loads(hctx.result)["recoverable"] is True

    def test_runtime_error_is_not_recoverable(self, ctx):
        hook = ErrorNormalizationHook()
        hctx = make_hctx(error=RuntimeError("schema mismatch"))
        hook(ctx, hctx)
        assert json.loads(hctx.result)["recoverable"] is False

    def test_no_error_leaves_result_unchanged(self, ctx):
        hook = ErrorNormalizationHook()
        hctx = make_hctx(result='[{"policy": "test"}]')
        hook(ctx, hctx)
        assert json.loads(hctx.result) == [{"policy": "test"}]

    def test_no_error_no_result_no_change(self, ctx):
        hook = ErrorNormalizationHook()
        hctx = make_hctx()
        hook(ctx, hctx)
        assert hctx.result is None


# ---------------------------------------------------------------------------
# EmptyResultHook
# ---------------------------------------------------------------------------

class TestEmptyResultHook:
    def test_enriches_empty_list(self, ctx):
        hook = EmptyResultHook()
        hctx = make_hctx(result="[]")
        hook(ctx, hctx)
        payload = json.loads(hctx.result)
        assert "_warning" in payload
        assert payload["data"] == []
        assert "get_policies" in payload["_warning"]

    def test_enriches_empty_object(self, ctx):
        hook = EmptyResultHook()
        hctx = make_hctx(result="{}")
        hook(ctx, hctx)
        payload = json.loads(hctx.result)
        assert "_warning" in payload

    def test_non_empty_list_unchanged(self, ctx):
        hook = EmptyResultHook()
        result = json.dumps([{"id": 1}])
        hctx = make_hctx(result=result)
        hook(ctx, hctx)
        assert json.loads(hctx.result) == [{"id": 1}]

    def test_no_result_no_change(self, ctx):
        hook = EmptyResultHook()
        hctx = make_hctx(result=None)
        hook(ctx, hctx)
        assert hctx.result is None

    def test_invalid_json_no_change(self, ctx):
        hook = EmptyResultHook()
        hctx = make_hctx(result="not json")
        hook(ctx, hctx)
        assert hctx.result == "not json"


# ---------------------------------------------------------------------------
# SizeLimiterHook
# ---------------------------------------------------------------------------

def _make_large_result(n_records: int = 200) -> str:
    records = [{"policy": f"POL-{i:03d}", "description": "x" * 50} for i in range(n_records)]
    return json.dumps(records)


class TestSizeLimiterHook:
    def test_small_result_unchanged(self, ctx):
        hook = SizeLimiterHook()
        result = json.dumps([{"id": 1}])
        hctx = make_hctx(result=result)
        hook(ctx, hctx)
        assert json.loads(hctx.result) == [{"id": 1}]

    def test_large_result_is_truncated(self, ctx):
        hook = SizeLimiterHook()
        hctx = make_hctx(result=_make_large_result(200))
        hook(ctx, hctx)
        payload = json.loads(hctx.result)
        assert payload["_truncated"] is True
        assert payload["_total_records"] == 200
        assert payload["_returned_records"] < 200

    def test_truncated_result_is_valid_json(self, ctx):
        hook = SizeLimiterHook()
        hctx = make_hctx(result=_make_large_result(200))
        hook(ctx, hctx)
        # Must not raise
        parsed = json.loads(hctx.result)
        assert isinstance(parsed, dict)

    def test_truncated_result_fits_within_limit(self, ctx):
        hook = SizeLimiterHook()
        hctx = make_hctx(result=_make_large_result(200))
        hook(ctx, hctx)
        # SizeLimiterHook reserves _TRUNCATION_OVERHEAD for the dict wrapper and
        # downstream MetaEnrichHook additions; full result must stay within budget.
        assert len(hctx.result) <= _MAX_RESULT_CHARS

    def test_non_list_result_unchanged(self, ctx):
        hook = SizeLimiterHook()
        result = json.dumps({"_warning": "no results", "data": []})
        hctx = make_hctx(result=result)
        hook(ctx, hctx)
        assert json.loads(hctx.result)["_warning"] == "no results"

    def test_total_and_returned_records_accurate(self, ctx):
        hook = SizeLimiterHook()
        hctx = make_hctx(result=_make_large_result(200))
        hook(ctx, hctx)
        payload = json.loads(hctx.result)
        assert len(payload["data"]) == payload["_returned_records"]
        assert payload["_total_records"] == 200

    def test_none_result_no_change(self, ctx):
        hook = SizeLimiterHook()
        hctx = make_hctx(result=None)
        hook(ctx, hctx)
        assert hctx.result is None


# ---------------------------------------------------------------------------
# MetaEnrichHook
# ---------------------------------------------------------------------------

class TestMetaEnrichHook:
    def test_wraps_list_result(self, ctx):
        hook = MetaEnrichHook()
        hctx = make_hctx(result=json.dumps([{"id": 1}, {"id": 2}]), latency_ms=42.5)
        hook(ctx, hctx)
        payload = json.loads(hctx.result)
        assert "data" in payload
        assert payload["data"] == [{"id": 1}, {"id": 2}]
        assert payload["_result_count"] == 2
        assert payload["_latency_ms"] == 42.5
        assert "_called_at" in payload

    def test_extends_dict_result(self, ctx):
        hook = MetaEnrichHook()
        hctx = make_hctx(
            result=json.dumps({"_truncated": True, "data": [{"id": 1}]}),
            latency_ms=10.0,
        )
        hook(ctx, hctx)
        payload = json.loads(hctx.result)
        assert payload["_truncated"] is True
        assert payload["_result_count"] == 1
        assert payload["_latency_ms"] == 10.0

    def test_skips_when_error_present(self, ctx):
        hook = MetaEnrichHook()
        hctx = make_hctx(result='[{"id": 1}]', error=RuntimeError("oops"))
        hook(ctx, hctx)
        assert json.loads(hctx.result) == [{"id": 1}]  # unchanged

    def test_no_result_no_change(self, ctx):
        hook = MetaEnrichHook()
        hctx = make_hctx(result=None, latency_ms=5.0)
        hook(ctx, hctx)
        assert hctx.result is None

    def test_latency_rounded_to_two_decimals(self, ctx):
        hook = MetaEnrichHook()
        hctx = make_hctx(result=json.dumps([{"id": 1}]), latency_ms=123.456789)
        hook(ctx, hctx)
        payload = json.loads(hctx.result)
        assert payload["_latency_ms"] == 123.46


# ---------------------------------------------------------------------------
# PostAuditHook
# ---------------------------------------------------------------------------

class TestPostAuditHook:
    def test_appends_tool_call_complete_event(self, ctx):
        hook = PostAuditHook()
        hctx = make_hctx(result=json.dumps([{"id": 1}]), latency_ms=50.0)
        hook(ctx, hctx)
        entry = ctx.audit_log[-1]
        assert entry["event"] == "tool_call_complete"
        assert entry["agent"] == "MCPClient"
        assert entry["tool"] == "get_policies"

    def test_outcome_success_for_list_result(self, ctx):
        hook = PostAuditHook()
        hctx = make_hctx(result=json.dumps([{"id": 1}]), latency_ms=10.0)
        hook(ctx, hctx)
        assert ctx.audit_log[-1]["outcome"] == "success"

    def test_outcome_error_for_error_result(self, ctx):
        hook = PostAuditHook()
        hctx = make_hctx(
            result=json.dumps({"_error": "DB down", "tool": "get_policies", "recoverable": True}),
            latency_ms=5.0,
        )
        hook(ctx, hctx)
        assert ctx.audit_log[-1]["outcome"] == "error"

    def test_outcome_empty_for_warning_result(self, ctx):
        hook = PostAuditHook()
        hctx = make_hctx(
            result=json.dumps({"_warning": "no results", "data": []}),
            latency_ms=5.0,
        )
        hook(ctx, hctx)
        assert ctx.audit_log[-1]["outcome"] == "empty"

    def test_outcome_truncated_for_truncated_result(self, ctx):
        hook = PostAuditHook()
        hctx = make_hctx(
            result=json.dumps({"_truncated": True, "_total_records": 50, "_returned_records": 10, "data": [{"id": i} for i in range(10)]}),
            latency_ms=30.0,
        )
        hook(ctx, hctx)
        assert ctx.audit_log[-1]["outcome"] == "truncated"

    def test_record_count_in_audit_log(self, ctx):
        hook = PostAuditHook()
        hctx = make_hctx(result=json.dumps([{"id": 1}, {"id": 2}, {"id": 3}]), latency_ms=10.0)
        hook(ctx, hctx)
        assert ctx.audit_log[-1]["record_count"] == 3

    def test_populates_budget_cache_on_success(self, ctx):
        budget_hook = CallBudgetHook()
        post_audit = PostAuditHook(budget_hook=budget_hook)
        result = json.dumps([{"id": 1}])
        cache_key = ("get_policies", (("csp", "aws"),))
        hctx = make_hctx(result=result, latency_ms=10.0)
        hctx.budget_cache_key = cache_key
        post_audit(ctx, hctx)
        assert budget_hook._cache.get(cache_key) == result

    def test_does_not_cache_when_budget_key_is_none(self, ctx):
        budget_hook = CallBudgetHook()
        post_audit = PostAuditHook(budget_hook=budget_hook)
        hctx = make_hctx(result=json.dumps([{"id": 1}]), latency_ms=10.0)
        # budget_cache_key stays None (simulates a cache-hit path)
        post_audit(ctx, hctx)
        assert len(budget_hook._cache) == 0


# ---------------------------------------------------------------------------
# HookChain — ordering and integration
# ---------------------------------------------------------------------------

class TestHookChain:
    def test_execute_pre_returns_true_when_no_short_circuit(self, ctx):
        chain = HookChain(pre_hooks=[], post_hooks=[])
        hctx = make_hctx()
        result = chain.execute_pre(ctx, hctx)
        assert result is True

    def test_execute_pre_returns_false_on_short_circuit(self, ctx):
        chain = HookChain(pre_hooks=[CSPGuardHook()], post_hooks=[])
        hctx = make_hctx(args={"csp": "amazon"})
        result = chain.execute_pre(ctx, hctx)
        assert result is False

    def test_pre_hooks_stop_after_short_circuit(self, ctx):
        execution_order = []

        class RecordingHook:
            def __init__(self, name):
                self.name = name

            def __call__(self, ctx, hctx):
                execution_order.append(self.name)

        class ShortCircuitHook:
            def __call__(self, ctx, hctx):
                execution_order.append("short_circuit")
                hctx.result = json.dumps({"_error": "stop"})

        chain = HookChain(
            pre_hooks=[RecordingHook("pre1"), ShortCircuitHook(), RecordingHook("pre2")],
            post_hooks=[],
        )
        hctx = make_hctx()
        chain.execute_pre(ctx, hctx)
        assert execution_order == ["pre1", "short_circuit"]
        assert "pre2" not in execution_order

    def test_full_pre_hook_order(self, ctx):
        """Verify documented pre-hook execution order via instrumented stubs."""
        order = []

        class Recorder:
            def __init__(self, name):
                self.name = name
            def __call__(self, ctx, hctx):
                order.append(self.name)

        chain = HookChain(
            pre_hooks=[
                Recorder("PreAudit"),
                Recorder("InputNorm"),
                Recorder("CSPGuard"),
                Recorder("ArgBounds"),
                Recorder("CallBudget"),
            ],
            post_hooks=[],
        )
        chain.execute_pre(ctx, make_hctx())
        assert order == ["PreAudit", "InputNorm", "CSPGuard", "ArgBounds", "CallBudget"]

    def test_full_post_hook_order(self, ctx):
        """Verify documented post-hook execution order via instrumented stubs."""
        order = []

        class Recorder:
            def __init__(self, name):
                self.name = name
            def __call__(self, ctx, hctx):
                order.append(self.name)

        chain = HookChain(
            pre_hooks=[],
            post_hooks=[
                Recorder("ErrorNorm"),
                Recorder("EmptyResult"),
                Recorder("SizeLimiter"),
                Recorder("MetaEnrich"),
                Recorder("PostAudit"),
            ],
        )
        hctx = make_hctx(result='[]', latency_ms=0.0)
        chain.execute_post(ctx, hctx)
        assert order == ["ErrorNorm", "EmptyResult", "SizeLimiter", "MetaEnrich", "PostAudit"]

    def test_csp_guard_runs_after_normalization_in_default_chain(self, ctx):
        """Confirm that build_default_hook_chain() accepts uppercase CSP values
        because normalization fires before the guard."""
        chain = build_default_hook_chain()
        hctx = make_hctx(args={"csp": "AWS"})
        should_call = chain.execute_pre(ctx, hctx)
        # After normalization 'AWS' → 'aws', which is valid, so no short-circuit.
        assert should_call is True
        assert hctx.args["csp"] == "aws"


class TestDefaultHookChainEndToEnd:
    """Integration-style tests running the full default chain against a synthetic result."""

    def test_empty_result_gets_warning_and_metadata(self, ctx):
        chain = build_default_hook_chain()
        hctx = make_hctx(args={"csp": "aws"})
        chain.execute_pre(ctx, hctx)
        hctx.result = "[]"
        hctx.latency_ms = 15.0
        chain.execute_post(ctx, hctx)
        payload = json.loads(hctx.result)
        assert "_warning" in payload
        assert "_latency_ms" in payload
        # audit log has start + complete
        events = [e["event"] for e in ctx.audit_log]
        assert "tool_call_start" in events
        assert "tool_call_complete" in events

    def test_error_result_normalized_and_audited(self, ctx):
        chain = build_default_hook_chain()
        hctx = make_hctx(args={"csp": "aws"})
        chain.execute_pre(ctx, hctx)
        hctx.error = RuntimeError("SQLite locked")
        hctx.latency_ms = 5.0
        chain.execute_post(ctx, hctx)
        payload = json.loads(hctx.result)
        assert "_error" in payload
        complete = next(e for e in ctx.audit_log if e["event"] == "tool_call_complete")
        assert complete["outcome"] == "error"

    def test_large_result_truncated_with_metadata(self, ctx):
        chain = build_default_hook_chain()
        hctx = make_hctx(args={"csp": "aws"})
        chain.execute_pre(ctx, hctx)
        hctx.result = _make_large_result(200)
        hctx.latency_ms = 80.0
        chain.execute_post(ctx, hctx)
        payload = json.loads(hctx.result)
        assert payload.get("_truncated") is True
        assert "_latency_ms" in payload
        # SizeLimiterHook reserves _TRUNCATION_OVERHEAD for downstream metadata;
        # the full enriched result must still fit within _MAX_RESULT_CHARS.
        assert len(hctx.result) <= _MAX_RESULT_CHARS

    def test_duplicate_call_short_circuits_and_posts(self, ctx):
        chain = build_default_hook_chain()
        first_result = json.dumps([{"id": 1}])

        # First call — populates the cache
        hctx1 = make_hctx(args={"csp": "aws"})
        chain.execute_pre(ctx, hctx1)
        hctx1.result = first_result
        hctx1.latency_ms = 20.0
        chain.execute_post(ctx, hctx1)

        # Second identical call — should be served from cache
        ctx2 = AssessmentContext.create(
            document=ctx.document,
            target_csp=CSP.aws,
            enable_multi_agent=True,
        )
        hctx2 = make_hctx(args={"csp": "aws"})
        should_call = chain.execute_pre(ctx2, hctx2)
        assert should_call is False   # short-circuited
        hctx2.latency_ms = 0.0
        chain.execute_post(ctx2, hctx2)
        # Result came from cache
        assert json.loads(hctx2.result)["data"][0] == {"id": 1}
