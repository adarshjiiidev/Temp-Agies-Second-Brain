//! AEGIS Dependency Graph Kernel (`aegis_graph_core`)
//!
//! Pure Rust implementation of the DAG operations from
//! `src/aegis/l6_planning/decomposition/dependency_graph.py`.
//!
//! Implements the same algorithms as the Python `DependencyGraph`:
//! - Topological sort (Kahn's algorithm — identical to Python)
//! - Cycle detection (DFS — identical to Python)
//! - Critical path (DP on topo order — identical to Python)
//! - Parallel groups (level BFS — identical to Python)
//!
//! # Design
//! - Nodes are indexed by `u32` (mapped from string IDs by the caller)
//! - Adjacency lists stored as `Vec<Vec<u32>>` (compact, cache-friendly)
//! - No heap allocation in inner loops (except result vecs)
//! - Intended as a performance reference and future PyO3 binding target

use std::collections::VecDeque;

/// Result of a graph operation.
#[derive(Debug)]
pub enum GraphError {
    CycleDetected(Vec<Vec<u32>>),
    InvalidNodeIndex(u32),
}

impl std::fmt::Display for GraphError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::CycleDetected(cycles) => write!(f, "Graph contains {} cycle(s)", cycles.len()),
            Self::InvalidNodeIndex(i)   => write!(f, "Invalid node index: {}", i),
        }
    }
}

/// Directed Acyclic Graph (DAG) for task dependency management.
///
/// Nodes are `u32` indices; edges are stored as successor/predecessor adjacency lists.
/// String-to-index mapping is the caller's responsibility.
#[derive(Debug, Clone)]
pub struct DependencyGraph {
    /// Number of nodes
    n: usize,
    /// successors[i] = nodes that depend on i (i must run before them)
    successors: Vec<Vec<u32>>,
    /// predecessors[i] = nodes that i depends on
    predecessors: Vec<Vec<u32>>,
    /// Node weights (estimated duration, arbitrary units)
    weights: Vec<f64>,
}

impl DependencyGraph {
    /// Create a new graph with `n` nodes, all with default weight 1.0.
    pub fn new(n: usize) -> Self {
        Self {
            n,
            successors: vec![Vec::new(); n],
            predecessors: vec![Vec::new(); n],
            weights: vec![1.0; n],
        }
    }

    /// Set node weight (duration estimate).
    pub fn set_weight(&mut self, node: u32, weight: f64) {
        self.weights[node as usize] = weight;
    }

    /// Add a directed edge: `to` depends on `from` (from → to).
    ///
    /// Does not check for duplicate edges (caller ensures uniqueness).
    pub fn add_edge(&mut self, from: u32, to: u32) {
        self.successors[from as usize].push(to);
        self.predecessors[to as usize].push(from);
    }

    /// Number of nodes.
    pub fn node_count(&self) -> usize {
        self.n
    }

    /// Number of edges.
    pub fn edge_count(&self) -> usize {
        self.successors.iter().map(|s| s.len()).sum()
    }

    // -----------------------------------------------------------------------
    // Topological sort — Kahn's algorithm (identical to Python implementation)
    // -----------------------------------------------------------------------

    /// Return nodes in topological order (dependencies before dependents).
    ///
    /// Equivalent to Python `DependencyGraph.topological_sort()`.
    pub fn topological_sort(&self) -> Result<Vec<u32>, GraphError> {
        let mut in_degree: Vec<u32> = self.predecessors.iter()
            .map(|p| p.len() as u32)
            .collect();

        let mut queue: VecDeque<u32> = (0..self.n as u32)
            .filter(|&i| in_degree[i as usize] == 0)
            .collect();

        // Sort for determinism (Python uses sorted(successors))
        let mut sorted_roots: Vec<u32> = queue.drain(..).collect();
        sorted_roots.sort_unstable();
        queue.extend(sorted_roots);

        let mut result = Vec::with_capacity(self.n);

        while let Some(node) = queue.pop_front() {
            result.push(node);

            // Sort successors for determinism
            let mut succs = self.successors[node as usize].clone();
            succs.sort_unstable();
            for succ in succs {
                let deg = &mut in_degree[succ as usize];
                *deg -= 1;
                if *deg == 0 {
                    queue.push_back(succ);
                }
            }
        }

        if result.len() != self.n {
            let cycles = self.detect_cycles();
            return Err(GraphError::CycleDetected(cycles));
        }

        Ok(result)
    }

    // -----------------------------------------------------------------------
    // Cycle detection — DFS (identical to Python implementation)
    // -----------------------------------------------------------------------

