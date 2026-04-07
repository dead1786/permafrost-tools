# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

_Nothing yet._

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

[Unreleased]: https://github.com/dead1786/permafrost-tools/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/dead1786/permafrost-tools/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/dead1786/permafrost-tools/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/dead1786/permafrost-tools/releases/tag/v0.1.0
