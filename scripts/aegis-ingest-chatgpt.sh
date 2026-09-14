#!/bin/bash
# aegis-ingest-chatgpt.sh — Ingest ChatGPT export ZIP into aegis memory
# Run: daily via systemd timer, or manually
# Usage: aegis-ingest-chatgpt.sh [/path/to/chatgpt-export.zip]

set -u

AEGIS_HOME="${AEGIS_HOME:-$HOME/.temporary-aegis}"
INGEST_DIR="$AEGIS_HOME/memory/0-Inbox/chatgpt"
EXTRACT_DIR="/tmp/aegis-chatgpt-$(date +%Y%m%d-%H%M%S)"
KNOWLEDGE_DIR="$AEGIS_HOME/memory"
LOG_FILE="$AEGIS_HOME/memory/logs/chatgpt-ingest.log"

mkdir -p "$INGEST_DIR"
mkdir -p "$EXTRACT_DIR"
mkdir -p "$(dirname "$LOG_FILE")"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Find export ZIP
EXPORT_ZIP="${1:-}"
if [ -z "$EXPORT_ZIP" ]; then
    for pattern in \
        "$HOME/Downloads/chatgpt-export.zip" \
        "$HOME/Downloads/chat_history.zip" \
        "$HOME/Downloads"/*.zip \
        "$HOME/Desktop"/*.zip \
        "$HOME"/*.zip; do
        if [ -f "$pattern" ]; then
            EXPORT_ZIP="$pattern"
            break
        fi
    done
fi

if [ -z "$EXPORT_ZIP" ] || [ ! -f "$EXPORT_ZIP" ]; then
    log "No ChatGPT export ZIP found. Place export in ~/Downloads/ and re-run, or pass path as argument."
    rm -rf "$EXTRACT_DIR"
    exit 0
fi

log "Processing: $EXPORT_ZIP"

# Extract
unzip -q "$EXPORT_ZIP" -d "$EXTRACT_DIR" 2>/dev/null || {
    log "ERROR: Failed to extract $EXPORT_ZIP"
    exit 1
}

# Find conversations.json
CONV_FILE=$(find "$EXTRACT_DIR" -name "conversations.json" -o -name "conversations*.json" 2>/dev/null | head -1)

if [ -z "$CONV_FILE" ]; then
    log "ERROR: conversations.json not found in export"
    ls -la "$EXTRACT_DIR" >> "$LOG_FILE"
    exit 1
fi

log "Found conversations: $CONV_FILE"

# Pass env vars to Python
export EXTRACT_DIR INGEST_DIR KNOWLEDGE_DIR LOG_FILE

# Process conversations
python3 << 'PYTHON_SCRIPT'
import json
import os
import re
from datetime import datetime
from pathlib import Path

extract_dir = Path(os.environ["EXTRACT_DIR"])
ingest_dir = Path(os.environ["INGEST_DIR"])
knowledge_dir = Path(os.environ["KNOWLEDGE_DIR"])
log_entries = []

def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{ts}] {msg}"
    log_entries.append(entry)
    print(entry)

log("Starting ChatGPT ingestion...")

# Load conversations
conv_file = extract_dir / "conversations.json"
if not conv_file.exists():
    for f in extract_dir.rglob("conversations*.json"):
        conv_file = f
        break

if not conv_file.exists():
    log("ERROR: No conversations.json found")
    exit(1)

with open(conv_file, "r", encoding="utf-8") as f:
    conversations = json.load(f)

log(f"Found {len(conversations)} conversations")

# Privacy patterns to redact
SECRET_PATTERNS = [
    (r"sk-(?:proj-)?[A-Za-z0-9_-]{20,}", "[REDACTED_API_KEY]"),
    (r"ghp_[A-Za-z0-9]{36}", "[REDACTED_GITHUB_TOKEN]"),
    (r"gho_[A-Za-z0-9]{36}", "[REDACTED_GITHUB_TOKEN]"),
    (r"[A-Za-z0-9_+/=]{40}", "[REDACTED_SHA]"),
    (r"-----BEGIN (RSA|OPENSSH|EC|PGP) PRIVATE KEY-----", "[REDACTED_KEY]"),
    (r"password[=:]\s*\S+", "password=[REDACTED]"),
    (r"secret[=:]\s*\S+", "secret=[REDACTED]"),
    (r"token[=:]\s*\S+", "token=[REDACTED]"),
]

def redact(text):
    for pattern, replacement in SECRET_PATTERNS:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    return text

# Classification keywords
PROJECT_KEYWORDS = [
    "aegis", "world-viewer", "repusense", "chrome-extra", "project",
    "architecture", "refactor", "debug", "fix", "implement", "build",
    "feature", "deploy", "config", "setup", "install", "error", "bug",
    "test", "ci", "cd", "docker", "container", "server", "api", "database",
    "frontend", "backend", "react", "next.js", "python", "rust", "electron"
]

PREFERENCE_KEYWORDS = [
    "prefer", "favorite", "best", "hate", "love", "like", "dislike",
    "choice", "option", "decision", "because", "reason", "why",
    "tool", "library", "framework", "editor", "ide", "os", "distro"
]

LESSON_KEYWORDS = [
    "learned", "discovered", "figured out", "solved",
    "problem", "issue", "fix", "workaround", "error", "fail",
    "mistake", "lesson", "tip", "trick", "how to", "way to"
]

def classify_conversation(messages):
    text = " ".join(m.get("content", "") for m in messages).lower()
    scores = {"project": 0, "preference": 0, "lesson": 0, "general": 1}
    
    for kw in PROJECT_KEYWORDS:
        if kw in text:
            scores["project"] += 1
    for kw in PREFERENCE_KEYWORDS:
        if kw in text:
            scores["preference"] += 1
    for kw in LESSON_KEYWORDS:
        if kw in text:
            scores["lesson"] += 1
    
    best = max(scores, key=scores.get)
    if scores[best] == 0:
        return "general"
    return best

def extract_useful_content(messages):
    useful = []
    for msg in messages:
        content = msg.get("content", "").strip()
        if not content or len(content) < 10:
            continue
        
        lower = content.lower()
        if any(phrase in lower for phrase in [
            "hello", "hi there", "hey", "thanks", "thank you",
            "ok", "okay", "sure", "yes", "no", "lol", "haha",
            "nice", "good", "great", "awesome", "cool"
        ]) and len(content) < 50:
            continue
        
        useful.append({
            "role": msg.get("role", "unknown"),
            "content": redact(content),
            "timestamp": msg.get("timestamp", "")
        })
    
    return useful

# Process each conversation
ingested = 0
skipped = 0

for conv in conversations:
    title = conv.get("title", "Untitled")
    messages = conv.get("messages", [])
    create_time = conv.get("create_time", "")
    
    if not messages:
        skipped += 1
        continue
    
    classification = classify_conversation(messages)
    useful = extract_useful_content(messages)
    
    if not useful:
        skipped += 1
        continue
    
    date_str = datetime.now().strftime("%Y-%m-%d")
    
    if classification == "project":
        project_name = "general"
        for proj in ["Aegis", "world-viewer", "repusense", "chrome-extra"]:
            if proj.lower() in title.lower() or any(kw in title.lower() for kw in ["aegis", "world", "repo", "chrome"]):
                project_name = proj
                break
        
        project_dir = knowledge_dir / "1-Projects" / project_name
        project_dir.mkdir(parents=True, exist_ok=True)
        
        note_file = project_dir / f"chatgpt-{date_str}-{ingested}.md"
        
        with open(note_file, "w") as f:
            f.write(f"# ChatGPT Conversation — {title}\n\n")
            f.write(f"**Date:** {datetime.fromtimestamp(int(create_time)).strftime('%Y-%m-%d %H:%M') if create_time else 'Unknown'}\n")
            f.write(f"**Type:** Project discussion\n")
            f.write(f"**Project:** {project_name}\n")
            f.write(f"**Ingested:** {date_str}\n\n")
            f.write(f"---\n\n")
            for msg in useful:
                role = msg["role"].capitalize()
                f.write(f"## {role}\n\n{msg['content']}\n\n")
        
        log(f"  Project note: {project_name}/chatgpt-{date_str}-{ingested}.md ({len(useful)} messages)")
    
    elif classification == "preference":
        pref_dir = knowledge_dir / "2-Areas" / "personal"
        pref_dir.mkdir(parents=True, exist_ok=True)
        
        note_file = pref_dir / f"chatgpt-preferences-{date_str}-{ingested}.md"
        
        with open(note_file, "w") as f:
            f.write(f"# User Preferences — from ChatGPT\n\n")
            f.write(f"**Date:** {date_str}\n")
            f.write(f"**Source:** {title}\n")
            f.write(f"**Ingested:** {date_str}\n\n")
            f.write(f"---\n\n")
            for msg in useful:
                role = msg["role"].capitalize()
                f.write(f"## {role}\n\n{msg['content']}\n\n")
        
        log(f"  Preference note: personal/chatgpt-preferences-{date_str}-{ingested}.md")
    
    elif classification == "lesson":
        res_dir = knowledge_dir / "3-Resources"
        res_dir.mkdir(parents=True, exist_ok=True)
        
        note_file = res_dir / f"chatgpt-lessons-{date_str}-{ingested}.md"
        
        with open(note_file, "w") as f:
            f.write(f"# Lessons Learned — from ChatGPT\n\n")
            f.write(f"**Date:** {date_str}\n")
            f.write(f"**Source:** {title}\n")
            f.write(f"**Ingested:** {date_str}\n\n")
            f.write(f"---\n\n")
            for msg in useful:
                role = msg["role"].capitalize()
                f.write(f"## {role}\n\n{msg['content']}\n\n")
        
        log(f"  Lesson note: resources/chatgpt-lessons-{date_str}-{ingested}.md")
    
    else:
        note_file = ingest_dir / f"chatgpt-general-{date_str}-{ingested}.md"
        
        with open(note_file, "w") as f:
            f.write(f"# ChatGPT Conversation — {title}\n\n")
            f.write(f"**Date:** {date_str}\n")
            f.write(f"**Source:** {title}\n\n")
            f.write(f"---\n\n")
            for msg in useful[:10]:
                role = msg["role"].capitalize()
                f.write(f"## {role}\n\n{msg['content'][:500]}\n\n")
        
        log(f"  Inbox: chatgpt-general-{date_str}-{ingested}.md (truncated)")
    
    ingested += 1

log(f"Done: {ingested} conversations ingested, {skipped} skipped")

# Write log
log_file_path = Path(os.environ["LOG_FILE"])
log_file_path.parent.mkdir(parents=True, exist_ok=True)
with open(log_file_path, "a") as f:
    f.write("\n".join(log_entries) + "\n")

PYTHON_SCRIPT

log "ChatGPT ingestion complete"

# Cleanup
rm -rf "$EXTRACT_DIR"

echo "ChatGPT ingestion complete. Check logs: $LOG_FILE"
