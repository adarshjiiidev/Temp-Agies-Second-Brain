import React, { useState, useEffect } from 'react';
import { useOS } from '../lib/store';
import { api } from '../lib/api';
import { Search, Zap, Wifi, Battery, Activity, Layers, Shield } from 'lucide-react';

export const TopBar: React.FC = () => {
  const {
    routerHealth,
    isSocketConnected,
    setSearchOpen,
    setQuickActionsOpen,
    runningScript,
    openPanel,
  } = useOS();

  const [timeStr, setTimeStr] = useState('');
  const [dateStr, setDateStr] = useState('');
  const [is24Hour, setIs24Hour] = useState(true);
  const [autonomyLevel, setAutonomyLevel] = useState<number>(2);
  const [autonomyName, setAutonomyName] = useState<string>('LEVEL_2');

  useEffect(() => {
    api.getGovernance().then((gov) => {
      setAutonomyLevel(gov.autonomy_level);
      setAutonomyName(gov.level_name);
    }).catch(() => {});
  }, []);

  const toggleGovernance = async () => {
    const nextLevel = (autonomyLevel + 1) % 6;
    try {
      const res = await api.setGovernanceLevel(nextLevel);
      setAutonomyLevel(res.autonomy_level);
      setAutonomyName(res.level_name);
    } catch (e) {
      console.warn('Could not update governance level:', e);
    }
  };

  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      setTimeStr(
        now.toLocaleTimeString([], {
          hour12: !is24Hour,
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit',
        })
      );
      setDateStr(
        now.toLocaleDateString([], {
          weekday: 'short',
          month: 'short',
          day: 'numeric',
        })
      );
    };

    updateTime();
    const interval = setInterval(updateTime, 1000);
    return () => clearInterval(interval);
  }, [is24Hour]);

  const routerIsOk = routerHealth?.status === 'running';

  return (
    <header className="h-8 bg-[#141414] border-b border-[#262626] px-3 flex items-center justify-between z-30 select-none shrink-0 font-mono text-xs">
      {/* Left: AEGIS Branding */}
      <div className="flex items-center space-x-2.5">
        <div className="flex items-center space-x-1.5 cursor-pointer" onClick={() => openPanel('chat')}>
          <span className="w-2.5 h-2.5 bg-[#4a9] inline-block animate-pulse-live" />
          <span className="font-semibold text-sm tracking-wider text-[#e8e8e8]">
            AEGIS
          </span>
          <span className="text-[11px] text-[#666666] tracking-tight">
            AI·OS v1.0
          </span>
        </div>

        <div className="h-3 w-px bg-[#2a2a2a] mx-1" />

        <div className="flex items-center space-x-2 text-[11px] text-[#888888]">
          <span className="hover:text-[#e8e8e8] cursor-pointer" onClick={() => openPanel('pc')}>
            node-01
          </span>
          <span className="text-[#444444]">/</span>
          <span className="text-[#a0a0a0]">adarshjii</span>
        </div>
      </div>

      {/* Center: Global Search Bar */}
      <div className="flex-1 max-w-md mx-4">
        <button
          onClick={() => setSearchOpen(true)}
          className="w-full h-6 px-2.5 bg-[#1c1c1c] hover:bg-[#242424] border border-[#2e2e2e] hover:border-[#404040] text-[#777777] hover:text-[#a0a0a0] flex items-center justify-between text-xs transition-os"
        >
          <div className="flex items-center space-x-2 truncate">
            <Search className="w-3 h-3 text-[#666666]" />
            <span className="truncate">Search vault, models, skills, tools...</span>
          </div>
          <kbd className="text-[10px] text-[#555555] bg-[#141414] px-1 py-0.5 border border-[#2a2a2a]">
            ⌘K
          </kbd>
        </button>
      </div>

      {/* Right: Telemetry, 9Router, Scripts, Clock */}
      <div className="flex items-center space-x-3 text-[11px]">
        {/* Spatial Memory Graph Button */}
        <button
          onClick={() => openPanel('graph')}
          className="h-5 px-2 flex items-center space-x-1.5 border border-[#2e2e2e] bg-[#1c1c1c] hover:bg-[#242424] text-[#a0a0a0] hover:text-[#e8e8e8] transition-os"
          title="Open Spatial Memory Graph (Neural Cards & Wires)"
        >
          <Layers className="w-3 h-3 text-amber-400" />
          <span>Spatial Graph</span>
        </button>

        {/* Governance Autonomy Level Indicator */}
        <div
          onClick={toggleGovernance}
          className="flex items-center space-x-1 px-1.5 h-5 border border-white/10 bg-white/5 cursor-pointer hover:bg-white/10 text-[#a0a0a0] hover:text-white transition-os"
          title={`Governance Autonomy: Level ${autonomyLevel} (${autonomyName}) - Click to cycle autonomy`}
        >
          <Shield className="w-3 h-3 text-amber-400" />
          <span className="font-semibold text-white">L{autonomyLevel}</span>
        </div>

        {/* Quick Actions Trigger */}
        <button
          onClick={() => setQuickActionsOpen(true)}
          className={`h-5 px-2 flex items-center space-x-1.5 border transition-os ${
            runningScript
              ? 'bg-[#2a2a2a] border-[#c9a] text-[#c9a]'
              : 'bg-[#1c1c1c] hover:bg-[#242424] border-[#2e2e2e] text-[#a0a0a0] hover:text-[#e8e8e8]'
          }`}
          title="Quick Actions (Snapshot, Ingest, Learn)"
        >
          <Zap className={`w-3 h-3 ${runningScript ? 'animate-spin' : ''}`} />
          <span>{runningScript ? `Running: ${runningScript.replace('.sh', '')}` : 'Actions'}</span>
        </button>

        {/* AI Fabric Status Indicator */}
        <div
          onClick={() => openPanel('models')}
          title={`AI Model Fabric: ${routerIsOk ? 'Online (Free Round-Robin)' : 'Standby'}`}
          className="flex items-center space-x-1.5 cursor-pointer hover:text-[#e8e8e8] text-[#888888] transition-os px-1"
        >
          <span
            className={`w-2 h-2 ${routerIsOk ? 'bg-[#4a9]' : 'bg-[#c55]'}`}
          />
          <span className="text-[11px]">
            AI Fabric: {routerIsOk ? 'OK' : 'STANDBY'}
          </span>
        </div>


        {/* Live WebSocket Indicator */}
        <div
          title={isSocketConnected ? 'Live WebSocket Connected' : 'WebSocket Reconnecting...'}
          className="flex items-center space-x-1 text-[#888888]"
        >
          <span
            className={`w-1.5 h-1.5 ${
              isSocketConnected ? 'bg-[#4a9] animate-pulse-live' : 'bg-[#c9a]'
            }`}
          />
          <span className="text-[10px] uppercase tracking-wider text-[#666666]">
            {isSocketConnected ? 'LIVE' : 'POLL'}
          </span>
        </div>

        {/* Hardware Status Icons */}
        <div className="flex items-center space-x-2 text-[#666666]">
          <Wifi className="w-3.5 h-3.5 text-[#888888]" />
          <Battery className="w-3.5 h-3.5 text-[#888888]" />
        </div>

        {/* Clock */}
        <div
          onClick={() => setIs24Hour(!is24Hour)}
          title="Click to toggle 12h / 24h format"
          className="cursor-pointer text-[#a0a0a0] hover:text-[#e8e8e8] flex items-center space-x-1.5 pl-1"
        >
          <span className="text-[#666666]">{dateStr}</span>
          <span className="text-[#e8e8e8] font-medium">{timeStr}</span>
        </div>
      </div>
    </header>
  );
};
