import React, { useState, useEffect } from 'react';
import { AgentTab } from './AgentTab';
import { useOS } from '../lib/store';
import {
  Terminal,
  Cpu,
  RefreshCw,
  Play,
  Layers,
  Sparkles,
  Command,
  ChevronRight,
  Shield,
  Bot
} from 'lucide-react';

interface AgentInfo {
  id: string;
  name: string;
  description: string;
  command: string;
  category: string;
  model: string;
  fallbackModel?: string;
  installed: boolean;
}

const DEFAULT_AGENTS: AgentInfo[] = [
  {
    id: 'hermes',
    name: 'Hermes (agies)',
    description: 'Hermes 2026 AI Agent profile with 18 skills, 20 tools, and unified memory',
    command: '/home/adarshjii/.local/bin/hermes chat --profile agies',
    category: 'Autonomous OS Agent',
    model: 'anthropic/claude-3-7-sonnet',
    fallbackModel: 'openai/gpt-4o',
    installed: true,
  },
  {
    id: 'claude',
    name: 'Claude Code',
    description: 'Anthropic Claude Code CLI with tool execution and code editing',
    command: 'claude',
    category: 'Frontier Coding Agent',
    model: 'anthropic/claude-3-7-sonnet',
    fallbackModel: 'deepseek/deepseek-r1',
    installed: true,
  },
  {
    id: 'codex',
    name: 'Codex CLI',
    description: 'OpenAI Codex specialized code generation and refactoring engine',
    command: 'codex',
    category: 'Code Synthesizer',
    model: 'openai/o3-mini',
    fallbackModel: 'anthropic/claude-3-5-sonnet',
    installed: true,
  },
  {
    id: 'deepseek',
    name: 'DeepSeek R1',
    description: 'DeepSeek R1 full reasoning CLI harness over 9Router with thinking tokens',
    command: 'deepseek-harness',
    category: 'Deep Reasoning Agent',
    model: 'deepseek/deepseek-r1',
    fallbackModel: 'openai/o3-mini',
    installed: true,
  },
  {
    id: 'openclaw',
    name: 'OpenClaw',
    description: 'OpenClaw Autonomous Agent harness wired with 9Router model matrix',
    command: 'openclaw-harness',
    category: 'Autonomous Framework',
    model: 'anthropic/claude-3-5-sonnet',
    fallbackModel: 'meta-llama/llama-3.3-70b-instruct',
    installed: true,
  },
  {
    id: 'opencode',
    name: 'OpenCode CLI',
    description: 'OpenCode autonomous agent TUI, ACP server, and MCP client',
    command: '/home/adarshjii/.opencode/bin/opencode',
    category: 'Agent Client Protocol (ACP)',
    model: 'opencode/frontier',
    installed: true,
  },
  {
    id: 'bash',
    name: 'Host Shell (Bash)',
    description: 'Interactive Linux PTY shell running in workspace directory',
    command: '/usr/bin/bash',
    category: 'System Shell',
    model: 'System CLI',
    installed: true,
  },
];

