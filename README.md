# ai-toolkit

Personal AI coding-agent config, kept in one place.

- **`ms-ai-toolkit/`** — the Claude Code setup, packaged as a plugin. This repo is its own
  marketplace (`ms-ai`, via `.claude-plugin/marketplace.json` at the root).
- **`opencode/`** — opencode config (`opencode.jsonc`, `tui.json`, prompts, plugins).

The **agent brain** — a SQLite working memory that agents read before they grep and write to the
moment they learn something — runs on both, from one shared engine in
[`ms-ai-toolkit/brain/`](ms-ai-toolkit/brain/README.md).

## Install the Claude Code plugin

```
/plugin marketplace add mythusiva/ai-toolkit
/plugin install ms-ai-toolkit@ms-ai
```

Restart Claude Code. Hooks, prompts, commands and skills wire themselves up — nothing is
copied into `~/.claude/`, no `settings.json` editing. Update with
`/plugin update ms-ai-toolkit@ms-ai`.

Then create the brain once (it is the only step the plugin cannot do for you):

```
python3 "$CLAUDE_PLUGIN_ROOT/brain/brain-init.py"
```

What it does: the agent brain (deterministic recall injected on every prompt, an
evidence-triggered capture nudge at Stop), manager-mode delegation gates (model tiers, leaf
agents can't delegate, verification evidence demanded at Stop), hard-requirement plan gates, an
advisory senior-review critic panel at Stop, ponytail + lean-speak reply modes, and six
on-demand skills (agent-brain upkeep, feature deep dives, Figma prefetch/export, Google Slides
editing, coding-guideline upkeep). Full detail, migration notes for the old hand-copied install, and the optional
status-line / local-Gemma extras: [`ms-ai-toolkit/README.md`](ms-ai-toolkit/README.md).

## Install on opencode

```
ln -s "$PWD/opencode/plugin/agent-brain.js"   ~/.config/opencode/plugin/
ln -s "$PWD/opencode/prompts/agent-brain.md"  ~/.config/opencode/prompts/
export BRAIN_SCRIPTS="$PWD/ms-ai-toolkit/brain"
python3 "$PWD/ms-ai-toolkit/brain/brain-init.py"
```

opencode auto-loads anything in `~/.config/opencode/plugin/`. The prompt is already listed in
`opencode/opencode.jsonc` under `instructions`. Details and the full variable list:
[`ms-ai-toolkit/brain/README.md`](ms-ai-toolkit/brain/README.md).

Previously this repo shipped a `claude/` directory you `cp`'d into `~/.claude/` and merged
into `settings.json` by hand. That's gone — if you still have those entries, remove them
before enabling the plugin or every hook fires twice
([why and how](ms-ai-toolkit/README.md#already-hand-installed-the-old-claude-bundle-clean-up-first)).
