export interface NoteLink { source: string; target: string }

/** Resolve API link endpoints to existing note IDs; never invent nodes. */
export function resolveGraphLinks<T extends NoteLink>(nodes: readonly { id: string }[], edges: readonly T[]): T[] {
  const ids = new Set(nodes.map(node => node.id));
  const resolve = (id: string): string | null =>
    ids.has(id) ? id : ids.has(`${id}.md`) ? `${id}.md` : null;
  return edges.flatMap(edge => {
    const source = resolve(edge.source);
    const target = resolve(edge.target);
    return source !== null && target !== null ? [{ ...edge, source, target }] : [];
  });
}
