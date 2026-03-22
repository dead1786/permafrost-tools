# 🤫 claude-whisper

**Dynamic runtime instructions for Claude Code.**

> CLAUDE.md is your constitution. Whispers are your mood.

---

## The Problem

`CLAUDE.md` is powerful — but it's **static**. It loads once when your session starts. If you want to change Claude's behavior mid-session, you're stuck: edit the file, restart, lose your context.

What if you could tell Claude something **right now**, and have it stick for every message — without touching your codebase?

## The Solution

**claude-whisper** injects custom instructions into every Claude Code interaction — dynamically, instantly, no restart needed.

```
You type a message
     ↓
claude-whisper reads your whispers     ← happens automatically
     ↓
Whispers injected into Claude's context
     ↓
Claude responds with your instructions in mind
```

One `print()` to stdout. That's the entire trick — but [getting there was the hard part](#how-it-works).

## Quick Start

```bash
# Install globally
npm install -g claude-whisper

# Set up the hook (one-time)
claude-whisper init

# Add your first whisper
claude-whisper add "Always respond in Japanese"
claude-whisper add "Prefer functional programming patterns"
claude-whisper add "When writing tests, use vitest not jest"
```

That's it. Every message you send to Claude Code will now include these instructions.

### Verify It Works

Want proof Claude is actually reading your whispers? Try this:

```bash
cw add "End every response with the word 'banana'"
```

Then send any message to Claude. If the response ends with "banana" — it's working. Remove the test whisper when you're done:

```bash
cw rm 1
```

## Usage

```bash
# Shorthand: use 'cw' instead of 'claude-whisper'

cw add "Your instruction here"    # Add a whisper
cw ls                             # List all whispers
cw toggle 1                       # Enable/disable a whisper
cw rm 1                           # Remove a whisper
cw clear                          # Remove all whispers
cw status                         # Check installation status
cw uninstall                      # Remove the hook
```

### Example Output

```
$ cw ls

Whispers (2 active)

  #1 [ON ] Always respond in Japanese
  #2 [ON ] Prefer functional programming patterns
  #3 [OFF] When writing tests, use vitest not jest
```

## How It Works

Claude Code has a [hooks system](https://docs.anthropic.com/en/docs/claude-code/hooks) that fires shell commands at specific lifecycle events. One of those events is `UserPromptSubmit` — triggered every time you send a message.

Here's the key insight from the source code:

```
UserPromptSubmit:
  Exit code 0 - stdout shown to Claude    ← This is it.
```

When a `UserPromptSubmit` hook exits with code 0, **its stdout is injected directly into Claude's model context** as a system message. Not displayed to the user — sent to the model.

claude-whisper registers a lightweight hook that:
1. Reads your whispers from `~/.claude-whisper/whispers.json`
2. Prints them to stdout
3. Exits with code 0

Claude Code does the rest. No monkey-patching, no proxy, no hacks.

## Use Cases

**Persona & Style**
```bash
cw add "Be extremely concise. No filler words."
cw add "Always explain your reasoning step by step"
cw add "Respond as a senior Go developer would"
```

**Project Conventions**
```bash
cw add "Use pnpm, not npm"
cw add "All new components should use Tailwind CSS"
cw add "Database migrations must be backwards-compatible"
```

**Temporary Context**
```bash
cw add "I'm working on the auth module today - prioritize security"
cw add "The CI is broken, don't suggest pushing until I say it's fixed"
# Later:
cw clear
```

**Language**
```bash
cw add "Always respond in Traditional Chinese (繁體中文)"
```

## FAQ

**Does this work mid-session?**
Yes! That's the whole point. Whispers are read fresh on every message. Add, remove, or toggle them anytime.

**Does this affect performance?**
The hook runs in <50ms. It reads a JSON file and prints text. You won't notice it.

**Where are whispers stored?**
`~/.claude-whisper/whispers.json` — plain JSON, easy to back up or share.

**Does this work with Claude Code teams/shared sessions?**
Whispers are per-machine (stored in your home directory). Each team member can have their own whispers.

**Can I use this with other hooks?**
Absolutely. claude-whisper adds its own `UserPromptSubmit` entry without touching your existing hooks.

## Uninstall

```bash
claude-whisper uninstall    # Removes the hook from settings
rm -rf ~/.claude-whisper    # Removes stored whispers
npm uninstall -g claude-whisper
```

## Requirements

- **Claude Code** ([@anthropic-ai/claude-code](https://www.npmjs.com/package/@anthropic-ai/claude-code)) v1.0+
- **Node.js** 18+

## License

MIT

---

<p align="center">
  <i>Built by discovering an undocumented behavior in Claude Code's hook system.</i><br>
  <i>One <code>print()</code> was all it took.</i>
</p>
