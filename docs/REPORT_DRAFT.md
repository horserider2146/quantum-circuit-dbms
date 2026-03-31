# Quantum Circuit DBMS Report Draft

Author: Team submission draft
Course: DBMS

This draft is aligned to the 10-12 page report expectations and can be converted to PDF after adding screenshots and team-specific details.

## 1. Problem Statement

We selected a quantum-circuit experiment dataset because it combines measurable hardware, algorithm, and execution metrics in a strongly relational form. The project goal is to transform raw experiment sheets into a complete DBMS pipeline that supports:

- reliable storage in connected relational tables
- CRUD operations through an authenticated API
- interactive dashboard exploration for trend and performance analysis

The data is analytically meaningful because users can compare fidelity trends across algorithms, backends, and time periods, and can link gate complexity/noise behavior with execution outcomes.

## 2. Database Design and Justification

### 2.1 Database choice

We used SQLite for local reproducibility and low setup overhead in a course setting. The workload is primarily analytical and read-heavy, with moderate CRUD for API demonstrations.

### 2.2 Relational model

The schema uses five connected tables sharing `circuit_id`:

- circuits
- qubits
- gates
- results
- noise_models

The central table stores experiment identity and headline KPIs; supporting tables isolate domain-specific fields to reduce duplication.

### 2.3 Indexing strategy

Indexes were added on:

- circuits(circuit_id)
- circuits(algorithm)
- circuits(backend)
- circuits(experiment_date)
- circuits(circuit_fidelity)
- circuit_id in each related table

This improves filtering and join responsiveness for dashboard/API queries.

### 2.4 ER diagram

Include diagram from docs/ER_DIAGRAM.md.

## 3. API Documentation and CRUD Mapping

Backend framework: FastAPI with Pydantic models.

Authentication:

- header name: X-API-Key
- all API routes require valid key

CRUD mapping:

- Create: POST /circuits
- Read: GET /circuits and GET /circuits/{circuit_id}
- Update: PATCH /circuits/{circuit_id}
- Delete (recoverable): DELETE /circuits/{circuit_id} (soft delete)
- Restore: POST /circuits/{circuit_id}/restore
- Permanent delete: DELETE /circuits/{circuit_id}/hard

Query endpoints used by frontend:

- GET /stats
- GET /search
- GET /circuits
- GET /meta/algorithms
- GET /meta/backends
- GET /meta/categories

Additional implemented endpoints include:

- DBMS features: /bulk/circuits, /filters, /audit/logs, /quality/report, /benchmark/compare
- Quantum analytics: /quantum/noise-aware-score, /quantum/mitigation/effectiveness, /quantum/hardware/recommend
- Builder endpoints: /builder/preview, /builder/save, /builder/circuits

Swagger docs are available at /docs for live testing and endpoint inspection.

## 4. Dashboard Description and Refresh Strategy

The API-driven dashboard is implemented in frontend/dashboard_api.py.

### 4.1 Visualizations

- KPI cards: total circuits, average fidelity, average success rate
- Top algorithms chart
- Top backends chart
- Fidelity distribution chart
- Top performers table

These views help users identify distribution patterns, backend usage concentration, and best-performing experiments.

### 4.2 Interactive elements

- Full-text search calls GET /search
- Multi-control filters call GET /circuits with dynamic parameters
- CRUD tabs call POST/PATCH/DELETE endpoints
- Circuit comparison tab allows side-by-side analysis by circuit ID
- Qubit builder supports preview/save/list/view/delete for custom circuits

### 4.3 Refresh logic

Two modes are supported:

- manual refresh for slower-changing data
- automatic polling (10, 15, 30 seconds) for near-real-time updates

This balances freshness and resource usage for different usage contexts.

## 5. SQL Commands Used

Representative commands are stored in sql/sample_queries.sql and include:

- algorithm distribution aggregation
- backend average fidelity analysis
- multi-table join between circuits, gates, and noise_models
- monthly time trend aggregation
- insert/update/delete examples

## 6. Challenges and Learnings

Main challenges:

- maintaining consistent schema naming across ETL, API, and UI
- keeping API and frontend integration clean while adding authentication
- ensuring dashboard query flexibility without direct DB coupling

Key learnings:

- strongly defined models and endpoint contracts reduce integration errors
- normalization and indexing decisions directly affect dashboard responsiveness
- explicit requirement-to-evidence mapping simplifies project review and demo preparation

## 7. Evidence Appendix (to add screenshots)

- Swagger with authenticated calls
- CRUD create/update/delete response screenshots
- Dashboard chart screenshots
- Search/filter interaction screenshots
- Validator output proving table row counts and endpoint coverage
