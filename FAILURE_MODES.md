# FitFindr — Deliberately Triggered Failure Modes (Milestone 5)

Every failure mode below was triggered on purpose from the terminal and the
output captured verbatim. Each one produces a **specific, informative response**
— never an unhandled Python exception, never a bare "no results".

Automated equivalents live in [`tests/test_failure_modes.py`](tests/test_failure_modes.py)
(`python -m pytest tests/test_failure_modes.py -v`) — 9 tests, all passing, none
needs a valid API key.

---

## Failure 1 — `search_listings` returns zero results

**Trigger (tool in isolation):**
```bash
python -c "from tools import search_listings; print(search_listings('designer ballgown', size='XXS', max_price=5))"
```
**Output:**
```
[]
```
Returns an empty list. No exception. (There is no ballgown in the 40-item
dataset, and the `XXS` / `$5` filters make it doubly impossible.)

**Trigger (full agent, same impossible query):**
```bash
python -c "
from agent import run_agent
from utils.data_loader import get_example_wardrobe
s = run_agent('designer ballgown size XXS under \$5', get_example_wardrobe())
print('error:', s['error'])
print('outfit_suggestion:', s['outfit_suggestion'])
print('fit_card:', s['fit_card'])
"
```
**Output:**
```
error: No listings matched "designer ballgown" (size XXS, under $5). Try broader keywords, a wider size, or a higher price ceiling.
outfit_suggestion: None
fit_card: None
```
**Agent behaviour:** the planning loop tried **one** relaxed retry (dropped the
`XXS` filter), still got nothing, then set `session["error"]` to a message that
names *what* was searched, *which filters* were applied, and *three concrete
things to try*. `suggest_outfit` and `create_fit_card` were never called —
`session["steps"]` records `"STOP: no results — suggest_outfit and
create_fit_card were not called"`.

---

## Failure 2 — `suggest_outfit` with an empty wardrobe

**Trigger:**
```bash
python -c "
from tools import search_listings, suggest_outfit
from utils.data_loader import get_example_wardrobe, get_empty_wardrobe
results = search_listings('vintage graphic tee', size=None, max_price=50)
print(suggest_outfit(results[0], get_empty_wardrobe()))
"
```
**Output (abridged):**
```
Pair the faded-grey vintage band tee with relaxed-fit denim—think straight-leg or
slightly tapered black or indigo jeans—to keep the grunge vibe grounded while
letting the graphic remain the focal point. Layering a lightweight, oversized
flannel shirt or a distressed leather jacket in muted earth tones (olive, rust,
or deep brown) adds texture and depth... An example outfit could be the band tee
tucked into black skinny jeans, topped with a dark green oversized flannel,
finished with black combat boots and a silver pendant.
```
**Behaviour:** `wardrobe["items"]` is empty, so the tool takes its
**general-styling-advice branch** instead of trying to name pieces the user
doesn't have. Returns a long, useful string — not `""`, not an exception. The
agent continues normally to `create_fit_card`.

---

## Failure 3 — `create_fit_card` with an empty outfit string

**Trigger:**
```bash
python -c "
from tools import search_listings, create_fit_card
results = search_listings('vintage graphic tee', size=None, max_price=50)
print(create_fit_card('', results[0]))
"
```
**Output:**
```
[create_fit_card error] No outfit was provided, so there's nothing to write a caption about. Run suggest_outfit first.
```
**Behaviour:** the guard clause catches the empty string **before any LLM call**
and returns a descriptive error string that says exactly what's missing and what
to do. No exception, no wasted API call.

---

## Failure 4 — LLM / network failure (invalid API key)

**Trigger (tool in isolation):**
```bash
GROQ_API_KEY=gsk_invalid_key_for_testing python -c "
from tools import search_listings, suggest_outfit
from utils.data_loader import get_example_wardrobe
r = search_listings('vintage graphic tee', size=None, max_price=50)
print(suggest_outfit(r[0], get_example_wardrobe()))
"
```
**Output:**
```
[suggest_outfit error] Could not generate outfit ideas: Error code: 401 - {'error': {'message': 'Invalid API Key', 'type': 'invalid_request_error', 'code': 'invalid_api_key'}}
```
The `try/except` around the Groq call caught the 401 and turned it into a string.

**Trigger (full agent):**
```bash
GROQ_API_KEY=gsk_invalid_key_for_testing python -c "
from agent import run_agent
from utils.data_loader import get_example_wardrobe
print(run_agent('vintage graphic tee under \$30', get_example_wardrobe())['error'])
"
```
**Output:**
```
Found "Vintage Band Tee — Faded Grey" ($19 on depop), but the styling step is
unavailable right now, so there's no outfit or fit card yet. Your search worked —
try again in a moment. (Technical detail: Could not generate outfit ideas: Error
code: 401 - {'error': {'message': 'Invalid API Key', ...}})
```
**Agent behaviour:** step 5b sees the `"[suggest_outfit error]"` prefix, so it
**does not call `create_fit_card`**, and rewrites the raw error into a
user-facing message: what still worked (the search + the found item), what
failed (styling), and what to do (try again shortly). The raw technical detail
is kept in parentheses for debugging.

---

## Checkpoint

| # | Failure mode | Triggered by | Result | Exception? |
|---|--------------|--------------|--------|:---:|
| 1 | `search_listings` → 0 results | impossible query | `[]`; agent gives query + filters + 3 things to try | No |
| 2 | `suggest_outfit` → empty wardrobe | `get_empty_wardrobe()` | general styling advice string | No |
| 3 | `create_fit_card` → empty outfit | `create_fit_card("", item)` | `"[create_fit_card error] ... Run suggest_outfit first."` | No |
| 4 | `suggest_outfit` / `create_fit_card` → LLM down | invalid `GROQ_API_KEY` | `"[tool error] ..."`; agent stops the funnel + actionable message | No |

All four produce a specific, informative response. The screenshot for the demo
video is [`docs/failure-mode-demo.png`](docs/failure-mode-demo.png).
