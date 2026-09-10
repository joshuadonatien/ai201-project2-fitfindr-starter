"""
agent.py

The FitFindr planning loop. Orchestrates the three tools in response to a
natural language user query, passing state between them via a session dict.

Complete tools.py and test each tool in isolation before implementing this file.

Usage (once implemented):
    from agent import run_agent
    from utils.data_loader import get_example_wardrobe

    result = run_agent(
        query="vintage graphic tee under $30, size M",
        wardrobe=get_example_wardrobe(),
    )
    print(result["fit_card"])
    print(result["error"])   # None on success
"""

import re

from tools import search_listings, suggest_outfit, create_fit_card


# ── session state ─────────────────────────────────────────────────────────────

def _new_session(query: str, wardrobe: dict) -> dict:
    """
    Initialize and return a fresh session dict for one user interaction.

    The session dict is the single source of truth for everything that happens
    during a run — it stores the original query, parsed parameters, tool results,
    and any error that caused early termination.

    You may add fields to this dict as needed for your implementation.
    """
    return {
        "query": query,              # original user query
        "parsed": {},                # extracted description / size / max_price
        "search_results": [],        # list of matching listing dicts
        "selected_item": None,       # top result, passed into suggest_outfit
        "wardrobe": wardrobe,        # user's wardrobe dict
        "outfit_suggestion": None,   # string returned by suggest_outfit
        "fit_card": None,            # string returned by create_fit_card
        "error": None,               # set if the interaction ended early
        # ── added for this implementation ───────────────────────────────────
        "steps": [],                 # human-readable log of what the loop did
        "retried_search": False,     # True if the no-results retry fired
        "relaxed_constraint": None,  # what was loosened on the retry, if any
    }


# ── query parsing ─────────────────────────────────────────────────────────────

# "under $30", "below 30", "less than $30.50", "max 30", "up to $40"
_PRICE_PATTERNS = [
    re.compile(
        r"(?:under|below|less than|no more than|max(?:imum)?|up to|<=?)\s*"
        r"\$?\s*(\d+(?:\.\d{1,2})?)",
        re.I,
    ),
    re.compile(r"\$\s*(\d+(?:\.\d{1,2})?)"),
]

# "size M", "size 8", "sz XL", "size W30"
_SIZE_PATTERN = re.compile(r"\b(?:size|sz)\s+([A-Za-z0-9/]+)", re.I)

# conversational filler that carries no search signal
_FILLER_PATTERN = re.compile(
    r"\b(i'?m|i am|looking for|look for|searching for|search for|i want|i need|"
    r"show me|find me|what'?s out there|how would i style it|"
    r"and how would i style it|can you help|please|mostly wear|i mostly wear)\b",
    re.I,
)


def _parse_query(query: str) -> dict:
    """
    Extract (description, size, max_price) from a natural language query.

    Deterministic regex parsing — chosen over an LLM parse so it is fast, free,
    and unit-testable. Documented in planning.md → Planning Loop.
    """
    size = None
    max_price = None

    m = _SIZE_PATTERN.search(query)
    if m:
        size = m.group(1).upper()

    for pattern in _PRICE_PATTERNS:
        m = pattern.search(query)
        if m:
            max_price = float(m.group(1))
            break

    # description = the query with the size/price clauses and filler stripped
    description = _SIZE_PATTERN.sub(" ", query)
    for pattern in _PRICE_PATTERNS:
        description = pattern.sub(" ", description)
    description = _FILLER_PATTERN.sub(" ", description)
    description = re.sub(r"[^\w\s/-]", " ", description)   # drop punctuation
    description = re.sub(r"\s+", " ", description).strip()
    if not description:                                    # fell through — keep the raw words
        description = re.sub(r"[^\w\s]", " ", query).strip()

    return {"description": description, "size": size, "max_price": max_price}


def _relax_constraints(parsed: dict) -> dict | None:
    """
    Loosen the single most restrictive optional filter for one retry.
    Returns a new parsed dict (with a "_changed" note), or None if there is
    nothing left to loosen (keywords only).
    """
    if parsed["size"] is not None:
        return {
            **parsed,
            "size": None,
            "_changed": f"dropped the size {parsed['size']} filter",
        }
    if parsed["max_price"] is not None:
        bumped = round(parsed["max_price"] * 1.5, 2)
        return {
            **parsed,
            "max_price": bumped,
            "_changed": f"raised the price ceiling to ${bumped:g}",
        }
    return None


def _no_results_message(parsed: dict) -> str:
    """Actionable message for the user when the search comes back empty."""
    filters = []
    if parsed["size"]:
        filters.append(f"size {parsed['size']}")
    if parsed["max_price"]:
        filters.append(f"under ${parsed['max_price']:g}")
    suffix = f" ({', '.join(filters)})" if filters else ""
    return (
        f"No listings matched \"{parsed['description']}\"{suffix}. "
        "Try broader keywords, a wider size, or a higher price ceiling."
    )


# ── planning loop ─────────────────────────────────────────────────────────────

