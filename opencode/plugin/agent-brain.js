/**
 * agent-brain for opencode.
 *
 * The same engine Claude Code runs, driven through opencode's two matching seams:
 *
 *   Claude Code            opencode                          what it does
 *   -------------------    -------------------------------   ------------------------------------
 *   UserPromptSubmit   ->  "chat.message"                    inject what the brain already knows
 *   Stop               ->  event, filtered to session.idle   nudge when a session learned and
 *                                                            wrote nothing down
 *
 * The Python is shared verbatim -- no logic is reimplemented here. That is deliberate: two
 * components that must agree WILL diverge if each restates the rule, so this file is a transport
 * and every decision stays in brain-recall.py / brain-capture.py. brain-selftest.py pushes one
 * value through both harnesses' readers and asserts they reach the same verdict.
 *
 * One real difference: opencode has no blocking Stop. A nudge raised at session.idle is stashed
 * and injected at the top of the next turn instead, which is the same information one turn later.
 * Nothing here ever calls session.prompt() on its own -- an autonomous turn the user did not ask
 * for costs tokens and, worse, trains them to disable the plugin.
 *
 * Config, all optional:
 *   BRAIN_SCRIPTS    where the engine lives (default: probed, see resolveScripts)
 *   BRAIN_DB         default ~/.agent-brain/brain.db
 *   BRAIN_HOME       default ~/.agent-brain
 *   BRAIN_STOP_EXTRA comma-separated stopwords; put your org name here
 *   BRAIN_REPO_ROOT  a directory holding your checkouts, if they share one
 *   BRAIN_DEBUG      1 to log every decision to stderr
 */
import { spawn } from "node:child_process"
import { existsSync } from "node:fs"
import { homedir } from "node:os"
import { dirname, join, resolve } from "node:path"
import { fileURLToPath } from "node:url"

const HERE = dirname(fileURLToPath(import.meta.url))
const DEBUG = process.env.BRAIN_DEBUG === "1"
const PYTHON = process.env.BRAIN_PYTHON || "python3"

const log = (...a) => DEBUG && console.error("[agent-brain]", ...a)

/**
 * Find the engine. Explicit env wins; then the repo layout (this file at
 * <repo>/opencode/plugin/, the engine at <repo>/ms-ai-toolkit/brain/), which is what you get by
 * symlinking the repo's opencode dir; then an installed copy.
 *
 * Probing beats hardcoding here, but a probe that silently finds nothing is the failure mode --
 * so a miss is loud and says exactly which paths were tried.
 */
function resolveScripts() {
  const candidates = [
    process.env.BRAIN_SCRIPTS,
    resolve(HERE, "../../ms-ai-toolkit/brain"),
    join(homedir(), ".agent-brain", "brain"),
    join(homedir(), ".claude", "plugins", "ms-ai-toolkit", "brain"),
  ].filter(Boolean)
  for (const c of candidates) {
    if (existsSync(join(c, "brain-recall.py"))) return c
  }
  console.error(
    "[agent-brain] DISABLED: could not find the engine. Set BRAIN_SCRIPTS to the directory " +
      "holding brain-recall.py. Tried:\n" + candidates.map((c) => "  " + c).join("\n"),
  )
  return null
}

const SCRIPTS = resolveScripts()

/** Run one engine script with a JSON payload on stdin. Never rejects: a transport failure must
 *  not be able to wedge a turn, which is the same contract the Python holds itself to. */
function runScript(script, args, payload, timeoutMs = 8000) {
  return new Promise((done) => {
    let child
    try {
      child = spawn(PYTHON, [join(SCRIPTS, script), ...args], {
        stdio: ["pipe", "pipe", "pipe"],
        env: { ...process.env },
      })
    } catch (e) {
      log(script, "spawn failed:", e.message)
      return done("")
    }
    let out = "", err = ""
    const timer = setTimeout(() => {
      log(script, `timed out after ${timeoutMs}ms`)
      try { child.kill("SIGKILL") } catch {}
      done("")
    }, timeoutMs)
    child.stdout.on("data", (d) => (out += d))
    child.stderr.on("data", (d) => (err += d))
    child.on("error", (e) => { clearTimeout(timer); log(script, "error:", e.message); done("") })
    child.on("close", (code) => {
      clearTimeout(timer)
      if (code !== 0 && err) log(script, `exit ${code}:`, err.trim().slice(0, 400))
      else if (err) log(script, "stderr:", err.trim().slice(0, 400))
      done(out)
    })
    try {
      child.stdin.end(JSON.stringify(payload))
    } catch (e) {
      log(script, "stdin failed:", e.message)
    }
  })
}

export const AgentBrain = async ({ client, directory, worktree }) => {
  if (!SCRIPTS) return {}
  log("engine at", SCRIPTS)

  // Nudges raised at session.idle, waiting for the next turn to carry them. Keyed by session,
  // and only ever one per session because the Python writes a once-per-session marker.
  const pending = new Map()

  const cwd = worktree || directory || process.cwd()

  return {
    /** UserPromptSubmit: inject what the brain already knows about this prompt. */
    "chat.message": async (input, output) => {
      const sessionID = input?.sessionID || output?.message?.sessionID || ""
      const parts = output?.parts
      if (!Array.isArray(parts)) return

      const prompt = parts
        .filter((p) => p?.type === "text" && typeof p.text === "string" && !p.synthetic)
        .map((p) => p.text)
        .join("\n")
        .trim()
      if (!prompt) return

      const inject = []

      // The capture nudge from the previous turn goes FIRST: it is about work already done and
      // would otherwise be buried under recall results about the new question.
      const owed = pending.get(sessionID)
      if (owed) {
        pending.delete(sessionID)
        inject.push(owed)
        log("delivered a capture nudge for", sessionID)
      }

      const recall = (
        await runScript("brain-recall.py", [], { prompt, session_id: sessionID, cwd })
      ).trim()
      if (recall) {
        inject.push(recall)
        log(`injected ${recall.split("\n").length} recall lines`)
      }

      // synthetic marks the part as something the plugin added, not something the user typed.
      for (const text of inject) {
        parts.push({ type: "text", text, synthetic: true })
      }
    },

    /** Stop: if the session learned something and wrote none of it down, stash the nudge. */
    event: async ({ event }) => {
      if (event?.type !== "session.idle") return
      const sessionID = event?.properties?.sessionID
      if (!sessionID || pending.has(sessionID)) return

      let messages
      try {
        const res = await client.session.messages({ path: { id: sessionID } })
        messages = res?.data ?? res
      } catch (e) {
        log("could not read session messages:", e.message)
        return
      }
      if (!Array.isArray(messages)) return

      // Only the tool parts matter to the counter; sending message text as well would push a
      // whole transcript through a pipe for nothing.
      const slim = messages.map((m) => ({
        parts: (m?.parts || []).filter((p) => p?.type === "tool"),
      }))

      const nudge = (
        await runScript("brain-capture.py", ["--harness", "opencode"], { sessionID, messages: slim })
      ).trim()
      if (nudge) {
        pending.set(sessionID, nudge)
        log("capture nudge queued for", sessionID, "- delivers on the next turn")
      }
    },
  }
}

export default AgentBrain