export const AgentTabs: React.FC = () => {
  const { activeAgentTab, setActiveAgentTab } = useOS();
  const [agents, setAgents] = useState<AgentInfo[]>(DEFAULT_AGENTS);
  const [agentStatuses, setAgentStatuses] = useState<Record<string, { status: string; pid?: number }>>({});
  const [loading, setLoading] = useState(false);

  // Fetch agent status from backend
  const refreshAgentStatuses = async () => {
    try {
      setLoading(true);
      const res = await fetch('/api/agents');
      if (res.ok) {
        const data = await res.json();
        if (data.agents && Array.isArray(data.agents)) {
          // Merge with defaults
          const merged = DEFAULT_AGENTS.map((def) => {
            const remote = data.agents.find((a: any) => a.id === def.id);
            return remote ? { ...def, ...remote } : def;
          });
          setAgents(merged);
        }
        if (data.statuses) {
          setAgentStatuses(data.statuses);
        }
      }
    } catch (err) {
      console.error('Failed to load agent statuses', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refreshAgentStatuses();
    const interval = setInterval(refreshAgentStatuses, 15000);
    return () => clearInterval(interval);
  }, []);

  const activeAgent = agents.find((a) => a.id === activeAgentTab) || agents[0];

  return (
    <div className="flex flex-col h-full w-full bg-[#0a0a0d] text-neutral-200 overflow-hidden select-none">
      {/* Multiplexer Top Bar */}
      <div className="flex items-center justify-between border-b border-white/10 px-3 py-2 bg-neutral-950/80 backdrop-blur-md">
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-white/5 border border-white/10 text-xs font-semibold text-emerald-400">
            <Terminal className="w-3.5 h-3.5" />
            <span>AEGIS CLI MULTIPLEXER</span>
          </div>
          <span className="text-[11px] text-neutral-500 hidden md:inline">
            Interactive Web PTY Sessions for all installed and bridged agents
          </span>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={refreshAgentStatuses}
            disabled={loading}
            className="flex items-center gap-1.5 px-2 py-1 rounded text-xs bg-white/5 hover:bg-white/10 border border-white/5 text-neutral-400 hover:text-white transition-colors"
          >
            <RefreshCw className={`w-3 h-3 ${loading ? 'animate-spin text-emerald-400' : ''}`} />
            <span>Sync</span>
          </button>
        </div>
      </div>

      {/* Agent Tabs Bar */}
      <div className="flex items-center gap-1.5 px-2 pt-2 bg-neutral-900/60 border-b border-white/5 overflow-x-auto scrollbar-none">
        {agents.map((agent) => {
          const isSelected = activeAgentTab === agent.id;
          const status = agentStatuses[agent.id]?.status || 'idle';
          const isRunning = status === 'running';

          return (
            <button
              key={agent.id}
              onClick={() => setActiveAgentTab(agent.id)}
              className={`flex items-center gap-2 px-3 py-2 rounded-t-md text-xs transition-all border-t border-x relative ${
                isSelected
                  ? 'bg-[#0a0a0d] border-white/15 text-white font-medium shadow-[0_-2px_10px_rgba(0,0,0,0.5)]'
                  : 'bg-black/40 border-transparent text-neutral-400 hover:text-neutral-200 hover:bg-white/5'
              }`}
            >
              <span
                className={`w-2 h-2 rounded-full ${
                  isRunning
                    ? 'bg-emerald-400 shadow-[0_0_6px_rgba(74,222,128,0.6)]'
                    : 'bg-neutral-600'
                }`}
              />
              <span className="font-mono">{agent.name}</span>

              {agent.category && (
                <span className="text-[10px] text-neutral-500 font-sans hidden lg:inline">
                  [{agent.category.split(' ')[0]}]
                </span>
              )}

              {isSelected && (
                <div className="absolute -bottom-px left-0 right-0 h-0.5 bg-emerald-400" />
              )}
            </button>
          );
        })}
      </div>

      {/* Agent Info Strip */}
      <div className="flex items-center justify-between px-3 py-1.5 bg-black/40 border-b border-white/5 text-[11px] text-neutral-400">
        <div className="flex items-center gap-2 truncate">
          <Bot className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
          <span className="font-medium text-white">{activeAgent.name}:</span>
          <span className="truncate text-neutral-400">{activeAgent.description}</span>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <span className="text-[10px] text-neutral-500">Tier Model:</span>
          <span className="font-mono text-[10px] text-neutral-300 bg-white/5 px-1.5 py-0.5 rounded border border-white/5">
            {activeAgent.model}
          </span>
          {activeAgent.fallbackModel && (
            <>
              <span className="text-neutral-600">⇄</span>
              <span className="font-mono text-[10px] text-amber-400/90 bg-amber-500/10 px-1.5 py-0.5 rounded border border-amber-500/20" title="1-on-1 Fallback Model">
                {activeAgent.fallbackModel}
              </span>
            </>
          )}
        </div>
      </div>

      {/* Terminal Workspaces Container */}
      <div className="flex-1 w-full relative bg-[#0a0a0d] overflow-hidden p-2">
        {agents.map((agent) => (
          <AgentTab
            key={agent.id}
            agentId={agent.id}
            agentName={agent.name}
            description={agent.description}
            command={agent.command}
            model={agent.model}
            fallbackModel={agent.fallbackModel}
            isActive={activeAgentTab === agent.id}
          />
        ))}
      </div>
    </div>
  );
};
