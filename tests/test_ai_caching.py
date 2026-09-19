"""
Prompt caching, and the meter knowing the difference.

Every assistant here re-sends the same thing on every turn: the instructions,
the workspace's saved memory, and a JSON dump of the business. On a forty-person
restaurant that dump alone is 46,110 tokens, paid for in full on each question,
to tell the model something it was told a minute ago.

Cached input is a tenth of the price. On that workspace it is the difference
between $0.2049 and $0.0273 a question — 87% — which makes it the largest single
lever in this product's unit economics, and it costs one field on one parameter.

Two things have to hold together or it is worse than not doing it:

  the request must be shaped so the cache can hit — the breakpoint at the end
  of the system prompt, because caching is a prefix match and everything after
  it varies

  the meter must count cache reads separately — they are billed at a tenth, so
  a wallet that cannot tell them apart charges the customer ten times what the
  call cost, on exactly the workspaces large enough for caching to matter
"""

from __future__ import annotations

import inspect

import pytest

from backend.app import ai_agent, ai_service, employee_assistant
from backend.app.ai_pricing import cached_system, cost_milli, dollars, usage_from


# ===========================================================================
# The request is shaped so it can hit
# ===========================================================================

def test_the_breakpoint_sits_at_the_end_of_the_system_prompt():
    blocks = cached_system("instructions and the whole business")
    assert len(blocks) == 1
    assert blocks[0]["cache_control"] == {"type": "ephemeral"}
    assert blocks[0]["type"] == "text"


@pytest.mark.parametrize("module,name", [
    (ai_service, "the scheduling assistant"),
    (ai_agent, "the business agent"),
    (employee_assistant, "the employee assistant"),
])
def test_every_assistant_caches_its_system_prompt(module, name):
    """
    All three, or the one that does not becomes the cheap way to spend the
    wallet — which is exactly how the scheduling assistant ended up being the
    one page with no accounting at all.
    """
    source = inspect.getsource(module)
    assert "cached_system(" in source, f"{name} pays full price on every turn"


def test_the_agents_tool_loop_caches_every_round():
    """
    The business agent runs its loop up to MAX_TOOL_ROUNDS times for one
    question, re-sending the system prompt and every tool definition each
    round. The saving is per round, not per question.
    """
    source = inspect.getsource(ai_agent.agent_chat)
    assert "cached_system(" in source
    assert "for _ in range(MAX_TOOL_ROUNDS)" in source


# ===========================================================================
# The meter counts it correctly
# ===========================================================================

def test_a_cache_read_costs_a_tenth_of_fresh_input():
    fresh = cost_milli("claude-sonnet-5", input_tokens=46_110)
    cached = cost_milli("claude-sonnet-5", cache_read_tokens=46_110)
    assert cached == pytest.approx(fresh * 0.1, rel=0.01)


def test_a_cache_write_costs_a_quarter_more_than_fresh():
    """
    Writing is more expensive than reading that input once, which is why
    caching a prompt used only once is a loss rather than a saving.
    """
    fresh = cost_milli("claude-sonnet-5", input_tokens=46_110)
    written = cost_milli("claude-sonnet-5", cache_write_tokens=46_110)
    assert written == pytest.approx(fresh * 1.25, rel=0.01)


def test_the_measured_saving_on_a_real_workspace():
    """
    The number the decision was made on, pinned so a rate change or a rounding
    change cannot quietly erase it.
    """
    uncached = cost_milli("claude-sonnet-5", input_tokens=99_442, output_tokens=600)
    cached = cost_milli(
        "claude-sonnet-5", input_tokens=800, cache_read_tokens=98_642, output_tokens=600
    )

    assert dollars(uncached) == pytest.approx(0.2049, abs=0.001)
    assert dollars(cached) == pytest.approx(0.0273, abs=0.001)
    assert 1 - cached / uncached > 0.85, "caching should be worth more than 85% here"


def test_usage_is_read_defensively():
    """
    The cache fields are absent from a response to a call that did not ask for
    caching, and from anything the SDK returns on a path that never reached the
    API. getattr with a default is the difference between a usage row and a 500
    in the one place that must not throw — after the money has been spent.
    """
    assert usage_from(object()) == (0, 0, 0, 0)
    assert usage_from(None) == (0, 0, 0, 0)


class _Usage:
    input_tokens = 800
    output_tokens = 600
    cache_read_input_tokens = 98_642
    cache_creation_input_tokens = 0


class _Response:
    usage = _Usage()


def test_all_four_numbers_come_back():
    assert usage_from(_Response()) == (800, 600, 98_642, 0)


# ===========================================================================
# The shape the meter depends on
# ===========================================================================

def test_the_scheduling_assistant_reports_four_numbers_on_every_path():
    """
    It has three returns — no API key, success, and exception — and a caller
    that unpacks four. One of them returning two is an unpack error in
    production on the path that is hardest to test, which is the exception.
    """
    import re

    # Line by line rather than one pattern over the whole source: a regex that
    # needs an escaped newline in it has now been mangled three times by the
    # tooling writing this file, and there is nothing here that needs one.
    returns = [
        line.strip()
        for line in inspect.getsource(ai_service.decide_with_ai).splitlines()
        if line.strip().startswith("return ") and "(" in line
    ]
    assert len(returns) >= 2, "expected several return paths to check"

    for line in returns:
        literal = re.search(r"(\([^)]*\))\s*$", line)
        assert literal, f"could not read the usage tuple from: {line}"
        width = literal.group(1).count(",") + 1
        assert width == 4, f"{line} reports {width} values, the caller unpacks 4"


def test_the_recorder_accepts_cache_tokens():
    signature = inspect.signature(ai_agent._record_usage)
    assert "cache_read_tokens" in signature.parameters
    assert "cache_write_tokens" in signature.parameters


def test_cached_tokens_are_not_billed_as_fresh_input():
    """
    The failure this guards is silent and expensive in the customer's
    direction: counting 98,642 cache reads as ordinary input charges them
    $0.2049 for a call that cost $0.0273.
    """
    from backend.app.ai_agent import MODEL

    honest = cost_milli(MODEL, input_tokens=800, cache_read_tokens=98_642, output_tokens=600)
    naive = cost_milli(MODEL, input_tokens=99_442, output_tokens=600)
    assert honest < naive / 7
