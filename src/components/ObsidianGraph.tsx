import React, { useState, useEffect, useRef, useMemo } from 'react';
import { Panel } from './Panel';
import { api, MemoryFile } from '../lib/api';
import { useOS } from '../lib/store';
import {
  Share2,
  ZoomIn,
  ZoomOut,
  RotateCcw,
  Layers,
  Search,
  Maximize2,
  Sparkles,
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
  radius: number;
  size: number;
  color: string;
  connections: string[];
}

interface GraphLink {
  source: string;
  target: string;
}

const CATEGORY_COLORS: Record<string, string> = {
  projects: '#4ade80',   // Green
  mocs: '#38bdf8',       // Cyan/Sky
  areas: '#a78bfa',      // Muted Violet
  resources: '#fbbf24',  // Amber
  archives: '#71717a',   // Zinc
  root: '#94a3b8',       // Slate
};

export const ObsidianGraph: React.FC<{ isEmbedded?: boolean }> = ({ isEmbedded = false }) => {
  const { openNoteInVault } = useOS();
  const canvasRef = useRef<HTMLCanvasElement>(null);

  const [nodes, setNodes] = useState<GraphNode[]>([]);
  const [links, setLinks] = useState<GraphLink[]>([]);
  const [loading, setLoading] = useState(true);
  const [hoveredNode, setHoveredNode] = useState<GraphNode | null>(null);
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState('');

  // Pan & Zoom
  const [transform, setTransform] = useState({ x: 0, y: 0, scale: 0.95 });
  const isDraggingRef = useRef(false);
  const dragStartRef = useRef({ x: 0, y: 0 });

  // Fetch memory files and build graph
  useEffect(() => {
    let isMounted = true;
    api.getMemoryFiles().then((files) => {
      if (!isMounted) return;

      const builtNodes: GraphNode[] = [];
      const builtLinks: GraphLink[] = [];

      // Filter out root files so default data stays in vault but is not displayed in graph
      const graphFiles = files.filter((file) => file.path.includes('/'));

      // Categorize files
      graphFiles.forEach((file, index) => {
        let category: GraphNode['category'] = 'resources';
        const lowerPath = file.path.toLowerCase();

        if (lowerPath.includes('1-projects') || lowerPath.includes('projects')) category = 'projects';
        else if (lowerPath.includes('mocs')) category = 'mocs';
        else if (lowerPath.includes('2-areas')) category = 'areas';
        else if (lowerPath.includes('3-resources')) category = 'resources';
        else if (lowerPath.includes('4-archives')) category = 'archives';
        else if (lowerPath.includes('agies')) category = 'areas';

        // Layout in organic clusters based on category
        const angle = (index / graphFiles.length) * Math.PI * 2;
        const clusterDist = category === 'mocs' ? 120 : category === 'projects' ? 200 : 280;
        const randomSpread = 60;

        const x = Math.cos(angle) * (clusterDist + (Math.random() - 0.5) * randomSpread);
        const y = Math.sin(angle) * (clusterDist + (Math.random() - 0.5) * randomSpread);

        const radius = category === 'mocs' ? 8 : category === 'projects' ? 6 : 4.5;

        builtNodes.push({
          id: file.path,
          name: file.name.replace(/\.(md|json)$/, ''),
          path: file.path,
          category,
          x,
          y,
          vx: 0,
          vy: 0,
          radius,
          size: file.size,
          color: CATEGORY_COLORS[category] || '#94a3b8',
          connections: [],
        });
      });

      // Synthesize inter-connections:
      // MOCs connect to related projects and categories
      const mocNodes = builtNodes.filter((n) => n.category === 'mocs');
      const projectNodes = builtNodes.filter((n) => n.category === 'projects');

      builtNodes.forEach((node) => {
        // Connect nodes within the same folder
        const folder = node.path.split('/')[0];
        const siblings = builtNodes.filter(
          (other) => other.id !== node.id && other.path.startsWith(folder)
        );

        siblings.slice(0, 2).forEach((sib) => {
          builtLinks.push({ source: node.id, target: sib.id });
          node.connections.push(sib.id);
        });

        // Connect projects to MOCs
        if (node.category === 'projects' && mocNodes.length > 0) {
          const targetMoc = mocNodes[Math.floor(Math.random() * mocNodes.length)];
          builtLinks.push({ source: node.id, target: targetMoc.id });
          node.connections.push(targetMoc.id);
        }
      });

      setNodes(builtNodes);
      setLinks(builtLinks);
      setLoading(false);
    }).catch(() => {
      setLoading(false);
    });

    return () => {
      isMounted = false;
    };
  }, []);

  // Filter nodes based on category and search
  const visibleNodes = useMemo(() => {
    return nodes.filter((n) => {
      const matchCat = selectedCategory === 'all' || n.category === selectedCategory;
      const matchSearch =
        !searchQuery ||
        n.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        n.path.toLowerCase().includes(searchQuery.toLowerCase());
      return matchCat && matchSearch;
    });
  }, [nodes, selectedCategory, searchQuery]);

  const visibleNodeIds = useMemo(() => new Set(visibleNodes.map((n) => n.id)), [visibleNodes]);

  const visibleLinks = useMemo(() => {
    return links.filter((l) => visibleNodeIds.has(l.source) && visibleNodeIds.has(l.target));
  }, [links, visibleNodeIds]);

  // Render loop
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let animId: number;

    const render = () => {
      const { width, height } = canvas;
      ctx.clearRect(0, 0, width, height);

      // Background gradient
      const bgGrad = ctx.createRadialGradient(
        width / 2,
        height / 2,
        20,
        width / 2,
        height / 2,
        Math.max(width, height)
      );
      bgGrad.addColorStop(0, 'rgba(20, 20, 26, 0.95)');
      bgGrad.addColorStop(1, 'rgba(10, 10, 12, 0.98)');
      ctx.fillStyle = bgGrad;
      ctx.fillRect(0, 0, width, height);

      // Apply Pan & Zoom Transform
      ctx.save();
      ctx.translate(width / 2 + transform.x, height / 2 + transform.y);
      ctx.scale(transform.scale, transform.scale);

      // Node lookup map
      const nodeMap = new Map<string, GraphNode>();
      visibleNodes.forEach((n) => nodeMap.set(n.id, n));

      // Draw Links / Edges
      visibleLinks.forEach((link) => {
        const source = nodeMap.get(link.source);
        const target = nodeMap.get(link.target);
        if (!source || !target) return;

        const isHighlighted =
          hoveredNode && (hoveredNode.id === source.id || hoveredNode.id === target.id);

        ctx.beginPath();
        ctx.moveTo(source.x, source.y);
        ctx.lineTo(target.x, target.y);

        if (isHighlighted) {
          ctx.strokeStyle = 'rgba(255, 255, 255, 0.45)';
          ctx.lineWidth = 1.5;
        } else {
          ctx.strokeStyle = 'rgba(255, 255, 255, 0.08)';
          ctx.lineWidth = 0.8;
        }
        ctx.stroke();
      });

      // Draw Nodes
      visibleNodes.forEach((node) => {
        const isHovered = hoveredNode?.id === node.id;
        const isConnectedToHover = hoveredNode?.connections.includes(node.id);

        ctx.beginPath();
        ctx.arc(node.x, node.y, node.radius * (isHovered ? 1.4 : 1), 0, Math.PI * 2);

        // Node fill
        if (isHovered) {
          ctx.fillStyle = '#ffffff';
          ctx.shadowColor = node.color;
          ctx.shadowBlur = 14;
        } else if (isConnectedToHover) {
          ctx.fillStyle = node.color;
          ctx.shadowColor = node.color;
          ctx.shadowBlur = 8;
        } else {
          ctx.fillStyle = node.color;
          ctx.shadowColor = 'transparent';
          ctx.shadowBlur = 0;
        }
        ctx.fill();

        // Node Label
        if (isHovered || isConnectedToHover || node.category === 'mocs' || transform.scale > 1.2) {
          ctx.font = '10px JetBrains Mono, monospace';
          ctx.fillStyle = isHovered ? '#ffffff' : 'rgba(240, 240, 240, 0.75)';
          ctx.fillText(node.name, node.x + node.radius + 4, node.y + 3);
        }
      });

      ctx.restore();
      animId = requestAnimationFrame(render);
    };

    render();

    return () => {
      cancelAnimationFrame(animId);
    };
  }, [visibleNodes, visibleLinks, transform, hoveredNode]);

  // Handle Canvas Resize
  useEffect(() => {
    const handleResize = () => {
      const canvas = canvasRef.current;
      if (canvas) {
        canvas.width = canvas.parentElement?.clientWidth || 800;
        canvas.height = canvas.parentElement?.clientHeight || 600;
      }
    };
    handleResize();
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  // Mouse Interaction (Pan, Zoom, Hover, Click)
  const getCanvasCoords = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return { worldX: 0, worldY: 0, mouseX: 0, mouseY: 0 };
    const rect = canvas.getBoundingClientRect();
    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;

    // Convert to world coordinates
    const worldX = (mouseX - canvas.width / 2 - transform.x) / transform.scale;
    const worldY = (mouseY - canvas.height / 2 - transform.y) / transform.scale;

    return { worldX, worldY, mouseX, mouseY };
  };

  const handleMouseDown = (e: React.MouseEvent<HTMLCanvasElement>) => {
    isDraggingRef.current = true;
    dragStartRef.current = { x: e.clientX - transform.x, y: e.clientY - transform.y };
  };

  const handleMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (isDraggingRef.current) {
      setTransform((prev) => ({
        ...prev,
        x: e.clientX - dragStartRef.current.x,
        y: e.clientY - dragStartRef.current.y,
      }));
      return;
    }

    const { worldX, worldY } = getCanvasCoords(e);
    let found: GraphNode | null = null;

    for (const node of visibleNodes) {
      const dist = Math.hypot(node.x - worldX, node.y - worldY);
      if (dist <= node.radius + 5) {
        found = node;
        break;
      }
    }

    setHoveredNode(found);
  };

  const handleMouseUp = () => {
    isDraggingRef.current = false;
  };

  const handleWheel = (e: React.WheelEvent<HTMLCanvasElement>) => {
    e.preventDefault();
    const zoomFactor = e.deltaY > 0 ? 0.92 : 1.08;
    setTransform((prev) => ({
      ...prev,
      scale: Math.min(Math.max(0.3, prev.scale * zoomFactor), 3.5),
    }));
  };

  const handleClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const { worldX, worldY } = getCanvasCoords(e);
    for (const node of visibleNodes) {
      const dist = Math.hypot(node.x - worldX, node.y - worldY);
      if (dist <= node.radius + 5) {
        openNoteInVault(node.path);
        break;
      }
    }
  };

  const content = (
    <div className="flex-1 flex flex-col h-full w-full relative overflow-hidden bg-[#0d0d10] select-none font-mono">
      {/* Top Glassmorphic Control Strip */}
      <div className="absolute top-3 inset-x-3 z-10 flex items-center justify-between pointer-events-none">
        {/* Left: Category Filters */}
        <div className="flex items-center space-x-1.5 p-1 glass-panel rounded-sm pointer-events-auto text-xs">
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

        {/* Right: Search & Zoom controls */}
        <div className="flex items-center space-x-2 pointer-events-auto">
          <div className="relative glass-panel flex items-center px-2 py-0.5 rounded-sm">
            <Search className="w-3 h-3 text-zinc-400 mr-1.5" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search graph..."
              className="w-32 bg-transparent text-xs text-white outline-none placeholder-zinc-500 font-mono"
            />
          </div>

          <div className="flex items-center space-x-1 p-1 glass-panel rounded-sm text-zinc-400">
            <button
              onClick={() => setTransform((p) => ({ ...p, scale: Math.min(3.5, p.scale * 1.2) }))}
              title="Zoom In"
              className="p-1 hover:text-white hover:bg-white/10 transition-os"
            >
              <ZoomIn className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={() => setTransform((p) => ({ ...p, scale: Math.max(0.3, p.scale * 0.8) }))}
              title="Zoom Out"
              className="p-1 hover:text-white hover:bg-white/10 transition-os"
            >
              <ZoomOut className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={() => setTransform({ x: 0, y: 0, scale: 0.95 })}
              title="Reset View"
              className="p-1 hover:text-white hover:bg-white/10 transition-os"
            >
              <RotateCcw className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </div>

      {/* Interactive Canvas */}
      <canvas
        ref={canvasRef}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onWheel={handleWheel}
        onClick={handleClick}
        className="w-full h-full cursor-grab active:cursor-grabbing"
      />

      {/* Floating Hover Node Info Card (Glassmorphic) */}
      {hoveredNode && (
        <div className="absolute bottom-4 left-4 z-10 glass-panel-elevated p-3 rounded-sm text-xs font-mono max-w-sm pointer-events-none border border-white/15 animate-in fade-in">
          <div className="flex items-center space-x-2 text-[11px] text-zinc-400 mb-1">
            <span
              className="w-2 h-2 rounded-full"
              style={{ backgroundColor: hoveredNode.color }}
            />
            <span className="uppercase tracking-wider font-semibold text-white">
              {hoveredNode.category}
            </span>
            <span>•</span>
            <span>{(hoveredNode.size / 1024).toFixed(1)} KB</span>
          </div>
          <div className="font-semibold text-sm text-white truncate mb-1">
            {hoveredNode.name}
          </div>
          <div className="text-[11px] text-zinc-400 truncate mb-2">
            {hoveredNode.path}
          </div>
          <div className="text-[10px] text-emerald-400 flex items-center space-x-1">
            <Sparkles className="w-3 h-3" />
            <span>Click to open in Vault Explorer</span>
          </div>
        </div>
      )}

      {/* Bottom Status & Metrics */}
      <div className="absolute bottom-3 right-3 z-10 glass-panel px-3 py-1 text-[11px] font-mono text-zinc-400 flex items-center space-x-3 pointer-events-none">
        <span>Nodes: {visibleNodes.length}</span>
        <span>•</span>
        <span>Edges: {visibleLinks.length}</span>
        <span>•</span>
        <span className="text-zinc-200">Obsidian Knowledge Mesh</span>
      </div>
    </div>
  );

  if (isEmbedded) {
    return content;
  }

  return (
    <Panel
      id="graph"
      title="Obsidian Knowledge Graph"
      icon={<Share2 className="w-3.5 h-3.5 text-[#38bdf8]" />}
      tag="Interactive Mesh"
    >
      {content}
    </Panel>
  );
};
