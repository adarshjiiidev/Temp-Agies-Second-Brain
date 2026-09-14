import React, { useState, useEffect, useRef } from 'react';
import { useOS } from '../lib/store';
import { api, MemoryFile, SkillItem, ToolItem } from '../lib/api';
import {
  Search,
  FileText,
  Compass,
  Boxes,
  Wrench,
  X,
  ArrowRight,
} from 'lucide-react';

export const GlobalSearchModal: React.FC = () => {
  const { isSearchOpen, setSearchOpen, openNoteInVault, openPanel } = useOS();
  const [query, setQuery] = useState('');
  const [vaultFiles, setVaultFiles] = useState<MemoryFile[]>([]);
  const [skills, setSkills] = useState<SkillItem[]>([]);
  const [tools, setTools] = useState<ToolItem[]>([]);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (isSearchOpen) {
      setTimeout(() => inputRef.current?.focus(), 50);

      // Preload search indexes
      api.getMemoryFiles().then(setVaultFiles).catch(() => {});
      api.getSkills().then((res) => setSkills(Object.values(res))).catch(() => {});
      api.getTools().then((res) => setTools(Object.values(res.tools || {}))).catch(() => {});
    }
  }, [isSearchOpen]);

  if (!isSearchOpen) return null;

  const q = query.trim().toLowerCase();

  const matchedNotes = q
    ? vaultFiles.filter((f) => f.name.toLowerCase().includes(q) || f.path.toLowerCase().includes(q)).slice(0, 6)
    : [];

  const matchedSkills = q
    ? skills.filter((s) => s.name.toLowerCase().includes(q) || (s.purpose && s.purpose.toLowerCase().includes(q))).slice(0, 4)
    : [];

  const matchedTools = q
    ? tools.filter((t) => t.identity?.toLowerCase().includes(q) || (t.capability && t.capability.toLowerCase().includes(q))).slice(0, 4)
    : [];

  const totalMatches = matchedNotes.length + matchedSkills.length + matchedTools.length;

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-20 p-4 bg-black/60 backdrop-blur-md animate-in fade-in select-none">
      <div className="glass-panel-elevated w-full max-w-xl rounded-sm overflow-hidden border border-white/20 shadow-2xl font-mono text-xs">
        {/* Search Input Bar */}
        <div className="p-3 border-b border-white/10 flex items-center space-x-2.5 bg-white/[0.02]">
          <Search className="w-4 h-4 text-zinc-400" />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search vault notes, skills, tools, models..."
            className="flex-1 bg-transparent text-sm text-white outline-none placeholder-zinc-500 font-mono"
          />
          <kbd className="text-[10px] text-zinc-500 bg-white/5 px-1.5 py-0.5 border border-white/10">
            ESC
          </kbd>
          <button
            onClick={() => setSearchOpen(false)}
            className="p-1 text-zinc-400 hover:text-white hover:bg-white/10 transition-os"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Results List */}
        <div className="max-h-96 overflow-y-auto p-3 space-y-3 select-text">
          {!q ? (
            <div className="py-6 text-center text-zinc-500 text-xs">
              Type to search across Obsidian knowledge base, skills, and tools...
            </div>
          ) : totalMatches === 0 ? (
            <div className="py-6 text-center text-zinc-500 text-xs">
              No results found for "{query}".
            </div>
          ) : (
            <>
              {/* Vault Notes */}
              {matchedNotes.length > 0 && (
                <div className="space-y-1">
                  <div className="text-[10px] text-zinc-500 uppercase tracking-wider font-semibold px-2">
                    Obsidian Vault Notes ({matchedNotes.length})
                  </div>
                  {matchedNotes.map((note) => (
                    <button
                      key={note.path}
                      onClick={() => {
                        openNoteInVault(note.path);
                        setSearchOpen(false);
                      }}
                      className="w-full text-left p-2 rounded-xs hover:bg-white/10 transition-os flex items-center justify-between group"
                    >
                      <div className="flex items-center space-x-2 truncate">
                        <FileText className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                        <div className="truncate">
                          <div className="text-white text-xs font-medium truncate">{note.name}</div>
                          <div className="text-[10px] text-zinc-500 truncate">{note.path}</div>
                        </div>
                      </div>
                      <ArrowRight className="w-3 h-3 text-zinc-500 group-hover:text-white transition-os shrink-0" />
                    </button>
                  ))}
                </div>
              )}

              {/* Skills */}
              {matchedSkills.length > 0 && (
                <div className="space-y-1">
                  <div className="text-[10px] text-zinc-500 uppercase tracking-wider font-semibold px-2">
                    Skills ({matchedSkills.length})
                  </div>
                  {matchedSkills.map((skill) => (
                    <button
                      key={skill.name}
                      onClick={() => {
                        openPanel('skills');
                        setSearchOpen(false);
                      }}
                      className="w-full text-left p-2 rounded-xs hover:bg-white/10 transition-os flex items-center justify-between group"
                    >
                      <div className="flex items-center space-x-2 truncate">
                        <Compass className="w-3.5 h-3.5 text-sky-400 shrink-0" />
                        <div className="truncate">
                          <div className="text-white text-xs font-medium truncate">{skill.name}</div>
                          <div className="text-[10px] text-zinc-500 truncate">{skill.purpose || skill.category}</div>
                        </div>
                      </div>
                      <ArrowRight className="w-3 h-3 text-zinc-500 group-hover:text-white transition-os shrink-0" />
                    </button>
                  ))}
                </div>
              )}

              {/* Tools */}
              {matchedTools.length > 0 && (
                <div className="space-y-1">
                  <div className="text-[10px] text-zinc-500 uppercase tracking-wider font-semibold px-2">
                    Tools ({matchedTools.length})
                  </div>
                  {matchedTools.map((tool, idx) => (
                    <button
                      key={idx}
                      onClick={() => {
                        openPanel('tools');
                        setSearchOpen(false);
                      }}
                      className="w-full text-left p-2 rounded-xs hover:bg-white/10 transition-os flex items-center justify-between group"
                    >
                      <div className="flex items-center space-x-2 truncate">
                        <Wrench className="w-3.5 h-3.5 text-amber-400 shrink-0" />
                        <div className="truncate">
                          <div className="text-white text-xs font-medium truncate">{tool.identity || 'Tool'}</div>
                          <div className="text-[10px] text-zinc-500 truncate">{tool.capability}</div>
                        </div>
                      </div>
                      <ArrowRight className="w-3 h-3 text-zinc-500 group-hover:text-white transition-os shrink-0" />
                    </button>
                  ))}
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
};
