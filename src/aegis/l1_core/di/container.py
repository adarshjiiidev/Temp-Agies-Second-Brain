"""L1 Core Dependency Injection container.

Supported lifetimes:
  - SINGLETON: one instance per container; disposed when container closes
  - SCOPED: one instance per Scope; disposed when scope closes
  - TRANSIENT: new instance per resolution; never disposed by container
  - FACTORY: injects a factory function () -> T (registered as Callable[[], T])
  - LAZY: wraps resolution in Lazy[T] descriptor; resolved on first attribute access

Circular dependency detection uses a "current resolution stack" per Scope.
Detected cycles raise AegisError with CIRCULAR_DEPENDENCY code, never silently cycle-break.
"""

from __future__ import annotations

import contextlib
import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any, Generic, TypeVar

from aegis.l1_core.errors.base import AegisError, ErrorContext

T = TypeVar("T")


class Lifetime(str, Enum):
    SINGLETON = "singleton"
    SCOPED = "scoped"
    TRANSIENT = "transient"
    FACTORY = "factory"
    LAZY = "lazy"


class RegistrationError(AegisError):
    def __init__(self, message: str, *, component: str = "di", **kw: Any) -> None:
        super().__init__(
            message, context=ErrorContext(component=component, operation="register"), **kw
        )


class ResolutionError(AegisError):
    def __init__(self, message: str, *, component: str = "di", **kw: Any) -> None:
        super().__init__(
            message, context=ErrorContext(component=component, operation="resolve"), **kw
        )


@dataclass
class _Registration:
    key: str
    lifetime: Lifetime
    factory: Callable[..., Any]
    dependencies: tuple[str, ...] = ()
    singleton_instance: Any = None  # for lifetime=SINGLETON
    created: bool = False


class Lazy(Generic[T]):
    """Lazy descriptor: resolves the dependency on first access to .value."""

    def __init__(self, resolve: Callable[[], T]) -> None:
        self._resolve = resolve
        self._cached: T | None = None
        self._has_value = False

    @property
    def value(self) -> T:
        if not self._has_value:
            self._cached = self._resolve()
            self._has_value = True
        return self._cached  # type: ignore[return-value]


