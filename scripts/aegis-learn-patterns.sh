#!/bin/bash
# aegis-learn-patterns.sh — Detect recurring patterns in user behavior
# Run: weekly via systemd timer

set -euo pipefail

KNOWLEDGE_DIR="/home/adarshjii/.temporary-aegis/memory"
LOG_FILE="$KNOWLEDGE_DIR/logs/learn-patterns.log"
INSIGHTS_FILE="$KNOWLEDGE_DIR/2-Areas/personal/usage-patterns.md"

mkdir -p "$(dirname "$LOG_FILE")"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "Starting pattern detection..."

# 1. Most visited directories (from bash history)
log "Analyzing shell history..."
HISTORY_FILE="/home/adarshjii/.bash_history"
if [ -f "$HISTORY_FILE" ]; then
    cd_patterns=$(grep -E "^cd " "$HISTORY_FILE" 2>/dev/null | awk '{print $2}' | sort | uniq -c | sort -rn | head -15)
else
    cd_patterns="No bash history found"
fi

# 2. Most used commands
cmd_patterns=$(grep -v "^cd " "$HISTORY_FILE" 2>/dev/null | awk '{print $1}' | sort | uniq -c | sort -rn | head -20)

# 3. Active projects (git activity in last 7 days)
log "Checking git activity..."
project_activity=""
for dir in /home/adarshjii/Projects/*/; do
    if [ -d "$dir/.git" ]; then
        name=$(basename "$dir")
        commits=$(cd "$dir" && git log --oneline --since="7 days ago" 2>/dev/null | wc -l)
        if [ "$commits" -gt 0 ]; then
            last_commit=$(cd "$dir" && git log -1 --format="%s" 2>/dev/null)
            project_activity="$project_activity\n- **$name**: $commits commits, last: $last_commit"
        fi
    fi
done

# 4. Recent file changes (editing patterns)
log "Checking recent file edits..."
recent_edits=$(find /home/adarshjii/Projects -type f -mtime -7 2>/dev/null | head -20)

# 5. System changes (packages installed recently)
recent_packages=$(pacman -Q --quiet 2>/dev/null | while read pkg; do
    rank=$(pacman -Qi "$pkg" 2>/dev/null | grep "Install Date" | awk '{print $4}')
    echo "$rank $pkg"
done | sort | tail -10)

# Write insights
cat > "$INSIGHTS_FILE" << INSIGHTS
# Usage Patterns — $(date '+%Y-%m-%d')

**Generated:** $(date '+%Y-%m-%d %H:%M')
**Type:** Weekly pattern detection

---

## Most Visited Directories (last ~30 days)

INSIGHTS
echo "$cd_patterns" >> "$INSIGHTS_FILE"

cat >> "$INSIGHTS_FILE" << INSIGHTS2

## Most Used Commands (last ~30 days)

INSIGHTS2
echo "$cmd_patterns" >> "$INSIGHTS_FILE"

cat >> "$INSIGHTS_FILE" << INSIGHTS3

## Active Projects (last 7 days)

INSIGHTS3
echo -e "$project_activity" >> "$INSIGHTS_FILE"

cat >> "$INSIGHTS_FILE" << INSIGHTS4

## Recently Edited Files (last 7 days)

INSIGHTS4
echo "$recent_edits" >> "$INSIGHTS_FILE"

cat >> "$INSIGHTS_FILE" << INSIGHTS5

## Recently Installed Packages

INSIGHTS5
echo "$recent_packages" >> "$INSIGHTS_FILE"

echo "" >> "$INSIGHTS_FILE"
echo "**Last updated:** $(date '+%Y-%m-%d %H:%M')" >> "$INSIGHTS_FILE"

log "Pattern insights written to: $INSIGHTS_FILE"
