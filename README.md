# FitFindr

FitFindr is a small planning-loop agent: describe a secondhand piece you want
in plain English, and it searches a mock listings dataset, builds an outfit
around the best match using your existing wardrobe, and writes a shareable
"fit card" caption — all through a Gradio UI.

**Demo video:** _[add your recorded demo link here before submitting]_

---

## What's Included

```
ai201-project2-fitfindr-starter/
├── data/
│   ├── listings.json          # 40 mock secondhand listings
│   └── wardrobe_schema.json   # Wardrobe format + example wardrobe
├── utils/
│   └── data_loader.py         # Helper functions for loading the data
├── tools.py                   # The 3 required tools
├── agent.py                   # The planning loop (run_agent)
├── app.py                     # Gradio UI (handle_query)
├── tests/                     # pytest suite (tools, loop, failure modes)
├── planning.md                # Design spec, written before implementation
├── FAILURE_MODES.md           # Deliberately triggered failures + output
└── requirements.txt           # Python dependencies
```

## Setup

**macOS / Linux:**
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**Windows:**
```bash
python -m venv .venv
source .venv/Scripts/activate
pip install -r requirements.txt
```

Set your Groq API key in a `.env` file (get a free key at [console.groq.com](https://console.groq.com)):
```
GROQ_API_KEY=your_key_here
```

## Running the App

```bash
python app.py
```

Open the URL printed in the terminal (usually `http://localhost:7860`, but
check the output — the port can differ). Type a query like `vintage graphic
tee under $30`, pick a wardrobe, and click **Find it**. All three panels
(listing, outfit, fit card) populate from one query.

## Running the Tests

```bash
python -m pytest tests/
```
20 of the 28 tests need no API key (pure logic + monkeypatched LLM calls); the
rest exercise the real Groq calls and are skipped automatically without a key.

---

## The Mock Listings Dataset

`data/listings.json` contains 40 mock secondhand listings across categories
(tops, bottoms, outerwear, shoes, accessories) and styles (vintage, y2k,
grunge, cottagecore, streetwear, and more). Each listing has: `id`, `title`,
`description`, `category`, `style_tags`, `size`, `condition`, `price`,
`colors`, `brand`, and `platform`.

## The Wardrobe Schema

`data/wardrobe_schema.json` defines the format used to represent a user's
existing wardrobe: `schema` (field definitions), `example_wardrobe` (10 sample
items), and `empty_wardrobe` (starting template for a new user).

---

## Tool Inventory

All three tools live in `tools.py`. Signatures below are copied from the code
— see `planning.md` for the full spec each was implemented against.

### 1. `search_listings(description, size=None, max_price=None)`

- **Purpose:** searches the 40-item mock dataset for listings matching free-text
  keywords, then filters by size and price and ranks by keyword relevance.
- **Inputs:**
  - `description` (str) — required. Keywords describing the item, e.g.
    `"vintage graphic tee"`.
  - `size` (str, optional, default `None`) — a size to filter by, e.g. `"M"`.
    Matching is case-insensitive substring, so `"M"` matches a listing sized
    `"S/M"`. `None` skips size filtering.
  - `max_price` (float, optional, default `None`) — inclusive price ceiling.
    `None` skips price filtering.
- **Returns:** `list[dict]` — matching listing dicts, best keyword match first.
  Each dict has `id` (str), `title` (str), `description` (str), `category`
  (str), `style_tags` (list[str]), `size` (str), `condition` (str), `price`
  (float), `colors` (list[str]), `brand` (str or `None`), `platform` (str).
  Returns `[]` when nothing matches — never raises.

### 2. `suggest_outfit(new_item, wardrobe)`

- **Purpose:** proposes 1–2 complete outfits combining the thrifted item with
  the user's existing wardrobe, or general styling advice if they have none
  entered yet. Calls the Groq LLM.
- **Inputs:**
  - `new_item` (dict) — required. A listing dict (typically
    `search_listings()`'s top result) — the item being styled.
  - `wardrobe` (dict) — required. A wardrobe dict with an `"items"` key holding
    a list of wardrobe-item dicts (`name`, `category`, `colors`, `style_tags`,
    `notes`). May be `{"items": []}`.
- **Returns:** `str` — a non-empty string. With a populated wardrobe: 1–2
  named outfits referencing specific wardrobe pieces. With an empty wardrobe:
  general styling advice for the item. On an LLM/network failure: a string
  starting with `"[suggest_outfit error] ..."` — never raises.

### 3. `create_fit_card(outfit, new_item)`

- **Purpose:** turns the outfit suggestion + item details into a short,
  casual, shareable social caption. Calls the Groq LLM at a higher temperature
  so repeated calls on the same input vary.
- **Inputs:**
  - `outfit` (str) — required. The outfit-suggestion string from
    `suggest_outfit()`. Must be non-empty/non-whitespace.
  - `new_item` (dict) — required. The listing dict for the item — its title,
    price, and platform are woven into the caption once each.
- **Returns:** `str` — a 2–4 sentence caption. If `outfit` is empty/whitespace,
  returns `"[create_fit_card error] No outfit was provided..."` with **no LLM
  call made**. On an LLM/network failure: `"[create_fit_card error] ..."`.
  Never raises.

**Model note:** both LLM tools use Groq's `openai/gpt-oss-120b`. The
Milestone 3 handout specified `meta-llama/llama-4-scout-17b-16e-instruct`,
which Groq no longer serves (`404 model_not_found`) — see Spec Reflection below.

---

## How the Planning Loop Works

The loop (`run_agent()` in `agent.py`) is **not** a fixed "call all three
tools" pipeline. After each tool call it inspects the result and branches:

1. **Parse** the query with regex (`_parse_query()`) into `description`,
   `size`, `max_price`. Regex was chosen over an LLM parse so it's
   deterministic, free, and unit-testable.
2. **`search_listings`** always runs first — nothing downstream is useful
   without a real item.
3. **Branch on result count:**
   - **Zero results** → `_relax_constraints()` loosens the single most
     restrictive optional filter (drops `size` first, else raises `max_price`
     by 1.5×) and retries **once**. Still zero → the loop sets
     `session["error"]` to a message naming the query, the filters applied,
     and concrete things to try, and **returns immediately**.
     `suggest_outfit` and `create_fit_card` are never called.
   - **One or more results** → continue.
4. **Select** the top-ranked result as `session["selected_item"]`.
5. **`suggest_outfit`** runs with that item + the wardrobe. The tool itself
   branches internally on whether the wardrobe is empty.
6. **Branch on the outfit string:** if it starts with `"[suggest_outfit
   error]"`, the loop rewrites it into a user-facing message (what worked, what
   failed, what to try) and **returns** — `create_fit_card` is never called.
7. **`create_fit_card`** runs with the outfit + item. If *this* fails, it's
   **non-fatal** — the error string is stored in `session["fit_card"]` but
   `session["error"]` stays `None`, because the listing and outfit are still
   valid output.
8. **Done** — return the completed session.

**Different inputs genuinely produce different tool sequences:**

| Input | search | retry | suggest_outfit | create_fit_card |
|-------|:---:|:---:|:---:|:---:|
| "vintage graphic tee under $30" (happy path) | ✓ 21 hits | – | ✓ | ✓ |
| "designer ballgown size XXS under $5" (no match) | ✓ 0 | ✓ still 0 | ✗ skipped | ✗ skipped |
| "combat boots size 99" (bad size) | ✓ 0 | ✓ drops size, finds matches | ✓ | ✓ |
| happy path, Groq down | ✓ | – | ✓ → error string | ✗ skipped |

## State Management

A single **session dict**, created once at the top of `run_agent()`, is the
one source of truth for the interaction — nothing lives in globals, and the
user supplies the query exactly once (the function argument) and is never
re-prompted mid-loop.

| Key | Written by | Read by |
|-----|-----------|---------|
| `parsed` (`{description, size, max_price}`) | the regex parser | `search_listings` call |
| `search_results` (`list[dict]`) | `search_listings` (+ retry) | the branch check, item selection |
| `selected_item` (`dict`) | "select top result" step | **`suggest_outfit` and `create_fit_card`** |
| `wardrobe` (`dict`) | set at session creation | `suggest_outfit` |
| `outfit_suggestion` (`str`) | `suggest_outfit` | the branch check, **`create_fit_card`** |
| `fit_card` (`str`) | `create_fit_card` | the UI |
| `error` (`str \| None`) | any early-return branch | the UI (checked first) |
| `steps` (`list[str]`) | every step | debugging / demo narration |

The key point: `session["selected_item"]` is passed **by reference** into
both `suggest_outfit()` and `create_fit_card()` — it is the exact same dict
object each time, not a re-fetched or re-typed copy. This was verified with an
`id()` check:

```
id(session["selected_item"])        = 4388424512
id(item passed into suggest_outfit) = 4388424512
id(item passed into create_fit_card)= 4388424512
```

Likewise, the exact string `suggest_outfit()` returns is what `create_fit_card()`
receives (`session["outfit_suggestion"]` passed by reference). `tests/test_agent.py`
has this as an automated monkeypatched test, not just a one-off check.

---

## Interaction Walkthrough

**User query:** _"I'm looking for a vintage graphic tee under $30. I mostly
wear baggy jeans and chunky sneakers. What's out there and how would I style
it?"_

Parsed to `{description: "a vintage graphic tee baggy jeans and chunky
sneakers", size: None, max_price: 30.0}`.

**Step 1 — Tool called:**
- Tool: `search_listings`
- Input: `("a vintage graphic tee baggy jeans and chunky sneakers", None, 30.0)`
- Why this tool: we need a real listing before anything else can happen.
- Output: 21 listing dicts, best match first. Top result: *Vintage Band Tee —
  Faded Grey*, $19, size L, depop.

**Step 2 — Tool called:**
- Tool: `suggest_outfit`
- Input: the exact `selected_item` dict from Step 1, plus the 10-item example
  wardrobe.
- Why this tool: the user explicitly asked "how would I style it", and we now
  have a real item + their wardrobe to work with.
- Output:
  > **Grunge Street Remix** – Vintage Band Tee + Baggy straight-leg jeans +
  > Black cropped zip hoodie + Black combat boots + Brown leather belt + Black
  > crossbody bag. The faded-grey tee anchors the dark, baggy denim...
  >
  > **Minimalist Retro Layer** – Vintage Band Tee + Wide-leg khaki trousers +
  > Vintage black denim jacket + Chunky white sneakers + Black crossbody bag...

**Step 3 — Tool called:**
- Tool: `create_fit_card`
- Input: the outfit string from Step 2, plus the *same* `selected_item` dict
  from Step 1 (not re-fetched).
- Why this tool: turn the styled look into something shareable.
- Output:
  > Scored this Vintage Band Tee — Faded Grey for $19 on depop and paired it
  > with baggy straight-leg jeans, a black cropped zip hoodie, and combat
  > boots for a full-on grunge street remix. The muted grey shirt anchors the
  > dark layers while the belt and crossbody keep the vibe rugged and
  > functional. Feeling like I'm straight out of a '90s music video today.
  > #grunge #secondhandstyle

**Final output to user (3 Gradio panels):** the listing details, the two named
outfits, and the caption above. `session["error"]` is `None` throughout.

**Contrast — no-results branch:** for *"designer ballgown size XXS under $5"*,
Step 1 returns `[]`, the loop retries once after dropping the size filter,
still gets `[]`, and returns with `session["error"] = 'No listings matched
"designer ballgown" (size XXS, under $5). Try broader keywords, a wider size,
or a higher price ceiling.'` — Steps 2 and 3 never run.

---

## Error Handling and Fail Points

Every failure mode below was triggered on purpose and the output captured in
[`FAILURE_MODES.md`](FAILURE_MODES.md); automated versions are in
[`tests/test_failure_modes.py`](tests/test_failure_modes.py) (9 tests, passing).

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| `search_listings` | Query + filters match nothing in the 40-item dataset (returns `[]`, never raises) | Planning loop makes **one** relaxed retry (drops `size`, else raises `max_price` 1.5×). Still empty → sets `session["error"]` naming the keywords, the applied filters, and three fixes ("broader keywords, a wider size, or a higher price ceiling"), then returns. `suggest_outfit` / `create_fit_card` are **not** called. |
| `suggest_outfit` | `wardrobe["items"]` is empty | Not treated as an error — the tool switches to its general-styling-advice prompt and returns a full advice string. The loop continues to `create_fit_card` normally. |
| `suggest_outfit` | Groq call fails (invalid key, network, rate limit) | Tool catches it and returns `"[suggest_outfit error] …"`. The loop detects the prefix, **skips `create_fit_card`**, and rewrites it into an actionable message: what still worked (search + found item), what failed (styling), what to do ("try again in a moment"), with the raw error kept in parentheses. |
| `create_fit_card` | `outfit` is empty / whitespace / not a string | Guard clause returns `"[create_fit_card error] No outfit was provided… Run suggest_outfit first."` **before any LLM call**. No exception, no wasted request. |
| `create_fit_card` | Groq call fails | Tool returns `"[create_fit_card error] …"`. **Non-fatal** — the loop keeps `session["error"] = None` and still returns the listing + outfit; the UI shows the caption panel with a "couldn't generate a caption this time" note. |

**Concrete example from testing** (from `FAILURE_MODES.md`, Failure 4):

```
$ GROQ_API_KEY=gsk_invalid_key_for_testing python -c "from agent import run_agent;
  from utils.data_loader import get_example_wardrobe;
  print(run_agent('vintage graphic tee under $30', get_example_wardrobe())['error'])"

Found "Vintage Band Tee — Faded Grey" ($19 on depop), but the styling step is
unavailable right now, so there's no outfit or fit card yet. Your search worked —
try again in a moment. (Technical detail: Could not generate outfit ideas:
Error code: 401 - {'error': {'message': 'Invalid API Key', ...}})
```

`create_fit_card` was never reached — `session["steps"]` ends with
`"STOP: suggest_outfit failed — create_fit_card was not called"`.

---

## Spec Reflection

**One way planning.md helped during implementation:**
Writing the Tool specs (typed inputs, exact return contents, failure mode) and
the Planning Loop branch logic *before* coding meant each tool and the loop
could be handed to an AI tool one spec block at a time and verified against a
written contract instead of a vague idea. The failure-mode column in
particular forced the `"[tool_name error] …"` string convention to be decided
up front — which is what lets the planning loop branch on `str.startswith(...)`
instead of catching exceptions across module boundaries. The Planning Loop →
tool-sequence table also became the test plan for `tests/test_agent.py` almost
verbatim.

**One divergence from your spec, and why:**
The Milestone 3 handout specified the LLM model
`meta-llama/llama-4-scout-17b-16e-instruct`, but Groq no longer serves it
(`404 model_not_found`), so both LLM tools use `openai/gpt-oss-120b`, a current
Groq chat model. The tool interfaces, prompts, and error handling are unchanged
— only the model id string differs. A second, smaller divergence: the spec's
no-results handling was "stop and tell the user"; the implementation adds one
automatic relaxed-constraint retry first, because for queries like "boots size
99" the user almost certainly wants the size loosened, and telling them so
("retried after dropping the size filter") is more helpful than a dead end.

---

## AI Usage Transparency

I used Claude (Claude Code) throughout implementation, one spec block at a
time rather than "write the whole project." Two specific instances:

**1. Implementing the three tools (Milestone 3).** I gave Claude the Tool 1/2/3
spec blocks from `planning.md` (what each does, parameter names + types,
return contents, failure mode) one at a time and asked it to implement that
function in `tools.py`. I reviewed each generated function against its spec
before trusting it — checking parameter names/types matched, and that the
failure mode was actually handled. When I ran the generated `suggest_outfit`
against a real Groq key it returned a 404 for the model named in the handout
spec (`meta-llama/llama-4-scout-17b-16e-instruct`); I directed Claude to check
which models the key could actually access and switch both LLM tools to
`openai/gpt-oss-120b` instead — I did not accept the first version as-is.

**2. Implementing the planning loop (Milestone 4).** I gave Claude the full
Planning Loop and State Management sections of `planning.md` plus the Mermaid
architecture diagram and asked it to implement `run_agent()` to match. The
first thing I checked was whether the loop actually branched instead of
running all three tools unconditionally — I had Claude add an explicit `id()`
identity check proving `session["selected_item"]` is the *same object* passed
into both downstream tools, not a re-fetched copy, before accepting the
implementation. I also directed a revision after Milestone 5 testing: the
initial LLM-failure path surfaced the raw `"[suggest_outfit error] Error code:
401 ..."` string straight to the user, which isn't actionable — I asked Claude
to rewrite that branch to state what still worked, what failed, and what to
try next, keeping the raw error only as a parenthetical detail.

In both cases the generated code was locked in with pytest tests
(`tests/test_tools.py`, `tests/test_agent.py`, `tests/test_failure_modes.py`)
before being trusted, not just eyeballed.

---

## Demo Video

**Link:** _[add here once recorded]_

The recording shows:
1. A complete interaction from a natural-language query to a fit card, using
   all 3 required tools.
2. State visibly passing between tools (the same item and outfit text carried
   forward with no re-entry).
3. At least one deliberately triggered failure and the agent's graceful,
   informative response.
