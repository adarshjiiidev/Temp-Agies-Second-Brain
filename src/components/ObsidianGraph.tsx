import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import { Panel } from './Panel';
import { api } from '../lib/api';
import { resolveGraphLinks } from '../lib/graphLinks';
import { useOS } from '../lib/store';
import { SpatialMemoryCanvas } from './SpatialMemoryCanvas';
import {
  Share2,
  ZoomIn,
  ZoomOut,
  RotateCcw,
  Layers,
  Search,
  Sparkles,
  Play,
  Pause,
  X,
} from 'lucide-react';

interface GraphNode {
  id: string;
  name: string;
  path: string;
  category: 'projects' | 'areas' | 'resources' | 'archives' | 'mocs' | 'root';
  x: number;
  y: number;
  vx: number;
  vy: number;
  fx?: number | null; // pinned x (user dragging)
  fy?: number | null; // pinned y (user dragging)
  radius: number;
  size: number;
  color: string;
  connections: string[];
  isHub?: boolean;
}

interface GraphLink {
  source: string;
  target: string;
}

interface CosmicStar {
  x: number;
  y: number;
  size: number;
  baseAlpha: number;
  twinkleSpeed: number;
  phase: number;
}

const CATEGORY_COLORS: Record<string, string> = {
  projects: '#10b981',   // Emerald
  mocs: '#06b6d4',       // Electric Cyan
  areas: '#a855f7',      // Cosmic Purple
  resources: '#f59e0b',  // Stellar Amber
  archives: '#475569',   // Cool Slate
  root: '#94a3b8',       // Starlight
};

// Alpha-decay cooling constants
const ALPHA_INIT = 1.0;
const ALPHA_DECAY = 0.022;   // decay per tick — faster settlement
const ALPHA_MIN  = 0.0005;   // settlement threshold
const VELOCITY_DECAY = 0.82; // strong friction so it brakes quickly

