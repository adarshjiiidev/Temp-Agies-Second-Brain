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
  status: 'running' | 'online' | 'stopped' | 'error' | 'degraded';
  code?: number;
  openrouter?: boolean;
  groq?: boolean;
  active_free_models?: number;
  available_models?: number;
  engine?: string;
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

export interface KnowledgeGraphNode {
  id: string;
  label: string;
  type: string;
  metadata?: Record<string, unknown>;
}

export interface KnowledgeGraphEdge {
  source: string;
  target: string;
  relation: string;
}

export interface KnowledgeGraphData {
  nodes: KnowledgeGraphNode[];
  edges: KnowledgeGraphEdge[];
  counts: Record<string, number>;
}

export interface ObsidianGraphNode {
  id: string;
  name: string;
  path: string;
  category: 'projects' | 'areas' | 'resources' | 'archives' | 'mocs';
  size: number;
}

export interface ObsidianGraphData {
  nodes: ObsidianGraphNode[];
  edges: KnowledgeGraphEdge[];
}

// ── Phase 6: AEGIS Unified Task Board ─────────────────────────────────────────
export interface AegisTask {
  id: string;
  status: 'BACKLOG' | 'READY' | 'RUNNING' | 'BLOCKED' | 'VERIFYING' | 'DONE' | 'FAILED' | 'NOT_CONFIGURED';
  task: string;
  project: string;
  kind: string;
  parallelism: number;
  long_horizon: boolean;
  created_at: number;
  updated_at: number;
  selected?: { id: string; name: string; status: string; score: number };
  result?: Record<string, unknown>;
  events?: Array<{ at: number; type: string; actor: string }>;
}

// ── Phase 7: Unified Skills Registry ─────────────────────────────────────────
export interface UnifiedSkill {
  id: string;
  name: string;
  description: string;
  category: string;
  requirements: string[];
  tools: string[];
  risk: string;
  permissions: string[];
  source: string; // 'ECC' | 'FrontierAgent' | 'Multica' | 'AEGIS' | 'VoiceStudio'
}

// ── Phase 4: Voice Status ─────────────────────────────────────────────────────
export interface VoiceStatus {
  engine: string;
  available: boolean;
  mic_state: 'OFF' | 'READY' | 'LISTENING' | 'PROCESSING';
  tts_state: 'IDLE' | 'SPEAKING';
  recent_transcripts: Array<{ text: string; timestamp: number }>;
}

// ── Phase 10: System Graph ─────────────────────────────────────────────────────
export interface SystemGraphNode {
  id: string;
  label: string;
  type: 'core' | 'executor' | 'memory' | 'skill' | 'ide' | 'capability';
  status: string;
  implementation?: string;
  description?: string;
}

export interface SystemGraphData {
  nodes: SystemGraphNode[];
  edges: Array<{ source: string; target: string; label?: string }>;
}

// ── Phase 16: AEGIS Doctor ─────────────────────────────────────────────────────
export interface DoctorCheck {
  name: string;
  status: 'PASS' | 'WARN' | 'FAIL' | 'NOT_CONFIGURED' | 'NOT_SUPPORTED';
  message?: string;
}

// ── Phase 5: IDE Adapters ─────────────────────────────────────────────────────
export interface IdeAdapterInfo {
  id: string;
  name: string;
  installed: boolean;
  status: 'AVAILABLE' | 'NOT_CONFIGURED' | 'RUNNING' | 'FAILED';
  capabilities: string[];
  memory_bridge: boolean;
  context_bridge: boolean;
}

const API_BASE = '/api';

async function fetchJson<T>(endpoint: string, options?: RequestInit, _retried = false): Promise<T> {
  const url = `${API_BASE}${endpoint}`;
  const res = await fetch(url, { credentials: 'same-origin', ...options });
  if (res.status === 403 && !_retried && (options?.method ?? 'GET') !== 'GET') {
    // Local HMI: establish the HttpOnly chat session, then retry once.
    try {
      await fetch(`${API_BASE}/chat/session`, { credentials: 'same-origin' });
      return fetchJson<T>(endpoint, options, true);
    } catch {
      // fall through to the 403 error below
    }
  }
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    const detail = typeof body?.detail === 'string' ? body.detail : res.statusText;
    throw new Error(`API Error ${res.status}: ${detail}`);
  }
  return res.json();
}

