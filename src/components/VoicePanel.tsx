import React, { useState, useEffect, useCallback } from 'react';
import { Panel } from './Panel';
import { api, VoiceStatus } from '../lib/api';
import { Mic, MicOff, Volume2, VolumeX, RefreshCw, Loader2, AlertTriangle } from 'lucide-react';

export const VoicePanel: React.FC = () => {
  const [status, setStatus] = useState<VoiceStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [input, setInput] = useState('');
  const [speaking, setSpeaking] = useState(false);
  const [transcript, setTranscript] = useState('');

  const load = useCallback(() => {
    api.voiceStatus()
      .then(s => { setStatus(s); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleSpeak = async () => {
    if (!input.trim()) return;
    setSpeaking(true);
    try {
      await api.voiceSpeak(input.trim());
      setTranscript(input.trim());
      setInput('');
    } catch { /* ignore */ } finally { setSpeaking(false); }
  };

  const micColor = {
    OFF: 'text-zinc-600',
    READY: 'text-amber-400',
    LISTENING: 'text-emerald-400',
    PROCESSING: 'text-sky-400',
  }[status?.mic_state ?? 'OFF'];

  return (
    <Panel
      id="voice"
      title="AEGIS Voice Interface"
      icon={<Mic className="w-3.5 h-3.5 text-amber-400" />}
      tag={status?.available ? 'READY' : 'NOT CONFIGURED'}
    >
      <div className="flex-1 flex flex-col h-full overflow-hidden bg-[#0e0e11] font-mono text-xs">
        {/* Status bar */}
        <div className="flex items-center gap-4 px-4 py-3 border-b border-white/5 bg-white/[0.02] shrink-0">
          <div className={`flex items-center gap-2 ${micColor}`}>
            {status?.mic_state === 'OFF' ? <MicOff className="w-4 h-4" /> : <Mic className="w-4 h-4" />}
            <span className="text-[11px] font-semibold">{status?.mic_state ?? 'LOADING'}</span>
          </div>
          <div className="h-4 w-px bg-white/10" />
          <div className="flex items-center gap-2 text-zinc-500">
            {status?.tts_state === 'SPEAKING' ? <Volume2 className="w-4 h-4 text-amber-400" /> : <VolumeX className="w-4 h-4" />}
            <span className="text-[11px]">{status?.tts_state ?? '—'}</span>
          </div>
          <div className="ml-auto flex items-center gap-2">
            <span className="text-[10px] text-zinc-600">{status?.engine}</span>
            <button onClick={load} className="p-1.5 hover:bg-white/5 text-zinc-600 hover:text-amber-400 rounded-xs transition-all">
              <RefreshCw className="w-3 h-3" />
            </button>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {!status?.available && (
            <div className="flex items-start gap-3 p-3 bg-amber-900/10 border border-amber-900/30 rounded-sm">
              <AlertTriangle className="w-4 h-4 text-amber-500 shrink-0 mt-0.5" />
              <div>
                <div className="text-amber-400 font-semibold mb-1">VoiceStudio Not Configured</div>
                <div className="text-zinc-500 leading-relaxed">
                  VoiceStudio (AGPL-3.0) runs as an isolated service to maintain license compliance.
                  Install and start the VoiceStudio service to enable voice capabilities.
                </div>
                <div className="mt-2 text-zinc-600 text-[11px]">
                  Install: <code className="text-sky-400">pip install voicestudio</code> then run as a separate service.
                </div>
              </div>
            </div>
          )}

          {/* Architecture diagram */}
          <div className="p-3 bg-white/[0.02] border border-white/[0.05] rounded-sm">
            <div className="text-[10px] text-zinc-600 uppercase tracking-widest mb-2">Voice Pipeline</div>
            <div className="flex items-center gap-2 text-[11px] text-zinc-500 flex-wrap">
              {['MIC', 'ASR', 'AEGIS', 'PLAN', 'EXECUTE', 'TTS', 'SPEAKER'].map((step, i, arr) => (
                <React.Fragment key={step}>
                  <span className={`px-2 py-0.5 rounded-xs border ${
                    ['AEGIS', 'PLAN', 'EXECUTE'].includes(step)
                      ? 'border-amber-600/50 bg-amber-900/20 text-amber-400'
                      : 'border-white/10 text-zinc-500'
                  }`}>{step}</span>
                  {i < arr.length - 1 && <span className="text-zinc-700">→</span>}
                </React.Fragment>
              ))}
            </div>
            <div className="mt-2 text-[10px] text-zinc-700">
              Voice is another interface to AEGIS — not a separate AI brain.
            </div>
          </div>

          {/* TTS test */}
          <div>
            <div className="text-[10px] text-zinc-600 uppercase tracking-widest mb-2">Test TTS</div>
            <div className="flex gap-2">
              <input
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && handleSpeak()}
                placeholder="Type something to speak..."
                disabled={!status?.available}
                className="flex-1 h-8 px-3 bg-white/5 border border-white/10 focus:border-amber-500/50 text-white text-xs outline-none placeholder-zinc-700 rounded-xs disabled:opacity-40"
              />
              <button
                onClick={handleSpeak}
                disabled={!status?.available || speaking || !input.trim()}
                className="h-8 px-3 bg-amber-600/80 hover:bg-amber-500/80 disabled:opacity-40 text-white rounded-xs flex items-center gap-1.5 transition-all"
              >
                {speaking ? <Loader2 className="w-3 h-3 animate-spin" /> : <Volume2 className="w-3 h-3" />}
                Speak
              </button>
            </div>
            {transcript && (
              <div className="mt-2 text-[11px] text-zinc-500">
                Last spoken: <span className="text-zinc-300">"{transcript}"</span>
              </div>
            )}
          </div>

          {/* Recent transcripts */}
          {status?.recent_transcripts && status.recent_transcripts.length > 0 && (
            <div>
              <div className="text-[10px] text-zinc-600 uppercase tracking-widest mb-2">Recent Transcripts</div>
              <div className="space-y-1.5">
                {status.recent_transcripts.map((t, i) => (
                  <div key={i} className="flex gap-3 p-2 bg-white/[0.02] border border-white/[0.04] rounded-xs">
                    <span className="text-zinc-700 text-[10px] shrink-0">{new Date(t.timestamp).toLocaleTimeString()}</span>
                    <span className="text-zinc-300 text-[11px]">{t.text}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </Panel>
  );
};
