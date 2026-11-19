"""Session 数据与用量的来源行为断言（MIT）。"""

import pytest

from ruocun.session.session import Session


def test_starts_with_system_and_given_model():
    s = Session("SYS", "deepseek-v4-pro", env={})
    assert s.messages == [{"role": "system", "content": "SYS"}]
    assert s.model == "deepseek-v4-pro" and s.mode == "normal"


def test_set_model_keeps_messages():
    s = Session("SYS", "m", env={})
    s.messages.append({"role": "user", "content": "a"})
    s.setModel("deepseek-v4-flash")
    assert s.model == "deepseek-v4-flash"
    assert s.messages == [{"role": "system", "content": "SYS"}, {"role": "user", "content": "a"}]


def test_accumulates_usage_and_cache_ratio():
    s = Session("SYS", "deepseek-v4-pro", env={})
    for hit in (900, 800):
        s.addUsage({"prompt_tokens": 1000, "completion_tokens": 50,
                    "prompt_cache_hit_tokens": hit, "prompt_cache_miss_tokens": 1000 - hit})
    assert s.usage["promptTokens"] == 2000
    assert s.usage["completionTokens"] == 100 and s.usage["cacheHitTokens"] == 1700
    assert s.cacheHitRatio() == pytest.approx(.85)


def test_missing_cache_and_empty_sessions():
    s = Session("S", "m", env={})
    s.addUsage({"prompt_tokens": 100, "completion_tokens": 10})
    assert s.usage["cacheHitTokens"] == 0 and s.cacheHitRatio() == 0


def test_cache_bust_fires_for_high_prefix_collapse():
    s = Session("S", "m", env={})
    hits = []
    s.onCacheBust(hits.append)
    s.addPrimaryUsage({"prompt_tokens": 20000, "prompt_cache_hit_tokens": 19000}, s.model)
    assert hits == []
    s.addPrimaryUsage({"prompt_tokens": 21000, "prompt_cache_hit_tokens": 1000}, s.model)
    assert len(hits) == 1
    assert hits[0]["from"] == pytest.approx(.95, abs=.1)
    assert hits[0]["to"] == pytest.approx(.05, abs=.1)


def test_cache_bust_changed_prefix_dimension():
    s = Session("S", "m", env={})
    hits = []
    s.onCacheBust(hits.append)
    s.notePrefix({"model": "pro", "sys": "h1", "tools": "t1", "tail": "x"})
    s.addPrimaryUsage({"prompt_tokens": 20000, "prompt_cache_hit_tokens": 19000}, s.model)
    s.notePrefix({"model": "pro", "sys": "h2", "tools": "t1", "tail": "x"})
    s.addPrimaryUsage({"prompt_tokens": 21000, "prompt_cache_hit_tokens": 500}, s.model)
    assert hits[0]["changed"] == ["sys"]


def test_first_small_and_healthy_calls_do_not_warn():
    s = Session("S", "m", env={})
    hits = []
    s.onCacheBust(hits.append)
    for prompt, hit in ((18000, 0), (19000, 18000), (20000, 19000), (500, 0)):
        s.addPrimaryUsage({"prompt_tokens": prompt, "prompt_cache_hit_tokens": hit}, s.model)
    assert hits == []
