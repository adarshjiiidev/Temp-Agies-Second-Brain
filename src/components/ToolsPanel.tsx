import React, { useState, useEffect } from 'react';
import { Panel } from './Panel';
import { api, ToolRegistryData, ToolItem } from '../lib/api';
import {
  Wrench,
  Search,
  Shield,
  AlertTriangle,
  CheckCircle,
  ChevronRight,
  ChevronDown,
  Terminal,
} from 'lucide-react';

export const ToolsPanel: React.FC = () => {
  const [toolData, setToolData] = useState<ToolRegistryData | null>(null);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [expandedTool, setExpandedTool] = useState<string | null>(null);

  useEffect(() => {
    api.getTools().then((data) => {
      setToolData(data);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  const tools = toolData?.tools || {};
  const toolList = Object.entries(tools);

  const filteredTools = toolList.filter(([name, t]) => {
    return (
      !searchQuery ||
      name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (t.capability && t.capability.toLowerCase().includes(searchQuery.toLowerCase())) ||
      (t.identity && t.identity.toLowerCase().includes(searchQuery.toLowerCase()))
    );
  });

  return (
    <Panel
      id="tools"
      title="Agent Tools Registry"
      icon={<Wrench className="w-3.5 h-3.5 text-[#fbbf24]" />}
      tag={`${toolList.length} Tools`}
    >
      <div className="flex-1 flex flex-col h-full overflow-hidden bg-[#0e0e11] font-mono text-xs">
        {/* Search Bar */}
        <div className="p-3 border-b border-white/5 bg-white/[0.02] flex items-center justify-between shrink-0">
          <div className="relative w-full sm:w-64">
            <Search className="w-3 h-3 text-zinc-400 absolute left-2.5 top-2.5" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search tools..."
              className="w-full h-8 pl-8 pr-3 bg-white/5 border border-white/10 focus:border-white/20 text-white text-xs outline-none placeholder-zinc-500 rounded-xs"
            />
          </div>
          <span className="text-[11px] text-zinc-500">
            {filteredTools.length} of {toolList.length} tools operational
          </span>
        </div>

        {/* Tools Grid */}
        <div className="flex-1 overflow-y-auto p-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {filteredTools.map(([name, tool]) => {
              const isExpanded = expandedTool === name;
              const riskColor =
                tool.risk === 'high'
                  ? 'text-red-400 bg-red-400/10 border-red-400/30'
                  : tool.risk === 'medium'
                  ? 'text-amber-400 bg-amber-400/10 border-amber-400/30'
                  : 'text-amber-400 bg-amber-400/10 border-amber-400/30';

              return (
                <div
                  key={name}
                  className="glass-panel p-3.5 rounded-sm space-y-2 hover:border-white/20 transition-os"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-2">
                      <Terminal className="w-3.5 h-3.5 text-zinc-400" />
                      <span className="font-semibold text-white text-xs">{name}</span>
                    </div>
                    <span className={`text-[10px] px-1.5 py-0.2 uppercase font-medium border ${riskColor}`}>
                      {tool.risk || 'low'} risk
                    </span>
                  </div>

                  <p className="text-[11px] text-zinc-300 line-clamp-2 leading-relaxed">
                    {tool.capability || 'Agent execution capability'}
                  </p>

                  <div className="flex items-center justify-between pt-2 border-t border-white/5 text-[10px] text-zinc-500">
                    <span>Provider: {tool.provider || 'hermes'}</span>
                    <button
                      onClick={() => setExpandedTool(isExpanded ? null : name)}
                      className="text-zinc-400 hover:text-white flex items-center space-x-1 transition-os"
                    >
                      <span>{isExpanded ? 'Hide Schema' : 'Schema & Perms'}</span>
                      {isExpanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
                    </button>
                  </div>

                  {/* Expanded Schema & Details */}
                  {isExpanded && (
                    <div className="pt-2 mt-2 border-t border-white/5 space-y-2 text-[11px] text-zinc-300">
                      {tool.schema && (
                        <div className="space-y-0.5">
                          <span className="text-zinc-500 text-[10px] uppercase">Parameter Schema:</span>
                          <pre className="p-2 bg-black/40 border border-white/5 rounded-xs overflow-x-auto text-[10px] text-amber-400">
                            {tool.schema}
                          </pre>
                        </div>
                      )}

                      {tool.permissions && tool.permissions.length > 0 && (
                        <div className="space-y-0.5">
                          <span className="text-zinc-500 text-[10px] uppercase">Granted Permissions:</span>
                          <div className="flex flex-wrap gap-1">
                            {tool.permissions.map((p, idx) => (
                              <span key={idx} className="px-1.5 py-0.5 bg-white/5 border border-white/5 text-[10px] text-zinc-300">
                                {p}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </Panel>
  );
};
