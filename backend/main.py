"""
Quantum Circuit Database - FastAPI Backend
==========================================
RESTful API for full CRUD operations on the quantum circuit database.
"""

from fastapi import FastAPI, HTTPException, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader
from typing import Optional, List
import sqlite3
import os
import json
from datetime import datetime, timezone
from uuid import uuid4
from contextlib import contextmanager
from backend.models import (
    CircuitCreate, CircuitUpdate, CircuitResponse,
    QubitUpdate, GateUpdate, ResultUpdate, NoiseModelUpdate,
    SearchResponse, StatsResponse,
    BuilderStep, BuilderPreviewRequest, BuilderPreviewResponse,
    BuilderSaveRequest, BuilderSaveResponse,
    BulkCircuitUploadRequest, BulkCircuitUploadResponse,
    SavedFilterCreate, SavedFilterResponse,
    SoftDeleteRequest, RestoreCircuitRequest,
    HardwareRecommendRequest,
    QuantumWhatIfRequest, QuantumWhatIfRecommendationRequest,
)

# ── Auth ───────────────────────────────────────────────────────────────────────
API_KEY = os.getenv("API_KEY", "dev-api-key")
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def require_api_key(api_key: Optional[str] = Depends(api_key_header)):
    if api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


# ── App Setup ──────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Quantum Circuit Database API",
    description="CRUD + Search API for 15,000 quantum circuit experiments",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    dependencies=[Depends(require_api_key)],
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

SINGLE_QUBIT_GATES = {"I", "X", "Y", "Z", "H", "S", "T", "RX", "RY", "RZ"}
CONTROLLED_GATES = {"CNOT", "CZ", "CRX", "CRY", "CRZ"}
SWAP_GATES = {"SWAP"}
PARAMETER_GATES = {"RX", "RY", "RZ", "CRX", "CRY", "CRZ"}
GATES_WITH_SECOND_QUBIT = CONTROLLED_GATES | SWAP_GATES
SUPPORTED_GATES = SINGLE_QUBIT_GATES | CONTROLLED_GATES | SWAP_GATES


