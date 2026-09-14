/**
 * AEGIS AI OS Dashboard — API Client
 * Connects to FastAPI backend on http://127.0.0.1:8787 (or via Vite dev proxy /api)
 */

export interface VaultNode {
  type: 'dir' | 'file';
  children?: string[];
  size?: number;
  modified?: string;
}

export interface VaultStructure {
  [name: string]: VaultNode;
}

export interface MemoryFile {
  path: string;
  name: string;
  size: number;
  modified: string;
}

export interface FileContent {
  content: string;
  path: string;
  name: string;
  size: number;
  modified: string;
}

export interface SearchResult {
  path: string;
  name: string;
  context: string;
  line: number;
}

export interface MOCItem {
  path: string;
  title: string;
  preview: string;
}

export interface ProjectItem {
  path: string;
  name?: string;
  title: string;
  status?: string;
  preview: string;
}

export interface SkillItem {
  name: string;
  version?: string;
  category?: string;
  purpose?: string;
  description?: string;
  inputs?: string[];
  outputs?: string[];
  required_tools?: string[];
  permissions?: string[];
  workflow?: string[];
  failure_modes?: string[];
  verification?: string[];
  confidence?: number;
  tests?: string[];
}

export interface CuratedModel {
  role?: string;
  context_window?: number;
  max_output?: number;
  reasoning?: boolean;
  tools?: boolean;
  vision?: boolean;
  thinking_format?: string;
  source?: string;
  notes?: string;
}

export interface ModelRegistryData {
  generated_at?: string;
  total_available?: number;
  "9router_url"?: string;
  hermes_default?: {
    model: string;
    provider: string;
    base_url: string;
  };
  routing_table?: Record<string, string>;
  curated_models?: Record<string, CuratedModel>;
  tiered_groups?: Record<string, {
    id: string;
    name: string;
    description: string;
    primary: string;
    fallback: string;
    target_agent: string;
    context_window?: number;
  }>;
}

export interface AgentItem {
  id: string;
  name: string;
  type: string;
  repo?: string;
  cli?: string;
  command?: string;
  profile?: string;
  installed?: boolean;
  default_model?: string;
  modes?: string[];
  runs_in?: string;
  config?: string;
  dashboard_tab?: string;
  icon?: string;
  description?: string;
}

export interface TaskClassification {
  domain: string;
  complexity: string;
  tier_id: string;
  tier_name: string;
  primary: string;
  fallback: string;
  target_agent: string;
  target_tab: string;
}

export interface ToolItem {
  identity?: string;
  capability?: string;
  schema?: string;
  permissions?: string[];
  risk?: 'low' | 'medium' | 'high';
  trust?: string;
  availability?: string;
  health?: string;
  provider?: string;
  notes?: string;
}

export interface ToolRegistryData {
  generated_at?: string;
  description?: string;
  tools?: Record<string, ToolItem>;
}

export interface PCProcess {
  user: string;
  pid: string;
  cpu: string;
  mem: string;
  vsz: string;
  rss: string;
  command: string;
}

export interface PCState {
  timestamp: string;
  system: Record<string, string>;
  memory: {
    total_kb: number;
    free_kb: number;
    available_kb: number;
    used_kb: number;
  };
  disk: {
    filesystem: string;
    size: string;
    used: string;
    avail: string;
    use_percent: string;
    mounted: string;
  };
  processes: PCProcess[];
  network: Record<string, {
    type: string;
    state: string;
    addresses: string[];
  }>;
  ports: Array<{
    state: string;
    recv_q: string;
    send_q: string;
    local_addr: string;
    peer: string;
    process: string;
  }>;
}

export interface RouterHealth {
  status: 'running' | 'stopped' | 'error';
  code?: number;
}

export interface ScriptRunResult {
  success: boolean;
  stdout: string;
  stderr: string;
  returncode: number;
  error?: string;
}

export interface ChatMessage {
  id: string;
  sender: 'user' | 'ai' | 'system';
  content: string;
  timestamp: string;
  model?: string;
  contextUsed?: string[];
  classification?: TaskClassification;
}

const API_BASE = '/api';

