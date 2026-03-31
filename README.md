# Quantum Circuit DBMS (Course-Ready)

This repository contains a full DBMS project built on quantum circuit experiment data with:

- Relational SQLite database across multiple connected tables
- FastAPI backend with authenticated CRUD, search, metadata, and analytics endpoints
- Streamlit dashboard that consumes FastAPI endpoints
- Database setup script and reusable SQL query samples

## Feature highlights

### DBMS-focused features

- Audit logs for create/update/delete events (`/audit/logs`)
- Bulk circuit upload with conflict handling (`/bulk/circuits`)
- Saved filter presets and reusable filtered result views (`/filters`, `/filters/{filter_id}/circuits`)
- Date-range aware filtering in both ad-hoc and saved filters (`experiment_date_start`, `experiment_date_end`)
- Soft delete with restore support (`DELETE /circuits/{circuit_id}`, `POST /circuits/{circuit_id}/restore`)
- Hard delete fallback when permanent removal is needed (`DELETE /circuits/{circuit_id}/hard`)
- Data quality report for orphan rows, out-of-range metrics, and null-heavy columns (`/quality/report`)
- Benchmark comparison endpoint for algorithm-level analysis (`/benchmark/compare`)

### Quantum-focused features

- Noise-aware circuit scoring endpoint for practical ranking (`/quantum/noise-aware-score`)
- Mitigation effectiveness analytics by backend and algorithm (`/quantum/mitigation/effectiveness`)
- Hardware recommendation endpoint based on similar workload profiles (`/quantum/hardware/recommend`)
- Quantum What-If Lab for counterfactual scenario prediction and recommendations (`/quantum/what-if`, `/quantum/what-if/recommendations`)

## 1) Why this database choice

The workload is mostly analytical (read-heavy aggregations, trend analysis, and comparisons), with moderate CRUD for demonstrations.

- SQLite is simple to distribute and run locally for a course project
- It supports relational modeling with joins and indexes
- It is sufficient for a few-thousand to 15,000+ row classroom workload
- Indexes are added for key query paths (algorithm, backend, circuit_id, date, fidelity)

## 2) Project structure

```text
quantum-circuit-dbms/
├── backend/
│   ├── main.py
│   └── models.py
├── frontend/
│   ├── dashboard.py
│   └── dashboard_api.py
├── scripts/
│   ├── load_excel_to_sqlite.py
│   ├── generate_synthetic_db.py
│   └── validate_project_requirements.py
├── sql/
│   └── sample_queries.sql
├── docs/
│   ├── README.md
│   ├── ER_DIAGRAM.md
│   ├── API_DOCUMENTATION.md
│   ├── REPORT_TEMPLATE.md
│   ├── LIVE_DEMO_SCRIPT.md
│   ├── PROJECT_REQUIREMENTS_TRACEABILITY.md
│   └── postman_collection.json
├── .env.example
└── requirements.txt
```

## 3) Setup

### Install dependencies

```powershell
pip install -r requirements.txt
```

### Configure environment

Create a local `.env` file (or set environment variables) using `.env.example` as a reference:

```text
API_KEY=dev-api-key
API_BASE_URL=http://localhost:8000
```

### Build database from Excel

```powershell
python scripts/load_excel_to_sqlite.py --excel C:/path/to/quantum_circuit_database.xlsx --db db/quantum_circuits.db
```

### Optional fallback: generate synthetic dataset

If the original Excel file is not available yet, generate a fully relational local DB with thousands of rows:

```powershell
python scripts/generate_synthetic_db.py --db db/quantum_circuits.db --rows 5000
```

## 4) Run the application

### Terminal 1: FastAPI backend

```powershell
$env:API_KEY="dev-api-key"
python -m uvicorn backend.main:app --reload --port 8000
```

### Terminal 2: Streamlit frontend (API-driven)

```powershell
$env:API_KEY="dev-api-key"
$env:API_BASE_URL="http://localhost:8000"
python -m streamlit run frontend/dashboard_api.py
```

Open:

- Dashboard: http://localhost:8501
- Swagger docs: http://localhost:8000/docs

In Swagger, click **Authorize** and provide your API key in `X-API-Key`.

## 5) API authentication

All endpoints are protected by an API key header:

- Header name: `X-API-Key`
- Value: value from `API_KEY` environment variable

