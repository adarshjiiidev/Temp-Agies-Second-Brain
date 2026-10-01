"""L5 Execution Engine — Verb Hierarchy.

Defines the complete SVRC verb tree and matching rules.
Verbs are colon-separated and hierarchical:
  granting 'fs' grants 'fs.read', 'fs.write', etc.
  granting 'fs.read' does NOT grant 'fs.write'.

Import safety: stdlib only.
"""

from __future__ import annotations

__all__ = [
    "VERB_TREE",
    "verb_matches",
    "verb_implies",
    "get_verb_namespace",
    "ALL_VERBS",
]

# ---------------------------------------------------------------------------
# Complete verb tree
# ---------------------------------------------------------------------------

VERB_TREE: dict[str, list[str]] = {
    "fs": [
        "fs.read",
        "fs.write",
        "fs.append",
        "fs.copy",
        "fs.move",
        "fs.delete",
        "fs.mkdir",
        "fs.chmod",
        "fs.exec",
        "fs.hash",
        "fs.search",
        "fs.watch",
    ],
    "proc": [
        "proc.spawn",
        "proc.read",
        "proc.signal",
        "proc.network_access",
    ],
    "shell": [
        "shell.exec",
    ],
    "python": [
        "python.exec",
        "python.eval",
    ],
    "git": [
        "git.clone",
        "git.status",
        "git.diff",
        "git.log",
        "git.commit",
        "git.branch",
        "git.checkout",
        "git.pull",
        "git.push",
        "git.stash",
        "git.reset",
        "git.merge",
        "git.rebase",
        "git.tag",
    ],
    "docker": [
        "docker.run",
        "docker.build",
        "docker.exec",
        "docker.logs",
        "docker.stop",
        "docker.remove",
        "docker.pull",
        "docker.push",
    ],
    "net": [
        "net.get",
        "net.post",
        "net.put",
        "net.delete",
        "net.patch",
        "net.listen",
        "net.upload",
        "net.request",
    ],
    "obsidian": [
        "obsidian.read",
        "obsidian.create",
        "obsidian.update",
        "obsidian.delete",
        "obsidian.search",
    ],
    "browser": [
        "browser.navigate",
        "browser.read",
        "browser.fill_form",
        "browser.click",
        "browser.download",
        "browser.upload",
        "browser.screenshot",
    ],
    "desktop": [
        "desktop.screenshot",
        "desktop.mouse",
        "desktop.keyboard",
        "desktop.window_manage",
        "desktop.clipboard",
    ],
    "camera": [
        "camera.list",
        "camera.capture",
        "camera.stream",
    ],
    "mic": [
        "mic.listen",
        "mic.stream",
    ],
    "vscode": [
        "vscode.read",
        "vscode.search",
        "vscode.diagnostics",
        "vscode.task",
        "vscode.write",
    ],
    "memory": [
        "memory.read",
        "memory.write",
        "memory.delete",
        "memory.export",
        "memory.promote",
    ],
    "ai": [
        "ai.completion",
        "ai.embedding",
        "ai.fine_tune",
    ],
    "exec": [
        "exec.tool",
        "exec.mcp",
        "exec.generated",
    ],
    "aegis": [
        "aegis.config.read",
        "aegis.config.write",
        "aegis.plugin.load",
        "aegis.plugin.unload",
        "aegis.core.mutate",
        "aegis.user.impersonate",
        "aegis.audit.read",
        "aegis.audit.verify",
    ],
}

# Flat set of all known leaf verbs
ALL_VERBS: frozenset[str] = frozenset(
    verb
    for verbs in VERB_TREE.values()
    for verb in verbs
)

# ---------------------------------------------------------------------------
# Matching functions
# ---------------------------------------------------------------------------


def get_verb_namespace(verb: str) -> str:
    """Return the top-level namespace of a verb (e.g. 'fs.read' → 'fs')."""
    return verb.split(".")[0].split(":")[0]


def verb_implies(grant_verb: str, requested_verb: str) -> bool:
    """Return True if ``grant_verb`` implies permission for ``requested_verb``.

    Rules:
    - Exact match: 'fs.read' implies 'fs.read'
    - Namespace match: 'fs' implies all verbs starting with 'fs.'
    - Wildcard root: '*' implies everything
    - Prefix: 'git.p' does NOT imply 'git.push' (must be exact or namespace)

    Examples::

        verb_implies('fs', 'fs.read')     → True
        verb_implies('fs.read', 'fs')     → False  (narrower doesn't imply broader)
        verb_implies('*', 'git.push')     → True
        verb_implies('fs.write', 'fs.read') → False
    """
    if grant_verb == "*":
        return True
    if grant_verb == requested_verb:
        return True
    # Namespace match: grant_verb is a namespace (no dot or ends before dot)
    ns = get_verb_namespace(grant_verb)
    if grant_verb == ns:
        # 'fs' granted: any 'fs.*' is covered
        return requested_verb.startswith(ns + ".")
    # Prefix hierarchical: 'git.p' is not a valid namespace check
    # Only exact match or pure namespace (no dot in grant) qualify
    return False


def verb_matches(grant_verbs: list[str], requested_verb: str) -> bool:
    """Return True if any grant in ``grant_verbs`` implies ``requested_verb``."""
    return any(verb_implies(g, requested_verb) for g in grant_verbs)


def is_known_verb(verb: str) -> bool:
    """Return True if the verb is in the known verb tree (leaf or namespace)."""
    if verb == "*":
        return True
    ns = get_verb_namespace(verb)
    if verb == ns:
        return ns in VERB_TREE
    return verb in ALL_VERBS
