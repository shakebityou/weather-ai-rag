"""熔断器（Circuit Breaker）：三态模型 CLOSED → OPEN → HALF_OPEN。

用法：
    @circuit("llm-grade", failure_threshold=3, recovery_timeout=30)
    def grade(question, doc):
        ...

    # 熔断器打开时调用 fallback 而非抛异常
    @circuit("llm-qa", fallback=lambda *a, **k: None)
    def answer(question):
        ...

状态说明：
    CLOSED    正常放行，连续失败达阈值后 → OPEN
    OPEN      快速失败（调用 fallback），超时后 → HALF_OPEN
    HALF_OPEN 放行一次探测请求，成功 → CLOSED，失败 → OPEN
"""
import functools
import threading
import time
from enum import Enum


class State(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """线程安全的熔断器实例。"""

    def __init__(self, name: str, failure_threshold: int = 3,
                 recovery_timeout: float = 30.0):
        self.name = name
        self.failure_threshold = max(1, failure_threshold)
        self.recovery_timeout = max(1.0, recovery_timeout)
        self._state = State.CLOSED
        self._failures = 0
        self._opened_at = 0.0
        self._lock = threading.Lock()

    @property
    def state(self) -> State:
        with self._lock:
            if self._state == State.OPEN and \
                    time.time() - self._opened_at >= self.recovery_timeout:
                self._state = State.HALF_OPEN
            return self._state

    def allow_request(self) -> bool:
        return self.state != State.OPEN

    def record_success(self):
        with self._lock:
            self._failures = 0
            self._state = State.CLOSED

    def record_failure(self):
        with self._lock:
            self._failures += 1
            if self._state == State.HALF_OPEN or \
                    self._failures >= self.failure_threshold:
                self._state = State.OPEN
                self._opened_at = time.time()

    @property
    def failures(self) -> int:
        with self._lock:
            return self._failures


# 全局熔断器注册表，按 name 复用实例
_registry: dict[str, CircuitBreaker] = {}
_registry_lock = threading.Lock()


def get_breaker(name: str, failure_threshold: int = 3,
                recovery_timeout: float = 30.0) -> CircuitBreaker:
    with _registry_lock:
        cb = _registry.get(name)
        if cb is None:
            cb = CircuitBreaker(name, failure_threshold, recovery_timeout)
            _registry[name] = cb
        return cb


def circuit(name: str, failure_threshold: int = 3,
            recovery_timeout: float = 30.0, fallback=None):
    """熔断器装饰器。

    Args:
        name: 熔断器名称，相同名称共享同一实例。
        failure_threshold: 连续失败次数阈值，达到后熔断。
        recovery_timeout: 熔断后恢复探测的等待秒数。
        fallback: 熔断时的降级回调，签名需与被装饰函数一致。
                  为 None 时熔断会直接抛出 RuntimeError。
    """
    def decorator(func):
        cb = get_breaker(name, failure_threshold, recovery_timeout)

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if not cb.allow_request():
                print(f"[circuit-breaker:{name}] 熔断中，调用降级方案")
                if fallback is not None:
                    return fallback(*args, **kwargs)
                raise RuntimeError(f"Circuit breaker '{name}' is OPEN")
            try:
                result = func(*args, **kwargs)
                cb.record_success()
                return result
            except Exception as e:
                cb.record_failure()
                print(f"[circuit-breaker:{name}] 调用失败 "
                      f"({cb.failures}/{cb.failure_threshold}): {e}")
                # 本次失败触发熔断后，直接走降级
                if not cb.allow_request() and fallback is not None:
                    print(f"[circuit-breaker:{name}] 已熔断，调用降级方案")
                    return fallback(*args, **kwargs)
                raise
        return wrapper
    return decorator
