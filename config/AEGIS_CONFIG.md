# TEMPORARY AEGIS — Configuration

**Generated:** 2026-09-12
**Purpose:** Central configuration for all TEMPORARY AEGIS subsystems

---

## 1. MODEL ROUTING CONFIGURATION

```json
{
  "routing_strategy": "task_based",
  "default_model": "cl/openai/gpt-5.6-terra",
  "fallback_chain": [
    "cl/openai/gpt-5.6-terra",
    "cl/openai/gpt-5.5",
    "cl/anthropic/claude-sonnet-4.6",
    "ag/gemini-3.8-flash"
  ],
  "task_routing": {
    "simple_query": "ag/gemini-3.8-flash-low",
    "default": "cl/openai/gpt-5.6-terra",
    "coding": "cl/openai/gpt-5.6-sol",
    "deep_reasoning": "cl/anthropic/claude-opus-5",
    "code_review": "cl/anthropic/claude-sonnet-4.6",
    "architecture_review": "cl/anthropic/claude-opus-5",
    "research": "cl/anthropic/claude-opus-5",
    "debugging": "cl/anthropic/claude-sonnet-4.6",
    "multimodal": "cl/google/gemini-3.8-flash",
    "long_context": "cl/anthropic/claude-sonnet-5",
    "summarization": "ag/gemini-3.8-flash-low",
    "classification": "ag/gemini-3.8-flash-extra-low",
    "fast_tool_use": "ag/gemini-3.8-flash",
    "long_horizon_agent": "kimi/kimi-k3"
  },
  "model_capabilities": {
    "requires_reasoning": ["deep_reasoning", "architecture_review", "research", "coding"],
    "requires_tools": ["coding", "debugging", "code_review", "fast_tool_use"],
    "requires_vision": ["multimodal"],
    "requires_long_context": ["long_context", "architecture_review", "research"]
  },
  "fallback_rules": {
    "model_unavailable": "Try next in fallback_chain",
    "rate_limited": "Wait 2s, retry once, then fall back",
    "context_overflow": "Try model with larger context window",
    "tool_failure": "Retry once, then try alternate model",
    "all_models_failed": "Report blocker, suggest manual intervention"
  }
}
```

**Usage:** When TEMPORARY AEGIS needs to select a model, it consults this routing table based on the task type.

---

## 2. PRIVACY CONFIGURATION

```json
{
  "privacy_levels": {
    "P0": {
      "label": "PRIVATE",
      "description": "Secrets, credentials, passwords, API keys, tokens, SSH keys",
      "storage": "encrypted_local_only",
      "cloud_allowed": false,
      "auto_detect_patterns": [
        ".env",
        "*.pem",
        "*.key",
        "id_rsa*",
        "id_ed25519*",
        "credentials*",
        "secrets*",
        "password*",
        "api_key*",
        "token*"
      ]
    },
    "P1": {
      "label": "PERSONAL",
      "description": "Personal information, conversations, preferences, non-public user data",
      "storage": "local_preferred",
      "cloud_allowed": "with_user_consent",
      "auto_detect_patterns": []
    },
    "P2": {
      "label": "PROJECT",
      "description": "Project code, architecture, decisions, project-specific knowledge",
      "storage": "project_local",
      "cloud_allowed": true,
      "auto_detect_patterns": []
    },
    "P3": {
      "label": "PUBLIC",
      "description": "General knowledge, documentation, public information",
      "storage": "any",
      "cloud_allowed": true,
      "auto_detect_patterns": []
    }
  },
  "automatic_filtering": {
    "enabled": true,
    "patterns": {
      "files": ["**.env", "**.pem", "**.key", "**id_rsa*", "**id_ed25519*", "***credentials*", "***secrets*", "***password*"],
      "content_patterns": ["api_key=", "token=", "password=", "secret="]
    },
    "action": "redact_or_reject"
  }
}
```

---

## 3. MEMORY CONFIGURATION

