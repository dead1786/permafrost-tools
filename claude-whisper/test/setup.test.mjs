// Tests for src/setup.mjs. Run: node --test claude-whisper/test/
// Uses a throwaway HOME so the real ~/.claude/settings.json is never touched.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, mkdirSync, writeFileSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const home = mkdtempSync(join(tmpdir(), 'cw-test-'));
process.env.HOME = home;
process.env.USERPROFILE = home;
mkdirSync(join(home, '.claude'), { recursive: true });
const settingsPath = join(home, '.claude', 'settings.json');

// Import after HOME is set: setup.mjs resolves paths at module load.
const { install, uninstall, isInstalled } = await import('../src/setup.mjs');

const readJson = () => JSON.parse(readFileSync(settingsPath, 'utf-8'));
const other = { type: 'command', command: 'python other-hook.py' };

test('install keeps existing hooks; uninstall removes only whisper', () => {
  writeFileSync(settingsPath, JSON.stringify({ model: 'x', hooks: { UserPromptSubmit: [{ hooks: [other] }] } }));
  install();
  assert.equal(isInstalled(), true);
  assert.equal(readJson().hooks.UserPromptSubmit.length, 2);

  assert.equal(uninstall(), true);
  assert.equal(isInstalled(), false);
  const s = readJson();
  assert.equal(s.model, 'x');
  assert.deepEqual(s.hooks.UserPromptSubmit, [{ hooks: [other] }]);
});

test('uninstall returns true when whisper shares a matcher group with another hook', () => {
  install();
  const s = readJson();
  const whisper = s.hooks.UserPromptSubmit[1].hooks[0];
  s.hooks.UserPromptSubmit = [{ hooks: [other, whisper] }]; // same array length before/after removal
  writeFileSync(settingsPath, JSON.stringify(s));

  assert.equal(uninstall(), true);
  assert.deepEqual(readJson().hooks.UserPromptSubmit, [{ hooks: [other] }]);
});

test('uninstall is a no-op (returns false, file untouched) when nothing is registered', () => {
  const raw = JSON.stringify({ model: 'y' });
  writeFileSync(settingsPath, raw);
  assert.equal(uninstall(), false);
  assert.equal(readFileSync(settingsPath, 'utf-8'), raw);
});

test('uninstall drops empty hooks object when whisper was the only hook', () => {
  writeFileSync(settingsPath, JSON.stringify({ model: 'z' }));
  install();
  assert.equal(uninstall(), true);
  assert.deepEqual(readJson(), { model: 'z' });
});

test('corrupt settings.json is never overwritten', () => {
  const corrupt = '{ "model": "x", "permissions": ';
  writeFileSync(settingsPath, corrupt);
  assert.throws(() => install(), /not valid JSON/);
  assert.throws(() => uninstall(), /not valid JSON/);
  assert.equal(isInstalled(), false);
  assert.equal(readFileSync(settingsPath, 'utf-8'), corrupt);
});
