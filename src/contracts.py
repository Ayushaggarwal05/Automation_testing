"""
API Contract and Schema Validation Engine.
Provides strict payload validation, structural schema definition, type verification, and contract compliance telemetry.
"""

import re
import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional, Union

try:
    from events import events
except ImportError:
    from src.events import events


SUPPORTED_TYPES = {"string", "integer", "number", "boolean", "array", "object"}


@dataclass
class SchemaField:
    """Represents an individual field specification within a contract schema."""
    name: str
    field_type: str = "string"  # string, integer, number, boolean, array, object
    required: bool = True
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    min_value: Optional[Union[int, float]] = None
    max_value: Optional[Union[int, float]] = None
    regex_pattern: Optional[str] = None
    allowed_values: Optional[List[Any]] = None
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ContractSchema:
    """Represents a versioned schema contract definition."""
    id: str
    name: str
    version: str = "1.0"
    fields: Dict[str, SchemaField] = field(default_factory=dict)
    strict: bool = True  # If strict, unexpected/extra fields cause validation failures
    description: str = ""
    created_at: float = field(default_factory=time.time)
    validation_count: int = 0
    violation_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "fields": {k: f.to_dict() if isinstance(f, SchemaField) else f for k, f in self.fields.items()},
            "strict": self.strict,
            "description": self.description,
            "created_at": self.created_at,
            "validation_count": self.validation_count,
            "violation_count": self.violation_count,
        }


