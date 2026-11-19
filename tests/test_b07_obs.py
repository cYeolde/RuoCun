"""Frozen obs attrs/backend/wrap semantics, using an injected recording backend."""

import asyncio
from contextlib import contextmanager


class Span:
    def __init__(self, options):
        self.options, self.attrs, self.ended = options, {}, False

    def setAttributes(self, attrs):
        self.attrs.update(attrs)

    def end(self):
        self.ended = True


class Backend:
    def __init__(self):
        self.spans, self.events, self.active = [], [], None

    def startSpan(self, options):
        span = Span({**options, "parent": self.active})
        self.spans.append(span)
        return span

    @contextmanager
    def activate(self, span):
        old, self.active = self.active, span
        try:
            yield
        finally:
            self.active = old

    def event(self, name, attributes):
        self.events.append((name, attributes))

    def flush(self):
        pass


def test_source_attributes_cache_tags_and_floor():
    from ruocun.obs.attrs import TAGS_KEY, cacheLow, cacheTag, llmAttributes

    usage = {"prompt_tokens": 20000, "completion_tokens": 4, "total_tokens": 20004,
             "prompt_cache_hit_tokens": 1111, "prompt_cache_miss_tokens": 18889}
    assert llmAttributes("model", usage)["gen_ai.usage.input_tokens"] == 20000
    assert cacheTag(usage) == "cache_hit" and cacheTag({"prompt_cache_miss_tokens": 1}) == "cache_miss"
    assert cacheTag({}) is None and TAGS_KEY == "lmnr.association.properties.tags"
    assert cacheLow(usage) == {"hit_rate": 0.056, "prompt_tokens": 20000}
    assert cacheLow({"prompt_tokens": 9999}) is None
    assert cacheLow({"prompt_tokens": 20000, "prompt_cache_hit_tokens": 10000}) is None


def test_source_wrappers_passthrough_parentage_usage_failure_and_redaction():
    from ruocun.client.resilient import ResilientResult
    from ruocun.obs.backend import (
        observationScope,
        setBackend,
        setObsRedactor,
        spanScope,
    )
    from ruocun.obs.wrap import wrapRequest, wrapToolHandler

    backend = Backend()
    setBackend(None)
    def request(opts, context):
        usage = {"prompt_tokens": 20000, "completion_tokens": 4, "total_tokens": 20004,
                 "prompt_cache_hit_tokens": 1}
        opts["onUsage"](usage)
        return ResilientResult("complete", [{"content": "synthetic-key"}],
            {"role": "assistant", "content": "synthetic-key"}, usage, "stop", [], {})
    assert wrapRequest(request) is request
    setBackend(backend)
    setObsRedactor(lambda text: text.replace("synthetic-key", "[redacted]"))
    seen = []
    async def handler():
        return "Error: synthetic-key"
    async def turn():
        result = wrapRequest(request)({"model": "model", "messages": [{"role": "user", "content": "synthetic-key"}],
            "onUsage": seen.append}, None)
        assert result.message["content"] == "synthetic-key"  # Business bytes untouched.
        assert await wrapToolHandler(handler, "Read", "synthetic-key")() == "Error: synthetic-key"
        return 7
    async def run():
        with observationScope(sessionId="session", taskId="task", runId="run", identity="child", depth=1):
            with spanScope("turn"):
                assert await turn() == 7
            with spanScope("reflect", metadata={"kind": "challenger"}):
                pass
    try:
        asyncio.run(run())
        assert seen and all(span.ended for span in backend.spans)
        parent, llm, tool, reflect = backend.spans
        assert llm.options["parent"] is parent and tool.options["parent"] is parent
        assert parent.options["metadata"]["runId"] == "run"
        assert parent.options["sessionId"] == "session"
        assert "synthetic-key" not in repr([(s.options, s.attrs) for s in backend.spans])
        assert {event[0] for event in backend.events} == {"cache_low", "tool_error"}
    finally:
        setBackend(None)
        setObsRedactor(None)


def test_observer_failure_never_reexecutes_business_and_close_is_bounded():
    from threading import Event

    import pytest

    from ruocun.obs import closeObs, isObsOn, spanScope
    from ruocun.obs.backend import setBackend

    closing = Event()
    allow_shutdown = Event()
    closed = Event()

    class Broken(Backend):
        @contextmanager
        def activate(self, span):
            yield
            raise RuntimeError("observer exit failure")

        def shutdown(self):
            closing.set()
            allow_shutdown.wait(2)
            closed.set()

    calls = []
    async def business():
        calls.append(1)
        raise ValueError("business failure")
    async def run():
        with pytest.raises(ValueError, match="business failure"), spanScope("turn"):
            await business()
        async with asyncio.timeout(1):
            await closeObs(10)
        assert not isObsOn()
        assert closing.wait(1) and not closed.is_set()
    try:
        setBackend(Broken())
        asyncio.run(run())
        assert calls == [1]
    finally:
        allow_shutdown.set()
        if closing.is_set():
            closed.wait(1)
        setBackend(None)


def test_source_init_off_imports_nothing_and_optional_sdk_failure_degrades(monkeypatch):
    import ruocun.obs.init as init
    from ruocun.obs.backend import obsStatus

    attempts = []
    def fail(name):
        attempts.append(name)
        raise ImportError("synthetic-private-error")
    monkeypatch.setattr(init.importlib, "import_module", fail)
    asyncio.run(init.initObs(False, environ={}))
    assert not attempts and obsStatus()["requested"] is False
    warnings = []
    asyncio.run(init.initObs(True, environ={}, warn=warnings.append))
    assert attempts and obsStatus()["requested"] is True and obsStatus()["on"] is False
    assert "synthetic-private-error" not in "".join(warnings)
