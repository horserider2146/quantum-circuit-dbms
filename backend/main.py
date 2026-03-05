"""
Quantum Circuit Database - FastAPI Backend
==========================================
RESTful API for full CRUD operations on the quantum circuit database.
"""

from fastapi import FastAPI, HTTPException, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, List
import sqlite3
import os
from contextlib import contextmanager
from backend.models import (
    CircuitCreate, CircuitUpdate, CircuitResponse,
    QubitUpdate, GateUpdate, ResultUpdate, NoiseModelUpdate,
    SearchResponse, StatsResponse
)

# ── App Setup ──────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Quantum Circuit Database API",
    description="CRUD + Search API for 15,000 quantum circuit experiments",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Resolve DB path relative to this file
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "db", "quantum_circuits.db")


# ── DB Helper ──────────────────────────────────────────────────────────────────
@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def row_to_dict(row):
    return dict(row) if row else None


# ── Health ─────────────────────────────────────────────────────────────────────
@app.get("/", tags=["Health"])
def root():
    return {"status": "ok", "message": "Quantum Circuit DB API is running 🚀"}


@app.get("/health", tags=["Health"])
def health():
    with get_db() as conn:
        count = conn.execute("SELECT COUNT(*) FROM circuits").fetchone()[0]
    return {"status": "healthy", "total_circuits": count, "db_path": DB_PATH}


# ── CIRCUITS CRUD ──────────────────────────────────────────────────────────────
@app.get("/circuits", tags=["Circuits"])
def list_circuits(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=200),
    algorithm: Optional[str] = None,
    backend: Optional[str] = None,
    category: Optional[str] = None,
    min_fidelity: Optional[float] = None,
    max_fidelity: Optional[float] = None,
    is_simulator: Optional[str] = None,
):
    """List circuits with optional filters and pagination."""
    offset = (page - 1) * limit
    where_clauses = []
    params = []

    if algorithm:
        where_clauses.append("LOWER(algorithm) LIKE ?")
        params.append(f"%{algorithm.lower()}%")
    if backend:
        where_clauses.append("LOWER(backend) LIKE ?")
        params.append(f"%{backend.lower()}%")
    if category:
        where_clauses.append("LOWER(category) LIKE ?")
        params.append(f"%{category.lower()}%")
    if min_fidelity is not None:
        where_clauses.append("circuit_fidelity >= ?")
        params.append(min_fidelity)
    if max_fidelity is not None:
        where_clauses.append("circuit_fidelity <= ?")
        params.append(max_fidelity)
    if is_simulator is not None:
        where_clauses.append("is_simulator = ?")
        params.append(is_simulator)

    where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

    with get_db() as conn:
        total = conn.execute(f"SELECT COUNT(*) FROM circuits {where_sql}", params).fetchone()[0]
        rows = conn.execute(
            f"SELECT * FROM circuits {where_sql} LIMIT ? OFFSET ?",
            params + [limit, offset]
        ).fetchall()

    return {
        "total": total,
        "page": page,
        "limit": limit,
        "pages": (total + limit - 1) // limit,
        "data": [row_to_dict(r) for r in rows]
    }


@app.get("/circuits/{circuit_id}", tags=["Circuits"])
def get_circuit(circuit_id: str):
    """Get a single circuit by ID with all related data."""
    with get_db() as conn:
        circuit = conn.execute("SELECT * FROM circuits WHERE circuit_id = ?", [circuit_id]).fetchone()
        if not circuit:
            raise HTTPException(status_code=404, detail=f"Circuit '{circuit_id}' not found")
        qubits = conn.execute("SELECT * FROM qubits WHERE circuit_id = ?", [circuit_id]).fetchone()
        gates = conn.execute("SELECT * FROM gates WHERE circuit_id = ?", [circuit_id]).fetchone()
        results = conn.execute("SELECT * FROM results WHERE circuit_id = ?", [circuit_id]).fetchone()
        noise = conn.execute("SELECT * FROM noise_models WHERE circuit_id = ?", [circuit_id]).fetchone()

    return {
        "circuit": row_to_dict(circuit),
        "qubits": row_to_dict(qubits),
        "gates": row_to_dict(gates),
        "results": row_to_dict(results),
        "noise_model": row_to_dict(noise)
    }


