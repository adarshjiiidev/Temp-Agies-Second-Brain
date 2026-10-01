import React from 'react';
import { Panel } from './Panel';
import { useOS, ActivityEvent } from '../lib/store';
import {
  Clock,
  Camera,
  Bot,
  Brain,
  Terminal,
  Activity,
  CheckCircle,
  AlertTriangle,
  Info,
} from 'lucide-react';

export const ActivityFeed: React.FC = () => {
  const { activities } = useOS();

  const getEventIcon = (type: ActivityEvent['type']) => {
    switch (type) {
      case 'snapshot':
        return <Camera className="w-3.5 h-3.5 text-amber-400" />;
      case 'chatgpt':
        return <Bot className="w-3.5 h-3.5 text-sky-400" />;
      case 'pattern':
        return <Brain className="w-3.5 h-3.5 text-purple-400" />;
      case 'script':
        return <Terminal className="w-3.5 h-3.5 text-amber-400" />;
      default:
        return <Activity className="w-3.5 h-3.5 text-zinc-400" />;
    }
  };

  const getStatusBadge = (status: ActivityEvent['status']) => {
    switch (status) {
      case 'ok':
        return <CheckCircle className="w-3 h-3 text-amber-400" />;
      case 'warn':
        return <AlertTriangle className="w-3 h-3 text-amber-400" />;
      case 'error':
        return <AlertTriangle className="w-3 h-3 text-red-400" />;
      default:
        return <Info className="w-3 h-3 text-sky-400" />;
    }
  };

  return (
    <Panel
      id="activity"
      title="System Activity Feed"
      icon={<Clock className="w-3.5 h-3.5 text-zinc-400" />}
      tag={`${activities.length} Events`}
    >
      <div className="flex-1 overflow-y-auto p-4 space-y-3 bg-[#0e0e11] font-mono text-xs select-text">
        {activities.map((act) => (
          <div
            key={act.id}
            className="glass-panel p-3 rounded-sm space-y-1.5 hover:border-white/20 transition-os"
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2">
                {getEventIcon(act.type)}
                <span className="font-semibold text-white text-xs">{act.title}</span>
              </div>
              <div className="flex items-center space-x-2 text-[10px] text-zinc-500">
                {getStatusBadge(act.status)}
                <span>{act.timestamp}</span>
              </div>
            </div>

            <p className="text-[11px] text-zinc-400 leading-relaxed pl-5">
              {act.description}
            </p>
          </div>
        ))}
      </div>
    </Panel>
  );
};
