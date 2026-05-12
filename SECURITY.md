# Security Policy

## Supported Versions

| Version | Supported          |
|---------|--------------------|
| Latest  | :white_check_mark: |

We only support the latest release. Please update to the newest version before reporting issues.

## Reporting a Vulnerability

If you discover a security vulnerability in Permafrost Tools, **please do not open a public GitHub issue.**

### How to Report

1. **Email**: Send a detailed report to the repository maintainer via [GitHub Security Advisories](https://github.com/dead1786/permafrost-tools/security/advisories/new)
2. **Include**:
   - Description of the vulnerability
   - Steps to reproduce
   - Affected component(s) (claude-whisper, claude-i18n, self-guard, frost-scheduler, frost-collab, memory-gc, pitfall-tracker)
   - Potential impact assessment
   - Any suggested fix (optional)

### What to Expect

| Timeframe | Action |
|-----------|--------|
| 48 hours  | Acknowledgment of your report |
| 7 days    | Initial assessment and severity classification |
| 30 days   | Fix developed and tested (for confirmed vulnerabilities) |
| 45 days   | Public disclosure (coordinated with reporter) |

### Severity Classification

We use the following severity levels:

- **Critical**: Remote code execution, credential theft, arbitrary file write outside intended scope
- **High**: Privilege escalation, injection of unintended instructions into AI context, bypass of self-guard protections
- **Medium**: Information disclosure, denial of service, configuration tampering
- **Low**: Minor information leak, edge-case behavior

### Scope

The following are **in scope**:

- **claude-whisper**: Hook injection mechanism, whisper storage security, potential for unauthorized instruction injection
- **claude-i18n**: Patch mechanism integrity, potential for code injection via translation strings
- **self-guard**: Bypass of behavior detection patterns, false negative scenarios
- **frost-scheduler**: Task injection, unauthorized command execution via schedule manipulation, SendInput abuse
- **frost-collab**: Task board tampering, unauthorized task dispatch/claim, file locking vulnerabilities
- **memory-gc / pitfall-tracker**: Data integrity, unauthorized data modification

The following are **out of scope**:

- Vulnerabilities in Claude Code itself (report to [Anthropic](https://www.anthropic.com/responsible-disclosure))
- Issues requiring physical access to the machine
- Social engineering attacks
- Denial of service via resource exhaustion on the local machine (these tools run locally)

### Safe Harbor

We consider security research conducted in good faith to be authorized. We will not pursue legal action against researchers who:

- Make a good faith effort to avoid privacy violations, data destruction, and service disruption
- Only interact with accounts they own or with explicit permission
- Report vulnerabilities through the process described above
- Allow reasonable time for remediation before disclosure

## Security Considerations

### claude-whisper

- Whispers are stored in `~/.claude-whisper/whispers.json` as plain text. Treat this file with the same care as your `CLAUDE.md`.
- The hook runs with the same permissions as your Claude Code session.
- Anyone with write access to `~/.claude-whisper/` can inject instructions into your AI context.

### frost-scheduler

- The scheduler daemon runs with your user permissions.
- `SendInput` wake method (Windows) types keystrokes into a terminal window — ensure the target window is correct.
- Schedule files should be protected with appropriate file permissions.

### frost-collab

- The shared task board (`~/.frost-collab/`) is accessible to all processes running as your user.
- In multi-user environments, consider directory permissions carefully.

### claude-i18n

- The patch modifies Claude Code's `cli.js` directly. A backup is created automatically.
- Use `python patch.py --restore` to revert changes at any time.

## General Best Practices

1. Keep file permissions restrictive on configuration directories (`~/.claude-whisper/`, `~/.frost-scheduler/`, `~/.frost-collab/`)
2. Review whisper content periodically — stale whispers may conflict with current intentions
3. Do not store secrets or credentials in whispers, schedules, or task descriptions
4. Use `self-guard` to detect unexpected AI behavior patterns
