import React, { useState } from 'react';
import { Panel } from './Panel';
import { useOS } from '../lib/store';
import {
  Cpu,
  HardDrive,
  Activity,
  Network,
  Radio,
  RefreshCw,
  Server,
  Layers,
} from 'lucide-react';

export const PCMonitor: React.FC = () => {
  const { pcState, refreshPCState, isSocketConnected } = useOS();
  const [refreshing, setRefreshing] = useState(false);
  const [activeTab, setActiveTab] = useState<'overview' | 'processes' | 'network' | 'ports'>('overview');

  const handleRefresh = async () => {
    setRefreshing(true);
    await refreshPCState();
    setRefreshing(false);
  };

  if (!pcState) {
    return (
      <Panel id="pc" title="PC Monitor" icon={<Cpu className="w-3.5 h-3.5 text-[#4ade80]" />} tag="Hardware">
        <div className="flex-1 flex items-center justify-center p-8 text-xs font-mono text-zinc-500">
          <div className="flex flex-col items-center space-y-2">
            <RefreshCw className="w-5 h-5 animate-spin text-zinc-400" />
            <span>Connecting to PC Telemetry Kernel...</span>
          </div>
        </div>
      </Panel>
    );
  }

  const { memory, disk, processes, network, ports, system, timestamp } = pcState;

  // RAM calculations
  const totalRamGb = Math.round(memory.total_kb / 1024 / 1024 * 10) / 10;
  const usedRamGb = Math.round(memory.used_kb / 1024 / 1024 * 10) / 10;
  const availRamGb = Math.round(memory.available_kb / 1024 / 1024 * 10) / 10;
  const ramPercent = memory.total_kb > 0 ? Math.round((memory.used_kb / memory.total_kb) * 100) : 0;

  // RAM bar color
  const ramBarColor =
    ramPercent > 85 ? 'bg-[#f87171]' : ramPercent > 70 ? 'bg-[#fbbf24]' : 'bg-[#4ade80]';

  // Disk calculations
  const diskPercent = parseInt(disk.use_percent?.replace('%', '') || '0', 10);
  const diskBarColor =
    diskPercent > 85 ? 'bg-[#f87171]' : diskPercent > 70 ? 'bg-[#fbbf24]' : 'bg-[#4ade80]';

  return (
    <Panel
      id="pc"
      title="System Telemetry & Hardware"
      icon={<Cpu className="w-3.5 h-3.5 text-[#4ade80]" />}
      tag={system.PRETTY_NAME || 'Linux'}
      headerRight={
        <div className="flex items-center space-x-2">
          <button
            onClick={handleRefresh}
            title="Refresh System Stats"
            className="w-5 h-5 flex items-center justify-center text-zinc-400 hover:text-white hover:bg-white/10 transition-os"
          >
            <RefreshCw className={`w-3 h-3 ${refreshing ? 'animate-spin text-emerald-400' : ''}`} />
          </button>
        </div>
      }
    >
      <div className="flex-1 flex flex-col h-full overflow-hidden bg-[#0e0e11] font-mono text-xs">
        {/* Navigation Sub-header */}
        <div className="h-8 px-3 border-b border-white/5 bg-white/[0.02] flex items-center justify-between shrink-0 select-none">
          <div className="flex items-center space-x-1">
            {(['overview', 'processes', 'network', 'ports'] as const).map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`px-2 py-0.5 uppercase tracking-wider text-[10px] transition-os ${
                  activeTab === tab
                    ? 'bg-white/10 text-white font-medium border border-white/15'
                    : 'text-zinc-400 hover:text-white hover:bg-white/5 border border-transparent'
                }`}
              >
                {tab}
              </button>
            ))}
          </div>

          <div className="text-[10px] text-zinc-500 flex items-center space-x-2">
            <span className={`w-1.5 h-1.5 rounded-full ${isSocketConnected ? 'bg-emerald-400 animate-pulse-live' : 'bg-amber-400'}`} />
            <span>Updated {new Date(timestamp).toLocaleTimeString()}</span>
          </div>
        </div>

        {/* Tab Contents */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4 select-text">
          {activeTab === 'overview' && (
            <>
              {/* Gauges Grid */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {/* Memory Gauge Card */}
                <div className="glass-panel p-3 rounded-sm space-y-2">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-1.5 text-zinc-300">
                      <Cpu className="w-3.5 h-3.5 text-emerald-400" />
                      <span className="font-semibold text-xs">Physical Memory (RAM)</span>
                    </div>
                    <span className="text-xs font-semibold text-white">{ramPercent}%</span>
                  </div>

                  {/* Progress bar */}
                  <div className="w-full h-2 bg-white/5 border border-white/10 overflow-hidden">
                    <div
                      className={`h-full ${ramBarColor} transition-all duration-300`}
                      style={{ width: `${ramPercent}%` }}
                    />
                  </div>

                  <div className="flex items-center justify-between text-[11px] text-zinc-400 pt-0.5">
                    <span>Used: {usedRamGb} GB</span>
                    <span>Avail: {availRamGb} GB</span>
                    <span>Total: {totalRamGb} GB</span>
                  </div>
                </div>

                {/* Disk Gauge Card */}
                <div className="glass-panel p-3 rounded-sm space-y-2">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-1.5 text-zinc-300">
                      <HardDrive className="w-3.5 h-3.5 text-sky-400" />
                      <span className="font-semibold text-xs">Root Filesystem (/)</span>
                    </div>
                    <span className="text-xs font-semibold text-white">{disk.use_percent || '0%'}</span>
                  </div>

                  {/* Progress bar */}
                  <div className="w-full h-2 bg-white/5 border border-white/10 overflow-hidden">
                    <div
                      className={`h-full ${diskBarColor} transition-all duration-300`}
                      style={{ width: `${diskPercent}%` }}
                    />
                  </div>

                  <div className="flex items-center justify-between text-[11px] text-zinc-400 pt-0.5">
                    <span>Used: {disk.used}</span>
                    <span>Avail: {disk.avail}</span>
                    <span>Total: {disk.size}</span>
                  </div>
                </div>
              </div>

              {/* Host OS Specs */}
              <div className="glass-panel p-3 rounded-sm space-y-2">
                <div className="flex items-center space-x-1.5 text-xs font-semibold text-zinc-200">
                  <Server className="w-3.5 h-3.5 text-amber-400" />
                  <span>Host Architecture & Node Specs</span>
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 text-[11px] text-zinc-300">
                  <div>
                    <span className="text-zinc-500">Distribution: </span>
                    <span className="text-white">{system.PRETTY_NAME || 'Linux 64-bit'}</span>
                  </div>
                  <div>
                    <span className="text-zinc-500">Kernel: </span>
                    <span className="text-white">{system.VERSION_ID ? `v${system.VERSION_ID}` : 'Linux'}</span>
                  </div>
                  <div>
                    <span className="text-zinc-500">Total Cores / Top CPU: </span>
                    <span className="text-white">{processes[0]?.cpu ? `${processes[0].cpu}% top` : 'Normal'}</span>
                  </div>
                  <div>
                    <span className="text-zinc-500">Total Procs: </span>
                    <span className="text-white">{processes.length} sampled</span>
                  </div>
                  <div>
                    <span className="text-zinc-500">Active Ports: </span>
                    <span className="text-white">{ports.length} listening</span>
                  </div>
                  <div>
                    <span className="text-zinc-500">Network Interfaces: </span>
                    <span className="text-white">{Object.keys(network).length} found</span>
                  </div>
                </div>
              </div>

              {/* Top 5 Active Processes Preview */}
              <div className="glass-panel p-3 rounded-sm space-y-2">
                <div className="flex items-center justify-between text-xs font-semibold text-zinc-200">
                  <div className="flex items-center space-x-1.5">
                    <Activity className="w-3.5 h-3.5 text-emerald-400" />
                    <span>Top Processes by Memory Consumption</span>
                  </div>
                  <button
                    onClick={() => setActiveTab('processes')}
                    className="text-[10px] text-zinc-400 hover:text-white transition-os"
                  >
                    View All →
                  </button>
                </div>

                <div className="overflow-x-auto">
                  <table className="w-full text-left text-[11px]">
                    <thead>
                      <tr className="border-b border-white/10 text-zinc-500">
                        <th className="py-1">PID</th>
                        <th className="py-1">%MEM</th>
                        <th className="py-1">%CPU</th>
                        <th className="py-1">USER</th>
                        <th className="py-1">COMMAND</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-white/5">
                      {processes.slice(0, 6).map((p) => (
                        <tr key={p.pid} className="hover:bg-white/[0.02]">
                          <td className="py-1 text-zinc-400">{p.pid}</td>
                          <td className="py-1 text-emerald-400 font-medium">{p.mem}%</td>
                          <td className="py-1 text-zinc-300">{p.cpu}%</td>
                          <td className="py-1 text-zinc-400">{p.user}</td>
                          <td className="py-1 text-zinc-300 truncate max-w-xs">{p.command}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </>
          )}

          {activeTab === 'processes' && (
            <div className="glass-panel p-3 rounded-sm space-y-3">
              <div className="flex items-center justify-between text-xs text-zinc-300">
                <span className="font-semibold">All Sampled Active Processes ({processes.length})</span>
                <span className="text-zinc-500 text-[10px]">Sorted by % Memory</span>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead>
                    <tr className="border-b border-white/10 text-zinc-500 text-[11px]">
                      <th className="py-1.5">PID</th>
                      <th className="py-1.5">USER</th>
                      <th className="py-1.5">%MEM</th>
                      <th className="py-1.5">%CPU</th>
                      <th className="py-1.5">COMMAND</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/5 text-[11px]">
                    {processes.map((p) => (
                      <tr key={p.pid} className="hover:bg-white/[0.02]">
                        <td className="py-1 text-zinc-400">{p.pid}</td>
                        <td className="py-1 text-zinc-400">{p.user}</td>
                        <td className="py-1 text-emerald-400 font-medium">{p.mem}%</td>
                        <td className="py-1 text-zinc-300">{p.cpu}%</td>
                        <td className="py-1 text-zinc-200 truncate max-w-md">{p.command}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {activeTab === 'network' && (
            <div className="glass-panel p-3 rounded-sm space-y-3">
              <div className="flex items-center space-x-1.5 text-xs font-semibold text-zinc-200">
                <Network className="w-3.5 h-3.5 text-sky-400" />
                <span>Network Interfaces & Hardware Links</span>
              </div>
              <div className="space-y-2">
                {Object.entries(network).map(([iface, data]) => (
                  <div key={iface} className="p-2.5 bg-white/[0.02] border border-white/5 rounded-xs space-y-1">
                    <div className="flex items-center justify-between text-xs">
                      <div className="flex items-center space-x-2">
                        <span className="font-semibold text-white">{iface}</span>
                        <span className="text-[10px] text-zinc-500 uppercase">{data.type}</span>
                      </div>
                      <span
                        className={`text-[10px] px-1.5 py-0.2 border ${
                          data.state === 'UP'
                            ? 'bg-emerald-400/10 border-emerald-400/30 text-emerald-400'
                            : 'bg-zinc-800 border-zinc-700 text-zinc-500'
                        }`}
                      >
                        {data.state}
                      </span>
                    </div>
                    <div className="text-[11px] text-zinc-400">
                      <span>Addresses: </span>
                      <span className="text-zinc-200">
                        {data.addresses.length > 0 ? data.addresses.join(', ') : 'None'}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {activeTab === 'ports' && (
            <div className="glass-panel p-3 rounded-sm space-y-3">
              <div className="flex items-center space-x-1.5 text-xs font-semibold text-zinc-200">
                <Radio className="w-3.5 h-3.5 text-emerald-400" />
                <span>Listening TCP Ports ({ports.length})</span>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead>
                    <tr className="border-b border-white/10 text-zinc-500 text-[11px]">
                      <th className="py-1.5">STATE</th>
                      <th className="py-1.5">LOCAL ADDRESS</th>
                      <th className="py-1.5">PROCESS / BINDING</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/5 text-[11px]">
                    {ports.map((p, idx) => (
                      <tr key={idx} className="hover:bg-white/[0.02]">
                        <td className="py-1 text-emerald-400 font-medium">{p.state}</td>
                        <td className="py-1 text-white">{p.local_addr}</td>
                        <td className="py-1 text-zinc-400 truncate max-w-md">{p.process || '-'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      </div>
    </Panel>
  );
};
