import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Panel } from './Panel';
import { api, SystemGraphData, SystemGraphNode } from '../lib/api';
import { Network, RefreshCw, Loader2, CheckCircle2, XCircle, AlertCircle, Info } from 'lucide-react';

const NODE_COLORS: Record<string, string> = {
  core:       '#f59e0b', // amber
  executor:   '#38bdf8', // sky
  memory:     '#a78bfa', // violet
  skill:      '#34d399', // emerald
  ide:        '#f87171', // red
  capability: '#fb923c', // orange
};

const STATUS_DOT: Record<string, string> = {
  PASS:           'bg-emerald-400',
  NOT_CONFIGURED: 'bg-zinc-500',
  FAIL:           'bg-red-400',
  WARN:           'bg-yellow-400',
};

function NodeCard({ node, onClick, selected }: { node: SystemGraphNode; onClick: () => void; selected: boolean }) {
  const color = NODE_COLORS[node.type] ?? '#9ca3af';
  return (
    <div
      onClick={onClick}
      className={`relative flex flex-col gap-1 p-3 rounded-sm border cursor-pointer transition-all select-none ${
        selected
          ? 'border-amber-500/70 bg-amber-900/20 shadow-[0_0_16px_2px_rgba(245,158,11,0.12)]'
          : 'border-white/[0.07] bg-white/[0.03] hover:border-white/20 hover:bg-white/[0.06]'
      }`}
    >
      {/* Type indicator strip */}
      <div className="absolute left-0 top-2 bottom-2 w-0.5 rounded-full" style={{ background: color }} />

      <div className="flex items-center justify-between pl-2">
        <span className="text-xs font-semibold text-white truncate" style={{ color }}>{node.label}</span>
        <span className={`w-2 h-2 rounded-full shrink-0 ${STATUS_DOT[node.status] ?? 'bg-zinc-600'}`} title={node.status} />
      </div>

      <div className="flex items-center gap-1.5 pl-2">
        <span className="text-[10px] text-zinc-500 uppercase tracking-wider border border-white/10 px-1 rounded-xs">{node.type}</span>
        {node.implementation && (
          <span className="text-[10px] text-zinc-600 truncate">{node.implementation}</span>
        )}
      </div>

      {node.description && (
        <p className="pl-2 text-[11px] text-zinc-500 leading-tight truncate">{node.description}</p>
      )}
    </div>
  );
}

