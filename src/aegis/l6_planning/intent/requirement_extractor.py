"""L6 Planning Engine — Requirement Extractor.

Automatically infers requirements from a parsed Intent:
software needed, permissions, memory tier, internet, effort, approval points.

Import safety: stdlib + pydantic + l6_planning.types + l6_planning.intent only.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from aegis.l6_planning.intent.intent_parser import Intent
from aegis.l6_planning.types import EffortEstimate, IntentDomain, ResourceSpec, RiskLevel

__all__ = ["Requirements", "RequirementExtractor"]


class Requirements(BaseModel):
    """Inferred requirements for a planned goal."""

    software_needed: list[str] = Field(default_factory=list)
    permissions_needed: list[str] = Field(default_factory=list)
    resources: list[ResourceSpec] = Field(default_factory=list)
    internet_required: bool = False
    offline_capable: bool = True
    estimated_effort: EffortEstimate = Field(default_factory=EffortEstimate.medium)
    human_approval_points: list[str] = Field(default_factory=list)
    gpu_required: bool = False
    estimated_ram_mb: int | None = None
    max_risk_level: RiskLevel = RiskLevel.MEDIUM
    notes: list[str] = Field(default_factory=list)


# Domain → base requirements mapping
_DOMAIN_SOFTWARE: dict[IntentDomain, list[str]] = {
    IntentDomain.CODING: ["python>=3.10", "git"],
    IntentDomain.RESEARCH: [],
    IntentDomain.BROWSER: ["browser-engine"],
    IntentDomain.FILESYSTEM: [],
    IntentDomain.TERMINAL: ["shell"],
    IntentDomain.FINANCE: ["data-feed-adapter"],
    IntentDomain.AUTOMATION: [],
    IntentDomain.VISION: ["ocr-engine"],
    IntentDomain.VOICE: ["tts-engine", "stt-engine"],
    IntentDomain.PLANNING: [],
    IntentDomain.MIXED: [],
    IntentDomain.UNKNOWN: [],
}

_DOMAIN_PERMISSIONS: dict[IntentDomain, list[str]] = {
    IntentDomain.CODING: ["fs.read", "fs.write", "git.*"],
    IntentDomain.RESEARCH: ["net.get"],
    IntentDomain.BROWSER: ["browser.*", "net.get"],
    IntentDomain.FILESYSTEM: ["fs.read", "fs.write"],
    IntentDomain.TERMINAL: ["shell.exec"],
    IntentDomain.FINANCE: ["net.get"],
    IntentDomain.AUTOMATION: ["fs.read", "fs.write"],
    IntentDomain.VISION: ["desktop.screenshot"],
    IntentDomain.VOICE: [],
    IntentDomain.PLANNING: [],
    IntentDomain.MIXED: [],
    IntentDomain.UNKNOWN: [],
}

_DOMAIN_EFFORT: dict[IntentDomain, EffortEstimate] = {
    IntentDomain.CODING: EffortEstimate.large(),
    IntentDomain.RESEARCH: EffortEstimate.medium(),
    IntentDomain.BROWSER: EffortEstimate.small(),
    IntentDomain.FILESYSTEM: EffortEstimate.small(),
    IntentDomain.TERMINAL: EffortEstimate.trivial(),
    IntentDomain.FINANCE: EffortEstimate.large(),
    IntentDomain.AUTOMATION: EffortEstimate.medium(),
    IntentDomain.VISION: EffortEstimate.medium(),
    IntentDomain.VOICE: EffortEstimate.small(),
    IntentDomain.PLANNING: EffortEstimate.medium(),
    IntentDomain.MIXED: EffortEstimate.large(),
    IntentDomain.UNKNOWN: EffortEstimate.medium(),
}

_HIGH_RISK_DOMAINS = {IntentDomain.TERMINAL, IntentDomain.FINANCE, IntentDomain.BROWSER}


class RequirementExtractor:
    """Infers structured requirements from a parsed Intent.

    Usage::

        extractor = RequirementExtractor()
        reqs = extractor.extract(intent)
        # reqs.software_needed == ["python>=3.10", "git"]
        # reqs.permissions_needed == ["fs.read", "fs.write", "git.*"]
    """

    def extract(self, intent: Intent) -> Requirements:
        """Extract requirements from a parsed Intent.

        Args:
            intent: Parsed intent from IntentParser.

        Returns:
            Requirements object with inferred dependencies.
        """
        domain = intent.domain
        software = list(_DOMAIN_SOFTWARE.get(domain, []))
        permissions = list(_DOMAIN_PERMISSIONS.get(domain, []))
        effort = _DOMAIN_EFFORT.get(domain, EffortEstimate.medium())
        internet_required = intent.requires_internet
        offline_capable = not internet_required
        notes: list[str] = []
        approval_points: list[str] = []
        max_risk = RiskLevel.LOW

        # Tool-specific adjustments
        if "git" in intent.detected_tools:
            if "git.*" not in permissions:
                permissions.append("git.*")
            if "git" not in software:
                software.append("git")

        if "docker" in intent.detected_tools:
            software.append("docker")
            permissions.append("docker.*")
            approval_points.append("Docker container provisioning requires user confirmation")
            max_risk = RiskLevel.HIGH

        if "browser" in intent.detected_tools:
            internet_required = True
            offline_capable = False
            if "net.get" not in permissions:
                permissions.append("net.get")

        if "obsidian" in intent.detected_tools:
            if "fs.read" not in permissions:
                permissions.append("fs.read")
            if "obsidian.read" not in permissions:
                permissions.extend(["obsidian.read", "obsidian.create"])

        # High-risk domain overrides
        if domain in _HIGH_RISK_DOMAINS:
            max_risk = max(max_risk, RiskLevel.MEDIUM)
            if domain is IntentDomain.TERMINAL:
                approval_points.append("Shell command execution requires user confirmation")
                max_risk = RiskLevel.HIGH
            if domain is IntentDomain.FINANCE:
                approval_points.append("Financial actions must be explicitly approved")
                max_risk = RiskLevel.CRITICAL
                notes.append("Live trading is disabled by default — paper trading only")

        # Internet requirements
        if intent.requires_internet and intent.requires_local_only:
            notes.append("Conflicting constraints: internet required but local-only requested. Defaulting to local-only.")
            internet_required = False
            offline_capable = True

        if intent.requires_local_only:
            internet_required = False
            offline_capable = True

        # Build ResourceSpec list
        resources = [
            ResourceSpec(name=sw, kind="tool", required=True)
            for sw in software
        ]
        for perm in permissions:
            resources.append(ResourceSpec(name=perm, kind="permission", required=True))

        return Requirements(
            software_needed=software,
            permissions_needed=permissions,
            resources=resources,
            internet_required=internet_required,
            offline_capable=offline_capable,
            estimated_effort=effort,
            human_approval_points=approval_points,
            max_risk_level=max_risk,
            notes=notes,
        )
