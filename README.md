# Automation Testing Repository

Welcome to the **Automation Testing** sample repository. This repository is structured to test GitHub workflows, CI/CD pipelines, and repository automations.

## Project Structure

```
.
├── README.md
├── docs/
│   └── architecture.md
└── src/
    ├── api.py
    └── auth.py
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
- **REST API Service**: Endpoints for health checks, resource lookup, creation, status update, and deletion.
- **Documentation**: Architectural overview and system diagrams.

## API Endpoints Summary

| Method | Endpoint | Description | Auth Required |
|---|---|---|---|
| `GET` | `/health` | Service health status check | No |
| `GET` | `/items` | List all stored items | Yes |
| `GET` | `/items/<id>` | Fetch single item by ID | Yes |
| `POST` | `/items` | Create a new item | Yes |
| `PATCH` | `/items/<id>/status` | Update status of an item | Yes |
| `DELETE` | `/items/<id>` | Delete an item by ID | Yes |

## License

MIT License.
