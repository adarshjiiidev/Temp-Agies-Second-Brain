#!/usr/bin/env python3
"""
AEGIS PTY Session Manager
==========================
Manages persistent pseudo-terminal sessions for all registered agents.
Agent command discovery is fully registry-driven via cfg.resolve_agent_command().
No hardcoded paths. No hardcoded usernames.
"""

import os
import pty
import fcntl
import termios
import struct
import asyncio
import subprocess
from typing import Dict, Optional, List
from collections import deque
from fastapi import WebSocket

from backend.config import cfg
from backend.logger import get_logger

log = get_logger("agent_pty")


class PTYSession:
    def __init__(
        self,
        session_id: str,
        command: List[str],
        cwd: Optional[str] = None,
        env: Optional[dict] = None,
    ):
        self.session_id = session_id
        self.command = command
        self.cwd = cwd or str(cfg.HOME)
        self.env = env or cfg.get_agent_env()
        self.master_fd: Optional[int] = None
        self.proc: Optional[subprocess.Popen] = None
        self.subscribers: List[WebSocket] = []
        self.history: deque = deque(maxlen=200)  # last 200 chunks for instant replay
        self.is_running = False
        self.read_task: Optional[asyncio.Task] = None

    def start(self):
        if self.is_running:
            return

        master_fd, slave_fd = pty.openpty()
        self.master_fd = master_fd

        flags = fcntl.fcntl(master_fd, fcntl.F_GETFL)
        fcntl.fcntl(master_fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

        winsize = struct.pack("HHHH", 24, 80, 0, 0)
        fcntl.ioctl(master_fd, termios.TIOCSWINSZ, winsize)

        try:
            self.proc = subprocess.Popen(
                self.command,
                stdin=slave_fd,
                stdout=slave_fd,
                stderr=slave_fd,
                cwd=self.cwd,
                env=self.env,
                preexec_fn=os.setsid,
                close_fds=True,
            )
            self.is_running = True
            log.info("PTY started: session=%s cmd=%s", self.session_id, self.command[0])
        except Exception as e:
            log.error("PTY start failed for %s: %s", self.session_id, e)
            raise
        finally:
            os.close(slave_fd)

        loop = asyncio.get_event_loop()
        self.read_task = loop.create_task(self._reader_loop())

    async def _reader_loop(self):
        loop = asyncio.get_event_loop()
        while self.is_running and self.master_fd is not None:
            try:
                await loop.run_in_executor(None, self._wait_read, 0.05)
                try:
                    data = os.read(self.master_fd, 4096)
                    if not data:
                        break
                    decoded = data.decode("utf-8", errors="replace")
                    self.history.append(decoded)
                    await self._broadcast(decoded)
                except (BlockingIOError, InterruptedError):
                    await asyncio.sleep(0.02)
                except OSError:
                    break
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.debug("PTY reader loop error [%s]: %s", self.session_id, e)
                await asyncio.sleep(0.05)

        self.is_running = False

    def _wait_read(self, timeout: float):
        import select
        if self.master_fd is not None:
            try:
                r, _, _ = select.select([self.master_fd], [], [], timeout)
                return bool(r)
            except Exception:
                return False
        return False

    async def _broadcast(self, text: str):
        dead_conns = []
        for ws in self.subscribers:
            try:
                await ws.send_json({"type": "output", "data": text})
            except Exception as e:
                log.debug("WS broadcast dead conn: %s", e)
                dead_conns.append(ws)
        for d in dead_conns:
            if d in self.subscribers:
                self.subscribers.remove(d)

    def write(self, text: str):
        if self.master_fd is not None and self.is_running:
            try:
                os.write(self.master_fd, text.encode("utf-8"))
            except Exception as e:
                log.warning("PTY write failed [%s]: %s", self.session_id, e)

    def resize(self, rows: int, cols: int):
        if self.master_fd is not None and self.is_running:
            try:
                winsize = struct.pack("HHHH", rows, cols, 0, 0)
                fcntl.ioctl(self.master_fd, termios.TIOCSWINSZ, winsize)
            except Exception as e:
                log.debug("PTY resize failed [%s]: %s", self.session_id, e)

    def stop(self):
        self.is_running = False
        if self.read_task:
            self.read_task.cancel()
        if self.proc:
            try:
                self.proc.terminate()
                self.proc.wait(timeout=1.0)
            except Exception:
                try:
                    self.proc.kill()
                except Exception as e:
                    log.debug("PTY kill failed [%s]: %s", self.session_id, e)
        if self.master_fd is not None:
            try:
                os.close(self.master_fd)
            except Exception:
                pass
            self.master_fd = None
        log.info("PTY stopped: session=%s", self.session_id)


class SessionManager:
    def __init__(self):
        self.sessions: Dict[str, PTYSession] = {}

    def get_command_for_agent(self, agent_id: str) -> List[str]:
        """
        Registry-driven command resolution.
        Reads AGENT_REGISTRY.json → discovers binary → returns command list.
        Falls back to /usr/bin/bash for unknown agents.
        """
        # Special cases that need extra args and aren't pure CLI binaries
        HARNESS_AGENTS = {"deepseek", "openclaw"}
        if agent_id in HARNESS_AGENTS:
            return ["python3", "-m", f"backend.{agent_id}_harness"]

        cmd = cfg.resolve_agent_command(agent_id)
        log.debug("Resolved command for agent '%s': %s", agent_id, cmd)
        return cmd

    def get_or_create_session(self, agent_id: str) -> PTYSession:
        if agent_id not in self.sessions or not self.sessions[agent_id].is_running:
            cmd = self.get_command_for_agent(agent_id)
            session = PTYSession(session_id=agent_id, command=cmd)
            session.start()
            self.sessions[agent_id] = session
        return self.sessions[agent_id]

    def restart_session(self, agent_id: str) -> PTYSession:
        if agent_id in self.sessions:
            self.sessions[agent_id].stop()
        cmd = self.get_command_for_agent(agent_id)
        session = PTYSession(session_id=agent_id, command=cmd)
        session.start()
        self.sessions[agent_id] = session
        return session

    def stop_session(self, agent_id: str):
        if agent_id in self.sessions:
            self.sessions[agent_id].stop()
            del self.sessions[agent_id]


manager = SessionManager()
