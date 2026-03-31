# Project Requirements Traceability

This checklist maps each DBMS course requirement to repository evidence.

## Build Requirements

| Requirement from Guidelines | Status | Evidence |
|---|---|---|
| Real-world structured dataset suitable for analysis | Covered | Dataset narrative in `README.md` and `docs/README.md` |
| Well-connected relational database with multiple tables | Covered | `docs/ER_DIAGRAM.md`, `scripts/load_excel_to_sqlite.py` |
| Database design practices: sensible types, normalization, indexing | Covered | `docs/ER_DIAGRAM.md`, index creation in `scripts/load_excel_to_sqlite.py` |
| Pre-populated data with at least a few thousand rows per table | Covered after loading dataset | Build from Excel via `scripts/load_excel_to_sqlite.py` or fallback synthetic generator `scripts/generate_synthetic_db.py`, then verify with `scripts/validate_project_requirements.py --db db/quantum_circuits.db` |
| FastAPI backend with full CRUD | Covered | `backend/main.py` (`GET/POST/PATCH/DELETE /circuits`) |
| At least 3 query endpoints used by frontend | Covered | `frontend/dashboard_api.py` calls `/stats`, `/search`, `/circuits`, `/meta/*` |
| Basic request/response validation with Pydantic | Covered | `backend/models.py`, response models on `/search` and `/stats` |
| API authentication required to use endpoints | Covered | `backend/main.py` (`X-API-Key` via `APIKeyHeader`) |
| API docs available in `/docs` | Covered | FastAPI auto docs from `backend/main.py` |
| Web dashboard connected to FastAPI API | Covered | `frontend/dashboard_api.py` |
| At least 3 visualizations | Covered | KPI cards + bar charts + tables in `frontend/dashboard_api.py` |
| Dashboard refresh logic with rationale | Covered | Manual and auto refresh controls in `frontend/dashboard_api.py` |
| At least one interactive element dynamically calling API | Covered | Search and filters in `frontend/dashboard_api.py` |
| BI tools not used | Covered | Custom Streamlit dashboard |

## Submission Requirements

| Submission Requirement | Status | Evidence |
|---|---|---|
| GitHub repo with source code | Covered | Repository structure |
| README with local run instructions | Covered | `README.md` |
| API endpoint list and samples | Covered | `docs/API_DOCUMENTATION.md` |
| SQL commands used in project | Covered | `sql/sample_queries.sql` |
| Report sections support material | Covered | `docs/REPORT_TEMPLATE.md` |
| Live showcase support material | Covered | `docs/LIVE_DEMO_SCRIPT.md` |
| ER diagram included | Covered | `docs/ER_DIAGRAM.md` |

## How to verify quickly

1. Build DB:
   - `python scripts/load_excel_to_sqlite.py --excel C:/path/to/quantum_circuit_database.xlsx --db db/quantum_circuits.db`
2. Run readiness check:
   - `python scripts/validate_project_requirements.py --db db/quantum_circuits.db --min-rows 3000`
3. Start backend and open docs:
   - `python -m uvicorn backend.main:app --reload --port 8000`
   - Visit `http://localhost:8000/docs`
4. Start dashboard:
   - `python -m streamlit run frontend/dashboard_api.py`
