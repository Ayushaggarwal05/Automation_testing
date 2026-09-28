"""
Unit tests for ContractValidationEngine module.
"""

import unittest
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.contracts import ContractValidationEngine, SchemaField, ContractSchema, ValidationResult
from src.events import events


class TestContractValidationEngine(unittest.TestCase):
    def setUp(self):
        self.engine = ContractValidationEngine(strict_mode=True, max_schemas=100)

    def test_register_and_get_schema(self):
        fields = {
            "username": {"field_type": "string", "min_length": 3, "max_length": 20},
            "age": {"field_type": "integer", "min_value": 18, "max_value": 120},
            "is_active": {"field_type": "boolean", "required": False},
        }
        schema = self.engine.register_schema(
            name="user_profile",
            fields=fields,
            version="1.0",
            description="User registration payload",
        )

        self.assertIsNotNone(schema.id)
        self.assertEqual(schema.name, "user_profile")
        self.assertEqual(schema.version, "1.0")
        self.assertEqual(len(schema.fields), 3)

        retrieved = self.engine.get_schema("user_profile")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.id, schema.id)

    def test_validate_valid_payload(self):
        self.engine.register_schema(
            name="create_order",
            fields=[
                {"name": "order_id", "field_type": "string", "regex_pattern": r"^ORD-\d{4}$"},
                {"name": "amount", "field_type": "number", "min_value": 0.01},
                {"name": "status", "field_type": "string", "allowed_values": ["PENDING", "COMPLETED"]},
                {"name": "items", "field_type": "array", "min_length": 1},
            ],
        )

        payload = {
            "order_id": "ORD-1234",
            "amount": 99.95,
            "status": "PENDING",
            "items": ["sku_1", "sku_2"],
        }

        result = self.engine.validate("create_order", payload)
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertEqual(result.schema_name, "create_order")

    def test_validate_type_and_constraint_violations(self):
        self.engine.register_schema(
            name="device_metric",
            fields={
                "device_id": {"field_type": "string", "min_length": 5},
                "temperature": {"field_type": "number", "min_value": -50, "max_value": 100},
                "tags": {"field_type": "array", "max_length": 3},
                "metadata": {"field_type": "object"},
            },
        )

        invalid_payload = {
            "device_id": "d1",  # too short
            "temperature": 150.0,  # exceeds max
            "tags": ["a", "b", "c", "d"],  # exceeds max_length
            "metadata": "not_an_object",  # invalid type
        }

        result = self.engine.validate("device_metric", invalid_payload)
        self.assertFalse(result.is_valid)
        self.assertEqual(len(result.errors), 4)

    def test_strict_mode_extraneous_fields(self):
        self.engine.register_schema(
            name="strict_item",
            fields={"sku": "string", "qty": "integer"},
            strict=True,
        )

        payload = {
            "sku": "ITEM-101",
            "qty": 5,
            "extra_field": "disallowed",
        }

        result = self.engine.validate("strict_item", payload)
        self.assertFalse(result.is_valid)
        self.assertTrue(any("Extraneous property" in err for err in result.errors))

    def test_non_strict_mode_allows_extra_fields(self):
        self.engine.register_schema(
            name="flexible_item",
            fields={"sku": "string"},
            strict=False,
        )

        payload = {
            "sku": "ITEM-101",
            "extra_meta": {"foo": "bar"},
        }

        result = self.engine.validate("flexible_item", payload)
        self.assertTrue(result.is_valid)

    def test_delete_and_list_schemas(self):
        s1 = self.engine.register_schema("schema_a", {"id": "string"})
        s2 = self.engine.register_schema("schema_b", {"name": "string"})

        schemas = self.engine.list_schemas()
        self.assertEqual(len(schemas), 2)

        deleted = self.engine.delete_schema(s1.id)
        self.assertTrue(deleted)
        self.assertIsNone(self.engine.get_schema("schema_a"))
        self.assertEqual(len(self.engine.list_schemas()), 1)

    def test_telemetry_stats(self):
        self.engine.register_schema("stat_schema", {"val": "integer"})

        self.engine.validate("stat_schema", {"val": 10})
        self.engine.validate("stat_schema", {"val": "invalid"})

        stats = self.engine.get_stats()
        self.assertEqual(stats["total_schemas"], 1)
        self.assertEqual(stats["total_validations"], 2)
        self.assertEqual(stats["total_violations"], 1)
        self.assertEqual(stats["pass_rate_percent"], 50.0)


if __name__ == "__main__":
    unittest.main()
