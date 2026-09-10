# FitFindr — planning.md

> Complete this document before writing any implementation code.
> Your spec and agent diagram are what you'll use to direct AI tools (Claude, Copilot, etc.) to generate your implementation — the more specific they are, the more useful the generated code will be.
> Your planning.md will be reviewed as part of your submission.
> Update it before starting any stretch features.

---

## Tools

List every tool your agent will use. For each tool, fill in all four fields.
You must have at least 3 tools. The three required tools are listed — add any additional tools below them.

### Tool 1: search_listings

**What it does:**
Searches the 40-item mock listings dataset for secondhand pieces that match the
user's keywords, and (optionally) filters those matches by size and by a maximum
price. It ranks the survivors by how well their text matches the keywords and
returns the best matches first.

**Input parameters:**
- `description` (str): free-text keywords describing the item the user wants,
  e.g. `"vintage graphic tee"`. Required. Tokenized and matched against each
  listing's title, description, style_tags, category, brand, and colors.
- `size` (str | None): a size string to filter by, e.g. `"M"`. Optional —
  pass `None` to skip size filtering. Matching is case-insensitive and
  substring-based, so `"M"` matches a listing sized `"S/M"`.
- `max_price` (float | None): inclusive price ceiling in dollars, e.g. `30.0`.
  Optional — pass `None` to skip price filtering.

**What it returns:**
`list[dict]` — a list of matching listing dicts, sorted by keyword-match score
(highest first). Each dict has: `id` (str), `title` (str), `description` (str),
`category` (str), `style_tags` (list[str]), `size` (str), `condition` (str),
`price` (float), `colors` (list[str]), `brand` (str | None), `platform` (str).
Returns `[]` (empty list) when nothing matches — never raises.

**What happens if it fails or returns nothing:**
Returns an empty list rather than raising. The planning loop treats an empty
list as a stop condition: it does NOT call `suggest_outfit`, and instead ends
the interaction early with an actionable message telling the user which
constraints (keywords / size / price) were applied and suggesting they loosen
one (raise `max_price`, drop the size, or use broader keywords).

---

### Tool 2: suggest_outfit

**What it does:**
Takes the thrifted item the user is considering plus the user's existing
wardrobe and asks the LLM (Groq `openai/gpt-oss-120b` — the handout's
`meta-llama/llama-4-scout-17b-16e-instruct` is no longer served by Groq)
to propose 1–2 complete, wearable outfits. When the wardrobe is empty it
switches to giving general styling advice for the item instead.

**Input parameters:**
- `new_item` (dict): a single listing dict from `search_listings` — the item
  being styled. Its `title`, `category`, `style_tags`, `colors`, and `condition`
  are formatted into the prompt.
- `wardrobe` (dict): a wardrobe dict with an `"items"` key holding a list of
  wardrobe-item dicts (`name`, `category`, `colors`, `style_tags`, `notes`).
  May be `{"items": []}` — handled as the empty-wardrobe case.

**What it returns:**
`str` — a non-empty, human-readable string. With a populated wardrobe it names
1–2 outfits that pair `new_item` with specific pieces from the wardrobe (by
name). With an empty wardrobe it returns general styling guidance (what
categories/colors/silhouettes pair well, what vibe it suits). On an LLM/network
failure it returns a plain-text error string beginning with `"[suggest_outfit
error]"` — it never raises.

**What happens if it fails or returns nothing:**
- Empty wardrobe → general styling advice branch (still a useful non-empty
  string; the agent continues to `create_fit_card`).
- LLM call raises (bad key, network, rate limit) → caught; returns
  `"[suggest_outfit error] ..."`. The planning loop detects the `[...]` error
  prefix and stops before `create_fit_card`, surfacing the message to the user.

---

### Tool 3: create_fit_card

**What it does:**
Turns the outfit suggestion plus the item details into a short, casual,
shareable caption (an OOTD / "fit card" post). Calls the LLM at a higher
temperature so repeated calls on the same input produce varied captions.

**Input parameters:**
- `outfit` (str): the outfit-suggestion string returned by `suggest_outfit`.
  Required and must be non-empty/non-whitespace — this is the guarded failure
  mode.
- `new_item` (dict): the listing dict for the thrifted item. Its `title`,
  `price`, and `platform` are woven into the caption once each.

**What it returns:**
`str` — a 2–4 sentence caption written to sound like a real person's post, that
mentions the item name, price, and platform naturally and captures the outfit
vibe. On an LLM/network failure it returns `"[create_fit_card error] ..."`.
It never raises.

**What happens if it fails or returns nothing:**
- `outfit` empty / whitespace-only / not a string → returns the descriptive
  string `"[create_fit_card error] No outfit was provided, so there's nothing
  to write a caption about. Run suggest_outfit first."` (no LLM call made).
- LLM call raises → caught; returns `"[create_fit_card error] ..."` naming the
  underlying problem so the agent can tell the user the caption step failed but
  the listing and outfit are still valid.

---

### Additional Tools (if any)

