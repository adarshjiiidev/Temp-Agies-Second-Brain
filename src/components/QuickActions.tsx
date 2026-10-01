import React, { useState } from 'react';
import { useOS } from '../lib/store';
import { api } from '../lib/api';
import {
  Zap,
  Camera,
  Bot,
  Brain,
  X,
  Play,
  CheckCircle,
  AlertTriangle,
  Terminal,
  Loader2,
  Sparkles,
  Rocket,
  Layers,
  BookOpen,
  FlaskConical,
  Palette,
} from 'lucide-react';

export const QuickActions: React.FC = () => {
  const { isQuickActionsOpen, setQuickActionsOpen, runningScript, executeScript, scriptLogs } = useOS();
  const [selectedScript, setSelectedScript] = useState<string>('aegis-snapshot.sh');
  const [actionOut, setActionOut] = useState<Record<string, string>>({});
  const [runningAction, setRunningAction] = useState<string | null>(null);

  if (!isQuickActionsOpen) return null;

  const actions = [
    {
      id: 'aegis-snapshot.sh',
      name: 'Snapshot PC',
      desc: 'Capture full hardware state, processes, and network info into daily log',
      icon: <Camera className="w-4 h-4 text-amber-400" />,
    },
    {
      id: 'aegis-ingest-chatgpt.sh',
      name: 'Ingest ChatGPT',
      desc: 'Sync recent conversations and learnings into Obsidian PARA structure',
      icon: <Bot className="w-4 h-4 text-sky-400" />,
    },
    {
      id: 'aegis-learn-patterns.sh',
      name: 'Learn Patterns',
      desc: 'Analyze memory logs for recurring development insights and update skills',
      icon: <Brain className="w-4 h-4 text-purple-400" />,
    },
    {
      id: 'aegis-ingest-chats.sh',
      name: 'Ingest All Chats',
      desc: 'Read all IDE & CLI chats (Antigravity, Claude, Codex, OpenCode) into Obsidian',
      icon: <Terminal className="w-4 h-4 text-orange-400" />,
    },
    {
      id: 'aegis-ai-ingest.sh',
      name: 'AI Ingest All',
      desc: 'LLM summarizes every chat → key decisions, lessons learned, action items into Obsidian',
      icon: <Sparkles className="w-4 h-4 text-violet-400" />,
    },
  ];

  const activeLog = scriptLogs[selectedScript];
  const activeActionOut = actionOut[selectedScript];

  const handleRun = async (scriptName: string) => {
    setSelectedScript(scriptName);
    await executeScript(scriptName);
  };

  const runAction = async (id: string, fn: () => Promise<unknown>) => {
    setSelectedScript(id);
    setRunningAction(id);
    setActionOut((p) => ({ ...p, [id]: 'Running...' }));
    try {
      const r = await fn();
      setActionOut((p) => ({ ...p, [id]: JSON.stringify(r, null, 1).slice(0, 4000) }));
    } catch (e) {
      setActionOut((p) => ({ ...p, [id]: `FAILED: ${e instanceof Error ? e.message : String(e)}` }));
    } finally {
      setRunningAction(null);
    }
  };

  const agiesActions = [
    {
      id: 'spatial-dry',
      name: 'Spatial Sweep (plan)',
      desc: 'One-by-one lane plan over all projects — executes nothing',
      icon: <Layers className="w-4 h-4 text-orange-400" />,
      fn: () => api.spatialSweep(undefined, '', true),
    },
    {
      id: 'ingest-run',
      name: 'Auto-Read Chats',
      desc: 'Universal ingest: latest agent sessions → Obsidian + mem0',
      icon: <BookOpen className="w-4 h-4 text-amber-400" />,
      fn: () => api.ingestRun(3),
    },
    {
      id: 'learn-run',
      name: 'Auto-Research',
      desc: 'One bounded learn-loop pass → note + mem0 + TurboQuant',
      icon: <FlaskConical className="w-4 h-4 text-violet-400" />,
      fn: () => api.learnRun(),
    },
    {
      id: 'frontier-status',
      name: 'Frontier Status',
      desc: 'Runtime, runs, traces — AEGIS execution backend health',
      icon: <Rocket className="w-4 h-4 text-orange-400" />,
      fn: async () => ({ status: await api.frontierStatus(), runs: (await api.frontierRuns(5)).runs }),
    },
    {
      id: 'lab-check',
      name: 'Lab Guard Check',
      desc: 'Probe RESEARCH_LAB scope: localhost dry-run-harness',
      icon: <Terminal className="w-4 h-4 text-amber-400" />,
      fn: async () => ({ profile: await api.labProfile('RESEARCH_LAB'), check: await api.labCheck('localhost', 'dry-run-harness') }),
    },
    {
      id: 'prefs-view',
      name: 'Preferences',
      desc: 'User profile sections driving theme + agents',
      icon: <Palette className="w-4 h-4 text-pink-400" />,
      fn: () => api.getPreferences(),
    },
  ];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-md animate-in fade-in select-none">
      <div className="glass-panel-elevated w-full max-w-2xl max-h-[85vh] flex flex-col rounded-sm overflow-hidden border border-white/20 shadow-2xl font-mono text-xs">
        {/* Header */}
        <div className="p-3.5 border-b border-white/10 flex items-center justify-between bg-white/[0.02]">
          <div className="flex items-center space-x-2">
            <Zap className="w-4 h-4 text-amber-400" />
            <span className="font-semibold text-sm text-white">System Quick Actions & Scripts</span>
          </div>
          <button
            onClick={() => setQuickActionsOpen(false)}
            className="p-1 text-zinc-400 hover:text-white hover:bg-white/10 transition-os"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Scrollable card grids — scripts + AEGIS actions */}
        <div className="overflow-y-auto min-h-0 max-h-[38vh] sm:max-h-[44vh] overscroll-contain">
        {/* Script Selector Grid */}
        <div className="p-4 grid grid-cols-1 sm:grid-cols-3 gap-2.5 border-b border-white/10">
          {actions.map((act) => {
            const isRunning = runningScript === act.id;
            const log = scriptLogs[act.id];

            return (
              <div
                key={act.id}
                onClick={() => setSelectedScript(act.id)}
                className={`p-3 rounded-xs border transition-os flex flex-col justify-between cursor-pointer ${
                  selectedScript === act.id
                    ? 'bg-white/10 border-white/30 text-white'
                    : 'bg-white/5 border-white/5 text-zinc-400 hover:bg-white/[0.08] hover:text-zinc-200'
                }`}
              >
                <div className="space-y-1.5 mb-3">
                  <div className="flex items-center justify-between">
                    {act.icon}
                    {isRunning ? (
                      <Loader2 className="w-3.5 h-3.5 animate-spin text-amber-400" />
                    ) : log?.success ? (
                      <CheckCircle className="w-3.5 h-3.5 text-amber-400" />
                    ) : log && !log.success ? (
                      <AlertTriangle className="w-3.5 h-3.5 text-red-400" />
                    ) : null}
                  </div>
                  <div className="font-semibold text-xs text-white">{act.name}</div>
                  <div className="text-[10px] text-zinc-400 leading-tight">{act.desc}</div>
                </div>

                <button
                  disabled={isRunning}
                  onClick={(e) => {
                    e.stopPropagation();
                    handleRun(act.id);
                  }}
                  className={`w-full py-1 px-2 text-[10px] uppercase font-semibold flex items-center justify-center space-x-1 border transition-os ${
                    isRunning
                      ? 'bg-amber-500/20 text-amber-400 border-amber-500/30 cursor-wait'
                      : 'bg-white/10 hover:bg-white/20 text-white border-white/20'
                  }`}
                >
                  <Play className="w-2.5 h-2.5" />
                  <span>{isRunning ? 'Running...' : 'Execute'}</span>
                </button>
              </div>
            );
          })}
        </div>

        {/* AEGIS Action Grid */}
        <div className="px-4 pt-3 text-[10px] uppercase tracking-wider text-zinc-500 font-semibold">
          AEGIS Actions — spatial · auto-read · auto-research · frontier · lab · prefs
        </div>
        <div className="p-4 pt-2 grid grid-cols-1 sm:grid-cols-3 gap-2.5 border-b border-white/10">
          {agiesActions.map((act) => {
            const isRunning = runningAction === act.id;
            const out = actionOut[act.id];
            const failed = out?.startsWith('FAILED');
            return (
              <div
                key={act.id}
                onClick={() => setSelectedScript(act.id)}
                className={`p-3 rounded-xs border transition-os flex flex-col justify-between cursor-pointer ${
                  selectedScript === act.id
                    ? 'bg-white/10 border-white/30 text-white'
                    : 'bg-white/5 border-white/5 text-zinc-400 hover:bg-white/[0.08] hover:text-zinc-200'
                }`}
              >
                <div className="space-y-1.5 mb-3">
                  <div className="flex items-center justify-between">
                    {act.icon}
                    {isRunning ? (
                      <Loader2 className="w-3.5 h-3.5 animate-spin text-amber-400" />
                    ) : out && !failed ? (
                      <CheckCircle className="w-3.5 h-3.5 text-amber-400" />
                    ) : failed ? (
                      <AlertTriangle className="w-3.5 h-3.5 text-red-400" />
                    ) : null}
                  </div>
                  <div className="font-semibold text-xs text-white">{act.name}</div>
                  <div className="text-[10px] text-zinc-400 leading-tight">{act.desc}</div>
                </div>

                <button
                  disabled={isRunning}
                  onClick={(e) => {
                    e.stopPropagation();
                    runAction(act.id, act.fn);
                  }}
                  className={`w-full py-1 px-2 text-[10px] uppercase font-semibold flex items-center justify-center space-x-1 border transition-os ${
                    isRunning
                      ? 'bg-amber-500/20 text-amber-400 border-amber-500/30 cursor-wait'
                      : 'bg-white/10 hover:bg-white/20 text-white border-white/20'
                  }`}
                >
                  <Play className="w-2.5 h-2.5" />
                  <span>{isRunning ? 'Running...' : 'Execute'}</span>
                </button>
              </div>
            );
          })}
        </div>
        </div>

        {/* Live Terminal Output Viewer (pinned) */}
        <div className="flex-1 flex flex-col min-h-40 max-h-80 shrink-0 overflow-hidden bg-black/70 p-3 select-text">
          <div className="flex items-center justify-between text-[11px] text-zinc-400 pb-2 border-b border-white/10 mb-2">
            <div className="flex items-center space-x-1.5">
              <Terminal className="w-3 h-3 text-amber-400" />
              <span>TERMINAL OUTPUT: {selectedScript}</span>
            </div>
            {activeLog && !activeActionOut && (
              <span className={activeLog.success ? 'text-amber-400' : 'text-red-400'}>
                Exit Status: {activeLog.returncode}
              </span>
            )}
          </div>

          <pre className="flex-1 overflow-y-auto font-mono text-[11px] text-zinc-300 leading-relaxed whitespace-pre-wrap">
            {runningScript === selectedScript || runningAction === selectedScript ? (
              <span className="text-amber-400 animate-pulse">Running {selectedScript}... Waiting for process execution...</span>
            ) : activeActionOut ? (
              activeActionOut
            ) : activeLog ? (
              activeLog.stdout || activeLog.stderr || activeLog.error || 'Execution completed with empty output.'
            ) : (
              <span className="text-zinc-600">No output yet. Click 'Execute' to trigger script.</span>
            )}
          </pre>
        </div>
      </div>
    </div>
  );
};
