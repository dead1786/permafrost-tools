#!/usr/bin/env python3
"""
pitfall-tracker.py - Learn from mistakes, evolve automatically.

A complete "learn from mistakes" pipeline:
  1. Record pitfalls (what happened, root cause, prevention rule)
  2. Track recurrence and auto-escalate
  3. Generate evolution/improvement items from recurring patterns
  4. Track resolution of those improvements

Escalation logic:
  - 3+ occurrences  -> tagged [RECURRING]
  - 5+ occurrences  -> tagged [ESCALATED], suggested for CLAUDE.md
  - Still recurring  -> flagged [NEEDS HUMAN REVIEW]

Usage:
  python pitfall-tracker.py add --what "..." --cause "..." --prevention "..."
  python pitfall-tracker.py add --what "..." --cause "..." --prevention "..." --category "Build"
  python pitfall-tracker.py scan
  python pitfall-tracker.py scan --threshold 2
  python pitfall-tracker.py list
  python pitfall-tracker.py list --category "Build"
  python pitfall-tracker.py evolve
  python pitfall-tracker.py done --id evo-001
  python pitfall-tracker.py stats

Global options:
  --pitfalls PATH   Path to pitfalls markdown file (default: ~/.claude/pitfalls.md)
  --queue PATH      Path to evolution queue JSON file (default: ~/.claude/evolution-queue.json)
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_PITFALLS_PATH = os.path.join(os.path.expanduser("~"), ".claude", "pitfalls.md")
DEFAULT_QUEUE_PATH = os.path.join(os.path.expanduser("~"), ".claude", "evolution-queue.json")

RECURRING_THRESHOLD = 3   # occurrences before tagging [RECURRING]
ESCALATED_THRESHOLD = 5   # occurrences before tagging [ESCALATED]

STATUS_VALUES = ("queued", "in_progress", "done", "blocked")


# ---------------------------------------------------------------------------
# File I/O helpers
# ---------------------------------------------------------------------------

def ensure_parent_dir(path: str) -> None:
    """Create parent directories if they don't exist."""
    parent = os.path.dirname(path)
    if parent and not os.path.exists(parent):
        os.makedirs(parent, exist_ok=True)


def read_file(path: str) -> str:
    """Read a UTF-8 file, return empty string if missing."""
    if not os.path.exists(path):
        return ""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def write_file(path: str, content: str) -> None:
    """Write content to a UTF-8 file, creating parent dirs as needed."""
    ensure_parent_dir(path)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)


def load_json(path: str) -> Dict[str, Any]:
    """Load a JSON file, return default structure if missing."""
    if not os.path.exists(path):
        return {"items": []}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: str, data: Dict[str, Any]) -> None:
    """Save data to a JSON file with pretty formatting."""
    ensure_parent_dir(path)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


# ---------------------------------------------------------------------------
# Pitfall parsing
# ---------------------------------------------------------------------------

def parse_pitfalls(content: str) -> List[Dict[str, Any]]:
    """
    Parse a pitfalls markdown file into structured records.

    Expected format:
        ## Category Name

        ### [RECURRING] Pattern Name (2025-01-15)
        - **What happened**: Description
        - **Root cause**: Why it happened
        - **Prevention**: Rule to prevent it
        - **Occurrences**: 3

    Returns a list of pitfall dicts with keys:
        category, title, clean_title, tags, what, cause, prevention,
        occurrences, date, raw_body
    """
    pitfalls = []
    current_category = "Uncategorized"

    # Split on ### headers (pitfall entries)
    # But first, track ## headers (categories)
    lines = content.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]

        # Category header (## but not ###)
        if line.startswith("## ") and not line.startswith("### "):
            current_category = line[3:].strip()
            i += 1
            continue

        # Pitfall header (###)
        if line.startswith("### "):
            header = line[4:].strip()

            # Extract tags like [RECURRING], [ESCALATED], [NEEDS HUMAN REVIEW]
            tags = re.findall(r"\[(RECURRING|ESCALATED|NEEDS HUMAN REVIEW)\]", header)
            clean_title = re.sub(r"\[(?:RECURRING|ESCALATED|NEEDS HUMAN REVIEW)\]\s*", "", header).strip()

            # Extract date from title if present, e.g., "Pattern Name (2025-01-15)"
            date_match = re.search(r"\((\d{4}-\d{2}-\d{2})\)", clean_title)
            date = date_match.group(1) if date_match else None
            if date_match:
                clean_title = clean_title[:date_match.start()].strip()

            # Collect body lines until next header
            body_lines = []
            i += 1
            while i < len(lines) and not lines[i].startswith("## ") and not lines[i].startswith("### "):
                body_lines.append(lines[i])
                i += 1

            body = "\n".join(body_lines).strip()

            # Extract structured fields from body
            what = _extract_field(body, "What happened")
            cause = _extract_field(body, "Root cause")
            prevention = _extract_field(body, "Prevention")
            occurrences = _extract_occurrences(body)

            pitfalls.append({
                "category": current_category,
                "title": header,
                "clean_title": clean_title,
                "tags": tags,
                "what": what,
                "cause": cause,
                "prevention": prevention,
                "occurrences": occurrences,
                "date": date,
                "raw_body": body,
            })
            continue

        i += 1

    return pitfalls