async function fetchJson<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE}${endpoint}`;
  const res = await fetch(url, options);
  if (!res.ok) {
    throw new Error(`API Error ${res.status}: ${res.statusText}`);
  }
  return res.json();
}

export const api = {
  // Vault
  getVaultStructure: () => fetchJson<VaultStructure>('/vault'),
  getMemoryFiles: () => fetchJson<MemoryFile[]>('/memory-files'),
  getFile: (relPath: string) => fetchJson<FileContent>(`/file/${encodeURIComponent(relPath)}`),
  searchVault: (q: string) => fetchJson<SearchResult[]>(`/search?q=${encodeURIComponent(q)}`),
  getMOCs: () => fetchJson<MOCItem[]>('/mocs'),
  getProjects: () => fetchJson<ProjectItem[]>('/projects'),

  // Registries & Agents
  getSkills: () => fetchJson<Record<string, SkillItem>>('/skills'),
  getModels: () => fetchJson<ModelRegistryData>('/models'),
  getTools: () => fetchJson<ToolRegistryData>('/tools'),
  getAgents: () => fetchJson<{ agents: AgentItem[] }>('/agents'),
  startAgent: (name: string) => fetchJson<{ status: string; agent: string }>(`/agent/${name}/start`, { method: 'POST' }),
  stopAgent: (name: string) => fetchJson<{ status: string; agent: string }>(`/agent/${name}/stop`, { method: 'POST' }),
  restartAgent: (name: string) => fetchJson<{ status: string; agent: string }>(`/agent/${name}/restart`, { method: 'POST' }),
  getAgentStatus: (name: string) => fetchJson<{ agent: string; running: boolean }>(`/agent/${name}/status`),

  // System
  getPCState: () => fetchJson<PCState>('/pc-state'),
  get9RouterHealth: () => fetchJson<RouterHealth>('/9router-health'),

  // Scripts
  runScript: (script: string) =>
    fetchJson<ScriptRunResult>('/run-script', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ script }),
    }),

  // Chat with Orchestrator classification
  sendChatMessage: (message: string, history: Array<{ role: string; content: string }> = [], model?: string) =>
    fetchJson<{ content: string; timestamp: string; model?: string; classification?: TaskClassification }>('/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message, history, model }),
    }),

  // Memories & Config
  getAgiesMemories: () => fetchJson<Array<{ path: string; name: string; size: number; content: string }>>('/agies-memories'),
  getConfigFiles: () => fetchJson<Array<{ path: string; name: string; preview: string }>>('/config-files'),
  getChatGPTTracking: () => fetchJson<Record<string, unknown>>('/chatgpt-tracking'),
};

// WebSocket real-time subscription
export type WebSocketMessage = 
  | { type: 'connected'; session_id: string; timestamp: string }
  | { type: 'pc_update'; data: PCState }
  | { type: 'script_result'; script: string; result: ScriptRunResult }
  | { type: 'initial_data'; [key: string]: unknown };

export class RealtimeSocket {
  private ws: WebSocket | null = null;
  private listeners: Array<(msg: WebSocketMessage) => void> = [];
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  public isConnected = false;

  constructor() {
    this.connect();
  }

  public connect() {
    if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
      return;
    }

    // Determine host: either via window location or fallback
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    const wsUrl = `${protocol}//${host}/ws`;

    try {
      this.ws = new WebSocket(wsUrl);

      this.ws.onopen = () => {
        this.isConnected = true;
      };

      this.ws.onmessage = (event) => {
        try {
          const data: WebSocketMessage = JSON.parse(event.data);
          this.listeners.forEach((fn) => fn(data));
        } catch {
          // parse error ignored
        }
      };

      this.ws.onclose = () => {
        this.isConnected = false;
        this.scheduleReconnect();
      };

      this.ws.onerror = () => {
        this.isConnected = false;
        this.ws?.close();
      };
    } catch {
      this.scheduleReconnect();
    }
  }

  private scheduleReconnect() {
    if (this.reconnectTimer) return;
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this.connect();
    }, 4000);
  }

  public subscribe(callback: (msg: WebSocketMessage) => void) {
    this.listeners.push(callback);
    return () => {
      this.listeners = this.listeners.filter((fn) => fn !== callback);
    };
  }

  public send(data: object) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data));
    }
  }
}

export const realtimeSocket = new RealtimeSocket();
