---
description: Toggle lean-speak (terse, token-lean) reply style on/off
allowed-tools: Bash
---
Toggle lean-speak mode using the sentinel `$HOME/.claude/lean-speak.on` (its presence = ON).
- If it exists: `rm` it -> mode now OFF. Confirm OFF in one line.
- If not: `touch` it -> mode now ON. Confirm ON in one line, written in lean style as a live sample.

The persistent behavior comes from the UserPromptSubmit hook (settings.json) that injects
`$HOME/.claude/lean-speak-style.md` every turn while the sentinel exists — you need not restate
the style here.
