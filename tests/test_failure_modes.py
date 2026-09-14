"""
tests/test_failure_modes.py

Milestone 5 — every failure mode triggered deliberately, as automated tests.
Each test mirrors one of the manual trigger commands in the milestone and
asserts the agent degrades gracefully (specific message, no exception).

Run from the repo root:  python -m pytest tests/test_failure_modes.py -v

None of these need a valid GROQ_API_KEY — the LLM-failure tests deliberately
use a bad one, and the guard/empty-result paths never reach the network.
"""

import os

import pytest

from tools import search_listings, suggest_outfit, create_fit_card
from agent import run_agent
from utils.data_loader import get_example_wardrobe, get_empty_wardrobe


# ── Failure 1: search_listings returns zero results ───────────────────────────

def test_search_listings_zero_results_returns_empty_list_no_exception():
    # python -c "from tools import search_listings;
    #            print(search_listings('designer ballgown', size='XXS', max_price=5))"
    result = search_listings("designer ballgown", size="XXS", max_price=5)
    assert result == []
    assert isinstance(result, list)


def test_agent_no_results_response_is_specific_and_actionable():
    session = run_agent("designer ballgown size XXS under $5", get_example_wardrobe())
    msg = session["error"]
    assert msg is not None
    # names WHAT failed (the query + filters), not just "no results found"
    assert "designer ballgown" in msg
    assert "XXS" in msg and "$5" in msg
    # tells the user WHAT TO TRY next
    assert any(hint in msg.lower()
               for hint in ("broader", "wider", "higher price"))
    # and it stopped before the LLM tools
    assert session["outfit_suggestion"] is None
    assert session["fit_card"] is None


# ── Failure 2: suggest_outfit with an empty wardrobe ──────────────────────────

@pytest.mark.skipif(not os.environ.get("GROQ_API_KEY"),
                    reason="needs a real key to exercise the advice branch")
def test_suggest_outfit_empty_wardrobe_returns_useful_advice():
    # python -c "... print(suggest_outfit(results[0], get_empty_wardrobe()))"
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    out = suggest_outfit(results[0], get_empty_wardrobe())
    assert isinstance(out, str)
    assert len(out.strip()) > 50                       # real advice, not ""
    assert not out.startswith("[suggest_outfit error]")


def test_suggest_outfit_empty_wardrobe_never_raises_even_offline():
    """The empty-wardrobe branch is reached and any network error is caught."""
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    old = os.environ.get("GROQ_API_KEY")
    os.environ["GROQ_API_KEY"] = "gsk_invalid_key_for_testing"
    try:
        out = suggest_outfit(results[0], get_empty_wardrobe())
    finally:
        if old is None:
            os.environ.pop("GROQ_API_KEY", None)
        else:
            os.environ["GROQ_API_KEY"] = old
    assert isinstance(out, str) and out                # never "" , never raises


# ── Failure 3: create_fit_card with an empty outfit string ────────────────────

def test_create_fit_card_empty_outfit_returns_descriptive_string_not_exception():
    # python -c "... print(create_fit_card('', results[0]))"
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    card = create_fit_card("", results[0])
    assert isinstance(card, str)
    assert card.startswith("[create_fit_card error]")
    assert "suggest_outfit" in card                    # tells you what to do


# ── Failure 4: LLM / network failure (invalid API key) ────────────────────────

def _with_bad_key():
    old = os.environ.get("GROQ_API_KEY")
    os.environ["GROQ_API_KEY"] = "gsk_invalid_key_for_testing"
    return old


def _restore_key(old):
    if old is None:
        os.environ.pop("GROQ_API_KEY", None)
    else:
        os.environ["GROQ_API_KEY"] = old


def test_suggest_outfit_llm_failure_returns_error_string_not_exception():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    old = _with_bad_key()
    try:
        out = suggest_outfit(results[0], get_example_wardrobe())
    finally:
        _restore_key(old)
    assert out.startswith("[suggest_outfit error]")


def test_agent_llm_failure_response_is_actionable():
    old = _with_bad_key()
    try:
        session = run_agent("vintage graphic tee under $30", get_example_wardrobe())
    finally:
        _restore_key(old)
    msg = session["error"]
    assert msg is not None
    assert not msg.startswith("[suggest_outfit error]")   # not the raw string
    assert "Vintage Band Tee" in msg                       # what we DID find
    assert "try again" in msg.lower()                      # what to do next
    assert session["fit_card"] is None                     # create_fit_card skipped


def test_agent_caption_failure_is_non_fatal():
    """create_fit_card failing must NOT wipe the listing + outfit."""
    import agent as agent_mod
    orig_suggest = agent_mod.suggest_outfit
    agent_mod.suggest_outfit = lambda item, wr: "OUTFIT: tee + jeans + boots"
    agent_mod.create_fit_card = lambda outfit, item: "[create_fit_card error] model down"
    try:
        session = run_agent("vintage graphic tee under $30", get_example_wardrobe())
    finally:
        agent_mod.suggest_outfit = orig_suggest
    assert session["error"] is None                        # non-fatal
    assert session["selected_item"] is not None
    assert session["outfit_suggestion"] == "OUTFIT: tee + jeans + boots"
    assert session["fit_card"].startswith("[create_fit_card error]")