@app.post("/circuits", tags=["Circuits"], status_code=201)
def create_circuit(data: CircuitCreate):
    """Create a new circuit record."""
    with get_db() as conn:
        existing = conn.execute("SELECT 1 FROM circuits WHERE circuit_id = ?", [data.circuit_id]).fetchone()
        if existing:
            raise HTTPException(status_code=409, detail=f"Circuit '{data.circuit_id}' already exists")
        conn.execute(
            """INSERT INTO circuits (circuit_id, job_id, circuit_name, algorithm, category,
               backend, architecture, quantum_volume, experiment_date, qiskit_version,
               is_simulator, optimization_level, transpiler_pass, connectivity,
               clops, shots, execution_time_ms, mitigation_technique,
               circuit_fidelity, success_rate, dominant_state)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            [data.circuit_id, data.job_id, data.circuit_name, data.algorithm, data.category,
             data.backend, data.architecture, data.quantum_volume, data.experiment_date,
             data.qiskit_version, data.is_simulator, data.optimization_level,
             data.transpiler_pass, data.connectivity, data.clops, data.shots,
             data.execution_time_ms, data.mitigation_technique,
             data.circuit_fidelity, data.success_rate, data.dominant_state]
        )
    return {"message": "Circuit created", "circuit_id": data.circuit_id}


@app.patch("/circuits/{circuit_id}", tags=["Circuits"])
def update_circuit(circuit_id: str, data: CircuitUpdate):
    """Partially update a circuit record."""
    updates = {k: v for k, v in data.dict().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields provided to update")

    set_clause = ", ".join(f"{k} = ?" for k in updates)
    params = list(updates.values()) + [circuit_id]

    with get_db() as conn:
        existing = conn.execute("SELECT 1 FROM circuits WHERE circuit_id = ?", [circuit_id]).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail=f"Circuit '{circuit_id}' not found")
        conn.execute(f"UPDATE circuits SET {set_clause} WHERE circuit_id = ?", params)

    return {"message": "Circuit updated", "circuit_id": circuit_id, "updated_fields": list(updates.keys())}


@app.delete("/circuits/{circuit_id}", tags=["Circuits"])
def delete_circuit(circuit_id: str):
    """Delete a circuit and all its related records."""
    with get_db() as conn:
        existing = conn.execute("SELECT 1 FROM circuits WHERE circuit_id = ?", [circuit_id]).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail=f"Circuit '{circuit_id}' not found")
        for table in ["qubits", "gates", "results", "noise_models", "circuits"]:
            conn.execute(f"DELETE FROM {table} WHERE circuit_id = ?", [circuit_id])

    return {"message": f"Circuit '{circuit_id}' and all related records deleted"}


# ── SEARCH ─────────────────────────────────────────────────────────────────────
@app.get("/search", tags=["Search"])
def search(
    q: str = Query(..., min_length=1, description="Search term"),
    limit: int = Query(20, ge=1, le=100)
):
    """Full-text search across circuit_id, algorithm, backend, category, circuit_name."""
    term = f"%{q.lower()}%"
    with get_db() as conn:
        rows = conn.execute(
            """SELECT circuit_id, circuit_name, algorithm, category, backend,
                      circuit_fidelity, success_rate, experiment_date
               FROM circuits
               WHERE LOWER(circuit_id) LIKE ?
                  OR LOWER(circuit_name) LIKE ?
                  OR LOWER(algorithm) LIKE ?
                  OR LOWER(category) LIKE ?
                  OR LOWER(backend) LIKE ?
               LIMIT ?""",
            [term, term, term, term, term, limit]
        ).fetchall()
    return {"query": q, "count": len(rows), "results": [row_to_dict(r) for r in rows]}


# ── STATS ──────────────────────────────────────────────────────────────────────
@app.get("/stats", tags=["Statistics"])
def get_stats():
    """Aggregate statistics for dashboard."""
    with get_db() as conn:
        total = conn.execute("SELECT COUNT(*) FROM circuits").fetchone()[0]
        avg_fidelity = conn.execute("SELECT ROUND(AVG(circuit_fidelity),4) FROM circuits").fetchone()[0]
        avg_success = conn.execute("SELECT ROUND(AVG(success_rate),4) FROM circuits").fetchone()[0]

        top_algorithms = conn.execute(
            "SELECT algorithm, COUNT(*) as count FROM circuits GROUP BY algorithm ORDER BY count DESC LIMIT 10"
        ).fetchall()

        top_backends = conn.execute(
            "SELECT backend, COUNT(*) as count FROM circuits GROUP BY backend ORDER BY count DESC LIMIT 10"
        ).fetchall()

        categories = conn.execute(
            "SELECT category, COUNT(*) as count FROM circuits GROUP BY category ORDER BY count DESC"
        ).fetchall()

        fidelity_dist = conn.execute(
            """SELECT
                CASE
                    WHEN circuit_fidelity >= 0.9 THEN '0.9-1.0'
                    WHEN circuit_fidelity >= 0.8 THEN '0.8-0.9'
                    WHEN circuit_fidelity >= 0.7 THEN '0.7-0.8'
                    WHEN circuit_fidelity >= 0.6 THEN '0.6-0.7'
                    ELSE '< 0.6'
                END as range, COUNT(*) as count
               FROM circuits GROUP BY range ORDER BY range DESC"""
        ).fetchall()

        sim_vs_real = conn.execute(
            "SELECT is_simulator, COUNT(*) as count FROM circuits GROUP BY is_simulator"
        ).fetchall()

        monthly = conn.execute(
            """SELECT strftime('%Y-%m', experiment_date) as month, COUNT(*) as count
               FROM circuits WHERE experiment_date IS NOT NULL
               GROUP BY month ORDER BY month"""
        ).fetchall()

    return {
        "total_circuits": total,
        "avg_fidelity": avg_fidelity,
        "avg_success_rate": avg_success,
        "top_algorithms": [row_to_dict(r) for r in top_algorithms],
        "top_backends": [row_to_dict(r) for r in top_backends],
        "categories": [row_to_dict(r) for r in categories],
        "fidelity_distribution": [row_to_dict(r) for r in fidelity_dist],
        "simulator_vs_real": [row_to_dict(r) for r in sim_vs_real],
        "monthly_experiments": [row_to_dict(r) for r in monthly],
    }


@app.get("/stats/top-performers", tags=["Statistics"])
def top_performers(limit: int = Query(10, ge=1, le=50)):
    """Top circuits by circuit fidelity."""
    with get_db() as conn:
        rows = conn.execute(
            """SELECT c.circuit_id, c.circuit_name, c.algorithm, c.backend,
                      c.circuit_fidelity, c.success_rate, c.shots,
                      g.total_gate_count, g.circuit_depth
               FROM circuits c
               LEFT JOIN gates g ON c.circuit_id = g.circuit_id
               ORDER BY c.circuit_fidelity DESC
               LIMIT ?""", [limit]
        ).fetchall()
    return {"data": [row_to_dict(r) for r in rows]}


# ── DISTINCT VALUES FOR FILTERS ────────────────────────────────────────────────
@app.get("/meta/algorithms", tags=["Meta"])
def get_algorithms():
    with get_db() as conn:
        rows = conn.execute("SELECT DISTINCT algorithm FROM circuits ORDER BY algorithm").fetchall()
    return [r[0] for r in rows if r[0]]


@app.get("/meta/backends", tags=["Meta"])
def get_backends():
    with get_db() as conn:
        rows = conn.execute("SELECT DISTINCT backend FROM circuits ORDER BY backend").fetchall()
    return [r[0] for r in rows if r[0]]


@app.get("/meta/categories", tags=["Meta"])
def get_categories():
    with get_db() as conn:
        rows = conn.execute("SELECT DISTINCT category FROM circuits ORDER BY category").fetchall()
    return [r[0] for r in rows if r[0]]


# ── RELATED TABLE UPDATES ──────────────────────────────────────────────────────
@app.patch("/qubits/{circuit_id}", tags=["Qubits"])
def update_qubits(circuit_id: str, data: QubitUpdate):
    updates = {k: v for k, v in data.dict().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    with get_db() as conn:
        conn.execute(f"UPDATE qubits SET {set_clause} WHERE circuit_id = ?", list(updates.values()) + [circuit_id])
    return {"message": "Qubits updated", "circuit_id": circuit_id}


@app.patch("/noise/{circuit_id}", tags=["Noise Models"])
def update_noise(circuit_id: str, data: NoiseModelUpdate):
    updates = {k: v for k, v in data.dict().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    with get_db() as conn:
        conn.execute(f"UPDATE noise_models SET {set_clause} WHERE circuit_id = ?", list(updates.values()) + [circuit_id])
    return {"message": "Noise model updated", "circuit_id": circuit_id}