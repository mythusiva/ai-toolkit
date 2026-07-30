---
name: google-slides-editing
description: Edit Google Slides deterministically via the Chrome DevTools MCP (no Google Slides API/OAuth). Use when asked to update, lay out, or add content/images to a Google Slides deck (docs.google.com/presentation/...). Covers connecting to a live Chrome tab, editing text + bullets, inserting app/DB screenshots as images, and placing/sizing elements by exact inch coordinates instead of nudge-and-screenshot loops.
---

# Editing Google Slides via Chrome DevTools MCP

There is **no Google Slides MCP or Workspace MCP**. Drive the real Slides web
app in a Chrome tab over the chrome-devtools MCP. The whole point of this skill:
**decide exact geometry up front and apply it once** — avoid the
change→screenshot→adjust loop.

## Connect
1. Chrome with remote debugging: `pgrep -f "remote-debugging-port=9222"` else
   launch `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome --remote-debugging-port=9222 --user-data-dir="$HOME/.chrome-debug-profile"`.
2. `curl -s localhost:9222/json/version` to confirm.
3. `new_page` the presentation URL. The debug profile is **separate** — the user
   is usually already signed into Google there; other services (a DB admin UI,
   your app) are NOT logged in and need their own login.

## Reading a deck (all slides, one call — for review/fact-check work)
The filmstrip renders **every** slide into ONE tall SVG (width ~200px, height ≈
102px × slide count) whose `<text>` nodes carry the real text. Group them by
thumbnail y-band → per-slide text in a single `evaluate_script`:
```js
const strip = [...document.querySelectorAll('svg')].find(s => {const r=s.getBoundingClientRect(); return r.width>150&&r.width<260&&r.height>1000});
const bands = [...document.querySelectorAll('svg')].map(s=>s.getBoundingClientRect()).filter(r=>Math.round(r.width)===146).map(r=>r.y).sort((a,b)=>a-b);
// bucket each text node by the band it falls in (y >= band-2 && y < band+84), sort by y then x, join
```
Write it to a file via `evaluate_script({filePath})` and grep — never inline a
whole deck. The **current** slide's text is also in the main canvas SVG
(width>400, height>300); notes are the short wide SVG (height<300).
Use this BEFORE any deck-wide edit to prove a search phrase is unique to the
slide you mean. Slide navigation: `Escape` then `Home` = slide 1, `PageDown` =
next (URL hash updates, so slide order/ids come free).
`/export/pdf` is a dead end: same-origin `fetch` fails (CORS redirect to
googleusercontent) and navigating to it gives `ERR_ABORTED` with no download.

## Editing text: Find and replace beats selecting boxes
For wording changes (not layout), skip Tab-cycling and text-box selection
entirely — **Edit → Find and replace** is surgical and preserves run
formatting (bold labels, italics, table cells all survive).
- Shortcut is **⌘+Shift+H**. Do NOT send `Meta+h` — on macOS that hides Chrome.
  Safest: click the `Edit` menuitem, then the "Find and replace" item.
- Fields are a11y-visible: `textbox "Find"`, `textbox "Replace with"`,
  `checkbox "Match case"` (turn it ON), `button "Replace all"`. Use `fill_form`
  for the pair, then click Replace all; the dialog stays open and its uids stay
  stable across many replacements.
- Replacement is **deck-wide** and **includes speaker notes** — so a claim you
  fix on the canvas usually needs a second pass for the notes that repeat it.
- The dialog has a **"Use regular expressions"** checkbox (supports `\n`, `\t`).
  Use it to dodge Slides' curly apostrophes/quotes: `isn.t`, `it.s` match both
  `'` and `’`. The `N of M` counter above "Replace with" tells you the match
  count before you commit — `0 of 1` means one match, ready to replace.
- Replacement is **deck-wide** — verify phrase uniqueness first (above).
- A cached text dump from an earlier session goes stale (someone edits, or you
  edited). Re-read the LIVE canvas SVG for the slide you're about to change —
  the real string may carry extra clauses the old dump never had.
- **"Replace all" staying disabled = zero matches.** That's the tell that the
  text you can see is not text (see next section), not a fill failure.
- Verify by re-reading the filmstrip SVG (`txt.includes(...)`), not screenshots.

