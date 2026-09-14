# FitFindr — Demo Recording Script (3–5 minutes)

This is a script you can read almost verbatim while recording. It's built to
hit every rubric requirement:
- a complete interaction using all 3 tools, narrated step by step
- state visibly/verbally passing between tools
- at least one deliberately triggered failure with a graceful response

Total runtime target: **~4 minutes**. Practice it once un-recorded first.

---

## How to record (macOS)

1. Make sure your `.env` has a real `GROQ_API_KEY` (Milestone 3–4 covered this).
2. Open a terminal in the project folder and start the app:
   ```bash
   source .venv/bin/activate
   python app.py
   ```
   Note the URL it prints (usually `http://localhost:7860`).
3. Open that URL in your browser, and arrange your terminal and browser
   windows so you can screen-record either one (or both, if your recorder
   supports multiple windows / full screen).
4. Start **QuickTime Player** → File → New Screen Recording → click the
   red record button → drag to select the region (or record full screen) →
   click **Start Recording**.
   - Turn on your microphone in the QuickTime recording options so your
     narration is captured.
5. Record the 4 segments below in order, following the script.
6. Stop recording (⌘+Ctrl+Esc, or click the stop icon in the menu bar).
7. Export/save the video, upload it (YouTube "Unlisted", Loom, or Google
   Drive with link-sharing on), and paste the link into `README.md` under
   **Demo Video**.

---

## Segment 1 — Intro (15–20 sec)

**Say:**
> "This is FitFindr — a planning-loop agent for CodePath AI201 Project 2. It
> takes a natural-language shopping query, searches a mock secondhand-listings
> dataset, builds an outfit from your wardrobe, and writes a shareable caption.
> I'll walk through a complete interaction, point out how state passes between
> the three tools, and then show one deliberately triggered failure."

---

## Segment 2 — Happy path, all 3 tools, narrated (≈ 2 min)

**Do:** In the browser, type this exact query into the search box:
```
I'm looking for a vintage graphic tee under $30. I mostly wear baggy jeans and chunky sneakers. What's out there and how would I style it?
```
Leave the wardrobe on **"Example wardrobe"**. Click **Find it**.

**Say, while it's loading / right after:**
> "First, the planning loop parses this into keywords, a size, and a max
> price — here there's no size, and the price ceiling is $30. It calls
> **tool one, `search_listings`**, which filters the 40-item mock dataset and
> ranks the rest by keyword overlap."

**Point at panel 1** (top listing) once it appears:
> "It found this Vintage Band Tee — Faded Grey for $19 on Depop. This exact
> listing — not a re-typed description, the same dictionary object — is what
> gets handed to the next tool."

**Point at panel 2** (outfit) once it appears:
> "That's **tool two, `suggest_outfit`**. It got the item from step one plus
> my example wardrobe, and it's naming actual pieces I already own — the baggy
> jeans, the combat boots — not generic advice. If my wardrobe were empty it
> would give general styling tips instead; it checks for that internally."

**Point at panel 3** (fit card) once it appears:
> "And **tool three, `create_fit_card`** took the outfit text from step two
> and the same item from step one, and turned it into this caption — it
> mentions the item name, the $19 price, and Depop naturally, and it reads
> like a real post, not a product listing. So one query, three tools, and the
> item and outfit carried forward the whole way without me typing anything
> twice."

---

## Segment 3 — Triggered failure, graceful response (≈ 1 min)

**Do:** Clear the search box and type:
```
designer ballgown size XXS under $5
```
Click **Find it**.

**Say, while narrating what you see:**
> "Now I'll deliberately break it — there's no designer ballgown in this
> 40-item dataset, and I've made the filters impossible: size XXS, under $5.
> Watch panel one."

**Point at panel 1** once the response appears:
> "Instead of crashing or just saying 'no results,' it tells me exactly what
> it searched for, which filters it applied, and — because it automatically
> retried once after loosening the size filter — that it still found nothing
> even then. It suggests broader keywords, a wider size, or a higher price.
> Panels two and three are empty on purpose: the outfit and caption tools were
> never called, because there's no real item to style or caption yet."

*(Optional, if you want a second failure on camera: open a terminal and run
the command from `FAILURE_MODES.md` Failure 4 — an invalid Groq key — to show
the styling-step failure message. Not required; one triggered failure is
enough.)*

---

## Segment 4 — Close (10–15 sec)

**Say:**
> "That's a complete interaction through all three tools with state passing
> between them, and one deliberately triggered failure handled gracefully.
> Full documentation is in the README and `FAILURE_MODES.md`. Thanks for
> watching."

---

## Checklist before you stop recording

- [ ] All 3 tools were called and shown on screen for the happy-path query
- [ ] You said out loud (or showed) that the same item/outfit carried between steps
- [ ] At least one failure was triggered and its response shown
- [ ] Total length is roughly 3–5 minutes
- [ ] Audio narration is audible throughout
