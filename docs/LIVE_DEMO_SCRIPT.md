# 10-Minute Live Demo Script

## Demo Goal
Show complete DBMS flow: dataset -> relational design -> API CRUD -> dashboard insights.

## Pre-demo Setup (before presentation)
1. Install dependencies:
   - `pip install -r requirements.txt`
2. Build database from Excel:
   - `python scripts/load_excel_to_sqlite.py --excel C:/path/to/quantum_circuit_database.xlsx --db db/quantum_circuits.db`
3. Start backend:
   - `set API_KEY=dev-api-key`
   - `python -m uvicorn backend.main:app --reload --port 8000`
4. Start frontend:
   - `set API_KEY=dev-api-key`
   - `set API_BASE_URL=http://localhost:8000`
   - `python -m streamlit run frontend/dashboard_api.py`

## Minute-by-minute flow

### 0:00-1:30 Dataset and database design
- Explain domain and why data is suitable for DBMS analysis.
- Show ER diagram in `docs/ER_DIAGRAM.md`.
- Explain table relationships and key indexes.

### 1:30-5:00 API walkthrough in Swagger (`/docs`)
- Click Authorize and set `X-API-Key`.
- Show `GET /circuits` with filters.
- Show `POST /circuits` to create a new record.
- Show `PATCH /circuits/{id}` update.
- Show `DELETE /circuits/{id}` cleanup.
- Show `GET /stats` and `GET /search` as UI data sources.

### 5:00-8:30 Dashboard walkthrough
- Open API-driven dashboard.
- Explain 3+ visualizations and what insight each provides.
- Use search and filter controls to show interactivity.
- Show refresh settings (manual / auto interval).

### 8:30-10:00 SQL and closing
- Open `sql/sample_queries.sql` and explain 2-3 important queries.
- Summarize key challenges and lessons.
- End with brief note on future improvements.

## Backup Plan if Runtime Issues Occur
- Keep screenshots of Swagger and dashboard ready.
- Keep one successful request/response sample in slides.
- Keep one saved query result table as fallback evidence.
