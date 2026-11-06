# ai-toolkit

Personal AI coding-agent config, kept in one place.

- **`ms-ai-toolkit/`** — the Claude Code setup, packaged as a plugin. This repo is its own
  marketplace (`ms-ai`, via `.claude-plugin/marketplace.json` at the root).
- **`opencode/`** — opencode config (`opencode.jsonc`, `tui.json`, prompts, plugins), plus
  skills (`handoff`, `director`, `authoring`), agents (`judge`, `scout`) and commands
  (`/handoff`, `/director-tick`).

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
mkdir -p ~/.config/opencode/plugin ~/.config/opencode/prompts
ln -s "$PWD/opencode/plugin/agent-brain.js"   ~/.config/opencode/plugin/
ln -s "$PWD/opencode/prompts/agent-brain.md"  ~/.config/opencode/prompts/
export BRAIN_SCRIPTS="$PWD/ms-ai-toolkit/brain"    # put this in your shell profile
python3 "$PWD/ms-ai-toolkit/brain/brain-init.py"
```

opencode discovers plugins with the glob `{plugin,plugins}/*.{ts,js}`, so the file has to keep
its `.js` extension — a `.mjs` there is silently never loaded. The prompt is already listed in
`opencode/opencode.jsonc` under `instructions`. Details and the full variable list:
[`ms-ai-toolkit/brain/README.md`](ms-ai-toolkit/brain/README.md).

### Skills, agents and commands

```
mkdir -p ~/.config/opencode/skills ~/.config/opencode/agents ~/.config/opencode/commands
for d in opencode/skills/*/;   do ln -s "$PWD/$d" ~/.config/opencode/skills/; done
for f in opencode/agents/*.md;   do ln -s "$PWD/$f" ~/.config/opencode/agents/; done
for f in opencode/commands/*.md; do ln -s "$PWD/$f" ~/.config/opencode/commands/; done
```

opencode finds these by directory, so nothing goes in `opencode.jsonc`. A skill's folder name must
equal the `name:` in its `SKILL.md`.

| Piece | What it does |
|---|---|
| `handoff` skill + `/handoff` | At ~300K tokens of context, writes notes, starts a successor session with a standalone brief, and retires this one |
| `director` skill + `/director-tick` | A long-lived coordinator session: rules, a tick checklist, a crontab schedule that follows the current director across handoffs, and Matrix as a second chat channel |
| `authoring` skill | Writing rules for docs, PR descriptions, posts and decks: a counted 3-minute reading budget, diagrams first, a plain opener |
| `judge` agent | Approves or rejects a plan or claim; needs each premise's evidence inline. Point it at your strongest model |
| `scout` agent | One read-only lookup at a time. Point it at your cheapest model |

Pin models per agent with `model: provider/model-id` in its frontmatter, or under `agent` in
`opencode.jsonc`. The existing `general` agent is the worker for edits.

Session handling assumes the `agent-manager` CLI is installed (`spawn`, `send`,
`archive-self`, `kill-self`). The director's first run:

```
export DIRECTOR_HOME=~/.director
mkdir -p "$DIRECTOR_HOME" && cp -n opencode/skills/director/templates/*.md "$DIRECTOR_HOME/"
~/.config/opencode/skills/director/scripts/install-schedule.sh   # crontab rows from schedule.md
```

The Matrix channel needs `MATRIX_HOMESERVER`, `MATRIX_OWNER`, `MATRIX_USER` and `MATRIX_PASSWORD`
in your shell profile, then `mx.py login` and `mx.py room` once.

Previously this repo shipped a `claude/` directory you `cp`'d into `~/.claude/` and merged
into `settings.json` by hand. That's gone — if you still have those entries, remove them
before enabling the plugin or every hook fires twice
([why and how](ms-ai-toolkit/README.md#already-hand-installed-the-old-claude-bundle-clean-up-first)).
