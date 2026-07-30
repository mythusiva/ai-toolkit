# ai-toolkit

Personal AI coding-agent config, kept in one place.

- **`ms-ai-toolkit/`** — the Claude Code setup, packaged as a plugin. This repo is its own
  marketplace (`ms-ai`, via `.claude-plugin/marketplace.json` at the root).
- **`opencode/`** — opencode config (`opencode.jsonc`, `tui.json`, prompts).

## Install the Claude Code plugin

```
/plugin marketplace add mythusiva/ai-toolkit
/plugin install ms-ai-toolkit@ms-ai
```

Restart Claude Code. Hooks, prompts, commands and skills wire themselves up — nothing is
copied into `~/.claude/`, no `settings.json` editing. Update with
`/plugin update ms-ai-toolkit@ms-ai`.

What it does: manager-mode delegation gates (model tiers, leaf agents can't delegate,
verification evidence demanded at Stop), hard-requirement plan gates, an advisory
senior-review critic panel at Stop, ponytail + lean-speak reply modes, and five on-demand
skills (feature deep dives, Figma prefetch/export, Google Slides editing, coding-guideline
upkeep). Full detail, migration notes for the old hand-copied install, and the optional
status-line / local-Gemma extras: [`ms-ai-toolkit/README.md`](ms-ai-toolkit/README.md).

Previously this repo shipped a `claude/` directory you `cp`'d into `~/.claude/` and merged
into `settings.json` by hand. That's gone — if you still have those entries, remove them
before enabling the plugin or every hook fires twice
([why and how](ms-ai-toolkit/README.md#already-hand-installed-the-old-claude-bundle-clean-up-first)).
