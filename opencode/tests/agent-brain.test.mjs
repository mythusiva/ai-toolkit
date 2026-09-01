// Seam probe for the opencode transport: real engine, throwaway brain, fake client.
// The Python decisions are covered by brain-selftest.py; this covers the JS carrying them.
//   node opencode/plugin/agent-brain.test.mjs
// Drives the opencode plugin against a throwaway brain with a fake client, proving the JS
// transport carries real values in both directions.
import { AgentBrain } from "../plugin/agent-brain.js"
import { execFileSync } from "node:child_process"
import { mkdtempSync, rmSync } from "node:fs"
import { tmpdir } from "node:os"
import { dirname, join, resolve } from "node:path"
import { fileURLToPath } from "node:url"

const BRAIN = resolve(dirname(fileURLToPath(import.meta.url)), "../../ms-ai-toolkit/brain")
const tmp = mkdtempSync(join(tmpdir(), "brain-plugin-"))
const repo = join(tmp, "checkouts", "widget-service")
Object.assign(process.env, {
  BRAIN_SCRIPTS: BRAIN, BRAIN_HOME: join(tmp, "state"), BRAIN_DB: join(tmp, "brain.db"),
  BRAIN_REPO_ROOT: join(tmp, "checkouts"),
})
const sh = (c, a, o = {}) => execFileSync(c, a, { encoding: "utf8", ...o })
let fails = 0, passed = 0
const check = (n, c, d = "") => c ? (passed++, console.log("  ok   " + n))
  : (fails++, console.log("  FAIL " + n + (d ? "\n       " + d : "")))

try {
  sh("mkdir", ["-p", join(repo, "src")])
  sh("python3", [join(BRAIN, "brain-init.py")])
  sh("git", ["init", "-q"], { cwd: repo })
  sh("git", ["config", "user.email", "t@t"], { cwd: repo })
  sh("git", ["config", "user.name", "t"], { cwd: repo })
  sh("bash", ["-c", `echo 'export class OtpThrottle {}' > ${join(repo, "src/throttle.ts")}`])
  sh("git", ["add", "-A"], { cwd: repo }); sh("git", ["commit", "-qm", "i"], { cwd: repo })
  sh("python3", [join(BRAIN, "brain-note.py"), "map", "widget-service", "src/throttle.ts",
                 "OtpThrottle", "throttles otp sends per msisdn"])

  // A fake opencode client: 10 read tool parts, no brain write -> capture must fire.
  const toolParts = Array.from({ length: 10 }, (_, i) => ({
    type: "tool", tool: "read",
    state: { status: "completed", input: { filePath: `/x/f${i}.ts` } },
  }))
  const client = {
    session: { messages: async () => ({ data: [{ info: {}, parts: toolParts }] }) },
  }

  const hooks = await AgentBrain({ client, directory: repo, worktree: repo })
  check("plugin exposes chat.message", typeof hooks["chat.message"] === "function")
  check("plugin exposes event", typeof hooks.event === "function")

  // --- recall through the JS transport ---
  const parts = [{ type: "text", text: "where does OtpThrottle live" }]
  await hooks["chat.message"]({ sessionID: "s1" }, { message: {}, parts })
  const added = parts.filter((p) => p.synthetic)
  check("recall injected a synthetic part", added.length === 1, JSON.stringify(parts))
  check("injected part carries the real row",
    added[0]?.text.includes("OtpThrottle") && added[0]?.text.includes("code_map"),
    added[0]?.text?.slice(0, 200))

  const p2 = [{ type: "text", text: "write me a haiku about rain" }]
  await hooks["chat.message"]({ sessionID: "s2" }, { message: {}, parts: p2 })
  check("silent on an unrelated prompt", p2.filter((p) => p.synthetic).length === 0,
    JSON.stringify(p2))

  // --- capture: idle stashes, next turn delivers ---
  await hooks.event({ event: { type: "session.idle", properties: { sessionID: "s3" } } })
  const p3 = [{ type: "text", text: "ok next question" }]
  await hooks["chat.message"]({ sessionID: "s3" }, { message: {}, parts: p3 })
  const nudge = p3.find((p) => p.synthetic && p.text.includes("BRAIN CAPTURE"))
  check("idle queued a nudge, next turn delivered it", !!nudge,
    JSON.stringify(p3.map((p) => (p.text || "").slice(0, 80))))
  check("nudge names the helper command",
    !!nudge && nudge.text.includes("brain-note.py"), nudge?.text?.slice(0, 200))

  const p4 = [{ type: "text", text: "and another" }]
  await hooks["chat.message"]({ sessionID: "s3" }, { message: {}, parts: p4 })
  check("nudge is delivered once, not every turn",
    !p4.some((p) => (p.text || "").includes("BRAIN CAPTURE")))

  await hooks.event({ event: { type: "session.idle", properties: { sessionID: "s3" } } })
  const p5 = [{ type: "text", text: "third" }]
  await hooks["chat.message"]({ sessionID: "s3" }, { message: {}, parts: p5 })
  check("a second idle does not re-nudge the same session",
    !p5.some((p) => (p.text || "").includes("BRAIN CAPTURE")))

  // --- other events are ignored, and a broken client cannot throw ---
  await hooks.event({ event: { type: "file.edited", properties: {} } })
  check("ignores unrelated events", true)
  const bad = await AgentBrain({
    client: { session: { messages: async () => { throw new Error("boom") } } },
    directory: repo, worktree: repo,
  })
  await bad.event({ event: { type: "session.idle", properties: { sessionID: "s9" } } })
  check("survives a client that throws", true)
} catch (e) {
  fails++; console.log("  FAIL threw: " + e.stack)
} finally {
  rmSync(tmp, { recursive: true, force: true })
}
console.log(fails ? `\nFAILED ${fails} of ${fails + passed}` : `\nok - ${passed} checks passed`)
process.exit(fails ? 1 : 0)
