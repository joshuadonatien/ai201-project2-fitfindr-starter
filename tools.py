"""
tools.py

The three required FitFindr tools. Each tool is a standalone function that
can be called and tested independently before being wired into the agent loop.

Complete and test each tool before moving to agent.py.

Tools:
    search_listings(description, size, max_price)  → list[dict]
    suggest_outfit(new_item, wardrobe)              → str
    create_fit_card(outfit, new_item)               → str
"""

import os
import re

from dotenv import load_dotenv
from groq import Groq

from utils.data_loader import load_listings

load_dotenv()

# Model used for the two LLM-backed tools.
# The Milestone 3 handout named "meta-llama/llama-4-scout-17b-16e-instruct", but
# Groq no longer serves that model (404 model_not_found). "openai/gpt-oss-120b"
# is a current Groq chat model and is what this project uses. See the Spec
# Reflection in README.md.
_MODEL = "openai/gpt-oss-120b"

# Tokens that carry no search signal — dropped before keyword scoring so a
# query like "vintage graphic tee under $30" scores on {vintage, graphic, tee}.
_STOPWORDS = {
    "a", "an", "the", "for", "with", "and", "or", "to", "in", "of", "on",
    "under", "over", "size", "sized", "price", "cheap", "looking", "look",
    "want", "wanted", "need", "find", "me", "my", "i", "im", "some", "any",
    "that", "this", "is", "are", "at", "up", "dollars", "dollar", "bucks",
}


# ── Groq client ───────────────────────────────────────────────────────────────

