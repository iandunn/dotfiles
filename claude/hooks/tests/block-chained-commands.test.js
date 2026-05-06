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

// -- git -C --

test("blocks git -C with path", () => {
  const { exitCode, stderr } = run("git -C /some/path status");
  assert.equal(exitCode, BLOCK_EXIT);
  assert.match(stderr, /git -C/i);
});

test("blocks git -C with relative path", () => {
  const { exitCode } = run("git -C ../other log");
  assert.equal(exitCode, BLOCK_EXIT);
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