def _extract_field(body: str, field_name: str) -> str:
    """Extract a **Field name**: value from the body text."""
    pattern = rf"\*\*{re.escape(field_name)}\*\*:\s*(.+)"
    match = re.search(pattern, body, re.IGNORECASE)
    return match.group(1).strip() if match else ""


def _extract_occurrences(body: str) -> int:
    """Extract occurrence count from body, default 1."""
    match = re.search(r"\*\*Occurrences\*\*:\s*(\d+)", body, re.IGNORECASE)
    return int(match.group(1)) if match else 1


# ---------------------------------------------------------------------------
# Pitfall serialization (writing back to markdown)
# ---------------------------------------------------------------------------

def serialize_pitfalls(pitfalls: List[Dict[str, Any]]) -> str:
    """Convert structured pitfall records back to markdown."""
    output_lines = ["# Pitfall Log\n"]

    # Group by category
    categories: Dict[str, List[Dict[str, Any]]] = {}
    for p in pitfalls:
        cat = p["category"]
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(p)

    for category, items in categories.items():
        output_lines.append(f"## {category}\n")

        for p in items:
            # Build header with tags and date
            tag_prefix = ""
            for tag in p.get("tags", []):
                tag_prefix += f"[{tag}] "

            date_suffix = f" ({p['date']})" if p.get("date") else ""
            output_lines.append(f"### {tag_prefix}{p['clean_title']}{date_suffix}")

            output_lines.append(f"- **What happened**: {p['what']}")
            output_lines.append(f"- **Root cause**: {p['cause']}")
            output_lines.append(f"- **Prevention**: {p['prevention']}")
            output_lines.append(f"- **Occurrences**: {p['occurrences']}")
            output_lines.append("")

    return "\n".join(output_lines)


# ---------------------------------------------------------------------------
# Similarity matching for deduplication
# ---------------------------------------------------------------------------

def normalize_text(text: str) -> str:
    """Lowercase and strip punctuation for fuzzy matching."""
    return re.sub(r"[^\w\s]", "", text.lower()).strip()


def titles_match(title_a: str, title_b: str) -> bool:
    """Check if two pitfall titles refer to the same pattern."""
    a = normalize_text(title_a)
    b = normalize_text(title_b)
    if not a or not b:
        return False
    # Exact match after normalization
    if a == b:
        return True
    # One contains the other (handles slight wording differences)
    if a in b or b in a:
        return True
    # Word overlap ratio > 0.6
    words_a = set(a.split())
    words_b = set(b.split())
    if not words_a or not words_b:
        return False
    overlap = len(words_a & words_b)
    ratio = overlap / min(len(words_a), len(words_b))
    return ratio > 0.6


