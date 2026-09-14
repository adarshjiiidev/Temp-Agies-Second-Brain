import React from 'react';
import { useOS, PanelId } from '../lib/store';
import {
  MessageSquare,
  FolderTree,
  Cpu,
  Boxes,
  Compass,
  Wrench,
  Zap,
  Clock,
  Share2,
  Terminal,
} from 'lucide-react';

interface DockItem {
  id: PanelId;
  label: string;
  icon: React.ReactNode;
  shortcut: string;
}

export const Dock: React.FC = () => {
  const { openPanels, activePanel, togglePanel, focusPanel, setQuickActionsOpen } = useOS();

  const dockItems: DockItem[] = [
    { id: 'chat', label: 'Chat', icon: <MessageSquare className="w-4 h-4" />, shortcut: '1' },
    { id: 'vault', label: 'Vault', icon: <FolderTree className="w-4 h-4" />, shortcut: '2' },
    { id: 'graph', label: 'Graph', icon: <Share2 className="w-4 h-4 text-[#38bdf8]" />, shortcut: '3' },
    { id: 'agents', label: 'Agent CLIs', icon: <Terminal className="w-4 h-4 text-emerald-400" />, shortcut: '4' },
    { id: 'pc', label: 'PC Mon', icon: <Cpu className="w-4 h-4" />, shortcut: '5' },
    { id: 'skills', label: 'Skills', icon: <Compass className="w-4 h-4" />, shortcut: '6' },
    { id: 'models', label: 'Models', icon: <Boxes className="w-4 h-4" />, shortcut: '7' },
    { id: 'tools', label: 'Tools', icon: <Wrench className="w-4 h-4" />, shortcut: '8' },
    { id: 'activity', label: 'Feed', icon: <Clock className="w-4 h-4" />, shortcut: '9' },
  ];

  const handleDockClick = (id: PanelId) => {
    if (!openPanels[id]) {
      focusPanel(id);
    } else if (activePanel === id) {
      togglePanel(id);
    } else {
      focusPanel(id);
    }
  };

  return (
    <footer className="h-10 bg-[#121212] border-t border-[#262626] px-4 flex items-center justify-between z-30 select-none shrink-0 font-mono text-xs">
      {/* Left: Quick System info badge */}
      <div className="flex items-center space-x-2 text-[#666666] text-[11px]">
        <span>AEGIS OS</span>
        <span className="text-[#333333]">|</span>
        <span className="text-[#888888]">Ready</span>
      </div>

      {/* Center: Main Dock Buttons */}
      <div className="flex items-center space-x-1.5">
        {dockItems.map((item) => {
          const isOpen = openPanels[item.id];
          const isActive = activePanel === item.id;

          return (
            <button
              key={item.id}
              onClick={() => handleDockClick(item.id)}
              className={`h-7 px-3 flex items-center space-x-2 border transition-os relative ${
                isActive
                  ? 'bg-[#262626] border-[#404040] text-[#e8e8e8]'
                  : isOpen
                  ? 'bg-[#1c1c1c] border-[#303030] text-[#a0a0a0] hover:text-[#e8e8e8] hover:bg-[#222222]'
                  : 'bg-transparent border-transparent text-[#666666] hover:text-[#a0a0a0] hover:bg-[#181818]'
              }`}
              title={`Toggle ${item.label}`}
            >
              <span className={isActive ? 'text-[#e8e8e8]' : isOpen ? 'text-[#aaaaaa]' : 'text-[#666666]'}>
                {item.icon}
              </span>
              <span className="text-xs font-medium">{item.label}</span>

              {/* Active Dot indicator under icon */}
              {isOpen && (
                <span
                  className={`absolute bottom-0.5 left-1/2 -translate-x-1/2 w-1 h-1 ${
                    isActive ? 'bg-[#e8e8e8]' : 'bg-[#666666]'
                  }`}
                />
              )}
            </button>
          );
        })}

        <div className="h-4 w-px bg-[#262626] mx-1" />

        {/* Quick Actions Drawer Trigger */}
        <button
          onClick={() => setQuickActionsOpen(true)}
          className="h-7 px-2.5 flex items-center space-x-1.5 border border-[#2e2e2e] bg-[#1a1a1a] hover:bg-[#242424] text-[#a0a0a0] hover:text-[#e8e8e8] transition-os"
          title="Open Quick Actions panel"
        >
          <Zap className="w-3.5 h-3.5 text-[#c9a]" />
          <span className="text-xs">Quick Scripts</span>
        </button>
      </div>

      {/* Right: Shortcuts & Status */}
      <div className="flex items-center space-x-3 text-[11px] text-[#666666]">
        <span>⌘K: Search</span>
        <span className="text-[#333333]">|</span>
        <span className="text-[#4a9]">System Normal</span>
      </div>
    </footer>
  );
};
