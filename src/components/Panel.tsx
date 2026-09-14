import React, { ReactNode } from 'react';
import { useOS, PanelId } from '../lib/store';
import { X, Square, Minus } from 'lucide-react';

interface PanelProps {
  id: PanelId;
  title: string;
  icon?: ReactNode;
  tag?: string;
  children: ReactNode;
  className?: string;
  headerRight?: ReactNode;
}

export const Panel: React.FC<PanelProps> = ({
  id,
  title,
  icon,
  tag,
  children,
  className = '',
  headerRight,
}) => {
  const { activePanel, maximizedPanel, focusPanel, closePanel, toggleMaximize } = useOS();

  const isFocused = activePanel === id;
  const isMaximized = maximizedPanel === id;

  return (
    <div
      onClick={() => focusPanel(id)}
      className={`flex flex-col bg-[#1a1a1a] border transition-os select-text overflow-hidden ${
        isFocused ? 'border-[#404040] bg-[#1d1d1d]' : 'border-[#2e2e2e]'
      } ${
        isMaximized
          ? 'fixed inset-x-2 top-10 bottom-12 z-40'
          : 'relative h-full w-full'
      } ${className}`}
      style={{
        boxShadow: isFocused ? '0 2px 8px rgba(0,0,0,0.6)' : '0 1px 3px rgba(0,0,0,0.4)',
      }}
    >
      {/* Title Bar (28px height) */}
      <div
        onDoubleClick={() => toggleMaximize(id)}
        className={`h-7 px-2.5 flex items-center justify-between border-b transition-os select-none cursor-default ${
          isFocused ? 'bg-[#222222] border-[#383838]' : 'bg-[#181818] border-[#262626]'
        }`}
      >
        {/* Left: Icon & Title */}
        <div className="flex items-center space-x-2 min-w-0">
          {icon && <span className="text-[#a0a0a0] flex items-center shrink-0">{icon}</span>}
          <span className="font-mono text-xs font-medium text-[#e8e8e8] truncate">
            {title}
          </span>
          {tag && (
            <span className="font-mono text-[10px] uppercase tracking-wider px-1.5 py-0.2 bg-[#262626] text-[#888888] border border-[#333333]">
              {tag}
            </span>
          )}
        </div>

        {/* Right: Custom actions + standard OS controls */}
        <div className="flex items-center space-x-1.5 shrink-0 ml-2" onClick={(e) => e.stopPropagation()}>
          {headerRight}
          <button
            onClick={() => toggleMaximize(id)}
            title={isMaximized ? 'Restore' : 'Maximize'}
            className="w-5 h-5 flex items-center justify-center text-[#888888] hover:text-[#e8e8e8] hover:bg-[#2a2a2a] transition-os"
          >
            <Square className="w-3 h-3" />
          </button>
          <button
            onClick={() => closePanel(id)}
            title="Close Panel"
            className="w-5 h-5 flex items-center justify-center text-[#888888] hover:text-[#c55] hover:bg-[#2a2a2a] transition-os"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Window Body */}
      <div className="flex-1 overflow-hidden relative flex flex-col">
        {children}
      </div>
    </div>
  );
};
