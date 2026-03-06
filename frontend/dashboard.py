"""
Quantum Circuit Dashboard - Streamlit Frontend
==============================================
Interactive dashboard with search, filters, stats & CRUD UI.
"""

import streamlit as st
import sqlite3
import pandas as pd
import numpy as np
import json
import os
from datetime import datetime

# ── Page Config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="⚛️ Quantum Circuit DB",
    page_icon="⚛️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── DB Path ────────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "db", "quantum_circuits.db")


# ── DB Helper ──────────────────────────────────────────────────────────────────
@st.cache_resource
def get_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def query(sql, params=None):
    conn = get_connection()
    params = params or []
    return pd.read_sql_query(sql, conn, params=params)


def execute(sql, params=None):
    conn = get_connection()
    params = params or []
    cursor = conn.cursor()
    cursor.execute(sql, params)
    conn.commit()
    return cursor.rowcount


# ── Sidebar Navigation ─────────────────────────────────────────────────────────
st.sidebar.image("https://upload.wikimedia.org/wikipedia/commons/5/51/Qiskit-Logo.svg", width=120)
st.sidebar.title("⚛️ Quantum Circuit DB")
st.sidebar.caption("15,000 IBM Quantum Experiments")
st.sidebar.divider()

page = st.sidebar.radio(
    "Navigate",
    ["🏠 Dashboard", "🔍 Search & Explore", "➕ Add Circuit",
     "✏️ Edit / Delete", "📊 Compare Circuits",
     "🧬 DNA Fingerprinting", "📖 Lessons & Guide"],
    label_visibility="collapsed"
)

