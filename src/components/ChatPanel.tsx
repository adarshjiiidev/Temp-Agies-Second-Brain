import React, { useState, useEffect, useRef } from 'react';
import { Panel } from './Panel';
import { api, ChatMessage, ModelRegistryData } from '../lib/api';
import { useOS } from '../lib/store';
import { marked } from 'marked';
import {
  Terminal,
  Send,
  Trash2,
  Download,
  Copy,
  Check,
  Cpu,
  ChevronDown,
  Layers,
  Code2,
  Sparkles,
} from 'lucide-react';

marked.setOptions({
  gfm: true,
  breaks: true,
});

const INITIAL_MESSAGES: ChatMessage[] = [
  {
    id: 'msg-init-1',
    sender: 'ai',
    content: 'Hello! I am **Agies**, your personal AI assistant. I have full context of all your projects, consolidated agent sessions, and tools across this machine.\n\nHow can I help you right now?',
    timestamp: 'Just now',
    model: 'gemini/gemini-3.8-flash',
  },
];

const CURATED_DEFAULT_MODELS = [
  'gemini/gemini-3.8-flash',
  'gemini/gemini-3.7-flash',
  'gemini/gemini-3.6-flash',
  'gemini/gemini-3.5-flash-lite',
  'gemini/gemini-3-flash-preview',
  'gemini/gemini-3.1-flash-lite-preview',
];

