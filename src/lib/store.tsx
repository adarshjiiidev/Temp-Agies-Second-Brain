import React, { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react';
import { api, PCState, RouterHealth, realtimeSocket, ScriptRunResult } from './api';

export type PanelId = 'home' | 'chat' | 'vault' | 'graph' | 'agents' | 'pc' | 'skills' | 'models' | 'tools' | 'activity' | 'quickactions' | 'tasks' | 'system' | 'voice' | 'doctor';

export interface ActivityEvent {
  id: string;
  type: 'snapshot' | 'chatgpt' | 'pattern' | 'chat' | 'script' | 'system';
  title: string;
  description: string;
  timestamp: string;
  status: 'ok' | 'warn' | 'error' | 'info';
}

interface OSContextType {
  // Window states
  openPanels: Record<PanelId, boolean>;
  activePanel: PanelId | null;
  maximizedPanel: PanelId | null;
  openPanel: (id: PanelId) => void;
  closePanel: (id: PanelId) => void;
  togglePanel: (id: PanelId) => void;
  focusPanel: (id: PanelId) => void;
  toggleMaximize: (id: PanelId) => void;

  // Agent CLI Multiplexer states
  activeAgentTab: string;
  setActiveAgentTab: (tabId: string) => void;
  openAgentTab: (agentId: string) => void;

  // Vault navigation
  targetVaultFile: string | null;
  setTargetVaultFile: (path: string | null) => void;
  openNoteInVault: (path: string) => void;

  // System stats & health
  pcState: PCState | null;
  routerHealth: RouterHealth | null;
  isSocketConnected: boolean;
  refreshPCState: () => Promise<void>;

  // Activity Feed
  activities: ActivityEvent[];
  addActivity: (event: Omit<ActivityEvent, 'id' | 'timestamp'>) => void;

  // Global Search modal
  isSearchOpen: boolean;
  setSearchOpen: (open: boolean) => void;
  searchQuery: string;
  setSearchQuery: (query: string) => void;

  // Quick Action execution state
  runningScript: string | null;
  scriptLogs: Record<string, ScriptRunResult>;
  executeScript: (scriptName: string) => Promise<ScriptRunResult>;
  isQuickActionsOpen: boolean;
  setQuickActionsOpen: (open: boolean) => void;

  // Codex Side-Panel state
  codexOpen: boolean;
  setCodexOpen: (open: boolean) => void;
  codexPrompt: string;
  setCodexPrompt: (prompt: string) => void;
}

const OSContext = createContext<OSContextType | null>(null);

export const OSProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [openPanels, setOpenPanels] = useState<Record<PanelId, boolean>>({
    home: true,
    chat: true,
    vault: true,
    graph: false,
    agents: false,
    pc: false,
    skills: false,
    models: false,
    tools: false,
    activity: false,
    quickactions: false,
    tasks: false,
    system: false,
    voice: false,
    doctor: false,
  });

  const [activePanel, setActivePanel] = useState<PanelId | null>('chat');
  const [maximizedPanel, setMaximizedPanel] = useState<PanelId | null>(null);
  const [targetVaultFile, setTargetVaultFile] = useState<string | null>(null);
  const [activeAgentTab, setActiveAgentTab] = useState<string>('hermes');

  const openAgentTab = useCallback((agentId: string) => {
    setActiveAgentTab(agentId);
    setOpenPanels((prev) => ({ ...prev, agents: true }));
    setActivePanel('agents');
  }, []);

  const openNoteInVault = useCallback((path: string) => {
    setTargetVaultFile(path);
    setOpenPanels((prev) => ({ ...prev, vault: true }));
    setActivePanel('vault');
  }, []);

  const [pcState, setPcState] = useState<PCState | null>(null);
  const [routerHealth, setRouterHealth] = useState<RouterHealth | null>(null);
  const [isSocketConnected, setIsSocketConnected] = useState(false);

  const [activities, setActivities] = useState<ActivityEvent[]>([]);
  const [isSearchOpen, setSearchOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');

  const [runningScript, setRunningScript] = useState<string | null>(null);
  const [scriptLogs, setScriptLogs] = useState<Record<string, ScriptRunResult>>({});
  const [isQuickActionsOpen, setQuickActionsOpen] = useState(false);

  const [codexOpen, setCodexOpen] = useState(false);
  const [codexPrompt, setCodexPrompt] = useState('');

  const addActivity = useCallback((event: Omit<ActivityEvent, 'id' | 'timestamp'>) => {
    const newAct: ActivityEvent = {
      ...event,
      id: `act-${Date.now()}-${Math.random().toString(36).substring(2, 6)}`,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
    };
    setActivities((prev) => [newAct, ...prev.slice(0, 49)]);
  }, []);

  const openPanel = useCallback((id: PanelId) => {
    setOpenPanels((prev) => ({ ...prev, [id]: true }));
    setActivePanel(id);
  }, []);

  const closePanel = useCallback((id: PanelId) => {
    setOpenPanels((prev) => ({ ...prev, [id]: false }));
    if (maximizedPanel === id) {
      setMaximizedPanel(null);
    }
    setActivePanel((prev) => (prev === id ? null : prev));
  }, [maximizedPanel]);

  const togglePanel = useCallback((id: PanelId) => {
    setOpenPanels((prev) => {
      const next = !prev[id];
      if (next) {
        setActivePanel(id);
      } else if (activePanel === id) {
        setActivePanel(null);
      }
      return { ...prev, [id]: next };
    });
  }, [activePanel]);

  const focusPanel = useCallback((id: PanelId) => {
    setActivePanel(id);
    setOpenPanels((prev) => ({ ...prev, [id]: true }));
  }, []);

  const toggleMaximize = useCallback((id: PanelId) => {
    setMaximizedPanel((prev) => (prev === id ? null : id));
    setActivePanel(id);
  }, []);

  const refreshPCState = useCallback(async () => {
    try {
      const state = await api.getPCState();
      setPcState(state);
    } catch {
      // ignore
    }
  }, []);

  const executeScript = useCallback(async (scriptName: string): Promise<ScriptRunResult> => {
    setRunningScript(scriptName);
    addActivity({
      type: 'script',
      title: `Executing ${scriptName}`,
      description: `Dispatched background script task via AEGIS kernel.`,
      status: 'info',
    });

    try {
      const res = await api.runScript(scriptName);
      setScriptLogs((prev) => ({ ...prev, [scriptName]: res }));
      addActivity({
        type: 'script',
        title: `${scriptName} ${res.success ? 'Completed' : 'Failed'}`,
        description: res.success ? `Exit code 0. Finished successfully.` : `Error: ${res.error || res.stderr || 'Non-zero exit'}`,
        status: res.success ? 'ok' : 'error',
      });
      return res;
    } catch (err: unknown) {
      const errorMsg = err instanceof Error ? err.message : String(err);
      const failRes: ScriptRunResult = {
        success: false,
        stdout: '',
        stderr: errorMsg,
        returncode: 1,
        error: errorMsg,
      };
      setScriptLogs((prev) => ({ ...prev, [scriptName]: failRes }));
      addActivity({
        type: 'script',
        title: `${scriptName} Error`,
        description: errorMsg,
        status: 'error',
      });
      return failRes;
    } finally {
      setRunningScript(null);
    }
  }, [addActivity]);

  // Initial load & periodic health checks
  useEffect(() => {
    refreshPCState();
    api.getModelHealth().then(setRouterHealth).catch(() => setRouterHealth({ status: 'stopped' }));

    const pcInterval = setInterval(refreshPCState, 30000);
    const healthInterval = setInterval(() => {
      api.getModelHealth().then(setRouterHealth).catch(() => setRouterHealth({ status: 'stopped' }));
    }, 45000);

    // WebSocket subscription
    const unsubscribe = realtimeSocket.subscribe((msg) => {
      setIsSocketConnected(true);
      if (msg.type === 'pc_update') {
        setPcState(msg.data);
      } else if (msg.type === 'script_result') {
        setScriptLogs((prev) => ({ ...prev, [msg.script]: msg.result }));
      }
    });

    return () => {
      clearInterval(pcInterval);
      clearInterval(healthInterval);
      unsubscribe();
    };
  }, [refreshPCState]);

  // Global keyboard shortcuts (Cmd+K / Ctrl+K for search, Esc to close modals)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setSearchOpen((prev) => !prev);
      } else if (e.key === 'Escape') {
        if (isSearchOpen) setSearchOpen(false);
        if (isQuickActionsOpen) setQuickActionsOpen(false);
        if (codexOpen) setCodexOpen(false);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isSearchOpen, isQuickActionsOpen, codexOpen]);

  return (
    <OSContext.Provider
      value={{
        openPanels,
        activePanel,
        maximizedPanel,
        openPanel,
        closePanel,
        togglePanel,
        focusPanel,
        toggleMaximize,
        targetVaultFile,
        setTargetVaultFile,
        openNoteInVault,
        activeAgentTab,
        setActiveAgentTab,
        openAgentTab,
        pcState,
        routerHealth,
        isSocketConnected,
        refreshPCState,
        activities,
        addActivity,
        isSearchOpen,
        setSearchOpen,
        searchQuery,
        setSearchQuery,
        runningScript,
        scriptLogs,
        executeScript,
        isQuickActionsOpen,
        setQuickActionsOpen,
        codexOpen,
        setCodexOpen,
        codexPrompt,
        setCodexPrompt,
      }}
    >
      {children}
    </OSContext.Provider>
  );
};

export const useOS = () => {
  const ctx = useContext(OSContext);
  if (!ctx) {
    throw new Error('useOS must be used within an OSProvider');
  }
  return ctx;
};