class Scope:
    """A scoped resolution context. Owns SCOPED lifetime instances and detection stack."""

    def __init__(self, container: DIContainer) -> None:
        self.scope_id = uuid.uuid4()
        self.container = container
        self._scoped_instances: dict[str, Any] = {}
        self._resolving: list[str] = []  # stack for circular dep detection
        self._resolving_lock = threading.RLock()
        self._disposed = False

    # -------- core resolve --------

    def resolve(self, key: str | type[T]) -> T:
        if self._disposed:
            raise ResolutionError(f"Scope {self.scope_id} disposed; cannot resolve {key}")
        key_str = self._normalize(key)
        with self._resolving_lock:
            if key_str in self._resolving:
                cycle = " → ".join(self._resolving + [key_str])
                raise ResolutionError(
                    f"Circular dependency detected: {cycle}",
                    error_code="E10202",
                )
            self._resolving.append(key_str)
        try:
            return self._do_resolve(key_str)
        finally:
            with self._resolving_lock, contextlib.suppress(ValueError):
                self._resolving.remove(key_str)

    def _do_resolve(self, key: str) -> Any:
        reg = self.container._regs.get(key)
        if reg is None:
            # Allow fallthrough: default factories for built-in known types
            builtin = self.container._builtins.get(key)
            if builtin is not None:
                return builtin()
            raise ResolutionError(f"No registration for key='{key}'", error_code="E10201")

        # Factory lifetime: inject factory callable (NOT the result)
        if reg.lifetime == Lifetime.FACTORY:

            def _factory(*, _reg=reg) -> Any:  # type: ignore[misc]
                return self._construct(_reg)

            return _factory

        # Lazy lifetime: inject Lazy wrapper
        if reg.lifetime == Lifetime.LAZY:
            return Lazy(lambda: self._construct(reg))  # type: ignore[return-value]

        # Singleton: cache on registration
        if reg.lifetime == Lifetime.SINGLETON:
            if not reg.created:
                reg.singleton_instance = self._construct(reg)
                reg.created = True
            return reg.singleton_instance

        # Scoped: cache on scope
        if reg.lifetime == Lifetime.SCOPED:
            if key not in self._scoped_instances:
                self._scoped_instances[key] = self._construct(reg)
            return self._scoped_instances[key]

        # Transient: always new
        return self._construct(reg)

    def _construct(self, reg: _Registration) -> Any:
        deps = [self.resolve(d) for d in reg.dependencies]
        try:
            return reg.factory(*deps)
        except AegisError:
            raise
        except Exception as exc:
            raise ResolutionError(
                f"Factory for {reg.key} raised {type(exc).__name__}: {exc!s}",
                cause=exc,
            ) from exc

    # -------- cleanup --------

    def _cleanup_instances_sync(self, instances: list) -> None:
        import asyncio as _aio
        import inspect as _inspect

        for instance in instances:
            aclose = getattr(instance, "aclose", None)
            close = getattr(instance, "close", None)
            try:
                if aclose is not None and callable(aclose):
                    coro = aclose()
                    try:
                        loop = _aio.get_running_loop()
                    except RuntimeError:
                        _aio.run(coro)
                        continue
                    try:
                        loop.run_until_complete(coro)
                    except RuntimeError:
                        loop.create_task(coro)
                elif close is not None and callable(close):
                    if _inspect.iscoroutinefunction(close) or _inspect.isasyncgenfunction(close):
                        coro = close()
                        try:
                            loop = _aio.get_running_loop()
                        except RuntimeError:
                            _aio.run(coro)
                            continue
                        try:
                            loop.run_until_complete(coro)
                        except RuntimeError:
                            loop.create_task(coro)
                    else:
                        result = close()
                        if hasattr(result, "__await__"):
                            try:
                                loop = _aio.get_running_loop()
                            except RuntimeError:
                                _aio.run(result)
                                continue
                            try:
                                loop.run_until_complete(result)
                            except RuntimeError:
                                loop.create_task(result)
            except Exception:
                pass

    def close(self) -> None:
        """Dispose scoped instances (sync entry point)."""
        if self._disposed:
            return
        self._disposed = True
        instances = list(reversed(list(self._scoped_instances.values())))
        self._cleanup_instances_sync(instances)
        self._scoped_instances.clear()

    async def aclose(self) -> None:
        """Dispose all scoped instances that implement close()/aclose()."""
        if self._disposed:
            return
        self._disposed = True
        for instance in reversed(list(self._scoped_instances.values())):
            aclose = getattr(instance, "aclose", None)
            close = getattr(instance, "close", None)
            try:
                if aclose is not None and callable(aclose):
                    await aclose()
                elif close is not None and callable(close):
                    result = close()
                    if hasattr(result, "__await__"):
                        await result
            except Exception:
                pass
        self._scoped_instances.clear()

    # -------- helpers --------

    @staticmethod
    def _normalize(key: str | type[Any]) -> str:
        if isinstance(key, str):
            return key
        mod = getattr(key, "__module__", "") or ""
        name = getattr(key, "__qualname__", getattr(key, "__name__", str(key)))
        return f"{mod}.{name}" if mod else name


