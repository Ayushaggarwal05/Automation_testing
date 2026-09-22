"""
Unit tests for ResilienceManager module.
"""

import unittest
import time
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from resilience import ResilienceManager, CircuitBreaker


class TestResilienceManager(unittest.TestCase):
    def setUp(self):
        self.manager = ResilienceManager()

    def test_create_and_get_circuit(self):
        circuit = self.manager.create_circuit(
            name="payment_gateway",
            failure_threshold=3,
            recovery_timeout_seconds=5.0,
            half_open_success_threshold=2,
        )
        self.assertIsInstance(circuit, CircuitBreaker)
        self.assertEqual(circuit.name, "payment_gateway")
        self.assertEqual(circuit.state, "CLOSED")

        retrieved = self.manager.get_circuit("payment_gateway")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.failure_threshold, 3)

    def test_duplicate_circuit_fails(self):
        self.manager.create_circuit(name="db_pool")
        with self.assertRaises(ValueError):
            self.manager.create_circuit(name="db_pool")

    def test_successful_execution(self):
        self.manager.create_circuit(name="echo_service")
        result = self.manager.execute(
            name="echo_service",
            action_name="echo",
            payload={"message": "hello resilience"},
        )
        self.assertEqual(result["status"], "SUCCESS")
        self.assertEqual(result["result"], {"status": "ok", "echo": "hello resilience"})
        self.assertFalse(result["fallback_applied"])

    def test_failure_trips_circuit_to_open(self):
        def failing_action(payload):
            raise ConnectionError("Service unreachable")

        self.manager.register_action("failing_call", failing_action)
        self.manager.create_circuit(name="fragile_service", failure_threshold=2)

        # 1st failure
        res1 = self.manager.execute(
            name="fragile_service",
            action_name="failing_call",
            fallback_value={"fallback": True},
        )
        self.assertEqual(res1["status"], "FAILED")
        self.assertEqual(res1["circuit_state"], "CLOSED")
        self.assertTrue(res1["fallback_applied"])

        # 2nd failure - should trip to OPEN
        res2 = self.manager.execute(
            name="fragile_service",
            action_name="failing_call",
            fallback_value={"fallback": True},
        )
        self.assertEqual(res2["status"], "FAILED")
        self.assertEqual(res2["circuit_state"], "OPEN")

        # 3rd call - fails fast without invoking handler
        res3 = self.manager.execute(
            name="fragile_service",
            action_name="failing_call",
            fallback_value={"fallback": True},
        )
        self.assertEqual(res3["status"], "CIRCUIT_OPEN")
        self.assertTrue(res3["fallback_applied"])

    def test_manual_trip_and_reset(self):
        self.manager.create_circuit(name="manual_test")
        self.assertTrue(self.manager.trip_circuit("manual_test", reason="Scheduled maintenance"))
        circuit = self.manager.get_circuit("manual_test")
        self.assertEqual(circuit.state, "OPEN")

        self.assertTrue(self.manager.reset_circuit("manual_test"))
        circuit = self.manager.get_circuit("manual_test")
        self.assertEqual(circuit.state, "CLOSED")

    def test_half_open_recovery_transition(self):
        def flaky_action(payload):
            if payload.get("fail"):
                raise RuntimeError("Failed")
            return {"status": "ok"}

        self.manager.register_action("flaky", flaky_action)
        # Low recovery timeout for testing
        circuit = self.manager.create_circuit(
            name="flaky_service",
            failure_threshold=1,
            recovery_timeout_seconds=0.05,
            half_open_success_threshold=1,
        )

        # Trip to OPEN
        self.manager.execute(name="flaky_service", action_name="flaky", payload={"fail": True})
        self.assertEqual(circuit.state, "OPEN")

        # Wait for timeout to elapse
        time.sleep(0.06)

        # Next check/execution transitions to HALF_OPEN and succeeds -> transitions to CLOSED
        res = self.manager.execute(name="flaky_service", action_name="flaky", payload={"fail": False})
        self.assertEqual(res["status"], "SUCCESS")
        self.assertEqual(circuit.state, "CLOSED")

    def test_list_and_stats(self):
        self.manager.create_circuit(name="c1")
        self.manager.create_circuit(name="c2")
        self.manager.trip_circuit("c2")

        stats = self.manager.get_stats()
        self.assertEqual(stats["total_circuits"], 2)
        self.assertEqual(stats["by_state"]["CLOSED"], 1)
        self.assertEqual(stats["by_state"]["OPEN"], 1)
        self.assertEqual(stats["total_trips"], 1)

        self.manager.clear()
        self.assertEqual(len(self.manager.list_circuits()), 0)


if __name__ == "__main__":
    unittest.main()