@dataclass
class ValidationResult:
    """Represents the outcome of a payload contract validation."""
    is_valid: bool
    schema_id: str
    schema_name: str
    schema_version: str
    errors: List[str] = field(default_factory=list)
    validated_at: float = field(default_factory=time.time)
    duration_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ContractValidationEngine:
    """Manages schema contracts and performs deterministic payload validation."""

    def __init__(self, strict_mode: bool = True, max_schemas: int = 500):
        self._schemas: Dict[str, ContractSchema] = {}  # key: schema_id
        self._name_index: Dict[str, Dict[str, str]] = {}  # name -> {version: schema_id}
        self.strict_mode = strict_mode
        self.max_schemas = max_schemas
        self._total_validations = 0
        self._total_violations = 0

    def register_schema(
        self,
        name: str,
        fields: Union[Dict[str, Any], List[Dict[str, Any]]],
        version: str = "1.0",
        strict: Optional[bool] = None,
        description: str = "",
    ) -> ContractSchema:
        """Register a new contract schema definition."""
        if not name or not name.strip():
            raise ValueError("Schema name cannot be empty.")

        name = name.strip()
        version = version.strip() if version else "1.0"

        if len(self._schemas) >= self.max_schemas:
            raise ValueError(f"Max schema limit of {self.max_schemas} reached.")

        parsed_fields: Dict[str, SchemaField] = {}
        if isinstance(fields, list):
            for f in fields:
                field_name = f.get("name")
                if not field_name:
                    raise ValueError("Field definition must contain a 'name'.")
                f_type = f.get("field_type", "string")
                if f_type not in SUPPORTED_TYPES:
                    raise ValueError(f"Unsupported field_type '{f_type}'. Supported: {sorted(SUPPORTED_TYPES)}")
                parsed_fields[field_name] = SchemaField(
                    name=field_name,
                    field_type=f_type,
                    required=f.get("required", True),
                    min_length=f.get("min_length"),
                    max_length=f.get("max_length"),
                    min_value=f.get("min_value"),
                    max_value=f.get("max_value"),
                    regex_pattern=f.get("regex_pattern"),
                    allowed_values=f.get("allowed_values"),
                    description=f.get("description", ""),
                )
        elif isinstance(fields, dict):
            for field_name, f in fields.items():
                if isinstance(f, SchemaField):
                    parsed_fields[field_name] = f
                elif isinstance(f, dict):
                    f_type = f.get("field_type", "string")
                    if f_type not in SUPPORTED_TYPES:
                        raise ValueError(f"Unsupported field_type '{f_type}'. Supported: {sorted(SUPPORTED_TYPES)}")
                    parsed_fields[field_name] = SchemaField(
                        name=field_name,
                        field_type=f_type,
                        required=f.get("required", True),
                        min_length=f.get("min_length"),
                        max_length=f.get("max_length"),
                        min_value=f.get("min_value"),
                        max_value=f.get("max_value"),
                        regex_pattern=f.get("regex_pattern"),
                        allowed_values=f.get("allowed_values"),
                        description=f.get("description", ""),
                    )
                elif isinstance(f, str):
                    if f not in SUPPORTED_TYPES:
                        raise ValueError(f"Unsupported field_type '{f}'. Supported: {sorted(SUPPORTED_TYPES)}")
                    parsed_fields[field_name] = SchemaField(name=field_name, field_type=f, required=True)
                else:
                    raise ValueError(f"Invalid field definition for '{field_name}'.")

        schema_id = f"sch_{uuid.uuid4().hex[:10]}"
        is_strict = self.strict_mode if strict is None else strict

        schema = ContractSchema(
            id=schema_id,
            name=name,
            version=version,
            fields=parsed_fields,
            strict=is_strict,
            description=description.strip(),
            created_at=time.time(),
        )

        self._schemas[schema_id] = schema
        if name not in self._name_index:
            self._name_index[name] = {}
        self._name_index[name][version] = schema_id

        events.publish("contract_registered", {"id": schema_id, "name": name, "version": version})
        return schema

    def get_schema(self, schema_id_or_name: str, version: Optional[str] = None) -> Optional[ContractSchema]:
        """Retrieve schema by unique ID or by name and optional version (defaults to latest/only)."""
        if schema_id_or_name in self._schemas:
            return self._schemas[schema_id_or_name]

        if schema_id_or_name in self._name_index:
            versions = self._name_index[schema_id_or_name]
            if version and version in versions:
                return self._schemas[versions[version]]
            elif versions:
                # Return highest version if not specified
                latest_ver = sorted(versions.keys())[-1]
                return self._schemas[versions[latest_ver]]
        return None

    def list_schemas(self) -> List[Dict[str, Any]]:
        """List all registered contract schemas."""
        schemas = list(self._schemas.values())
        schemas.sort(key=lambda s: s.created_at)
        return [s.to_dict() for s in schemas]

    def delete_schema(self, schema_id: str) -> bool:
        """Delete a registered contract schema."""
        if schema_id in self._schemas:
            schema = self._schemas[schema_id]
            del self._schemas[schema_id]
            if schema.name in self._name_index and schema.version in self._name_index[schema.name]:
                del self._name_index[schema.name][schema.version]
                if not self._name_index[schema.name]:
                    del self._name_index[schema.name]
            events.publish("contract_deleted", {"id": schema_id, "name": schema.name})
            return True
        return False

    def validate(
        self,
        schema_id_or_name: str,
        payload: Dict[str, Any],
        version: Optional[str] = None,
    ) -> ValidationResult:
        """Validate a dictionary payload against a registered schema contract."""
        start_time = time.time()
        schema = self.get_schema(schema_id_or_name, version=version)
        if not schema:
            raise ValueError(f"Contract schema '{schema_id_or_name}' (version: {version or 'latest'}) not found.")

        if not isinstance(payload, dict):
            raise ValueError("Payload to validate must be a dictionary.")

        errors: List[str] = []

        # 1. Check required fields and validate defined fields
        for field_name, spec in schema.fields.items():
            if field_name not in payload or payload[field_name] is None:
                if spec.required:
                    errors.append(f"Missing required field: '{field_name}'")
                continue

            val = payload[field_name]

            # Type checking
            if spec.field_type == "string":
                if not isinstance(val, str):
                    errors.append(f"Field '{field_name}' must be of type string, got {type(val).__name__}")
                else:
                    if spec.min_length is not None and len(val) < spec.min_length:
                        errors.append(f"Field '{field_name}' length {len(val)} is below minimum {spec.min_length}")
                    if spec.max_length is not None and len(val) > spec.max_length:
                        errors.append(f"Field '{field_name}' length {len(val)} exceeds maximum {spec.max_length}")
                    if spec.regex_pattern:
                        if not re.match(spec.regex_pattern, val):
                            errors.append(f"Field '{field_name}' value does not match regex pattern '{spec.regex_pattern}'")
                    if spec.allowed_values is not None and val not in spec.allowed_values:
                        errors.append(f"Field '{field_name}' value '{val}' is not in allowed values: {spec.allowed_values}")

            elif spec.field_type == "integer":
                if not isinstance(val, int) or isinstance(val, bool):
                    errors.append(f"Field '{field_name}' must be of type integer, got {type(val).__name__}")
                else:
                    if spec.min_value is not None and val < spec.min_value:
                        errors.append(f"Field '{field_name}' value {val} is below minimum {spec.min_value}")
                    if spec.max_value is not None and val > spec.max_value:
                        errors.append(f"Field '{field_name}' value {val} exceeds maximum {spec.max_value}")
                    if spec.allowed_values is not None and val not in spec.allowed_values:
                        errors.append(f"Field '{field_name}' value {val} is not in allowed values: {spec.allowed_values}")

            elif spec.field_type == "number":
                if not isinstance(val, (int, float)) or isinstance(val, bool):
                    errors.append(f"Field '{field_name}' must be of type number, got {type(val).__name__}")
                else:
                    if spec.min_value is not None and val < spec.min_value:
                        errors.append(f"Field '{field_name}' value {val} is below minimum {spec.min_value}")
                    if spec.max_value is not None and val > spec.max_value:
                        errors.append(f"Field '{field_name}' value {val} exceeds maximum {spec.max_value}")

            elif spec.field_type == "boolean":
                if not isinstance(val, bool):
                    errors.append(f"Field '{field_name}' must be of type boolean, got {type(val).__name__}")

            elif spec.field_type == "array":
                if not isinstance(val, list):
                    errors.append(f"Field '{field_name}' must be of type array, got {type(val).__name__}")
                else:
                    if spec.min_length is not None and len(val) < spec.min_length:
                        errors.append(f"Field '{field_name}' array size {len(val)} is below minimum {spec.min_length}")
                    if spec.max_length is not None and len(val) > spec.max_length:
                        errors.append(f"Field '{field_name}' array size {len(val)} exceeds maximum {spec.max_length}")

            elif spec.field_type == "object":
                if not isinstance(val, dict):
                    errors.append(f"Field '{field_name}' must be of type object, got {type(val).__name__}")

        # 2. Strict mode validation: detect extraneous fields
        if schema.strict:
            for key in payload:
                if key not in schema.fields:
                    errors.append(f"Extraneous property '{key}' not permitted in strict contract schema")

        duration_ms = round((time.time() - start_time) * 1000, 3)
        is_valid = len(errors) == 0

        # Update telemetry
        self._total_validations += 1
        schema.validation_count += 1
        if not is_valid:
            self._total_violations += 1
            schema.violation_count += 1

        result = ValidationResult(
            is_valid=is_valid,
            schema_id=schema.id,
            schema_name=schema.name,
            schema_version=schema.version,
            errors=errors,
            validated_at=time.time(),
            duration_ms=duration_ms,
        )

        if is_valid:
            events.publish("contract_validated", {"schema_id": schema.id, "schema_name": schema.name})
        else:
            events.publish("validation_failed", {"schema_id": schema.id, "schema_name": schema.name, "errors": errors})

        return result

    def get_stats(self) -> Dict[str, Any]:
        """Retrieve aggregated validation statistics and telemetry."""
        pass_rate = 100.0
        if self._total_validations > 0:
            pass_rate = round(((self._total_validations - self._total_violations) / self._total_validations) * 100, 2)

        return {
            "total_schemas": len(self._schemas),
            "total_validations": self._total_validations,
            "total_violations": self._total_violations,
            "pass_rate_percent": pass_rate,
            "strict_mode_default": self.strict_mode,
            "max_schemas": self.max_schemas,
        }

    def clear(self):
        """Reset internal schema state."""
        self._schemas.clear()
        self._name_index.clear()
        self._total_validations = 0
        self._total_violations = 0


# Singleton instance for system-wide access
contracts = ContractValidationEngine()
