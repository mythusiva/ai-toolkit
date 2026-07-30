---
name: figma-export
description: Export every screen/frame under a Figma link as a PNG plus its full metadata tree and a "copy link to selection" deep link, into a portable design-map folder (map.md + map.json + metadata.xml + PNGs). Use when the user runs /figma-export, provides a figma.com/design URL and wants the designs saved locally, or wants a feature's screens preserved with their node ids/links/dimensions (like feature-plans/*/design). Reads the Figma DESKTOP app via the Figma MCP — no REST token, no rate limits.
---

# Figma export (screens + metadata + deep links)

Pulls screens from the **Figma desktop app** via the Figma MCP (`get_metadata` + `get_screenshot`) — no REST API, so no `FIGMA_PAT` and no 429 rate limits. The bundled `export.mjs` turns the metadata dump into the map files; you (the agent) make the two MCP calls.

## Precondition
Figma desktop must be running with the target file open — the MCP reads the desktop app's current document. If `get_metadata` errors, ask the user to open the file in Figma desktop.

## Steps

1. Parse the URL `figma.com/design/<fileKey>/<fileName>?node-id=<a-b>`. nodeId = `<a-b>` with `-`→`:`. Pick an `<outdir>` (a feature root, e.g. `~/work/feature-plans/<feature>`; a `design-map/` subfolder is created inside it).

2. Call `get_metadata` (Figma MCP) with that fileKey + nodeId. It returns `[{type,text}]` where `text` is the XML tree. Save that XML to `<outdir>/design-map/metadata.xml`:
   - Inline result → write the `.text` value to the file.
   - Too large / auto-saved to a tool-results file → `mkdir -p <outdir>/design-map && jq -r '.[0].text' <tool-results-file> > <outdir>/design-map/metadata.xml`.

3. Build the map + screenshot worklist:
   ```bash
   node ~/.claude/skills/figma-export/export.mjs "<figma-url>" "<outdir>/design-map/metadata.xml" "<outdir>"
   ```
   It writes `map.json`, `map.md`, copies in `metadata.xml`, and prints `FRAMES\t<n>` then one `<nodeId>\t<pngfile>` line per screen.

4. For each worklist line, capture the PNG with `get_screenshot` (Figma MCP) using that fileKey + nodeId and `maxDimension: 1600` (caps the longer edge; it only downscales — it will not upscale past the frame's native size, so a 360×800 frame renders at 360×800). It returns a short-lived URL + a curl command — run the curl to save the image to `<outdir>/design-map/<pngfile>`. Do them sequentially or in small batches.

5. Report the frame count and the `map.md` path.

## Output (in `<outdir>/design-map/`)
- `<frame>.png` — one PNG per screen frame (filename = sanitized frame name).
- `map.md` — readable index: per frame the deep link, node id / type / dimensions, embedded image.
- `map.json` — index: source URL, fileKey, nodeId, and per frame `{ name, id, type, width, height, link, image }`.
- `metadata.xml` — the full raw node tree (every instance/component/icon with its name, id, size) — the source of truth for exact icon & component names.

## What it exports
Descends SECTION/CANVAS containers and exports the frame-like children (FRAME/COMPONENT/COMPONENT_SET/INSTANCE) as screens. If the link points at a single frame, it exports that frame. Deeper structure (icons, nested components) lives in `metadata.xml`, not as separate PNGs. For richer per-node context, call `get_design_context` / `get_variable_defs` on a specific node id taken from `metadata.xml`.
