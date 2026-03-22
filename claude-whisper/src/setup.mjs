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
  try {
    return JSON.parse(readFileSync(SETTINGS_FILE, 'utf-8'));
  } catch {
    return {};
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
  if (!settings.hooks?.UserPromptSubmit) return false;

  const before = settings.hooks.UserPromptSubmit.length;

  // Remove whisper entries
  settings.hooks.UserPromptSubmit = settings.hooks.UserPromptSubmit.filter(entry => {
    if (isWhisperHook(entry)) return false;
    if (entry.hooks && Array.isArray(entry.hooks)) {
      entry.hooks = entry.hooks.filter(h => !isWhisperHook(h));
      return entry.hooks.length > 0;
    }
    return true;
  });

  if (settings.hooks.UserPromptSubmit.length === 0) {
    delete settings.hooks.UserPromptSubmit;
  }
  if (Object.keys(settings.hooks).length === 0) {
    delete settings.hooks;
  }

  writeSettings(settings);
  return settings.hooks?.UserPromptSubmit?.length !== before;
}

export function isInstalled() {
  const settings = readSettings();
  const entries = settings.hooks?.UserPromptSubmit ?? [];
  return entries.some(entry => {
    if (isWhisperHook(entry)) return true;
    if (entry.hooks && Array.isArray(entry.hooks)) {
      return entry.hooks.some(h => isWhisperHook(h));
    }
    return false;
  });
}
