"""
Resilience and Circuit Breaker subsystem for fault tolerance, automatic failure isolation, and graceful degradation.
"""

import time
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional, Callable

try:
    from events import events
except ImportError:
    from src.events import events


CIRCUIT_STATES = {"CLOSED", "OPEN", "HALF_OPEN"}


@dataclass
class CircuitBreaker:
    """Represents a circuit breaker instance guarding an action or service call."""
    name: str
    failure_threshold: int = 5
    recovery_timeout_seconds: float = 30.0
    half_open_success_threshold: int = 2
    state: str = "CLOSED"
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    total_failures: int = 0
    total_successes: int = 0
    total_trips: int = 0
    last_failure_time: Optional[float] = None
    last_state_change: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ResilienceManager:
    """Manages creation, execution wrapping, state transitions, and fallback handlers for circuit breakers."""

    def __init__(self):
        self._circuits: Dict[str, CircuitBreaker] = {}
        self._action_handlers: Dict[str, Callable[[Dict[str, Any]], Any]] = {}
        self._register_default_handlers()

    def _register_default_handlers(self):
        self.register_action("http_call", lambda p: {"status": "ok", "url": p.get("url")})
        self.register_action("db_query", lambda p: {"status": "ok", "query": p.get("query")})
        self.register_action("echo", lambda p: {"status": "ok", "echo": p.get("message")})

    def register_action(self, action_name: str, handler: Callable[[Dict[str, Any]], Any]) -> None:
        """Register an execution handler callable for a specific action type."""
        self._action_handlers[action_name] = handler

    def create_circuit(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout_seconds: float = 30.0,
        half_open_success_threshold: int = 2,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> CircuitBreaker:
        """Register a new circuit breaker."""
        if not name or not name.strip():
            raise ValueError("Circuit breaker name cannot be empty.")

        clean_name = name.strip().lower()
        if clean_name in self._circuits:
            raise ValueError(f"Circuit breaker '{clean_name}' already exists.")

        if failure_threshold <= 0:
            raise ValueError("Failure threshold must be greater than 0.")
        if recovery_timeout_seconds <= 0:
            raise ValueError("Recovery timeout must be greater than 0.")

        circuit = CircuitBreaker(
            name=clean_name,
            failure_threshold=failure_threshold,
            recovery_timeout_seconds=recovery_timeout_seconds,
            half_open_success_threshold=half_open_success_threshold,
            metadata=metadata or {},
        )
        self._circuits[clean_name] = circuit

        events.publish("circuit_created", {"name": clean_name, "failure_threshold": failure_threshold})
        return circuit

    def get_circuit(self, name: str) -> Optional[CircuitBreaker]:
        """Retrieve a circuit breaker by name and update state if recovery timeout elapsed."""
        clean_name = name.strip().lower()
        circuit = self._circuits.get(clean_name)
        if circuit:
            self._check_and_update_state(circuit)
        return circuit

    def list_circuits(self) -> List[Dict[str, Any]]:
        """List all circuit breakers with updated state."""
        for c in self._circuits.values():
            self._check_and_update_state(c)
        return [c.to_dict() for c in self._circuits.values()]

    def _check_and_update_state(self, circuit: CircuitBreaker) -> None:
        """Check if an OPEN circuit should transition to HALF_OPEN after timeout."""
        if circuit.state == "OPEN":
            elapsed = time.time() - circuit.last_state_change
            if elapsed >= circuit.recovery_timeout_seconds:
                self._transition_state(circuit, "HALF_OPEN", reason="Recovery timeout elapsed")

    def _transition_state(self, circuit: CircuitBreaker, new_state: str, reason: str = "") -> None:
        """Execute state transition and publish events."""
        old_state = circuit.state
        circuit.state = new_state
        circuit.last_state_change = time.time()

        if new_state == "HALF_OPEN":
            circuit.consecutive_successes = 0
        elif new_state == "CLOSED":
            circuit.consecutive_failures = 0
            circuit.consecutive_successes = 0
        elif new_state == "OPEN":
            circuit.total_trips += 1

        events.publish(
            "circuit_state_changed",
            {"name": circuit.name, "old_state": old_state, "new_state": new_state, "reason": reason},
        )

    def trip_circuit(self, name: str, reason: str = "Manual intervention") -> bool:
        """Manually trip a circuit to OPEN state."""
        circuit = self.get_circuit(name)
        if not circuit:
            return False
        self._transition_state(circuit, "OPEN", reason=reason)
        return True

    def reset_circuit(self, name: str) -> bool:
        """Manually reset a circuit to CLOSED state."""
        circuit = self.get_circuit(name)
        if not circuit:
            return False
        self._transition_state(circuit, "CLOSED", reason="Manual reset")
        return True

    def execute(
        self,
        name: str,
        action_name: str,
        payload: Optional[Dict[str, Any]] = None,
        fallback_value: Any = None,
    ) -> Dict[str, Any]:
        """
        Execute an action wrapped within circuit breaker protection.
        If the circuit is OPEN, returns the fallback response immediately.
        """
        circuit = self.get_circuit(name)
        if not circuit:
            raise ValueError(f"Circuit breaker '{name}' not found.")

        # If OPEN, fail fast
        if circuit.state == "OPEN":
            events.publish("circuit_execution_rejected", {"name": circuit.name, "reason": "Circuit is OPEN"})
            return {
                "status": "CIRCUIT_OPEN",
                "circuit_state": "OPEN",
                "result": fallback_value,
                "fallback_applied": True,
            }

        handler = self._action_handlers.get(action_name)
        if not handler:
            raise ValueError(f"Action '{action_name}' handler not found.")

        try:
            res = handler(payload or {})
            self._record_success(circuit)
            return {
                "status": "SUCCESS",
                "circuit_state": circuit.state,
                "result": res,
                "fallback_applied": False,
            }
        except Exception as e:
            self._record_failure(circuit, str(e))
            return {
                "status": "FAILED",
                "circuit_state": circuit.state,
                "error": str(e),
                "result": fallback_value,
                "fallback_applied": True,
            }

    def _record_success(self, circuit: CircuitBreaker) -> None:
        circuit.total_successes += 1
        circuit.consecutive_failures = 0

        if circuit.state == "HALF_OPEN":
            circuit.consecutive_successes += 1
            if circuit.consecutive_successes >= circuit.half_open_success_threshold:
                self._transition_state(circuit, "CLOSED", reason="Success threshold reached in HALF_OPEN")

    def _record_failure(self, circuit: CircuitBreaker, error_msg: str) -> None:
        circuit.total_failures += 1
        circuit.consecutive_failures += 1
        circuit.last_failure_time = time.time()

        if circuit.state == "HALF_OPEN":
            self._transition_state(circuit, "OPEN", reason=f"Failure in HALF_OPEN: {error_msg}")
        elif circuit.state == "CLOSED":
            if circuit.consecutive_failures >= circuit.failure_threshold:
                self._transition_state(circuit, "OPEN", reason=f"Failure threshold reached: {error_msg}")

    def get_stats(self) -> Dict[str, Any]:
        """Aggregate stats across all circuit breakers."""
        total = len(self._circuits)
        by_state = {"CLOSED": 0, "OPEN": 0, "HALF_OPEN": 0}
        total_trips = 0

        for c in self._circuits.values():
            self._check_and_update_state(c)
            by_state[c.state] = by_state.get(c.state, 0) + 1
            total_trips += c.total_trips

        return {
            "total_circuits": total,
            "by_state": by_state,
            "total_trips": total_trips,
        }

    def clear(self) -> None:
        """Clear all registered circuits."""
        self._circuits.clear()


# Global resilience manager instance
resilience = ResilienceManager()