def run_agent(query: str, wardrobe: dict) -> dict:
    """
    Main agent entry point. Runs the FitFindr planning loop for a single
    user interaction and returns the completed session dict.

    Args:
        query:    Natural language user request
                  (e.g., "vintage graphic tee under $30, size M")
        wardrobe: User's wardrobe dict — use get_example_wardrobe() or
                  get_empty_wardrobe() from utils/data_loader.py

    Returns:
        The session dict after the interaction completes. Check session["error"]
        first — if it is not None, the interaction ended early and the other
        output fields (outfit_suggestion, fit_card) will be None.

    The loop is conditional, not a fixed 3-call pipeline:
      • search_listings always runs.
      • If it returns [] the loop tries ONE relaxed retry; if that is still
        empty it sets session["error"] and returns — suggest_outfit and
        create_fit_card never run.
      • suggest_outfit runs only with a real selected item. Its behavior itself
        branches on whether the wardrobe has items.
      • If suggest_outfit returns a "[suggest_outfit error] ..." string the loop
        sets session["error"] and returns — create_fit_card never runs.
      • create_fit_card runs last. A caption-only failure is non-fatal: it is
        stored in session["fit_card"] but session["error"] stays None.
    """
    # Step 1 — fresh session
    session = _new_session(query, wardrobe)

    # Step 2 — parse the query into search parameters
    session["parsed"] = _parse_query(query)
    p = session["parsed"]
    session["steps"].append(
        f"Parsed query → description={p['description']!r}, "
        f"size={p['size']}, max_price={p['max_price']}"
    )

    # Step 3 — search_listings (always runs)
    results = search_listings(p["description"], p["size"], p["max_price"])
    session["search_results"] = results
    session["steps"].append(f"search_listings → {len(results)} listing(s)")

    # Step 3b — adaptive branch: no results → one relaxed retry, else stop
    if not results:
        relaxed = _relax_constraints(p)
        if relaxed is not None:
            session["retried_search"] = True
            session["relaxed_constraint"] = relaxed["_changed"]
            results = search_listings(
                relaxed["description"], relaxed["size"], relaxed["max_price"]
            )
            session["search_results"] = results
            session["steps"].append(
                f"No matches — retried after {relaxed['_changed']} "
                f"→ {len(results)} listing(s)"
            )

    if not results:
        session["error"] = _no_results_message(p)
        session["steps"].append(
            "STOP: no results — suggest_outfit and create_fit_card were not called"
        )
        return session

    # Step 4 — select the item to carry forward (top-ranked result)
    session["selected_item"] = results[0]
    session["steps"].append(
        f"Selected top result: {results[0]['title']} (${results[0]['price']:g})"
    )

    # Step 5 — suggest_outfit  (state in: selected_item + wardrobe)
    n_items = len((session["wardrobe"] or {}).get("items", []))
    session["outfit_suggestion"] = suggest_outfit(
        session["selected_item"], session["wardrobe"]
    )
    session["steps"].append(
        "suggest_outfit called with the selected item + "
        + (f"{n_items}-item wardrobe"
           if n_items else "empty wardrobe → general-advice branch")
    )

    # Step 5b — adaptive branch: styling failed → stop before create_fit_card
    if session["outfit_suggestion"].startswith("[suggest_outfit error]"):
        session["error"] = session["outfit_suggestion"]
        session["steps"].append(
            "STOP: suggest_outfit failed — create_fit_card was not called"
        )
        return session

    # Step 6 — create_fit_card  (state in: outfit_suggestion + selected_item)
    session["fit_card"] = create_fit_card(
        session["outfit_suggestion"], session["selected_item"]
    )
    if session["fit_card"].startswith("[create_fit_card error]"):
        session["steps"].append(
            "create_fit_card failed — returning listing + outfit without a caption"
        )
    else:
        session["steps"].append(
            "create_fit_card called with the outfit suggestion + selected item"
        )

    # Step 7 — done
    return session


# ── CLI test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from utils.data_loader import get_example_wardrobe, get_empty_wardrobe

    def _dump(session: dict) -> None:
        print("  steps:")
        for i, step in enumerate(session["steps"], 1):
            print(f"    {i}. {step}")
        print(f"  error: {session['error']}")
        print(f"  selected_item: "
              f"{session['selected_item']['title'] if session['selected_item'] else None}")
        print(f"  outfit_suggestion set: {session['outfit_suggestion'] is not None}")
        print(f"  fit_card set: {session['fit_card'] is not None}")

    print("=== Happy path: graphic tee ===\n")
    session = run_agent(
        query="looking for a vintage graphic tee under $30",
        wardrobe=get_example_wardrobe(),
    )
    if session["error"]:
        print(f"Error: {session['error']}")
    else:
        print(f"Found: {session['selected_item']['title']}")
        print(f"\nOutfit: {session['outfit_suggestion']}")
        print(f"\nFit card: {session['fit_card']}")
    print()
    _dump(session)

    print("\n\n=== No-results path ===\n")
    session2 = run_agent(
        query="designer ballgown size XXS under $5",
        wardrobe=get_example_wardrobe(),
    )
    print(f"Error message: {session2['error']}")
    print(f"fit_card is None: {session2['fit_card'] is None}")
    print(f"outfit_suggestion is None: {session2['outfit_suggestion'] is None}")
    print()
    _dump(session2)
