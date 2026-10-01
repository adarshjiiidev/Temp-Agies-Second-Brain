import React, { useState, useEffect, useCallback } from 'react';
import { Panel } from './Panel';
import { api, AegisTask } from '../lib/api';
import {
  LayoutList, Plus, Play, RefreshCw, Clock, CheckCircle2,
  XCircle, AlertTriangle, Loader2, ChevronDown, ChevronRight,
  Zap, Box, Cpu,
} from 'lucide-react';

const STATUS_META: Record<string, { color: string; bg: string; icon: React.ReactNode }> = {
  BACKLOG:       { color: 'text-zinc-400',  bg: 'bg-zinc-800/60',   icon: <Clock className="w-3 h-3" /> },
  READY:         { color: 'text-sky-400',   bg: 'bg-sky-900/30',    icon: <Zap className="w-3 h-3" /> },
  RUNNING:       { color: 'text-amber-400', bg: 'bg-amber-900/30',  icon: <Loader2 className="w-3 h-3 animate-spin" /> },
  BLOCKED:       { color: 'text-orange-400',bg: 'bg-orange-900/30', icon: <AlertTriangle className="w-3 h-3" /> },
  VERIFYING:     { color: 'text-violet-400',bg: 'bg-violet-900/30', icon: <RefreshCw className="w-3 h-3 animate-pulse" /> },
  DONE:          { color: 'text-emerald-400',bg:'bg-emerald-900/30', icon: <CheckCircle2 className="w-3 h-3" /> },
  FAILED:        { color: 'text-red-400',   bg: 'bg-red-900/30',    icon: <XCircle className="w-3 h-3" /> },
  NOT_CONFIGURED:{ color: 'text-zinc-500',  bg: 'bg-zinc-900/40',   icon: <Box className="w-3 h-3" /> },
};