## When a "diagram slide" is actually a flat image
If a slide's canvas SVG has ~no `<text>` while the screenshot clearly shows
labelled boxes, the content is an inserted image (typically a mermaid render).
Fix the SOURCE, then swap the picture:
1. Edit the `.mmd`/`.html`, reload the tab, `wait_for` new label text.
2. `take_screenshot({uid: <diagram element>, filePath})` under a workspace root.
3. In Slides: `Escape`, then `Tab` to cycle objects (Tab1 title, Tab2 image —
   confirm via the toolbar showing "Replace image"), click
   `button "Replace image"` **with `includeSnapshot:true`** (a plain snapshot
   afterwards can lose the selection and close the menu), then `upload_file`
   on `menuitem "Upload from computer"`.
4. Replace image keeps position + size — no Format-options pass needed.

## Slide geometry (the key to one-pass layout)
- Default widescreen slide = **10.0 × 5.63 in**. Position origin = **Top left**.
- Every shape/image/text box has exact **Width/Height** and **X/Y in inches**,
  editable numerically via **Format options** (see below). Compute target
  coordinates from slide size + element aspect BEFORE touching anything.
- Image aspect: read the source PNG's px dims (`sips -g pixelWidth -g pixelHeight`);
  ratio = W/H. To keep it undistorted, set Width and derive Height = W / ratio
  (and set both — don't trust "lock aspect ratio" being on).
- A tall text box with vertically-centered text makes text float to the middle,
  not the top — shrink the box **Height** (and set Y) to raise the text. Measuring
  the box (Format options) beats eyeballing pixels.

## Selecting objects (reliable, deterministic)
- **Text edit**: `click` a text run with `dblClick:true` → enters edit mode.
  Then `Cmd+a` + `Delete` to clear, `type_text` to write.
- **Object select** (needed for Format options): single-click on canvas text
  via the MCP is UNRELIABLE and pasted images have **no uid** in the a11y tree.
  Instead: put focus in the editor, press **Tab** to cycle objects
  (Tab1 = title, Tab2 = body, Tab3 = image, in creation/z order). Screenshot
  once to confirm which is selected, then it's deterministic for the session.
- Format options panel **stays open and re-populates** as you Tab between
  objects — open it once, edit each object's fields, done.

## Setting size/position (Format options)
1. Object selected → menu **Format → Format options** (or the contextual
   toolbar's "Format options" button; greyed out ⇒ nothing is selected).
2. Expand **Size & Rotation** and **Position**. Fields are spinbuttons in
   **inches**: Width, Height, X, Y.
3. `fill` each field then press **Enter** to commit (blur alone is unreliable).
4. Set Width AND Height explicitly for images to control aspect.

## Text + bullets (avoid the double-bullet trap)
- Typed newlines become paragraphs. To get ONE clean bulleted list: type the
  first bullet line prefixed with `• ` — Slides autoformats it into a real list
  and **subsequent lines auto-continue** the list. Do NOT prefix the later lines
  with `• ` (you'd get a real bullet + a literal `•` = double bullets).
- A non-bulleted header/diagram line: type it first, then a blank line, then the
  `• `-triggered list below it.
- List formatting **persists** after clearing a box; retype may re-bullet the
  header. If so, remove the bullet via the text toolbar's bulleted-list button
  (the `Cmd+Shift+8` keystroke was rejected in one environment — use the button).

## Inserting an image (DB table, app screen, chart, etc.)
OS-clipboard **paste does NOT work** (`Cmd+V` via CDP won't give Slides access to
an OS-clipboard image — Chrome blocks it even though `osascript`-set clipboard
holds the PNG). Use the file-chooser route:
1. Capture the source: `navigate`/`new_page` to it, `take_screenshot` with
   `filePath` **under a workspace root** (e.g. `~/work/foo.png` — a
   `/tmp` scratch path is rejected). Crop with `sips -s format png
   --cropToHeightWidth H W --cropOffset TOP LEFT in.png --out out.png`.
2. Menu **Insert → Image → Upload from computer**, then call the MCP
   **`upload_file`** tool with `uid` = the "Upload from computer" menu item and
   `filePath` = the PNG. This drives the native chooser CDP can't click.
3. The image lands centered and selected → set its Format-options coordinates.
4. Delete scratch PNGs afterward.

## Mermaid → image (in-browser render, no install)
Google Slides can't embed mermaid natively (Marketplace add-ons need install +
auth). Render it to an image and insert via the image route above:
1. Write an HTML file under a workspace root that loads mermaid from a CDN and
   holds a `<pre class="mermaid">…</pre>` diagram, with
   `mermaid.initialize({startOnLoad:true})`. The debug Chrome profile has
   internet so the CDN loads (no `mmdc`/puppeteer install needed).
2. `new_page` the `file://…` path; `wait_for` the rendered `<svg>`.
3. `take_screenshot` the `.mermaid` element **by its uid** (element shot = tight
   crop, transparent margins); or full-page + `sips` crop. Save PNG under a
   workspace root.
4. Insert into the slide via Insert → Image → Upload from computer + `upload_file`,
   then place via Format options.
5. Trade-off: it's a FLAT image in Slides (not editable there) — keep the
   .mmd/.html and re-render when the diagram changes. Prefer native shapes when
   the deck needs to highlight/animate individual nodes.

## Creating shapes + drawing (when you DO want native shapes)
- The Insert → Shape → Shapes grid icons have **no a11y uid** (can't `click` them).
  Select one via `evaluate_script`: `elementFromPoint(x,y)` → find the
  `[aria-label="Rounded Rectangle"]` (etc.) and dispatch `mousedown`+`mouseup`+`click`.
- Then draw on the canvas: `evaluate_script` dispatching `pointerdown`+`mousedown`
  at (ax,ay) → `pointermove`/`mousemove` to (bx,by) → `pointerup`+`mouseup`
  (`drag` tool is uid→uid only, useless for drawing). Shape lands selected; fix
  geometry via Format options. Type while selected to add its label.
- Duplicate identical boxes with `Cmd+d`. Line arrows: Insert → Line → Arrow, then
  the same synthesized drag between box edges (calibrate endpoints from a screenshot).

## Verify
- ONE final `take_screenshot` at the end (not per tweak). Confirm no overlaps,
  nothing clipped past slide edges, only the intended slide changed.
- Slides autosaves; the header shows "Saved to Drive".
- If others are editing live (header shows "Last edit … by <name>"), touch only
  your target slide.

## Cost note
Full `take_snapshot` on a multi-slide deck is large (filmstrip text included).
Minimize snapshots: take one to grab the uids you need (object text run, menu
item, panel fields), then act; prefer `take_screenshot` (image) for visual
checks over `take_snapshot` (a11y tree).
- **Best token saver:** `take_snapshot({filePath: "~/repo/snap.txt"})` writes the
  tree to a FILE instead of your context, then `grep` it for the one uid you need
  (`grep -iE 'menuitem "Image i|Upload from computer|Format options' snap.txt`;
  for panel fields `grep 'spinbutton "(Width|Height|X position|Y position)'`).
  Cuts each ~8k-token snapshot to a few lines.

## Precision & selecting on a crowded/live slide
- Small window = tiny canvas = imprecise clicks. `resize_page(1600,1000)` first so
  the slide is large enough to click elements accurately.
- To select a canvas object that has NO a11y uid (images) or is under others:
  `evaluate_script` dispatching `mousedown`+`mouseup`+`click` at its on-screen
  (x,y); then read the Format panel size/position to CONFIRM you grabbed the right
  one before deleting. `elementFromPoint` sees the preview layer, but Slides'
  click hit-tests its own edit layer — so verify via the panel, don't trust the
  DOM node.
- Concurrent editors can merge/replace your elements: what reads as "two images"
  can be one merged image spanning both. Confirm size/position before any delete;
  if a delete would remove more than intended, stop and ask.
- "Replace image" (right-click / image toolbar) keeps position+size — cheaper than
  delete+reinsert+reposition when you only need to swap the picture.

## Mermaid diagram types
`flowchart` for process/flow; `erDiagram` for a DB table/entity schema (columns +
types + PK/FK, with `"comment"` per field). Same render-to-image route as above.

## Worked defaults (bottom-band figure layout, 10×5.63 slide)
- Body text (header line + a few bullets): X0.5 Y1.1 W9.0 H1.9 (keeps text in the
  top band).
- Wide figure below: center it — X=(10−W)/2, Y≈3.35, W≈6.6, H=W/aspect.

_Improve this skill whenever a new Slides gotcha or a cleaner technique shows up._
