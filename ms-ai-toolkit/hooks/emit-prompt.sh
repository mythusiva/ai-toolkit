#!/usr/bin/env bash
# Print a prompt file from prompts/, resolving its @PLUGIN@ placeholders to this plugin's
# install path. Hook command strings get ${CLAUDE_PLUGIN_ROOT} expanded by Claude Code, but
# file *contents* do not -- so any path a prompt names has to be substituted here.
# Split on the placeholder rather than substituting it. Neither sed nor bash's ${v//p/r} is
# safe here: both treat an unescaped & in the replacement as "the matched text", so an install
# path containing & silently emits @PLUGIN@ back into the prompt. sed does this everywhere;
# bash does it from 5.2 on (5.1 and earlier are fine), which is exactly the platforms most
# teammates run. Prefix/suffix trimming has no replacement semantics on any version.
# Usage: emit-prompt.sh <basename-without-.md>
root="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
f="$root/prompts/$1.md"
[ -s "$f" ] || exit 0     # missing prompt -> inject nothing rather than an error
out=""; rest=$(cat "$f")
while [ "${rest#*@PLUGIN@}" != "$rest" ]; do
  out="$out${rest%%@PLUGIN@*}$root"
  rest="${rest#*@PLUGIN@}"
done
printf '%s\n' "$out$rest"
