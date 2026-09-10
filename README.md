# FitFindr — Starter Kit

This starter kit contains everything you need to begin Project 2.

## What's Included

```
ai201-project2-fitfindr-starter/
├── data/
│   ├── listings.json          # 40 mock secondhand listings
│   └── wardrobe_schema.json   # Wardrobe format + example wardrobe
├── utils/
│   └── data_loader.py         # Helper functions for loading the data
├── planning.md                # Your planning template — fill this out first
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

## The Mock Listings Dataset

`data/listings.json` contains 40 mock secondhand listings across categories (tops, bottoms, outerwear, shoes, accessories) and styles (vintage, y2k, grunge, cottagecore, streetwear, and more).

Each listing has: `id`, `title`, `description`, `category`, `style_tags`, `size`, `condition`, `price`, `colors`, `brand`, and `platform`.

Load it with:
```python
from utils.data_loader import load_listings
listings = load_listings()
```

## The Wardrobe Schema

`data/wardrobe_schema.json` defines the format your agent uses to represent a user's existing wardrobe. It includes:

- `schema`: field definitions for a wardrobe item
- `example_wardrobe`: a sample wardrobe with 10 items you can use for testing
- `empty_wardrobe`: a starting template for a new user

Load an example wardrobe with:
```python
from utils.data_loader import get_example_wardrobe
wardrobe = get_example_wardrobe()
```

## Tool Inventory

Your README submission must document each tool's name, inputs, and return value. **These must exactly match your actual function signatures in `tools.py`.** Your documented interfaces will be checked against your actual function signatures in `tools.py` — if the parameter count or types contradict what's in the code, you may not receive full credit for that tool.

---

## Interaction Walkthrough

<!-- Walk through a complete interaction step by step: natural language query → each tool call (and why) → final fit card.
     Walk through this carefully — it's how graders follow your agent's reasoning without a live demo.
     Use a specific example — do not leave this as a template. -->

**User query:**

**Step 1 — Tool called:**
- Tool:
- Input:
- Why this tool:
- Output:

**Step 2 — Tool called:**
- Tool:
- Input:
- Why this tool:
- Output:

**Step 3 — Tool called:**
- Tool:
- Input:
- Why this tool:
- Output:

**Final output to user:**

---

## Error Handling and Fail Points

<!-- For each tool, describe the specific failure mode and what your agent does in response.
     This maps to the error handling section of the rubric (F5-C1). -->

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
written contract instead of a vague idea. The failure-mode column in particular
forced the `"[tool_name error] …"` string convention to be decided up front —
which is what lets the planning loop branch on `str.startswith(...)` instead of
catching exceptions across module boundaries. The Planning Loop → tool-sequence
table also became the test plan for `tests/test_agent.py` almost verbatim.

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

## Where to Start

1. **Read `planning.md` and fill it out before writing any code.**
2. Verify the data loads correctly by running `python utils/data_loader.py`.
3. Build and test each tool individually before connecting them through your planning loop.

Your implementation files go in this same directory. There's no required file structure for your agent code — organize it however makes sense for your design.
