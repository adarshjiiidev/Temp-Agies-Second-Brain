import React, { useState, useEffect } from 'react';
import { Panel } from './Panel';
import { api, ModelRegistryData, CuratedModel } from '../lib/api';
import { useOS } from '../lib/store';
import {
  Boxes,
  Search,
  CheckCircle,
  Eye,
  Wrench,
  BrainCircuit,
  ExternalLink,
  Cpu,
  Layers,
} from 'lucide-react';

export const ModelsPanel: React.FC = () => {
  const { routerHealth, openAgentTab } = useOS();
  const [modelData, setModelData] = useState<ModelRegistryData | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'tiers' | 'routing' | 'curated' | 'gateway'>('tiers');
  const [searchQuery, setSearchQuery] = useState('');

  useEffect(() => {
    api.getModels().then((data) => {
      setModelData(data);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  const routingTable = modelData?.routing_table || {};
  const curatedModels = modelData?.curated_models || {};
  const tieredGroups = modelData?.tiered_groups || {};
  const is9RouterOk = routerHealth?.status === 'running';

  const filteredCurated = Object.entries(curatedModels).filter(([id, model]) => {
    return (
      !searchQuery ||
      id.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (model.role && model.role.toLowerCase().includes(searchQuery.toLowerCase())) ||
      (model.notes && model.notes.toLowerCase().includes(searchQuery.toLowerCase()))
    );
  });

  return (
    <Panel
      id="models"
      title="Model Routing & 9Router"
      icon={<Boxes className="w-3.5 h-3.5 text-[#a78bfa]" />}
      tag={is9RouterOk ? '9Router: Online' : '9Router: Offline'}
    >
      <div className="flex-1 flex flex-col h-full overflow-hidden bg-[#0e0e11] font-mono text-xs">
        {/* Navigation Tabs Header */}
        <div className="h-8 px-3 border-b border-white/5 bg-white/[0.02] flex items-center justify-between shrink-0 select-none">
          <div className="flex items-center space-x-1">
            {[
              { id: 'tiers', label: 'Tiers & 1:1 Fallbacks' },
              { id: 'routing', label: 'Task Routing Table' },
              { id: 'curated', label: 'Curated Models' },
              { id: 'gateway', label: '9Router Gateway' },
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as any)}
                className={`px-2.5 py-1 uppercase tracking-wider text-[10px] transition-os ${
                  activeTab === tab.id
                    ? 'bg-white/10 text-white font-medium border border-white/15'
                    : 'text-zinc-400 hover:text-white hover:bg-white/5 border border-transparent'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          <div className="flex items-center space-x-2 text-[11px]">
            <span
              className={`w-2 h-2 rounded-full ${
                is9RouterOk ? 'bg-emerald-400 animate-pulse-live' : 'bg-red-400'
              }`}
            />
            <span className="text-zinc-400">
              860 models exposed
            </span>
          </div>
        </div>

        {/* Tab: Capability Tiers & 1:1 Fallbacks */}
        {activeTab === 'tiers' && (
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            <div className="glass-panel p-3 rounded-sm space-y-2 border border-emerald-500/20 bg-emerald-500/[0.03]">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-emerald-400">
                  AEGIS Autonomous Orchestrator Model Matrix
                </span>
                <span className="text-[10px] bg-emerald-500/20 text-emerald-300 px-2 py-0.5 rounded border border-emerald-500/30">
                  1-on-1 Fallback Enabled
                </span>
              </div>
              <p className="text-[11px] text-zinc-400 leading-relaxed">
                Every incoming user task is classified by the orchestrator based on complexity, domain, and latency budget, then dispatched to the primary model with guaranteed instant failover to its 1:1 fallback model.
              </p>
            </div>

            <div className="space-y-3">
              {Object.entries(tieredGroups).length > 0 ? (
                Object.entries(tieredGroups).map(([key, tier]) => (
                  <div key={key} className="glass-panel p-3.5 rounded-sm border border-white/10 hover:border-white/20 transition-os space-y-2.5">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className="font-semibold text-white text-xs">{tier.name}</span>
                        {tier.context_window && (
                          <span className="text-[10px] text-neutral-500 font-mono">
                            ({Math.round(tier.context_window / 1000)}k ctx)
                          </span>
                        )}
                      </div>
                      <button
                        onClick={() => openAgentTab(tier.target_agent)}
                        className="text-[10px] flex items-center gap-1 px-2 py-0.5 rounded bg-white/5 hover:bg-emerald-500/20 text-neutral-300 hover:text-emerald-300 border border-white/10 transition-colors font-mono"
                      >
                        <span>Open {tier.target_agent.toUpperCase()} CLI →</span>
                      </button>
                    </div>

                    <p className="text-[11px] text-zinc-400">{tier.description}</p>

                    {/* 1:1 Pair Grid */}
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 pt-1">
                      <div className="flex items-center justify-between p-2 rounded bg-black/40 border border-emerald-500/20 text-xs">
                        <span className="text-[10px] text-emerald-400 uppercase font-semibold">Primary:</span>
                        <span className="font-mono text-white text-[11px] truncate max-w-[200px]" title={tier.primary}>
                          {tier.primary}
                        </span>
                      </div>

                      <div className="flex items-center justify-between p-2 rounded bg-black/40 border border-amber-500/20 text-xs">
                        <span className="text-[10px] text-amber-400 uppercase font-semibold">1:1 Fallback:</span>
                        <span className="font-mono text-amber-200 text-[11px] truncate max-w-[200px]" title={tier.fallback}>
                          {tier.fallback}
                        </span>
                      </div>
                    </div>
                  </div>
                ))
              ) : (
                <div className="text-center py-8 text-zinc-500 text-xs">
                  Loading tiered model groups from MODEL_REGISTRY...
                </div>
              )}
            </div>
          </div>
        )}

        {/* Tab 1: Task Routing Table */}
        {activeTab === 'routing' && (
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            <div className="glass-panel p-3 rounded-sm space-y-2">
              <div className="text-xs font-semibold text-white">
                AEGIS Task-Based Dynamic LLM Router
              </div>
              <p className="text-[11px] text-zinc-400 leading-relaxed">
                Requests are automatically matched against specialized models based on reasoning depth, code synthesis capabilities, and latency requirements.
              </p>
            </div>

            <div className="glass-panel rounded-sm overflow-hidden">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-white/10 bg-white/[0.02] text-zinc-400 text-[11px]">
                    <th className="p-3">TASK DOMAIN</th>
                    <th className="p-3">PRIMARY ROUTED MODEL</th>
                    <th className="p-3">SOURCE GATEWAY</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5">
                  {Object.entries(routingTable).map(([task, modelId]) => (
                    <tr key={task} className="hover:bg-white/[0.02] transition-os">
                      <td className="p-3 font-semibold uppercase text-zinc-300 text-[11px]">
                        {task.replace('_', ' ')}
                      </td>
                      <td className="p-3 font-mono text-emerald-400">
                        {modelId || 'None'}
                      </td>
                      <td className="p-3 text-zinc-500 text-[11px]">
                        {modelId?.startsWith('cl/') ? 'Codex Proxy' : modelId?.startsWith('ag/') ? 'Antigravity Direct' : '9Router'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Tab 2: Curated Models Grid */}
        {activeTab === 'curated' && (
          <div className="flex-1 flex flex-col h-full overflow-hidden">
            <div className="p-3 border-b border-white/5 flex items-center justify-between shrink-0">
              <div className="relative w-full sm:w-64">
                <Search className="w-3 h-3 text-zinc-400 absolute left-2.5 top-2.5" />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Search models..."
                  className="w-full h-8 pl-8 pr-3 bg-white/5 border border-white/10 focus:border-white/20 text-white text-xs outline-none placeholder-zinc-500 rounded-xs"
                />
              </div>
              <span className="text-[11px] text-zinc-500">
                Showing {filteredCurated.length} of {Object.keys(curatedModels).length} curated models
              </span>
            </div>

            <div className="flex-1 overflow-y-auto p-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {filteredCurated.map(([id, m]) => (
                  <div key={id} className="glass-panel p-3.5 rounded-sm space-y-2 hover:border-white/20 transition-os">
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-white text-xs truncate max-w-[70%]">
                        {id}
                      </span>
                      {m.role && (
                        <span className="text-[10px] uppercase px-1.5 py-0.2 bg-white/5 border border-white/10 text-emerald-400">
                          {m.role}
                        </span>
                      )}
                    </div>

                    <p className="text-[11px] text-zinc-300 line-clamp-2">
                      {m.notes || 'Curated high-performance foundation model'}
                    </p>

                    {/* Capabilities Badges */}
                    <div className="flex items-center space-x-1.5 pt-1">
                      {m.reasoning && (
                        <span className="text-[10px] px-1.5 py-0.5 bg-purple-500/10 border border-purple-500/30 text-purple-300 flex items-center space-x-1">
                          <BrainCircuit className="w-2.5 h-2.5" />
                          <span>Reasoning</span>
                        </span>
                      )}
                      {m.tools && (
                        <span className="text-[10px] px-1.5 py-0.5 bg-blue-500/10 border border-blue-500/30 text-blue-300 flex items-center space-x-1">
                          <Wrench className="w-2.5 h-2.5" />
                          <span>Tools</span>
                        </span>
                      )}
                      {m.vision && (
                        <span className="text-[10px] px-1.5 py-0.5 bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 flex items-center space-x-1">
                          <Eye className="w-2.5 h-2.5" />
                          <span>Vision</span>
                        </span>
                      )}
                    </div>

                    <div className="flex items-center justify-between pt-2 border-t border-white/5 text-[10px] text-zinc-500">
                      <span>Context: {m.context_window ? `${Math.round(m.context_window / 1000)}k` : 'N/A'}</span>
                      <span>Max Out: {m.max_output ? `${Math.round(m.max_output / 1000)}k` : 'N/A'}</span>
                      <span className="text-zinc-400">{m.source || '9Router'}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Tab 3: 9Router Gateway Status */}
        {activeTab === 'gateway' && (
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            <div className="glass-panel p-4 rounded-sm space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2 text-sm font-semibold text-white">
                  <Cpu className="w-4 h-4 text-emerald-400" />
                  <span>9Router Local AI Proxy Daemon</span>
                </div>
                <span
                  className={`text-[11px] px-2 py-0.5 uppercase tracking-wider font-semibold border ${
                    is9RouterOk
                      ? 'bg-emerald-400/10 border-emerald-400/30 text-emerald-400'
                      : 'bg-red-400/10 border-red-400/30 text-red-400'
                  }`}
                >
                  {is9RouterOk ? 'Operational' : 'Stopped / Standby'}
                </span>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs text-zinc-300 pt-2">
                <div>
                  <span className="text-zinc-500">Gateway URL: </span>
                  <span className="text-white">http://127.0.0.1:20128/v1</span>
                </div>
                <div>
                  <span className="text-zinc-500">Total Registered Models: </span>
                  <span className="text-white">{modelData?.total_available || 860} models</span>
                </div>
                <div>
                  <span className="text-zinc-500">Hermes Default Model: </span>
                  <span className="text-emerald-400">
                    {modelData?.hermes_default?.model || 'upstage/solar-pro4:free'}
                  </span>
                </div>
                <div>
                  <span className="text-zinc-500">Hermes Base URL: </span>
                  <span className="text-white truncate">
                    {modelData?.hermes_default?.base_url || 'https://inference-api.nousresearch.com/v1'}
                  </span>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </Panel>
  );
};
