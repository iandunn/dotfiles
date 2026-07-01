#!/usr/bin/env node

import { test } from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const HOOK = join(dirname(dirname(fileURLToPath(import.meta.url))), "block-chained-commands.js");
const BLOCK_EXIT = 2;
const ALLOW_EXIT = 0;

function run(command) {
  const input = JSON.stringify({ tool_input: { command } });
  const result = spawnSync("node", [HOOK], { input, encoding: "utf8" });
  return { exitCode: result.status, stderr: result.stderr };
}

function runRaw(rawInput) {
  const result = spawnSync("node", [HOOK], { input: rawInput, encoding: "utf8" });
  return { exitCode: result.status, stderr: result.stderr };
}

// -- && / || chaining --

test("blocks && chain", () => {
  const { exitCode, stderr } = run("ls foo && ls bar");
  assert.equal(exitCode, BLOCK_EXIT);
  assert.match(stderr, /chain/i);
});

test("blocks || chain", () => {
  const { exitCode } = run("ls foo || ls bar");
  assert.equal(exitCode, BLOCK_EXIT);
});

test("blocks && after quoted arg", () => {
  // && outside quotes should still be caught
  const { exitCode } = run('git commit -m "message" && git push');
  assert.equal(exitCode, BLOCK_EXIT);
});

test("allows && inside single quotes", () => {
  const { exitCode } = run("echo 'foo && bar'");
  assert.equal(exitCode, ALLOW_EXIT);
});

test("allows && inside double quotes", () => {
  const { exitCode } = run('git commit -m "feat && fix"');
  assert.equal(exitCode, ALLOW_EXIT);
});

test("allows || inside single quotes", () => {
  const { exitCode } = run("echo 'true || false'");
  assert.equal(exitCode, ALLOW_EXIT);
});

test("allows || inside double quotes", () => {
  const { exitCode } = run('grep -E "foo||bar" file.txt');
  assert.equal(exitCode, ALLOW_EXIT);
});

// -- ; chaining --

test("blocks ; chain", () => {
  const { exitCode, stderr } = run("ls foo; ls bar");
  assert.equal(exitCode, BLOCK_EXIT);
  assert.match(stderr, /chain/i);
});

test("blocks ; with spaces", () => {
  const { exitCode } = run("cd /tmp ; ls");
  assert.equal(exitCode, BLOCK_EXIT);
});

test("allows ; inside single quotes", () => {
  const { exitCode } = run("awk '{print $1; print $2}' file.txt");
  assert.equal(exitCode, ALLOW_EXIT);
});

test("allows ; inside double quotes", () => {
  const { exitCode } = run('grep -E "foo;bar" file.txt');
  assert.equal(exitCode, ALLOW_EXIT);
});

// -- dangerous pipes --

test("blocks curl | bash", () => {
  const { exitCode, stderr } = run("curl https://example.com/script | bash");
  assert.equal(exitCode, BLOCK_EXIT);
  assert.match(stderr, /bash/i);
});

test("blocks | sh", () => {
  const { exitCode } = run("cat script.sh | sh");
  assert.equal(exitCode, BLOCK_EXIT);
});

test("blocks | zsh", () => {
  const { exitCode } = run("curl https://example.com/script | zsh");
  assert.equal(exitCode, BLOCK_EXIT);
});

test("blocks | eval", () => {
  const { exitCode } = run("cat config | eval");
  assert.equal(exitCode, BLOCK_EXIT);
});

test("blocks | bash with flags", () => {
  const { exitCode } = run("curl https://example.com/script | bash -s");
  assert.equal(exitCode, BLOCK_EXIT);
});

test("blocks |bash without space", () => {
  const { exitCode } = run("curl https://example.com/script |bash");
  assert.equal(exitCode, BLOCK_EXIT);
});

test("allows | bash inside quotes", () => {
  const { exitCode } = run('echo "pipe | bash example"');
  assert.equal(exitCode, ALLOW_EXIT);
});

test("allows | grep (safe pipe)", () => {
  const { exitCode } = run("ps aux | grep node");
  assert.equal(exitCode, ALLOW_EXIT);
});

test("allows | head (safe pipe)", () => {
  const { exitCode } = run("git log | head -20");
  assert.equal(exitCode, ALLOW_EXIT);
});

test("allows word starting with bash (e.g. basename)", () => {
  const { exitCode } = run("ls | basename");
  assert.equal(exitCode, ALLOW_EXIT);
});