def pitfall_has_evolution(pitfall_title: str, evo_items: List[Dict[str, Any]]) -> bool:
    """Check if a pitfall already has a corresponding evolution item."""
    norm_title = normalize_text(pitfall_title)
    for item in evo_items:
        item_text = normalize_text(
            item.get("title", "") + " " + item.get("why", "")
        )
        # Check if the pitfall title (or a significant chunk) appears in the evo item
        if norm_title and norm_title in item_text:
            return True
        # Check word overlap
        title_words = set(norm_title.split())
        item_words = set(item_text.split())
        if title_words and item_words:
            overlap = len(title_words & item_words)
            if overlap >= max(2, len(title_words) * 0.5):
                return True
    return False


# ---------------------------------------------------------------------------
# Command: add
# ---------------------------------------------------------------------------

def cmd_add(args: argparse.Namespace) -> None:
    """Record a new pitfall or increment occurrences of an existing one."""
    content = read_file(args.pitfalls)
    pitfalls = parse_pitfalls(content) if content.strip() else []

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    category = args.category or "General"

    # Check for existing pitfall with similar title/description
    existing = None
    for p in pitfalls:
        # Match by prevention rule or by what-happened description
        if (titles_match(p["what"], args.what) or
                titles_match(p["prevention"], args.prevention)):
            existing = p
            break

    if existing:
        # Increment occurrences on existing entry
        existing["occurrences"] += 1
        existing["date"] = today  # update to latest occurrence

        # Apply escalation logic
        existing["tags"] = _compute_tags(existing["occurrences"], args.threshold)

        print(f"Updated existing pitfall: {existing['clean_title']}")
        print(f"  Occurrences: {existing['occurrences']}")
        if "ESCALATED" in existing["tags"]:
            print("  [!] ESCALATED - Consider adding prevention rule to your CLAUDE.md")
        elif "RECURRING" in existing["tags"]:
            print(f"  [!] RECURRING - This has happened {existing['occurrences']} times")
    else:
        # Create new pitfall entry
        new_pitfall = {
            "category": category,
            "title": f"{args.what[:60]} ({today})",
            "clean_title": args.what[:60],
            "tags": [],
            "what": args.what,
            "cause": args.cause,
            "prevention": args.prevention,
            "occurrences": 1,
            "date": today,
            "raw_body": "",
        }
        pitfalls.append(new_pitfall)
        print(f"Recorded new pitfall: {new_pitfall['clean_title']}")
        print(f"  Category: {category}")

    # Write back
    write_file(args.pitfalls, serialize_pitfalls(pitfalls))
    print(f"  Saved to: {args.pitfalls}")


def _compute_tags(occurrences: int, threshold: int) -> List[str]:
    """Compute escalation tags based on occurrence count."""
    tags = []
    escalated_threshold = threshold + 2  # default: recurring=3, escalated=5

    if occurrences >= escalated_threshold:
        tags.append("ESCALATED")
        # Check if still recurring even after escalation (needs human review)
        if occurrences >= escalated_threshold + 3:
            tags.append("NEEDS HUMAN REVIEW")
    elif occurrences >= threshold:
        tags.append("RECURRING")

    return tags


# ---------------------------------------------------------------------------
# Command: scan
# ---------------------------------------------------------------------------

