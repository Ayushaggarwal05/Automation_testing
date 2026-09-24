# Automation Testing Repository

Welcome to the **Automation Testing** sample repository (v2.4.0). This repository is structured to test GitHub workflows, CI/CD pipelines, and repository automations.

## Project Structure

```
.
├── README.md
├── docs/
│   └── architecture.md
└── src/
    ├── api.py
    ├── auth.py
    ├── webhooks.py
    ├── workflows.py
    ├── audit.py
    ├── feature_flags.py
    ├── resilience.py
    └── vault.py
```

## Getting Started

### Prerequisites

- Python 3.9+

### Setup

```bash
# Clone the repository
git clone https://github.com/your-username/automation-testing.git

# Navigate into project directory
cd automation-testing

# Run sample API module
python src/api.py
```

## Features

- **Authentication Module**: Token generation, role-based access control, and validation mock utilities.
- **REST API Service**: Endpoints for health checks (reporting service version 2.4.0), resource lookup, creation, status update, deletion, and webhook management.
- **Webhook Management**: Register subscriptions, list active webhooks, and process event payloads with HMAC-SHA256 signatures.
- **Audit Logging Module**: Tamper-evident, cryptographically chained audit logging with SHA-256 hash validation, compliance categorization, and integrity verification.
- **Feature Flag Management**: Feature flags with percentage rollouts, user/role targeting, evaluation caching, and event publishing.
- **Resilience Module**: Circuit breaker state machines, automatic failure isolation, fallback handlers, and resilience management.
- **Vault Module**: Encrypted secret storage, versioning, rotation policies, TTL expiration, access control, and event publishing.
- **Documentation**: Architectural overview and system diagrams.

## API Endpoints Summary

| Method | Endpoint | Description | Auth Required |
|---|---|---|---|
| `GET` | `/health` | Service health status check (v2.4.0) | No |
| `GET` | `/items` | List all stored items | Yes |
| `GET` | `/items/<id>` | Fetch single item by ID | Yes |
| `POST` | `/items` | Create a new item | Yes |
| `PATCH` | `/items/<id>/status` | Update status of an item | Yes |
| `DELETE` | `/items/<id>` | Delete an item by ID | Yes |
| `POST` | `/webhooks` | Register a new webhook subscription | Yes |
| `GET` | `/webhooks` | List active webhook subscriptions | Yes |
| `GET` | `/plugins` | List active plugins | Yes |

### Webhook API & Payload Verification

#### Endpoint Details

##### `register_webhook` (`POST /webhooks`)
- **Authentication**: Requires a valid Bearer/Auth token.
- **Parameters**:
  - `event_name` (*string*, required): Name of the event to subscribe to.
  - `target_url` (*string*, required): Destination URL for webhook notifications.
- **Response**: `201 Created` with subscription details (UUID, target URL, event name, creation timestamp) or `401 Unauthorized`.

##### `list_webhooks` (`GET /webhooks`)
- **Authentication**: Requires a valid Bearer/Auth token.
- **Parameters**:
  - `event_filter` (*string*, optional): Filter active webhooks by event name.
- **Response**: `200 OK` with a list of active subscriptions and total count, or `401 Unauthorized`.

#### Webhook Payload Verification (HMAC-SHA256)

When events are dispatched to registered webhooks, payloads are signed to guarantee authenticity and integrity:

1. The JSON payload is formatted with key sorting (`sort_keys=True`).
2. An HMAC-SHA256 signature is calculated over the canonical payload using the configured webhook secret.
3. Receiving services can recompute the HMAC-SHA256 signature using their shared secret and compare it against the signature header to verify that the message originated from the service and was not altered in transit.

### Plugin API

#### Endpoint Details

##### `list_plugins` (`GET /plugins`)
- **Authentication**: Requires a valid authorization token verified via `AuthService`.
- **Parameters**:
  - `token` (*string*, required): Authorization token.
- **Response**:
  - `200 OK`: `{"plugins": [{"name": str, "version": str, "enabled": bool}], "status_code": 200}`
  - `401 Unauthorized`: `{"error": "Unauthorized", "status_code": 401}`

## License

MIT License.
