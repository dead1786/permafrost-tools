import { readFileSync, writeFileSync, mkdirSync, existsSync } from 'node:fs';
import { join } from 'node:path';
import { homedir } from 'node:os';

const STORE_DIR = join(homedir(), '.claude-whisper');
const STORE_FILE = join(STORE_DIR, 'whispers.json');

export function getStoreDir() {
  return STORE_DIR;
}


function isValidWhisper(w) {
  return w && typeof w.id === 'number' && typeof w.text === 'string' && w.id > 0 && w.text.trim().length > 0;
}

export function isExpired(w) {
  if (!w.expires) return false;
  return new Date(w.expires) <= new Date();
}

export function getWhispers({ includeExpired = false } = {}) {
  if (!existsSync(STORE_FILE)) return [];
  try {
    const all = JSON.parse(readFileSync(STORE_FILE, 'utf-8')).filter(isValidWhisper);
    return includeExpired ? all : all.filter(w => !isExpired(w));
  } catch {
    return [];
  }
}

export function saveWhispers(whispers) {
  mkdirSync(STORE_DIR, { recursive: true });
  writeFileSync(STORE_FILE, JSON.stringify(whispers, null, 2), 'utf-8');
}

export function addWhisper(text, { ttlHours } = {}) {
  const trimmed = text.trim();
  if (!trimmed) throw new Error('Whisper text cannot be empty.');
  const whispers = getWhispers({ includeExpired: true });
  const id = whispers.length > 0
    ? Math.max(...whispers.map(w => w.id)) + 1
    : 1;
  const whisper = { id, text: trimmed, active: true, created: new Date().toISOString() };
  if (ttlHours != null) {
    const exp = new Date();
    exp.setTime(exp.getTime() + ttlHours * 60 * 60 * 1000);
    whisper.expires = exp.toISOString();
  }
  whispers.push(whisper);
  saveWhispers(whispers);
  return whisper;
}

export function removeWhisper(id) {
  const whispers = getWhispers({ includeExpired: true });
  const idx = whispers.findIndex(w => w.id === id);
  if (idx === -1) return null;
  const [removed] = whispers.splice(idx, 1);
  saveWhispers(whispers);
  return removed;
}

export function toggleWhisper(id) {
  const whispers = getWhispers({ includeExpired: true });
  const whisper = whispers.find(w => w.id === id);
  if (!whisper) return null;
  whisper.active = !whisper.active;
  saveWhispers(whispers);
  return whisper;
}

export function clearWhispers() {
  saveWhispers([]);
}

export function purgeExpired() {
  const whispers = getWhispers({ includeExpired: true });
  const active = whispers.filter(w => !isExpired(w));
  const removed = whispers.length - active.length;
  if (removed > 0) saveWhispers(active);
  return removed;
}
