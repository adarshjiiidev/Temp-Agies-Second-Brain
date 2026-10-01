import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import { api, MemoryFile, MOCItem, ProjectItem, ObsidianGraphData } from '../lib/api';
import { useOS } from '../lib/store';
import {
  Folder,
  Layers,
  ZoomIn,
  ZoomOut,
  RotateCcw,
  Search,
  ExternalLink,
  Sparkles,
  Share2,
  RefreshCw,
  BookOpen,
  Cpu,
  X,
  Tag,
  Hash,
} from 'lucide-react';

export interface ObsidianCardNode {
  id: string;
  title: string;
  badgeType: 'MOC' | 'Project' | 'Area' | 'Resource' | 'Core' | 'Archive';
  categoryColor: string;
  categoryBg: string;
  categoryBorder: string;
  filePath: string;
  size: number;
  previewText: string;
  metrics: { label: string; value: string }[];
  tags: string[];
  connections: string[];
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface ObsidianWire {
  id: string;
  sourceId: string;
  targetId: string;
  relation: string;
  color: string;
}

const CATEGORY_STYLES: Record<string, { badge: string; color: string; bg: string; border: string }> = {
  MOC: { badge: 'MOC', color: '#06b6d4', bg: 'rgba(6, 182, 212, 0.12)', border: 'rgba(6, 182, 212, 0.3)' },
  Project: { badge: 'Project', color: '#10b981', bg: 'rgba(16, 185, 129, 0.12)', border: 'rgba(16, 185, 129, 0.3)' },
  Area: { badge: 'Area', color: '#a855f7', bg: 'rgba(168, 85, 247, 0.12)', border: 'rgba(168, 85, 247, 0.3)' },
  Resource: { badge: 'Resource', color: '#f59e0b', bg: 'rgba(245, 158, 11, 0.12)', border: 'rgba(245, 158, 11, 0.3)' },
  Core: { badge: 'Core', color: '#38bdf8', bg: 'rgba(56, 189, 248, 0.12)', border: 'rgba(56, 189, 248, 0.3)' },
  Archive: { badge: 'Archive', color: '#71717a', bg: 'rgba(113, 113, 122, 0.12)', border: 'rgba(113, 113, 122, 0.3)' },
};

function cleanNoteTitle(raw: string): string {
  if (!raw) return 'Untitled';
  return raw
    .replace(/^\[+/, '')
    .replace(/\]+$/, '')
    .replace(/\.(md|json)$/, '')
    .replace(/[-_]/g, ' ')
    .trim();
}

function cleanMarkdownPreview(raw: string): string {
  if (!raw) return '';
  return raw
    .replace(/^---[\s\S]*?---/m, '')
    .replace(/^#+\s+[^\n]+/gm, '')
    .replace(/\*\*([^*]+)\*\*/g, '$1')
    .replace(/\[\[([^\]|]+)(?:\|[^\]]+)?\]\]/g, '$1')
    .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
    .replace(/[*_`>#-]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .slice(0, 160);
}

export const SpatialMemoryCanvas: React.FC<{
  onSwitchToConstellation?: () => void;
  isEmbedded?: boolean;
}> = ({ onSwitchToConstellation }) => {
  const { openNoteInVault } = useOS();
  const containerRef = useRef<HTMLDivElement>(null);

  const [cards, setCards] = useState<ObsidianCardNode[]>([]);
  const [wires, setWires] = useState<ObsidianWire[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedFilter, setSelectedFilter] = useState<string>('all');
  const [selectedCard, setSelectedCard] = useState<ObsidianCardNode | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);

  // Pan & Zoom
  const [transform, setTransform] = useState({ x: 50, y: 40, scale: 0.72 });
  const isPanningRef = useRef(false);
  const panStartRef = useRef({ x: 0, y: 0 });
  const transformStartRef = useRef({ x: 0, y: 0 });

  // Dragging cards
  const [draggingCardId, setDraggingCardId] = useState<string | null>(null);
  const dragCardOffsetRef = useRef({ x: 0, y: 0 });

  // Build real Obsidian cards from live vault files, MOCs, Projects, and Graph
  const loadGraphData = useCallback(async () => {
    setLoading(true);
    try {
      const [files, mocs, projects, graphData] = await Promise.all([
        api.getMemoryFiles().catch(() => [] as MemoryFile[]),
        api.getMOCs().catch(() => [] as MOCItem[]),
        api.getProjects().catch(() => [] as ProjectItem[]),
        api.getObsidianGraph().catch(() => ({ nodes: [], edges: [] } as ObsidianGraphData)),
      ]);

      const cardList: ObsidianCardNode[] = [];
      const wireList: ObsidianWire[] = [];
      const cardMap = new Map<string, ObsidianCardNode>();

      // Link resolution map from real Obsidian edges
      const linkMap = new Map<string, string[]>();
      (graphData.edges || []).forEach((e) => {
        linkMap.set(e.source, [...(linkMap.get(e.source) || []), e.target]);
        linkMap.set(e.target, [...(linkMap.get(e.target) || []), e.source]);
      });

      const cardWidth = 320;
      const cardHeight = 230;
      const gapX = 40;
      const gapY = 35;

      // ── Lane 1: Obsidian MOCs (Maps of Content) — Column 0 (x = 50) ──────────
      const mocItems = mocs.length > 0 ? mocs.slice(0, 4) : files.filter((f) => f.path.toLowerCase().includes('moc')).slice(0, 4);
      mocItems.forEach((moc, idx) => {
        const id = moc.path;
        const rawTitle = 'title' in moc ? moc.title : moc.name;
        const title = cleanNoteTitle(rawTitle);
        const style = CATEGORY_STYLES.MOC;
        const links = linkMap.get(id) || [];
        const preview = 'preview' in moc && moc.preview
          ? cleanMarkdownPreview(moc.preview)
          : 'High-level Map of Content indexing domain architecture, systems, and wikilink pathways.';
        const size = 'size' in moc ? moc.size : 4096;

        const card: ObsidianCardNode = {
          id,
          title,
          badgeType: 'MOC',
          categoryColor: style.color,
          categoryBg: style.bg,
          categoryBorder: style.border,
          filePath: moc.path,
          size,
          previewText: preview,
          metrics: [
            { label: 'Wikilinks', value: `${links.length} Connected` },
            { label: 'Type', value: 'Obsidian MOC' },
          ],
          tags: ['MOC', 'PARA', 'Hub'],
          connections: links,
          x: 50,
          y: 50 + idx * (cardHeight + gapY),
          width: cardWidth,
          height: cardHeight,
        };
        cardList.push(card);
        cardMap.set(id, card);
      });

      // ── Lane 2: Active Projects — Columns 1 & 2 (x = 410, x = 770) ───────────
      const projectItems = projects.length > 0 ? projects.slice(0, 6) : files.filter((f) => f.path.toLowerCase().includes('project')).slice(0, 6);
      projectItems.forEach((proj, idx) => {
        const id = proj.path;
        const rawTitle = 'title' in proj ? proj.title : proj.name;
        const title = cleanNoteTitle(rawTitle);
        const col = idx % 2;
        const row = Math.floor(idx / 2);
        const style = CATEGORY_STYLES.Project;
        const links = linkMap.get(id) || [];
        const status = 'status' in proj && proj.status ? proj.status : 'Active';
        const preview = 'preview' in proj && proj.preview
          ? cleanMarkdownPreview(proj.preview)
          : 'Obsidian Project File';
        const size = 'size' in proj ? proj.size : 5120;

        const card: ObsidianCardNode = {
          id,
          title,
          badgeType: 'Project',
          categoryColor: style.color,
          categoryBg: style.bg,
          categoryBorder: style.border,
          filePath: proj.path,
          size,
          previewText: preview,
          metrics: [
            { label: 'Status', value: status },
            { label: 'Domain', value: '1-Projects' },
          ],
          tags: ['Project', 'Active', 'Tracked'],
          connections: links,
          x: 410 + col * (cardWidth + gapX),
          y: 50 + row * (cardHeight + gapY),
          width: cardWidth,
          height: cardHeight,
        };
        cardList.push(card);
        cardMap.set(id, card);
      });

      // ── Lane 3: Core Memories & Areas — Column 3 (x = 1130) ─────────────────
      const areas = files.filter(
        (f) =>
          f.path.toLowerCase().includes('area') ||
          f.path.startsWith('agies/') ||
          f.path.startsWith('agies-memories/')
      ).slice(0, 4);

      areas.forEach((file, idx) => {
        const id = file.path;
        const title = cleanNoteTitle(file.name);
        const isCore = file.path.startsWith('agies');
        const style = isCore ? CATEGORY_STYLES.Core : CATEGORY_STYLES.Area;
        const links = linkMap.get(id) || [];
        const card: ObsidianCardNode = {
          id,
          title,
          badgeType: isCore ? 'Core' : 'Area',
          categoryColor: style.color,
          categoryBg: style.bg,
          categoryBorder: style.border,
          filePath: file.path,
          size: file.size,
          previewText: 'preview' in file ? cleanMarkdownPreview((file as any).preview) : 'Obsidian vault file.',
          metrics: [
            { label: 'Domain', value: isCore ? 'Core-Memory' : '2-Areas' },
            { label: 'Size', value: `${(file.size / 1024).toFixed(1)} KB` },
          ],
          tags: [isCore ? 'Memory' : 'Area', 'Standard'],
          connections: links,
          x: 1130,
          y: 50 + idx * (cardHeight + gapY),
          width: cardWidth,
          height: cardHeight,
        };
        cardList.push(card);
        cardMap.set(id, card);
      });

      // ── Lane 4: Resources & Knowledge References — Lower Bank (y = 860) ─────
      const resources = files.filter(
        (f) =>
          f.path.toLowerCase().includes('resource') ||
          f.path.toLowerCase().includes('structure') ||
          f.path.toLowerCase().includes('system')
      ).slice(0, 4);

      resources.forEach((file, idx) => {
        const id = file.path;
        const title = cleanNoteTitle(file.name);
        const style = CATEGORY_STYLES.Resource;
        const links = linkMap.get(id) || [];
        const card: ObsidianCardNode = {
          id,
          title,
          badgeType: 'Resource',
          categoryColor: style.color,
          categoryBg: style.bg,
          categoryBorder: style.border,
          filePath: file.path,
          size: file.size,
          previewText: 'Knowledge resource, technical cheat-sheets, model architectures, and reference guides.',
          metrics: [
            { label: 'Domain', value: '3-Resources' },
            { label: 'Size', value: `${(file.size / 1024).toFixed(1)} KB` },
          ],
          tags: ['Resource', 'CheatSheet', 'Reference'],
          connections: links,
          x: 50 + idx * (cardWidth + gapX),
          y: 860,
          width: cardWidth,
          height: cardHeight,
        };
        cardList.push(card);
        cardMap.set(id, card);
      });

      // ── Build True Wires from Obsidian Graph Edges ───────────────────────────
      const addedWireKeys = new Set<string>();
      (graphData.edges || []).forEach((e, idx) => {
        if (cardMap.has(e.source) && cardMap.has(e.target)) {
          const wireKey = [e.source, e.target].sort().join(':::');
          if (!addedWireKeys.has(wireKey)) {
            addedWireKeys.add(wireKey);
            const sourceCard = cardMap.get(e.source)!;
            wireList.push({
              id: `obs-wire-${idx}`,
              sourceId: e.source,
              targetId: e.target,
              relation: e.relation || 'WIKILINK',
              color: sourceCard.categoryColor,
            });
          }
        }
      });

      // Structural inter-domain wires to represent Obsidian PARA flow
      if (wireList.length < 5 && cardList.length > 2) {
        const firstMoc = cardList.find((c) => c.badgeType === 'MOC');
        const firstProj = cardList.find((c) => c.badgeType === 'Project');
        const secondProj = cardList.filter((c) => c.badgeType === 'Project')[1];
        const firstCore = cardList.find((c) => c.badgeType === 'Core');
        const firstRes = cardList.find((c) => c.badgeType === 'Resource');

        if (firstMoc && firstProj) {
          wireList.push({
            id: 'syn-moc-proj',
            sourceId: firstMoc.id,
            targetId: firstProj.id,
            relation: 'INDEXES',
            color: '#06b6d4',
          });
        }
        if (firstProj && firstCore) {
          wireList.push({
            id: 'syn-proj-core',
            sourceId: firstProj.id,
            targetId: firstCore.id,
            relation: 'LOGS_TO',
            color: '#10b981',
          });
        }
        if (firstProj && secondProj) {
          wireList.push({
            id: 'syn-proj-proj',
            sourceId: firstProj.id,
            targetId: secondProj.id,
            relation: 'COORDINATES',
            color: '#10b981',
          });
        }
        if (firstCore && firstRes) {
          wireList.push({
            id: 'syn-core-res',
            sourceId: firstCore.id,
            targetId: firstRes.id,
            relation: 'REFERENCES',
            color: '#38bdf8',
          });
        }
      }

      setCards(cardList);
      setWires(wireList);
    } catch (err) {
      console.error('Failed to load Obsidian spatial cards:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadGraphData();
  }, [loadGraphData]);

  // Card dragging handlers
  const handleCardMouseDown = (e: React.MouseEvent, card: ObsidianCardNode) => {
    e.stopPropagation();
    if (e.button !== 0) return;
    setDraggingCardId(card.id);
    dragCardOffsetRef.current = {
      x: (e.clientX - transform.x) / transform.scale - card.x,
      y: (e.clientY - transform.y) / transform.scale - card.y,
    };
  };

  const handleCanvasMouseDown = (e: React.MouseEvent) => {
    if (e.button !== 0) return;
    isPanningRef.current = true;
    panStartRef.current = { x: e.clientX, y: e.clientY };
    transformStartRef.current = { x: transform.x, y: transform.y };
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (draggingCardId) {
      const mouseWorldX = (e.clientX - transform.x) / transform.scale;
      const mouseWorldY = (e.clientY - transform.y) / transform.scale;
      const newX = Math.round(mouseWorldX - dragCardOffsetRef.current.x);
      const newY = Math.round(mouseWorldY - dragCardOffsetRef.current.y);

      setCards((prev) =>
        prev.map((c) => (c.id === draggingCardId ? { ...c, x: newX, y: newY } : c))
      );
      return;
    }

    if (isPanningRef.current) {
      const dx = e.clientX - panStartRef.current.x;
      const dy = e.clientY - panStartRef.current.y;
      setTransform({
        ...transformStartRef.current,
        x: transformStartRef.current.x + dx,
        y: transformStartRef.current.y + dy,
        scale: transform.scale,
      });
    }
  };

  const handleMouseUp = () => {
    isPanningRef.current = false;
    setDraggingCardId(null);
  };

  // Zoom handlers
  const handleWheel = (e: React.WheelEvent) => {
    e.preventDefault();
    const zoomFactor = e.deltaY > 0 ? 0.92 : 1.08;
    const newScale = Math.min(Math.max(0.25, transform.scale * zoomFactor), 2.2);

    if (containerRef.current) {
      const rect = containerRef.current.getBoundingClientRect();
      const mouseX = e.clientX - rect.left;
      const mouseY = e.clientY - rect.top;

      const newX = mouseX - (mouseX - transform.x) * (newScale / transform.scale);
      const newY = mouseY - (mouseY - transform.y) * (newScale / transform.scale);

      setTransform({ x: newX, y: newY, scale: newScale });
    } else {
      setTransform((prev) => ({ ...prev, scale: newScale }));
    }
  };

  const handleResetView = () => {
    setTransform({ x: 50, y: 40, scale: 0.72 });
  };

  const handleRebuild = async () => {
    setIsRefreshing(true);
    try {
      await fetch('/api/knowledge/rebuild', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      });
      await loadGraphData();
    } catch (e) {
      console.warn('Rebuild error:', e);
    } finally {
      setIsRefreshing(false);
    }
  };

  // Filter cards by category and search
  const filteredCards = useMemo(() => {
    return cards.filter((card) => {
      const matchCat =
        selectedFilter === 'all' ||
        card.badgeType.toLowerCase() === selectedFilter.toLowerCase();
      const matchSearch =
        !searchQuery ||
        card.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
        card.filePath.toLowerCase().includes(searchQuery.toLowerCase()) ||
        card.previewText.toLowerCase().includes(searchQuery.toLowerCase()) ||
        card.tags.some((t) => t.toLowerCase().includes(searchQuery.toLowerCase()));
      return matchCat && matchSearch;
    });
  }, [cards, selectedFilter, searchQuery]);

  const filteredCardIds = useMemo(() => new Set(filteredCards.map((c) => c.id)), [filteredCards]);

  // Compute Bezier Curves for Wires
  const visibleWires = useMemo(() => {
    const cardPositionMap = new Map<string, ObsidianCardNode>();
    cards.forEach((c) => cardPositionMap.set(c.id, c));

    return wires
      .filter((w) => filteredCardIds.has(w.sourceId) && filteredCardIds.has(w.targetId))
      .map((w) => {
        const source = cardPositionMap.get(w.sourceId);
        const target = cardPositionMap.get(w.targetId);
        if (!source || !target) return null;

        // Port calculation: source right -> target left
        let x1 = source.x + source.width;
        let y1 = source.y + source.height / 2;
        let x2 = target.x;
        let y2 = target.y + target.height / 2;

        if (target.x + target.width < source.x) {
          x1 = source.x;
          x2 = target.x + target.width;
        }

        const dx = Math.abs(x2 - x1);
        const curvature = Math.max(dx * 0.45, 50);

        const pathData = `M ${x1} ${y1} C ${x1 + curvature} ${y1}, ${x2 - curvature} ${y2}, ${x2} ${y2}`;
        const midX = (x1 + x2) / 2;
        const midY = (y1 + y2) / 2;

        return {
          wire: w,
          path: pathData,
          x1,
          y1,
          x2,
          y2,
          midX,
          midY,
          color: w.color || '#06b6d4',
        };
      })
      .filter(Boolean) as {
      wire: ObsidianWire;
      path: string;
      x1: number;
      y1: number;
      x2: number;
      y2: number;
      midX: number;
      midY: number;
      color: string;
    }[];
  }, [wires, cards, filteredCardIds]);

  return (
    <div
      ref={containerRef}
      onMouseDown={handleCanvasMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onWheel={handleWheel}
      className="flex-1 w-full h-full relative overflow-hidden bg-[#09090b] select-none font-sans cursor-grab active:cursor-grabbing"
      style={{
        backgroundImage: `
          radial-gradient(circle at 1px 1px, rgba(255, 255, 255, 0.04) 1px, transparent 0),
          radial-gradient(ellipse at 50% 0%, rgba(6, 182, 212, 0.03), transparent 60%)
        `,
        backgroundSize: '28px 28px, 100% 100%',
      }}
    >
      {/* ── Top Bar Controls (Exact Dashboard Dark Glassmorphic) ── */}
      <div className="absolute top-3 inset-x-3 z-30 flex flex-wrap items-center justify-between pointer-events-none gap-2">
        {/* Left: Obsidian Vault Memory Badge & Mode Switcher */}
        <div className="flex items-center space-x-2 pointer-events-auto">
          <div className="glass-panel px-3 py-1.5 rounded-sm flex items-center space-x-2 border border-white/10 shadow-lg">
            <BookOpen className="w-3.5 h-3.5 text-orange-400" />
            <span className="font-semibold text-xs text-white uppercase tracking-wider font-mono">Vault Memory</span>
            <span className="text-zinc-500 text-xs font-mono">/ Spatial Board</span>
          </div>

          {/* Mode Switcher */}
          <div className="glass-panel p-1 rounded-sm flex items-center space-x-1 text-xs">
            <button className="px-2.5 py-1 rounded-xs text-xs font-medium bg-white/10 text-white shadow-xs flex items-center space-x-1.5 transition-os border border-white/15">
              <Layers className="w-3.5 h-3.5 text-amber-400" />
              <span>Spatial Cards</span>
            </button>
            {onSwitchToConstellation && (
              <button
                onClick={onSwitchToConstellation}
                className="px-2.5 py-1 rounded-xs text-xs font-medium text-zinc-400 hover:text-white hover:bg-white/5 flex items-center space-x-1.5 transition-os border border-transparent"
              >
                <Share2 className="w-3.5 h-3.5 text-sky-400" />
                <span>Constellation</span>
              </button>
            )}
          </div>
        </div>

        {/* Center: Obsidian PARA Categories */}
        <div className="hidden lg:flex items-center space-x-1 p-1 glass-panel rounded-sm pointer-events-auto text-xs">
          {['all', 'moc', 'project', 'area', 'resource', 'core'].map((cat) => (
            <button
              key={cat}
              onClick={() => setSelectedFilter(cat)}
              className={`px-2.5 py-1 rounded-xs uppercase tracking-wider text-[10px] font-mono transition-os ${
                selectedFilter === cat
                  ? 'bg-white/15 text-white font-medium border border-white/20'
                  : 'text-zinc-400 hover:text-white hover:bg-white/5 border border-transparent'
              }`}
            >
              {cat === 'all' ? 'All Notes' : cat}
            </button>
          ))}
        </div>

        {/* Right: Search & Zoom Controls */}
        <div className="flex items-center space-x-2 pointer-events-auto">
          <div className="relative glass-panel flex items-center px-2.5 py-1 rounded-sm border border-white/10 shadow-md">
            <Search className="w-3 h-3 text-zinc-400 mr-2" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search vault cards..."
              className="w-36 md:w-44 bg-transparent text-xs text-white outline-none placeholder-zinc-500 font-mono"
            />
            {searchQuery && (
              <button onClick={() => setSearchQuery('')} className="text-zinc-400 hover:text-white">
                <X className="w-3 h-3" />
              </button>
            )}
          </div>

          <button
            onClick={handleRebuild}
            disabled={isRefreshing}
            title="Rebuild Knowledge Mesh"
            className="p-1.5 glass-panel rounded-sm text-zinc-400 hover:text-white hover:bg-white/10 transition-os"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isRefreshing ? 'animate-spin text-orange-400' : ''}`} />
          </button>

          <div className="flex items-center space-x-1 p-1 glass-panel rounded-sm text-zinc-400">
            <button
              onClick={() => setTransform((p) => ({ ...p, scale: Math.min(2.2, p.scale * 1.15) }))}
              title="Zoom In"
              className="p-1 hover:text-white hover:bg-white/10 rounded transition-os"
            >
              <ZoomIn className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={() => setTransform((p) => ({ ...p, scale: Math.max(0.25, p.scale * 0.85) }))}
              title="Zoom Out"
              className="p-1 hover:text-white hover:bg-white/10 rounded transition-os"
            >
              <ZoomOut className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={handleResetView}
              title="Center View"
              className="p-1 hover:text-white hover:bg-white/10 rounded transition-os"
            >
              <RotateCcw className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </div>

      {/* ── Spatial World Canvas ── */}
      <div
        className="w-full h-full absolute inset-0 origin-top-left"
        style={{
          transform: `translate(${transform.x}px, ${transform.y}px) scale(${transform.scale})`,
        }}
      >
        {/* SVG Bezier Connection Wires Layer */}
        <svg
          className="absolute inset-0 pointer-events-none overflow-visible w-full h-full"
          style={{ width: '100%', height: '100%', top: 0, left: 0 }}
        >
          <defs>
            <filter id="wire-glow-subtle" x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur stdDeviation="2.5" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>

          {visibleWires.map((item) => {
            const isSelected =
              selectedCard && (selectedCard.id === item.wire.sourceId || selectedCard.id === item.wire.targetId);

            return (
              <g key={item.wire.id} className="transition-opacity duration-300">
                {/* Connection Cable */}
                <path
                  d={item.path}
                  fill="none"
                  stroke={isSelected ? 'rgba(255, 255, 255, 0.45)' : 'rgba(255, 255, 255, 0.12)'}
                  strokeWidth={isSelected ? 2.4 : 1.6}
                  strokeLinecap="round"
                />

                {/* Laser Glow Pulse */}
                <path
                  d={item.path}
                  fill="none"
                  stroke={item.color}
                  strokeWidth={isSelected ? 2.6 : 1.8}
                  strokeLinecap="round"
                  className="animate-wire-flow"
                  filter="url(#wire-glow-subtle)"
                  strokeDasharray="6 14"
                />

                {/* Anchor Points */}
                <circle cx={item.x1} cy={item.y1} r={3.5} fill="#0e0e13" stroke={item.color} strokeWidth={2} />
                <circle cx={item.x2} cy={item.y2} r={3.5} fill="#0e0e13" stroke={item.color} strokeWidth={2} />
              </g>
            );
          })}
        </svg>

        {/* Real Obsidian Notes Cards (Styled in Dashboard Dark Glassmorphism) */}
        {filteredCards.map((card) => {
          const isSelected = selectedCard?.id === card.id;
          const isDragging = draggingCardId === card.id;

          return (
            <div
              key={card.id}
              onMouseDown={(e) => handleCardMouseDown(e, card)}
              onClick={() => setSelectedCard(card)}
              onDoubleClick={() => openNoteInVault(card.filePath)}
              style={{
                transform: `translate(${card.x}px, ${card.y}px)`,
                width: `${card.width}px`,
                minHeight: `${card.height}px`,
                zIndex: isDragging ? 50 : isSelected ? 40 : 10,
              }}
              className={`absolute rounded-xl p-4 flex flex-col justify-between cursor-grab active:cursor-grabbing backdrop-blur-xl border transition-all duration-200 select-none ${
                isSelected
                  ? 'bg-[#12131a]/95 text-white border-orange-400 shadow-[0_0_30px_rgba(6,182,212,0.25)] ring-1 ring-orange-400/40'
                  : 'bg-[#0f1015]/90 text-zinc-200 border-white/10 shadow-xl hover:border-white/25 hover:bg-[#13141b]/95'
              }`}
            >
              {/* Connection Ports on Card Edges */}
              <div
                className="absolute -left-1.5 top-1/2 -translate-y-1/2 w-3 h-3 rounded-full bg-[#0a0b0e] border-2 shadow-xs transition-colors"
                style={{ borderColor: card.categoryColor }}
              />
              <div
                className="absolute -right-1.5 top-1/2 -translate-y-1/2 w-3 h-3 rounded-full bg-[#0a0b0e] border-2 shadow-xs transition-colors"
                style={{ borderColor: card.categoryColor }}
              />

              {/* Card Header: Category Badge & Wikilinks */}
              <div className="flex items-center justify-between gap-2 mb-2">
                <div
                  className="inline-flex items-center space-x-1.5 px-2.5 py-0.5 rounded-sm text-[11px] font-mono font-medium border"
                  style={{
                    backgroundColor: card.categoryBg,
                    borderColor: card.categoryBorder,
                    color: card.categoryColor,
                  }}
                >
                  {card.badgeType === 'MOC' && <BookOpen className="w-3 h-3" />}
                  {card.badgeType === 'Project' && <Folder className="w-3 h-3" />}
                  {card.badgeType === 'Area' && <Layers className="w-3 h-3" />}
                  {card.badgeType === 'Resource' && <Sparkles className="w-3 h-3" />}
                  {card.badgeType === 'Core' && <Cpu className="w-3 h-3" />}
                  <span>{card.badgeType}</span>
                </div>

                <div className="flex items-center space-x-1 text-[10px] font-mono text-zinc-500">
                  <Hash className="w-3 h-3 text-zinc-600" />
                  <span>{card.connections.length} links</span>
                </div>
              </div>

              {/* Note Title */}
              <div className="mb-2">
                <h3 className="font-semibold text-sm text-zinc-100 leading-snug line-clamp-2 font-mono">
                  {card.title}
                </h3>
                <div className="text-[10px] font-mono text-zinc-500 truncate mt-0.5">
                  {card.filePath}
                </div>
              </div>

              {/* Body: Real Note Preview Snippet */}
              <div className="mb-3 flex-1">
                <p className="text-xs text-zinc-400 line-clamp-2 leading-relaxed font-sans font-normal">
                  {card.previewText}
                </p>
              </div>

              {/* Card Footer: Metrics & Open Note in Vault Action */}
              <div className="pt-2 border-t border-white/5 flex items-center justify-between mt-auto">
                <div className="flex items-center space-x-3 text-[10px] font-mono text-zinc-400">
                  {card.metrics.map((m, idx) => (
                    <div key={idx}>
                      <span className="text-zinc-600">{m.label}: </span>
                      <span className="text-zinc-300 font-medium">{m.value}</span>
                    </div>
                  ))}
                </div>

                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    openNoteInVault(card.filePath);
                  }}
                  className="px-2 py-1 rounded-sm text-[10px] font-mono text-orange-400 hover:text-white bg-orange-500/10 hover:bg-orange-500/25 border border-orange-500/30 flex items-center space-x-1 transition-os"
                >
                  <span>Open</span>
                  <ExternalLink className="w-2.5 h-2.5" />
                </button>
              </div>
            </div>
          );
        })}
      </div>

      {/* Bottom Status Strip */}
      <div className="absolute bottom-3 left-3 z-20 glass-panel px-3 py-1.5 rounded-sm text-xs font-mono text-zinc-400 flex items-center space-x-3 pointer-events-none border border-white/10">
        <span className="flex items-center gap-1.5">
          <span className="w-2 h-2 rounded-full bg-orange-400 animate-pulse-live" />
          <span className="text-white font-medium">Obsidian Vault Mesh</span>
        </span>
        <span>•</span>
        <span>Notes: {filteredCards.length}</span>
        <span>•</span>
        <span>Connections: {visibleWires.length}</span>
        <span>•</span>
        <span className="text-zinc-500">Double-click note card to edit in Vault</span>
      </div>
    </div>
  );
};