class DIContainer:
    """Root DI container. Register once, then create Scope objects to resolve."""

    def __init__(self) -> None:
        self._regs: dict[str, _Registration] = {}
        self._builtins: dict[str, Callable[[], Any]] = {}
        self._root_scope: Scope | None = None  # singleton resolution uses root for stack
        self._closed = False
        self._lock = threading.RLock()

    # -------- Registration API --------

    def register(
        self,
        key: str | type[T],
        lifetime: Lifetime | Callable[..., T],
        factory: Callable[..., T] | None = None,
        *,
        dependencies: tuple[str | type[Any], ...] = (),
        deps: tuple[str | type[Any], ...] | None = None,
    ) -> None:
        if self._closed:
            raise RegistrationError("Container closed; cannot register")
        # Support two call conventions:
        #   A) register(key, factory, *, lifetime=..., dependencies=...)
        #   B) register(key, lifetime, factory, *, deps=[...])  # tests + examples
        if callable(lifetime) and factory is None:
            # Convention A: factory is 2nd positional, lifetime= keyword only
            actual_factory: Callable[..., T] = lifetime  # type: ignore[assignment]
            actual_lifetime = Lifetime.SINGLETON
            actual_deps = dependencies
        else:
            # Convention B: lifetime is 2nd positional, factory is 3rd positional
            actual_lifetime = lifetime  # type: ignore[assignment]
            actual_factory = factory  # type: ignore[assignment]
            if actual_factory is None:
                raise RegistrationError("register requires a factory callable")
            actual_deps = tuple(deps) if deps is not None else dependencies
        with self._lock:
            norm = Scope._normalize(key)
            if norm in self._regs:
                raise RegistrationError(f"Key already registered: {norm}")
            norm_deps = tuple(Scope._normalize(d) for d in actual_deps)
            self._regs[norm] = _Registration(
                key=norm,
                lifetime=actual_lifetime,
                factory=actual_factory,
                dependencies=norm_deps,
            )

    def register_singleton(self, key: str | type[T], instance: T) -> None:
        """Register a pre-constructed singleton directly (no factory call)."""
        key_str = Scope._normalize(key)
        reg = _Registration(
            key=key_str,
            lifetime=Lifetime.SINGLETON,
            factory=lambda: instance,
        )
        reg.singleton_instance = instance
        reg.created = True
        with self._lock:
            self._regs[key_str] = reg

    def register_builtin(self, key: str | type[T], factory: Callable[[], T]) -> None:
        """Fallback if not explicitly registered. Used by runtime for bootstrap services."""
        self._builtins[Scope._normalize(key)] = factory

    # -------- Resolution API --------

    def create_scope(self) -> Scope:
        if self._closed:
            raise RegistrationError("Container closed")
        scope = Scope(self)
        if self._root_scope is None:
            self._root_scope = scope  # first scope is used for singleton stacks
        return scope

    def resolve(self, key: str | type[T]) -> T:
        """Resolve using an implicit root scope (created on demand)."""
        if self._root_scope is None:
            self._root_scope = self.create_scope()
        return self._root_scope.resolve(key)

    # -------- Cleanup --------

    def close(self) -> None:
        """Sync entry point for container cleanup."""
        if self._closed:
            return
        with self._lock:
            self._closed = True
            if self._root_scope is not None:
                self._root_scope.close()
            # Singletons with close()
            singletons = [
                reg.singleton_instance
                for reg in reversed(list(self._regs.values()))
                if reg.lifetime == Lifetime.SINGLETON
                and reg.created
                and reg.singleton_instance is not None
            ]
            if self._root_scope is not None:
                self._root_scope._cleanup_instances_sync(singletons)
            else:
                # Use a temporary scope instance's helper via standalone code
                import asyncio as _aio
                import inspect as _inspect

                for instance in singletons:
                    aclose = getattr(instance, "aclose", None)
                    close = getattr(instance, "close", None)
                    try:
                        if aclose is not None and callable(aclose):
                            coro = aclose()
                            try:
                                loop = _aio.get_running_loop()
                            except RuntimeError:
                                _aio.run(coro)
                                continue
                            try:
                                loop.run_until_complete(coro)
                            except RuntimeError:
                                loop.create_task(coro)
                        elif close is not None and callable(close):
                            if _inspect.iscoroutinefunction(close) or _inspect.isasyncgenfunction(
                                close
                            ):
                                coro = close()
                                try:
                                    loop = _aio.get_running_loop()
                                except RuntimeError:
                                    _aio.run(coro)
                                    continue
                                try:
                                    loop.run_until_complete(coro)
                                except RuntimeError:
                                    loop.create_task(coro)
                            else:
                                res = close()
                                if hasattr(res, "__await__"):
                                    try:
                                        loop = _aio.get_running_loop()
                                    except RuntimeError:
                                        _aio.run(res)
                                        continue
                                    try:
                                        loop.run_until_complete(res)
                                    except RuntimeError:
                                        loop.create_task(res)
                    except Exception:
                        pass

    async def aclose(self) -> None:
        if self._closed:
            return
        with self._lock:
            self._closed = True
            if self._root_scope is not None:
                await self._root_scope.aclose()
            # Singletons with close()
            for reg in reversed(list(self._regs.values())):
                if (
                    reg.lifetime == Lifetime.SINGLETON
                    and reg.created
                    and reg.singleton_instance is not None
                ):
                    aclose = getattr(reg.singleton_instance, "aclose", None)
                    close = getattr(reg.singleton_instance, "close", None)
                    try:
                        if aclose and callable(aclose):
                            await aclose()
                        elif close and callable(close):
                            res = close()
                            if hasattr(res, "__await__"):
                                await res
                    except Exception:
                        pass
