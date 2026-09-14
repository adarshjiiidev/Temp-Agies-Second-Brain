#!/bin/bash
# aegis-snapshot.sh — Full PC state snapshot for agies memory
# Run: daily via systemd timer, or manually: ~/.temporary-aegis/scripts/aegis-snapshot.sh

set -u

TIMESTAMP=$(date +%Y-%m-%dT%H:%M:%S)
SNAPSHOT_DIR="$HOME/.temporary-aegis/memory/pc-state"
mkdir -p "$SNAPSHOT_DIR"
SNAPSHOT_FILE="$SNAPSHOT_DIR/$(date +%Y-%m-%d).md"

echo "# PC State Snapshot — $(date '+%Y-%m-%d %H:%M')" > "$SNAPSHOT_FILE"
echo "**Generated:** $TIMESTAMP" >> "$SNAPSHOT_FILE"
echo "" >> "$SNAPSHOT_FILE"

# 1. System info
echo "## System" >> "$SNAPSHOT_FILE"
echo "\`\`\`" >> "$SNAPSHOT_FILE"
uname -a >> "$SNAPSHOT_FILE"
echo "" >> "$SNAPSHOT_FILE"
cat /etc/os-release 2>/dev/null | head -5 >> "$SNAPSHOT_FILE"
echo "" >> "$SNAPSHOT_FILE"
echo "\`\`\`" >> "$SNAPSHOT_FILE"
echo "" >> "$SNAPSHOT_FILE"

# 2. Hardware
echo "## Hardware" >> "$SNAPSHOT_FILE"
echo "\`\`\`" >> "$SNAPSHOT_FILE"
free -h >> "$SNAPSHOT_FILE" 2>/dev/null
echo "---" >> "$SNAPSHOT_FILE"
lscpu | grep -E "Model name|CPU\(s\)|Architecture|Thread" >> "$SNAPSHOT_FILE" 2>/dev/null
echo "---" >> "$SNAPSHOT_FILE"
lsblk -o NAME,SIZE,TYPE,MOUNTPOINT 2>/dev/null >> "$SNAPSHOT_FILE"
echo "" >> "$SNAPSHOT_FILE"
echo "\`\`\`" >> "$SNAPSHOT_FILE"
echo "" >> "$SNAPSHOT_FILE"

# 3. Disk usage
echo "## Disk Usage" >> "$SNAPSHOT_FILE"
echo "\`\`\`" >> "$SNAPSHOT_FILE"
df -h 2>/dev/null | grep -E "^/dev|^Filesystem" >> "$SNAPSHOT_FILE"
echo "" >> "$SNAPSHOT_FILE"
echo "\`\`\`" >> "$SNAPSHOT_FILE"
echo "" >> "$SNAPSHOT_FILE"

# 4. Memory usage
echo "## Memory" >> "$SNAPSHOT_FILE"
echo "\`\`\`" >> "$SNAPSHOT_FILE"
free -h >> "$SNAPSHOT_FILE" 2>/dev/null
echo "" >> "$SNAPSHOT_FILE"
echo "\`\`\`" >> "$SNAPSHOT_FILE"
echo "" >> "$SNAPSHOT_FILE"

# 5. Top processes
echo "## Top Processes" >> "$SNAPSHOT_FILE"
echo "\`\`\`" >> "$SNAPSHOT_FILE"
ps aux --sort=-%mem 2>/dev/null | head -15 >> "$SNAPSHOT_FILE"
echo "" >> "$SNAPSHOT_FILE"
echo "\`\`\`" >> "$SNAPSHOT_FILE"
echo "" >> "$SNAPSHOT_FILE"

# 6. Network
echo "## Network" >> "$SNAPSHOT_FILE"
echo "\`\`\`" >> "$SNAPSHOT_FILE"
ip addr show 2>/dev/null | grep -E "^[0-9]:|inet " | head -20 >> "$SNAPSHOT_FILE"
echo "" >> "$SNAPSHOT_FILE"
echo "\`\`\`" >> "$SNAPSHOT_FILE"
echo "" >> "$SNAPSHOT_FILE"

# 7. Listening ports
echo "## Listening Ports" >> "$SNAPSHOT_FILE"
echo "\`\`\`" >> "$SNAPSHOT_FILE"
ss -tlnp 2>/dev/null | head -20 >> "$SNAPSHOT_FILE"
echo "" >> "$SNAPSHOT_FILE"
echo "\`\`\`" >> "$SNAPSHOT_FILE"
echo "" >> "$SNAPSHOT_FILE"

# 8. Systemd services (user)
echo "## User Systemd Services" >> "$SNAPSHOT_FILE"
echo "\`\`\`" >> "$SNAPSHOT_FILE"
systemctl --user list-units --type=service --state=running 2>/dev/null | tail -n +2 >> "$SNAPSHOT_FILE"
echo "" >> "$SNAPSHOT_FILE"
echo "\`\`\`" >> "$SNAPSHOT_FILE"
echo "" >> "$SNAPSHOT_FILE"

