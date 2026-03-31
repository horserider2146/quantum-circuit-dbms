# API Documentation

This document lists the FastAPI endpoints used in the project.

## Authentication

- Required header: `X-API-Key`
- Value source: `API_KEY` environment variable
- Behavior: missing or invalid key returns `401`

## Base URL

- Local default: `http://localhost:8000`

## Health

### GET /

- Purpose: basic service status check.

### GET /health

- Purpose: DB-aware health check with total row count.

## Core Circuits CRUD

### GET /circuits

- Purpose: paginated listing with filters.
- Query params: `page`, `limit`, `algorithm`, `backend`, `category`, `min_fidelity`, `max_fidelity`, `is_simulator`, `experiment_date_start`, `experiment_date_end`, `include_deleted`

### GET /circuits/{circuit_id}

- Purpose: full details for one active circuit across related tables.

### POST /circuits

- Purpose: create a new circuit record.

### PATCH /circuits/{circuit_id}

- Purpose: partial update for one active circuit.

### DELETE /circuits/{circuit_id}

- Purpose: soft delete a circuit (recoverable).

### POST /circuits/{circuit_id}/restore

- Purpose: restore a previously soft-deleted circuit.

### DELETE /circuits/{circuit_id}/hard

- Purpose: permanent delete from `circuits` and related tables.

## Search, Stats, and Metadata

### GET /search

- Purpose: text search across circuit id, name, algorithm, category, backend.

### GET /stats

- Purpose: aggregate KPI data for dashboard cards and charts.

### GET /stats/top-performers

- Purpose: highest-ranked circuits by fidelity.

### GET /meta/algorithms

### GET /meta/backends

### GET /meta/categories

- Purpose: provide distinct values for filter dropdowns.

## DBMS Feature Endpoints

### POST /bulk/circuits

- Purpose: bulk create/update/skip behavior for many records.
- Request fields: `records`, `conflict_strategy` (`skip|update|error`), `created_by`.

### POST /filters

- Purpose: save a named reusable filter preset.
- Supports date windows via `experiment_date_start` and `experiment_date_end`.

### GET /filters

- Purpose: list saved filter presets.

### GET /filters/{filter_id}/circuits

- Purpose: apply a saved filter and return paginated results.

### GET /audit/logs

- Purpose: retrieve audit trail events.
- Optional query params: `table_name`, `record_id`, `limit`.

### GET /quality/report

- Purpose: quality checks (orphan rows, out-of-range metrics, soft-deleted counts, null-heavy columns).

### GET /benchmark/compare

- Purpose: compare two algorithms (optionally by backend) across aggregate metrics.

## Quantum Feature Endpoints

### GET /quantum/noise-aware-score

- Purpose: rank circuits using a composite score of fidelity, success, depth, and noise.

### GET /quantum/mitigation/effectiveness

- Purpose: compare mitigation effectiveness by backend and algorithm.

### POST /quantum/hardware/recommend

- Purpose: recommend suitable backends for a target workload profile.
- Request fields: `num_qubits_used`, `circuit_depth`, optional `cnot_count`, `min_samples`.

### POST /quantum/what-if

- Purpose: predict expected fidelity/success for a counterfactual scenario.
- Request fields: baseline via `circuit_id` or explicit scenario fields like `algorithm`, `backend`, `mitigation_technique`, `shots`, `circuit_depth`, `num_qubits_used`, `total_circuit_error`.

### POST /quantum/what-if/recommendations

- Purpose: return top recommended backend/mitigation/optimization combinations with estimated gains.
- Request fields: same as `/quantum/what-if` plus `top_k`.

## Related Table Updates

### PATCH /qubits/{circuit_id}

### PATCH /noise/{circuit_id}

- Purpose: update specialized table values by circuit id.
- Behavior: returns `404` if the target row does not exist.

## Circuit Builder Endpoints

### POST /builder/preview

- Purpose: validate gate sequence and return a wire-layout preview.

### POST /builder/save

- Purpose: persist user-composed custom circuits.

### GET /builder/circuits

- Purpose: list saved custom circuits.

### GET /builder/circuits/{user_circuit_id}

- Purpose: get a saved circuit with ordered steps.

### DELETE /builder/circuits/{user_circuit_id}

- Purpose: delete a saved custom circuit.

## Swagger Documentation

- Interactive docs: `/docs`
- Alternate docs: `/redoc`
- All protected endpoints can be tested after setting `X-API-Key` in Swagger Authorize.