export const SystemGraphPanel: React.FC = () => {
  const [data, setData] = useState<SystemGraphData | null>(null);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<SystemGraphNode | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    api.getSystemGraph()
      .then(d => { setData(d); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  useEffect(() => { load(); }, [load]);

  const typeGroups = data
    ? (['core', 'memory', 'executor', 'skill', 'capability', 'ide'] as const).map(type => ({
        type,
        nodes: data.nodes.filter(n => n.type === type),
      })).filter(g => g.nodes.length > 0)
    : [];

  const TYPE_LABELS: Record<string, string> = {
    core: 'AEGIS Core Systems',
    memory: 'Memory & Knowledge',
    executor: 'Execution Backends',
    skill: 'Skill Registries',
    capability: 'Capabilities',
    ide: 'AI IDEs & Agents',
  };

  const passCount = data?.nodes.filter(n => n.status === 'PASS').length ?? 0;
  const totalCount = data?.nodes.length ?? 0;

  // Edges for selected node
  const connectedNodeIds = selected && data
    ? new Set(
        data.edges
          .filter(e => e.source === selected.id || e.target === selected.id)
          .flatMap(e => [e.source, e.target])
      )
    : new Set<string>();

  const outgoing = selected && data
    ? data.edges.filter(e => e.source === selected.id)
    : [];
  const incoming = selected && data
    ? data.edges.filter(e => e.target === selected.id)
    : [];

  return (
    <Panel
      id="system"
      title="AEGIS System Graph"
      icon={<Network className="w-3.5 h-3.5 text-amber-400" />}
      tag={`${passCount}/${totalCount} active`}
    >
      <div className="flex-1 flex flex-col h-full overflow-hidden bg-[#0e0e11] font-mono text-xs">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-2 border-b border-white/5 bg-white/[0.02] shrink-0">
          <span className="text-zinc-500 text-[11px]">
            One core. Many internal capabilities. Click a node to inspect.
          </span>
          <button onClick={load} className="p-1.5 text-zinc-500 hover:text-amber-400 hover:bg-white/5 rounded-xs transition-all">
            <RefreshCw className="w-3 h-3" />
          </button>
        </div>

        <div className="flex-1 flex overflow-hidden">
          {/* Main grid */}
          <div className="flex-1 overflow-y-auto p-4">
            {loading ? (
              <div className="flex items-center justify-center h-40 text-zinc-600">
                <Loader2 className="w-5 h-5 animate-spin mr-2" /> Mapping system...
              </div>
            ) : !data ? (
              <div className="flex items-center justify-center h-40 text-zinc-600">Failed to load system graph</div>
            ) : (
              <div className="space-y-5">
                {typeGroups.map(group => (
                  <div key={group.type}>
                    <div className="flex items-center gap-2 mb-2">
                      <div className="h-px flex-1 bg-white/[0.04]" />
                      <span
                        className="text-[10px] uppercase tracking-widest font-semibold px-2"
                        style={{ color: NODE_COLORS[group.type] }}
                      >
                        {TYPE_LABELS[group.type] ?? group.type}
                      </span>
                      <div className="h-px flex-1 bg-white/[0.04]" />
                    </div>
                    <div className="grid grid-cols-2 lg:grid-cols-3 gap-2">
                      {group.nodes.map(node => (
                        <NodeCard
                          key={node.id}
                          node={node}
                          onClick={() => setSelected(prev => prev?.id === node.id ? null : node)}
                          selected={selected?.id === node.id}
                        />
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Detail sidebar */}
          {selected && (
            <div className="w-64 shrink-0 border-l border-white/[0.06] bg-[#0d0d10] overflow-y-auto p-4 space-y-4">
              <div>
                <div className="text-[10px] text-zinc-600 uppercase tracking-wider mb-1">Selected Node</div>
                <div className="font-semibold text-sm" style={{ color: NODE_COLORS[selected.type] }}>
                  {selected.label}
                </div>
                <div className="text-zinc-500 text-[11px] mt-1">{selected.description}</div>
              </div>

              <div className="space-y-1">
                <Row label="Type" value={selected.type} />
                <Row label="Status" value={selected.status} valueClass={
                  selected.status === 'PASS' ? 'text-emerald-400' :
                  selected.status === 'NOT_CONFIGURED' ? 'text-zinc-500' : 'text-red-400'
                } />
                {selected.implementation && <Row label="Impl" value={selected.implementation} />}
              </div>

              {outgoing.length > 0 && (
                <div>
                  <div className="text-[10px] text-zinc-600 uppercase tracking-wider mb-1.5">Sends to</div>
                  {outgoing.map((e, i) => (
                    <div key={i} className="flex items-center gap-1.5 text-[11px] text-zinc-400 mb-1">
                      <div className="w-1.5 h-1.5 rounded-full bg-amber-500" />
                      <span>{data?.nodes.find(n => n.id === e.target)?.label ?? e.target}</span>
                      {e.label && <span className="text-zinc-600">({e.label})</span>}
                    </div>
                  ))}
                </div>
              )}

              {incoming.length > 0 && (
                <div>
                  <div className="text-[10px] text-zinc-600 uppercase tracking-wider mb-1.5">Receives from</div>
                  {incoming.map((e, i) => (
                    <div key={i} className="flex items-center gap-1.5 text-[11px] text-zinc-400 mb-1">
                      <div className="w-1.5 h-1.5 rounded-full bg-violet-500" />
                      <span>{data?.nodes.find(n => n.id === e.source)?.label ?? e.source}</span>
                      {e.label && <span className="text-zinc-600">({e.label})</span>}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Legend */}
        <div className="flex items-center gap-4 px-4 py-2 border-t border-white/[0.04] bg-white/[0.01] shrink-0 overflow-x-auto">
          {Object.entries(NODE_COLORS).map(([type, color]) => (
            <div key={type} className="flex items-center gap-1.5 shrink-0">
              <div className="w-2 h-2 rounded-full" style={{ background: color }} />
              <span className="text-[10px] text-zinc-600 capitalize">{type}</span>
            </div>
          ))}
          <div className="ml-auto flex items-center gap-3 shrink-0">
            <div className="flex items-center gap-1"><div className="w-2 h-2 rounded-full bg-emerald-400" /><span className="text-[10px] text-zinc-600">Active</span></div>
            <div className="flex items-center gap-1"><div className="w-2 h-2 rounded-full bg-zinc-500" /><span className="text-[10px] text-zinc-600">Not Configured</span></div>
          </div>
        </div>
      </div>
    </Panel>
  );
};

function Row({ label, value, valueClass = 'text-zinc-300' }: { label: string; value: string; valueClass?: string }) {
  return (
    <div className="flex items-center justify-between gap-2">
      <span className="text-[11px] text-zinc-600">{label}</span>
      <span className={`text-[11px] truncate ${valueClass}`}>{value}</span>
    </div>
  );
}
