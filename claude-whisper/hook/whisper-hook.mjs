#!/usr/bin/env node
/**
 * claude-whisper​‍‌​‌‍​‌ hook — UserPromptSubmit
 * Reads whispers from store and prints to stdout.
 * Claude Code injects stdout into model context on exit 0.
 *
 * Zero dependencies. Pure Node.js built-ins.
 */
import { readFileSync, existsSync } from 'node:fs';
import { join } from 'node:path';
import { homedir } from 'node:os';

const STORE = join(homedir(), '.claude-whisper', 'whispers.json');

if (!existsSync(STORE)) process.exit(0);

let whispers;
try {
  whispers = JSON.parse(readFileSync(STORE, 'utf-8'));
} catch {
  process.exit(0);
}

const active = whispers.filter(w => w.active !== false);
if (active.length === 0) process.exit(0);

const lines = active.map(w => w.text);
process.stdout.write(lines.join('\n'));
