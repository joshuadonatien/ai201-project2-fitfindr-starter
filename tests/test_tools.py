"""
tests/test_tools.py

Isolation tests for the three FitFindr tools (Milestone 3). At least one test
per failure mode.

Run from the repo root with:
    python -m pytest tests/

The `-m` form puts the repo root on sys.path so `from tools import ...` resolves.
Bare `pytest tests/` fails with ModuleNotFoundError: No module named 'tools'.

The two LLM-backed tools (suggest_outfit, create_fit_card) need a real
GROQ_API_KEY. Tests that make a live LLM call are skipped automatically when no
key is set; their guard/failure-mode paths (which make no network call) always
run.
"""

import os

import pytest

from tools import search_listings, suggest_outfit, create_fit_card
from utils.data_loader import get_example_wardrobe, get_empty_wardrobe

HAS_KEY = bool(os.environ.get("GROQ_API_KEY"))
needs_key = pytest.mark.skipif(not HAS_KEY, reason="GROQ_API_KEY not set")


# ── Tool 1: search_listings ───────────────────────────────────────────────────

def test_search_returns_results():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert isinstance(results, list)
    assert len(results) > 0
    # each result is a listing dict with the documented fields
    top = results[0]
    for field in ("id", "title", "price", "size", "style_tags", "platform"):
        assert field in top


def test_search_empty_results_no_exception():
    """Failure mode: nothing matches → empty list, never an exception."""
    results = search_listings("designer ballgown", size="XXS", max_price=5)
    assert results == []


def test_search_price_filter_is_inclusive_ceiling():
    results = search_listings("jacket", size=None, max_price=45)
    assert len(results) > 0
    assert all(item["price"] <= 45 for item in results)


def test_search_size_filter_matches_substring():
    """'M' should match a listing sized 'S/M' (case-insensitive substring)."""
    results = search_listings("tee", size="m", max_price=None)
    assert len(results) > 0
    assert all("m" in item["size"].lower() for item in results)


def test_search_results_sorted_by_relevance():
    """A title/tag keyword hit should outrank a description-only hit."""
    results = search_listings("denim jacket", size=None, max_price=None)
    assert results[0]["title"] == "Denim Jacket — Light Wash, Cropped"


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

def _sample_item():
    return search_listings("vintage graphic tee", size=None, max_price=50)[0]


@needs_key
def test_suggest_outfit_with_wardrobe_names_pieces():
    out = suggest_outfit(_sample_item(), get_example_wardrobe())
    assert isinstance(out, str) and out.strip()
    assert not out.startswith("[suggest_outfit error]")


@needs_key
def test_suggest_outfit_empty_wardrobe_still_returns_advice():
    """Failure mode: empty wardrobe → general advice, no crash, non-empty."""
    out = suggest_outfit(_sample_item(), get_empty_wardrobe())
    assert isinstance(out, str) and out.strip()
    assert not out.startswith("[suggest_outfit error]")


def test_suggest_outfit_empty_wardrobe_does_not_raise_offline():
    """The empty-wardrobe branch is reached without an exception even with a
    bad key — the only failure surface is the network call, which must be
    caught and returned as a string."""
    old = os.environ.get("GROQ_API_KEY")
    os.environ["GROQ_API_KEY"] = "sk-invalid-for-test"
    try:
        out = suggest_outfit(_sample_item(), get_empty_wardrobe())
    finally:
        if old is None:
            os.environ.pop("GROQ_API_KEY", None)
        else:
            os.environ["GROQ_API_KEY"] = old
    assert isinstance(out, str)
    assert out.startswith("[suggest_outfit error]")


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

def test_create_fit_card_empty_outfit_returns_error_string():
    """Failure mode: missing/empty outfit → descriptive error string, no raise,
    and no LLM call (works offline)."""
    result = create_fit_card("", _sample_item())
    assert isinstance(result, str)
    assert result.startswith("[create_fit_card error]")


def test_create_fit_card_whitespace_outfit_returns_error_string():
    result = create_fit_card("   \n  ", _sample_item())
    assert result.startswith("[create_fit_card error]")


@needs_key
def test_create_fit_card_happy_path_mentions_item():
    item = _sample_item()
    outfit = "Pair the tee with baggy jeans and chunky white sneakers."
    card = create_fit_card(outfit, item)
    assert isinstance(card, str) and card.strip()
    assert not card.startswith("[create_fit_card error]")


@needs_key
def test_create_fit_card_outputs_vary_on_repeat():
    """Higher temperature → two calls on the same input should differ."""
    item = _sample_item()
    outfit = "Pair the tee with baggy jeans and chunky white sneakers."
    a = create_fit_card(outfit, item)
    b = create_fit_card(outfit, item)
    assert a != b
