"""L6 Planning Engine — Intent Parser.

Parses raw user goal text into a typed Intent with detected domain,
primary verb, required tools, and confidence score.

No LLM calls — fully deterministic keyword/pattern-based in P06.

Import safety: stdlib + pydantic + l6_planning.types only.
"""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field

from aegis.l6_planning.types import IntentDomain

__all__ = ["Intent", "IntentParser"]


# ---------------------------------------------------------------------------
# Domain keyword mapping (order = priority)
# ---------------------------------------------------------------------------

_DOMAIN_KEYWORDS: list[tuple[IntentDomain, list[str]]] = [
    (IntentDomain.CODING, [
        "code", "program", "develop", "implement", "build", "refactor",
        "debug", "test", "fix bug", "write a function", "write a class",
        "react", "python", "javascript", "typescript", "api", "backend",
        "frontend", "database", "deploy", "docker", "git", "repository",
        "module", "library", "package", "script", "cli",
    ]),
    (IntentDomain.RESEARCH, [
        "research", "study", "learn", "investigate", "analyse", "analyze",
        "survey", "literature", "paper", "find information", "gather data",
        "compare", "quantum", "topic", "overview", "explain", "summarize",
        "summarise", "report",
    ]),
    (IntentDomain.BROWSER, [
        "browse", "website", "web page", "url", "navigate", "search online",
        "download from", "fill form", "click", "scrape", "crawl",
    ]),
    (IntentDomain.FILESYSTEM, [
        "file", "folder", "directory", "path", "move", "copy", "rename",
        "delete file", "organize", "organise", "vault", "obsidian",
        "sort files", "clean up",
    ]),
    (IntentDomain.TERMINAL, [
        "run command", "execute", "shell", "terminal", "bash", "powershell",
        "install", "pip install", "npm install", "cargo",
    ]),
    (IntentDomain.FINANCE, [
        "trade", "stock", "invest", "portfolio", "market", "nse", "bse",
        "finance", "budget", "expense", "money", "crypto",
    ]),
    (IntentDomain.AUTOMATION, [
        "automate", "automation", "workflow", "schedule", "recurring",
        "batch", "pipeline", "trigger",
    ]),
    (IntentDomain.VISION, [
        "image", "photo", "picture", "camera", "screenshot", "ocr",
        "detect", "recognise", "recognize", "classify",
    ]),
    (IntentDomain.VOICE, [
        "voice", "speech", "audio", "record", "transcribe", "speak", "tts",
    ]),
    (IntentDomain.PLANNING, [
        "plan", "prepare", "outline", "strategy", "roadmap", "presentation",
        "project plan",
    ]),
]

_INTERNET_KEYWORDS = [
    "online", "web", "internet", "download", "browse", "search",
    "fetch", "api call", "http", "url", "website",
]

_LOCAL_ONLY_KEYWORDS = [
    "offline", "local", "on-device", "no internet", "private",
    "without internet",
]

_TOOL_KEYWORDS: dict[str, list[str]] = {
    "git": ["git", "repository", "commit", "branch", "pull request"],
    "docker": ["docker", "container", "dockerfile"],
    "python": ["python", "pip", ".py", "script"],
    "browser": ["browser", "web", "url", "website"],
    "filesystem": ["file", "folder", "directory", "path"],
    "obsidian": ["obsidian", "vault", "note"],
}


# ---------------------------------------------------------------------------
# Intent model
# ---------------------------------------------------------------------------


class Intent(BaseModel):
    """Typed representation of parsed user intent."""

    raw_text: str
    domain: IntentDomain
    primary_verb: str
    target_resource: str | None = None
    detected_tools: list[str] = Field(default_factory=list)
    requires_internet: bool = False
    requires_local_only: bool = False
    confidence: float = Field(default=0.6, ge=0.0, le=1.0)
    ambiguities: list[str] = Field(default_factory=list)
    keyword_matches: list[str] = Field(default_factory=list)

    @property
    def is_ambiguous(self) -> bool:
        return len(self.ambiguities) > 0 or self.confidence < 0.4

    @property
    def is_mixed(self) -> bool:
        return self.domain is IntentDomain.MIXED


# ---------------------------------------------------------------------------
# Intent Parser
# ---------------------------------------------------------------------------