def cmd_scan(args: argparse.Namespace) -> None:
    """Scan pitfalls and generate evolution items for unaddressed recurring patterns."""
    content = read_file(args.pitfalls)
    if not content.strip():
        print("No pitfalls file found or file is empty.")
        print(f"  Expected at: {args.pitfalls}")
        print("  Use 'add' command to record your first pitfall.")
        return

    pitfalls = parse_pitfalls(content)
    evo_data = load_json(args.queue)
    evo_items = evo_data.get("items", [])

    # Find the next available evolution ID
    max_id = 0
    for item in evo_items:
        match = re.match(r"evo-(\d+)", item.get("id", ""))
        if match:
            max_id = max(max_id, int(match.group(1)))

    threshold = args.threshold
    new_items = []

    for pitfall in pitfalls:
        # Only generate evolution items for recurring patterns
        if pitfall["occurrences"] < threshold:
            continue

        # Skip if already has an evolution item
        if pitfall_has_evolution(pitfall["clean_title"], evo_items + new_items):
            continue

        max_id += 1
        evo_id = f"evo-{max_id:03d}"

        priority = 0 if "ESCALATED" in pitfall.get("tags", []) else 1
        if "NEEDS HUMAN REVIEW" in pitfall.get("tags", []):
            priority = 0  # highest priority

        new_item = {
            "id": evo_id,
            "title": f"Auto-block: {pitfall['clean_title'][:50]}",
            "source": "pitfall-scan",
            "why": (
                f"Recurring pattern ({pitfall['occurrences']}x): "
                f"{pitfall['what'][:120]}"
            ),
            "expected": (
                f"Automated prevention: {pitfall['prevention'][:150]}"
            ),
            "status": "queued",
            "priority": priority,
            "created": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "completed": None,
        }
        new_items.append(new_item)

    if not new_items:
        print("All recurring pitfalls already have corresponding evolution items.")
        return

    if args.dry_run:
        print(f"[DRY RUN] Would create {len(new_items)} evolution item(s):")
        for item in new_items:
            print(f"  {item['id']}: {item['title']} (priority={item['priority']})")
        return

    # Append new items and save
    evo_items.extend(new_items)
    evo_data["items"] = evo_items
    evo_data["last_updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    save_json(args.queue, evo_data)

    print(f"Created {len(new_items)} evolution item(s):")
    for item in new_items:
        print(f"  {item['id']}: {item['title']} (priority={item['priority']})")
    print(f"  Saved to: {args.queue}")


# ---------------------------------------------------------------------------
# Command: list
# ---------------------------------------------------------------------------

def cmd_list(args: argparse.Namespace) -> None:
    """List all pitfalls with frequency counts."""
    content = read_file(args.pitfalls)
    if not content.strip():
        print("No pitfalls recorded yet.")
        return

    pitfalls = parse_pitfalls(content)

    # Optional category filter
    if args.category:
        pitfalls = [p for p in pitfalls if p["category"].lower() == args.category.lower()]

    if not pitfalls:
        print("No pitfalls found matching the filter.")
        return

    # Sort by occurrences descending, then by date
    pitfalls.sort(key=lambda p: (-p["occurrences"], p.get("date") or ""))

    current_category = None
    for p in pitfalls:
        if p["category"] != current_category:
            current_category = p["category"]
            print(f"\n{'='*60}")
            print(f"  {current_category}")
            print(f"{'='*60}")

        tags_str = " ".join(f"[{t}]" for t in p["tags"]) if p["tags"] else ""
        date_str = p["date"] or "unknown"
        print(f"\n  {p['clean_title']}")
        print(f"    Occurrences: {p['occurrences']}  {tags_str}")
        print(f"    Last seen:   {date_str}")
        print(f"    Prevention:  {p['prevention'][:80]}")

    total = len(pitfalls)
    recurring = sum(1 for p in pitfalls if "RECURRING" in p.get("tags", []))
    escalated = sum(1 for p in pitfalls if "ESCALATED" in p.get("tags", []))

    print(f"\n{'='*60}")
    print(f"  Total: {total}  |  Recurring: {recurring}  |  Escalated: {escalated}")
    print(f"{'='*60}")


# ---------------------------------------------------------------------------
# Command: evolve
# ---------------------------------------------------------------------------

def cmd_evolve(args: argparse.Namespace) -> None:
    """Show pending evolution items generated from pitfalls."""
    evo_data = load_json(args.queue)
    items = evo_data.get("items", [])

    if not items:
        print("No evolution items found.")
        print(f"  Run 'scan' to generate items from pitfalls.")
        return

    # Filter by status
    status_filter = args.status
    if status_filter:
        items = [i for i in items if i.get("status") == status_filter]
    else:
        # Default: show non-done items
        items = [i for i in items if i.get("status") != "done"]

    if not items:
        filter_msg = f" with status '{status_filter}'" if status_filter else " (pending)"
        print(f"No evolution items{filter_msg}.")
        return

    # Sort by priority (lower = higher priority), then by creation date
    items.sort(key=lambda i: (i.get("priority", 5), i.get("created", "")))

    print(f"{'ID':<10} {'P':>1} {'Status':<12} {'Title'}")
    print("-" * 70)

    for item in items:
        status = item.get("status", "queued")
        priority = item.get("priority", 5)
        title = item.get("title", "Untitled")[:48]

        # Status indicator
        status_icon = {
            "queued": "[ ]",
            "in_progress": "[~]",
            "blocked": "[!]",
            "done": "[x]",
        }.get(status, "[ ]")

        print(f"{item['id']:<10} {priority:>1} {status_icon} {status:<8} {title}")

    print(f"\nTotal: {len(items)} item(s)")


# ---------------------------------------------------------------------------
# Command: done
# ---------------------------------------------------------------------------

def cmd_done(args: argparse.Namespace) -> None:
    """Mark an evolution item as completed."""
    evo_data = load_json(args.queue)
    items = evo_data.get("items", [])

    target_id = args.id
    found = False

    for item in items:
        if item.get("id") == target_id:
            if item.get("status") == "done":
                print(f"Item {target_id} is already marked as done.")
                return

            item["status"] = "done"
            item["completed"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            found = True
            print(f"Marked {target_id} as done: {item.get('title', '')}")
            break

    if not found:
        print(f"Evolution item '{target_id}' not found.")
        print("  Use 'evolve' to see available items.")
        return

    evo_data["items"] = items
    evo_data["last_updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    save_json(args.queue, evo_data)
    print(f"  Saved to: {args.queue}")


# ---------------------------------------------------------------------------
# Command: stats
# ---------------------------------------------------------------------------

def cmd_stats(args: argparse.Namespace) -> None:
    """Show pitfall statistics: recurring patterns, resolution rate, etc."""
    content = read_file(args.pitfalls)
    pitfalls = parse_pitfalls(content) if content.strip() else []

    evo_data = load_json(args.queue)
    evo_items = evo_data.get("items", [])

    # Pitfall stats
    total_pitfalls = len(pitfalls)
    total_occurrences = sum(p["occurrences"] for p in pitfalls)
    recurring = [p for p in pitfalls if "RECURRING" in p.get("tags", [])]
    escalated = [p for p in pitfalls if "ESCALATED" in p.get("tags", [])]
    needs_review = [p for p in pitfalls if "NEEDS HUMAN REVIEW" in p.get("tags", [])]

    # Category breakdown
    categories: Dict[str, int] = {}
    for p in pitfalls:
        cat = p["category"]
        categories[cat] = categories.get(cat, 0) + 1

    # Evolution stats
    total_evo = len(evo_items)
    done_evo = sum(1 for i in evo_items if i.get("status") == "done")
    queued_evo = sum(1 for i in evo_items if i.get("status") == "queued")
    in_progress_evo = sum(1 for i in evo_items if i.get("status") == "in_progress")
    blocked_evo = sum(1 for i in evo_items if i.get("status") == "blocked")

    resolution_rate = (done_evo / total_evo * 100) if total_evo > 0 else 0

    # Coverage: how many recurring pitfalls have evolution items
    covered = sum(1 for p in recurring + escalated
                  if pitfall_has_evolution(p["clean_title"], evo_items))
    coverage_count = len(recurring) + len(escalated)
    coverage_rate = (covered / coverage_count * 100) if coverage_count > 0 else 100

    print("=" * 50)
    print("  PITFALL STATISTICS")
    print("=" * 50)

    print(f"\n  Pitfalls")
    print(f"    Total patterns:     {total_pitfalls}")
    print(f"    Total occurrences:  {total_occurrences}")
    print(f"    Recurring:          {len(recurring)}")
    print(f"    Escalated:          {len(escalated)}")
    print(f"    Needs human review: {len(needs_review)}")

    if categories:
        print(f"\n  Categories")
        for cat, count in sorted(categories.items(), key=lambda x: -x[1]):
            print(f"    {cat}: {count}")

    print(f"\n  Evolution Pipeline")
    print(f"    Total items:        {total_evo}")
    print(f"    Queued:             {queued_evo}")
    print(f"    In progress:        {in_progress_evo}")
    print(f"    Blocked:            {blocked_evo}")
    print(f"    Done:               {done_evo}")
    print(f"    Resolution rate:    {resolution_rate:.0f}%")
    print(f"    Pitfall coverage:   {coverage_rate:.0f}%")

    # Top recurring patterns
    if pitfalls:
        top = sorted(pitfalls, key=lambda p: -p["occurrences"])[:5]
        print(f"\n  Top Recurring Patterns")
        for p in top:
            tags = " ".join(f"[{t}]" for t in p["tags"]) if p["tags"] else ""
            print(f"    {p['occurrences']:>3}x  {p['clean_title'][:40]}  {tags}")

    # Actionable suggestions
    suggestions = []
    if escalated:
        suggestions.append(
            f"  -> {len(escalated)} escalated pattern(s) should be added to CLAUDE.md"
        )
    if needs_review:
        suggestions.append(
            f"  -> {len(needs_review)} pattern(s) need human review (still recurring after escalation)"
        )
    uncovered = coverage_count - covered
    if uncovered > 0:
        suggestions.append(
            f"  -> {uncovered} recurring pattern(s) lack evolution items (run 'scan')"
        )

    if suggestions:
        print(f"\n  Action Items")
        for s in suggestions:
            print(s)

    print(f"\n{'=' * 50}")


# ---------------------------------------------------------------------------
# CLI argument parsing
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser with all subcommands."""
    parser = argparse.ArgumentParser(
        prog="pitfall-tracker",
        description="Learn from mistakes. Track pitfalls, generate evolution items, measure improvement.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  %(prog)s add --what 'Deployed without tests' --cause 'Rushed deadline' "
            "--prevention 'Always run test suite before deploy'\n"
            "  %(prog)s scan\n"
            "  %(prog)s list\n"
            "  %(prog)s evolve\n"
            "  %(prog)s done --id evo-001\n"
            "  %(prog)s stats\n"
        ),
    )

    # Global options
    parser.add_argument(
        "--pitfalls",
        default=DEFAULT_PITFALLS_PATH,
        help=f"Path to pitfalls markdown file (default: {DEFAULT_PITFALLS_PATH})",
    )
    parser.add_argument(
        "--queue",
        default=DEFAULT_QUEUE_PATH,
        help=f"Path to evolution queue JSON file (default: {DEFAULT_QUEUE_PATH})",
    )
    parser.add_argument(
        "--threshold",
        type=int,
        default=RECURRING_THRESHOLD,
        help=f"Occurrences before marking as recurring (default: {RECURRING_THRESHOLD})",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # --- add ---
    add_parser = subparsers.add_parser("add", help="Record a new pitfall")
    add_parser.add_argument("--what", required=True, help="What happened")
    add_parser.add_argument("--cause", required=True, help="Root cause")
    add_parser.add_argument("--prevention", required=True, help="Prevention rule")
    add_parser.add_argument("--category", default=None, help="Category name (default: General)")

    # --- scan ---
    scan_parser = subparsers.add_parser("scan", help="Scan pitfalls and generate evolution items")
    scan_parser.add_argument("--dry-run", action="store_true", dest="dry_run",
                             help="Preview without writing")

    # --- list ---
    list_parser = subparsers.add_parser("list", help="List all pitfalls with frequency counts")
    list_parser.add_argument("--category", default=None, help="Filter by category")

    # --- evolve ---
    evolve_parser = subparsers.add_parser("evolve", help="Show pending evolution items")
    evolve_parser.add_argument("--status", choices=STATUS_VALUES, default=None,
                               help="Filter by status (default: show non-done)")

    # --- done ---
    done_parser = subparsers.add_parser("done", help="Mark an evolution item as completed")
    done_parser.add_argument("--id", required=True, help="Evolution item ID (e.g., evo-001)")

    # --- stats ---
    subparsers.add_parser("stats", help="Show pitfall statistics")

    return parser


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Propagate threshold to add command (used for tag computation)
    if not hasattr(args, "threshold") or args.threshold is None:
        args.threshold = RECURRING_THRESHOLD

    # Dispatch to subcommand
    commands = {
        "add": cmd_add,
        "scan": cmd_scan,
        "list": cmd_list,
        "evolve": cmd_evolve,
        "done": cmd_done,
        "stats": cmd_stats,
    }

    handler = commands.get(args.command)
    if handler:
        handler(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
