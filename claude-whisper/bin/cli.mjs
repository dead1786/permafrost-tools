#!/usr/bin/env node
const VERSION = '1.1.0'; // cw-v1
import { addWhisper, getWhispers, removeWhisper, toggleWhisper, clearWhispers, purgeExpired, isExpired } from '../src/store.mjs';
import { install, uninstall, isInstalled } from '../src/setup.mjs';

const [,, command, ...rest] = process.argv;

const RESET = '\x1b[0m';
const BOLD = '\x1b[1m';
const DIM = '\x1b[2m';
const GREEN = '\x1b[32m';
const YELLOW = '\x1b[33m';
const RED = '\x1b[31m';
const CYAN = '\x1b[36m';
const GRAY = '\x1b[90m';

function log(msg = '') { console.log(msg); }

function showHelp() {
  log();
  log(`${BOLD}claude-whisper${RESET} ${DIM}— Dynamic runtime instructions for Claude Code${RESET}`);
  log();
  log(`${BOLD}Usage:${RESET}`);
  log(`  ${CYAN}claude-whisper init${RESET}                    Install the hook into Claude Code`);
  log(`  ${CYAN}claude-whisper add ${DIM}<text>${RESET}               Add a new whisper`);
  log(`  ${CYAN}claude-whisper add ${DIM}--ttl <hours> <text>${RESET}  Add a whisper that expires after N hours`);
  log(`  ${CYAN}claude-whisper ls${RESET}                      List all whispers`);
  log(`  ${CYAN}claude-whisper toggle ${DIM}<id>${RESET}             Enable/disable a whisper`);
  log(`  ${CYAN}claude-whisper rm ${DIM}<id>${RESET}                 Remove a whisper`);
  log(`  ${CYAN}claude-whisper purge${RESET}                   Remove all expired whispers`);
  log(`  ${CYAN}claude-whisper clear${RESET}                   Remove all whispers`);
  log(`  ${CYAN}claude-whisper uninstall${RESET}               Remove the hook from Claude Code`);
  log(`  ${CYAN}claude-whisper status${RESET}                  Check installation status`);
  log(`  ${CYAN}claude-whisper version${RESET}                 Show version`);
  log();
  log(`${BOLD}Shorthand:${RESET} ${DIM}You can also use${RESET} ${CYAN}cw${RESET} ${DIM}instead of${RESET} ${CYAN}claude-whisper${RESET}`);
  log();
  log(`${BOLD}How it works:${RESET}`);
  log(`  Whispers are injected into Claude's context via the UserPromptSubmit hook.`);
  log(`  Every message you send to Claude will include your active whispers.`);
  log(`  ${DIM}CLAUDE.md is your constitution. Whispers are your mood.${RESET}`);
  log();
  log(`${BOLD}TTL examples:${RESET}`);
  log(`  ${CYAN}cw add --ttl 2 "Use bullet points"${RESET}      ${DIM}# expires in 2 hours${RESET}`);
  log(`  ${CYAN}cw add --ttl 24 "Focus on performance"${RESET}  ${DIM}# expires in 24 hours${RESET}`);
  log();
}

function formatExpiry(w) {
  if (!w.expires) return '';
  const exp = new Date(w.expires);
  const now = new Date();
  const diffMs = exp - now;
  if (diffMs <= 0) return ` ${RED}[expired]${RESET}`;
  const diffH = Math.floor(diffMs / 3600000);
  const diffM = Math.floor((diffMs % 3600000) / 60000);
  if (diffH >= 24) {
    const days = Math.floor(diffH / 24);
    return ` ${YELLOW}[expires in ${days}d]${RESET}`;
  }
  if (diffH > 0) return ` ${YELLOW}[expires in ${diffH}h ${diffM}m]${RESET}`;
  return ` ${YELLOW}[expires in ${diffM}m]${RESET}`;
}

function formatWhisper(w) {
  const status = w.active !== false
    ? `${GREEN}ON ${RESET}`
    : `${RED}OFF${RESET}`;
  return `  ${GRAY}#${w.id}${RESET} [${status}] ${w.text}${formatExpiry(w)}`;
}