    /// Detect all cycles in the graph.
    ///
    /// Returns a list of cycles (each cycle is a list of node indices).
    /// Empty vec means the graph is acyclic.
    ///
    /// Equivalent to Python `DependencyGraph.detect_cycles()`.
    pub fn detect_cycles(&self) -> Vec<Vec<u32>> {
        let mut cycles: Vec<Vec<u32>> = Vec::new();
        let mut visited  = vec![false; self.n];
        let mut in_stack = vec![false; self.n];
        let mut stack: Vec<u32> = Vec::new();

        for start in 0..self.n as u32 {
            if !visited[start as usize] {
                self.dfs_cycles(start, &mut visited, &mut in_stack, &mut stack, &mut cycles);
            }
        }

        cycles
    }

    fn dfs_cycles(
        &self,
        node: u32,
        visited: &mut Vec<bool>,
        in_stack: &mut Vec<bool>,
        stack: &mut Vec<u32>,
        cycles: &mut Vec<Vec<u32>>,
    ) {
        visited[node as usize]   = true;
        in_stack[node as usize]  = true;
        stack.push(node);

        for &succ in &self.successors[node as usize] {
            if !visited[succ as usize] {
                self.dfs_cycles(succ, visited, in_stack, stack, cycles);
            } else if in_stack[succ as usize] {
                // Found a cycle — extract it
                if let Some(pos) = stack.iter().position(|&x| x == succ) {
                    let mut cycle = stack[pos..].to_vec();
                    cycle.push(succ);
                    cycles.push(cycle);
                }
            }
        }

        stack.pop();
        in_stack[node as usize] = false;
    }

    /// Return true if the graph has no cycles.
    pub fn is_acyclic(&self) -> bool {
        self.detect_cycles().is_empty()
    }

    // -----------------------------------------------------------------------
    // Critical path — DP on topological order (identical to Python)
    // -----------------------------------------------------------------------

    /// Return the critical path (longest weighted path from any root to any leaf).
    ///
    /// Returns node indices in order from start to finish.
    /// Equivalent to Python `DependencyGraph.critical_path()`.
    pub fn critical_path(&self) -> Result<Vec<u32>, GraphError> {
        if self.n == 0 {
            return Ok(Vec::new());
        }

        let topo = self.topological_sort()?;

        // earliest[node] = (earliest_start, predecessor_on_critical_path)
        let mut earliest: Vec<(f64, Option<u32>)> = vec![(0.0, None); self.n];

        for &node in &topo {
            let preds = &self.predecessors[node as usize];
            if preds.is_empty() {
                earliest[node as usize] = (0.0, None);
            } else {
                let best_pred = preds.iter().copied().max_by(|&a, &b| {
                    let va = earliest[a as usize].0 + self.weights[a as usize];
                    let vb = earliest[b as usize].0 + self.weights[b as usize];
                    va.partial_cmp(&vb).unwrap_or(std::cmp::Ordering::Equal)
                }).unwrap();

                let start = earliest[best_pred as usize].0 + self.weights[best_pred as usize];
                earliest[node as usize] = (start, Some(best_pred));
            }
        }

        // Find the leaf with the latest finish time
        let leaves: Vec<u32> = (0..self.n as u32)
            .filter(|&i| self.successors[i as usize].is_empty())
            .collect();

        let leaves = if leaves.is_empty() { topo.clone() } else { leaves };

        let last_node = leaves.iter().copied().max_by(|&a, &b| {
            let va = earliest[a as usize].0 + self.weights[a as usize];
            let vb = earliest[b as usize].0 + self.weights[b as usize];
            va.partial_cmp(&vb).unwrap_or(std::cmp::Ordering::Equal)
        }).unwrap();

        // Trace back
        let mut path = Vec::new();
        let mut current = Some(last_node);
        while let Some(node) = current {
            path.push(node);
            current = earliest[node as usize].1;
        }
        path.reverse();
        Ok(path)
    }

    // -----------------------------------------------------------------------
    // Parallel groups — level BFS (identical to Python implementation)
    // -----------------------------------------------------------------------

