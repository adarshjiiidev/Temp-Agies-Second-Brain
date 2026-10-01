import React, { useState } from 'react';
import { useOS } from '../lib/store';
import { Code2, X, Play, Copy, Check, Terminal } from 'lucide-react';

export const CodexModal: React.FC = () => {
  const { codexOpen, setCodexOpen, codexPrompt } = useOS();
  const [codeSnippet, setCodeSnippet] = useState(codexPrompt || '');
  const [output, setOutput] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [copied, setCopied] = useState(false);

  React.useEffect(() => {
    if (codexPrompt) {
      setCodeSnippet(codexPrompt);
    }
  }, [codexPrompt]);

  if (!codexOpen) return null;

  const handleRunSimulation = () => {
    setRunning(true);
    setTimeout(() => {
      setOutput(
        `[Codex Sandbox Execution] :: Node v22.23.2 / Python 3.11.16\n` +
        `✓ Validated AST syntax without warnings\n` +
        `✓ Environment checks passed: permissions OK\n` +
        `Output stream:\n` +
        `-----------------------------------------\n` +
        `Ready for pipeline integration.\n` +
        `Process finished with exit code 0.`
      );
      setRunning(false);
    }, 800);
  };

  const handleCopy = () => {
    navigator.clipboard.writeText(codeSnippet);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-md animate-in fade-in select-none">
      <div className="glass-panel-elevated w-full max-w-3xl max-h-[85vh] flex flex-col rounded-sm overflow-hidden border border-white/20 shadow-2xl font-mono text-xs">
        {/* Header */}
        <div className="p-3 border-b border-white/10 flex items-center justify-between bg-white/[0.02]">
          <div className="flex items-center space-x-2">
            <Code2 className="w-4 h-4 text-amber-400" />
            <span className="font-semibold text-sm text-white">Codex Agent Sandbox & Code Inspector</span>
          </div>
          <div className="flex items-center space-x-2">
            <button
              onClick={handleCopy}
              className="p-1 text-zinc-400 hover:text-white transition-os flex items-center space-x-1"
              title="Copy code"
            >
              {copied ? <Check className="w-3.5 h-3.5 text-amber-400" /> : <Copy className="w-3.5 h-3.5" />}
            </button>
            <button
              onClick={() => setCodexOpen(false)}
              className="p-1 text-zinc-400 hover:text-white hover:bg-white/10 transition-os"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Editor Area */}
        <div className="flex-1 p-4 flex flex-col space-y-3 bg-[#0a0a0c] overflow-hidden">
          <div className="flex items-center justify-between text-[11px] text-zinc-400">
            <span>Buffer: codex_snippet.py</span>
            <button
              onClick={handleRunSimulation}
              disabled={running}
              className="px-2.5 py-1 bg-amber-500/20 hover:bg-amber-500/30 text-amber-400 border border-amber-500/40 rounded-xs flex items-center space-x-1.5 transition-os"
            >
              <Play className="w-3 h-3" />
              <span>{running ? 'Executing...' : 'Run in Sandbox'}</span>
            </button>
          </div>

          <textarea
            value={codeSnippet}
            onChange={(e) => setCodeSnippet(e.target.value)}
            className="flex-1 w-full bg-black/60 border border-white/10 p-3 text-xs text-amber-400 font-mono outline-none resize-none placeholder-zinc-600 rounded-xs leading-relaxed"
            rows={10}
            placeholder="Type or paste code for Codex to analyze..."
          />

          {output && (
            <div className="p-3 bg-black/80 border border-white/10 rounded-xs max-h-40 overflow-y-auto space-y-1">
              <div className="flex items-center space-x-1.5 text-[10px] text-zinc-500">
                <Terminal className="w-3 h-3 text-amber-400" />
                <span>SANDBOX CONSOLE</span>
              </div>
              <pre className="text-[11px] text-zinc-300 font-mono whitespace-pre-wrap">{output}</pre>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
