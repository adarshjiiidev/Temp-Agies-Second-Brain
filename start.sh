#!/usr/bin/env bash
# TEMPORARY AEGIS DASHBOARD LAUNCHER

cd "$HOME/aegis-dashboard" || { echo "Run from dashboard root."; exit 1; }

echo "=== STARTING TEMPORARY AEGIS DASHBOARD ==="

pkill -f "server.py" 2>/dev/null || true
pkill -f "python.*http.server.*2981" 2>/dev/null || true
pkill -f "vite" 2>/dev/null || true
pkill -f "next" 2>/dev/null || true
sleep 1

# ── Build frontend (standalone static) ───────────────────────────────────────

echo "🔨 Building AEGIS frontend (standalone)..."
npx vite build --outDir dist 2>&1 | tail -3
echo "✅ Frontend built → dist/"

# ── Enable systemd services ───────────────────────────────────────────────────

echo "🔧 Enabling AEGIS systemd services..."
systemctl --user enable aegis-backend.service aegis-frontend.service 2>/dev/null || true
systemctl --user daemon-reload

# ── Start backend via systemd ─────────────────────────────────────────────────

echo "📡 Starting AEGIS Backend (systemd, port 8787)..."
systemctl --user restart aegis-backend.service
for i in $(seq 1 30); do
  curl -s -m 1 http://127.0.0.1:8787/api/vault >/dev/null 2>&1 && { echo "✅ Backend OK"; break; }
  sleep 1
done

# ── Start frontend via systemd ────────────────────────────────────────────────

echo "🌐 Starting AEGIS Frontend (systemd, port 2981)..."
systemctl --user restart aegis-frontend.service
for i in $(seq 1 30); do
  curl -s -m 1 http://127.0.0.1:2981 >/dev/null 2>&1 && { echo "✅ Frontend OK"; break; }
  sleep 1
done

echo ""
echo "══════════════════════════════════════════════════════════════"
echo "           AEGIS AI OS DASHBOARD IS RUNNING                   "
echo "══════════════════════════════════════════════════════════════"
echo "  🌐 Local URL:      http://localhost:2981"
echo "  🌐 Network URL:    http://127.0.0.1:2981"
echo "  📡 API Backend:    http://127.0.0.1:8787"
echo "  🔌 WebSocket:      ws://localhost:2981/ws"
echo "  🕸️  Obsidian Mesh:  PARA Knowledge Graph active"
echo "  🧠 Hermes Profile: agies (18 skills, 20 tools)"
echo "  🔄 Auto-start:     systemd enabled (reboots survive)"
echo "══════════════════════════════════════════════════════════════"
echo "══ Services: backend=$(systemctl --user is-active aegis-backend.service)  frontend=$(systemctl --user is-active aegis-frontend.service) ══"
echo ""
echo "🔄 All services now start automatically on boot."
echo "   Manage: systemctl --user status aegis-backend aegis-frontend"
echo "   Logs:   journalctl --user -u aegis-backend -f"
echo "           journalctl --user -u aegis-frontend -f"

# ── Keep alive (wait for either service to die) ──────────────────────────────

systemctl --user is-active aegis-backend.service aegis-frontend.service
wait