# 9. Docker
echo "## Docker" >> "$SNAPSHOT_FILE"
echo "\`\`\`" >> "$SNAPSHOT_FILE"
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null >> "$SNAPSHOT_FILE" || echo "No Docker containers running" >> "$SNAPSHOT_FILE"
echo "" >> "$SNAPSHOT_FILE"
docker images --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}" 2>/dev/null | head -10 >> "$SNAPSHOT_FILE" || echo "No Docker images" >> "$SNAPSHOT_FILE"
echo "" >> "$SNAPSHOT_FILE"
echo "\`\`\`" >> "$SNAPSHOT_FILE"
echo "" >> "$SNAPSHOT_FILE"

# 10. Installed packages (pacman)
echo "## Installed Packages (top 30)" >> "$SNAPSHOT_FILE"
echo "\`\`\`" >> "$SNAPSHOT_FILE"
pacman -Q 2>/dev/null | head -30 >> "$SNAPSHOT_FILE" || echo "pacman not available" >> "$SNAPSHOT_FILE"
echo "" >> "$SNAPSHOT_FILE"
echo "\`\`\`" >> "$SNAPSHOT_FILE"
echo "" >> "$SNAPSHOT_FILE"

# 11. Python packages
echo "## Python Packages" >> "$SNAPSHOT_FILE"
echo "\`\`\`" >> "$SNAPSHOT_FILE"
pip list 2>/dev/null | head -30 >> "$SNAPSHOT_FILE" || echo "pip not available" >> "$SNAPSHOT_FILE"
echo "" >> "$SNAPSHOT_FILE"
echo "\`\`\`" >> "$SNAPSHOT_FILE"
echo "" >> "$SNAPSHOT_FILE"

# 12. Node.js
echo "## Node.js" >> "$SNAPSHOT_FILE"
echo "\`\`\`" >> "$SNAPSHOT_FILE"
node --version 2>/dev/null >> "$SNAPSHOT_FILE"
npm list -g --depth=0 2>/dev/null >> "$SNAPSHOT_FILE"
echo "" >> "$SNAPSHOT_FILE"
echo "\`\`\`" >> "$SNAPSHOT_FILE"
echo "" >> "$SNAPSHOT_FILE"

# 13. Git projects in ~/Projects
echo "## Git Projects" >> "$SNAPSHOT_FILE"
echo "\`\`\`" >> "$SNAPSHOT_FILE"
for dir in $HOME/Projects/*/; do
    if [ -d "$dir/.git" ]; then
        name=$(basename "$dir")
        branch=$(cd "$dir" && git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")
        status=$(cd "$dir" && git status --short 2>/dev/null | head -3 || echo "")
        echo "### $name" >> "$SNAPSHOT_FILE"
        echo "Branch: $branch" >> "$SNAPSHOT_FILE"
        if [ -n "$status" ]; then
            echo "Changes:" >> "$SNAPSHOT_FILE"
            echo "$status" >> "$SNAPSHOT_FILE"
        fi
        echo "" >> "$SNAPSHOT_FILE"
    fi
done
echo "\`\`\`" >> "$SNAPSHOT_FILE"
echo "" >> "$SNAPSHOT_FILE"

# 14. Recent file changes in home (last 24h)
echo "## Recent File Changes (last 24h)" >> "$SNAPSHOT_FILE"
echo "\`\`\`" >> "$SNAPSHOT_FILE"
find /home/adarshjii -maxdepth 3 -type f -mtime -1 2>/dev/null | grep -v "/.cache/" | grep -v "/.local/share/Trash/" | head -30  >> "$SNAPSHOT_FILE" || true
echo "" >> "$SNAPSHOT_FILE"
echo "\`\`\`" >> "$SNAPSHOT_FILE"
echo "" >> "$SNAPSHOT_FILE"

# 15. Omarchy config summary
echo "## Omarchy Config Summary" >> "$SNAPSHOT_FILE"
echo "\`\`\`" >> "$SNAPSHOT_FILE"
if [ -f $HOME/.config/hypr/hyprland.conf ]; then
    echo "Hyprland: configured" >> "$SNAPSHOT_FILE"
    grep -E "exec=|bind=|workspace=|monitor=" $HOME/.config/hypr/hyprland.conf 2>/dev/null | head -10 >> "$SNAPSHOT_FILE"
else
    echo "Hyprland: not configured" >> "$SNAPSHOT_FILE"
fi
echo ""
if [ -f $HOME/.config/omarchy/shell.json ]; then
    echo "Omarchy shell: configured" >> "$SNAPSHOT_FILE"
else
    echo "Omarchy shell: not configured" >> "$SNAPSHOT_FILE"
fi
echo "" >> "$SNAPSHOT_FILE"
echo "\`\`\`" >> "$SNAPSHOT_FILE"
echo "" >> "$SNAPSHOT_FILE"

echo "# End of Snapshot" >> "$SNAPSHOT_FILE"

echo "Snapshot saved: $SNAPSHOT_FILE"
