#!/usr/bin/env python3
"""
memory-gc.py — Memory Lifecycle Manager for Permafrost Tools

A complete memory lifecycle management system for AI agents. Provides
structured storage, automatic expiry (GC), deduplication, contradiction
detection, promotion of frequently-accessed memories, and keyword search.

Memory Types:
    context     — Temporary context (default TTL: 14 days)
    preference  — User/system preferences (default TTL: 30 days)
    progress    — Project/task progress (default TTL: 7 days)
    insight     — Learned insights and patterns (default TTL: 21 days)

Memory Status Lifecycle:
    active → expired (via GC) or promoted (via promote command)

Usage:
    python memory-gc.py add --type context --key "api_pattern" --value "Uses REST not GraphQL" --importance 3
    python memory-gc.py gc
    python memory-gc.py validate
    python memory-gc.py promote --key "api_pattern"
    python memory-gc.py search --query "API"
    python memory-gc.py stats
    python memory-gc.py list [--type context] [--status active]

Global Options:
    --index PATH    Path to memory index file (default: ~/.claude/memory-index.json)
    --config PATH   Path to config file (default: ~/.claude/memory-gc-config.json)

Requirements:
    Python 3.8+, no external dependencies.

License: MIT
"""

import json
import os
import re
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def _utcnow() -> datetime:
    """Return current UTC time as a timezone-naive datetime.

    Uses timezone-aware API internally to avoid the Python 3.12+
    deprecation warning on _utcnow().
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ═══════════════════════════════════════════════════════════════════════════
# Section 1: Constants & Defaults
# ═══════════════════════════════════════════════════════════════════════════

VERSION = "1.0.0"

DEFAULT_INDEX_PATH = os.path.join(
    os.path.expanduser("~"), ".claude", "memory-index.json"
)

VALID_TYPES = {"context", "preference", "progress", "insight"}

DEFAULT_TTL = {
    "context": 14,
    "preference": 30,
    "progress": 7,
    "insight": 21,
}

# Importance multipliers for TTL calculation.
# Higher importance memories live longer.
IMPORTANCE_TTL_MULTIPLIER = {
    1: 0.5,   # Low importance: TTL halved
    2: 0.8,
    3: 1.0,   # Default
    4: 1.5,
    5: 2.0,   # Critical: TTL doubled
}

# Each access extends TTL by this many days (capped at ACCESS_TTL_MAX_DAYS)
ACCESS_TTL_BONUS_DAYS = 7
ACCESS_TTL_MAX_DAYS = 90

# Memories accessed >= this many times are candidates for promotion
DEFAULT_PROMOTE_THRESHOLD = 3

# Jaccard similarity threshold for deduplication
SIMILARITY_THRESHOLD = 0.55

# Maximum number of active memories before overflow eviction
MAX_ACTIVE_MEMORIES = 200

# Similarity range for contradiction detection (related but not duplicate)
CONTRADICTION_SIM_LOW = 0.35
CONTRADICTION_SIM_HIGH = SIMILARITY_THRESHOLD

# Patterns that may indicate injection or credential leaks
INJECTION_PATTERNS = [
    (r"<[a-z_-]+>", "possible XML/HTML tag injection"),
    (r"ignore\s+(previous|above|all)", "ignore-previous prompt injection"),
    (r"system\s*prompt", "system prompt reference"),
    (r"[A-Za-z0-9+/]{40,}={0,2}", "possible base64 blob"),
    (r"(api[_-]?key|token|password|secret)\s*[:=]\s*\S+", "possible credential"),
    (r"(?:sk|pk|rk)-[a-zA-Z0-9]{20,}", "possible API key pattern"),
]


# ═══════════════════════════════════════════════════════════════════════════
# Section 2: Configuration
# ═══════════════════════════════════════════════════════════════════════════

def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """Load configuration from a JSON file, falling back to defaults.

    Config file format:
    {
        "ttl": {"context": 14, "preference": 30, "progress": 7, "insight": 21},
        "promote_threshold": 3,
        "max_active_memories": 200,
        "similarity_threshold": 0.55
    }
    """
    defaults = {
        "ttl": dict(DEFAULT_TTL),
        "promote_threshold": DEFAULT_PROMOTE_THRESHOLD,
        "max_active_memories": MAX_ACTIVE_MEMORIES,
        "similarity_threshold": SIMILARITY_THRESHOLD,
    }
    if config_path and os.path.isfile(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                user_config = json.load(f)
            # Merge: user overrides defaults (shallow for top-level, deep for ttl)
            if "ttl" in user_config:
                defaults["ttl"].update(user_config["ttl"])
            for key in ("promote_threshold", "max_active_memories", "similarity_threshold"):
                if key in user_config:
                    defaults[key] = user_config[key]
        except (json.JSONDecodeError, OSError) as e:
            print(f"WARN: Failed to load config from {config_path}: {e}", file=sys.stderr)
    return defaults


# ═══════════════════════════════════════════════════════════════════════════
# Section 3: Index I/O
# ═══════════════════════════════════════════════════════════════════════════

def _empty_index() -> Dict[str, Any]:
    """Return a fresh, empty memory index."""
    return {
        "version": "1.0",
        "memories": [],
        "stats": {
            "total_created": 0,
            "total_promoted": 0,
            "total_expired": 0,
            "total_merged": 0,
            "last_gc": None,
        },
    }


def load_index(index_path: str) -> Dict[str, Any]:
    """Load the memory index from disk. Returns empty index if missing/corrupt."""
    if not os.path.isfile(index_path):
        return _empty_index()
    try:
        with open(index_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Ensure required fields exist
        if "memories" not in data:
            data["memories"] = []
        if "stats" not in data:
            data["stats"] = _empty_index()["stats"]
        return data
    except (json.JSONDecodeError, OSError):
        return _empty_index()


def save_index(index_path: str, idx: Dict[str, Any]) -> None:
    """Atomically save the memory index to disk.

    Uses write-to-temp + rename to prevent corruption on crash.
    """
    idx["version"] = "1.0"
    parent = os.path.dirname(index_path)
    if parent:
        os.makedirs(parent, exist_ok=True)

    tmp_path = index_path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(idx, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, index_path)


# ═══════════════════════════════════════════════════════════════════════════
# Section 4: Text Similarity (Jaccard over token sets)
# ═══════════════════════════════════════════════════════════════════════════

def tokenize(text: str) -> set:
    """Tokenize text into a set of normalized terms.

    Splits on whitespace/punctuation, lowercases, and filters out
    single-character tokens. Also extracts CJK character bigrams
    for Chinese/Japanese/Korean text support.
    """
    tokens = set()
    text = text.lower().strip()

    # Alphanumeric words (including underscores/hyphens)
    for word in re.findall(r"[a-z0-9_\-]+", text):
        if len(word) > 1:
            tokens.add(word)

    # CJK characters: unigrams + bigrams for better matching
    cjk_segments = re.findall(r"[\u4e00-\u9fff]+", text)
    for segment in cjk_segments:
        for i in range(len(segment)):
            tokens.add(segment[i])
            if i + 1 < len(segment):
                tokens.add(segment[i : i + 2])

    return tokens


def similarity(text_a: str, text_b: str) -> float:
    """Compute Jaccard similarity between two texts.

    Returns a value between 0.0 (no overlap) and 1.0 (identical token sets).
    """
    tokens_a = tokenize(text_a)
    tokens_b = tokenize(text_b)
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b
    return len(intersection) / len(union) if union else 0.0


def find_most_similar(
    memories: List[Dict], value: str, exclude_key: Optional[str] = None
) -> Tuple[Optional[Dict], float]:
    """Find the most similar active memory to the given value.

    Skips promoted memories and the memory with the given key.
    Returns (best_match, similarity_score).
    """
    best_sim = 0.0
    best_match = None
    for mem in memories:
        if mem.get("status") == "promoted":
            continue
        if exclude_key and mem["key"] == exclude_key:
            continue
        sim = similarity(value, mem.get("value", ""))
        if sim > best_sim:
            best_sim = sim
            best_match = mem
    return best_match, best_sim


# ═══════════════════════════════════════════════════════════════════════════
# Section 5: Core Operations
# ═══════════════════════════════════════════════════════════════════════════

def cmd_add(
    index_path: str,
    mem_type: str,
    key: str,
    value: str,
    importance: int = 3,
    ttl_days: Optional[int] = None,
    config: Optional[Dict] = None,
) -> str:
    """Add a new memory entry with automatic deduplication.

    If a similar memory already exists (Jaccard >= threshold), the
    existing memory is updated (merged) instead of creating a duplicate.

    Args:
        index_path: Path to the memory index file.
        mem_type: Memory type (context, preference, progress, insight).
        key: Unique identifier for the memory.
        value: Description/content of the memory.
        importance: Priority level 1-5 (default 3).
        ttl_days: Override TTL in days (None = use type default).
        config: Configuration dict (None = use defaults).

    Returns:
        The key of the created or merged memory.
    """
    config = config or {}
    ttl_map = config.get("ttl", DEFAULT_TTL)
    sim_threshold = config.get("similarity_threshold", SIMILARITY_THRESHOLD)

    if mem_type not in VALID_TYPES:
        print(f"WARN: Invalid type '{mem_type}', defaulting to 'context'")
        mem_type = "context"
    importance = max(1, min(5, importance))

    idx = load_index(index_path)
    now = _utcnow()
    now_str = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    # --- Deduplication check ---
    active = [m for m in idx["memories"] if m.get("status") != "promoted"]
    similar, sim_score = find_most_similar(active, value)

    if similar and sim_score >= sim_threshold:
        # Merge into existing memory: keep longer value, higher importance
        if len(value) > len(similar.get("value", "")):
            similar["value"] = value
        similar["importance"] = max(similar.get("importance", 3), importance)
        similar["last_accessed"] = now_str

        # Recalculate expiry with refreshed TTL
        base_ttl = ttl_days or ttl_map.get(mem_type, 14)
        imp_mult = IMPORTANCE_TTL_MULTIPLIER.get(importance, 1.0)
        effective_ttl = int(base_ttl * imp_mult)
        similar["ttl_days"] = effective_ttl
        # Extend from now, not from original creation
        expires = now + timedelta(days=effective_ttl)
        similar["_expires"] = expires.strftime("%Y-%m-%dT%H:%M:%SZ")

        idx["stats"]["total_merged"] = idx["stats"].get("total_merged", 0) + 1
        save_index(index_path, idx)
        print(f"MERGED: into '{similar['key']}' (similarity={sim_score:.2f})")
        return similar["key"]

    # --- Check for key collision ---
    for mem in idx["memories"]:
        if mem["key"] == key:
            # Update existing key in place
            mem["type"] = mem_type
            mem["value"] = value
            mem["importance"] = importance
            mem["last_accessed"] = now_str
            base_ttl = ttl_days or ttl_map.get(mem_type, 14)
            imp_mult = IMPORTANCE_TTL_MULTIPLIER.get(importance, 1.0)
            effective_ttl = int(base_ttl * imp_mult)
            mem["ttl_days"] = effective_ttl
            mem["_expires"] = (now + timedelta(days=effective_ttl)).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            )
            mem["status"] = "active"
            save_index(index_path, idx)
            print(f"UPDATED: key '{key}' (type={mem_type}, importance={importance})")
            return key

    # --- Create new memory ---
    base_ttl = ttl_days or ttl_map.get(mem_type, 14)
    imp_mult = IMPORTANCE_TTL_MULTIPLIER.get(importance, 1.0)
    effective_ttl = int(base_ttl * imp_mult)
    expires = now + timedelta(days=effective_ttl)

    memory = {
        "key": key,
        "type": mem_type,
        "value": value,
        "importance": importance,
        "created": now_str,
        "last_accessed": now_str,
        "access_count": 0,
        "ttl_days": effective_ttl,
        "status": "active",
        "_expires": expires.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    idx["memories"].append(memory)
    idx["stats"]["total_created"] = idx["stats"].get("total_created", 0) + 1
    save_index(index_path, idx)
    print(
        f"ADDED: key '{key}' (type={mem_type}, importance={importance}, "
        f"ttl={effective_ttl}d)"
    )
    return key


def cmd_gc(index_path: str, config: Optional[Dict] = None) -> Dict[str, int]:
    """Run garbage collection: expire old memories, deduplicate, and evict overflow.

    The GC pipeline:
    1. Extend TTL for frequently-accessed memories (access_count * bonus days).
    2. Mark expired memories (status → 'expired').
    3. Deduplicate remaining active memories (Jaccard merge).
    4. Evict lowest-priority memories if count exceeds max_active_memories.

    Args:
        index_path: Path to the memory index file.
        config: Configuration dict.

    Returns:
        Summary dict with counts: expired, merged, promotable, active.
    """
    config = config or {}
    promote_threshold = config.get("promote_threshold", DEFAULT_PROMOTE_THRESHOLD)
    max_active = config.get("max_active_memories", MAX_ACTIVE_MEMORIES)
    sim_threshold = config.get("similarity_threshold", SIMILARITY_THRESHOLD)

    idx = load_index(index_path)
    now = _utcnow()
    now_str = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    expired_memories = []
    promotable = []
    kept = []

    for mem in idx["memories"]:
        # Skip already promoted or expired
        if mem.get("status") == "promoted":
            kept.append(mem)
            continue
        if mem.get("status") == "expired":
            expired_memories.append(mem)
            continue

        # --- Access-based TTL extension ---
        access_count = mem.get("access_count", 0)
        if access_count > 0 and "_expires" in mem:
            try:
                original_expires = datetime.strptime(
                    mem["_expires"], "%Y-%m-%dT%H:%M:%SZ"
                )
                bonus = min(access_count * ACCESS_TTL_BONUS_DAYS, ACCESS_TTL_MAX_DAYS)
                created = datetime.strptime(mem["created"], "%Y-%m-%dT%H:%M:%SZ")
                max_expires = created + timedelta(days=ACCESS_TTL_MAX_DAYS)
                extended = original_expires + timedelta(days=bonus)
                new_expires = min(extended, max_expires)
                if new_expires > original_expires:
                    mem["_expires"] = new_expires.strftime("%Y-%m-%dT%H:%M:%SZ")
            except (ValueError, KeyError):
                pass

        # --- Check expiry ---
        expires_str = mem.get("_expires", "")
        if expires_str and expires_str < now_str:
            mem["status"] = "expired"
            expired_memories.append(mem)
            continue

        # --- Check if promotable ---
        if access_count >= promote_threshold:
            promotable.append(mem)

        kept.append(mem)

    # --- Deduplication pass on active memories ---
    merged_count = 0
    deduped = []
    seen_keys = set()

    for i, mem in enumerate(kept):
        if mem["key"] in seen_keys:
            continue
        if mem.get("status") == "promoted":
            deduped.append(mem)
            seen_keys.add(mem["key"])
            continue

        # Check remaining entries for duplicates
        for j in range(i + 1, len(kept)):
            other = kept[j]
            if other["key"] in seen_keys or other.get("status") == "promoted":
                continue
            sim = similarity(mem.get("value", ""), other.get("value", ""))
            if sim >= sim_threshold:
                # Merge: keep the longer/more important one
                if len(other.get("value", "")) > len(mem.get("value", "")):
                    target, source = other, mem
                else:
                    target, source = mem, other
                target["importance"] = max(
                    target.get("importance", 3), source.get("importance", 3)
                )
                target["access_count"] = max(
                    target.get("access_count", 0), source.get("access_count", 0)
                )
                seen_keys.add(source["key"])
                merged_count += 1
                print(
                    f"  DEDUP: merged '{source['key']}' into '{target['key']}' "
                    f"(similarity={sim:.2f})"
                )

        deduped.append(mem)
        seen_keys.add(mem["key"])

    # --- Overflow eviction: remove lowest-priority active memories ---
    active_only = [m for m in deduped if m.get("status") != "promoted"]
    overflow_count = 0
    if len(active_only) > max_active:
        overflow = len(active_only) - max_active
        # Sort by importance (asc) then created (asc) — evict low+old first
        active_only.sort(
            key=lambda m: (m.get("importance", 3), m.get("created", ""))
        )
        evicted = active_only[:overflow]
        for m in evicted:
            m["status"] = "expired"
            expired_memories.append(m)
        overflow_count = len(evicted)
        print(f"  OVERFLOW: evicted {overflow_count} entries (cap={max_active})")

    # --- Reassemble and save ---
    idx["memories"] = expired_memories + deduped
    idx["stats"]["total_expired"] = (
        idx["stats"].get("total_expired", 0) + len(expired_memories)
    )
    idx["stats"]["total_merged"] = (
        idx["stats"].get("total_merged", 0) + merged_count
    )
    idx["stats"]["last_gc"] = now_str
    save_index(index_path, idx)

    # --- Report ---
    newly_expired = len(expired_memories)
    print(f"GC complete:")
    print(f"  expired:   {newly_expired}")
    print(f"  merged:    {merged_count}")
    print(f"  promotable: {len(promotable)} (access_count >= {promote_threshold})")
    print(f"  active:    {len([m for m in deduped if m.get('status') != 'promoted'])}")

    if promotable:
        print(f"\nPromotable memories (access >= {promote_threshold}):")
        for m in promotable:
            print(
                f"  '{m['key']}' [{m['type']}]: {m['value'][:60]} "
                f"(accessed {m['access_count']}x)"
            )

    return {
        "expired": newly_expired,
        "merged": merged_count,
        "promotable": len(promotable),
        "active": len([m for m in deduped if m.get("status") != "promoted"]),
    }


def cmd_validate(index_path: str, config: Optional[Dict] = None) -> Dict[str, int]:
    """Validate memories: detect injection patterns, contradictions, and low-quality entries.

    Checks performed:
    1. Injection/credential scan (regex patterns).
    2. Contradiction detection (similar but not duplicate memories).
    3. Low-quality detection (too short, low importance + stale).

    Returns:
        Summary dict with counts: issues, contradictions.
    """
    config = config or {}
    sim_threshold = config.get("similarity_threshold", SIMILARITY_THRESHOLD)

    idx = load_index(index_path)
    active = [m for m in idx["memories"] if m.get("status") == "active"]
    issues = []
    contradictions = []

    # --- 1. Injection / credential scan ---
    for mem in active:
        value = mem.get("value", "")
        for pattern, label in INJECTION_PATTERNS:
            if re.search(pattern, value, re.IGNORECASE):
                issues.append(
                    {
                        "type": "injection",
                        "key": mem["key"],
                        "label": label,
                        "value_preview": value[:80],
                    }
                )

    # --- 2. Contradiction scan ---
    for i, a in enumerate(active):
        for j in range(i + 1, len(active)):
            b = active[j]
            sim = similarity(a.get("value", ""), b.get("value", ""))
            if CONTRADICTION_SIM_LOW <= sim < sim_threshold:
                contradictions.append(
                    {
                        "keys": [a["key"], b["key"]],
                        "similarity": round(sim, 2),
                        "a_preview": a.get("value", "")[:60],
                        "b_preview": b.get("value", "")[:60],
                        "a_importance": a.get("importance", 3),
                        "b_importance": b.get("importance", 3),
                    }
                )

    # --- 3. Low-quality entries ---
    now = _utcnow()
    for mem in active:
        value = mem.get("value", "")
        importance = mem.get("importance", 3)

        if len(value) < 10:
            issues.append(
                {
                    "type": "too_short",
                    "key": mem["key"],
                    "value_preview": value,
                }
            )

        try:
            created = datetime.strptime(mem["created"], "%Y-%m-%dT%H:%M:%SZ")
            age_days = (now - created).days
        except (ValueError, KeyError):
            age_days = 0

        if importance <= 1 and age_days > 7:
            issues.append(
                {
                    "type": "low_importance_stale",
                    "key": mem["key"],
                    "importance": importance,
                    "age_days": age_days,
                    "value_preview": value[:60],
                }
            )

    # --- Report ---
    print(f"Validate: {len(active)} active memories scanned")

    if not issues and not contradictions:
        print("  All clean. No issues found.")
        return {"issues": 0, "contradictions": 0}

    if issues:
        print(f"\n  Issues ({len(issues)}):")
        for iss in issues:
            if iss["type"] == "injection":
                print(f"    INJECT  [{iss['key']}] {iss['label']}: {iss['value_preview']}")
            elif iss["type"] == "too_short":
                print(f"    SHORT   [{iss['key']}] \"{iss['value_preview']}\"")
            elif iss["type"] == "low_importance_stale":
                print(
                    f"    STALE   [{iss['key']}] importance={iss['importance']} "
                    f"age={iss['age_days']}d: {iss['value_preview']}"
                )

    if contradictions:
        print(f"\n  Potential contradictions ({len(contradictions)}):")
        for c in contradictions:
            print(f"    SIM={c['similarity']} [{c['keys'][0]}] vs [{c['keys'][1]}]")
            print(f"      A (imp={c['a_importance']}): {c['a_preview']}")
            print(f"      B (imp={c['b_importance']}): {c['b_preview']}")

    return {"issues": len(issues), "contradictions": len(contradictions)}


def cmd_promote(
    index_path: str, key: str, config: Optional[Dict] = None
) -> bool:
    """Promote a memory from L3 (dynamic) to L2 (verified).

    Promoted memories are excluded from GC expiry and deduplication.
    Typically used for memories that have proven their value through
    repeated access.

    Args:
        index_path: Path to the memory index file.
        key: The memory key to promote.

    Returns:
        True if promoted, False if not found.
    """
    idx = load_index(index_path)
    for mem in idx["memories"]:
        if mem["key"] == key:
            if mem.get("status") == "promoted":
                print(f"ALREADY_PROMOTED: '{key}'")
                return True
            mem["status"] = "promoted"
            idx["stats"]["total_promoted"] = (
                idx["stats"].get("total_promoted", 0) + 1
            )
            save_index(index_path, idx)
            print(f"PROMOTED: '{key}' (type={mem['type']}, importance={mem.get('importance', 3)})")
            return True

    print(f"NOT_FOUND: '{key}'")
    return False


# Common English stop words for search filtering
_STOP_WORDS = {
    "the", "is", "a", "an", "in", "of", "to", "and", "or", "for", "on", "at",
    "it", "be", "as", "by", "this", "that", "with", "from", "not", "are", "was",
    "but", "have", "has", "had", "do", "does", "did", "will", "would", "can",
    "could", "should", "may", "might", "must", "shall", "if", "then", "else",
    "so", "no", "yes", "all", "each", "every", "both", "few", "more", "most",
    "other", "some", "such", "only", "own", "same", "than", "too", "very",
}


def cmd_search(
    index_path: str,
    query: str,
    mem_type: Optional[str] = None,
    limit: int = 10,
    include_expired: bool = False,
) -> List[Dict]:
    """Search memories by keyword matching.

    Scores are based on keyword overlap between the query and
    memory key+value, weighted by importance.

    Args:
        index_path: Path to the memory index file.
        query: Search query string.
        mem_type: Filter by memory type (optional).
        limit: Maximum number of results.
        include_expired: Whether to include expired memories.

    Returns:
        List of matching memories sorted by relevance score.
    """
    idx = load_index(index_path)
    query_words = set(query.lower().split()) - _STOP_WORDS

    if not query_words:
        print("WARN: Query is empty after removing stop words.")
        return []

    scored = []
    for mem in idx["memories"]:
        # Filter by status
        if not include_expired and mem.get("status") == "expired":
            continue
        # Filter by type
        if mem_type and mem.get("type") != mem_type:
            continue

        # Build word set from key + value
        mem_words = set()
        mem_words.update(mem.get("key", "").lower().replace("_", " ").split())
        mem_words.update(mem.get("value", "").lower().split())
        mem_words -= _STOP_WORDS

        overlap = query_words & mem_words
        if overlap:
            # Score: overlap count + importance bonus
            importance_bonus = mem.get("importance", 3) * 0.1
            score = len(overlap) + importance_bonus
            scored.append((score, mem))

    scored.sort(key=lambda x: x[0], reverse=True)
    results = [mem for _, mem in scored[:limit]]

    # Increment access counts for returned results
    if results:
        result_keys = {m["key"] for m in results}
        now_str = _utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        for mem in idx["memories"]:
            if mem["key"] in result_keys:
                mem["access_count"] = mem.get("access_count", 0) + 1
                mem["last_accessed"] = now_str
        save_index(index_path, idx)

    # Display results
    if not results:
        print(f"No results for query: '{query}'")
    else:
        print(f"Found {len(results)} result(s) for '{query}':")
        for mem in results:
            status_tag = f"[{mem.get('status', 'active')}]"
            print(
                f"  {status_tag:<11} [{mem['type']}] '{mem['key']}' "
                f"(imp={mem.get('importance', 3)}, acc={mem.get('access_count', 0)}): "
                f"{mem.get('value', '')[:70]}"
            )

    return results


def cmd_stats(index_path: str) -> None:
    """Display memory index statistics.

    Shows counts by type, by status, by importance, and aggregate stats.
    """
    idx = load_index(index_path)
    memories = idx["memories"]
    stats = idx["stats"]

    by_type: Dict[str, int] = {}
    by_status: Dict[str, int] = {}
    by_importance: Dict[int, int] = {}

    for mem in memories:
        t = mem.get("type", "unknown")
        by_type[t] = by_type.get(t, 0) + 1

        s = mem.get("status", "active")
        by_status[s] = by_status.get(s, 0) + 1

        imp = mem.get("importance", 3)
        by_importance[imp] = by_importance.get(imp, 0) + 1

    print(f"Memory Index Statistics")
    print(f"{'=' * 40}")
    print(f"Total memories:  {len(memories)}")
    print(f"Index file:      {index_path}")
    print()
    print(f"By status:")
    for s in sorted(by_status.keys()):
        print(f"  {s:<12} {by_status[s]}")
    print()
    print(f"By type:")
    for t in sorted(by_type.keys()):
        print(f"  {t:<12} {by_type[t]}")
    print()
    print(f"By importance:")
    for imp in sorted(by_importance.keys()):
        print(f"  level {imp}:     {by_importance[imp]}")
    print()
    print(f"Lifetime stats:")
    print(f"  created:     {stats.get('total_created', 0)}")
    print(f"  promoted:    {stats.get('total_promoted', 0)}")
    print(f"  expired:     {stats.get('total_expired', 0)}")
    print(f"  merged:      {stats.get('total_merged', 0)}")
    print(f"  last GC:     {stats.get('last_gc', 'never')}")


def cmd_list(
    index_path: str,
    mem_type: Optional[str] = None,
    status: Optional[str] = None,
) -> None:
    """List all memories, optionally filtered by type and/or status."""
    idx = load_index(index_path)
    memories = idx["memories"]

    if mem_type:
        memories = [m for m in memories if m.get("type") == mem_type]
    if status:
        memories = [m for m in memories if m.get("status", "active") == status]

    if not memories:
        print("(no memories found)")
        return

    for mem in memories:
        status_tag = mem.get("status", "active")[0].upper()  # A/E/P
        imp = mem.get("importance", 3)
        acc = mem.get("access_count", 0)
        expires = mem.get("_expires", "?")[:10]
        print(
            f"[{status_tag}] {mem.get('type', '?'):<12} imp:{imp} acc:{acc:<3} "
            f"exp:{expires} | '{mem['key']}': {mem.get('value', '')[:55]}"
        )


# ═══════════════════════════════════════════════════════════════════════════
# Section 6: CLI Parser
# ═══════════════════════════════════════════════════════════════════════════

def _parse_global_args(argv: List[str]) -> Tuple[str, Dict[str, str], List[str]]:
    """Extract global flags (--index, --config) and the subcommand from argv.

    Returns:
        (index_path, config_dict, remaining_argv)
    """
    index_path = DEFAULT_INDEX_PATH
    config_path = None
    remaining = []
    i = 0

    while i < len(argv):
        if argv[i] == "--index" and i + 1 < len(argv):
            index_path = argv[i + 1]
            i += 2
        elif argv[i] == "--config" and i + 1 < len(argv):
            config_path = argv[i + 1]
            i += 2
        else:
            remaining.append(argv[i])
            i += 1

    config = load_config(config_path)
    return index_path, config, remaining


def _parse_named_args(argv: List[str]) -> Tuple[List[str], Dict[str, str]]:
    """Parse --key value pairs from a list of arguments.

    Returns:
        (positional_args, named_args_dict)
    """
    named = {}
    positional = []
    i = 0
    while i < len(argv):
        if argv[i].startswith("--") and i + 1 < len(argv):
            key = argv[i][2:]
            named[key] = argv[i + 1]
            i += 2
        else:
            positional.append(argv[i])
            i += 1
    return positional, named


def main(argv: Optional[List[str]] = None) -> int:
    """Main entry point. Parse args and dispatch to the appropriate command."""
    if argv is None:
        argv = sys.argv[1:]

    if not argv:
        print(__doc__)
        return 1

    index_path, config, remaining = _parse_global_args(argv)

    if not remaining:
        print(__doc__)
        return 1

    cmd = remaining[0]
    cmd_args = remaining[1:]

    # ─── add ───
    if cmd == "add":
        _, named = _parse_named_args(cmd_args)
        mem_type = named.get("type")
        key = named.get("key")
        value = named.get("value")

        if not mem_type or not key or not value:
            print(
                "Usage: memory-gc.py add --type <type> --key <key> "
                "--value <value> [--importance 1-5] [--ttl <days>]"
            )
            return 1

        importance = int(named.get("importance", "3"))
        ttl = int(named["ttl"]) if "ttl" in named else None
        cmd_add(index_path, mem_type, key, value, importance, ttl, config)

    # ─── gc ───
    elif cmd == "gc":
        cmd_gc(index_path, config)

    # ─── validate ───
    elif cmd == "validate":
        cmd_validate(index_path, config)

    # ─── promote ───
    elif cmd == "promote":
        _, named = _parse_named_args(cmd_args)
        key = named.get("key")
        if not key:
            # Also accept positional: promote <key>
            if cmd_args and not cmd_args[0].startswith("--"):
                key = cmd_args[0]
            else:
                print("Usage: memory-gc.py promote --key <key>")
                return 1
        cmd_promote(index_path, key, config)

    # ─── search ───
    elif cmd == "search":
        _, named = _parse_named_args(cmd_args)
        query = named.get("query", "")
        if not query:
            # Accept positional: search <query>
            if cmd_args and not cmd_args[0].startswith("--"):
                query = " ".join(
                    a for a in cmd_args if not a.startswith("--")
                )
            else:
                print("Usage: memory-gc.py search --query <query> [--type <type>] [--limit N]")
                return 1
        mem_type = named.get("type")
        limit = int(named.get("limit", "10"))
        include_expired = named.get("include-expired", "").lower() in ("true", "1", "yes")
        cmd_search(index_path, query, mem_type, limit, include_expired)

    # ─── stats ───
    elif cmd == "stats":
        cmd_stats(index_path)

    # ─── list ───
    elif cmd == "list":
        _, named = _parse_named_args(cmd_args)
        mem_type = named.get("type")
        status = named.get("status")
        cmd_list(index_path, mem_type, status)

    # ─── version ───
    elif cmd in ("version", "--version", "-v"):
        print(f"memory-gc {VERSION}")

    # ─── help ───
    elif cmd in ("help", "--help", "-h"):
        print(__doc__)

    else:
        print(f"Unknown command: {cmd}")
        print("Available commands: add, gc, validate, promote, search, stats, list")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