def ensure_builder_tables():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS user_circuits (
                user_circuit_id TEXT PRIMARY KEY,
                circuit_name TEXT NOT NULL,
                num_qubits INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                created_by TEXT,
                notes TEXT
            );

            CREATE TABLE IF NOT EXISTS user_circuit_steps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_circuit_id TEXT NOT NULL,
                step_index INTEGER NOT NULL,
                gate TEXT NOT NULL,
                target_qubit INTEGER NOT NULL,
                control_qubit INTEGER,
                parameter REAL,
                FOREIGN KEY(user_circuit_id) REFERENCES user_circuits(user_circuit_id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_user_circuits_created_at
            ON user_circuits(created_at DESC);

            CREATE INDEX IF NOT EXISTS idx_user_circuit_steps_order
            ON user_circuit_steps(user_circuit_id, step_index);

            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                table_name TEXT NOT NULL,
                record_id TEXT NOT NULL,
                operation TEXT NOT NULL,
                changed_by TEXT,
                changed_at TEXT NOT NULL,
                details_json TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_audit_logs_record
            ON audit_logs(table_name, record_id, changed_at DESC);

            CREATE TABLE IF NOT EXISTS saved_filters (
                filter_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                params_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                created_by TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_saved_filters_created_at
            ON saved_filters(created_at DESC);
            """
        )

        has_circuits = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='circuits'"
        ).fetchone()
        if has_circuits:
            columns = {
                row[1] for row in conn.execute("PRAGMA table_info(circuits)").fetchall()
            }
            if "is_deleted" not in columns:
                conn.execute("ALTER TABLE circuits ADD COLUMN is_deleted INTEGER NOT NULL DEFAULT 0")
            if "deleted_at" not in columns:
                conn.execute("ALTER TABLE circuits ADD COLUMN deleted_at TEXT")
            if "deleted_by" not in columns:
                conn.execute("ALTER TABLE circuits ADD COLUMN deleted_by TEXT")

            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_circuits_is_deleted ON circuits(is_deleted)"
            )
        conn.commit()
    finally:
        conn.close()


@app.on_event("startup")
def startup():
    ensure_builder_tables()


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


def circuit_insert_payload(data: CircuitCreate) -> List[Optional[object]]:
    return [
        data.circuit_id,
        data.job_id,
        data.circuit_name,
        data.algorithm,
        data.category,
        data.backend,
        data.architecture,
        data.quantum_volume,
        data.experiment_date,
        data.qiskit_version,
        data.is_simulator,
        data.optimization_level,
        data.transpiler_pass,
        data.connectivity,
        data.clops,
        data.shots,
        data.execution_time_ms,
        data.mitigation_technique,
        data.circuit_fidelity,
        data.success_rate,
        data.dominant_state,
    ]


def add_audit_log(
    conn: sqlite3.Connection,
    table_name: str,
    record_id: str,
    operation: str,
    changed_by: Optional[str],
    details: dict,
):
    conn.execute(
        """INSERT INTO audit_logs (table_name, record_id, operation, changed_by, changed_at, details_json)
           VALUES (?, ?, ?, ?, ?, ?)""",
        [
            table_name,
            record_id,
            operation,
            changed_by,
            datetime.now(timezone.utc).isoformat(),
            json.dumps(details),
        ],
    )


def validate_builder_payload(num_qubits: int, steps: List[BuilderStep], require_steps: bool = False):
    if num_qubits < 1 or num_qubits > 32:
        raise HTTPException(status_code=400, detail="num_qubits must be between 1 and 32")

    if require_steps and not steps:
        raise HTTPException(status_code=400, detail="At least one gate step is required")

    for idx, step in enumerate(steps, start=1):
        gate = step.gate.upper().strip()
        if gate not in SUPPORTED_GATES:
            raise HTTPException(status_code=400, detail=f"Step {idx}: unsupported gate '{step.gate}'")

        if step.target_qubit < 0 or step.target_qubit >= num_qubits:
            raise HTTPException(
                status_code=400,
                detail=f"Step {idx}: target_qubit must be between 0 and {num_qubits - 1}",
            )

        second_qubit = step.control_qubit
        if gate in GATES_WITH_SECOND_QUBIT:
            if second_qubit is None:
                raise HTTPException(status_code=400, detail=f"Step {idx}: {gate} requires control_qubit")
            if second_qubit < 0 or second_qubit >= num_qubits:
                raise HTTPException(
                    status_code=400,
                    detail=f"Step {idx}: control_qubit must be between 0 and {num_qubits - 1}",
                )
            if second_qubit == step.target_qubit:
                raise HTTPException(status_code=400, detail=f"Step {idx}: qubit indices must be distinct")
        elif second_qubit is not None:
            raise HTTPException(status_code=400, detail=f"Step {idx}: gate {gate} does not use control_qubit")

        if gate in PARAMETER_GATES and step.parameter is None:
            raise HTTPException(status_code=400, detail=f"Step {idx}: gate {gate} requires parameter")
        if gate not in PARAMETER_GATES and step.parameter is not None:
            raise HTTPException(status_code=400, detail=f"Step {idx}: gate {gate} does not use parameter")


def render_builder_preview(num_qubits: int, steps: List[BuilderStep]) -> List[str]:
    lines = [f"q{i}: " for i in range(num_qubits)]
    for step in steps:
        gate = step.gate.upper().strip()
        low = min(step.target_qubit, step.control_qubit) if step.control_qubit is not None else -1
        high = max(step.target_qubit, step.control_qubit) if step.control_qubit is not None else -1

        for q in range(num_qubits):
            token = "---"
            if q == step.target_qubit:
                if gate == "CNOT":
                    token = "X"
                elif gate == "SWAP":
                    token = "x"
                else:
                    token = gate
            elif step.control_qubit is not None and q == step.control_qubit:
                token = "x" if gate == "SWAP" else "o"
            elif step.control_qubit is not None and low < q < high:
                token = "|"

            lines[q] += f"{token:^9}"

    return lines


def _fetch_base_profile(conn: sqlite3.Connection, payload: QuantumWhatIfRequest) -> dict:
    profile = {
        "circuit_id": payload.circuit_id,
        "algorithm": payload.algorithm,
        "backend": payload.backend,
        "mitigation_technique": payload.mitigation_technique,
        "optimization_level": payload.optimization_level,
        "shots": payload.shots,
        "circuit_depth": payload.circuit_depth,
        "num_qubits_used": payload.num_qubits_used,
        "total_circuit_error": payload.total_circuit_error,
    }

    if payload.circuit_id:
        row = conn.execute(
            """SELECT c.circuit_id, c.algorithm, c.backend, c.mitigation_technique,
                      c.optimization_level, c.shots, g.circuit_depth,
                      q.num_qubits_used, n.total_circuit_error
               FROM circuits c
               LEFT JOIN gates g ON c.circuit_id = g.circuit_id
               LEFT JOIN qubits q ON c.circuit_id = q.circuit_id
               LEFT JOIN noise_models n ON c.circuit_id = n.circuit_id
               WHERE c.circuit_id = ? AND COALESCE(c.is_deleted, 0) = 0""",
            [payload.circuit_id],
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Circuit '{payload.circuit_id}' not found")

        row_dict = row_to_dict(row)
        for key in profile:
            if profile[key] is None:
                profile[key] = row_dict.get(key)

    if not profile.get("algorithm"):
        raise HTTPException(status_code=400, detail="Provide algorithm or a valid circuit_id")

    return profile


def _predict_from_profile(conn: sqlite3.Connection, profile: dict, min_samples: int) -> dict:
    where = ["COALESCE(c.is_deleted, 0) = 0", "LOWER(c.algorithm) = ?"]
    params: List[object] = [str(profile.get("algorithm", "")).lower()]

    if profile.get("backend"):
        where.append("LOWER(c.backend) = ?")
        params.append(str(profile["backend"]).lower())
    if profile.get("mitigation_technique"):
        where.append("LOWER(COALESCE(c.mitigation_technique, 'none')) = ?")
        params.append(str(profile["mitigation_technique"]).lower())
    if profile.get("optimization_level") is not None:
        where.append("c.optimization_level = ?")
        params.append(profile["optimization_level"])

    if profile.get("shots") is not None:
        shots = max(int(profile["shots"]), 1)
        where.append("c.shots BETWEEN ? AND ?")
        params.extend([int(shots * 0.7), int(shots * 1.3)])

    if profile.get("circuit_depth") is not None:
        depth = max(int(profile["circuit_depth"]), 1)
        where.append("g.circuit_depth BETWEEN ? AND ?")
        params.extend([max(1, int(depth * 0.7)), int(depth * 1.3)])

    if profile.get("num_qubits_used") is not None:
        num_qubits = max(int(profile["num_qubits_used"]), 1)
        where.append("q.num_qubits_used BETWEEN ? AND ?")
        params.extend([max(1, num_qubits - 6), num_qubits + 6])

    if profile.get("total_circuit_error") is not None:
        err = float(profile["total_circuit_error"])
        low, high = max(0.0, err - 0.03), err + 0.03
        where.append("COALESCE(n.total_circuit_error, 0) BETWEEN ? AND ?")
        params.extend([low, high])

    where_sql = " AND ".join(where)
    row = conn.execute(
        f"""SELECT COUNT(*) AS sample_count,
                   ROUND(AVG(c.circuit_fidelity), 6) AS predicted_fidelity,
                   ROUND(AVG(c.success_rate), 6) AS predicted_success_rate,
                   ROUND(AVG(COALESCE(n.total_circuit_error, 0)), 6) AS avg_total_error,
                   ROUND(AVG(COALESCE(g.circuit_depth, 0)), 2) AS avg_depth,
                   ROUND(AVG(COALESCE(q.num_qubits_used, 0)), 2) AS avg_num_qubits
            FROM circuits c
            LEFT JOIN gates g ON c.circuit_id = g.circuit_id
            LEFT JOIN qubits q ON c.circuit_id = q.circuit_id
            LEFT JOIN noise_models n ON c.circuit_id = n.circuit_id
            WHERE {where_sql}""",
        params,
    ).fetchone()

    data = row_to_dict(row) or {}
    sample_count = int(data.get("sample_count") or 0)
    confidence = min(1.0, sample_count / max(min_samples, 1))
    data["confidence"] = round(confidence, 3)
    data["is_low_sample"] = sample_count < min_samples
    return data


def validate_bulk_circuit_record(conn: sqlite3.Connection, rec: CircuitCreate) -> list[str]:
    errors: list[str] = []
    values = rec.model_dump()

    required_fields = ["circuit_id", "algorithm", "backend", "shots", "circuit_fidelity", "success_rate"]
    for field in required_fields:
        value = values.get(field)
        if value is None or (isinstance(value, str) and not value.strip()):
            errors.append(f"missing required field '{field}'")

    if values.get("shots") is not None and int(values["shots"]) <= 0:
        errors.append("shots must be > 0")

    for metric in ["circuit_fidelity", "success_rate"]:
        metric_value = values.get(metric)
        if metric_value is not None and not (0.0 <= float(metric_value) <= 1.0):
            errors.append(f"{metric} must be in [0, 1]")

    backend = values.get("backend")
    if backend:
        backend_row = conn.execute(
            """SELECT 1
               FROM circuits
               WHERE LOWER(backend) = ?
               LIMIT 1""",
            [str(backend).lower()],
        ).fetchone()
        if not backend_row:
            errors.append(f"unknown backend '{backend}'")

    return errors


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
    experiment_date_start: Optional[str] = None,
    experiment_date_end: Optional[str] = None,
    include_deleted: bool = False,
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
    if experiment_date_start:
        where_clauses.append("experiment_date >= ?")
        params.append(experiment_date_start)
    if experiment_date_end:
        where_clauses.append("experiment_date <= ?")
        params.append(experiment_date_end)
    if not include_deleted:
        where_clauses.append("COALESCE(is_deleted, 0) = 0")

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
        circuit = conn.execute(
            "SELECT * FROM circuits WHERE UPPER(circuit_id) = UPPER(?) AND COALESCE(is_deleted, 0) = 0",
            [circuit_id],
        ).fetchone()
        if not circuit:
            raise HTTPException(status_code=404, detail=f"Circuit '{circuit_id}' not found")
        canonical_circuit_id = circuit["circuit_id"]
        qubits = conn.execute("SELECT * FROM qubits WHERE circuit_id = ?", [canonical_circuit_id]).fetchone()
        gates = conn.execute("SELECT * FROM gates WHERE circuit_id = ?", [canonical_circuit_id]).fetchone()
        results = conn.execute("SELECT * FROM results WHERE circuit_id = ?", [canonical_circuit_id]).fetchone()
        noise = conn.execute("SELECT * FROM noise_models WHERE circuit_id = ?", [canonical_circuit_id]).fetchone()

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
            circuit_insert_payload(data),
        )
        add_audit_log(
            conn,
            table_name="circuits",
            record_id=data.circuit_id,
            operation="CREATE",
            changed_by="api",
            details={"source": "create_circuit"},
        )
    return {"message": "Circuit created", "circuit_id": data.circuit_id}


@app.patch("/circuits/{circuit_id}", tags=["Circuits"])
def update_circuit(circuit_id: str, data: CircuitUpdate):
    """Partially update a circuit record."""
    updates = {k: v for k, v in data.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields provided to update")

    set_clause = ", ".join(f"{k} = ?" for k in updates)
    params = list(updates.values()) + [circuit_id]

    with get_db() as conn:
        existing = conn.execute(
            "SELECT 1 FROM circuits WHERE circuit_id = ? AND COALESCE(is_deleted, 0) = 0",
            [circuit_id],
        ).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail=f"Circuit '{circuit_id}' not found")
        conn.execute(f"UPDATE circuits SET {set_clause} WHERE circuit_id = ?", params)
        add_audit_log(
            conn,
            table_name="circuits",
            record_id=circuit_id,
            operation="UPDATE",
            changed_by="api",
            details={"updated_fields": list(updates.keys())},
        )

    return {"message": "Circuit updated", "circuit_id": circuit_id, "updated_fields": list(updates.keys())}


@app.delete("/circuits/{circuit_id}", tags=["Circuits"])
def delete_circuit(circuit_id: str, payload: Optional[SoftDeleteRequest] = None):
    """Soft-delete a circuit so it can be restored later."""
    deleted_by = payload.deleted_by if payload else None
    with get_db() as conn:
        existing = conn.execute(
            "SELECT 1 FROM circuits WHERE circuit_id = ? AND COALESCE(is_deleted, 0) = 0",
            [circuit_id],
        ).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail=f"Circuit '{circuit_id}' not found")

        conn.execute(
            """UPDATE circuits
               SET is_deleted = 1, deleted_at = ?, deleted_by = ?
               WHERE circuit_id = ?""",
            [datetime.now(timezone.utc).isoformat(), deleted_by, circuit_id],
        )
        add_audit_log(
            conn,
            table_name="circuits",
            record_id=circuit_id,
            operation="SOFT_DELETE",
            changed_by=deleted_by,
            details={"source": "delete_circuit"},
        )

    return {"message": f"Circuit '{circuit_id}' soft-deleted"}


@app.post("/circuits/{circuit_id}/restore", tags=["Circuits"])
def restore_circuit(circuit_id: str, payload: Optional[RestoreCircuitRequest] = None):
    restored_by = payload.restored_by if payload else None
    with get_db() as conn:
        existing = conn.execute(
            "SELECT 1 FROM circuits WHERE circuit_id = ? AND COALESCE(is_deleted, 0) = 1",
            [circuit_id],
        ).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail=f"Circuit '{circuit_id}' is not deleted or does not exist")

        conn.execute(
            """UPDATE circuits
               SET is_deleted = 0, deleted_at = NULL, deleted_by = NULL
               WHERE circuit_id = ?""",
            [circuit_id],
        )
        add_audit_log(
            conn,
            table_name="circuits",
            record_id=circuit_id,
            operation="RESTORE",
            changed_by=restored_by,
            details={"source": "restore_circuit"},
        )

    return {"message": f"Circuit '{circuit_id}' restored"}


@app.delete("/circuits/{circuit_id}/hard", tags=["Circuits"])
def hard_delete_circuit(circuit_id: str):
    """Permanently delete a circuit and all its related rows."""
    with get_db() as conn:
        existing = conn.execute("SELECT 1 FROM circuits WHERE circuit_id = ?", [circuit_id]).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail=f"Circuit '{circuit_id}' not found")
        for table in ["qubits", "gates", "results", "noise_models", "circuits"]:
            conn.execute(f"DELETE FROM {table} WHERE circuit_id = ?", [circuit_id])

        add_audit_log(
            conn,
            table_name="circuits",
            record_id=circuit_id,
            operation="HARD_DELETE",
            changed_by="api",
            details={"source": "hard_delete_circuit"},
        )

    return {"message": f"Circuit '{circuit_id}' and all related records permanently deleted"}


# ── SEARCH ─────────────────────────────────────────────────────────────────────
@app.get("/search", tags=["Search"], response_model=SearchResponse)
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
               WHERE COALESCE(is_deleted, 0) = 0
                 AND (
                      LOWER(circuit_id) LIKE ?
                  OR LOWER(circuit_name) LIKE ?
                  OR LOWER(algorithm) LIKE ?
                  OR LOWER(category) LIKE ?
                  OR LOWER(backend) LIKE ?)
               LIMIT ?""",
            [term, term, term, term, term, limit]
        ).fetchall()
    return {"query": q, "count": len(rows), "results": [row_to_dict(r) for r in rows]}


# ── STATS ──────────────────────────────────────────────────────────────────────
@app.get("/stats", tags=["Statistics"], response_model=StatsResponse)
def get_stats():
    """Aggregate statistics for dashboard."""
    with get_db() as conn:
        total = conn.execute("SELECT COUNT(*) FROM circuits WHERE COALESCE(is_deleted, 0) = 0").fetchone()[0]
        avg_fidelity = conn.execute(
            "SELECT ROUND(AVG(circuit_fidelity),4) FROM circuits WHERE COALESCE(is_deleted, 0) = 0"
        ).fetchone()[0]
        avg_success = conn.execute(
            "SELECT ROUND(AVG(success_rate),4) FROM circuits WHERE COALESCE(is_deleted, 0) = 0"
        ).fetchone()[0]

        top_algorithms = conn.execute(
                """SELECT algorithm, COUNT(*) as count
                    FROM circuits
                    WHERE COALESCE(is_deleted, 0) = 0
                    GROUP BY algorithm ORDER BY count DESC LIMIT 10"""
        ).fetchall()

        top_backends = conn.execute(
                """SELECT backend, COUNT(*) as count
                    FROM circuits
                    WHERE COALESCE(is_deleted, 0) = 0
                    GROUP BY backend ORDER BY count DESC LIMIT 10"""
        ).fetchall()

        categories = conn.execute(
                """SELECT category, COUNT(*) as count
                    FROM circuits
                    WHERE COALESCE(is_deleted, 0) = 0
                    GROUP BY category ORDER BY count DESC"""
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
             FROM circuits
             WHERE COALESCE(is_deleted, 0) = 0
             GROUP BY range ORDER BY range DESC"""
        ).fetchall()

        sim_vs_real = conn.execute(
                """SELECT is_simulator, COUNT(*) as count
                    FROM circuits
                    WHERE COALESCE(is_deleted, 0) = 0
                    GROUP BY is_simulator"""
        ).fetchall()

        monthly = conn.execute(
            """SELECT strftime('%Y-%m', experiment_date) as month, COUNT(*) as count
             FROM circuits
             WHERE experiment_date IS NOT NULL AND COALESCE(is_deleted, 0) = 0
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
             WHERE COALESCE(c.is_deleted, 0) = 0
               ORDER BY c.circuit_fidelity DESC
               LIMIT ?""", [limit]
        ).fetchall()
    return {"data": [row_to_dict(r) for r in rows]}


# ── DISTINCT VALUES FOR FILTERS ────────────────────────────────────────────────
@app.get("/meta/algorithms", tags=["Meta"])
def get_algorithms():
    with get_db() as conn:
        rows = conn.execute(
            "SELECT DISTINCT algorithm FROM circuits WHERE COALESCE(is_deleted, 0) = 0 ORDER BY algorithm"
        ).fetchall()
    return [r[0] for r in rows if r[0]]


@app.get("/meta/backends", tags=["Meta"])
def get_backends():
    with get_db() as conn:
        rows = conn.execute(
            "SELECT DISTINCT backend FROM circuits WHERE COALESCE(is_deleted, 0) = 0 ORDER BY backend"
        ).fetchall()
    return [r[0] for r in rows if r[0]]


@app.get("/meta/categories", tags=["Meta"])
def get_categories():
    with get_db() as conn:
        rows = conn.execute(
            "SELECT DISTINCT category FROM circuits WHERE COALESCE(is_deleted, 0) = 0 ORDER BY category"
        ).fetchall()
    return [r[0] for r in rows if r[0]]


# ── DBMS ENHANCEMENTS ─────────────────────────────────────────────────────────
@app.post("/bulk/circuits", tags=["Bulk"], response_model=BulkCircuitUploadResponse)
def bulk_upload_circuits(payload: BulkCircuitUploadRequest):
    if not payload.records:
        raise HTTPException(status_code=400, detail="records cannot be empty")

    inserted = 0
    updated = 0
    skipped = 0
    failed = 0
    errors: List[dict] = []

    updatable_fields = [
        "job_id", "circuit_name", "algorithm", "category", "backend", "architecture",
        "quantum_volume", "experiment_date", "qiskit_version", "is_simulator",
        "optimization_level", "transpiler_pass", "connectivity", "clops", "shots",
        "execution_time_ms", "mitigation_technique", "circuit_fidelity", "success_rate",
        "dominant_state",
    ]

    with get_db() as conn:
        for idx, rec in enumerate(payload.records, start=1):
            try:
                row_errors = validate_bulk_circuit_record(conn, rec)
                if row_errors:
                    failed += 1
                    errors.append({"row": idx, "circuit_id": rec.circuit_id, "error": "; ".join(row_errors)})
                    continue

                existing = conn.execute(
                    "SELECT 1 FROM circuits WHERE circuit_id = ?",
                    [rec.circuit_id],
                ).fetchone()

                if existing and payload.conflict_strategy == "skip":
                    skipped += 1
                    continue

                if existing and payload.conflict_strategy == "error":
                    failed += 1
                    errors.append({"row": idx, "circuit_id": rec.circuit_id, "error": "already exists"})
                    continue

                if existing and payload.conflict_strategy == "update":
                    values_map = rec.model_dump()
                    set_clause = ", ".join(f"{k} = ?" for k in updatable_fields)
                    conn.execute(
                        f"UPDATE circuits SET {set_clause}, is_deleted = 0, deleted_at = NULL, deleted_by = NULL WHERE circuit_id = ?",
                        [values_map.get(k) for k in updatable_fields] + [rec.circuit_id],
                    )
                    updated += 1
                    add_audit_log(
                        conn,
                        table_name="circuits",
                        record_id=rec.circuit_id,
                        operation="BULK_UPDATE",
                        changed_by=payload.created_by,
                        details={"conflict_strategy": payload.conflict_strategy},
                    )
                    continue

                conn.execute(
                    """INSERT INTO circuits (circuit_id, job_id, circuit_name, algorithm, category,
                       backend, architecture, quantum_volume, experiment_date, qiskit_version,
                       is_simulator, optimization_level, transpiler_pass, connectivity,
                       clops, shots, execution_time_ms, mitigation_technique,
                       circuit_fidelity, success_rate, dominant_state)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    circuit_insert_payload(rec),
                )
                inserted += 1
                add_audit_log(
                    conn,
                    table_name="circuits",
                    record_id=rec.circuit_id,
                    operation="BULK_INSERT",
                    changed_by=payload.created_by,
                    details={"conflict_strategy": payload.conflict_strategy},
                )
            except Exception as exc:
                failed += 1
                errors.append({"row": idx, "circuit_id": rec.circuit_id, "error": str(exc)})

    return {
        "received": len(payload.records),
        "inserted": inserted,
        "updated": updated,
        "skipped": skipped,
        "failed": failed,
        "errors": errors,
    }


@app.post("/filters", tags=["Filters"], response_model=SavedFilterResponse, status_code=201)
def create_saved_filter(payload: SavedFilterCreate):
    params = {
        "algorithm": payload.algorithm,
        "backend": payload.backend,
        "category": payload.category,
        "min_fidelity": payload.min_fidelity,
        "max_fidelity": payload.max_fidelity,
        "is_simulator": payload.is_simulator,
        "experiment_date_start": payload.experiment_date_start,
        "experiment_date_end": payload.experiment_date_end,
    }

    created_at = datetime.now(timezone.utc).isoformat()
    with get_db() as conn:
        cur = conn.execute(
            """INSERT INTO saved_filters (name, params_json, created_at, created_by)
               VALUES (?, ?, ?, ?)""",
            [payload.name.strip(), json.dumps(params), created_at, payload.created_by],
        )
        filter_id = cur.lastrowid

    return {
        "filter_id": filter_id,
        "name": payload.name.strip(),
        "created_at": created_at,
        "created_by": payload.created_by,
        "params": params,
    }


@app.get("/filters", tags=["Filters"])
def list_saved_filters(limit: int = Query(50, ge=1, le=500)):
    with get_db() as conn:
        rows = conn.execute(
            """SELECT filter_id, name, params_json, created_at, created_by
               FROM saved_filters
               ORDER BY created_at DESC
               LIMIT ?""",
            [limit],
        ).fetchall()

    data = []
    for row in rows:
        item = row_to_dict(row)
        item["params"] = json.loads(item.pop("params_json"))
        data.append(item)
    return {"count": len(data), "data": data}


@app.get("/filters/{filter_id}/circuits", tags=["Filters"])
def apply_saved_filter(filter_id: int, page: int = Query(1, ge=1), limit: int = Query(20, ge=1, le=200)):
    with get_db() as conn:
        row = conn.execute(
            "SELECT params_json FROM saved_filters WHERE filter_id = ?",
            [filter_id],
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Saved filter '{filter_id}' not found")

        params = json.loads(row[0])
        where_clauses = ["COALESCE(is_deleted, 0) = 0"]
        query_params = []

        if params.get("algorithm"):
            where_clauses.append("LOWER(algorithm) LIKE ?")
            query_params.append(f"%{params['algorithm'].lower()}%")
        if params.get("backend"):
            where_clauses.append("LOWER(backend) LIKE ?")
            query_params.append(f"%{params['backend'].lower()}%")
        if params.get("category"):
            where_clauses.append("LOWER(category) LIKE ?")
            query_params.append(f"%{params['category'].lower()}%")
        if params.get("min_fidelity") is not None:
            where_clauses.append("circuit_fidelity >= ?")
            query_params.append(params["min_fidelity"])
        if params.get("max_fidelity") is not None:
            where_clauses.append("circuit_fidelity <= ?")
            query_params.append(params["max_fidelity"])
        if params.get("is_simulator") is not None:
            where_clauses.append("is_simulator = ?")
            query_params.append(params["is_simulator"])
        if params.get("experiment_date_start"):
            where_clauses.append("experiment_date >= ?")
            query_params.append(params["experiment_date_start"])
        if params.get("experiment_date_end"):
            where_clauses.append("experiment_date <= ?")
            query_params.append(params["experiment_date_end"])

        where_sql = "WHERE " + " AND ".join(where_clauses)
        offset = (page - 1) * limit

        total = conn.execute(f"SELECT COUNT(*) FROM circuits {where_sql}", query_params).fetchone()[0]
        rows = conn.execute(
            f"SELECT * FROM circuits {where_sql} LIMIT ? OFFSET ?",
            query_params + [limit, offset],
        ).fetchall()

    return {
        "filter_id": filter_id,
        "total": total,
        "page": page,
        "limit": limit,
        "pages": (total + limit - 1) // limit,
        "data": [row_to_dict(r) for r in rows],
    }


@app.get("/audit/logs", tags=["Audit"])
def get_audit_logs(
    table_name: Optional[str] = None,
    record_id: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500),
):
    where = []
    params = []

    if table_name:
        where.append("table_name = ?")
        params.append(table_name)
    if record_id:
        where.append("record_id = ?")
        params.append(record_id)

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    with get_db() as conn:
        rows = conn.execute(
            f"""SELECT id, table_name, record_id, operation, changed_by, changed_at, details_json
                FROM audit_logs
                {where_sql}
                ORDER BY changed_at DESC
                LIMIT ?""",
            params + [limit],
        ).fetchall()

    data = []
    for row in rows:
        item = row_to_dict(row)
        item["details"] = json.loads(item.pop("details_json") or "{}")
        data.append(item)
    return {"count": len(data), "data": data}


@app.get("/quality/report", tags=["Quality"])
def data_quality_report():
    with get_db() as conn:
        total = conn.execute("SELECT COUNT(*) FROM circuits").fetchone()[0]
        deleted = conn.execute("SELECT COUNT(*) FROM circuits WHERE COALESCE(is_deleted, 0) = 1").fetchone()[0]
        out_of_range = conn.execute(
            """SELECT COUNT(*) FROM circuits
               WHERE (circuit_fidelity IS NOT NULL AND (circuit_fidelity < 0 OR circuit_fidelity > 1))
                  OR (success_rate IS NOT NULL AND (success_rate < 0 OR success_rate > 1))"""
        ).fetchone()[0]

        orphan_qubits = conn.execute(
            """SELECT COUNT(*)
               FROM qubits q
               LEFT JOIN circuits c ON q.circuit_id = c.circuit_id
               WHERE c.circuit_id IS NULL"""
        ).fetchone()[0]
        orphan_gates = conn.execute(
            """SELECT COUNT(*)
               FROM gates g
               LEFT JOIN circuits c ON g.circuit_id = c.circuit_id
               WHERE c.circuit_id IS NULL"""
        ).fetchone()[0]
        orphan_results = conn.execute(
            """SELECT COUNT(*)
               FROM results r
               LEFT JOIN circuits c ON r.circuit_id = c.circuit_id
               WHERE c.circuit_id IS NULL"""
        ).fetchone()[0]
        orphan_noise = conn.execute(
            """SELECT COUNT(*)
               FROM noise_models n
               LEFT JOIN circuits c ON n.circuit_id = c.circuit_id
               WHERE c.circuit_id IS NULL"""
        ).fetchone()[0]

        null_specs = {
            "circuits": ["algorithm", "backend", "circuit_fidelity", "success_rate", "shots", "experiment_date"],
            "qubits": ["num_qubits_used", "t1_relaxation_us", "t2_decoherence_us", "readout_error"],
            "gates": ["total_gate_count", "circuit_depth", "cnot_count"],
            "results": ["success_rate", "circuit_fidelity", "hellinger_fidelity"],
            "noise_models": ["noise_model", "single_qubit_error_rate", "two_qubit_error_rate", "total_circuit_error"],
        }

        null_profile = {}
        high_null_columns = []
        for table, cols in null_specs.items():
            table_total = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            rates = {}
            for col in cols:
                null_count = conn.execute(
                    f"SELECT COUNT(*) FROM {table} WHERE {col} IS NULL"
                ).fetchone()[0]
                rate = (null_count / table_total) if table_total else 0.0
                rates[col] = {
                    "null_count": null_count,
                    "null_ratio": round(rate, 4),
                }
                if rate >= 0.30:
                    high_null_columns.append(
                        {
                            "table": table,
                            "column": col,
                            "null_count": null_count,
                            "null_ratio": round(rate, 4),
                        }
                    )
            null_profile[table] = {
                "row_count": table_total,
                "columns": rates,
            }

    return {
        "total_circuits": total,
        "soft_deleted_circuits": deleted,
        "out_of_range_metrics": out_of_range,
        "orphan_rows": {
            "qubits": orphan_qubits,
            "gates": orphan_gates,
            "results": orphan_results,
            "noise_models": orphan_noise,
        },
        "null_profile": null_profile,
        "high_null_columns": high_null_columns,
    }


@app.get("/quality/lineage", tags=["Quality"])
def data_quality_lineage():
    checks = [
        {
            "name": "Total circuits",
            "sqlite": "SELECT COUNT(*) FROM circuits;",
            "postgresql": "SELECT COUNT(*) FROM circuits;",
        },
        {
            "name": "Soft-deleted circuits",
            "sqlite": "SELECT COUNT(*) FROM circuits WHERE COALESCE(is_deleted, 0) = 1;",
            "postgresql": "SELECT COUNT(*) FROM circuits WHERE COALESCE(is_deleted, 0) = 1;",
        },
        {
            "name": "Out-of-range fidelity/success",
            "sqlite": """SELECT COUNT(*) FROM circuits
WHERE (circuit_fidelity IS NOT NULL AND (circuit_fidelity < 0 OR circuit_fidelity > 1))
   OR (success_rate IS NOT NULL AND (success_rate < 0 OR success_rate > 1));""",
            "postgresql": """SELECT COUNT(*) FROM circuits
WHERE (circuit_fidelity IS NOT NULL AND (circuit_fidelity < 0 OR circuit_fidelity > 1))
   OR (success_rate IS NOT NULL AND (success_rate < 0 OR success_rate > 1));""",
        },
        {
            "name": "Orphan rows (example: qubits)",
            "sqlite": """SELECT COUNT(*)
FROM qubits q
LEFT JOIN circuits c ON q.circuit_id = c.circuit_id
WHERE c.circuit_id IS NULL;""",
            "postgresql": """SELECT COUNT(*)
FROM qubits q
LEFT JOIN circuits c ON q.circuit_id = c.circuit_id
WHERE c.circuit_id IS NULL;""",
        },
        {
            "name": "Null count per column (pattern)",
            "sqlite": "SELECT COUNT(*) FROM <table_name> WHERE <column_name> IS NULL;",
            "postgresql": "SELECT COUNT(*) FROM <table_name> WHERE <column_name> IS NULL;",
        },
    ]

    sqlite_test_queries = [
        {
            "title": "Total circuits",
            "sql": "SELECT COUNT(*) AS total_circuits FROM circuits;",
        },
        {
            "title": "Soft-deleted circuits",
            "sql": "SELECT COUNT(*) AS soft_deleted FROM circuits WHERE COALESCE(is_deleted, 0) = 1;",
        },
        {
            "title": "Rows with invalid fidelity/success",
            "sql": """SELECT circuit_id, circuit_fidelity, success_rate
FROM circuits
WHERE (circuit_fidelity IS NOT NULL AND (circuit_fidelity < 0 OR circuit_fidelity > 1))
   OR (success_rate IS NOT NULL AND (success_rate < 0 OR success_rate > 1))
LIMIT 50;""",
        },
        {
            "title": "Orphan rows by table",
            "sql": """SELECT 'qubits' AS table_name, COUNT(*) AS orphan_rows
FROM qubits q LEFT JOIN circuits c ON q.circuit_id = c.circuit_id
WHERE c.circuit_id IS NULL
UNION ALL
SELECT 'gates' AS table_name, COUNT(*) AS orphan_rows
FROM gates g LEFT JOIN circuits c ON g.circuit_id = c.circuit_id
WHERE c.circuit_id IS NULL
UNION ALL
SELECT 'results' AS table_name, COUNT(*) AS orphan_rows
FROM results r LEFT JOIN circuits c ON r.circuit_id = c.circuit_id
WHERE c.circuit_id IS NULL
UNION ALL
SELECT 'noise_models' AS table_name, COUNT(*) AS orphan_rows
FROM noise_models n LEFT JOIN circuits c ON n.circuit_id = c.circuit_id
WHERE c.circuit_id IS NULL;""",
        },
        {
            "title": "High-null columns in circuits",
            "sql": """SELECT
    ROUND(100.0 * SUM(CASE WHEN algorithm IS NULL THEN 1 ELSE 0 END) / COUNT(*), 2) AS algorithm_null_pct,
    ROUND(100.0 * SUM(CASE WHEN backend IS NULL THEN 1 ELSE 0 END) / COUNT(*), 2) AS backend_null_pct,
    ROUND(100.0 * SUM(CASE WHEN circuit_fidelity IS NULL THEN 1 ELSE 0 END) / COUNT(*), 2) AS fidelity_null_pct,
    ROUND(100.0 * SUM(CASE WHEN success_rate IS NULL THEN 1 ELSE 0 END) / COUNT(*), 2) AS success_null_pct
FROM circuits;""",
        },
    ]

    postgresql_test_queries = [
        {
            "title": "Total circuits",
            "sql": "SELECT COUNT(*) AS total_circuits FROM circuits;",
        },
        {
            "title": "Soft-deleted circuits",
            "sql": "SELECT COUNT(*) AS soft_deleted FROM circuits WHERE COALESCE(is_deleted, 0) = 1;",
        },
        {
            "title": "Rows with invalid fidelity/success",
            "sql": """SELECT circuit_id, circuit_fidelity, success_rate
FROM circuits
WHERE (circuit_fidelity IS NOT NULL AND (circuit_fidelity < 0 OR circuit_fidelity > 1))
   OR (success_rate IS NOT NULL AND (success_rate < 0 OR success_rate > 1))
LIMIT 50;""",
        },
        {
            "title": "Orphan rows by table",
            "sql": """SELECT 'qubits' AS table_name, COUNT(*) AS orphan_rows
FROM qubits q LEFT JOIN circuits c ON q.circuit_id = c.circuit_id
WHERE c.circuit_id IS NULL
UNION ALL
SELECT 'gates' AS table_name, COUNT(*) AS orphan_rows
FROM gates g LEFT JOIN circuits c ON g.circuit_id = c.circuit_id
WHERE c.circuit_id IS NULL
UNION ALL
SELECT 'results' AS table_name, COUNT(*) AS orphan_rows
FROM results r LEFT JOIN circuits c ON r.circuit_id = c.circuit_id
WHERE c.circuit_id IS NULL
UNION ALL
SELECT 'noise_models' AS table_name, COUNT(*) AS orphan_rows
FROM noise_models n LEFT JOIN circuits c ON n.circuit_id = c.circuit_id
WHERE c.circuit_id IS NULL;""",
        },
        {
            "title": "High-null columns in circuits",
            "sql": """SELECT
    ROUND(100.0 * SUM(CASE WHEN algorithm IS NULL THEN 1 ELSE 0 END) / COUNT(*), 2) AS algorithm_null_pct,
    ROUND(100.0 * SUM(CASE WHEN backend IS NULL THEN 1 ELSE 0 END) / COUNT(*), 2) AS backend_null_pct,
    ROUND(100.0 * SUM(CASE WHEN circuit_fidelity IS NULL THEN 1 ELSE 0 END) / COUNT(*), 2) AS fidelity_null_pct,
    ROUND(100.0 * SUM(CASE WHEN success_rate IS NULL THEN 1 ELSE 0 END) / COUNT(*), 2) AS success_null_pct
FROM circuits;""",
        },
    ]

    return {
        "source_database": {
            "engine": "sqlite",
            "driver": "sqlite3",
            "path": DB_PATH,
        },
        "target_database": {
            "engine": "postgresql",
            "note": "Equivalent SQL shown for migration/readiness documentation.",
        },
        "quality_checks": checks,
        "test_queries": {
            "sqlite": sqlite_test_queries,
            "postgresql": postgresql_test_queries,
        },
    }


@app.post("/quality/query/execute", tags=["Quality"])
def execute_quality_query(payload: dict):
    sql = str(payload.get("sql") or "").strip()
    limit = int(payload.get("limit") or 200)

    if not sql:
        raise HTTPException(status_code=400, detail="SQL query is required")
    if limit < 1 or limit > 1000:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 1000")

    sql_lower = sql.lower().lstrip()
    if not (sql_lower.startswith("select") or sql_lower.startswith("with")):
        raise HTTPException(status_code=400, detail="Only read-only SELECT/WITH queries are allowed")

    blocked_tokens = [
        " insert ",
        " update ",
        " delete ",
        " drop ",
        " alter ",
        " create ",
        " replace ",
        " truncate ",
        " attach ",
        " detach ",
        " pragma ",
        " vacuum ",
    ]
    sql_scan = f" {sql_lower} "
    if any(token in sql_scan for token in blocked_tokens):
        raise HTTPException(status_code=400, detail="Potentially destructive SQL is not allowed")

    try:
        with get_db() as conn:
            cursor = conn.execute(sql)
            columns = [desc[0] for desc in (cursor.description or [])]
            fetched = cursor.fetchmany(limit + 1)
    except sqlite3.Error as exc:
        raise HTTPException(status_code=400, detail=f"SQL error: {exc}")

    is_truncated = len(fetched) > limit
    rows = fetched[:limit]
    row_dicts = [dict(zip(columns, row)) for row in rows]

    return {
        "columns": columns,
        "rows": row_dicts,
        "row_count": len(row_dicts),
        "truncated": is_truncated,
        "limit": limit,
    }


@app.get("/benchmark/compare", tags=["Benchmark"])
def benchmark_compare(
    algorithm_a: str,
    algorithm_b: str,
    backend: Optional[str] = None,
):
    with get_db() as conn:
        filters = ["COALESCE(c.is_deleted, 0) = 0", "LOWER(c.algorithm) IN (?, ?)"]
        params = [algorithm_a.lower(), algorithm_b.lower()]
        if backend:
            filters.append("LOWER(c.backend) = ?")
            params.append(backend.lower())

        where_sql = " AND ".join(filters)
        rows = conn.execute(
            f"""SELECT c.algorithm,
                       COUNT(*) AS runs,
                       ROUND(AVG(c.circuit_fidelity), 4) AS avg_fidelity,
                       ROUND(AVG(c.success_rate), 4) AS avg_success_rate,
                       ROUND(AVG(c.execution_time_ms), 3) AS avg_execution_time_ms,
                       ROUND(AVG(g.circuit_depth), 2) AS avg_depth,
                       ROUND(AVG(n.total_circuit_error), 6) AS avg_total_error
                FROM circuits c
                LEFT JOIN gates g ON c.circuit_id = g.circuit_id
                LEFT JOIN noise_models n ON c.circuit_id = n.circuit_id
                WHERE {where_sql}
                GROUP BY c.algorithm""",
            params,
        ).fetchall()

    return {"algorithm_a": algorithm_a, "algorithm_b": algorithm_b, "backend": backend, "data": [row_to_dict(r) for r in rows]}


# ── QUANTUM-SPECIFIC FEATURES ────────────────────────────────────────────────
@app.get("/quantum/noise-aware-score", tags=["Quantum"])
def noise_aware_scores(limit: int = Query(20, ge=1, le=200)):
    with get_db() as conn:
        rows = conn.execute(
            """SELECT c.circuit_id,
                      c.algorithm,
                      c.backend,
                      c.circuit_fidelity,
                      c.success_rate,
                      g.circuit_depth,
                      n.total_circuit_error,
                      ROUND(
                        (COALESCE(c.circuit_fidelity, 0) * 0.45)
                        + (COALESCE(c.success_rate, 0) * 0.35)
                        - (MIN(COALESCE(g.circuit_depth, 0) / 2000.0, 1.0) * 0.10)
                        - (COALESCE(n.total_circuit_error, 0) * 0.10),
                        6
                      ) AS noise_aware_score
               FROM circuits c
               LEFT JOIN gates g ON c.circuit_id = g.circuit_id
               LEFT JOIN noise_models n ON c.circuit_id = n.circuit_id
               WHERE COALESCE(c.is_deleted, 0) = 0
               ORDER BY noise_aware_score DESC
               LIMIT ?""",
            [limit],
        ).fetchall()

    return {"count": len(rows), "data": [row_to_dict(r) for r in rows]}


@app.get("/quantum/mitigation/effectiveness", tags=["Quantum"])
def mitigation_effectiveness(limit: int = Query(100, ge=1, le=500)):
    with get_db() as conn:
        rows = conn.execute(
            """SELECT c.backend,
                      c.algorithm,
                      c.mitigation_technique,
                      COUNT(*) AS runs,
                      ROUND(AVG(c.circuit_fidelity), 4) AS avg_fidelity,
                      ROUND(AVG(c.success_rate), 4) AS avg_success_rate,
                      ROUND(AVG(n.total_circuit_error), 6) AS avg_total_error
               FROM circuits c
               LEFT JOIN noise_models n ON c.circuit_id = n.circuit_id
               WHERE COALESCE(c.is_deleted, 0) = 0
               GROUP BY c.backend, c.algorithm, c.mitigation_technique
               HAVING COUNT(*) >= 3
               ORDER BY avg_fidelity DESC, avg_success_rate DESC
               LIMIT ?""",
            [limit],
        ).fetchall()

    return {"count": len(rows), "data": [row_to_dict(r) for r in rows]}


@app.post("/quantum/hardware/recommend", tags=["Quantum"])
def recommend_hardware(payload: HardwareRecommendRequest):
    depth_cap = max(int(payload.circuit_depth * 1.5), payload.circuit_depth + 20)
    with get_db() as conn:
        rows = conn.execute(
            """SELECT c.backend,
                      COUNT(*) AS matched_runs,
                      ROUND(AVG(c.circuit_fidelity), 4) AS avg_fidelity,
                      ROUND(AVG(c.success_rate), 4) AS avg_success_rate,
                      ROUND(AVG(n.total_circuit_error), 6) AS avg_total_error,
                      ROUND(AVG(g.circuit_depth), 2) AS avg_depth,
                      ROUND(
                        (AVG(COALESCE(c.circuit_fidelity, 0)) * 0.5)
                        + (AVG(COALESCE(c.success_rate, 0)) * 0.4)
                        - (AVG(COALESCE(n.total_circuit_error, 0)) * 0.1),
                        6
                      ) AS recommendation_score
               FROM circuits c
               JOIN qubits q ON c.circuit_id = q.circuit_id
               JOIN gates g ON c.circuit_id = g.circuit_id
               LEFT JOIN noise_models n ON c.circuit_id = n.circuit_id
               WHERE COALESCE(c.is_deleted, 0) = 0
                 AND q.num_qubits_used >= ?
                 AND q.num_qubits_used <= ?
                 AND g.circuit_depth <= ?
               GROUP BY c.backend
               HAVING COUNT(*) >= ?
               ORDER BY recommendation_score DESC""",
            [
                max(payload.num_qubits_used - 4, 1),
                payload.num_qubits_used + 8,
                depth_cap,
                payload.min_samples,
            ],
        ).fetchall()

    return {
        "input": payload.model_dump(),
        "count": len(rows),
        "recommended_backends": [row_to_dict(r) for r in rows],
    }


@app.post("/quantum/what-if", tags=["Quantum"])
def quantum_what_if(payload: QuantumWhatIfRequest):
    with get_db() as conn:
        base_profile = _fetch_base_profile(conn, payload)

        baseline_profile = {
            "algorithm": base_profile.get("algorithm"),
            "backend": base_profile.get("backend"),
            "mitigation_technique": base_profile.get("mitigation_technique"),
            "optimization_level": base_profile.get("optimization_level"),
            "shots": base_profile.get("shots"),
            "circuit_depth": base_profile.get("circuit_depth"),
            "num_qubits_used": base_profile.get("num_qubits_used"),
            "total_circuit_error": base_profile.get("total_circuit_error"),
        }

        scenario_profile = {
            "algorithm": payload.algorithm or baseline_profile.get("algorithm"),
            "backend": payload.backend,
            "mitigation_technique": payload.mitigation_technique,
            "optimization_level": payload.optimization_level,
            "shots": payload.shots,
            "circuit_depth": payload.circuit_depth,
            "num_qubits_used": payload.num_qubits_used,
            "total_circuit_error": payload.total_circuit_error,
        }

        baseline_prediction = _predict_from_profile(conn, baseline_profile, payload.min_samples)
        scenario_prediction = _predict_from_profile(conn, scenario_profile, payload.min_samples)

    base_fid = float(baseline_prediction.get("predicted_fidelity") or 0.0)
    scen_fid = float(scenario_prediction.get("predicted_fidelity") or 0.0)
    base_suc = float(baseline_prediction.get("predicted_success_rate") or 0.0)
    scen_suc = float(scenario_prediction.get("predicted_success_rate") or 0.0)

    return {
        "source_circuit_id": base_profile.get("circuit_id"),
        "baseline_profile": baseline_profile,
        "scenario_profile": scenario_profile,
        "baseline": baseline_prediction,
        "scenario": scenario_prediction,
        "delta": {
            "fidelity": round(scen_fid - base_fid, 6),
            "success_rate": round(scen_suc - base_suc, 6),
        },
    }


@app.post("/quantum/what-if/recommendations", tags=["Quantum"])
def quantum_what_if_recommendations(payload: QuantumWhatIfRecommendationRequest):
    with get_db() as conn:
        base_profile = _fetch_base_profile(conn, payload)
        baseline = _predict_from_profile(
            conn,
            {
                "algorithm": base_profile.get("algorithm"),
                "backend": base_profile.get("backend"),
                "mitigation_technique": base_profile.get("mitigation_technique"),
                "optimization_level": base_profile.get("optimization_level"),
                "shots": base_profile.get("shots"),
                "circuit_depth": base_profile.get("circuit_depth"),
                "num_qubits_used": base_profile.get("num_qubits_used"),
                "total_circuit_error": base_profile.get("total_circuit_error"),
            },
            payload.min_samples,
        )

        rows = conn.execute(
            """SELECT c.backend,
                      COALESCE(c.mitigation_technique, 'none') AS mitigation_technique,
                      c.optimization_level,
                      COUNT(*) AS sample_count,
                      ROUND(AVG(c.circuit_fidelity), 6) AS predicted_fidelity,
                      ROUND(AVG(c.success_rate), 6) AS predicted_success_rate,
                      ROUND(AVG(COALESCE(n.total_circuit_error, 0)), 6) AS avg_total_error,
                      ROUND(
                        (AVG(COALESCE(c.circuit_fidelity, 0)) * 0.55)
                        + (AVG(COALESCE(c.success_rate, 0)) * 0.35)
                        - (AVG(COALESCE(n.total_circuit_error, 0)) * 0.10),
                        6
                      ) AS recommendation_score
               FROM circuits c
               LEFT JOIN noise_models n ON c.circuit_id = n.circuit_id
               LEFT JOIN gates g ON c.circuit_id = g.circuit_id
               LEFT JOIN qubits q ON c.circuit_id = q.circuit_id
               WHERE COALESCE(c.is_deleted, 0) = 0
                 AND LOWER(c.algorithm) = ?
               GROUP BY c.backend, COALESCE(c.mitigation_technique, 'none'), c.optimization_level
               HAVING COUNT(*) >= ?
               ORDER BY recommendation_score DESC
               LIMIT 50""",
            [str(base_profile.get("algorithm")).lower(), max(3, payload.min_samples // 2)],
        ).fetchall()

    baseline_fid = float(baseline.get("predicted_fidelity") or 0.0)
    baseline_success = float(baseline.get("predicted_success_rate") or 0.0)

    recommendations = []
    for row in rows:
        item = row_to_dict(row)
        fid = float(item.get("predicted_fidelity") or 0.0)
        suc = float(item.get("predicted_success_rate") or 0.0)
        delta_fid = fid - baseline_fid
        delta_suc = suc - baseline_success
        item["delta_fidelity"] = round(delta_fid, 6)
        item["delta_success_rate"] = round(delta_suc, 6)
        item["action"] = (
            f"Use backend={item.get('backend')}, mitigation={item.get('mitigation_technique')}, "
            f"optimization_level={item.get('optimization_level')}"
        )
        recommendations.append(item)

    recommendations.sort(
        key=lambda x: (
            x.get("delta_fidelity", 0.0),
            x.get("delta_success_rate", 0.0),
            x.get("recommendation_score", 0.0),
        ),
        reverse=True,
    )

    top_k = max(1, min(payload.top_k, 10))
    return {
        "source_circuit_id": base_profile.get("circuit_id"),
        "baseline": baseline,
        "top_k": top_k,
        "recommendations": recommendations[:top_k],
    }


# ── RELATED TABLE UPDATES ──────────────────────────────────────────────────────
@app.patch("/qubits/{circuit_id}", tags=["Qubits"])
def update_qubits(circuit_id: str, data: QubitUpdate):
    updates = {k: v for k, v in data.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    with get_db() as conn:
        existing = conn.execute("SELECT 1 FROM qubits WHERE circuit_id = ?", [circuit_id]).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail=f"Qubits record for '{circuit_id}' not found")
        conn.execute(f"UPDATE qubits SET {set_clause} WHERE circuit_id = ?", list(updates.values()) + [circuit_id])
        add_audit_log(
            conn,
            table_name="qubits",
            record_id=circuit_id,
            operation="UPDATE",
            changed_by="api",
            details={"updated_fields": list(updates.keys())},
        )
    return {"message": "Qubits updated", "circuit_id": circuit_id}


@app.patch("/noise/{circuit_id}", tags=["Noise Models"])
def update_noise(circuit_id: str, data: NoiseModelUpdate):
    updates = {k: v for k, v in data.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    with get_db() as conn:
        existing = conn.execute("SELECT 1 FROM noise_models WHERE circuit_id = ?", [circuit_id]).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail=f"Noise model for '{circuit_id}' not found")
        conn.execute(f"UPDATE noise_models SET {set_clause} WHERE circuit_id = ?", list(updates.values()) + [circuit_id])
        add_audit_log(
            conn,
            table_name="noise_models",
            record_id=circuit_id,
            operation="UPDATE",
            changed_by="api",
            details={"updated_fields": list(updates.keys())},
        )
    return {"message": "Noise model updated", "circuit_id": circuit_id}


# ── CIRCUIT BUILDER ───────────────────────────────────────────────────────────
@app.post("/builder/preview", tags=["Circuit Builder"], response_model=BuilderPreviewResponse)
def builder_preview(payload: BuilderPreviewRequest):
    validate_builder_payload(payload.num_qubits, payload.steps, require_steps=False)
    preview_lines = render_builder_preview(payload.num_qubits, payload.steps)
    return {
        "num_qubits": payload.num_qubits,
        "depth": len(payload.steps),
        "gate_count": len(payload.steps),
        "preview_lines": preview_lines,
    }


@app.post("/builder/save", tags=["Circuit Builder"], response_model=BuilderSaveResponse, status_code=201)
def builder_save(payload: BuilderSaveRequest):
    validate_builder_payload(payload.num_qubits, payload.steps, require_steps=True)
    ensure_builder_tables()

    user_circuit_id = f"USR-{uuid4().hex[:10].upper()}"
    created_at = datetime.now(timezone.utc).isoformat()

    with get_db() as conn:
        conn.execute(
            """INSERT INTO user_circuits (user_circuit_id, circuit_name, num_qubits, created_at, created_by, notes)
               VALUES (?, ?, ?, ?, ?, ?)""",
            [
                user_circuit_id,
                payload.circuit_name.strip(),
                payload.num_qubits,
                created_at,
                payload.created_by,
                payload.notes,
            ],
        )

        for idx, step in enumerate(payload.steps):
            conn.execute(
                """INSERT INTO user_circuit_steps
                   (user_circuit_id, step_index, gate, target_qubit, control_qubit, parameter)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                [
                    user_circuit_id,
                    idx,
                    step.gate.upper().strip(),
                    step.target_qubit,
                    step.control_qubit,
                    step.parameter,
                ],
            )

    return {
        "message": "Custom circuit saved",
        "user_circuit_id": user_circuit_id,
        "step_count": len(payload.steps),
    }


@app.get("/builder/circuits", tags=["Circuit Builder"])
def list_builder_circuits(limit: int = Query(20, ge=1, le=200)):
    ensure_builder_tables()
    with get_db() as conn:
        rows = conn.execute(
            """SELECT user_circuit_id, circuit_name, num_qubits, created_at, created_by
               FROM user_circuits
               ORDER BY created_at DESC
               LIMIT ?""",
            [limit],
        ).fetchall()
    return {"count": len(rows), "data": [row_to_dict(r) for r in rows]}


@app.get("/builder/circuits/{user_circuit_id}", tags=["Circuit Builder"])
def get_builder_circuit(user_circuit_id: str):
    ensure_builder_tables()
    with get_db() as conn:
        circuit = conn.execute(
            """SELECT user_circuit_id, circuit_name, num_qubits, created_at, created_by, notes
               FROM user_circuits
               WHERE user_circuit_id = ?""",
            [user_circuit_id],
        ).fetchone()
        if not circuit:
            raise HTTPException(status_code=404, detail=f"Builder circuit '{user_circuit_id}' not found")

        steps = conn.execute(
            """SELECT step_index, gate, target_qubit, control_qubit, parameter
               FROM user_circuit_steps
               WHERE user_circuit_id = ?
               ORDER BY step_index ASC""",
            [user_circuit_id],
        ).fetchall()

    return {"circuit": row_to_dict(circuit), "steps": [row_to_dict(r) for r in steps]}


@app.delete("/builder/circuits/{user_circuit_id}", tags=["Circuit Builder"])
def delete_builder_circuit(user_circuit_id: str):
    ensure_builder_tables()
    with get_db() as conn:
        existing = conn.execute(
            "SELECT 1 FROM user_circuits WHERE user_circuit_id = ?",
            [user_circuit_id],
        ).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail=f"Builder circuit '{user_circuit_id}' not found")

        conn.execute("DELETE FROM user_circuits WHERE user_circuit_id = ?", [user_circuit_id])

    return {"message": f"Builder circuit '{user_circuit_id}' deleted"}