    /// Return groups of nodes that can execute in parallel.
    ///
    /// Nodes in the same group share the same topological level.
    /// Equivalent to Python `DependencyGraph.parallel_groups()`.
    pub fn parallel_groups(&self) -> Vec<Vec<u32>> {
        if self.n == 0 {
            return Vec::new();
        }

        let mut in_degree: Vec<u32> = self.predecessors.iter()
            .map(|p| p.len() as u32)
            .collect();

        let mut remaining: Vec<bool> = vec![true; self.n];
        let mut groups: Vec<Vec<u32>> = Vec::new();

        loop {
            let mut group: Vec<u32> = (0..self.n as u32)
                .filter(|&i| remaining[i as usize] && in_degree[i as usize] == 0)
                .collect();

            if group.is_empty() {
                break;
            }

            group.sort_unstable(); // determinism
            for &node in &group {
                remaining[node as usize] = false;
                for &succ in &self.successors[node as usize] {
                    if remaining[succ as usize] {
                        in_degree[succ as usize] -= 1;
                    }
                }
            }
            groups.push(group);
        }

        groups
    }
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    /// Build a simple linear chain: 0 → 1 → 2 → ... → n-1
    fn linear_chain(n: usize) -> DependencyGraph {
        let mut g = DependencyGraph::new(n);
        for i in 0..(n as u32 - 1) {
            g.add_edge(i, i + 1);
        }
        g
    }

    /// Build a diamond: 0 → 1, 0 → 2, 1 → 3, 2 → 3
    fn diamond() -> DependencyGraph {
        let mut g = DependencyGraph::new(4);
        g.add_edge(0, 1);
        g.add_edge(0, 2);
        g.add_edge(1, 3);
        g.add_edge(2, 3);
        g
    }

    #[test]
    fn linear_chain_topo_sort() {
        let g = linear_chain(5);
        let order = g.topological_sort().unwrap();
        assert_eq!(order, vec![0, 1, 2, 3, 4]);
    }

    #[test]
    fn diamond_topo_sort_valid() {
        let g = diamond();
        let order = g.topological_sort().unwrap();
        // 0 must come first, 3 must come last
        assert_eq!(order[0], 0);
        assert_eq!(order[order.len() - 1], 3);
        assert_eq!(order.len(), 4);
    }

    #[test]
    fn cycle_detected() {
        let mut g = DependencyGraph::new(3);
        g.add_edge(0, 1);
        g.add_edge(1, 2);
        g.add_edge(2, 0); // cycle
        let cycles = g.detect_cycles();
        assert!(!cycles.is_empty(), "expected cycle");
    }

    #[test]
    fn acyclic_dag_no_cycles() {
        let g = diamond();
        assert!(g.is_acyclic());
    }

    #[test]
    fn critical_path_linear() {
        let mut g = DependencyGraph::new(4);
        for i in 0..3u32 { g.add_edge(i, i + 1); }
        for i in 0..4u32 { g.set_weight(i, 1.0); }
        let path = g.critical_path().unwrap();
        assert_eq!(path, vec![0, 1, 2, 3]);
    }

    #[test]
    fn critical_path_picks_heavier_branch() {
        // 0 → 1 (weight 1.0), 0 → 2 (weight 5.0), both → 3
        let mut g = DependencyGraph::new(4);
        g.add_edge(0, 1);
        g.add_edge(0, 2);
        g.add_edge(1, 3);
        g.add_edge(2, 3);
        g.set_weight(0, 1.0);
        g.set_weight(1, 1.0);
        g.set_weight(2, 5.0);  // heavier
        g.set_weight(3, 1.0);
        let path = g.critical_path().unwrap();
        // Critical path should go through node 2
        assert!(path.contains(&2), "expected node 2 in critical path: {:?}", path);
    }

    #[test]
    fn parallel_groups_linear() {
        let g = linear_chain(4);
        let groups = g.parallel_groups();
        // Each node in its own group for a linear chain
        assert_eq!(groups.len(), 4);
        for (i, grp) in groups.iter().enumerate() {
            assert_eq!(grp, &vec![i as u32]);
        }
    }

    #[test]
    fn parallel_groups_diamond() {
        let g = diamond();
        let groups = g.parallel_groups();
        // [0], [1,2], [3]
        assert_eq!(groups.len(), 3);
        assert_eq!(groups[0], vec![0]);
        assert_eq!(groups[1], vec![1, 2]);
        assert_eq!(groups[2], vec![3]);
    }

    #[test]
    fn large_dag_1000_nodes() {
        // Build a DAG: i → i+1 for even i, creating N/2 parallel chains
        let n = 1000usize;
        let mut g = DependencyGraph::new(n);
        for i in (0..n as u32 - 1).step_by(2) {
            g.add_edge(i, i + 1);
        }
        let order = g.topological_sort().unwrap();
        assert_eq!(order.len(), n);
        assert!(g.is_acyclic());
    }
}