# ── Helper: Cached distinct values ────────────────────────────────────────────
@st.cache_data(ttl=300)
def get_distinct(col, table="circuits"):
    df = query(f"SELECT DISTINCT {col} FROM {table} WHERE {col} IS NOT NULL ORDER BY {col}")
    return df[col].tolist()


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 1 — DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════
if page == "🏠 Dashboard":
    st.title("⚛️ Quantum Circuit Database Dashboard")
    st.caption("IBM Quantum Experiment Analytics — 15,000 circuits across 5 relational tables")

    # KPI Row
    total = query("SELECT COUNT(*) as c FROM circuits").iloc[0]["c"]
    avg_fid = query("SELECT ROUND(AVG(circuit_fidelity),4) as f FROM circuits").iloc[0]["f"]
    avg_suc = query("SELECT ROUND(AVG(success_rate),4) as s FROM circuits").iloc[0]["s"]
    sim_count = query("SELECT COUNT(*) as c FROM circuits WHERE is_simulator='True'").iloc[0]["c"]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Circuits", f"{total:,}")
    c2.metric("Avg Fidelity", f"{avg_fid:.2%}")
    c3.metric("Avg Success Rate", f"{avg_suc:.2%}")
    c4.metric("Simulated Runs", f"{sim_count:,}")

    st.divider()

    col1, col2 = st.columns(2)

    # Algorithm distribution
    with col1:
        st.subheader("🔬 Top Algorithms")
        algo_df = query(
            "SELECT algorithm, COUNT(*) as count FROM circuits GROUP BY algorithm ORDER BY count DESC LIMIT 10"
        )
        if not algo_df.empty:
            import json
            # Build inline bar chart using st.bar_chart
            algo_df = algo_df.set_index("algorithm")
            st.bar_chart(algo_df["count"])

    # Backend distribution
    with col2:
        st.subheader("🖥️ Top Backends")
        backend_df = query(
            "SELECT backend, COUNT(*) as count FROM circuits GROUP BY backend ORDER BY count DESC LIMIT 10"
        )
        if not backend_df.empty:
            backend_df = backend_df.set_index("backend")
            st.bar_chart(backend_df["count"])

    col3, col4 = st.columns(2)

    with col3:
        st.subheader("📊 Fidelity Distribution")
        fid_df = query(
            """SELECT
                CASE
                    WHEN circuit_fidelity >= 0.9 THEN '0.9–1.0'
                    WHEN circuit_fidelity >= 0.8 THEN '0.8–0.9'
                    WHEN circuit_fidelity >= 0.7 THEN '0.7–0.8'
                    WHEN circuit_fidelity >= 0.6 THEN '0.6–0.7'
                    ELSE '< 0.6'
                END as range, COUNT(*) as count
               FROM circuits GROUP BY range ORDER BY range DESC"""
        )
        fid_df = fid_df.set_index("range")
        st.bar_chart(fid_df["count"])

    with col4:
        st.subheader("📂 Categories")
        cat_df = query(
            "SELECT category, COUNT(*) as count FROM circuits GROUP BY category ORDER BY count DESC"
        )
        if not cat_df.empty:
            cat_df = cat_df.set_index("category")
            st.bar_chart(cat_df["count"])

    # Top 10 performers table
    st.subheader("🏆 Top 10 Circuits by Fidelity")
    top_df = query(
        """SELECT c.circuit_id, c.circuit_name, c.algorithm, c.backend,
                  ROUND(c.circuit_fidelity,4) as fidelity,
                  ROUND(c.success_rate,4) as success_rate,
                  g.total_gate_count, g.circuit_depth
           FROM circuits c LEFT JOIN gates g ON c.circuit_id = g.circuit_id
           ORDER BY c.circuit_fidelity DESC LIMIT 10"""
    )
    st.dataframe(top_df, use_container_width=True, hide_index=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 2 — SEARCH & EXPLORE
# ══════════════════════════════════════════════════════════════════════════════
elif page == "🔍 Search & Explore":
    st.title("🔍 Search & Explore Circuits")

    # ── Search Bar ─────────────────────────────────────────────────────────────
    st.subheader("Quick Search")
    search_col, btn_col = st.columns([4, 1])
    with search_col:
        search_term = st.text_input("Search by Circuit ID, Name, Algorithm, Backend, or Category",
                                    placeholder="e.g. QFT, ibm_seattle, CIR-00042...")
    with btn_col:
        st.write("")
        st.write("")
        do_search = st.button("Search 🔎", use_container_width=True)

    if search_term and do_search:
        t = f"%{search_term}%"
        results = query(
            """SELECT circuit_id, circuit_name, algorithm, category, backend,
                      ROUND(circuit_fidelity,4) as fidelity,
                      ROUND(success_rate,4) as success_rate, experiment_date
               FROM circuits
               WHERE LOWER(circuit_id) LIKE LOWER(?)
                  OR LOWER(circuit_name) LIKE LOWER(?)
                  OR LOWER(algorithm) LIKE LOWER(?)
                  OR LOWER(category) LIKE LOWER(?)
                  OR LOWER(backend) LIKE LOWER(?)
               LIMIT 100""",
            [t, t, t, t, t]
        )
        st.success(f"Found **{len(results)}** results for '{search_term}'")
        st.dataframe(results, use_container_width=True, hide_index=True)

    st.divider()

    # ── Advanced Filters ───────────────────────────────────────────────────────
    st.subheader("Advanced Filters")
    fc1, fc2, fc3 = st.columns(3)

    algorithms = ["All"] + get_distinct("algorithm")
    backends = ["All"] + get_distinct("backend")
    categories = ["All"] + get_distinct("category")

    with fc1:
        sel_algo = st.selectbox("Algorithm", algorithms)
    with fc2:
        sel_backend = st.selectbox("Backend", backends)
    with fc3:
        sel_cat = st.selectbox("Category", categories)

    fc4, fc5 = st.columns(2)
    with fc4:
        fidelity_range = st.slider("Fidelity Range", 0.0, 1.0, (0.0, 1.0), 0.01)
    with fc5:
        is_sim = st.selectbox("Simulator?", ["All", "True", "False"])

    limit = st.slider("Max Results", 10, 500, 50, 10)

    if st.button("Apply Filters 🔧", use_container_width=True):
        where = ["circuit_fidelity BETWEEN ? AND ?"]
        params = [fidelity_range[0], fidelity_range[1]]

        if sel_algo != "All":
            where.append("algorithm = ?")
            params.append(sel_algo)
        if sel_backend != "All":
            where.append("backend = ?")
            params.append(sel_backend)
        if sel_cat != "All":
            where.append("category = ?")
            params.append(sel_cat)
        if is_sim != "All":
            where.append("is_simulator = ?")
            params.append(is_sim)

        sql = f"""SELECT circuit_id, circuit_name, algorithm, category, backend,
                         ROUND(circuit_fidelity,4) as fidelity,
                         ROUND(success_rate,4) as success_rate, shots, experiment_date
                  FROM circuits WHERE {' AND '.join(where)} LIMIT ?"""
        params.append(limit)

        filtered = query(sql, params)
        st.success(f"**{len(filtered)}** results with current filters")
        st.dataframe(filtered, use_container_width=True, hide_index=True)

        if not filtered.empty:
            avg_f = filtered["fidelity"].mean()
            avg_s = filtered["success_rate"].mean()
            m1, m2, m3 = st.columns(3)
            m1.metric("Results Shown", len(filtered))
            m2.metric("Avg Fidelity", f"{avg_f:.2%}")
            m3.metric("Avg Success Rate", f"{avg_s:.2%}")

    st.divider()

    # ── Detailed Circuit View ──────────────────────────────────────────────────
    st.subheader("📋 Full Circuit Detail")
    detail_id = st.text_input("Enter Circuit ID for full detail", placeholder="CIR-00001")
    if detail_id:
        c = query("SELECT * FROM circuits WHERE circuit_id = ?", [detail_id])
        if c.empty:
            st.error(f"Circuit '{detail_id}' not found.")
        else:
            tabs = st.tabs(["⚡ Circuit", "🔬 Qubits", "🔩 Gates", "📈 Results", "🌊 Noise Model"])
            with tabs[0]:
                st.dataframe(c.T.rename(columns={0: "Value"}), use_container_width=True)
            with tabs[1]:
                q_df = query("SELECT * FROM qubits WHERE circuit_id = ?", [detail_id])
                st.dataframe(q_df.T.rename(columns={0: "Value"}), use_container_width=True)
            with tabs[2]:
                g_df = query("SELECT * FROM gates WHERE circuit_id = ?", [detail_id])
                st.dataframe(g_df.T.rename(columns={0: "Value"}), use_container_width=True)
            with tabs[3]:
                r_df = query("SELECT * FROM results WHERE circuit_id = ?", [detail_id])
                st.dataframe(r_df.T.rename(columns={0: "Value"}), use_container_width=True)
            with tabs[4]:
                n_df = query("SELECT * FROM noise_models WHERE circuit_id = ?", [detail_id])
                st.dataframe(n_df.T.rename(columns={0: "Value"}), use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 3 — ADD CIRCUIT
# ══════════════════════════════════════════════════════════════════════════════
elif page == "➕ Add Circuit":
    st.title("➕ Add New Circuit")
    st.info("Fill in the fields below to insert a new circuit record into the database.")

    with st.form("add_circuit_form"):
        col1, col2 = st.columns(2)
        with col1:
            circuit_id = st.text_input("Circuit ID *", placeholder="CIR-99999")
            job_id = st.text_input("Job ID", placeholder="JOB-IBM-XXXXXX")
            circuit_name = st.text_input("Circuit Name", placeholder="My QFT Circuit")
            algorithm = st.text_input("Algorithm", placeholder="QFT")
            category = st.selectbox("Category", [""] + get_distinct("category"))
            backend = st.selectbox("Backend", [""] + get_distinct("backend"))
        with col2:
            architecture = st.text_input("Architecture", placeholder="heavy-hex")
            quantum_volume = st.number_input("Quantum Volume", min_value=0, value=32)
            experiment_date = st.date_input("Experiment Date", value=datetime.today())
            shots = st.number_input("Shots", min_value=1, value=1024)
            circuit_fidelity = st.slider("Circuit Fidelity", 0.0, 1.0, 0.85, 0.001)
            success_rate = st.slider("Success Rate", 0.0, 1.0, 0.80, 0.001)
            is_simulator = st.selectbox("Is Simulator?", ["False", "True"])

        submitted = st.form_submit_button("💾 Insert Circuit", use_container_width=True)

    if submitted:
        if not circuit_id:
            st.error("Circuit ID is required!")
        else:
            existing = query("SELECT 1 FROM circuits WHERE circuit_id = ?", [circuit_id])
            if not existing.empty:
                st.error(f"Circuit '{circuit_id}' already exists!")
            else:
                try:
                    conn = get_connection()
                    conn.execute(
                        """INSERT INTO circuits
                           (circuit_id, job_id, circuit_name, algorithm, category,
                            backend, architecture, quantum_volume, experiment_date,
                            shots, circuit_fidelity, success_rate, is_simulator)
                           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                        [circuit_id, job_id, circuit_name, algorithm, category,
                         backend, architecture, quantum_volume,
                         str(experiment_date), shots, circuit_fidelity,
                         success_rate, is_simulator]
                    )
                    conn.commit()
                    st.success(f"✅ Circuit '{circuit_id}' inserted successfully!")
                    st.balloons()
                except Exception as e:
                    st.error(f"Error: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 4 — EDIT / DELETE
# ══════════════════════════════════════════════════════════════════════════════
elif page == "✏️ Edit / Delete":
    st.title("✏️ Edit / Delete Circuits")

    circuit_id = st.text_input("Enter Circuit ID to modify", placeholder="CIR-00001")

    if circuit_id:
        c_df = query("SELECT * FROM circuits WHERE circuit_id = ?", [circuit_id])
        if c_df.empty:
            st.error(f"Circuit '{circuit_id}' not found.")
        else:
            c = c_df.iloc[0]
            st.success(f"Found: **{c.get('circuit_name', 'N/A')}** | Algorithm: {c.get('algorithm')} | Backend: {c.get('backend')}")

            edit_tab, delete_tab = st.tabs(["✏️ Edit", "🗑️ Delete"])

            with edit_tab:
                st.subheader("Update Circuit Fields")
                with st.form("edit_form"):
                    col1, col2 = st.columns(2)
                    with col1:
                        new_name = st.text_input("Circuit Name", value=str(c.get("circuit_name", "") or ""))
                        new_algo = st.text_input("Algorithm", value=str(c.get("algorithm", "") or ""))
                        new_backend = st.selectbox("Backend",
                                                    get_distinct("backend"),
                                                    index=get_distinct("backend").index(c.get("backend")) if c.get("backend") in get_distinct("backend") else 0)
                        new_shots = st.number_input("Shots", min_value=1, value=int(c.get("shots") or 1024))
                    with col2:
                        new_fidelity = st.slider("Circuit Fidelity", 0.0, 1.0,
                                                  float(c.get("circuit_fidelity") or 0.8), 0.001)
                        new_success = st.slider("Success Rate", 0.0, 1.0,
                                                 float(c.get("success_rate") or 0.8), 0.001)
                        new_mitigation = st.text_input("Mitigation Technique",
                                                        value=str(c.get("mitigation_technique", "") or ""))
                        new_opt = st.selectbox("Optimization Level", [0, 1, 2, 3],
                                               index=int(c.get("optimization_level") or 0))

                    update_btn = st.form_submit_button("💾 Save Changes", use_container_width=True)

                if update_btn:
                    try:
                        conn = get_connection()
                        conn.execute(
                            """UPDATE circuits SET
                               circuit_name=?, algorithm=?, backend=?, shots=?,
                               circuit_fidelity=?, success_rate=?,
                               mitigation_technique=?, optimization_level=?
                               WHERE circuit_id=?""",
                            [new_name, new_algo, new_backend, new_shots,
                             new_fidelity, new_success, new_mitigation, new_opt, circuit_id]
                        )
                        conn.commit()
                        st.success("✅ Circuit updated successfully!")
                    except Exception as e:
                        st.error(f"Error: {e}")

            with delete_tab:
                st.warning(f"⚠️ This will permanently delete circuit **{circuit_id}** and all related qubits, gates, results, and noise model records.")
                confirm = st.text_input("Type the Circuit ID to confirm deletion", placeholder=circuit_id)
                if st.button("🗑️ Delete Permanently", type="primary"):
                    if confirm != circuit_id:
                        st.error("Circuit ID does not match. Deletion cancelled.")
                    else:
                        try:
                            conn = get_connection()
                            for table in ["qubits", "gates", "results", "noise_models", "circuits"]:
                                conn.execute(f"DELETE FROM {table} WHERE circuit_id=?", [circuit_id])
                            conn.commit()
                            st.success(f"✅ Circuit '{circuit_id}' and all related records deleted.")
                        except Exception as e:
                            st.error(f"Error: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 5 — LESSONS & GUIDE
# ══════════════════════════════════════════════════════════════════════════════
elif page == "📖 Lessons & Guide":
    st.title("📖 Step-by-Step DBMS Lessons")
    st.caption("Learn how this Quantum Circuit DBMS was built — from scratch to production.")

    lessons = {
        "Lesson 1: What is a DBMS?": {
            "icon": "🗄️",
            "content": """
A **Database Management System (DBMS)** is software that organizes, stores, retrieves, and manages data efficiently.

### Key Concepts
- **Database**: An organized collection of structured data (our 15,000 quantum circuits)
- **DBMS**: The engine that manages the database (we use **SQLite**)
- **Schema**: The blueprint defining tables, columns, and data types

### Why Not Just Use Excel?
| Feature | Excel | DBMS (SQLite) |
|---------|-------|---------------|
| Row Limit | ~1M rows | Billions |
| Concurrent Users | 1 | Many |
| Relationships | Manual | Foreign Keys |
| Search Speed | Slow | Indexed, instant |
| CRUD APIs | No | Yes |

### Our Database Structure
```
quantum_circuits.db
├── circuits      (15,000 rows, 21 columns)   ← Main table
├── qubits        (15,000 rows, 20 columns)   ← Qubit hardware data
├── gates         (15,000 rows, 23 columns)   ← Gate composition
├── results       (15,000 rows, 22 columns)   ← Execution outcomes
└── noise_models  (15,000 rows, 23 columns)   ← Error/noise profiles
```
All tables are linked via the `circuit_id` primary key.
"""},
        "Lesson 2: Relational Design & SQL": {
            "icon": "🔗",
            "content": """
### Relational Databases
Data is split across **related tables** to avoid duplication (normalization).

```sql
-- Each table shares the circuit_id key
SELECT c.circuit_id, c.algorithm, q.num_qubits_used, g.total_gate_count
FROM circuits c
JOIN qubits q ON c.circuit_id = q.circuit_id
JOIN gates  g ON c.circuit_id = g.circuit_id
WHERE c.circuit_fidelity > 0.9
LIMIT 5;
```

### CRUD Operations
| Operation | SQL | HTTP Method |
|-----------|-----|-------------|
| **C**reate | `INSERT INTO ...` | POST |
| **R**ead   | `SELECT * FROM ...` | GET |
| **U**pdate | `UPDATE ... SET ...` | PATCH |
| **D**elete | `DELETE FROM ...` | DELETE |

### Indexes for Speed
```sql
-- Without index: full table scan (15,000 rows)
-- With index: O(log n) lookup
CREATE INDEX idx_circuits_algo ON circuits(algorithm);
CREATE INDEX idx_circuits_backend ON circuits(backend);
```
We created 7 indexes on `circuit_id`, `algorithm`, and `backend`.
"""},
        "Lesson 3: FastAPI Backend": {
            "icon": "⚡",
            "content": """
### What is FastAPI?
FastAPI is a modern Python web framework for building **REST APIs** — fast, with automatic docs.

### How to Run the API
```bash
# From the project root
uvicorn backend.main:app --reload --port 8000
```
Then visit: **http://localhost:8000/docs** for interactive Swagger UI.

### Key Endpoints We Built

```
GET    /circuits          → List all circuits (paginated + filtered)
GET    /circuits/{id}     → Full detail for one circuit
POST   /circuits          → Create a new circuit
PATCH  /circuits/{id}     → Update specific fields
DELETE /circuits/{id}     → Delete circuit + all related records

GET    /search?q=QFT      → Full-text search
GET    /stats             → Aggregate statistics
GET    /stats/top-performers  → Top 10 by fidelity
GET    /meta/algorithms   → Distinct algorithm names
```

### Example API Call
```python
import requests

# Search for QFT circuits
r = requests.get("http://localhost:8000/search", params={"q": "QFT"})
circuits = r.json()["results"]

# Update a circuit's fidelity
r = requests.patch("http://localhost:8000/circuits/CIR-00001",
    json={"circuit_fidelity": 0.95, "mitigation_technique": "TREX"})
```

### Why FastAPI over Flask?
- **Automatic validation** via Pydantic models
- **Auto-generated docs** at `/docs`
- **Type hints** = fewer bugs
- **Async support** for high throughput
"""},
        "Lesson 4: Streamlit Dashboard": {
            "icon": "📊",
            "content": """
### What is Streamlit?
Streamlit turns Python scripts into interactive web dashboards — no HTML/JS needed.

### How to Run the Dashboard
```bash
streamlit run frontend/dashboard.py
```
Opens automatically at **http://localhost:8501**

### Dashboard Pages We Built

| Page | Purpose |
|------|---------|
| 🏠 Dashboard | KPIs, charts, top performers |
| 🔍 Search & Explore | Full-text + filtered search |
| ➕ Add Circuit | Insert new records via form |
| ✏️ Edit / Delete | Modify or remove records |
| 📖 Lessons | This guide! |

### Key Streamlit Concepts Used
```python
# Caching — avoid re-running expensive DB queries
@st.cache_data(ttl=300)
def get_distinct(col):
    return query(f"SELECT DISTINCT {col} FROM circuits")

# Multi-column layouts
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Total Circuits", "15,000")

# Forms for safe data entry
with st.form("my_form"):
    name = st.text_input("Circuit Name")
    submitted = st.form_submit_button("Save")

# Tabs for organized content
tab1, tab2 = st.tabs(["Circuit", "Qubits"])
```
"""},
        "Lesson 5: Full Architecture Overview": {
            "icon": "🏗️",
            "content": """
### System Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    User's Browser                        │
└──────────────┬──────────────────────┬───────────────────┘
               │                      │
               ▼                      ▼
┌─────────────────────┐   ┌────────────────────────┐
│  Streamlit Frontend │   │  FastAPI Backend        │
│  (Port 8501)        │   │  (Port 8000)            │
│                     │   │                         │
│  • Dashboard        │   │  • REST API endpoints   │
│  • Search UI        │   │  • Pydantic validation  │
│  • CRUD Forms       │   │  • Business logic       │
│  Direct DB access   │   │  • Auto Swagger docs    │
└──────────┬──────────┘   └────────────┬────────────┘
           │                           │
           └──────────┬────────────────┘
                      ▼
         ┌────────────────────────┐
         │   SQLite Database      │
         │   quantum_circuits.db  │
         │                        │
         │  circuits (21 cols)    │
         │  qubits   (20 cols)    │
         │  gates    (23 cols)    │
         │  results  (22 cols)    │
         │  noise_models (23 cols)│
         └────────────────────────┘
```

### Quick Start Commands
```bash
# Terminal 1 — Start FastAPI
cd quantum_dbms
uvicorn backend.main:app --reload --port 8000

# Terminal 2 — Start Streamlit
cd quantum_dbms
streamlit run frontend/dashboard.py

# View API docs
open http://localhost:8000/docs

# View Dashboard
open http://localhost:8501
```

### Project File Structure
```
quantum_dbms/
├── backend/
│   ├── main.py       ← FastAPI routes
│   └── models.py     ← Pydantic schemas
├── frontend/
│   └── dashboard.py  ← Streamlit app
├── db/
│   └── quantum_circuits.db  ← SQLite database
├── docs/
│   └── README.md     ← This guide
└── requirements.txt  ← Dependencies
```
"""},
        "Lesson 6: Running a SQL Query Playground": {
            "icon": "🧪",
            "content": """
### Try SQL Queries Directly

Open a Python shell or Jupyter notebook in the project directory:

```python
import sqlite3
import pandas as pd

conn = sqlite3.connect("db/quantum_circuits.db")

# 1. Find top 5 highest-fidelity QFT circuits
df = pd.read_sql(\"\"\"
    SELECT c.circuit_id, c.algorithm, c.backend,
           c.circuit_fidelity, g.total_gate_count
    FROM circuits c
    JOIN gates g ON c.circuit_id = g.circuit_id
    WHERE c.algorithm LIKE '%QFT%'
    ORDER BY c.circuit_fidelity DESC
    LIMIT 5
\"\"\", conn)
print(df)

# 2. Average fidelity by backend
df2 = pd.read_sql(\"\"\"
    SELECT backend, COUNT(*) as runs,
           ROUND(AVG(circuit_fidelity), 4) as avg_fidelity
    FROM circuits
    GROUP BY backend
    ORDER BY avg_fidelity DESC
\"\"\", conn)
print(df2)

# 3. Noise model impact on fidelity
df3 = pd.read_sql(\"\"\"
    SELECT n.noise_model,
           ROUND(AVG(c.circuit_fidelity), 4) as avg_fidelity,
           ROUND(AVG(n.total_circuit_error), 6) as avg_error
    FROM circuits c
    JOIN noise_models n ON c.circuit_id = n.circuit_id
    GROUP BY n.noise_model
    ORDER BY avg_fidelity DESC
    LIMIT 10
\"\"\", conn)
print(df3)

conn.close()
```

### Useful SQL Patterns
```sql
-- Window function: rank circuits within each algorithm
SELECT circuit_id, algorithm, circuit_fidelity,
       RANK() OVER (PARTITION BY algorithm ORDER BY circuit_fidelity DESC) as rank
FROM circuits;

-- Subquery: circuits better than average
SELECT * FROM circuits
WHERE circuit_fidelity > (SELECT AVG(circuit_fidelity) FROM circuits);

-- Multi-table join
SELECT c.circuit_id, c.algorithm, q.t1_relaxation_us,
       g.cnot_count, r.hellinger_fidelity
FROM circuits c
JOIN qubits q ON c.circuit_id = q.circuit_id
JOIN gates g ON c.circuit_id = g.circuit_id
JOIN results r ON c.circuit_id = r.circuit_id
WHERE c.circuit_fidelity > 0.95;
```
"""},
    }

    for title, lesson in lessons.items():
        with st.expander(f"{lesson['icon']} {title}", expanded=False):
            st.markdown(lesson["content"])

    st.divider()
    st.subheader("🧪 Live SQL Playground")
    st.info("Run any SELECT query against the live database below.")
    sql_input = st.text_area(
        "SQL Query",
        value="SELECT algorithm, COUNT(*) as count, ROUND(AVG(circuit_fidelity),4) as avg_fidelity\nFROM circuits\nGROUP BY algorithm\nORDER BY avg_fidelity DESC\nLIMIT 10",
        height=120
    )
    if st.button("▶️ Run Query", use_container_width=True):
        sql_clean = sql_input.strip().lower()
        if any(kw in sql_clean for kw in ["drop", "delete", "insert", "update", "alter", "create"]):
            st.error("❌ Only SELECT queries are allowed in the playground.")
        else:
            try:
                result = query(sql_input)
                st.dataframe(result, use_container_width=True)
                st.caption(f"{len(result)} rows returned")
            except Exception as e:
                st.error(f"SQL Error: {e}")
# ══════════════════════════════════════════════════════════════════════════════
# PAGE 5 — COMPARE CIRCUITS
# ══════════════════════════════════════════════════════════════════════════════
elif page == "📊 Compare Circuits":
    st.title("📊 Circuit Comparison Tool")
    st.caption("Compare any two circuits side by side across all metrics.")

    col1, col2 = st.columns(2)
    with col1:
        id1 = st.text_input("Circuit ID #1", placeholder="CIR-00001")
    with col2:
        id2 = st.text_input("Circuit ID #2", placeholder="CIR-00002")

    if id1 and id2:
        df1 = query("SELECT * FROM circuits WHERE circuit_id = ?", [id1])
        df2 = query("SELECT * FROM circuits WHERE circuit_id = ?", [id2])

        if df1.empty:
            st.error(f"Circuit '{id1}' not found.")
        elif df2.empty:
            st.error(f"Circuit '{id2}' not found.")
        else:
            c1, c2 = df1.iloc[0], df2.iloc[0]

            # ── KPI Comparison ─────────────────────────────────────────────
            st.subheader("⚡ Key Metrics")
            m1, m2, m3, m4 = st.columns(4)

            fid1, fid2 = float(c1.get("circuit_fidelity") or 0), float(c2.get("circuit_fidelity") or 0)
            suc1, suc2 = float(c1.get("success_rate") or 0), float(c2.get("success_rate") or 0)
            sh1, sh2 = int(c1.get("shots") or 0), int(c2.get("shots") or 0)

            m1.metric("Fidelity", f"{fid1:.2%}", f"{fid1 - fid2:+.2%} vs #2")
            m2.metric("Fidelity #2", f"{fid2:.2%}", f"{fid2 - fid1:+.2%} vs #1")
            m3.metric("Success Rate #1", f"{suc1:.2%}", f"{suc1 - suc2:+.2%} vs #2")
            m4.metric("Success Rate #2", f"{suc2:.2%}", f"{suc2 - suc1:+.2%} vs #1")

            # ── Winner Banner ───────────────────────────────────────────────
            st.divider()
            if fid1 > fid2:
                st.success(f"🏆 **{id1}** has higher fidelity by {fid1 - fid2:.2%}")
            elif fid2 > fid1:
                st.success(f"🏆 **{id2}** has higher fidelity by {fid2 - fid1:.2%}")
            else:
                st.info("🤝 Both circuits have equal fidelity!")

            # ── Side by Side Table ──────────────────────────────────────────
            st.subheader("📋 Circuit Details")
            merged = pd.DataFrame({
                "Field": df1.columns.tolist(),
                id1: df1.iloc[0].tolist(),
                id2: df2.iloc[0].tolist()
            })
            # Highlight rows where values differ
            def highlight_diff(row):
                if str(row[id1]) != str(row[id2]):
                    return ["background-color: #fff3cd"] * 3
                return [""] * 3
            st.dataframe(merged.style.apply(highlight_diff, axis=1), use_container_width=True, hide_index=True)

            # ── Gates Comparison ────────────────────────────────────────────
            st.subheader("🔩 Gates Comparison")
            g1 = query("SELECT * FROM gates WHERE circuit_id = ?", [id1])
            g2 = query("SELECT * FROM gates WHERE circuit_id = ?", [id2])

            if not g1.empty and not g2.empty:
                gate_cols = ["total_gate_count", "circuit_depth", "cnot_count",
                             "h_gate_count", "rz_gate_count", "two_qubit_gates", "transpiled_depth"]
                gate_data = pd.DataFrame({
                    "Metric": gate_cols,
                    id1: [g1.iloc[0].get(c, "N/A") for c in gate_cols],
                    id2: [g2.iloc[0].get(c, "N/A") for c in gate_cols],
                })
                st.dataframe(gate_data, use_container_width=True, hide_index=True)

                # Bar chart comparison
                chart_df = pd.DataFrame({
                    id1: [float(g1.iloc[0].get(c) or 0) for c in gate_cols],
                    id2: [float(g2.iloc[0].get(c) or 0) for c in gate_cols],
                }, index=gate_cols)
                st.bar_chart(chart_df)

            # ── Noise Model Comparison ──────────────────────────────────────
            st.subheader("🌊 Noise Model Comparison")
            n1 = query("SELECT * FROM noise_models WHERE circuit_id = ?", [id1])
            n2 = query("SELECT * FROM noise_models WHERE circuit_id = ?", [id2])

            if not n1.empty and not n2.empty:
                noise_cols = ["noise_model", "single_qubit_error_rate", "two_qubit_error_rate",
                              "readout_error_rate", "total_circuit_error", "depolarizing_prob_1q"]
                noise_data = pd.DataFrame({
                    "Metric": noise_cols,
                    id1: [n1.iloc[0].get(c, "N/A") for c in noise_cols],
                    id2: [n2.iloc[0].get(c, "N/A") for c in noise_cols],
                })
                st.dataframe(noise_data, use_container_width=True, hide_index=True)

            # ── Verdict ─────────────────────────────────────────────────────
            st.divider()
            st.subheader("📝 Auto Verdict")
            verdicts = []
            if fid1 > fid2:
                verdicts.append(f"✅ **{id1}** wins on fidelity ({fid1:.2%} vs {fid2:.2%})")
            else:
                verdicts.append(f"✅ **{id2}** wins on fidelity ({fid2:.2%} vs {fid1:.2%})")
            if suc1 > suc2:
                verdicts.append(f"✅ **{id1}** wins on success rate ({suc1:.2%} vs {suc2:.2%})")
            else:
                verdicts.append(f"✅ **{id2}** wins on success rate ({suc2:.2%} vs {suc1:.2%})")
            if sh1 > sh2:
                verdicts.append(f"ℹ️ **{id1}** used more shots ({sh1:,} vs {sh2:,}) — more statistically reliable")
            else:
                verdicts.append(f"ℹ️ **{id2}** used more shots ({sh2:,} vs {sh1:,}) — more statistically reliable")

            for v in verdicts:
                st.markdown(v)
# ══════════════════════════════════════════════════════════════════════════════
# PAGE — 🧬 CIRCUIT DNA FINGERPRINTING
# ══════════════════════════════════════════════════════════════════════════════
elif page == "🧬 DNA Fingerprinting":
    st.title("🧬 Quantum Circuit DNA Fingerprinting")
    st.caption("Every circuit has a unique genetic fingerprint built from 20 parameters across all 5 tables. Find circuits that are quantum twins — same DNA, different identity.")

    # ── How it works expander ──────────────────────────────────────────────────
    with st.expander("🔬 How does DNA Fingerprinting work?"):
        st.markdown("""
        Each circuit is converted into a **20-dimensional fingerprint vector** using:

        | Gene Group | Parameters |
        |------------|-----------|
        | 🔩 Gate DNA | two_qubit_gate_ratio, gate_depth_ratio, gate_cancellation_ratio, clifford ratio, circuit_depth |
        | 🔬 Qubit DNA | t1_relaxation_us, t2_decoherence_us, qubit_frequency_ghz, readout_error, crosstalk_coefficient |
        | 🌊 Noise DNA | single_qubit_error_rate, two_qubit_error_rate, total_circuit_error, amplitude_damping_rate, spam_error_rate |
        | ⚡ Performance DNA | circuit_fidelity, success_rate, leakage_rate, transpiled_depth, cnot_count |

        All values are **normalized** so no single parameter dominates.
        Similarity is measured using **cosine similarity** — two circuits with score > 0.99 are quantum twins.
        """)

    st.divider()

    # ── Load data ──────────────────────────────────────────────────────────────
    @st.cache_data(ttl=300)
    def load_dna_data(sample_size=2000):
        df = query(f"""
            SELECT c.circuit_id, c.algorithm, c.backend, c.category,
                   c.circuit_fidelity, c.success_rate,
                   g.two_qubit_gate_ratio, g.gate_depth_ratio, g.gate_cancellation_ratio,
                   g.circuit_depth, g.cnot_count, g.transpiled_depth,
                   CAST(g.clifford_gates AS FLOAT) / NULLIF(g.total_gate_count, 0) as clifford_ratio,
                   q.t1_relaxation_us, q.t2_decoherence_us, q.qubit_frequency_ghz,
                   q.readout_error, q.crosstalk_coefficient, q.leakage_rate,
                   n.single_qubit_error_rate, n.two_qubit_error_rate,
                   n.total_circuit_error, n.amplitude_damping_rate, n.spam_error_rate
            FROM circuits c
            JOIN gates g ON c.circuit_id = g.circuit_id
            JOIN qubits q ON c.circuit_id = q.circuit_id
            JOIN noise_models n ON c.circuit_id = n.circuit_id
            LIMIT {sample_size}
        """)
        return df

    FEATURE_COLS = [
        "two_qubit_gate_ratio", "gate_depth_ratio", "gate_cancellation_ratio",
        "clifford_ratio", "circuit_depth",
        "t1_relaxation_us", "t2_decoherence_us", "qubit_frequency_ghz",
        "readout_error", "crosstalk_coefficient",
        "single_qubit_error_rate", "two_qubit_error_rate",
        "total_circuit_error", "amplitude_damping_rate", "spam_error_rate",
        "circuit_fidelity", "success_rate", "leakage_rate",
        "transpiled_depth", "cnot_count"
    ]

    sample_size = st.slider("Sample size (more = slower but richer)", 500, 3000, 1000, 500)
    df = load_dna_data(sample_size)

    # Normalize the feature matrix
    features = df[FEATURE_COLS].fillna(0).values.astype(float)
    col_min = features.min(axis=0)
    col_max = features.max(axis=0)
    col_range = col_max - col_min
    col_range[col_range == 0] = 1
    features_norm = (features - col_min) / col_range

    # ── SECTION 1: Single Circuit DNA ─────────────────────────────────────────
    st.subheader("🔬 View a Circuit's DNA Fingerprint")
    dna_id = st.text_input("Enter a Circuit ID", placeholder="CIR-00001", key="dna_input")

    if dna_id:
        match = df[df["circuit_id"] == dna_id]
        if match.empty:
            st.error(f"Circuit '{dna_id}' not found in current sample. Try increasing sample size or check the ID.")
        else:
            idx = match.index[0]
            row = match.iloc[0]
            fingerprint = features_norm[df.index.get_loc(idx)]

            st.success(f"**{dna_id}** | Algorithm: `{row['algorithm']}` | Backend: `{row['backend']}` | Fidelity: `{row['circuit_fidelity']:.4f}`")

            # Radar-style bar chart of the DNA
            dna_df = pd.DataFrame({
                "Gene": FEATURE_COLS,
                "Value": fingerprint,
                "Group": (
                    ["🔩 Gate"] * 5 +
                    ["🔬 Qubit"] * 5 +
                    ["🌊 Noise"] * 5 +
                    ["⚡ Performance"] * 5
                )
            })

            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**Full DNA Strand**")
                dna_chart = dna_df.set_index("Gene")["Value"]
                st.bar_chart(dna_chart)

            with col2:
                st.markdown("**DNA by Gene Group**")
                group_avg = dna_df.groupby("Group")["Value"].mean()
                st.bar_chart(group_avg)

            # Gene breakdown table
            st.markdown("**Raw Gene Values**")
            display_df = pd.DataFrame({
                "Gene": FEATURE_COLS,
                "Group": dna_df["Group"],
                "Normalized (0-1)": [f"{v:.4f}" for v in fingerprint],
                "Raw Value": [f"{match.iloc[0][c]:.6f}" if isinstance(match.iloc[0][c], float) else str(match.iloc[0][c]) for c in FEATURE_COLS]
            })
            st.dataframe(display_df, use_container_width=True, hide_index=True)

    st.divider()

    # ── SECTION 2: Find Quantum Twins ─────────────────────────────────────────
    st.subheader("👯 Find Quantum Twins (Most Similar Circuits)")
    st.caption("Find circuits with the most similar DNA fingerprint — regardless of algorithm or backend.")

    twin_id = st.text_input("Enter Circuit ID to find its twins", placeholder="CIR-00001", key="twin_input")
    top_n = st.slider("Number of twins to find", 3, 20, 8)

    if twin_id:
        match = df[df["circuit_id"] == twin_id]
        if match.empty:
            st.error(f"Circuit '{twin_id}' not found in current sample.")
        else:
            idx = df.index.get_loc(match.index[0])
            query_vec = features_norm[idx]

            # Cosine similarity
            norms = np.linalg.norm(features_norm, axis=1, keepdims=True)
            norms[norms == 0] = 1
            normed = features_norm / norms
            query_norm = query_vec / (np.linalg.norm(query_vec) or 1)
            similarities = normed @ query_norm

            sim_df = df[["circuit_id", "algorithm", "backend", "category",
                          "circuit_fidelity", "success_rate"]].copy()
            sim_df["dna_similarity"] = similarities
            sim_df = sim_df[sim_df["circuit_id"] != twin_id]
            sim_df = sim_df.sort_values("dna_similarity", ascending=False).head(top_n)
            sim_df["dna_similarity"] = sim_df["dna_similarity"].apply(lambda x: f"{x:.6f}")

            target = match.iloc[0]
            st.info(f"**{twin_id}** → Algorithm: `{target['algorithm']}` | Backend: `{target['backend']}`")

            # Highlight twins with different algorithm (the interesting ones)
            st.markdown("**Top DNA Twins** — 🟡 highlights circuits with a *different* algorithm (cross-algorithm twins)")

            def highlight_cross_algo(row):
                algo = row["algorithm"]
                color = "#2d5a27" if algo != target["algorithm"] else ""
                return [f"background-color: {color}"] * len(row)

            st.dataframe(
                sim_df.style.apply(highlight_cross_algo, axis=1),
                use_container_width=True,
                hide_index=True
            )

            # Summary stats
            result_df = sim_df.copy()
            result_df["dna_similarity"] = result_df["dna_similarity"].astype(float)
            same_algo = (result_df["algorithm"] == target["algorithm"]).sum()
            diff_algo = (result_df["algorithm"] != target["algorithm"]).sum()
            same_backend = (result_df["backend"] == target["backend"]).sum()

            m1, m2, m3 = st.columns(3)
            m1.metric("Same Algorithm Twins", same_algo)
            m2.metric("Cross-Algorithm Twins 🟡", diff_algo)
            m3.metric("Same Backend Twins", same_backend)

    st.divider()

    # ── SECTION 3: Anomaly Detector ───────────────────────────────────────────
    st.subheader("🕵️ Quantum Anomalies — Circuits That Defy Their DNA")
    st.caption("Circuits whose performance is wildly different from what their hardware & gate DNA predicts.")

    if st.button("🔍 Find Anomalies", use_container_width=True):
        # Predict fidelity from non-performance features (first 15 genes)
        X = features_norm[:, :15]   # Gate + Qubit + Noise DNA only
        y = features_norm[:, 15]    # circuit_fidelity (normalized)

        # Simple linear prediction using dot product weights
        # Use correlation of each feature with fidelity as weight
        correlations = np.array([np.corrcoef(X[:, i], y)[0, 1] for i in range(X.shape[1])])
        correlations = np.nan_to_num(correlations)
        weights = correlations / (np.sum(np.abs(correlations)) or 1)
        predicted = X @ weights

        # Normalize predicted to 0-1
        pred_min, pred_max = predicted.min(), predicted.max()
        if pred_max > pred_min:
            predicted_norm = (predicted - pred_min) / (pred_max - pred_min)
        else:
            predicted_norm = predicted

        actual_norm = features_norm[:, 15]
        residual = actual_norm - predicted_norm  # positive = overperformer, negative = underperformer

        anomaly_df = df[["circuit_id", "algorithm", "backend", "circuit_fidelity", "success_rate"]].copy()
        anomaly_df["predicted_fidelity_score"] = predicted_norm
        anomaly_df["actual_fidelity_score"] = actual_norm
        anomaly_df["anomaly_score"] = residual

        overperformers = anomaly_df.nlargest(8, "anomaly_score")
        underperformers = anomaly_df.nsmallest(8, "anomaly_score")

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("### 🚀 Overperformers")
            st.caption("High fidelity despite bad hardware/noise DNA")
            op = overperformers[["circuit_id", "algorithm", "backend",
                                  "circuit_fidelity", "anomaly_score"]].copy()
            op["anomaly_score"] = op["anomaly_score"].apply(lambda x: f"+{x:.4f}")
            st.dataframe(op, use_container_width=True, hide_index=True)

        with col2:
            st.markdown("### 💀 Underperformers")
            st.caption("Low fidelity despite good hardware/noise DNA")
            up = underperformers[["circuit_id", "algorithm", "backend",
                                   "circuit_fidelity", "anomaly_score"]].copy()
            up["anomaly_score"] = up["anomaly_score"].apply(lambda x: f"{x:.4f}")
            st.dataframe(up, use_container_width=True, hide_index=True)

    st.divider()

    # ── SECTION 4: Algorithm DNA Clusters ─────────────────────────────────────
    st.subheader("🗺️ Algorithm DNA Similarity Map")
    st.caption("Which algorithms share the most similar average DNA fingerprint?")

    if st.button("🧬 Generate Similarity Map", use_container_width=True):
        algo_groups = df.groupby("algorithm")
        algo_names = []
        algo_vecs = []

        for algo, group in algo_groups:
            if len(group) >= 3:
                idxs = [df.index.get_loc(i) for i in group.index if i < len(features_norm)]
                vecs = features_norm[idxs]
                algo_vecs.append(vecs.mean(axis=0))
                algo_names.append(algo)

        algo_matrix = np.array(algo_vecs)
        norms = np.linalg.norm(algo_matrix, axis=1, keepdims=True)
        norms[norms == 0] = 1
        algo_normed = algo_matrix / norms
        sim_matrix = algo_normed @ algo_normed.T

        sim_display = pd.DataFrame(sim_matrix, index=algo_names, columns=algo_names)

        st.markdown("**Algorithm DNA Similarity Matrix** (1.0 = identical DNA)")
        st.dataframe(
            sim_display.style.background_gradient(cmap="YlOrRd", vmin=0.5, vmax=1.0)
                             .format("{:.3f}"),
            use_container_width=True
        )

        # Find most and least similar pairs
        pairs = []
        for i in range(len(algo_names)):
            for j in range(i+1, len(algo_names)):
                pairs.append((algo_names[i], algo_names[j], sim_matrix[i][j]))

        pairs_df = pd.DataFrame(pairs, columns=["Algorithm A", "Algorithm B", "DNA Similarity"])

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**🧬 Most Similar Algorithm Pairs**")
            top_pairs = pairs_df.nlargest(5, "DNA Similarity")
            top_pairs["DNA Similarity"] = top_pairs["DNA Similarity"].apply(lambda x: f"{x:.4f}")
            st.dataframe(top_pairs, use_container_width=True, hide_index=True)
        with col2:
            st.markdown("**🔀 Most Different Algorithm Pairs**")
            bot_pairs = pairs_df.nsmallest(5, "DNA Similarity")
            bot_pairs["DNA Similarity"] = bot_pairs["DNA Similarity"].apply(lambda x: f"{x:.4f}")
            st.dataframe(bot_pairs, use_container_width=True, hide_index=True)