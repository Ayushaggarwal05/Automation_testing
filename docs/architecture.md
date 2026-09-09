# System Architecture

This document provides a high-level overview of the automation testing demo architecture.

## Overview

The system is designed as a modular service architecture consisting of an API layer, authentication middleware, and background automation tasks.

```mermaid
graph TD
    Client[Client / Automated Tests] -->|HTTP Requests| API[APIService (src/api.py)]
    API -->|Validate Token| Auth[AuthService (src/auth.py)]
    API -->|Read / Write| Storage[(In-Memory Data Store)]
```

## Components

### 1. API Service (`src/api.py`)
- Provides entry points for health checks, data retrieval, and data mutations.
- Interacts with `AuthService` to ensure protected routes have valid credentials.

### 2. Authentication Service (`src/auth.py`)
- Handles token generation, validation, and session lifecycle.
- In-memory mock token store with time-based expiration.

### 3. Documentation (`docs/`)
- Contains architectural guidelines, diagrams, and developer notes.

## Automation & CI/CD Integration

This structure is optimized for:
- Automated linting (e.g. `flake8`, `black`, `ruff`)
- Unit test execution (`pytest`)
- GitHub Action workflow triggers on push/pull requests