export const api = {
  establishChatSession: () => fetchJson<{ status: string }>('/chat/session', { credentials: 'same-origin' }),
  // Vault
  getVaultStructure: () => fetchJson<VaultStructure>('/vault'),
  getMemoryFiles: () => fetchJson<MemoryFile[]>('/memory-files'),
  getFile: (relPath: string) => fetchJson<FileContent>(`/file/${encodeURIComponent(relPath)}`),
  searchVault: (q: string) => fetchJson<SearchResult[]>(`/search?q=${encodeURIComponent(q)}`),
  getMOCs: () => fetchJson<MOCItem[]>('/mocs'),
  getProjects: () => fetchJson<ProjectItem[]>('/projects'),
  getGraph: () => fetchJson<KnowledgeGraphData>('/graph'),
  getObsidianGraph: () => fetchJson<ObsidianGraphData>('/obsidian-graph'),

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
  getModelHealth: () => fetchJson<RouterHealth>('/model-health'),


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

  // Agent Supervisor
  getSupervisorTasks: () => fetchJson<{ active_tasks: Record<string, unknown> }>('/supervisor/tasks'),
  dispatchSupervisorTask: (project: string, goal: string, subtasks: Array<Record<string, unknown>>) =>
    fetchJson<{ status: string; task_id: string }>('/supervisor/dispatch', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ project, goal, subtasks }),
    }),
  getSupervisorTaskStatus: (taskId: string) => fetchJson<Record<string, unknown>>(`/supervisor/tasks/${taskId}`),

  // Governance & Autonomy
  getGovernance: () => fetchJson<{ autonomy_level: number; level_name: string }>('/governance'),
  setGovernanceLevel: (level: number) =>
    fetchJson<{ status: string; autonomy_level: number; level_name: string }>('/governance/level', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ level }),
    }),

  // Context Router
  assembleContext: (q: string) => fetchJson<Record<string, unknown>>(`/context/assemble?q=${encodeURIComponent(q)}`),

  // TurboQuant Knowledge Store
  searchTurboQuant: (q: string, limit = 5) => fetchJson<{ results: Array<Record<string, unknown>> }>(`/turboquant/search?q=${encodeURIComponent(q)}&limit=${limit}`),
  ingestTurboQuant: (sourceId: string, content: string, metadata: Record<string, unknown> = {}) =>
    fetchJson<{ status: string; source_id: string }>('/turboquant/ingest', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ source_id: sourceId, content, metadata }),
    }),

  // Mem0 Personalized Memory Layer
  mem0Add: (text: string, category = 'general', metadata: Record<string, unknown> = {}) =>
    fetchJson<{ status: string; memory: Record<string, unknown> }>('/memory/mem0/add', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, category, metadata }),
    }),
  mem0Search: (q: string, limit = 5) => fetchJson<{ results: Array<Record<string, unknown>> }>(`/memory/mem0/search?q=${encodeURIComponent(q)}&limit=${limit}`),
  mem0GetAll: (limit = 50) => fetchJson<{ memories: Array<Record<string, unknown>> }>(`/memory/mem0/all?limit=${limit}`),

  // Cloudroom Workspaces & Command Guard
  getCloudroomWorkspaces: () => fetchJson<{ workspaces: Array<Record<string, unknown>> }>('/cloudroom/workspaces'),
  validateCommandGuard: (command: string, workspace?: string) =>
    fetchJson<{ allowed: boolean; risk_level: string; reason: string; command: string; autonomy_level?: number }>('/cloudroom/guard', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ command, workspace }),
    }),

  // FrontierAgent Execution Backend
  frontierStatus: () => fetchJson<Record<string, unknown>>('/frontier/status'),
  frontierRuns: (limit = 20) => fetchJson<{ runs: Array<Record<string, unknown>> }>(`/frontier/runs?limit=${limit}`),
  frontierRun: (task: string, opts: { mode?: string; project?: string; max_turns?: number } = {}) =>
    fetchJson<Record<string, unknown>>('/frontier/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ task, mode: opts.mode ?? 'react', project: opts.project ?? '', max_turns: opts.max_turns ?? 20 }),
    }),
  frontierTrace: (session: string, limit = 50) =>
    fetchJson<{ session: string; lines: Array<Record<string, unknown>> }>(`/frontier/trace/${session}?limit=${limit}`),

  // Spatial Mode (one-by-one lanes)
  spatialSweep: (projects?: string[], task = '', dryRun = true) =>
    fetchJson<Record<string, unknown>>('/spatial/sweep', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ projects, task, dry_run: dryRun }),
    }),
  spatialStatus: (limit = 20) => fetchJson<Record<string, unknown>>(`/spatial/status?limit=${limit}`),

  // Universal Ingest (auto-reading)
  ingestRun: (maxPerAgent = 3) =>
    fetchJson<Record<string, unknown>>('/ingest/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ max_per_agent: maxPerAgent }),
    }),

  // Learn Loop (auto-research)
  learnRun: (topic?: string) =>
    fetchJson<Record<string, unknown>>('/learn/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ topic: topic ?? '' }),
    }),

  // Preferences
  getPreferences: () => fetchJson<{ sections: string[]; profile: Record<string, unknown> }>('/preferences'),

  // Research Lab
  labProfile: (name: string) => fetchJson<Record<string, unknown>>(`/lab/profile/${name}`),
  labCheck: (targetId: string, capability: string) =>
    fetchJson<{ result: string }>('/lab/check', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ target_id: targetId, capability }),
    }),

  // Org Cameras
  orgCameraStatus: () => fetchJson<Record<string, unknown>>('/org-cameras/status'),

  // AEGIS Task Board (Phase 6)
  getTasks: (limit = 50) => fetchJson<{ tasks: AegisTask[] }>(`/tasks?limit=${limit}`),
  createTask: (task: string, project?: string, kind?: string) =>
    fetchJson<AegisTask>('/tasks', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ task, project: project ?? '', kind: kind ?? 'general' }),
    }),
  dispatchTask: (taskId: string) =>
    fetchJson<AegisTask>(`/tasks/${taskId}/dispatch`, { method: 'POST' }),

  // Unified Skills Registry (Phase 7) — now maps /api/skills which returns normalized list
  getUnifiedSkills: () => fetchJson<{ skills: UnifiedSkill[] }>('/skills'),

  // Voice Interface (Phase 4)
  voiceTranscribe: (audioBase64: string) =>
    fetchJson<{ transcript: string }>('/voice/transcribe', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ audio: audioBase64 }),
    }),
  voiceSpeak: (text: string) =>
    fetchJson<{ audio_url: string }>('/voice/speak', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text }),
    }),
  voiceStatus: () => fetchJson<VoiceStatus>('/voice/status'),

  // System Graph (Phase 10)
  getSystemGraph: () => fetchJson<SystemGraphData>('/system/graph'),

  // AEGIS Doctor/Health (Phase 16)
  aegisDoctor: () => fetchJson<{ checks: DoctorCheck[] }>('/health/doctor'),

  // IDE Adapter Registry (Phase 5)
  getIdeAdapters: () => fetchJson<{ adapters: IdeAdapterInfo[] }>('/ide-adapters'),
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

