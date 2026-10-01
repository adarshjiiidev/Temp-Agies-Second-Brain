import React, { useState, useEffect } from 'react';
import { Panel } from './Panel';
import { api, SkillItem } from '../lib/api';
import {
  Compass,
  Search,
  CheckCircle2,
  AlertTriangle,
  Shield,
  Workflow,
  Sparkles,
  X,
  FileCode,
} from 'lucide-react';

export const SkillsPanel: React.FC = () => {
  const [skills, setSkills] = useState<Record<string, SkillItem>>({});
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('all');
  const [activeSkill, setActiveSkill] = useState<SkillItem | null>(null);

  useEffect(() => {
    api.getSkills().then((data) => {
      setSkills(data);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  const allSkillsList = Object.values(skills);

  // Extract unique categories
  const categories = ['all', ...Array.from(new Set(allSkillsList.map((s) => s.category || 'other')))];

  const filteredSkills = allSkillsList.filter((s) => {
    const matchesCategory = selectedCategory === 'all' || s.category === selectedCategory;
    const matchesSearch =
      !searchQuery ||
      s.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (s.purpose && s.purpose.toLowerCase().includes(searchQuery.toLowerCase())) ||
      (s.description && s.description.toLowerCase().includes(searchQuery.toLowerCase()));
    return matchesCategory && matchesSearch;
  });

  return (
    <Panel
      id="skills"
      title="Agent Skills Registry"
      icon={<Compass className="w-3.5 h-3.5 text-[#38bdf8]" />}
      tag={`${allSkillsList.length} Skills`}
    >
      <div className="flex-1 flex flex-col h-full overflow-hidden bg-[#0e0e11] font-mono text-xs">
        {/* Search & Category Filter Bar */}
        <div className="p-3 border-b border-white/5 bg-white/[0.02] flex flex-col sm:flex-row items-center justify-between gap-2 shrink-0">
          <div className="relative w-full sm:w-64">
            <Search className="w-3 h-3 text-zinc-400 absolute left-2.5 top-2.5" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search skills..."
              className="w-full h-8 pl-8 pr-3 bg-white/5 border border-white/10 focus:border-white/20 text-white text-xs outline-none placeholder-zinc-500 rounded-xs"
            />
          </div>

          <div className="flex items-center space-x-1 overflow-x-auto max-w-full pb-0.5">
            {categories.map((cat) => (
              <button
                key={cat}
                onClick={() => setSelectedCategory(cat)}
                className={`px-2 py-1 uppercase tracking-wider text-[10px] transition-os shrink-0 rounded-xs ${
                  selectedCategory === cat
                    ? 'bg-white/10 text-white font-medium border border-white/20'
                    : 'text-zinc-400 hover:text-white hover:bg-white/5 border border-transparent'
                }`}
              >
                {cat}
              </button>
            ))}
          </div>
        </div>

        {/* Skills Grid */}
        <div className="flex-1 overflow-y-auto p-4">
          {loading ? (
            <div className="h-40 flex items-center justify-center text-zinc-500">
              <span>Loading skill registry...</span>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              {filteredSkills.map((skill) => (
                <div
                  key={skill.name}
                  onClick={() => setActiveSkill(skill)}
                  className="glass-panel hover:glass-panel-elevated p-3.5 rounded-sm cursor-pointer transition-os flex flex-col justify-between group"
                >
                  <div className="space-y-1.5">
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-white group-hover:text-amber-400 transition-os truncate text-xs">
                        {skill.name}
                      </span>
                      <span className="text-[10px] uppercase px-1.5 py-0.2 bg-white/5 border border-white/10 text-zinc-300">
                        v{skill.version || '1.0'}
                      </span>
                    </div>

                    <div className="text-[10px] text-zinc-400 font-medium tracking-wide uppercase">
                      {skill.category || 'General'}
                    </div>

                    <p className="text-[11px] text-zinc-300 line-clamp-3 leading-relaxed">
                      {skill.purpose || skill.description || 'No description available'}
                    </p>
                  </div>

                  <div className="flex items-center justify-between pt-3 mt-2 border-t border-white/5 text-[10px] text-zinc-400">
                    <span className="flex items-center space-x-1">
                      <Sparkles className="w-2.5 h-2.5 text-amber-400" />
                      <span>{skill.confidence ? `${Math.round(skill.confidence * 100)}% conf` : 'Loaded'}</span>
                    </span>
                    <span className="text-zinc-500 group-hover:text-white transition-os">
                      Inspect SKILL.md →
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Active Skill Deep Dive Modal */}
        {activeSkill && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-md animate-in fade-in">
            <div className="glass-panel-elevated w-full max-w-2xl max-h-[85vh] flex flex-col rounded-sm overflow-hidden border border-white/20 shadow-2xl">
              {/* Modal Header */}
              <div className="p-4 border-b border-white/10 flex items-center justify-between bg-white/[0.02]">
                <div className="flex items-center space-x-2">
                  <Compass className="w-4 h-4 text-amber-400" />
                  <span className="font-semibold text-sm text-white">{activeSkill.name}</span>
                  <span className="text-[10px] px-1.5 py-0.2 bg-white/10 border border-white/20 text-zinc-300">
                    {activeSkill.category || 'Skill'}
                  </span>
                </div>
                <button
                  onClick={() => setActiveSkill(null)}
                  className="p-1 text-zinc-400 hover:text-white hover:bg-white/10 transition-os"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              {/* Modal Body */}
              <div className="p-5 overflow-y-auto space-y-4 text-xs select-text">
                {/* Purpose */}
                <div className="space-y-1">
                  <span className="text-zinc-400 text-[11px] uppercase tracking-wider font-semibold">Purpose & Summary</span>
                  <p className="text-white text-xs leading-relaxed bg-white/[0.02] p-3 border border-white/5 rounded-xs">
                    {activeSkill.purpose || activeSkill.description || 'No detailed purpose'}
                  </p>
                </div>

                {/* Workflow */}
                {activeSkill.workflow && activeSkill.workflow.length > 0 && (
                  <div className="space-y-1.5">
                    <span className="text-zinc-400 text-[11px] uppercase tracking-wider font-semibold flex items-center space-x-1.5">
                      <Workflow className="w-3 h-3 text-sky-400" />
                      <span>Execution Workflow</span>
                    </span>
                    <ol className="list-decimal list-inside space-y-1 text-zinc-200 bg-white/[0.02] p-3 border border-white/5 rounded-xs">
                      {activeSkill.workflow.map((step, idx) => (
                        <li key={idx} className="leading-relaxed">{step}</li>
                      ))}
                    </ol>
                  </div>
                )}

                {/* Inputs & Outputs */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {activeSkill.inputs && (
                    <div className="space-y-1">
                      <span className="text-zinc-400 text-[11px] uppercase tracking-wider font-semibold">Inputs</span>
                      <ul className="space-y-1 bg-white/[0.02] p-2.5 border border-white/5 rounded-xs text-zinc-300">
                        {activeSkill.inputs.map((inp, idx) => (
                          <li key={idx} className="text-[11px] flex items-center space-x-1.5">
                            <span className="w-1 h-1 bg-amber-400 rounded-full" />
                            <span>{inp}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {activeSkill.outputs && (
                    <div className="space-y-1">
                      <span className="text-zinc-400 text-[11px] uppercase tracking-wider font-semibold">Outputs</span>
                      <ul className="space-y-1 bg-white/[0.02] p-2.5 border border-white/5 rounded-xs text-zinc-300">
                        {activeSkill.outputs.map((out, idx) => (
                          <li key={idx} className="text-[11px] flex items-center space-x-1.5">
                            <span className="w-1 h-1 bg-sky-400 rounded-full" />
                            <span>{out}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>

                {/* Permissions & Required Tools */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {activeSkill.permissions && (
                    <div className="space-y-1">
                      <span className="text-zinc-400 text-[11px] uppercase tracking-wider font-semibold flex items-center space-x-1">
                        <Shield className="w-3 h-3 text-amber-400" />
                        <span>Permissions</span>
                      </span>
                      <ul className="space-y-1 bg-white/[0.02] p-2.5 border border-white/5 rounded-xs text-zinc-300">
                        {activeSkill.permissions.map((p, idx) => (
                          <li key={idx} className="text-[11px] text-amber-300/90">{p}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {activeSkill.failure_modes && (
                    <div className="space-y-1">
                      <span className="text-zinc-400 text-[11px] uppercase tracking-wider font-semibold flex items-center space-x-1">
                        <AlertTriangle className="w-3 h-3 text-red-400" />
                        <span>Failure Modes</span>
                      </span>
                      <ul className="space-y-1 bg-white/[0.02] p-2.5 border border-white/5 rounded-xs text-zinc-300">
                        {activeSkill.failure_modes.map((fm, idx) => (
                          <li key={idx} className="text-[11px] text-red-300/90">{fm}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </Panel>
  );
};