```json
{
  "storage_path": "/home/adarshjii/.temporary-aegis/memory",
  "retention": {
    "working_memory_ttl_seconds": 3600,
    "temporary_memory_default_ttl_seconds": 3600,
    "episodic_review_interval_days": 7,
    "episodic_archive_interval_days": 30,
    "semantic_review_interval_days": 90,
    "confidence_threshold_minimum": 0.3
  },
  "ingestion": {
    "auto_ingestion_enabled": true,
    "git_triggered": true,
    "filesystem_triggered": false,
    "session_end_extraction": true,
    "daily_summary": true,
    "weekly_review": true,
    "monthly_audit": true
  },
  "deduplication": {
    "enabled": true,
    "method": "content_hash",
    "merge_similar": true,
    "similarity_threshold": 0.85
  }
}
```

---

## 4. SKILL CONFIGURATION

```json
{
  "skill_directory": "/home/adarshjii/.temporary-aegis/skills",
  "active_skills": [
    "repository-analysis",
    "coding",
    "debugging",
    "linux-troubleshooting",
    "git-analysis",
    "architecture-review",
    "research",
    "documentation",
    "project-resume",
    "environment-audit",
    "memory-audit"
  ],
  "skill_learning": {
    "enabled": true,
    "min_occurrences_before_candidate": 3,
    "test_before_register": true,
    "require_user_confirmation": true
  }
}
```

---

## 5. TOOL CONFIGURATION

```json
{
  "tool_registry_path": "/home/adarshjii/.temporary-aegis/TOOL_REGISTRY.json",
  "capability_discovery": {
    "enabled": true,
    "search_order": ["existing_tools", "existing_skills", "mcp_servers", "cli_tools", "apis", "documentation", "acquire_build"],
    "require_testing_before_registration": true
  },
  "tool_failure_recovery": {
    "retry_attempts": 2,
    "fallback_to_alternate_tool": true,
    "report_blocker_after": 3,
    "record_failure_for_learning": true
  }
}
```

---

## 6. AUTHORIZATION & SECURITY

```json
{
  "authorization_flow": ["REQUEST", "POLICY", "PERMISSION", "EXECUTION", "AUDIT", "VERIFICATION"],
  "risk_tiers": {
    "LOW": {
      "auto_execute": true,
      "audit": "log_only"
    },
    "MEDIUM": {
      "auto_execute": true,
      "audit": "log_with_context"
    },
    "HIGH": {
      "auto_execute": false,
      "require_approval": true,
      "audit": "full"
    },
    "CRITICAL": {
      "auto_execute": false,
      "require_approval": true,
      "audit": "full_with_alert"
    }
  },
  "untrusted_content_policy": {
    "external_content": "treat_as_untrusted",
    "mcp_servers": "treat_as_untrusted",
    "plugins": "treat_as_untrusted",
    "generated_code": "sandbox_before_execution",
    "downloaded_code": "scan_before_execution"
  }
}
```

---

## 7. MULTI-AGENT ORCHESTRATION

```json
{
  "enabled": true,
  "max_concurrent_agents": 5,
  "agent_roles": {
    "planner": "Decompose tasks, create plans",
    "researcher": "Conduct research, find information",
    "coder": "Write and modify code",
    "auditor": "Review code, check quality",
    "critic": "Challenge assumptions, find flaws",
    "executor": "Execute planned actions",
    "synthesizer": "Combine results, create summaries"
  },
  "resource_limits": {
    "max_iterations_per_agent": 250,
    "total_budget_per_task": "configurable"
  },
  "coordination": {
    "shared_context": true,
    "result_aggregation": "synthesizer_role",
    "conflict_resolution": "user_involvement_for_high_stakes"
  }
}
```

---

## 8. AUTOMATION SCHEDULING

```json
{
  "daily_summary": {
    "enabled": true,
    "schedule": "09:00 IST",
    "content": ["projects_worked_on", "major_changes", "problems_encountered", "decisions_made", "research_conducted", "ideas_generated", "skills_discovered", "open_tasks"]
  },
  "weekly_review": {
    "enabled": true,
    "schedule": "Sunday 20:00 IST",
    "content": ["memory_review", "stale_memory_cleanup", "project_resume_summaries", "skill_effectiveness_review"]
  },
  "monthly_audit": {
    "enabled": true,
    "schedule": "1st of month 10:00 IST",
    "content": ["full_memory_audit", "tool_health_check", "model_availability_check", "configuration_review"]
  }
}
```

---

*This configuration is the central reference. Individual subsystems may have their own config files that reference or extend this.*