export const ObsidianGraph: React.FC<{ isEmbedded?: boolean }> = ({ isEmbedded = false }) => {
  const { openNoteInVault } = useOS();
  const canvasRef = useRef<HTMLCanvasElement>(null);

  const [viewMode, setViewMode] = useState<'constellation' | 'spatial'>('constellation');
  const [nodes, setNodes] = useState<GraphNode[]>([]);
  const [links, setLinks] = useState<GraphLink[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [viewport, setViewport] = useState({ width: 800, height: 600, dpr: 1 });
  const [hoveredNode, setHoveredNode] = useState<GraphNode | null>(null);
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [showAll, setShowAll] = useState(false);
  const [physicsActive, setPhysicsActive] = useState(true);

  // Pan & Zoom
  const [transform, setTransform] = useState({ x: 0, y: 0, scale: 0.85 });
  const isDraggingCanvasRef = useRef(false);
  const draggedNodeRef = useRef<GraphNode | null>(null);
  const movedRef = useRef(false);
  const pointerStartRef = useRef({ x: 0, y: 0 });
  const dragStartRef = useRef({ x: 0, y: 0 });

  // Alpha-decay state
  const alphaRef       = useRef(ALPHA_INIT);
  const settledRef     = useRef(false);
  const animIdRef      = useRef<number>(0);
  const needsDrawRef   = useRef(true); // triggers one-shot redraw
  const transformRef   = useRef(transform);
  const hoveredNodeRef = useRef<GraphNode | null>(null);

  // Background starfield
  const starsRef = useRef<CosmicStar[]>([]);
  useEffect(() => {
    const stars: CosmicStar[] = [];
    for (let i = 0; i < 140; i++) {
      stars.push({
        x: (Math.random() - 0.5) * 3800,
        y: (Math.random() - 0.5) * 2800,
        size: Math.random() * 1.5 + 0.25,
        // static alpha — no time-based twinkle so settled canvas never forces redraws
        baseAlpha: Math.random() * 0.28 + 0.07,
        twinkleSpeed: 0, // disabled post-settlement
        phase: 0,
      });
    }
    starsRef.current = stars;
  }, []);

  // Load live vault graph
  useEffect(() => {
    let isMounted = true;
    api.getObsidianGraph().then((graph) => {
      if (!isMounted) return;
      const resolvedEdges = resolveGraphLinks(graph.nodes, graph.edges);
      const connectionMap = new Map<string, string[]>();
      resolvedEdges.forEach((edge) => {
        connectionMap.set(edge.source, [...(connectionMap.get(edge.source) || []), edge.target]);
        connectionMap.set(edge.target, [...(connectionMap.get(edge.target) || []), edge.source]);
      });

      // Cluster nodes by category with radial initial placement
      const categoryCounters: Record<string, number> = {};
      const catAngleOffset: Record<string, number> = {
        mocs: 0,
        projects: (Math.PI * 2) / 5 * 1,
        areas: (Math.PI * 2) / 5 * 2,
        resources: (Math.PI * 2) / 5 * 3,
        archives: (Math.PI * 2) / 5 * 4,
      };

      const builtNodes = graph.nodes.map((node) => {
        const cat = node.category || 'resources';
        const index = categoryCounters[cat] || 0;
        categoryCounters[cat] = index + 1;

        const baseAngle = catAngleOffset[cat] || 0;
        const goldenSpread = index * 2.399963229728653;
        const angle = baseAngle + (index % 12) * 0.52 + goldenSpread * 0.15;
        const dist = cat === 'mocs'
          ? 50 + Math.sqrt(index) * 22
          : 170 + Math.sqrt(index) * 26;

        const connectionCount = connectionMap.get(node.id)?.length || 0;
        const isHub = connectionCount > 4 || cat === 'mocs' || cat === 'projects';

        return {
          ...node,
          x: Math.cos(angle) * dist + (Math.random() - 0.5) * 25,
          y: Math.sin(angle) * dist + (Math.random() - 0.5) * 25,
          vx: 0,
          vy: 0,
          fx: null,
          fy: null,
          radius: cat === 'mocs' ? 9.0 : isHub ? 6.5 : 3.8,
          color: CATEGORY_COLORS[node.category] || '#94a3b8',
          connections: connectionMap.get(node.id) || [],
          isHub,
        } as GraphNode;
      });

      // Reset alpha for fresh layout
      alphaRef.current = ALPHA_INIT;
      settledRef.current = false;

      setNodes(builtNodes);
      setLinks(resolvedEdges);
      setLoading(false);
    }).catch((err: unknown) => {
      if (!isMounted) return;
      setError(err instanceof Error ? err.message : String(err));
      setLoading(false);
    });

    return () => { isMounted = false; };
  }, []);

  // Filter nodes
  const visibleNodes = useMemo(() => {
    const q = searchQuery.toLowerCase().trim();
    return nodes.filter((n) => {
      const matchCat = selectedCategory === 'all' || n.category === selectedCategory;
      const matchSearch = !q || n.name.toLowerCase().includes(q) || n.path.toLowerCase().includes(q);

      if (q) return matchCat && matchSearch;
      if (showAll) return matchCat;

      // Constellation mode: MOCs, hubs, and connected notes only
      const isCoreHub = n.category === 'mocs' || n.category === 'projects' || n.isHub;
      const isConnected = n.connections.length >= 1;
      return matchCat && (isCoreHub || isConnected);
    }).slice(0, showAll ? 2500 : 180);
  }, [nodes, selectedCategory, searchQuery, showAll]);

  const visibleNodeIds = useMemo(() => new Set(visibleNodes.map((n) => n.id)), [visibleNodes]);
  const visibleLinks = useMemo(() => links.filter((l) => visibleNodeIds.has(l.source) && visibleNodeIds.has(l.target)), [links, visibleNodeIds]);

  // Fit initial view
  const calculateFittedView = useCallback((targetNodes: GraphNode[]) => {
    if (!targetNodes.length) return { x: 0, y: 0, scale: 0.85 };
    const xs = targetNodes.map(n => n.x);
    const ys = targetNodes.map(n => n.y);
    const minX = Math.min(...xs) - 60;
    const maxX = Math.max(...xs) + 60;
    const minY = Math.min(...ys) - 60;
    const maxY = Math.max(...ys) + 60;
    const w = maxX - minX || 500;
    const h = maxY - minY || 500;
    const scale = Math.max(0.35, Math.min(1.2, Math.min((viewport.width - 80) / w, (viewport.height - 100) / h)));
    const centerX = (minX + maxX) / 2;
    const centerY = (minY + maxY) / 2;
    return { x: -centerX * scale, y: -centerY * scale, scale };
  }, [viewport.width, viewport.height]);

  const fittedView = useMemo(() => calculateFittedView(visibleNodes), [visibleNodes, calculateFittedView]);

  useEffect(() => {
    if (visibleNodes.length > 0) {
      setTransform(fittedView);
    }
  }, [showAll, selectedCategory]);

  // Keep refs in sync so render closure always reads latest values
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { transformRef.current = transform; drawFrame(); }, [transform]);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { hoveredNodeRef.current = hoveredNode; drawFrame(); }, [hoveredNode]);

  // Fast node lookup
  const nodeMap = useMemo(() => {
    const map = new Map<string, GraphNode>();
    for (const n of visibleNodes) map.set(n.id, n);
    return map;
  }, [visibleNodes]);

  // ── Draw function (pure) — called by physics loop and on-demand ──────────────
  const drawFrame = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    const tf = transformRef.current;
    const hn = hoveredNodeRef.current;
    const { width, height, dpr } = viewport;

    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, width, height);

    // Deep space background
    const bgGrad = ctx.createRadialGradient(width / 2, height / 2, 40, width / 2, height / 2, Math.max(width, height) * 0.85);
    bgGrad.addColorStop(0, '#0a0d14');
    bgGrad.addColorStop(0.5, '#07080d');
    bgGrad.addColorStop(1, '#030407');
    ctx.fillStyle = bgGrad;
    ctx.fillRect(0, 0, width, height);

    ctx.save();
    ctx.translate(width / 2 + tf.x, height / 2 + tf.y);
    ctx.scale(tf.scale, tf.scale);

    // Static starfield (no time-variable alpha = no redraw needed)
    for (const star of starsRef.current) {
      ctx.fillStyle = `rgba(200, 220, 255, ${star.baseAlpha})`;
      ctx.beginPath();
      ctx.arc(star.x, star.y, star.size, 0, Math.PI * 2);
      ctx.fill();
    }

    // Edges
    const hoveredId = hn?.id;
    const hoveredNeighborSet = hn ? new Set(hn.connections) : null;

    for (const link of visibleLinks) {
      const s = nodeMap.get(link.source);
      const tgt = nodeMap.get(link.target);
      if (!s || !tgt) continue;

      const isDirect = hoveredId && (link.source === hoveredId || link.target === hoveredId);
      const isNeighborEdge = hoveredNeighborSet && hoveredNeighborSet.has(link.source) && hoveredNeighborSet.has(link.target);

      ctx.beginPath();
      ctx.moveTo(s.x, s.y);
      ctx.lineTo(tgt.x, tgt.y);
      ctx.shadowBlur = 0;
      ctx.shadowColor = 'transparent';

      if (isDirect) {
        ctx.strokeStyle = 'rgba(56, 189, 248, 0.88)';
        ctx.lineWidth = 1.8 / tf.scale;
        ctx.shadowColor = '#0284c7';
        ctx.shadowBlur = 6;
      } else if (isNeighborEdge) {
        ctx.strokeStyle = 'rgba(56, 189, 248, 0.32)';
        ctx.lineWidth = 1.0 / tf.scale;
      } else if (hoveredId) {
        ctx.strokeStyle = 'rgba(255,255,255,0.03)';
        ctx.lineWidth = 0.55 / tf.scale;
      } else {
        ctx.strokeStyle = 'rgba(148,163,184,0.14)';
        ctx.lineWidth = 0.7 / tf.scale;
      }
      ctx.stroke();
    }

    ctx.shadowBlur = 0;
    ctx.shadowColor = 'transparent';

    // Nodes
    for (const node of visibleNodes) {
      const isHovered = hoveredId === node.id;
      const isConnected = hoveredNeighborSet?.has(node.id);
      const isMoc = node.category === 'mocs';
      const isHub = node.isHub;
      let nodeAlpha = 1.0;
      if (hoveredId && !isHovered && !isConnected) nodeAlpha = 0.10;

      ctx.save();
      ctx.globalAlpha = nodeAlpha;

      // Hub/MOC orbital ring — static, no wobble
      if ((isMoc || isHub || isHovered) && nodeAlpha > 0.4) {
        const ringR = node.radius + (isHovered ? 9 : 6);
        ctx.beginPath();
        ctx.arc(node.x, node.y, ringR, 0, Math.PI * 2);
        ctx.strokeStyle = node.color;
        ctx.lineWidth = 0.8;
        ctx.globalAlpha = nodeAlpha * (isHovered ? 0.55 : 0.28);
        ctx.stroke();
        if (isMoc) {
          ctx.beginPath();
          ctx.arc(node.x, node.y, node.radius + 13, 0, Math.PI * 2);
          ctx.globalAlpha = nodeAlpha * 0.12;
          ctx.stroke();
        }
        ctx.globalAlpha = nodeAlpha;
      }

      const r = node.radius * (isHovered ? 1.55 : 1);
      // Atmospheric glow
      ctx.beginPath();
      ctx.arc(node.x, node.y, r + 3, 0, Math.PI * 2);
      ctx.fillStyle = node.color;
      ctx.shadowColor = node.color;
      ctx.shadowBlur = isHovered ? 22 : isHub ? 10 : 4;
      ctx.globalAlpha = nodeAlpha * 0.28;
      ctx.fill();
      ctx.globalAlpha = nodeAlpha;

      // Solid core
      ctx.beginPath();
      ctx.arc(node.x, node.y, r, 0, Math.PI * 2);
      ctx.fillStyle = isHovered ? '#ffffff' : node.color;
      ctx.shadowColor = 'transparent';
      ctx.shadowBlur = 0;
      ctx.fill();

      // Bright stellar center
      ctx.beginPath();
      ctx.arc(node.x, node.y, r * 0.38, 0, Math.PI * 2);
      ctx.fillStyle = 'rgba(255,255,255,0.88)';
      ctx.fill();

      // Labels
      const showLabel = isHovered || isConnected || (isHub && tf.scale > 0.55) || tf.scale > 1.3;
      if (showLabel) {
        const label = node.name.length > 24 ? node.name.slice(0, 24) + '\u2026' : node.name;
        ctx.font = isHovered ? 'bold 11px Inter,sans-serif' : '9.5px Inter,sans-serif';
        ctx.fillStyle = isHovered ? '#fff' : isConnected ? '#e2e8f0' : 'rgba(200,210,230,0.8)';
        if (isHovered) { ctx.shadowColor = 'rgba(0,0,0,0.95)'; ctx.shadowBlur = 5; }
        ctx.fillText(label, node.x + r + 5, node.y + 4);
        ctx.shadowBlur = 0;
      }
      ctx.restore();
    }

    ctx.restore();
  }, [visibleNodes, visibleLinks, nodeMap, viewport]);

  // ── Physics loop — runs ONLY while alpha > ALPHA_MIN, then exits ────────────
  useEffect(() => {
    cancelAnimationFrame(animIdRef.current);
    if (!physicsActive || visibleNodes.length === 0) {
      needsDrawRef.current = true;
      drawFrame();
      return;
    }

    alphaRef.current = ALPHA_INIT;
    settledRef.current = false;
    let tickTime = performance.now();

    const tick = (now: number) => {
      const dt = Math.min(32, now - tickTime) / 16.67;
      tickTime = now;
      const alpha = alphaRef.current;

      if (alpha > ALPHA_MIN) {
        alphaRef.current = Math.max(ALPHA_MIN, alpha - ALPHA_DECAY * dt);

        const springLength = 65;
        const springK      = 0.028 * alpha;
        const repulseStr   = 500 * alpha;
        const centerG      = 0.004 * alpha;

        // Spring attraction along links
        for (const l of visibleLinks) {
          const s   = nodeMap.get(l.source);
          const tgt = nodeMap.get(l.target);
          if (!s || !tgt || s === draggedNodeRef.current || tgt === draggedNodeRef.current) continue;
          const dx = tgt.x - s.x, dy = tgt.y - s.y;
          const dist = Math.hypot(dx, dy) || 1;
          const f = (dist - springLength) * springK;
          s.vx  += (dx / dist) * f;  s.vy  += (dy / dist) * f;
          tgt.vx -= (dx / dist) * f; tgt.vy -= (dy / dist) * f;
        }

        // Coulomb repulsion (small graphs only)
        if (visibleNodes.length <= 200) {
          for (let i = 0; i < visibleNodes.length; i++) {
            const a = visibleNodes[i];
            if (a === draggedNodeRef.current) continue;
            for (let j = i + 1; j < visibleNodes.length; j++) {
              const b = visibleNodes[j];
              if (b === draggedNodeRef.current) continue;
              const dx = b.x - a.x, dy = b.y - a.y;
              const d2 = dx * dx + dy * dy;
              if (d2 < 0.01) continue;
              const d = Math.sqrt(d2);
              const f = repulseStr / d2;
              a.vx -= (dx / d) * f; a.vy -= (dy / d) * f;
              b.vx += (dx / d) * f; b.vy += (dy / d) * f;
            }
          }
        }

        // Integrate + strong friction
        for (const node of visibleNodes) {
          if (node === draggedNodeRef.current) continue;
          node.vx = (node.vx - node.x * centerG) * VELOCITY_DECAY;
          node.vy = (node.vy - node.y * centerG) * VELOCITY_DECAY;
          node.x += node.vx * dt;
          node.y += node.vy * dt;
        }

        drawFrame();
        animIdRef.current = requestAnimationFrame(tick);
      } else {
        // ── SETTLED: stop the loop, draw once, freeze ──
        settledRef.current = true;
        // Zero all velocities
        for (const node of visibleNodes) { node.vx = 0; node.vy = 0; }
        drawFrame();
        // rAF loop exits here — no more frames until user interaction triggers reheat
      }
    };

    animIdRef.current = requestAnimationFrame(tick);
    return () => { cancelAnimationFrame(animIdRef.current); };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [visibleNodes, visibleLinks, nodeMap, physicsActive]);

  // Canvas Resize Observer
  useEffect(() => {
    const handleResize = () => {
      const canvas = canvasRef.current;
      if (canvas) {
        const width = canvas.parentElement?.clientWidth || 800;
        const height = canvas.parentElement?.clientHeight || 600;
        const dpr = window.devicePixelRatio || 1;
        canvas.width = Math.round(width * dpr);
        canvas.height = Math.round(height * dpr);
        setViewport({ width, height, dpr });
      }
    };
    handleResize();
    const observer = new ResizeObserver(handleResize);
    if (canvasRef.current?.parentElement) observer.observe(canvasRef.current.parentElement);
    window.addEventListener('resize', handleResize);
    return () => { observer.disconnect(); window.removeEventListener('resize', handleResize); };
  }, []);

  // ── Mouse Handlers ────────────────────────────────────────────────────────────
  const getCanvasCoords = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return { worldX: 0, worldY: 0 };
    const rect = canvas.getBoundingClientRect();
    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;
    const worldX = (mouseX - viewport.width / 2 - transform.x) / transform.scale;
    const worldY = (mouseY - viewport.height / 2 - transform.y) / transform.scale;
    return { worldX, worldY };
  };

  const handleMouseDown = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (e.button !== 0) return;
    movedRef.current = false;
    pointerStartRef.current = { x: e.clientX, y: e.clientY };

    const { worldX, worldY } = getCanvasCoords(e);
    let clickedNode: GraphNode | null = null;
    for (const node of visibleNodes) {
      if (Math.hypot(node.x - worldX, node.y - worldY) <= node.radius + 8) {
        clickedNode = node; break;
      }
    }

    if (clickedNode) {
      draggedNodeRef.current = clickedNode;
      // Wake up physics when user grabs a node — restart tick if settled
      if (settledRef.current) {
        settledRef.current = false;
        alphaRef.current = 0.35;
        let tickTime2 = performance.now();
        const dragTick = (now: number) => {
          if (!draggedNodeRef.current && alphaRef.current <= ALPHA_MIN) {
            settledRef.current = true;
            for (const n of visibleNodes) { n.vx = 0; n.vy = 0; }
            drawFrame();
            return;
          }
          const dt2 = Math.min(32, now - tickTime2) / 16.67;
          tickTime2 = now;
          if (!draggedNodeRef.current) {
            alphaRef.current = Math.max(ALPHA_MIN, alphaRef.current - ALPHA_DECAY * dt2);
          }
          const springLength = 65, springK = 0.028 * alphaRef.current;
          const repulseStr = 500 * alphaRef.current, centerG = 0.004 * alphaRef.current;
          for (const l of visibleLinks) {
            const s = nodeMap.get(l.source), tgt = nodeMap.get(l.target);
            if (!s || !tgt || s === draggedNodeRef.current || tgt === draggedNodeRef.current) continue;
            const dx = tgt.x - s.x, dy = tgt.y - s.y, dist = Math.hypot(dx, dy) || 1;
            const f = (dist - springLength) * springK;
            s.vx += (dx / dist) * f; s.vy += (dy / dist) * f;
            tgt.vx -= (dx / dist) * f; tgt.vy -= (dy / dist) * f;
          }
          if (visibleNodes.length <= 200) {
            for (let i = 0; i < visibleNodes.length; i++) {
              const a = visibleNodes[i]; if (a === draggedNodeRef.current) continue;
              for (let j = i + 1; j < visibleNodes.length; j++) {
                const b = visibleNodes[j]; if (b === draggedNodeRef.current) continue;
                const dx = b.x - a.x, dy = b.y - a.y, d2 = dx * dx + dy * dy;
                if (d2 < 0.01) continue;
                const d = Math.sqrt(d2), f = repulseStr / d2;
                a.vx -= (dx / d) * f; a.vy -= (dy / d) * f;
                b.vx += (dx / d) * f; b.vy += (dy / d) * f;
              }
            }
          }
          for (const node of visibleNodes) {
            if (node === draggedNodeRef.current) continue;
            node.vx = (node.vx - node.x * centerG) * VELOCITY_DECAY;
            node.vy = (node.vy - node.y * centerG) * VELOCITY_DECAY;
            node.x += node.vx * dt2; node.y += node.vy * dt2;
          }
          drawFrame();
          animIdRef.current = requestAnimationFrame(dragTick);
        };
        animIdRef.current = requestAnimationFrame(dragTick);
      } else {
        alphaRef.current = Math.max(alphaRef.current, 0.3);
      }
    } else {
      isDraggingCanvasRef.current = true;
      dragStartRef.current = { x: e.clientX - transform.x, y: e.clientY - transform.y };
    }
  };

  const handleMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const { worldX, worldY } = getCanvasCoords(e);

    if (draggedNodeRef.current) {
      movedRef.current = true;
      draggedNodeRef.current.x = worldX;
      draggedNodeRef.current.y = worldY;
      draggedNodeRef.current.vx = 0;
      draggedNodeRef.current.vy = 0;
      // Redraw while dragging even if settled
      if (settledRef.current) drawFrame();
      return;
    }

    if (isDraggingCanvasRef.current) {
      if (Math.hypot(e.clientX - pointerStartRef.current.x, e.clientY - pointerStartRef.current.y) > 4) {
        movedRef.current = true;
      }
      setHoveredNode(null);
      setTransform(prev => ({ ...prev, x: e.clientX - dragStartRef.current.x, y: e.clientY - dragStartRef.current.y }));
      return;
    }

    let found: GraphNode | null = null;
    for (const node of visibleNodes) {
      if (Math.hypot(node.x - worldX, node.y - worldY) <= node.radius + 7) {
        found = node; break;
      }
    }
    setHoveredNode(found);
  };

  const handleMouseUp = () => {
    isDraggingCanvasRef.current = false;
    draggedNodeRef.current = null;
  };

  const handleWheel = (e: React.WheelEvent<HTMLCanvasElement>) => {
    e.preventDefault();
    const zoomFactor = e.deltaY > 0 ? 0.90 : 1.10;
    setTransform(prev => ({ ...prev, scale: Math.min(Math.max(0.05, prev.scale * zoomFactor), 4.0) }));
  };

  const handleClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (movedRef.current) return;
    const { worldX, worldY } = getCanvasCoords(e);
    for (const node of visibleNodes) {
      if (Math.hypot(node.x - worldX, node.y - worldY) <= node.radius + 8) {
        openNoteInVault(node.path);
        break;
      }
    }
  };

  const handleHeatingPhysics = () => {
    // Re-heat physics for user to rearrange
    alphaRef.current = 0.5;
    settledRef.current = false;
    setPhysicsActive(true);
  };

  const content = (
    <div className="flex-1 flex flex-col h-full w-full relative overflow-hidden bg-[#050608] select-none font-mono">
      {/* Top Glassmorphic Control Strip */}
      <div className="absolute top-3 inset-x-3 z-10 flex flex-wrap gap-2 items-center justify-between pointer-events-none">
        {/* Left: View Mode Toggle & Category Filters */}
        <div className="flex items-center space-x-2 pointer-events-auto">
          <div className="flex items-center space-x-1 p-1 glass-panel rounded-sm text-xs">
            <button
              onClick={() => setViewMode('spatial')}
              className={`px-2 py-0.5 uppercase tracking-wider text-[10px] transition-os flex items-center space-x-1 ${
                viewMode === 'spatial'
                  ? 'bg-white/10 text-white font-medium border border-white/20'
                  : 'text-zinc-400 hover:text-white hover:bg-white/5 border border-transparent'
              }`}
            >
              <Layers className="w-3 h-3 text-amber-400" />
              <span>Spatial Cards</span>
            </button>
            <button
              onClick={() => setViewMode('constellation')}
              className={`px-2 py-0.5 uppercase tracking-wider text-[10px] transition-os flex items-center space-x-1 ${
                viewMode === 'constellation'
                  ? 'bg-white/10 text-white font-medium border border-white/20'
                  : 'text-zinc-400 hover:text-white hover:bg-white/5 border border-transparent'
              }`}
            >
              <Share2 className="w-3 h-3 text-sky-400" />
              <span>Constellation</span>
            </button>
          </div>

          {viewMode === 'constellation' && (
            <div className="flex items-center space-x-1 p-1 glass-panel rounded-sm text-xs">
              {['all', 'projects', 'mocs', 'areas', 'resources', 'archives'].map((cat) => (
                <button
                  key={cat}
                  onClick={() => setSelectedCategory(cat)}
                  className={`px-2 py-0.5 uppercase tracking-wider text-[10px] transition-os ${
                    selectedCategory === cat
                      ? 'bg-white/10 text-white font-medium border border-white/20'
                      : 'text-zinc-400 hover:text-white hover:bg-white/5 border border-transparent'
                  }`}
                >
                  {cat}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Right: Controls */}
        {viewMode === 'constellation' && (
          <div className="flex items-center space-x-2 pointer-events-auto">
            {/* Physics toggle */}
            <button
              onClick={() => {
                if (!physicsActive) { handleHeatingPhysics(); } else { setPhysicsActive(false); }
              }}
              title={physicsActive ? 'Freeze constellation' : 'Resume physics'}
              className={`glass-panel p-1.5 rounded-sm transition-os ${physicsActive && !settledRef.current ? 'text-amber-400 hover:text-amber-300' : 'text-zinc-500 hover:text-zinc-300'}`}
            >
              {physicsActive && !settledRef.current ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
            </button>

            <button
              onClick={() => setShowAll((v) => !v)}
              title="Toggle between Interconnected Constellation and Full Galaxy"
              className={`glass-panel px-2.5 py-1 text-[10px] uppercase tracking-wider transition-os ${
                showAll ? 'bg-white/10 text-white font-medium border border-white/20' : 'text-zinc-400 hover:text-white'
              }`}
            >
              {showAll ? `Galaxy: All (${nodes.length})` : 'Constellation: Core'}
            </button>

            <div className="relative glass-panel flex items-center px-2 py-0.5 rounded-sm">
              <Search className="w-3 h-3 text-zinc-400 mr-1.5" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search constellation..."
                className="w-36 bg-transparent text-xs text-white outline-none placeholder-zinc-500 font-mono"
              />
              {searchQuery && (
                <button onClick={() => setSearchQuery('')} className="text-zinc-400 hover:text-white ml-1">
                  <X className="w-3 h-3" />
                </button>
              )}
            </div>

            <div className="flex items-center space-x-1 p-1 glass-panel rounded-sm text-zinc-400">
              <button onClick={() => setTransform(p => ({ ...p, scale: Math.min(4.0, p.scale * 1.25) }))} title="Zoom In" className="p-1 hover:text-white hover:bg-white/10 transition-os"><ZoomIn className="w-3.5 h-3.5" /></button>
              <button onClick={() => setTransform(p => ({ ...p, scale: Math.max(0.05, p.scale * 0.80) }))} title="Zoom Out" className="p-1 hover:text-white hover:bg-white/10 transition-os"><ZoomOut className="w-3.5 h-3.5" /></button>
              <button onClick={() => { setTransform(fittedView); handleHeatingPhysics(); }} title="Reset & Center" className="p-1 hover:text-white hover:bg-white/10 transition-os"><RotateCcw className="w-3.5 h-3.5" /></button>
            </div>
          </div>
        )}
      </div>

      {(loading || error || (viewMode === 'constellation' && visibleNodes.length === 0)) && (
        <div role="status" className="absolute inset-0 flex items-center justify-center text-xs text-zinc-300 pointer-events-none">
          {loading ? 'Mapping neural constellation from vault...' : error ? `Error: ${error}` : 'No notes match filter.'}
        </div>
      )}

      {/* Interactive Constellation Canvas */}
      {viewMode === 'constellation' && (
        <canvas
          ref={canvasRef}
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          onMouseLeave={handleMouseUp}
          aria-label="Interactive Obsidian Knowledge Graph Constellation"
          onWheel={handleWheel}
          onClick={handleClick}
          className="w-full h-full cursor-grab active:cursor-grabbing"
        />
      )}

      {/* Hover Node HUD Card */}
      {viewMode === 'constellation' && hoveredNode && (
        <div className="absolute bottom-10 left-4 z-10 glass-panel-elevated p-3 rounded-sm text-xs font-mono max-w-xs pointer-events-none border border-white/20 shadow-2xl">
          <div className="flex items-center space-x-2 text-[11px] text-zinc-400 mb-1">
            <span className="w-2.5 h-2.5 rounded-full shadow-sm" style={{ backgroundColor: hoveredNode.color }} />
            <span className="uppercase tracking-wider font-semibold text-white">{hoveredNode.category}</span>
            <span>·</span>
            <span className="text-sky-300 font-medium">{hoveredNode.connections.length} links</span>
            <span>·</span>
            <span>{(hoveredNode.size / 1024).toFixed(1)} KB</span>
          </div>
          <div className="font-semibold text-sm text-white truncate mb-1">{hoveredNode.name}</div>
          <div className="text-[11px] text-zinc-400 truncate mb-2">{hoveredNode.path}</div>
          <div className="text-[10px] text-amber-400 flex items-center space-x-1">
            <Sparkles className="w-3 h-3" />
            <span>Click to open in Vault Explorer</span>
          </div>
        </div>
      )}

      {/* Bottom Status Strip */}
      {viewMode === 'constellation' && (
        <div className="absolute bottom-3 right-3 z-10 glass-panel px-3 py-1 text-[11px] font-mono text-zinc-400 flex items-center space-x-3 pointer-events-none">
          <span className="flex items-center gap-1.5">
            <span className={`w-2 h-2 rounded-full ${settledRef.current || !physicsActive ? 'bg-zinc-600' : 'bg-amber-400 animate-pulse-live'}`} />
            <span>{settledRef.current || !physicsActive ? 'Settled' : 'Simulating…'}</span>
          </span>
          <span>·</span>
          <span>Nodes: {visibleNodes.length}/{nodes.length}</span>
          <span>·</span>
          <span>Links: {visibleLinks.length}</span>
          <span>·</span>
          <span className="text-zinc-200">Obsidian Live Graph</span>
        </div>
      )}
    </div>
  );

  if (viewMode === 'spatial') {
    if (isEmbedded) {
      return <SpatialMemoryCanvas onSwitchToConstellation={() => setViewMode('constellation')} isEmbedded />;
    }
    return (
      <Panel id="graph" title="Spatial Memory Canvas" icon={<Layers className="w-3.5 h-3.5 text-amber-400" />} tag="Neural Cards & Wires">
        <SpatialMemoryCanvas onSwitchToConstellation={() => setViewMode('constellation')} />
      </Panel>
    );
  }

  if (isEmbedded) return content;

  return (
    <Panel id="graph" title="Obsidian Knowledge Graph" icon={<Share2 className="w-3.5 h-3.5 text-[#38bdf8]" />} tag="Live Constellation">
      {content}
    </Panel>
  );
};