class IntentParser:
    """Parses raw goal text into a typed Intent.

    Fully deterministic — no LLM calls. Uses keyword matching with
    domain priority ordering and confidence scoring.

    Usage::

        parser = IntentParser()
        intent = parser.parse("Build a React portfolio website")
        # intent.domain == IntentDomain.CODING
        # intent.detected_tools == ["browser", "python"]
    """

    def parse(self, goal_text: str, context: dict[str, Any] | None = None) -> Intent:
        """Parse goal text into a typed Intent.

        Args:
            goal_text: Raw user goal string.
            context: Optional planning context hints.

        Returns:
            Typed Intent with domain, confidence, tools, ambiguities.
        """
        text = goal_text.strip()
        lower = text.lower()

        domain, keyword_matches, confidence = self._detect_domain(lower)
        primary_verb = self._extract_primary_verb(lower)
        target_resource = self._extract_target(text, domain)
        detected_tools = self._detect_tools(lower)
        requires_internet = self._check_internet(lower)
        requires_local_only = self._check_local_only(lower)
        ambiguities = self._detect_ambiguities(lower, domain, confidence)

        # Context overrides
        if context:
            if context.get("force_offline"):
                requires_local_only = True
                requires_internet = False
            if context.get("domain_hint"):
                try:
                    domain = IntentDomain(context["domain_hint"])
                    confidence = min(1.0, confidence + 0.2)
                except ValueError:
                    pass

        return Intent(
            raw_text=text,
            domain=domain,
            primary_verb=primary_verb,
            target_resource=target_resource,
            detected_tools=detected_tools,
            requires_internet=requires_internet,
            requires_local_only=requires_local_only,
            confidence=confidence,
            ambiguities=ambiguities,
            keyword_matches=keyword_matches,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _detect_domain(self, lower: str) -> tuple[IntentDomain, list[str], float]:
        """Returns (domain, matched_keywords, confidence)."""
        domain_scores: dict[IntentDomain, list[str]] = {}

        for domain, keywords in _DOMAIN_KEYWORDS:
            matches = [kw for kw in keywords if kw in lower]
            if matches:
                domain_scores[domain] = matches

        if not domain_scores:
            return IntentDomain.UNKNOWN, [], 0.3

        if len(domain_scores) == 1:
            domain, matches = next(iter(domain_scores.items()))
            confidence = min(0.95, 0.55 + len(matches) * 0.10)
            return domain, matches, confidence

        # Multiple domains → pick highest match count; mark as MIXED if close
        sorted_domains = sorted(domain_scores.items(), key=lambda x: len(x[1]), reverse=True)
        top_domain, top_matches = sorted_domains[0]
        second_domain, second_matches = sorted_domains[1]

        if len(top_matches) == len(second_matches):
            all_matches = top_matches + second_matches
            return IntentDomain.MIXED, all_matches, 0.50

        confidence = min(0.90, 0.50 + len(top_matches) * 0.08)
        return top_domain, top_matches, confidence

    def _extract_primary_verb(self, lower: str) -> str:
        """Extract the first action verb from the goal text."""
        verb_patterns = [
            r"\b(build|create|make|write|develop|implement|design)\b",
            r"\b(research|study|investigate|analyze|analyse|learn)\b",
            r"\b(organize|organise|sort|clean|manage|prepare)\b",
            r"\b(train|run|execute|deploy|install|configure)\b",
            r"\b(refactor|fix|debug|improve|optimize|optimise)\b",
            r"\b(find|search|fetch|download|browse)\b",
        ]
        for pattern in verb_patterns:
            match = re.search(pattern, lower)
            if match:
                return match.group(1)
        # Fallback: first word
        words = lower.split()
        return words[0] if words else "do"

    def _extract_target(self, text: str, domain: IntentDomain) -> str | None:
        """Attempt to extract the primary target resource/object."""
        # Look for quoted strings first
        quoted = re.findall(r'"([^"]+)"|\'([^\']+)\'', text)
        if quoted:
            return quoted[0][0] or quoted[0][1]

        # Look for "a <noun phrase>" or "an <noun phrase>"
        match = re.search(r'\b(?:a|an|the|my)\s+([A-Za-z][A-Za-z0-9 _-]{1,30})', text)
        if match:
            return match.group(1).strip()

        return None

    def _detect_tools(self, lower: str) -> list[str]:
        """Detect which tool categories are mentioned."""
        detected: list[str] = []
        for tool, keywords in _TOOL_KEYWORDS.items():
            if any(kw in lower for kw in keywords):
                detected.append(tool)
        return detected

    def _check_internet(self, lower: str) -> bool:
        return any(kw in lower for kw in _INTERNET_KEYWORDS)

    def _check_local_only(self, lower: str) -> bool:
        return any(kw in lower for kw in _LOCAL_ONLY_KEYWORDS)

    def _detect_ambiguities(
        self, lower: str, domain: IntentDomain, confidence: float
    ) -> list[str]:
        """Identify sources of ambiguity in the goal."""
        issues: list[str] = []

        if confidence < 0.40:
            issues.append("The primary domain of the goal is unclear.")

        if domain is IntentDomain.MIXED:
            issues.append("The goal spans multiple domains — clarify the primary focus.")

        if domain is IntentDomain.UNKNOWN:
            issues.append("Could not determine what kind of task this is.")

        # Very short goal
        if len(lower.split()) < 4:
            issues.append("Goal description is very short — more detail would improve planning accuracy.")

        # Vague terms
        vague_terms = ["something", "stuff", "things", "some", "maybe", "perhaps"]
        if any(vt in lower.split() for vt in vague_terms):
            issues.append("Goal contains vague terms — please be more specific.")

        return issues