// ── LM Studio local model management ───────────────────────────────────────────
// LM Studio exposes a v1 REST API on port 1234 by default.
// The backend proxies these calls; the browser never talks to LM Studio directly.
// Models are stored on disk under ~/.lmstudio/models/.
export const LMSTUDIO_DEFAULT_MODEL = 'qwen3.5-2b-uncensored-hauhaucs-aggressive';

export async function loadLocalModel(model_id = LMSTUDIO_DEFAULT_MODEL): Promise<void> {
  const resp = await fetch('/api/local-model/load', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ model: model_id }),
  });
  if (!resp.ok) throw new Error(`loadLocalModel: HTTP ${resp.status}`);
}

export async function unloadLocalModel(model_id = LMSTUDIO_DEFAULT_MODEL): Promise<void> {
  const resp = await fetch('/api/local-model/unload', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ model: model_id }),
  });
  if (!resp.ok) throw new Error(`unloadLocalModel: HTTP ${resp.status}`);
}

export interface LocalModelInfo {
  id: string;
  name: string;
  size?: string;
  loaded?: boolean;
  type?: string;
  progress?: number; // 0..1 download progress
}

export async function listLocalModels(): Promise<LocalModelInfo[]> {
  const resp = await fetch('/api/local-model/status');
  if (!resp.ok) throw new Error(`listLocalModels: HTTP ${resp.status}`);
  const data = (await resp.json()) as { models?: LocalModelInfo[]; error?: string };
  return data.models || [];
}

export async function downloadLocalModel(model_id: string): Promise<void> {
  const resp = await fetch('/api/local-model/download', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ model_id }),
  });
  if (!resp.ok) throw new Error(`downloadLocalModel: HTTP ${resp.status}`);
}

// ============================================================================
// Camera & Vision Interfaces
// ============================================================================
export interface CameraData {
  name: string;
  uri: string;
  type: string;
  authorized: boolean;
  vision_enabled: boolean;
  recording_enabled: boolean;
}

export interface CameraRegistryState {
  cameras: Record<string, CameraData>;
}

export async function getCameras(): Promise<CameraRegistryState> {
  const resp = await fetch('/api/cameras');
  if (!resp.ok) throw new Error(`getCameras: HTTP ${resp.status}`);
  return await resp.json();
}

export async function discoverCameras(): Promise<{ status: string; discovered: CameraData[] }> {
  const resp = await fetch('/api/cameras/discover', { method: 'POST' });
  if (!resp.ok) throw new Error(`discoverCameras: HTTP ${resp.status}`);
  return await resp.json();
}

export async function authorizeCamera(camId: string): Promise<any> {
  const resp = await fetch(`/api/cameras/${camId}/authorize`, { method: 'POST' });
  if (!resp.ok) throw new Error(`authorizeCamera: HTTP ${resp.status}`);
  return await resp.json();
}

export async function enableCameraVision(camId: string): Promise<any> {
  const resp = await fetch(`/api/cameras/${camId}/vision/enable`, { method: 'POST' });
  if (!resp.ok) throw new Error(`enableCameraVision: HTTP ${resp.status}`);
  return await resp.json();
}
