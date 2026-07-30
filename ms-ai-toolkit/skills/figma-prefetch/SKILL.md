---
name: figma-prefetch
description: Bulk-prefetch an entire Figma file into a local cache once, then read designs from the cache instead of repeatedly calling the Figma MCP server — preventing rate limiting. Use at the START of any task that involves reading or implementing from a Figma design or when a figma.com URL is provided. This is a read/extraction workflow; writing designs INTO Figma stays with the Figma plugin's own skills (e.g. figma-use).
---

# Figma prefetch (cache-first, rate-limit-safe)

Calling the Figma MCP node-by-node (`get_screenshot` / `get_design_context` / `get_metadata` over
and over) is slow and triggers **rate limiting**. Instead, do ONE bulk extraction pass into a local
cache at the start, then read everything from the cache.

**Cache location:** repo-root `.figma-cache/<fileKey>/`.

## Workflow

1. **Check the cache first.** If `.figma-cache/<fileKey>/` already exists for this file, read from
   it and skip the network entirely. Only fetch nodes genuinely missing from the cache.
2. **Resolve the target.** Parse the Figma URL → `fileKey` and the starting `node-id`
   (`figma.com/design/<fileKey>/...?node-id=<id>`).
3. **One metadata pass.** Call `get_metadata` on the file / top node to get the node tree (IDs,
   names, types, layout). Save to `.figma-cache/<fileKey>/metadata.json`. Use this tree as the
   index for everything else — do not call `get_metadata` again.
4. **Per-frame export.** For each relevant top-level frame/screen node in the metadata, batch the
   calls (parallel where possible):
   - `get_screenshot` → `.figma-cache/<fileKey>/screens/<node-id>.png`
   - `get_design_context` → `.figma-cache/<fileKey>/context/<node-id>.<ext>`
5. **Tokens once.** `get_variable_defs` → `.figma-cache/<fileKey>/variables.json`.
6. **Assets once.** `download_assets` for images/icons → `.figma-cache/<fileKey>/assets/`.
7. **Write a manifest.** `.figma-cache/<fileKey>/index.md` mapping `node-id → name → cached file
   paths`, plus the source URL and the fetch context. Note the data is point-in-time.
8. **Read from the cache thereafter.** For the rest of the session, reference the cached files
   instead of calling the Figma MCP. Re-fetch a single node only if it is absent from the cache or
   the user says the design changed. Refresh the whole cache only on explicit request.

## Guidance

- **Goal:** minimize Figma MCP calls. Pay the cost once, up front; never re-fetch cached data.
- **Resumable.** If a pass is rate-limited mid-way, back off and resume — the `metadata.json` index
  lets you skip nodes already saved in `screens/` and `context/`.
- **Staleness.** The cache is point-in-time; if the design may have changed, tell the user and
  refresh only the affected nodes (or the whole file on request).
- `.figma-cache/` is a working cache — add it to `.gitignore` if the working directory is a git repo.
