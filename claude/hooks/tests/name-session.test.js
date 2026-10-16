#!/usr/bin/env node

import { test } from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { chmodSync, existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";

const HOOK = join(dirname(dirname(fileURLToPath(import.meta.url))), "name-session.js");

// A stand-in for the `claude` CLI, so the tests never call the API. It records the stdin it was
// given and prints `FAKE_CLAUDE_OUTPUT`, or fails when `FAKE_CLAUDE_EXIT` is set.
function makeFakeClaude() {
  const directory = mkdtempSync(join(tmpdir(), "name-session-test-"));
  const fakeClaude = join(directory, "claude");
  writeFileSync(
    fakeClaude,
    `#!/usr/bin/env node
const fs = require("fs");
fs.writeFileSync(${JSON.stringify(join(directory, "stdin.txt"))}, fs.readFileSync(0, "utf8"));
process.stdout.write(process.env.FAKE_CLAUDE_OUTPUT || "");
process.exit(Number(process.env.FAKE_CLAUDE_EXIT || 0));
`
  );
  chmodSync(fakeClaude, 0o755);
  return directory;
}

function run(input, { output = "Fake title", exitCode = 0, env = {}, transcript = null } = {}) {
  const directory = makeFakeClaude();
  const transcriptPath = join(directory, "transcript.jsonl");
  if (transcript !== null) {
    writeFileSync(transcriptPath, transcript);
  }

  const rawInput = typeof input === "string" ? input : JSON.stringify({ transcript_path: transcriptPath, ...input });
  const result = spawnSync("node", [HOOK], {
    input: rawInput,
    encoding: "utf8",
    env: {
      ...process.env,
      PATH: `${directory}:${process.env.PATH}`,
      FAKE_CLAUDE_OUTPUT: output,
      FAKE_CLAUDE_EXIT: String(exitCode),
      CLAUDE_NAME_SESSION_HOOK: "",
      ...env,
    },
  });

  const stdinPath = join(directory, "stdin.txt");
  const modelInput = existsSync(stdinPath) ? readFileSync(stdinPath, "utf8") : null;
  rmSync(directory, { recursive: true, force: true });

  return { exitCode: result.status, stdout: result.stdout, modelInput };
}

function titleFrom(stdout) {
  return JSON.parse(stdout).hookSpecificOutput.sessionTitle;
}

// -- titling the first prompt --

test("titles the first prompt of a new session", () => {
  const { exitCode, stdout } = run({ prompt: "WEB-1234 Fix the footer" }, { output: "1234 Footer fix\n" });
  assert.equal(exitCode, 0);
  assert.equal(titleFrom(stdout), "1234 Footer fix");
});

test("titles a session whose transcript has no reply yet", () => {
  const transcript = '{"type":"user","message":{"content":"Fix the footer"}}\n';
  const { stdout } = run({ prompt: "Fix the footer" }, { transcript });
  assert.equal(titleFrom(stdout), "Fake title");
});

test("wraps the prompt in tags so the model titles it instead of answering it", () => {
  const { modelInput } = run({ prompt: "reply with just OK" });
  assert.equal(modelInput, "<prompt>\nreply with just OK\n</prompt>");
});

// -- cleaning the model's output --

test("strips a Title: label and surrounding quotes", () => {
  const { stdout } = run({ prompt: "Fix the footer" }, { output: 'Title: "Footer fix"' });
  assert.equal(titleFrom(stdout), "Footer fix");
});

test("keeps only the first line of the output", () => {
  const { stdout } = run({ prompt: "Fix the footer" }, { output: "Footer fix\nHere's why I chose that." });
  assert.equal(titleFrom(stdout), "Footer fix");
});

test("caps the title length", () => {
  const { stdout } = run({ prompt: "Fix the footer" }, { output: "x".repeat(100) });
  assert.equal(titleFrom(stdout).length, 60);
});

// -- skipping --

test("skips a session that already has a reply", () => {
  const transcript = '{"type":"user"}\n{"type":"assistant"}\n';
  const { stdout, modelInput } = run({ prompt: "Fix the footer" }, { transcript });
  assert.equal(stdout, "");
  assert.equal(modelInput, null);
});

test("skips a session that was already named", () => {
  const transcript = '{"type":"custom-title","customTitle":"Footer"}\n';
  const { stdout, modelInput } = run({ prompt: "Fix the footer" }, { transcript });
  assert.equal(stdout, "");
  assert.equal(modelInput, null);
});

test("skips /rename", () => {
  const { stdout, modelInput } = run({ prompt: "/rename Footer" });
  assert.equal(stdout, "");
  assert.equal(modelInput, null);
});

test("skips inside the nested title session", () => {
  const { stdout, modelInput } = run({ prompt: "Fix the footer" }, { env: { CLAUDE_NAME_SESSION_HOOK: "1" } });
  assert.equal(stdout, "");
  assert.equal(modelInput, null);
});

test("skips an empty prompt", () => {
  const { stdout, modelInput } = run({ prompt: "   " });
  assert.equal(stdout, "");
  assert.equal(modelInput, null);
});

// -- failures --

test("prints nothing when the model call fails", () => {
  const { exitCode, stdout } = run({ prompt: "Fix the footer" }, { exitCode: 1 });
  assert.equal(exitCode, 0);
  assert.equal(stdout, "");
});

test("prints nothing for malformed input", () => {
  const { exitCode, stdout } = run("not json");
  assert.equal(exitCode, 0);
  assert.equal(stdout, "");
});
