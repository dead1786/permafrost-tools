# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added
- **self-guard**: `hooks/install.py` — one-click installer that copies `self-guard.py` + config into `~/.claude/hooks/` and registers it in `settings.json`. Appends a new matcher-group entry to `hooks.Stop` instead of overwriting the array, so any Stop hooks you already have (yours or another tool's) are preserved. Refuses to touch `settings.json` if it can't be parsed, rather than risk clobbering it. `--status` / `--uninstall` included.
- **ci**: Add GitHub Actions workflow (`.github/workflows/ci.yml`) — Python syntax + ruff lint, Node.js syntax checks, cross-platform (Ubuntu/Windows/macOS) CLI smoke tests for claude-whisper, self-guard, and the new installer, plus the hidden zero-width character scan below. *(Committed locally; not yet pushed — see repo note about the PAT `workflow` scope.)*
- **claude-i18n**: `--scan` now supports the winget `claude.exe` binary (`patch.py --scan --winget`, or auto-detected when only a winget install is present). Previously `--scan` only understood the npm `cli.js` and hard-errored (`找不到 cli.js`) on winget-only machines — the exact setup used by the majority of Windows users this tool targets — leaving them with no way to detect newly-added commands after a `winget upgrade` short of a manual diff. The winget scan decodes the packed binary leniently (`errors="ignore"`) and judges translation status by description only, since command *names* are intentionally left in English in binary builds (byte-length constraint — see `binary_names` note in `translations.json`), unlike the npm scan which requires both name and description to be Chinese.

### Fixed
- **self-guard**: README's manual-install JSON example was missing the nested `"hooks": [...]` array that Claude Code's real settings.json schema requires for every hook event (confirmed against current Claude Code hook documentation and a live `hooks.Stop` config) — `"Stop": [{"type": "command", ...}]` is not a valid entry shape; it needs to be `"Stop": [{"hooks": [{"type": "command", ...}]}]`. Following the old snippet literally could silently fail to register the hook, or clobber an existing `hooks.Stop` array if the user pasted it in as a full replacement. The installer above always emits the correct shape.

### Security
- **repo**: Remove hidden zero-width Unicode characters (U+200B/U+200C/U+200D) found embedded in comments/headers of `claude-whisper/hook/whisper-hook.mjs`, `claude-whisper/README.md`, `claude-i18n/patch.py`, and `claude-i18n/README.md`. These are invisible in normal viewers and are a known steganography / prompt-injection smuggling technique — unacceptable in a repo whose tools inject content directly into an LLM's context.

### Changed
- **claude-i18n**: Bump verified version to 2.1.219 — ran the new `--scan --winget` against a live winget install on that release and confirmed 100% description coverage (110/110), so the existing translation table still applies cleanly; no translation content changed.
- **claude-whisper**: Re-verified compatible with Claude Code 2.1.219 — the hook only depends on the `UserPromptSubmit` event firing and stdout being captured on exit 0 (it doesn't read or depend on any stdin field), so it isn't affected by hook-input-schema changes between releases.

## [0.3.2] - 2026-06-24

### Fixed
- **claude-whisper**: Add trailing newline to hook stdout so whispers are cleanly separated from user prompt on injection
- **claude-whisper**: Trim whitespace from whisper text in `addWhisper`; reject empty or whitespace-only whispers in both `addWhisper` and `isValidWhisper`
- **claude-whisper**: Correct `hookTimeout` in `package.json` from `2000` to `2` (unit is seconds, matching Claude Code hook config)

### Changed
- **claude-i18n**: Bump verified version to 2.1.178 — translations confirmed working on current Claude Code release
- **repo**: Remove stale RELEASE_NOTES_DRAFT.md (internal draft file not intended for publication)

## [0.3.1] - 2026-04-08

### Changed
- **claude-i18n**: Bump verified version to 2.1.91 — all 461 translations confirmed working
- **claude-i18n**: Add 4 missing command descriptions: `/autocompact`, `/toggle-memory`, `/powerup`, `/buddy`

## [0.3.0] - 2026-04-01

### Added
- **claude-i18n**: Full Claude Code localization tool — commands, UI strings, spinners, prompts, errors, and labels
- **claude-i18n**: Winget (native binary) support with byte-length-aware translation
- **claude-i18n**: 312 translation entries with 307 binary-verified for winget compatibility
- **claude-i18n**: `--scan` flag to detect untranslated commands after Claude Code updates
- **claude-i18n**: `--restore` one-click backup restoration
- **claude-i18n**: `--dry-run` preview mode
- **claude-i18n**: Update notification when Claude Code version changes
- **self-guard**: Migrated from non-existent `PreResponse` hook to `Stop` hook
- **self-guard**: Config-driven pattern detection (replacing hardcoded patterns)
- **self-guard**: Chinese language pattern support across all 4 detection modes

### Fixed
- **claude-i18n**: UTF-8 encoding for accented characters in translations
- **claude-i18n**: Byte-overflow translations for winget binary (20 entries fixed)
- **claude-i18n**: Removed effort statusline translations that caused "max精力" display bug
- **claude-i18n**: Split npm/winget behavior for correct name translation handling
- **claude-whisper**: Validate hook source exists before install

## [0.2.0] - 2026-03-23

### Added
- **frost-collab**: Multi-AI collaboration tool — dispatch, claim, progress, complete workflow
- **frost-collab**: Priority queue, dependency tracking, file-level locking, stale lock recovery
- **frost-scheduler**: Session-aware task scheduler daemon
- **frost-scheduler**: SendInput wake method (Windows) for context-preserving task injection
- **frost-scheduler**: Ack (acknowledgment) system for task completion tracking
- **frost-scheduler**: Pending queue — missed tasks are queued, never lost
- **frost-scheduler**: Night mode with configurable quiet hours
- **frost-scheduler**: Hot-reload — edit schedule.json, changes apply in 30 seconds
- **frost-scheduler**: One-click install with optional auto-start on boot
- **self-guard**: Upgraded to v3.2 with improved detection patterns

## [0.1.0] - 2026-03-22

### Added
- **claude-whisper**: Dynamic runtime instructions for Claude Code via `UserPromptSubmit` hook
- **claude-whisper**: CLI with `add`, `ls`, `toggle`, `rm`, `clear`, `status`, `uninstall` commands
- **claude-whisper**: `cw` shorthand alias
- **claude-whisper**: Global npm install support
- **self-guard**: AI behavior detection hook — sycophancy, ask-instead-of-do, acknowledge-without-action, passive waiting
- **memory-gc**: Memory lifecycle manager with TTL, garbage collection, deduplication, contradiction detection, promotion
- **pitfall-tracker**: AI mistake tracker with recurring pattern detection, 3-strike flagging, 5-strike escalation
- Initial project structure with MIT license

[Unreleased]: https://github.com/dead1786/permafrost-tools/compare/v0.3.2...HEAD
[0.3.2]: https://github.com/dead1786/permafrost-tools/compare/v0.3.1...v0.3.2
[0.3.1]: https://github.com/dead1786/permafrost-tools/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/dead1786/permafrost-tools/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/dead1786/permafrost-tools/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/dead1786/permafrost-tools/releases/tag/v0.1.0
