"""L1 Dependency Injection container per Prompt 02.
Supported lifetimes: SINGLETON / SCOPED / TRANSIENT / FACTORY / LAZY.
Circular dependency detection is explicit, never silent cycle-by-accident."""
from aegis.l1_core.di.container import DIContainer, Lifetime, Scope

__all__ = ["DIContainer", "Lifetime", "Scope"]