def _get_groq_client():
    """Initialize and return a Groq client using GROQ_API_KEY from .env."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY not set. Add it to a .env file in the project root."
        )
    return Groq(api_key=api_key)


def _chat(prompt: str, temperature: float) -> str:
    """
    Send a single user prompt to the LLM and return the response text.

    Raised exceptions (missing key, network, rate limit) are the caller's
    responsibility to catch — the two tools below wrap this in try/except.
    """
    client = _get_groq_client()
    response = client.chat.completions.create(
        model=_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
    )
    return response.choices[0].message.content.strip()


# ── Tool 1: search_listings ───────────────────────────────────────────────────

def _tokenize(text: str) -> list[str]:
    """Lowercase, split on non-alphanumerics, drop stopwords and bare numbers."""
    raw = re.split(r"[^a-z0-9]+", text.lower())
    return [t for t in raw if t and t not in _STOPWORDS and not t.isdigit()]


def _searchable_text(listing: dict) -> str:
    """Flatten the fields worth matching against into one lowercase string."""
    parts = [
        listing.get("title", ""),
        listing.get("description", ""),
        listing.get("category", ""),
        listing.get("brand") or "",
        " ".join(listing.get("style_tags", [])),
        " ".join(listing.get("colors", [])),
    ]
    return " ".join(parts).lower()


def search_listings(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
) -> list[dict]:
    """
    Search the mock listings dataset for items matching the description,
    optional size, and optional price ceiling.

    Args:
        description: Keywords describing what the user is looking for
                     (e.g., "vintage graphic tee").
        size:        Size string to filter by, or None to skip size filtering.
                     Matching is case-insensitive (e.g., "M" matches "S/M").
        max_price:   Maximum price (inclusive), or None to skip price filtering.

    Returns:
        A list of matching listing dicts, sorted by relevance (best match first).
        Returns an empty list if nothing matches — does NOT raise an exception.

    Each listing dict has the following fields:
        id, title, description, category, style_tags (list), size,
        condition, price (float), colors (list), brand, platform

    TODO:
        1. Load all listings with load_listings().
        2. Filter by max_price and size (if provided).
        3. Score each remaining listing by keyword overlap with `description`.
        4. Drop any listings with a score of 0 (no relevant matches).
        5. Sort by score, highest first, and return the listing dicts.
    """
    listings = load_listings()
    query_tokens = _tokenize(description or "")

    size_filter = size.strip().lower() if size else None

    scored: list[tuple[int, float, dict]] = []
    for listing in listings:
        # 2a. price ceiling
        if max_price is not None and listing.get("price", 0) > max_price:
            continue

        # 2b. size (case-insensitive substring: "m" matches "s/m")
        if size_filter and size_filter not in str(listing.get("size", "")).lower():
            continue

        # 3. keyword score — count distinct query tokens that appear, with a
        #    small bonus for hits in the high-signal title / style_tags fields.
        text = _searchable_text(listing)
        tags = " ".join(listing.get("style_tags", [])).lower()
        title = listing.get("title", "").lower()
        score = 0
        for token in set(query_tokens):
            if token in text:
                score += 1
                if token in title:
                    score += 2
                if token in tags:
                    score += 1

        # 4. drop listings with no keyword overlap
        if score > 0:
            scored.append((score, listing.get("price", 0.0), listing))

    # 5. best score first; cheaper item breaks ties
    scored.sort(key=lambda row: (-row[0], row[1]))
    return [listing for _, _, listing in scored]


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

def _format_item(item: dict) -> str:
    """One-line description of the thrifted item for a prompt."""
    return (
        f"{item.get('title', 'Unknown item')} "
        f"(category: {item.get('category', 'n/a')}, "
        f"style: {', '.join(item.get('style_tags', [])) or 'n/a'}, "
        f"colors: {', '.join(item.get('colors', [])) or 'n/a'}, "
        f"condition: {item.get('condition', 'n/a')})"
    )


def _format_wardrobe(wardrobe: dict) -> str:
    """Bulleted list of wardrobe pieces for a prompt."""
    lines = []
    for w in wardrobe.get("items", []):
        note = f" — {w['notes']}" if w.get("notes") else ""
        lines.append(
            f"- {w.get('name', 'unnamed')} "
            f"({w.get('category', 'n/a')}; "
            f"{', '.join(w.get('colors', [])) or 'n/a'}; "
            f"{', '.join(w.get('style_tags', [])) or 'n/a'}){note}"
        )
    return "\n".join(lines)


def suggest_outfit(new_item: dict, wardrobe: dict) -> str:
    """
    Given a thrifted item and the user's wardrobe, suggest 1–2 complete outfits.

    Args:
        new_item: A listing dict (the item the user is considering buying).
        wardrobe: A wardrobe dict with an 'items' key containing a list of
                  wardrobe item dicts. May be empty — handle this gracefully.

    Returns:
        A non-empty string with outfit suggestions.
        If the wardrobe is empty, offer general styling advice for the item
        rather than raising an exception or returning an empty string.
        On an LLM/network failure, returns a string beginning with
        "[suggest_outfit error]" instead of raising.

    TODO:
        1. Check whether wardrobe['items'] is empty.
        2. If empty: call the LLM with a prompt for general styling ideas.
        3. If not empty: format the wardrobe items into a prompt and ask
           the LLM to suggest specific outfit combinations.
        4. Return the LLM's response as a string.
    """
    item_desc = _format_item(new_item)
    items = (wardrobe or {}).get("items", [])

    if not items:
        # 2. empty-wardrobe branch — general styling advice, no crash
        prompt = (
            "A shopper is considering buying this secondhand item but hasn't "
            "told us anything about their existing wardrobe:\n\n"
            f"ITEM: {item_desc}\n\n"
            "Give general styling advice for this piece in 4-6 sentences: what "
            "categories, colors, and silhouettes pair well with it, what overall "
            "vibe it suits, and one specific example outfit someone could build "
            "around it. Do not invent specific items the shopper owns."
        )
    else:
        # 3. wardrobe branch — concrete combinations using named pieces
        prompt = (
            "A shopper is considering buying this secondhand item:\n\n"
            f"NEW ITEM: {item_desc}\n\n"
            "Here is their current wardrobe:\n"
            f"{_format_wardrobe(wardrobe)}\n\n"
            "Suggest 1-2 complete outfits that combine the NEW ITEM with "
            "specific pieces from their wardrobe. Refer to wardrobe pieces by "
            "name. For each outfit give a one-line name, the pieces used, and a "
            "sentence on why it works. Keep it under 150 words."
        )

    try:
        result = _chat(prompt, temperature=0.7)
    except Exception as exc:  # missing key, network, rate limit, bad response
        return f"[suggest_outfit error] Could not generate outfit ideas: {exc}"

    return result or "[suggest_outfit error] The model returned an empty response."


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

def create_fit_card(outfit: str, new_item: dict) -> str:
    """
    Generate a short, shareable outfit caption for the thrifted find.

    Args:
        outfit:   The outfit suggestion string from suggest_outfit().
        new_item: The listing dict for the thrifted item.

    Returns:
        A 2–4 sentence string usable as an Instagram/TikTok caption.
        If outfit is empty or missing, returns a descriptive error message
        string beginning with "[create_fit_card error]" — does NOT raise.

    TODO:
        1. Guard against an empty or whitespace-only outfit string.
        2. Build a prompt with the item details and the outfit.
        3. Call the LLM and return the response.
    """
    # 1. guard — no LLM call if there's no outfit to caption
    if not isinstance(outfit, str) or not outfit.strip():
        return (
            "[create_fit_card error] No outfit was provided, so there's nothing "
            "to write a caption about. Run suggest_outfit first."
        )

    title = new_item.get("title", "this find")
    price = new_item.get("price")
    price_str = f"${price:g}" if isinstance(price, (int, float)) else "a steal"
    platform = new_item.get("platform", "secondhand")

    # 2. prompt
    prompt = (
        "Write a caption for an outfit-of-the-day social post about a "
        "secondhand fashion find. Style guidelines:\n"
        "- 2 to 4 sentences, casual and authentic, like a real person's post\n"
        "- NOT a product description\n"
        f"- mention the item name (\"{title}\"), the price ({price_str}), and "
        f"the platform ({platform}) naturally, once each\n"
        "- capture the outfit's vibe in specific terms\n"
        "- a couple of tasteful hashtags at the end are fine\n\n"
        f"THE ITEM: {_format_item(new_item)}\n"
        f"THE OUTFIT: {outfit}\n"
    )

    # 3. call the LLM — higher temperature so repeated calls vary
    try:
        result = _chat(prompt, temperature=1.0)
    except Exception as exc:
        return f"[create_fit_card error] Could not generate a caption: {exc}"

    return result or "[create_fit_card error] The model returned an empty response."


# ── manual isolation checks (run: python tools.py) ────────────────────────────

if __name__ == "__main__":
    from utils.data_loader import get_example_wardrobe, get_empty_wardrobe

    print("── search_listings ──")
    hits = search_listings("vintage graphic tee", size=None, max_price=30)
    print(f"{len(hits)} hits; top: {hits[0]['title']} (${hits[0]['price']})")
    print("empty case:", search_listings("designer ballgown", "XXS", 5))

    print("\n── suggest_outfit (empty wardrobe) ──")
    print(suggest_outfit(hits[0], get_empty_wardrobe())[:400])

    print("\n── suggest_outfit (example wardrobe) ──")
    outfit = suggest_outfit(hits[0], get_example_wardrobe())
    print(outfit[:400])

    print("\n── create_fit_card ──")
    print("guard case:", create_fit_card("", hits[0]))
    print(create_fit_card(outfit, hits[0]))
