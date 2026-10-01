import React, { useEffect, useState } from 'react';
import { api, ProjectItem } from '../lib/api';
import { Panel } from './Panel';
import { Activity, Server, Cpu, CheckCircle, Clock, Zap, Target, BookOpen } from 'lucide-react';
import { useOS } from '../lib/store';

export const HomePanel: React.FC = () => {
  const { openNoteInVault, togglePanel } = useOS();
  const [agents, setAgents] = useState<any[]>([]);
  const [tasks, setTasks] = useState<any[]>([]);
  const [projects, setProjects] = useState<ProjectItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchDashboard = async () => {
      try {
        const [agentsRes, tasksRes, projectsRes] = await Promise.all([
          api.getAgents().catch(() => ({ agents: [] })),
          fetch('/api/tasks').then(res => res.json()).catch(() => ({ tasks: [] })),
          api.getProjects().catch(() => [])
        ]);
        setAgents(agentsRes.agents || []);
        setTasks(tasksRes.tasks || []);
        setProjects(projectsRes || []);
      } catch (e) {
        console.error('HomePanel load error:', e);
      } finally {
        setLoading(false);
      }
    };
    fetchDashboard();
    const interval = setInterval(fetchDashboard, 10000);
    return () => clearInterval(interval);
  }, []);

  const activeTasks = tasks.filter(t => ['RUNNING', 'READY', 'VERIFYING'].includes(t.status));

  return (
    <Panel id="home" title="AEGIS Command Center" icon={<Target className="w-4 h-4 text-amber-400" />} tag="Overview">
      <div className="flex flex-col gap-4 p-4 h-full overflow-y-auto text-neutral-300">
        
        {/* Top metrics */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <MetricCard title="Active Agents" value={agents.filter(a => a.status === 'RUNNING').length} icon={<Zap className="w-4 h-4" />} color="amber" />
          <MetricCard title="Active Tasks" value={activeTasks.length} icon={<Activity className="w-4 h-4" />} color="blue" />
          <MetricCard title="Tracked Projects" value={projects.length} icon={<Server className="w-4 h-4" />} color="purple" />
          <MetricCard title="System Health" value="NOMINAL" icon={<CheckCircle className="w-4 h-4" />} color="amber" />
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 flex-1">
          {/* Active Tasks */}
          <div className="glass-panel rounded-md border border-white/10 flex flex-col overflow-hidden">
            <div className="px-3 py-2 border-b border-white/10 bg-white/5 font-semibold text-white flex items-center gap-2">
              <Activity className="w-4 h-4 text-amber-400" />
              Active Tasks
            </div>
            <div className="p-3 flex-1 overflow-y-auto space-y-2">
              {activeTasks.length === 0 ? (
                <div className="text-neutral-500 text-sm text-center py-6">No active tasks. Systems standing by.</div>
              ) : (
                activeTasks.map((t, i) => (
                  <div key={i} className="bg-white/5 border border-white/5 rounded p-2 text-xs flex justify-between items-center hover:border-amber-400/50 transition-colors">
                    <div>
                      <div className="font-medium text-white mb-0.5">{t.description || t.id}</div>
                      <div className="text-neutral-500">{t.project_id || 'Global Scope'}</div>
                    </div>
                    <span className="px-2 py-1 bg-amber-500/20 text-amber-400 rounded-sm">{t.status}</span>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Agents */}
          <div className="glass-panel rounded-md border border-white/10 flex flex-col overflow-hidden">
            <div className="px-3 py-2 border-b border-white/10 bg-white/5 font-semibold text-white flex items-center gap-2">
              <Cpu className="w-4 h-4 text-amber-400" />
              Execution Capabilities
            </div>
            <div className="p-3 flex-1 overflow-y-auto space-y-2">
              {agents.map((a, i) => (
                <div key={i} className="bg-white/5 border border-white/5 rounded p-2 text-xs flex justify-between items-center cursor-pointer hover:border-amber-400/50" onClick={() => togglePanel('agents')}>
                  <div className="flex items-center gap-2">
                    <span className={`w-2 h-2 rounded-full ${a.status === 'RUNNING' ? 'bg-amber-400 animate-pulse-live' : 'bg-neutral-600'}`} />
                    <span className="font-medium text-white">{a.name}</span>
                  </div>
                  <span className="text-neutral-500 font-mono text-[10px]">{a.type}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

      </div>
    </Panel>
  );
};

const MetricCard = ({ title, value, icon, color }: any) => (
  <div className="glass-panel p-3 rounded-md border border-white/10 flex flex-col gap-1">
    <div className={`text-${color}-400 flex items-center gap-1.5 opacity-80 text-xs uppercase tracking-wider font-semibold`}>
      {icon} {title}
    </div>
    <div className="text-2xl font-bold text-white tracking-tight">{value}</div>
  </div>
);
