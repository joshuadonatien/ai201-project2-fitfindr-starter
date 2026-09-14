# FitFindr — Demo Recording Steps (click-by-click, no script)

No narration required — you can talk in your own words or add captions after.
This is just the sequence of clicks/actions to hit every rubric requirement:
a complete interaction using all 3 tools, state visibly passing between them,
and one deliberately triggered failure.

Target length: 3–5 minutes.

---

## Setup (before you hit record)

1. Terminal → project folder → `source .venv/bin/activate` → `python app.py`
2. Copy the URL it prints (usually `http://localhost:7860`) and open it in
   your browser.
3. Arrange the browser window so it fills the screen/region you'll record.
4. **QuickTime Player** → File → New Screen Recording → click the little
   arrow next to the record button → turn the **microphone on** if you want
   to narrate live, or leave it off if you're adding captions later → select
   the region → click **Start Recording**.

---

## Recording — click sequence

### Part 1 — Happy path (all 3 tools)

1. Click into the **"What are you looking for?"** box.
2. Type:
   ```
   I'm looking for a vintage graphic tee under $30. I mostly wear baggy jeans and chunky sneakers. What's out there and how would I style it?
   ```
3. Leave the wardrobe radio button on **"Example wardrobe"**.
4. Click **Find it**.
5. Wait for all three panels to fill in. **Pause the cursor / hover over each
   panel for a few seconds, left to right**, so it's visible in the recording:
   - **🛍️ Top listing found** — the item `search_listings` picked
   - **👗 Outfit idea** — outfit built by `suggest_outfit` from that *same*
     item, naming pieces from the example wardrobe
   - **✨ Your fit card** — caption from `create_fit_card`, mentioning that
     *same* item's name/price/platform
6. This sequence alone shows all 3 tools ran and that the item/outfit carried
   forward — no re-typing between panels.

### Part 2 — Triggered failure

7. Clear the search box.
8. Type:
   ```
   designer ballgown size XXS under $5
   ```
9. Click **Find it**.
10. Hover/pause over panel 1 — it shows an error message (not a crash, not a
    blank screen) explaining nothing matched and what to try.
11. Point the cursor at panels 2 and 3 — **still empty**, showing the outfit
    and caption tools were never called for this failed search.

### Optional Part 3 — a second failure (only if you want more coverage)

12. Switch back to the terminal (still visible in your recording region, or
    stop/start a second recording).
13. Run:
    ```bash
    GROQ_API_KEY=gsk_invalid_key_for_testing python -c "from agent import run_agent; from utils.data_loader import get_example_wardrobe; print(run_agent('vintage graphic tee under \$30', get_example_wardrobe())['error'])"
    ```
14. Let the printed message sit on screen for a few seconds — it shows the
    agent found the item but the styling step failed, with a suggestion to
    retry.

### Close

15. Stop the recording (⌘+Ctrl+Esc, or the stop icon in the menu bar).

---

## After recording

1. Save/export the file from QuickTime (File → Export As → 1080p is fine).
2. Upload it — pick one:
   - **YouTube**: Upload → set visibility to **Unlisted** → copy the link
   - **Loom**: record directly in Loom instead of QuickTime, or upload the
     QuickTime file → copy the share link
   - **Google Drive**: upload the file → Share → "Anyone with the link" →
     copy the link
3. Paste that link into `README.md` in the two spots marked
   `_[add here once recorded]_` / `_[add your recorded demo link here...]_`.

---

## Checklist before you stop recording

- [ ] All 3 panels filled in for the happy-path query
- [ ] You paused on each panel long enough for a viewer to read it
- [ ] The failed-search query was run and its panels shown
- [ ] Total length is roughly 3–5 minutes
