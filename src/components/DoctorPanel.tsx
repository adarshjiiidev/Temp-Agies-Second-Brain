import React, { useState, useEffect, useCallback } from 'react';
import { Panel } from './Panel';
import { api, DoctorCheck, IdeAdapterInfo } from '../lib/api';
import { Stethoscope, RefreshCw, Loader2, CheckCircle2, XCircle, AlertTriangle, MinusCircle, Cpu } from 'lucide-react';

const STATUS_CONFIG = {
  PASS:           { icon: <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />, label: 'PASS',           cls: 'text-emerald-400 bg-emerald-900/20' },
  FAIL:           { icon: <XCircle className="w-3.5 h-3.5 text-red-400" />,          label: 'FAIL',           cls: 'text-red-400 bg-red-900/20' },
  WARN:           { icon: <AlertTriangle className="w-3.5 h-3.5 text-yellow-400" />, label: 'WARN',           cls: 'text-yellow-400 bg-yellow-900/20' },
  NOT_CONFIGURED: { icon: <MinusCircle className="w-3.5 h-3.5 text-zinc-500" />,     label: 'NOT_CONFIGURED', cls: 'text-zinc-500 bg-zinc-800/40' },
  NOT_SUPPORTED:  { icon: <MinusCircle className="w-3.5 h-3.5 text-zinc-600" />,     label: 'NOT_SUPPORTED',  cls: 'text-zinc-600 bg-zinc-900/40' },
};

export const DoctorPanel: React.FC = () => {
  const [checks, setChecks] = useState<DoctorCheck[]>([]);
  const [adapters, setAdapters] = useState<IdeAdapterInfo[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(() => {
    setLoading(true);
    Promise.all([
      api.aegisDoctor().catch(() => ({ checks: [] })),
      api.getIdeAdapters().catch(() => ({ adapters: [] })),
    ]).then(([d, a]) => {
      setChecks(d.checks);
      setAdapters(a.adapters);
      setLoading(false);
    });
  }, []);

  useEffect(() => { load(); }, [load]);

  const pass = checks.filter(c => c.status === 'PASS').length;
  const fail = checks.filter(c => c.status === 'FAIL').length;
  const nc   = checks.filter(c => c.status === 'NOT_CONFIGURED').length;

  return (
    <Panel
      id="doctor"
      title="AEGIS Doctor"
      icon={<Stethoscope className="w-3.5 h-3.5 text-amber-400" />}
      tag={`${pass} pass · ${fail} fail · ${nc} n/c`}
    >
      <div className="flex-1 flex flex-col h-full overflow-hidden bg-[#0e0e11] font-mono text-xs">
        {/* Summary bar */}
        <div className="flex items-center gap-4 px-4 py-2.5 border-b border-white/5 bg-white/[0.02] shrink-0">
          <div className="flex items-center gap-1.5">
            <div className="w-2 h-2 rounded-full bg-emerald-400" />
            <span className="text-emerald-400">{pass} pass</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="w-2 h-2 rounded-full bg-red-400" />
            <span className="text-red-400">{fail} fail</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="w-2 h-2 rounded-full bg-zinc-500" />
            <span className="text-zinc-500">{nc} not configured</span>
          </div>
          <button onClick={load} className="ml-auto p-1.5 text-zinc-500 hover:text-amber-400 hover:bg-white/5 rounded-xs transition-all">
            <RefreshCw className="w-3 h-3" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-5">
          {loading ? (
            <div className="flex items-center justify-center h-40 text-zinc-600">
              <Loader2 className="w-5 h-5 animate-spin mr-2" /> Running diagnostics...
            </div>
          ) : (
            <>
              {/* System checks */}
              <section>
                <div className="text-[10px] uppercase tracking-widest text-zinc-600 mb-2">System Checks</div>
                <div className="space-y-1">
                  {checks.map((c, i) => {
                    const cfg = STATUS_CONFIG[c.status] ?? STATUS_CONFIG.NOT_CONFIGURED;
                    return (
                      <div key={i} className={`flex items-center gap-3 px-3 py-2 rounded-xs border border-white/[0.04] ${c.status === 'FAIL' ? 'bg-red-900/10' : 'bg-white/[0.02]'}`}>
                        {cfg.icon}
                        <span className="flex-1 text-zinc-300">{c.name}</span>
                        <span className={`text-[10px] px-1.5 py-0.5 rounded-xs font-semibold ${cfg.cls}`}>{cfg.label}</span>
                        {c.message && <span className="text-zinc-600 text-[10px] truncate max-w-[160px]">{c.message}</span>}
                      </div>
                    );
                  })}
                </div>
              </section>

              {/* IDE Adapters */}
              <section>
                <div className="text-[10px] uppercase tracking-widest text-zinc-600 mb-2">AI IDE Adapters</div>
                <div className="space-y-1">
                  {adapters.map((a, i) => (
                    <div key={i} className="flex items-center gap-3 px-3 py-2 rounded-xs border border-white/[0.04] bg-white/[0.02]">
                      <Cpu className="w-3.5 h-3.5 text-sky-400 shrink-0" />
                      <span className="flex-1 text-zinc-300">{a.name}</span>
                      <div className="flex items-center gap-1.5">
                        {a.memory_bridge && <span className="text-[9px] px-1 py-0.5 bg-violet-900/30 text-violet-400 rounded-xs border border-violet-900/50">mem</span>}
                        {a.context_bridge && <span className="text-[9px] px-1 py-0.5 bg-sky-900/30 text-sky-400 rounded-xs border border-sky-900/50">ctx</span>}
                      </div>
                      <span className={`text-[10px] px-1.5 py-0.5 rounded-xs font-semibold ${a.status === 'AVAILABLE' ? STATUS_CONFIG.PASS.cls : STATUS_CONFIG.NOT_CONFIGURED.cls}`}>
                        {a.status === 'AVAILABLE' ? 'ACTIVE' : 'N/C'}
                      </span>
                    </div>
                  ))}
                </div>
              </section>
            </>
          )}
        </div>
      </div>
    </Panel>
  );
};