If the header is missing or invalid, endpoints return `401`.

## 6) Core endpoints

### CRUD

- `GET /circuits`
- `GET /circuits/{circuit_id}`
- `POST /circuits`
- `PATCH /circuits/{circuit_id}`
- `DELETE /circuits/{circuit_id}` (soft delete)
- `POST /circuits/{circuit_id}/restore`
- `DELETE /circuits/{circuit_id}/hard`

### DBMS enhancements

- `POST /bulk/circuits`
- `POST /filters`
- `GET /filters`
- `GET /filters/{filter_id}/circuits`
- `GET /audit/logs`
- `GET /quality/report`
- `GET /benchmark/compare`

### Quantum analytics extensions

- `GET /quantum/noise-aware-score`
- `GET /quantum/mitigation/effectiveness`
- `POST /quantum/hardware/recommend`
- `POST /quantum/what-if`
- `POST /quantum/what-if/recommendations`

### Frontend query endpoints (used by dashboard)

- `GET /stats`
- `GET /stats/top-performers`
- `GET /search`
- `GET /meta/algorithms`
- `GET /meta/backends`
- `GET /meta/categories`

### Extra endpoints: custom circuit builder

- `POST /builder/preview`
- `POST /builder/save`
- `GET /builder/circuits`
- `GET /builder/circuits/{user_circuit_id}`
- `DELETE /builder/circuits/{user_circuit_id}`

## 7) Dashboard requirements coverage

`frontend/dashboard_api.py` includes:

- 3+ visualizations:
  - KPI cards (total circuits, avg fidelity, avg success)
  - Top algorithm bar chart
  - Top backend bar chart
  - Fidelity distribution chart
  - Top performers table
- Interactive API calls:
  - Search input -> `/search`
  - Filter controls -> `/circuits` with dynamic params including date windows
  - Save/load reusable filter presets via `/filters` endpoints
- CRUD demo via API:
  - Create, Update, Delete tabs calling POST/PATCH/DELETE endpoints
- Circuit Comparison:
  - Side-by-side metrics and table comparison for two circuit IDs
  - Gate and noise profile comparison with auto verdict
- Qubit Builder:
  - Build circuits by adding gate steps (single, controlled, and parameterized gates)
  - Preview circuit layout before saving
  - Save, list, view, and delete custom builder circuits through API endpoints
- Quantum What-If Lab:
  - Predict expected fidelity and success rate for user-defined scenario changes
  - Show top recommended backend/mitigation/optimization actions with estimated deltas
- Data Quality Dashboard:
  - Visual summary for orphan rows and out-of-range metrics
  - Null-heavy column detection and per-table null profile view
- Refresh logic:
  - Manual refresh button for slower-changing data
  - Optional auto polling (10/15/30 sec) using `streamlit-autorefresh`

## 8) SQL commands used

See `sql/sample_queries.sql` for:

- Aggregation and trend queries
- Multi-table join examples
- Insert / update / delete examples

## 9) What to include in the final report

Use this repository evidence for the course PDF:

- Problem statement and dataset story
- ER diagram and relational design decisions
- API endpoint documentation and CRUD mapping
- Dashboard visualization intent and refresh strategy
- SQL commands actually used
- Challenges and learnings

The repository already contains the code artifacts; your report should explain the decisions and outcomes.

## 10) Submission support assets

- ER diagram: `docs/ER_DIAGRAM.md`
- Endpoint catalog and sample payloads: `docs/API_DOCUMENTATION.md`
- 10-12 page report structure: `docs/REPORT_TEMPLATE.md`
- prefilled report draft: `docs/REPORT_DRAFT.md`
- 10-minute demo flow: `docs/LIVE_DEMO_SCRIPT.md`
- Guideline-to-evidence checklist: `docs/PROJECT_REQUIREMENTS_TRACEABILITY.md`
- Postman collection for CRUD and analytics demo: `docs/postman_collection.json`

## 11) Readiness validation

Run a single command to verify key requirements coverage and minimum DB row counts:

```powershell
python scripts/validate_project_requirements.py --db db/quantum_circuits.db --min-rows 3000
```

This validates:

- required repository files for submission
- required OpenAPI endpoints
- API key security presence
- required DB tables and minimum row counts