<!-- Copy the block above for any tools beyond the required three -->

---

## Planning Loop

**How does your agent decide which tool to call next?**
<!-- Describe the logic your planning loop uses. What does it look at? What conditions change its behavior? How does it know when it's done? -->

---

## State Management

**How does information from one tool get passed to the next?**
<!-- Describe how your agent stores and accesses state within a session. What data is tracked? How is it passed between tool calls? -->

---

## Error Handling

For each tool, describe the specific failure mode you're handling and what the agent does in response.

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| search_listings | No results match the query (keywords/size/price too narrow) | Tool returns `[]`. Agent stops the loop before `suggest_outfit`, and returns a message naming the applied filters and suggesting the user loosen one (raise price, drop size, broaden keywords). |
| suggest_outfit | Wardrobe is empty (`wardrobe["items"] == []`) | Not an error — tool switches to a general-styling-advice prompt and still returns a useful non-empty string. Agent continues to `create_fit_card`. |
| suggest_outfit | LLM call fails (bad/missing API key, network, rate limit) | Tool catches the exception and returns `"[suggest_outfit error] ..."`. Agent detects the `[...]` prefix, stops before `create_fit_card`, and tells the user the styling step failed and to retry. |
| create_fit_card | Outfit input missing / empty / whitespace-only | Tool makes no LLM call and returns `"[create_fit_card error] No outfit was provided..."`. Agent surfaces this; the listing and outfit (if any) are still shown. |
| create_fit_card | LLM call fails | Tool catches and returns `"[create_fit_card error] ..."`. Agent shows the listing + outfit and notes the caption couldn't be generated. |

---

## Architecture

<!-- Draw a diagram of your agent showing how the components connect:
     User input → Planning Loop → Tools (search_listings, suggest_outfit, create_fit_card)
                                                                          ↕
                                                                   State / Session
     Show what triggers each tool, how state flows between them, and where error paths branch off.
     Use ASCII art or a Mermaid diagram (https://mermaid.js.org/syntax/flowchart.html).
     Do NOT embed an image — graders need to read your diagram directly in the file;
     an embedded image or screenshot cannot be evaluated.
     You'll share this diagram with an AI tool when asking it to implement
     the planning loop and each individual tool. -->

---

## AI Tool Plan

<!-- For each part of the implementation below, describe:
     - Which AI tool you plan to use (Claude, Copilot, ChatGPT, etc.)
     - What you'll give it as input (which sections of this planning.md, your agent diagram)
     - What you expect it to produce
     - How you'll verify the output matches your spec before moving on

     "I'll use AI to help me code" is not a plan.
     "I'll give Claude my Tool 1 spec (inputs, return value, failure mode) and ask it to implement
     search_listings() using load_listings() from the data loader — then test it against 3 queries
     before trusting it" is a plan. -->

**Milestone 3 — Individual tool implementations:**
Tool used: Claude (Claude Code). For each of the three tools I pasted that
tool's spec block from the "Tools" section above (what it does, input parameter
names + types, return value, failure mode) and asked for an implementation in
`tools.py` — one tool per prompt, not all at once.
- `search_listings`: directed it to use `load_listings()` from
  `utils/data_loader.py` (not re-read the file), filter by `max_price` and
  `size` first, then score by keyword overlap, drop score-0 rows, sort
  descending. Verified against 3 queries: a normal query returns results, an
  over-constrained query returns `[]`, and a `max_price` query returns only
  items at/under the ceiling.
- `suggest_outfit`: directed it to branch on `wardrobe["items"]` being empty,
  call the Groq LLM, and wrap the call in try/except returning a
  `"[suggest_outfit error] ..."` string. Verified the empty-wardrobe branch
  returns advice without crashing. Divergence found while testing: the handout's
  model `meta-llama/llama-4-scout-17b-16e-instruct` returns 404 from Groq, so
  both LLM tools use `openai/gpt-oss-120b` (a current Groq chat model) instead.
- `create_fit_card`: directed it to guard an empty/whitespace `outfit` string
  before any LLM call, and to use a higher temperature so captions vary.
  Verified by calling it twice on the same input and confirming the outputs
  differ, and by passing `""` and confirming an error string (no exception).
Every generated function was checked against its spec block for matching
parameter names/types and failure-mode handling before being run, then locked
in with the pytest tests in `tests/test_tools.py`.

**Milestone 4 — Planning loop and state management:**

---

## A Complete Interaction (Step by Step)

Write out what a full user interaction looks like from start to finish — tool call by tool call. Use a specific example query.

**Example user query:** "I'm looking for a vintage graphic tee under $30. I mostly wear baggy jeans and chunky sneakers. What's out there and how would I style it?"

**Step 1:**
<!-- What does the agent do first? Which tool is called? With what input? -->

**Step 2:**
<!-- What happens next? What was returned from step 1? What tool is called now? -->

**Step 3:**
<!-- Continue until the full interaction is complete -->

**Final output to user:**
<!-- What does the user actually see at the end? -->
