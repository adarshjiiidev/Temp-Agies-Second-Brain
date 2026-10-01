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

export const AgentTabs: React.FC = () => {
  const { activeAgentTab, setActiveAgentTab } = useOS();
  const [agents, setAgents] = useState<AgentInfo[]>([]);
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
          setAgents(data.agents.map((agent: any) => ({
            id: agent.id,
            name: agent.name || agent.id,
            description: agent.description || 'AEGIS capability',
            command: agent.command || agent.binary || '',
            category: agent.type || 'Capability',
            model: agent.default_model || 'AEGIS-selected',
            installed: agent.status === 'AVAILABLE',
          })));
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
  if (!activeAgent) {
    return <div className="h-full grid place-items-center bg-[#0a0a0d] text-sm text-neutral-500">No AEGIS agent capabilities are configured.</div>;
  }

  return (
    <div className="flex flex-col h-full w-full bg-[#0a0a0d] text-neutral-200 overflow-hidden select-none">
      {/* Multiplexer Top Bar */}
      <div className="flex items-center justify-between border-b border-white/10 px-3 py-2 bg-neutral-950/80 backdrop-blur-md">
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-white/5 border border-white/10 text-xs font-semibold text-amber-400">
            <Terminal className="w-3.5 h-3.5" />
            <span>AEGIS CAPABILITY CONSOLE</span>
          </div>
          <span className="text-[11px] text-neutral-500 hidden md:inline">
            Runtime-discovered internal capabilities; unavailable adapters are not launchable.
          </span>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={refreshAgentStatuses}
            disabled={loading}
            className="flex items-center gap-1.5 px-2 py-1 rounded text-xs bg-white/5 hover:bg-white/10 border border-white/5 text-neutral-400 hover:text-white transition-colors"
          >
            <RefreshCw className={`w-3 h-3 ${loading ? 'animate-spin text-amber-400' : ''}`} />
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
                    ? 'bg-amber-400 shadow-[0_0_6px_rgba(74,222,128,0.6)]'
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
                <div className="absolute -bottom-px left-0 right-0 h-0.5 bg-amber-400" />
              )}
            </button>
          );
        })}
      </div>

      {/* Agent Info Strip */}
      <div className="flex items-center justify-between px-3 py-1.5 bg-black/40 border-b border-white/5 text-[11px] text-neutral-400">
        <div className="flex items-center gap-2 truncate">
          <Bot className="w-3.5 h-3.5 text-amber-400 shrink-0" />
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
