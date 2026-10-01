import assert from 'node:assert/strict';
import { readFileSync, mkdtempSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { pathToFileURL } from 'node:url';
import ts from 'typescript';

// Run the exact production resolver, transpiled without a test-runner dependency.
const dir = mkdtempSync(join(tmpdir(), 'aegis-graph-test-'));
try {
  const source = readFileSync(new URL('../src/lib/graphLinks.ts', import.meta.url), 'utf8');
  const output = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 } }).outputText;
  const file = join(dir, 'resolver.mjs');
  writeFileSync(file, output);
  const { resolveGraphLinks } = await import(pathToFileURL(file).href);
  const nodes = [{ id: 'folder/a.md' }, { id: 'b.md' }, { id: 'exact' }, { id: 'exact.md' }];
  const edges = [
    { source: 'folder/a', target: 'b', relation: 'LINKS_TO' },
    { source: 'folder/a.md', target: 'b.md' },
    { source: 'exact', target: 'b' },
    { source: 'missing', target: 'b' },
    { source: 'folder/a', target: 'missing' },
  ];
  const before = JSON.stringify(edges);
  assert.deepEqual(resolveGraphLinks(nodes, edges), [
    { source: 'folder/a.md', target: 'b.md', relation: 'LINKS_TO' },
    { source: 'folder/a.md', target: 'b.md' },
    { source: 'exact', target: 'b.md' },
  ]);
  assert.equal(JSON.stringify(edges), before);
  assert.deepEqual(resolveGraphLinks([], edges), []);
  console.log('PASS: extensionless, exact IDs, exact-match precedence, missing endpoints, metadata, immutability, empty graph');
  if (process.env.LIVE_GRAPH_URL) {
    const response = await fetch(process.env.LIVE_GRAPH_URL);
    assert.equal(response.status, 200);
    const graph = await response.json();
    const resolved = resolveGraphLinks(graph.nodes, graph.edges);
    const ids = new Set(graph.nodes.map(node => node.id));
    assert.ok(resolved.every(edge => ids.has(edge.source) && ids.has(edge.target)));
    assert.equal(resolved.length, graph.edges.length, 'Live edges should all resolve');
    console.log(`PASS live vault: ${graph.nodes.length} nodes, ${graph.edges.length} API edges, ${resolved.length} resolved edges`);
  }
} finally {
  rmSync(dir, { recursive: true, force: true });
}
