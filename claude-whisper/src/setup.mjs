import { readFileSync, writeFileSync, mkdirSync, copyFileSync, existsSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { homedir } from 'node:os';
import { fileURLToPath } from 'node:url';
import { getStoreDir } from './store.mjs';

const CLAUDE_DIR = join(homedir(), '.claude');
const SETTINGS_FILE = join(CLAUDE_DIR, 'settings.json');
const HOOK_SOURCE = resolve(fileURLToPath(import.meta.url), '../../hook/whisper-hook.mjs');
const HOOK_DEST = join(getStoreDir(), 'hook.mjs');

function getHookCommand() {
  // Use forward slashes for cross-platform compatibility in shell
  const hookPath = HOOK_DEST.replace(/\\/g, '/');
  return `node "${hookPath}"`;
}

function readSettings() {
  if (!existsSync(SETTINGS_FILE)) return {};
  const raw = readFileSync(SETTINGS_FILE, 'utf-8');
  if (!raw.trim()) return {};
  try {
    return JSON.parse(raw);
  } catch (e) {
    // Never fall back to {}: callers write the result back, which would
    // replace the user's entire settings.json with just our hook entry.
    throw new Error(
      `${SETTINGS_FILE} exists but is not valid JSON (${e.message}).
` +
      `Refusing to touch it - fix the JSON manually, then re-run.`
    );
  }
}

function writeSettings(settings) {
  mkdirSync(CLAUDE_DIR, { recursive: true });
  writeFileSync(SETTINGS_FILE, JSON.stringify(settings, null, 2), 'utf-8');
}

function isWhisperHook(hook) {
  return hook?.type === 'command' && hook?.command?.includes('claude-whisper');
}

export function install() {
  // 1. Copy hook script to ~/.claude-whisper/
  if (!existsSync(HOOK_SOURCE)) {
    throw new Error(
      `Hook source not found: ${HOOK_SOURCE}\n` +
      `This usually means the package was not installed correctly. Try reinstalling.`
    );
  }
  mkdirSync(getStoreDir(), { recursive: true });
  copyFileSync(HOOK_SOURCE, HOOK_DEST);

  // 2. Register in settings.json
  const settings = readSettings();
  if (!settings.hooks) settings.hooks = {};
  if (!settings.hooks.UserPromptSubmit) settings.hooks.UserPromptSubmit = [];

  const existing = settings.hooks.UserPromptSubmit;

  // Check if already installed (in hooks array or hooks[].hooks array)
  const alreadyInstalled = existing.some(entry => {
    if (isWhisperHook(entry)) return true;
    if (entry.hooks && Array.isArray(entry.hooks)) {
      return entry.hooks.some(h => isWhisperHook(h));
    }
    return false;
  });

  if (!alreadyInstalled) {
    existing.push({
      hooks: [{
        type: 'command',
        command: getHookCommand(),
        timeout: 2
      }]
    });
    writeSettings(settings);
  }

  return { hookPath: HOOK_DEST, settingsPath: SETTINGS_FILE };
}

export function uninstall() {
  const settings = readSettings();
  const entries = settings.hooks?.UserPromptSubmit;
  if (!Array.isArray(entries)) return false;

  let removed = 0;
  const remaining = [];
  for (const entry of entries) {
    if (isWhisperHook(entry)) {
      removed++;
      continue;
    }
    if (Array.isArray(entry?.hooks)) {
      const kept = entry.hooks.filter(h => !isWhisperHook(h));
      removed += entry.hooks.length - kept.length;
      if (kept.length === 0) continue;
      entry.hooks = kept;
    }
    remaining.push(entry);
  }

  // Nothing of ours in there: leave settings.json untouched.
  if (removed === 0) return false;

  if (remaining.length > 0) {
    settings.hooks.UserPromptSubmit = remaining;
  } else {
    delete settings.hooks.UserPromptSubmit;
  }
  if (Object.keys(settings.hooks).length === 0) {
    delete settings.hooks;
  }

  writeSettings(settings);
  return true;
}

export function isInstalled() {
  let settings;
  try {
    settings = readSettings();
  } catch {
    return false; // unreadable settings.json: report "not installed"; init/uninstall surface the real error
  }
  const entries = settings.hooks?.UserPromptSubmit ?? [];
  return entries.some(entry => {
    if (isWhisperHook(entry)) return true;
    if (entry.hooks && Array.isArray(entry.hooks)) {
      return entry.hooks.some(h => isWhisperHook(h));
    }
    return false;
  });
}