function TaskCard({ task, onDispatch }: { task: AegisTask; onDispatch: (id: string) => void }) {
  const [expanded, setExpanded] = useState(false);
  const meta = STATUS_META[task.status] ?? STATUS_META.BACKLOG;
  const elapsed = task.updated_at
    ? `${Math.round((Date.now() / 1000 - task.updated_at) / 60)}m ago`
    : '—';

  return (
    <div className="border border-white/[0.06] rounded-sm bg-white/[0.025] hover:bg-white/[0.04] transition-all group">
      {/* Header */}
      <div
        className="flex items-center gap-2.5 p-3 cursor-pointer select-none"
        onClick={() => setExpanded(v => !v)}
      >
        {/* Status pill */}
        <span className={`flex items-center gap-1 px-1.5 py-0.5 rounded-xs text-[10px] font-mono font-semibold ${meta.color} ${meta.bg} shrink-0`}>
          {meta.icon}
          {task.status}
        </span>

        {/* Task summary */}
        <span className="flex-1 text-zinc-200 text-xs truncate font-mono leading-tight">
          {task.task}
        </span>

        {/* Agent badge */}
        {task.selected?.id && (
          <span className="text-[10px] text-zinc-500 font-mono px-1.5 py-0.5 border border-white/10 rounded-xs shrink-0">
            <Cpu className="w-2.5 h-2.5 inline mr-1" />
            {task.selected.id}
          </span>
        )}

        {/* Time */}
        <span className="text-zinc-600 text-[10px] font-mono shrink-0">{elapsed}</span>

        {/* Dispatch / expand */}
        <div className="flex items-center gap-1 shrink-0">
          {(task.status === 'READY' || task.status === 'BACKLOG') && (
            <button
              onClick={(e) => { e.stopPropagation(); onDispatch(task.id); }}
              className="p-1 text-amber-500 hover:text-amber-300 hover:bg-amber-900/30 rounded-xs transition-all"
              title="Dispatch task"
            >
              <Play className="w-3 h-3" />
            </button>
          )}
          {expanded
            ? <ChevronDown className="w-3 h-3 text-zinc-600" />
            : <ChevronRight className="w-3 h-3 text-zinc-600" />
          }
        </div>
      </div>

      {/* Expanded details */}
      {expanded && (
        <div className="px-3 pb-3 border-t border-white/[0.04] pt-2.5 space-y-1.5 font-mono text-[11px]">
          <div className="grid grid-cols-2 gap-x-4 gap-y-1">
            <div><span className="text-zinc-600">ID</span> <span className="text-zinc-300">{task.id}</span></div>
            <div><span className="text-zinc-600">Kind</span> <span className="text-zinc-300">{task.kind}</span></div>
            <div><span className="text-zinc-600">Project</span> <span className="text-zinc-300">{task.project || '—'}</span></div>
            <div><span className="text-zinc-600">Score</span> <span className="text-amber-400">{task.selected?.score ?? '—'}</span></div>
          </div>
          {task.result && (
            <div className="mt-1.5">
              <span className="text-zinc-600">Result: </span>
              <span className="text-zinc-400">{JSON.stringify(task.result).slice(0, 200)}</span>
            </div>
          )}
          {task.events && task.events.length > 0 && (
            <div className="mt-1.5 space-y-0.5">
              <div className="text-zinc-600 mb-1">Events:</div>
              {task.events.slice(-5).map((ev, i) => (
                <div key={i} className="text-zinc-500 flex gap-2">
                  <span className="text-zinc-700">{new Date(ev.at * 1000).toLocaleTimeString()}</span>
                  <span className="text-amber-600/70">[{ev.actor}]</span>
                  <span>{ev.type}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export const TaskBoardPanel: React.FC = () => {
  const [tasks, setTasks] = useState<AegisTask[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [newTask, setNewTask] = useState('');
  const [newProject, setNewProject] = useState('');
  const [newKind, setNewKind] = useState('general');
  const [filter, setFilter] = useState<string>('all');

  const load = useCallback(() => {
    setLoading(true);
    api.getTasks(100)
      .then(d => { setTasks(d.tasks); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  useEffect(() => { load(); const t = setInterval(load, 10000); return () => clearInterval(t); }, [load]);

  const handleCreate = async () => {
    if (!newTask.trim()) return;
    setCreating(true);
    try {
      await api.createTask(newTask.trim(), newProject.trim() || undefined, newKind);
      setNewTask('');
      setNewProject('');
      load();
    } catch { /* ignore */ } finally { setCreating(false); }
  };

  const handleDispatch = async (taskId: string) => {
    try {
      await api.dispatchTask(taskId);
      load();
    } catch { /* ignore */ }
  };

  const STATUS_GROUPS = ['RUNNING', 'VERIFYING', 'READY', 'BACKLOG', 'BLOCKED', 'DONE', 'FAILED', 'NOT_CONFIGURED'];
  const filtered = filter === 'all' ? tasks : tasks.filter(t => t.status === filter);
  const grouped = STATUS_GROUPS.map(s => ({ status: s, tasks: filtered.filter(t => t.status === s) })).filter(g => g.tasks.length > 0);

  return (
    <Panel
      id="tasks"
      title="AEGIS Task Board"
      icon={<LayoutList className="w-3.5 h-3.5 text-amber-400" />}
      tag={`${tasks.length} tasks`}
    >
      <div className="flex-1 flex flex-col h-full overflow-hidden bg-[#0e0e11] font-mono text-xs">
        {/* Create Task Row */}
        <div className="p-3 border-b border-white/5 bg-white/[0.02] space-y-2 shrink-0">
          <div className="flex gap-2">
            <input
              value={newTask}
              onChange={e => setNewTask(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleCreate()}
              placeholder="New task description..."
              className="flex-1 h-8 px-3 bg-white/5 border border-white/10 focus:border-amber-500/50 text-white text-xs outline-none placeholder-zinc-600 rounded-xs"
            />
            <select
              value={newKind}
              onChange={e => setNewKind(e.target.value)}
              className="h-8 px-2 bg-white/5 border border-white/10 text-zinc-300 text-xs outline-none rounded-xs"
            >
              <option value="general">General</option>
              <option value="coding">Coding</option>
              <option value="research">Research</option>
            </select>
            <button
              onClick={handleCreate}
              disabled={creating || !newTask.trim()}
              className="h-8 px-3 bg-amber-600/80 hover:bg-amber-500/80 disabled:opacity-40 text-white rounded-xs flex items-center gap-1.5 transition-all"
            >
              {creating ? <Loader2 className="w-3 h-3 animate-spin" /> : <Plus className="w-3 h-3" />}
              Create
            </button>
            <button onClick={load} className="h-8 px-2 border border-white/10 hover:bg-white/5 text-zinc-400 rounded-xs transition-all">
              <RefreshCw className="w-3 h-3" />
            </button>
          </div>
          <input
            value={newProject}
            onChange={e => setNewProject(e.target.value)}
            placeholder="Project name (optional)..."
            className="w-full h-7 px-3 bg-white/5 border border-white/10 focus:border-white/20 text-white text-[11px] outline-none placeholder-zinc-700 rounded-xs"
          />
        </div>

        {/* Status Filter */}
        <div className="flex items-center gap-1 px-3 py-2 border-b border-white/5 overflow-x-auto shrink-0">
          {['all', 'RUNNING', 'READY', 'DONE', 'FAILED', 'BLOCKED'].map(s => (
            <button
              key={s}
              onClick={() => setFilter(s)}
              className={`px-2 py-0.5 text-[10px] rounded-xs uppercase tracking-wider transition-all shrink-0 ${
                filter === s
                  ? 'bg-amber-600/80 text-white'
                  : 'text-zinc-500 hover:text-zinc-300 hover:bg-white/5'
              }`}
            >
              {s === 'all' ? `All (${tasks.length})` : `${s} (${tasks.filter(t => t.status === s).length})`}
            </button>
          ))}
        </div>

        {/* Task List */}
        <div className="flex-1 overflow-y-auto p-3 space-y-3">
          {loading ? (
            <div className="flex items-center justify-center h-40 text-zinc-600">
              <Loader2 className="w-5 h-5 animate-spin mr-2" /> Loading tasks...
            </div>
          ) : filtered.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-40 text-zinc-700 gap-2">
              <LayoutList className="w-8 h-8 opacity-30" />
              <span>No tasks yet. Create one above.</span>
            </div>
          ) : (
            grouped.map(group => (
              <div key={group.status}>
                <div className="flex items-center gap-2 mb-1.5">
                  {STATUS_META[group.status]?.icon}
                  <span className={`text-[10px] uppercase tracking-widest font-semibold ${STATUS_META[group.status]?.color}`}>
                    {group.status}
                  </span>
                  <span className="text-zinc-700 text-[10px]">({group.tasks.length})</span>
                </div>
                <div className="space-y-1.5">
                  {group.tasks.map(task => (
                    <TaskCard key={task.id} task={task} onDispatch={handleDispatch} />
                  ))}
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </Panel>
  );
};
