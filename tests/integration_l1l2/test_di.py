"""Prompt 02 tests: DI container, lifetimes, circular dep detection, cleanup."""

from __future__ import annotations

import pytest

import aegis
from aegis import DIContainer, Lifetime


class _A:
    def __init__(self, b: _B = None) -> None:  # type: ignore[valid-type]
        self.b = b
        self.closed = False

    def close(self) -> None:
        self.closed = True


class _B:
    def __init__(self, a: _A | None = None) -> None:
        self.a = a


def test_singleton_returns_same_instance():
    c = DIContainer()
    c.register("a", Lifetime.SINGLETON, lambda: _A())
    x = c.resolve("a")
    y = c.resolve("a")
    assert x is y


def test_transient_returns_new():
    c = DIContainer()
    c.register("a", Lifetime.TRANSIENT, lambda: _A())
    x = c.resolve("a")
    y = c.resolve("a")
    assert x is not y


def test_scoped_isolated_between_scopes():
    c = DIContainer()
    c.register("a", Lifetime.SCOPED, lambda: _A())
    s1 = c.create_scope()
    s2 = c.create_scope()
    a1 = s1.resolve("a")
    a2 = s2.resolve("a")
    assert a1 is not a2
    # Same scope returns same
    assert s1.resolve("a") is a1


def test_lazy_requires_explicit_value_access():
    c = DIContainer()
    calls: list[int] = []

    def factory():
        calls.append(1)
        return _A()

    c.register("a", Lifetime.LAZY, factory)
    lz = c.resolve("a")
    assert len(calls) == 0  # not evaluated yet
    inst = lz.value
    assert isinstance(inst, _A)
    assert len(calls) == 1
    # second access cached
    lz.value
    assert len(calls) == 1


def test_factory_returns_callable():
    c = DIContainer()
    c.register("a_f", Lifetime.FACTORY, lambda: _A())
    fn = c.resolve("a_f")
    assert callable(fn)
    assert fn() is not fn()


def test_scope_close_calls_close_on_instances():
    c = DIContainer()
    c.register("a", Lifetime.SCOPED, lambda: _A())
    s = c.create_scope()
    a = s.resolve("a")
    s.close()
    assert a.closed is True


def test_circular_dependency_raises():
    c = DIContainer()
    c.register("a", Lifetime.TRANSIENT, lambda b: _A(b=b), deps=["b"])
    c.register("b", Lifetime.TRANSIENT, lambda a: _B(a=a), deps=["a"])
    s = c.create_scope()
    with pytest.raises(aegis.AegisError):
        s.resolve("a")