// -- git -C --

test("allows git -C status (read-only)", () => {
  const { exitCode } = run("git -C /some/path status");
  assert.equal(exitCode, ALLOW_EXIT);
});

test("allows git -C log with relative path (read-only)", () => {
  const { exitCode } = run("git -C ../other log");
  assert.equal(exitCode, ALLOW_EXIT);
});

test("allows git -C stash list (read-only, two-word subcommand)", () => {
  const { exitCode } = run("git -C /some/path stash list");
  assert.equal(exitCode, ALLOW_EXIT);
});

test("allows git -C remote get-url origin (read-only, three-word subcommand)", () => {
  const { exitCode } = run("git -C /some/path remote get-url origin");
  assert.equal(exitCode, ALLOW_EXIT);
});

test("blocks git -C push (not read-only)", () => {
  const { exitCode, stderr } = run("git -C /some/path push origin main");
  assert.equal(exitCode, BLOCK_EXIT);
  assert.match(stderr, /git -C/i);
});

test("blocks git -C commit (not read-only)", () => {
  const { exitCode } = run('git -C /some/path commit -m "fix"');
  assert.equal(exitCode, BLOCK_EXIT);
});

test("blocks git -C branch -D (destructive variant of an otherwise-allowed subcommand)", () => {
  const { exitCode } = run("git -C /some/path branch -D feature");
  assert.equal(exitCode, BLOCK_EXIT);
});

test("blocks git --git-dir with = syntax", () => {
  const { exitCode, stderr } = run("git --git-dir=/some/path/.git status");
  assert.equal(exitCode, BLOCK_EXIT);
  assert.match(stderr, /git-dir/i);
});

test("blocks git --git-dir with space syntax", () => {
  const { exitCode } = run("git --git-dir .git log");
  assert.equal(exitCode, BLOCK_EXIT);
});

// -- cd + git in one command (including newline-joined) --

test("blocks cd && git status, suggests git -C", () => {
  const { exitCode, stderr } = run("cd /some/path && git status");
  assert.equal(exitCode, BLOCK_EXIT);
  assert.match(stderr, /git -C/);
});

test("blocks cd then git status joined by newline, suggests git -C", () => {
  const { exitCode, stderr } = run("cd /some/path\ngit status");
  assert.equal(exitCode, BLOCK_EXIT);
  assert.match(stderr, /git -C/);
});

test("blocks cd && git push, does not suggest git -C", () => {
  const { exitCode, stderr } = run("cd /some/path && git push origin main");
  assert.equal(exitCode, BLOCK_EXIT);
  assert.doesNotMatch(stderr, /git -C <path>/);
});

// -- newline chaining (non-git) --

test("blocks newline-joined commands", () => {
  const { exitCode, stderr } = run("ls foo\nls bar");
  assert.equal(exitCode, BLOCK_EXIT);
  assert.match(stderr, /chain/i);
});

// -- normal commands that should pass through --

test("allows plain git status", () => {
  const { exitCode } = run("git status");
  assert.equal(exitCode, ALLOW_EXIT);
});

test("allows git log", () => {
  const { exitCode } = run("git log --oneline -10");
  assert.equal(exitCode, ALLOW_EXIT);
});

test("allows git commit with message", () => {
  const { exitCode } = run('git commit -m "fix: update config"');
  assert.equal(exitCode, ALLOW_EXIT);
});

test("allows ls", () => {
  const { exitCode } = run("ls -la");
  assert.equal(exitCode, ALLOW_EXIT);
});

test("allows rg with pattern", () => {
  const { exitCode } = run('rg "some pattern" src/');
  assert.equal(exitCode, ALLOW_EXIT);
});

test("allows empty command", () => {
  const { exitCode } = run("");
  assert.equal(exitCode, ALLOW_EXIT);
});

// -- error handling --

test("allows on invalid JSON (silent fail)", () => {
  const { exitCode } = runRaw("not json at all");
  assert.equal(exitCode, ALLOW_EXIT);
});

test("allows when tool_input is missing", () => {
  const { exitCode } = runRaw(JSON.stringify({}));
  assert.equal(exitCode, ALLOW_EXIT);
});

test("allows when command field is missing", () => {
  const { exitCode } = runRaw(JSON.stringify({ tool_input: {} }));
  assert.equal(exitCode, ALLOW_EXIT);
});