switch (command) {
  case 'init': {
    if (isInstalled()) {
      log(`${YELLOW}Already installed.${RESET} Whisper hook is active.`);
      break;
    }
    const result = install();
    log();
    log(`${GREEN}${BOLD}Installed.${RESET}`);
    log(`  Hook: ${DIM}${result.hookPath}${RESET}`);
    log(`  Config: ${DIM}${result.settingsPath}${RESET}`);
    log();
    log(`Get started:`);
    log(`  ${CYAN}claude-whisper add "Always respond concisely"${RESET}`);
    log();
    break;
  }

  case 'add': {
    // Parse optional --ttl <hours> flag
    let ttlHours = null;
    const ttlIdx = rest.indexOf('--ttl');
    const filteredRest = [...rest];
    if (ttlIdx !== -1) {
      const ttlVal = parseFloat(rest[ttlIdx + 1]);
      if (isNaN(ttlVal) || ttlVal <= 0) {
        log(`${RED}Error:${RESET} --ttl requires a positive number of hours.`);
        log(`  ${DIM}Example: claude-whisper add --ttl 2 "Use bullet points"${RESET}`);
        process.exit(1);
      }
      ttlHours = ttlVal;
      filteredRest.splice(ttlIdx, 2);
    }
    const text = filteredRest.join(' ').trim();
    if (!text) {
      log(`${RED}Error:${RESET} Provide whisper text.`);
      log(`  ${DIM}Example: claude-whisper add "Always use TypeScript"${RESET}`);
      log(`  ${DIM}With TTL:  claude-whisper add --ttl 2 "Use bullet points"${RESET}`);
      process.exit(1);
    }
    if (!isInstalled()) {
      log(`${YELLOW}Hook not installed.${RESET} Run ${CYAN}claude-whisper init${RESET} first.`);
      process.exit(1);
    }
    const whisper = addWhisper(text, { ttlHours });
    const expiry = ttlHours != null ? ` ${YELLOW}(expires in ${ttlHours}h)${RESET}` : '';
    log(`${GREEN}Added${RESET} whisper ${GRAY}#${whisper.id}${RESET}: ${text}${expiry}`);
    break;
  }

  case 'ls':
  case 'list': {
    const whispers = getWhispers({ includeExpired: true });
    if (whispers.length === 0) {
      log(`${DIM}No whispers. Add one:${RESET} ${CYAN}claude-whisper add "..."${RESET}`);
      break;
    }
    const activeCount = whispers.filter(w => w.active !== false && !isExpired(w)).length;
    const expiredCount = whispers.filter(w => isExpired(w)).length;
    log();
    const expiredNote = expiredCount > 0 ? `, ${expiredCount} expired` : '';
    log(`${BOLD}Whispers${RESET} ${DIM}(${activeCount} active${expiredNote})${RESET}`);
    log();
    whispers.forEach(w => log(formatWhisper(w)));
    if (expiredCount > 0) {
      log();
      log(`${DIM}Run ${CYAN}claude-whisper purge${DIM} to remove expired whispers.${RESET}`);
    }
    log();
    break;
  }

  case 'toggle': {
    const id = parseInt(rest[0], 10);
    if (isNaN(id)) {
      log(`${RED}Error:${RESET} Provide a whisper ID. Run ${CYAN}claude-whisper ls${RESET} to see IDs.`);
      process.exit(1);
    }
    const toggled = toggleWhisper(id);
    if (!toggled) {
      log(`${RED}Error:${RESET} Whisper #${id} not found.`);
      process.exit(1);
    }
    const state = toggled.active ? `${GREEN}ON${RESET}` : `${RED}OFF${RESET}`;
    log(`Whisper ${GRAY}#${id}${RESET} is now ${state}`);
    break;
  }

  case 'rm':
  case 'remove': {
    const id = parseInt(rest[0], 10);
    if (isNaN(id)) {
      log(`${RED}Error:${RESET} Provide a whisper ID. Run ${CYAN}claude-whisper ls${RESET} to see IDs.`);
      process.exit(1);
    }
    const removed = removeWhisper(id);
    if (!removed) {
      log(`${RED}Error:${RESET} Whisper #${id} not found.`);
      process.exit(1);
    }
    log(`${RED}Removed${RESET} whisper ${GRAY}#${id}${RESET}: ${removed.text}`);
    break;
  }

  case 'purge': {
    const removed = purgeExpired();
    if (removed === 0) {
      log(`${DIM}No expired whispers to remove.${RESET}`);
    } else {
      log(`${RED}Purged${RESET} ${removed} expired whisper${removed !== 1 ? 's' : ''}.`);
    }
    break;
  }

  case 'clear': {
    const whispers = getWhispers({ includeExpired: true });
    if (whispers.length === 0) {
      log(`${DIM}Nothing to clear.${RESET}`);
      break;
    }
    clearWhispers();
    log(`${RED}Cleared${RESET} ${whispers.length} whisper${whispers.length !== 1 ? 's' : ''}.`);
    break;
  }

  case 'uninstall': {
    uninstall();
    log(`${RED}Uninstalled.${RESET} Whisper hook removed from Claude Code settings.`);
    log(`${DIM}Your whispers are still in ~/.claude-whisper/ if you want them later.${RESET}`);
    break;
  }

  case 'status': {
    const installed = isInstalled();
    const whispers = getWhispers({ includeExpired: true });
    const active = whispers.filter(w => w.active !== false && !isExpired(w)).length;
    const expired = whispers.filter(w => isExpired(w)).length;
    log();
    log(`${BOLD}claude-whisper${RESET}`);
    log(`  Hook: ${installed ? `${GREEN}installed${RESET}` : `${RED}not installed${RESET}`}`);
    log(`  Whispers: ${whispers.length} total, ${active} active${expired > 0 ? `, ${expired} expired` : ''}`);
    log();
    break;
  }

  case 'version':
  case '--version':
  case '-v': {
    log(`claude-whisper v${VERSION}`);
    break;
  }

  case 'help':
  case '--help':
  case '-h':
  case undefined:
    showHelp();
    break;

  default:
    log(`${RED}Unknown command:${RESET} ${command}`);
    showHelp();
    process.exit(1);
}
