"""
tests/test_agent.py

Planning-loop tests (Milestone 4). These monkeypatch the two LLM-backed tools so
the loop's control flow and state-passing can be verified WITHOUT an API key:

  - state identity: the exact dict from search_listings reaches suggest_outfit,
    and the string from suggest_outfit reaches create_fit_card — no re-entry.
  - adaptiveness: the loop does NOT call all three tools unconditionally.

Run from the repo root with:  python -m pytest tests/
"""

import os

import pytest

import agent as agent_mod
from agent import run_agent, _parse_query
from utils.data_loader import get_example_wardrobe, get_empty_wardrobe

HAS_KEY = bool(os.environ.get("GROQ_API_KEY"))
needs_key = pytest.mark.skipif(not HAS_KEY, reason="GROQ_API_KEY not set")


# ── query parsing ─────────────────────────────────────────────────────────────

def test_parse_extracts_size_and_price_and_cleans_description():
    p = _parse_query("90s track jacket in size M under $45")
    assert p["size"] == "M"
    assert p["max_price"] == 45.0
    assert "track" in p["description"] and "jacket" in p["description"]
    assert "size" not in p["description"].lower()
    assert "$" not in p["description"] and "45" not in p["description"]


def test_parse_no_filters():
    p = _parse_query("flowy midi skirt")
    assert p["size"] is None
    assert p["max_price"] is None


# ── state passes between tools without re-entry ───────────────────────────────

def test_selected_item_and_outfit_flow_through_unchanged(monkeypatch):
    seen = {}

    def fake_suggest(new_item, wardrobe):
        seen["suggest_item"] = new_item          # capture what search handed us
        return "OUTFIT: tee + baggy jeans + sneakers"

    def fake_card(outfit, new_item):
        seen["card_outfit"] = outfit             # capture what suggest handed us
        seen["card_item"] = new_item
        return "a shareable caption"

    monkeypatch.setattr(agent_mod, "suggest_outfit", fake_suggest)
    monkeypatch.setattr(agent_mod, "create_fit_card", fake_card)

    session = run_agent("vintage graphic tee under $30", get_example_wardrobe())

    # the SAME object that search_listings selected went into suggest_outfit
    assert seen["suggest_item"] is session["selected_item"]
    # the outfit string suggest_outfit returned went into create_fit_card verbatim
    assert seen["card_outfit"] == session["outfit_suggestion"]
    assert seen["card_outfit"] == "OUTFIT: tee + baggy jeans + sneakers"
    # and create_fit_card got the same item too — nothing re-entered by the user
    assert seen["card_item"] is session["selected_item"]
    assert session["fit_card"] == "a shareable caption"
    assert session["error"] is None


# ── adaptiveness: different inputs → different tool sequences ──────────────────

def test_no_results_stops_before_the_llm_tools(monkeypatch):
    calls = []
    monkeypatch.setattr(agent_mod, "suggest_outfit",
                        lambda *a, **k: calls.append("suggest") or "x")
    monkeypatch.setattr(agent_mod, "create_fit_card",
                        lambda *a, **k: calls.append("card") or "y")

    session = run_agent("designer ballgown size XXS under $5", get_example_wardrobe())

    assert calls == []                       # neither LLM tool was called
    assert session["error"] is not None
    assert session["selected_item"] is None
    assert session["outfit_suggestion"] is None
    assert session["fit_card"] is None


def test_happy_path_calls_all_three_in_order(monkeypatch):
    order = []
    monkeypatch.setattr(agent_mod, "suggest_outfit",
                        lambda *a, **k: order.append("suggest") or "OUTFIT")
    monkeypatch.setattr(agent_mod, "create_fit_card",
                        lambda *a, **k: order.append("card") or "CARD")

    session = run_agent("vintage graphic tee under $30", get_example_wardrobe())

    assert order == ["suggest", "card"]      # search ran first (real), then these
    assert session["error"] is None
    assert session["fit_card"] == "CARD"


def test_suggest_outfit_failure_stops_before_create_fit_card(monkeypatch):
    calls = []
    monkeypatch.setattr(agent_mod, "suggest_outfit",
                        lambda *a, **k: "[suggest_outfit error] simulated outage")
    monkeypatch.setattr(agent_mod, "create_fit_card",
                        lambda *a, **k: calls.append("card") or "y")

    session = run_agent("vintage graphic tee under $30", get_example_wardrobe())

    assert calls == []                       # create_fit_card was skipped
    assert session["fit_card"] is None
    # the agent surfaces an actionable message, not the raw error string
    assert not session["error"].startswith("[suggest_outfit error]")
    assert "styling step is unavailable" in session["error"]
    assert "simulated outage" in session["error"]   # technical detail preserved


def test_zero_result_search_triggers_one_relaxed_retry(monkeypatch):
    # "combat boots" exists only in size ~8; ask for an impossible size so the
    # first search is empty and the loop must relax the size filter.
    session = run_agent("combat boots size 99", get_empty_wardrobe())
    # either the retry found something (size dropped) or it stopped cleanly —
    # but the retry MUST have been attempted, and the loop MUST have adapted.
    assert session["retried_search"] is True
    assert session["relaxed_constraint"] is not None


# ── end-to-end (needs a real key) ────────────────────────────────────────────

@needs_key
def test_end_to_end_happy_path_produces_a_fit_card():
    session = run_agent("vintage graphic tee under $30", get_example_wardrobe())
    assert session["error"] is None
    assert session["selected_item"] is not None
    assert session["outfit_suggestion"] and not session["outfit_suggestion"].startswith("[")
    assert session["fit_card"] and not session["fit_card"].startswith("[")
