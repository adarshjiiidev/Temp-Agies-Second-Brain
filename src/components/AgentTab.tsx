import React, { useEffect, useRef, useState, useCallback } from 'react';
import { Terminal } from '@xterm/xterm';
import { FitAddon } from '@xterm/addon-fit';
import { Play, Square, RotateCcw, Trash2, Terminal as TermIcon, Shield, Cpu, Activity } from 'lucide-react';

interface AgentTabProps {
  agentId: string;
  agentName: string;
  description?: string;
  command?: string;
  model?: string;
  fallbackModel?: string;
  isActive: boolean;
}

export const AgentTab: React.FC<AgentTabProps> = ({
  agentId,
  agentName,
  description,
  command,
  model,
  fallbackModel,
  isActive,
}) => {
  const terminalRef = useRef<HTMLDivElement>(null);
  const termInstanceRef = useRef<Terminal | null>(null);
  const fitAddonRef = useRef<FitAddon | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  const [connectionStatus, setConnectionStatus] = useState<'connecting' | 'connected' | 'disconnected'>('disconnected');
  const [processStatus, setProcessStatus] = useState<string>('idle');
  const [pid, setPid] = useState<number | null>(null);

  // Initialize terminal and WebSocket
  useEffect(() => {
    if (!terminalRef.current) return;

    const term = new Terminal({
      cursorBlink: true,
      cursorStyle: 'block',
      fontFamily: "'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace",
      fontSize: 13,
      lineHeight: 1.35,
      scrollback: 5000,
      theme: {
        background: '#0a0a0d',
        foreground: '#e4e4e7',
        cursor: '#4ade80',
        cursorAccent: '#0a0a0d',
        selectionBackground: 'rgba(255, 255, 255, 0.22)',
        black: '#18181b',
        red: '#f87171',
        green: '#4ade80',
        yellow: '#fbbf24',
        blue: '#60a5fa',
        magenta: '#c084fc',
        cyan: '#38bdf8',
        white: '#f4f4f5',
        brightBlack: '#52525b',
        brightRed: '#ef4444',
        brightGreen: '#22c55e',
        brightYellow: '#eab308',
        brightBlue: '#3b82f6',
        brightMagenta: '#a855f7',
        brightCyan: '#06b6d4',
        brightWhite: '#ffffff',
      },
    });

    const fitAddon = new FitAddon();
    term.loadAddon(fitAddon);
    term.open(terminalRef.current);
    fitAddon.fit();

    termInstanceRef.current = term;
    fitAddonRef.current = fitAddon;

    // Connect WebSocket
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsHost = window.location.host;
    const wsUrl = `${protocol}//${wsHost}/ws/agent/${agentId}`;

    setConnectionStatus('connecting');
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      setConnectionStatus('connected');
      // Send initial terminal dimensions
      try {
        fitAddon.fit();
        ws.send(JSON.stringify({ type: 'resize', cols: term.cols, rows: term.rows }));
      } catch (err) {
        console.error('Failed to send initial resize', err);
      }
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === 'output' && msg.data) {
          term.write(msg.data);
        } else if (msg.type === 'status') {
          setProcessStatus(msg.status || 'running');
          if (msg.pid) setPid(msg.pid);
        }
      } catch {
        // Raw text output fallback
        term.write(event.data);
      }
    };

    ws.onerror = () => {
      setConnectionStatus('disconnected');
    };

    ws.onclose = () => {
      setConnectionStatus('disconnected');
    };

    // User input from terminal to backend PTY
    const onDataDisposable = term.onData((data) => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'input', data }));
      }
    });

    // Resize observer
    const resizeObserver = new ResizeObserver(() => {
      if (isActive && fitAddonRef.current && termInstanceRef.current) {
        try {
          fitAddonRef.current.fit();
          const { cols, rows } = termInstanceRef.current;
          if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
            wsRef.current.send(JSON.stringify({ type: 'resize', cols, rows }));
          }
        } catch {
          // Ignore resize errors when hidden
        }
      }
    });

    if (terminalRef.current) {
      resizeObserver.observe(terminalRef.current);
    }

    return () => {
      resizeObserver.disconnect();
      onDataDisposable.dispose();
      ws.close();
      term.dispose();
    };
  }, [agentId]);

  // Handle re-fit when tab becomes active
  useEffect(() => {
    if (isActive && fitAddonRef.current && termInstanceRef.current) {
      const timer = setTimeout(() => {
        try {
          fitAddonRef.current?.fit();
          const cols = termInstanceRef.current?.cols || 80;
          const rows = termInstanceRef.current?.rows || 24;
          if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
            wsRef.current.send(JSON.stringify({ type: 'resize', cols, rows }));
          }
        } catch (err) {
          console.error(err);
        }
      }, 50);
      return () => clearTimeout(timer);
    }
  }, [isActive]);

  const sendSpecialKey = (key: string) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'input', data: key }));
    }
  };

  const handleRestart = async () => {
    try {
      await fetch(`/api/agent/${agentId}/restart`, { method: 'POST' });
      termInstanceRef.current?.write('\r\n\x1b[33m>>> Restarting session...\x1b[0m\r\n');
    } catch (err) {
      console.error(err);
    }
  };

  const handleStop = async () => {
    try {
      await fetch(`/api/agent/${agentId}/stop`, { method: 'POST' });
      termInstanceRef.current?.write('\r\n\x1b[31m>>> Process stopped.\x1b[0m\r\n');
    } catch (err) {
      console.error(err);
    }
  };

  const handleClear = () => {
    termInstanceRef.current?.clear();
  };

  return (
    <div
      className={`flex flex-col h-full w-full bg-[#0a0a0d] border border-white/5 rounded-lg overflow-hidden ${
        isActive ? 'block' : 'hidden'
      }`}
    >
      {/* Tab Control Bar */}
      <div className="flex items-center justify-between px-3 py-2 bg-neutral-900/80 border-b border-white/10 text-xs backdrop-blur-sm">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5 font-medium text-neutral-200">
            <TermIcon className="w-3.5 h-3.5 text-amber-400" />
            <span>{agentName}</span>
          </div>

          {command && (
            <span className="hidden sm:inline-block font-mono text-[11px] text-neutral-500 truncate max-w-xs bg-black/40 px-2 py-0.5 rounded border border-white/5">
              {command}
            </span>
          )}

          {model && (
            <div className="flex items-center gap-1 bg-white/5 px-2 py-0.5 rounded text-[11px] text-neutral-400 border border-white/5">
              <Cpu className="w-3 h-3 text-orange-400" />
              <span className="truncate max-w-[140px]">{model}</span>
              {fallbackModel && (
                <span className="text-[10px] text-amber-400/80 ml-1" title={`1:1 Fallback: ${fallbackModel}`}>
                  ⇄ {fallbackModel.split('/').pop()?.slice(0, 10)}
                </span>
              )}
            </div>
          )}
        </div>

        {/* Process Indicators & Controls */}
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1.5 px-2 py-0.5 rounded text-[11px] bg-black/40 border border-white/5">
            <span
              className={`w-2 h-2 rounded-full ${
                connectionStatus === 'connected'
                  ? 'bg-amber-400 shadow-[0_0_8px_rgba(74,222,128,0.5)]'
                  : connectionStatus === 'connecting'
                  ? 'bg-amber-400 animate-pulse'
                  : 'bg-red-500'
              }`}
            />
            <span className="text-neutral-400 capitalize">{processStatus}</span>
            {pid && <span className="text-neutral-600 font-mono">#{pid}</span>}
          </div>

          <div className="flex items-center gap-1 bg-black/30 p-0.5 rounded border border-white/5">
            <button
              onClick={() => sendSpecialKey('\x03')}
              className="px-2 py-1 hover:bg-white/10 rounded text-neutral-400 hover:text-white transition-colors"
              title="Send Ctrl+C (Interrupt)"
            >
              ^C
            </button>
            <button
              onClick={handleRestart}
              className="p-1 hover:bg-white/10 rounded text-neutral-400 hover:text-amber-400 transition-colors"
              title="Restart Agent Process"
            >
              <RotateCcw className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={handleStop}
              className="p-1 hover:bg-white/10 rounded text-neutral-400 hover:text-red-400 transition-colors"
              title="Stop Agent Process"
            >
              <Square className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={handleClear}
              className="p-1 hover:bg-white/10 rounded text-neutral-400 hover:text-white transition-colors"
              title="Clear Terminal Display"
            >
              <Trash2 className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </div>

      {/* Terminal Viewport */}
      <div className="flex-1 w-full h-full p-2 relative bg-[#0a0a0d] overflow-hidden">
        <div ref={terminalRef} className="w-full h-full" />
      </div>

      {/* Quick Footer Shortcut Keys */}
      <div className="flex items-center justify-between px-3 py-1 bg-neutral-950/90 border-t border-white/5 text-[10px] text-neutral-500 font-mono">
        <div className="flex items-center gap-3">
          <span>PTY Stream Active</span>
          {description && <span className="text-neutral-600 hidden md:inline">{description}</span>}
        </div>
        <div className="flex items-center gap-2">
          <span>Esc/Enter ready</span>
          <button
            onClick={() => sendSpecialKey('\r')}
            className="hover:text-neutral-300 underline"
          >
            [Enter]
          </button>
          <button
            onClick={() => sendSpecialKey('\x1b')}
            className="hover:text-neutral-300 underline"
          >
            [Esc]
          </button>
        </div>
      </div>
    </div>
  );
};
