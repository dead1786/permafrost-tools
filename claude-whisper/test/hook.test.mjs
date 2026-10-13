// Tests for hook/whisper-hook.mjs. Run: node --test claude-whisper/test/hook.test.mjs
// Uses a throwaway HOME so the real ~/.claude-whisper store is never read.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, mkdirSync, writeFileSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { tmpdir } from 'node:os';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const hook = join(dirname(fileURLToPath(import.meta.url)), '..', 'hook', 'whisper-hook.mjs');

function run(storeContent) {
  const home = mkdtempSync(join(tmpdir(), 'cw-hook-'));
  if (storeContent !== undefined) {
    mkdirSync(join(home, '.claude-whisper'), { recursive: true });
    writeFileSync(join(home, '.claude-whisper', 'whispers.json'), storeContent);
  }
  return spawnSync(process.execPath, [hook], {
    env: { ...process.env, HOME: home, USERPROFILE: home },
    encoding: 'utf-8',
  });
}

test('prints active whispers, skips inactive and expired', () => {
  const past = new Date(Date.now() - 3600e3).toISOString();
  const r = run(JSON.stringify([
    { id: 1, text: 'keep me', active: true },
    { id: 2, text: 'off', active: false },
    { id: 3, text: 'old', expires: past },
  ]));
  assert.equal(r.status, 0);
  assert.equal(r.stdout, 'keep me\n');
});

test('no store file: silent exit 0', () => {
  const r = run(undefined);
  assert.equal(r.status, 0);
  assert.equal(r.stdout, '');
});

test('malformed stores never crash the hook (exit 0, no output)', () => {
  for (const bad of ['not json', '{"a":1}', 'null', '[null, 42, {"id":1}, {"text":"  "}]']) {
    const r = run(bad);
    assert.equal(r.status, 0, `store ${bad}: ${r.stderr}`);
    assert.equal(r.stdout, '', `store ${bad}`);
  }
});

test('valid entries still print alongside malformed ones', () => {
  const r = run(JSON.stringify([null, { text: 'ok' }, 5]));
  assert.equal(r.status, 0);
  assert.equal(r.stdout, 'ok\n');
});