export const ChatPanel: React.FC = () => {
  const { pcState, setCodexOpen, setCodexPrompt, openAgentTab } = useOS();

  const [messages, setMessages] = useState<ChatMessage[]>(() => {
    try {
      const saved = localStorage.getItem('aegis_chat_history');
      if (saved) return JSON.parse(saved);
    } catch {
      // fallback
    }
    return INITIAL_MESSAGES;
  });

  const [inputMessage, setInputMessage] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [selectedModel, setSelectedModel] = useState<string>('gemini/gemini-3.8-flash');
  const [availableModels, setAvailableModels] = useState<string[]>(CURATED_DEFAULT_MODELS);
  const [showContext, setShowContext] = useState(false);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Load models from backend registry for dropdown
  useEffect(() => {
    api.getModels().then((data: ModelRegistryData) => {
      if (data.curated_models) {
        const keys = Object.keys(data.curated_models);
        if (keys.length > 0) {
          setAvailableModels(keys);
        }
      }
    }).catch(() => {
      // fallback to curated default
    });
  }, []);

  // Save history to localStorage
  useEffect(() => {
    try {
      localStorage.setItem('aegis_chat_history', JSON.stringify(messages.slice(-50)));
    } catch {
      // ignore
    }
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = async () => {
    const text = inputMessage.trim();
    if (!text || isTyping) return;

    // Handle local slash command: /clear
    if (text === '/clear') {
      setMessages([]);
      setInputMessage('');
      localStorage.removeItem('aegis_chat_history');
      return;
    }

    const userMsg: ChatMessage = {
      id: `msg-${Date.now()}`,
      sender: 'user',
      content: text,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
    };

    const newHistory = [...messages, userMsg];
    setMessages(newHistory);
    setInputMessage('');
    setIsTyping(true);

    try {
      // Prepare history formatted for multi-turn
      const historyContext = newHistory
        .filter((m) => m.sender === 'user' || m.sender === 'ai')
        .slice(-6)
        .map((m) => ({
          role: m.sender === 'user' ? 'user' : 'assistant',
          content: m.content,
        }));

      const res = await api.sendChatMessage(text, historyContext, selectedModel);

      const aiMsg: ChatMessage = {
        id: `msg-${Date.now() + 1}`,
        sender: 'ai',
        content: res.content,
        timestamp: new Date(res.timestamp || Date.now()).toLocaleTimeString([], {
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit',
        }),
        model: res.model || selectedModel,
        classification: res.classification,
      };

      setMessages((prev) => [...prev, aiMsg]);
    } catch (err: unknown) {
      const errMsg: ChatMessage = {
        id: `msg-${Date.now() + 1}`,
        sender: 'system',
        content: `Error communicating with Hermes AI service: ${err instanceof Error ? err.message : String(err)}`,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
      };
      setMessages((prev) => [...prev, errMsg]);
    } finally {
      setIsTyping(false);
      setTimeout(() => textareaRef.current?.focus(), 100);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleCopy = (id: string, text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const handleExportMarkdown = () => {
    const md = messages
      .map((m) => `### [${m.timestamp}] ${m.sender.toUpperCase()}${m.model ? ` (${m.model})` : ''}\n\n${m.content}\n\n---`)
      .join('\n\n');

    const blob = new Blob([md], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `aegis-chat-${new Date().toISOString().slice(0, 10)}.md`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleSendToCodex = (content: string) => {
    setCodexPrompt(content);
    setCodexOpen(true);
  };

  return (
    <Panel
      id="chat"
      title="Agies AI"
      icon={<Sparkles className="w-3.5 h-3.5 text-emerald-400" />}
      tag="AGIES"
      headerRight={
        <div className="flex items-center space-x-1">
          {/* Model Selector Dropdown */}
          <div className="relative">
            <select
              value={selectedModel}
              onChange={(e) => setSelectedModel(e.target.value)}
              className="bg-[#242424] text-[#a0a0a0] hover:text-[#e8e8e8] border border-[#383838] text-[11px] font-mono px-2 py-0.5 outline-none cursor-pointer pr-4 appearance-none"
              title="Select active LLM routing model"
            >
              {availableModels.map((m) => (
                <option key={m} value={m}>
                  {m.split('/').pop() || m}
                </option>
              ))}
            </select>
            <ChevronDown className="w-2.5 h-2.5 text-[#888888] absolute right-1 top-1.5 pointer-events-none" />
          </div>

          {/* Context Inspector Toggle */}
          <button
            onClick={() => setShowContext(!showContext)}
            title="Inspect Agent Context"
            className={`w-5 h-5 flex items-center justify-center transition-os ${
              showContext ? 'text-[#e8e8e8] bg-[#333333]' : 'text-[#888888] hover:text-[#e8e8e8] hover:bg-[#262626]'
            }`}
          >
            <Layers className="w-3 h-3" />
          </button>

          {/* Export Chat */}
          <button
            onClick={handleExportMarkdown}
            title="Export Chat History as Markdown"
            className="w-5 h-5 flex items-center justify-center text-[#888888] hover:text-[#e8e8e8] hover:bg-[#262626] transition-os"
          >
            <Download className="w-3 h-3" />
          </button>

          {/* Clear Chat */}
          <button
            onClick={() => {
              if (confirm('Clear chat session history?')) {
                setMessages([]);
                localStorage.removeItem('aegis_chat_history');
              }
            }}
            title="Clear Chat Session"
            className="w-5 h-5 flex items-center justify-center text-[#888888] hover:text-[#c55] hover:bg-[#262626] transition-os"
          >
            <Trash2 className="w-3 h-3" />
          </button>
        </div>
      }
    >
      <div className="flex-1 flex flex-col h-full overflow-hidden bg-[#121212] font-mono">
        {/* Collapsible Context Drawer */}
        {showContext && (
          <div className="p-3 bg-[#181818] border-b border-[#2a2a2a] text-xs space-y-1.5 shrink-0 transition-os select-text">
            <div className="flex items-center justify-between text-[#888888] text-[11px] pb-1 border-b border-[#242424]">
              <span className="font-semibold text-[#e8e8e8]">ACTIVE AGENT CONTEXT INJECTION</span>
              <span className="text-[#4a9]">HERMES AGIES PROFILE</span>
            </div>
            <div className="grid grid-cols-2 gap-2 text-[11px] text-[#a0a0a0]">
              <div>
                <span className="text-[#666666]">Vault Path: </span>
                <span className="text-[#e8e8e8]">/home/adarshjii/ObsidianVault/</span>
              </div>
              <div>
                <span className="text-[#666666]">Host Machine: </span>
                <span className="text-[#e8e8e8]">
                  {pcState?.system.NAME || 'Linux'} (RAM: {pcState ? Math.round(pcState.memory.used_kb / 1024 / 1024) : 0}GB / {pcState ? Math.round(pcState.memory.total_kb / 1024 / 1024) : 0}GB)
                </span>
              </div>
              <div>
                <span className="text-[#666666]">Active Model: </span>
                <span className="text-[#e8e8e8]">{selectedModel}</span>
              </div>
              <div>
                <span className="text-[#666666]">Persona: </span>
                <span className="text-[#e8e8e8]">agies (God PC user, high technical fluency)</span>
              </div>
            </div>
          </div>
        )}

        {/* Model Selector Bar */}
        <div className="px-3 py-1.5 bg-[#141416] border-b border-[#252528] flex items-center justify-between gap-2 shrink-0 select-none">
          <div className="flex items-center gap-1.5 overflow-x-auto py-0.5 no-scrollbar">
            <span className="text-[10px] text-[#71717a] uppercase font-semibold tracking-wider mr-0.5 shrink-0">Model:</span>
            {[
              { id: 'gemini/gemini-3.8-flash', label: '3.8 Flash', tag: 'Frontier' },
              { id: 'gemini/gemini-3.7-flash', label: '3.7 Flash', tag: 'Thinking' },
              { id: 'gemini/gemini-3.6-flash', label: '3.6 Flash', tag: 'Low-Latency' },
              { id: 'gemini/gemini-3.5-flash-lite', label: '3.5 Lite', tag: 'Fast' },
              { id: 'auto', label: 'Auto (MoE)', tag: 'Router' },
            ].map((m) => (
              <button
                key={m.id}
                onClick={() => setSelectedModel(m.id)}
                className={`px-2 py-0.5 text-[11px] font-mono rounded flex items-center gap-1 transition-os shrink-0 ${
                  selectedModel === m.id
                    ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 font-medium'
                    : 'bg-white/5 hover:bg-white/10 text-zinc-400 hover:text-zinc-200 border border-white/5'
                }`}
                title={`Switch model to ${m.id}`}
              >
                <span className={`w-1.5 h-1.5 rounded-full ${selectedModel === m.id ? 'bg-emerald-400 animate-pulse-live' : 'bg-zinc-600'}`} />
                <span>{m.label}</span>
              </button>
            ))}
          </div>

          <div className="flex items-center gap-1.5 shrink-0 text-[11px] font-mono text-zinc-400">
            <span className="hidden sm:inline text-emerald-400/90 text-[10px] bg-emerald-500/10 px-1.5 py-0.5 rounded border border-emerald-500/20">
              9Router: 870 models
            </span>
          </div>
        </div>

        {/* Message Log */}
        <div className="flex-1 overflow-y-auto p-4 space-y-3 select-text">
          {messages.map((m) => {
            if (m.sender === 'system') {
              return (
                <div key={m.id} className="text-[11px] text-[#c9a] bg-[#1a1814] border-l-2 border-[#c9a] px-3 py-1.5 my-2">
                  <span className="text-[#887755] mr-2">[{m.timestamp}]</span>
                  <span>{m.content}</span>
                </div>
              );
            }

            if (m.sender === 'user') {
              return (
                <div key={m.id} className="flex flex-col items-end pl-12 group">
                  <div className="flex items-center space-x-2 text-[10px] text-[#666666] mb-1">
                    <span>{m.timestamp}</span>
                    <span className="text-[#a0a0a0] font-medium">YOU</span>
                  </div>
                  <div className="bg-[#242424] hover:bg-[#282828] border border-[#333333] px-3 py-2 text-xs text-[#e8e8e8] max-w-full whitespace-pre-wrap transition-os">
                    {m.content}
                  </div>
                </div>
              );
            }

            // AI message
            return (
              <div key={m.id} className="flex flex-col items-start pr-8 group">
                <div className="flex items-center justify-between w-full text-[10px] text-[#666666] mb-1">
                  <div className="flex items-center space-x-1.5">
                    <span className="w-1.5 h-1.5 bg-[#4a9] inline-block" />
                    <span className="text-[#6a8] font-semibold">HERMES</span>
                    {m.model && <span className="text-[#555555]">({m.model.split('/').pop()})</span>}
                    <span>{m.timestamp}</span>
                  </div>

                  <div className="opacity-0 group-hover:opacity-100 flex items-center space-x-1.5 transition-os">
                    <button
                      onClick={() => handleSendToCodex(m.content)}
                      className="px-1.5 py-0.5 text-[10px] text-[#888888] hover:text-[#e8e8e8] bg-[#1a1a1a] hover:bg-[#242424] border border-[#2a2a2a] flex items-center space-x-1"
                      title="Send response to Codex editor/runner"
                    >
                      <Code2 className="w-2.5 h-2.5" />
                      <span>Codex</span>
                    </button>
                    <button
                      onClick={() => handleCopy(m.id, m.content)}
                      className="p-1 text-[#888888] hover:text-[#e8e8e8] transition-os"
                      title="Copy response text"
                    >
                      {copiedId === m.id ? <Check className="w-3 h-3 text-[#4a9]" /> : <Copy className="w-3 h-3" />}
                    </button>
                  </div>
                </div>

                <div
                  className="bg-[#181818] border border-[#262626] p-3 text-xs text-[#e8e8e8] w-full leading-relaxed select-text markdown-body"
                  dangerouslySetInnerHTML={{ __html: marked.parse(m.content) as string }}
                />

                {/* Orchestrator Classification & Fallback Card */}
                {m.classification && (
                  <div className="mt-1.5 w-full flex flex-wrap items-center justify-between gap-1.5 px-2.5 py-1.5 rounded bg-black/40 border border-white/5 text-[11px]">
                    <div className="flex items-center gap-2">
                      <span className="text-emerald-400 font-medium">
                        [{m.classification.tier_name}]
                      </span>
                      <span className="text-neutral-500">
                        Primary: <span className="text-neutral-300 font-mono">{m.classification.primary.split('/').pop()}</span>
                      </span>
                      {m.classification.fallback && (
                        <span className="text-amber-400/90 font-mono">
                          ⇄ Fallback: {m.classification.fallback.split('/').pop()}
                        </span>
                      )}
                    </div>
                    {m.classification.target_tab && (
                      <button
                        onClick={() => openAgentTab(m.classification?.target_tab || 'hermes')}
                        className="flex items-center gap-1 px-2 py-0.5 rounded bg-white/10 hover:bg-emerald-500/20 hover:text-emerald-300 text-neutral-300 transition-colors font-mono text-[10px]"
                      >
                        <Terminal className="w-3 h-3 text-emerald-400" />
                        <span>Launch in {m.classification.target_tab} tab →</span>
                      </button>
                    )}
                  </div>
                )}
              </div>
            );
          })}

          {isTyping && (
            <div className="flex items-center space-x-2 text-xs text-[#6a8] py-2 px-1">
              <span className="w-2 h-2 bg-[#6a8] animate-pulse-live" />
              <span className="text-[11px] text-[#888888]">Hermes & 9Router generating response...</span>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Quick Slash Commands Strip */}
        <div className="px-3 py-1.5 bg-[#141414] border-t border-[#222222] flex items-center justify-between text-[11px] text-[#666666] shrink-0">
          <div className="flex items-center space-x-1.5 overflow-x-auto">
            <span className="text-[#444444] shrink-0">Commands:</span>
            {['/pc', '/vault', '/skills', '/models', '/clear', '/help'].map((cmd) => (
              <button
                key={cmd}
                onClick={() => {
                  setInputMessage(cmd);
                  textareaRef.current?.focus();
                }}
                className="px-1.5 py-0.5 bg-[#1a1a1a] hover:bg-[#262626] text-[#888888] hover:text-[#e8e8e8] border border-[#262626] transition-os shrink-0 font-mono text-[10px]"
              >
                {cmd}
              </button>
            ))}
          </div>
          <div className="flex items-center space-x-1 text-[10px] font-mono text-zinc-400">
            <span className="text-zinc-500">Route:</span>
            <span className="text-emerald-400 font-medium truncate max-w-[140px]">{selectedModel.split('/').pop()}</span>
          </div>
        </div>

        {/* Input Area */}
        <div className="p-3 bg-[#161616] border-t border-[#262626] flex items-end space-x-2 shrink-0">
          <textarea
            ref={textareaRef}
            rows={2}
            value={inputMessage}
            onChange={(e) => setInputMessage(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask anything or use /pc, /vault, /skills, /models..."
            className="flex-1 bg-[#121212] border border-[#2a2a2a] focus:border-[#404040] text-[#e8e8e8] text-xs p-2.5 outline-none resize-none placeholder-[#555555] font-mono leading-relaxed"
          />

          <button
            onClick={handleSend}
            disabled={!inputMessage.trim() || isTyping}
            className={`h-11 px-4 flex items-center justify-center font-mono text-xs font-medium transition-os ${
              inputMessage.trim() && !isTyping
                ? 'bg-[#2a2a2a] hover:bg-[#333333] text-[#e8e8e8] border border-[#444444]'
                : 'bg-[#1a1a1a] text-[#555555] border border-[#222222] cursor-not-allowed'
            }`}
            title="Send Message (Enter)"
          >
            <Send className="w-3.5 h-3.5 mr-1.5" />
            <span>Send</span>
          </button>
        </div>
      </div>
    </Panel>
  );
};
