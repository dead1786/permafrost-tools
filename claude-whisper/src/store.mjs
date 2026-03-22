import { readFileSync, writeFileSync, mkdirSync, existsSync } from 'node:fs';
import { join } from 'node:path';
import { homedir } from 'node:os';

const STORE_DIR = join(homedir(), '.claude-whisper');
const STORE_FILE = join(STORE_DIR, 'whispers.json');

export function getStoreDir() {
  return STORE_DIR;
}


function isValidWhisper(w) {
  return w && typeof w.id === 'number' && typeof w.text === 'string' && w.id > 0;
}
export function getWhispers() {
  if (!existsSync(STORE_FILE)) return [];
  try {
    return JSON.parse(readFileSync(STORE_FILE, 'utf-8')).filter(isValidWhisper);
  } catch {
    return [];
  }
}

export function saveWhispers(whispers) {
  mkdirSync(STORE_DIR, { recursive: true });
  writeFileSync(STORE_FILE, JSON.stringify(whispers, null, 2), 'utf-8');
}

export function addWhisper(text) {
  const whispers = getWhispers();
  const id = whispers.length > 0
    ? Math.max(...whispers.map(w => w.id)) + 1
    : 1;
  const whisper = { id, text, active: true, created: new Date().toISOString() };
  whispers.push(whisper);
  saveWhispers(whispers);
  return whisper;
}

export function removeWhisper(id) {
  const whispers = getWhispers();
  const idx = whispers.findIndex(w => w.id === id);
  if (idx === -1) return null;
  const [removed] = whispers.splice(idx, 1);
  saveWhispers(whispers);
  return removed;
}

export function toggleWhisper(id) {
  const whispers = getWhispers();
  const whisper = whispers.find(w => w.id === id);
  if (!whisper) return null;
  whisper.active = !whisper.active;
  saveWhispers(whispers);
  return whisper;
}

export function clearWhispers() {
  saveWhispers([]);
}
