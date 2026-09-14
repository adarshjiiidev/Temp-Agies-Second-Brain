import React from 'react';
import { useOS, PanelId } from '../lib/store';
import { ChatPanel } from './ChatPanel';
import { VaultExplorer } from './VaultExplorer';
import { ObsidianGraph } from './ObsidianGraph';
import { PCMonitor } from './PCMonitor';
import { SkillsPanel } from './SkillsPanel';
import { ModelsPanel } from './ModelsPanel';
import { ToolsPanel } from './ToolsPanel';
import { ActivityFeed } from './ActivityFeed';
import { QuickActions } from './QuickActions';
import { GlobalSearchModal } from './GlobalSearchModal';
import { CodexModal } from './CodexModal';
import { AgentTabs } from './AgentTabs';

export const Desktop: React.FC = () => {
  const { openPanels, activePanel, maximizedPanel, focusPanel } = useOS();

  // Panels list for secondary small panels
  const secondaryPanels: { id: PanelId; component: React.ReactNode }[] = [
    { id: 'graph', component: <ObsidianGraph /> },
    { id: 'pc', component: <PCMonitor /> },
    { id: 'skills', component: <SkillsPanel /> },
    { id: 'models', component: <ModelsPanel /> },
    { id: 'tools', component: <ToolsPanel /> },
    { id: 'activity', component: <ActivityFeed /> },
  ];

  const activeSecondary = secondaryPanels.filter((p) => openPanels[p.id]);

  // Determine whether to show AgentTabs or Vault in the primary right workspace
  const showAgents = openPanels.agents;
  const showVault = openPanels.vault;

  return (
    <main className="flex-1 w-full h-[calc(100vh-72px)] overflow-hidden relative p-2 cyber-grid">
      {/* If any panel is maximized, it takes full canvas */}
      {maximizedPanel ? (
        <div className="w-full h-full">
          {maximizedPanel === 'chat' && <ChatPanel />}
          {maximizedPanel === 'agents' && <AgentTabs />}
          {maximizedPanel === 'vault' && <VaultExplorer />}
          {maximizedPanel === 'graph' && <ObsidianGraph />}
          {maximizedPanel === 'pc' && <PCMonitor />}
          {maximizedPanel === 'skills' && <SkillsPanel />}
          {maximizedPanel === 'models' && <ModelsPanel />}
          {maximizedPanel === 'tools' && <ToolsPanel />}
          {maximizedPanel === 'activity' && <ActivityFeed />}
        </div>
      ) : (
        // Standard Desktop Tiling Grid
        <div className="w-full h-full flex flex-col md:flex-row gap-2 overflow-hidden">
          {/* Left Column: Hermes AI Chat Assistant */}
          {openPanels.chat && (
            <div
              className={`h-full transition-os ${
                showVault || showAgents || activeSecondary.length > 0
                  ? 'w-full md:w-[45%] lg:w-[42%]'
                  : 'w-full'
              }`}
            >
              <ChatPanel />
            </div>
          )}

          {/* Right Column / Primary Workspace: Agent CLIs, Vault & Secondary Panels */}
          {(showVault || showAgents || activeSecondary.length > 0) && (
            <div className="flex-1 h-full flex flex-col gap-2 overflow-hidden min-w-0">
              {/* If both Vault and Agents are open, show workspace tab switcher */}
              {showVault && showAgents && (
                <div className="flex items-center gap-1 px-1 bg-black/40 border border-white/10 rounded-md p-1 shrink-0 text-xs">
                  <button
                    onClick={() => focusPanel('agents')}
                    className={`px-3 py-1 rounded transition-colors ${
                      activePanel === 'agents'
                        ? 'bg-white/15 text-emerald-400 font-medium'
                        : 'text-neutral-400 hover:text-white'
                    }`}
                  >
                    🖥️ Agent CLIs (PTY)
                  </button>
                  <button
                    onClick={() => focusPanel('vault')}
                    className={`px-3 py-1 rounded transition-colors ${
                      activePanel === 'vault'
                        ? 'bg-white/15 text-white font-medium'
                        : 'text-neutral-400 hover:text-white'
                    }`}
                  >
                    📁 PARA Vault
                  </button>
                </div>
              )}

              {/* Primary View: AgentTabs or Vault */}
              {(showAgents || showVault) && (
                <div
                  className={`w-full transition-os min-h-0 ${
                    activeSecondary.length > 0 ? 'h-[60%]' : 'h-full'
                  }`}
                >
                  {showAgents && (!showVault || activePanel === 'agents') ? (
                    <AgentTabs />
                  ) : showVault ? (
                    <VaultExplorer />
                  ) : (
                    <AgentTabs />
                  )}
                </div>
              )}

              {/* Secondary Active Panels Strip / Grid */}
              {activeSecondary.length > 0 && (
                <div
                  className={`w-full grid gap-2 transition-os min-h-0 ${
                    !showVault && !showAgents
                      ? 'h-full grid-cols-1 md:grid-cols-2'
                      : 'h-[40%] grid-cols-1 md:grid-cols-2'
                  }`}
                >
                  {activeSecondary.map((p) => (
                    <div key={p.id} className="h-full min-h-0 min-w-0">
                      {p.component}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Global Modals & Drawers */}
      <QuickActions />
      <GlobalSearchModal />
      <CodexModal />
    </main>
  );
};
