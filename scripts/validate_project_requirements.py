"""Validate course-project readiness for DBMS guidelines.

Checks:
- required files exist
- OpenAPI includes required endpoints
- API security scheme is present
- DB has required tables and minimum row counts
"""

import argparse
import sqlite3
import sys
from pathlib import Path


REQUIRED_FILES = [
    "README.md",
    "backend/main.py",
    "backend/models.py",
    "frontend/dashboard_api.py",
    "scripts/load_excel_to_sqlite.py",
    "sql/sample_queries.sql",
    "docs/ER_DIAGRAM.md",
    "docs/API_DOCUMENTATION.md",
    "docs/REPORT_TEMPLATE.md",
    "docs/REPORT_DRAFT.md",
    "docs/LIVE_DEMO_SCRIPT.md",
    "docs/PROJECT_REQUIREMENTS_TRACEABILITY.md",
]

REQUIRED_TABLES = ["circuits", "qubits", "gates", "results", "noise_models"]
REQUIRED_ENDPOINTS = [
    "/circuits",
    "/circuits/{circuit_id}",
    "/search",
    "/stats",
    "/stats/top-performers",
    "/meta/algorithms",
    "/meta/backends",
    "/meta/categories",
]


def parse_args():
    parser = argparse.ArgumentParser(description="Validate DBMS project readiness")
    parser.add_argument("--db", default="db/quantum_circuits.db", help="Path to sqlite database")
    parser.add_argument("--min-rows", type=int, default=3000, help="Minimum rows per table")
    return parser.parse_args()


def check_files(repo_root: Path):
    missing = []
    for rel in REQUIRED_FILES:
        if not (repo_root / rel).exists():
            missing.append(rel)
    return missing


def check_openapi(repo_root: Path):
    sys.path.insert(0, str(repo_root))
    from backend.main import app  # pylint: disable=import-error

    schema = app.openapi()
    paths = schema.get("paths", {})
    components = schema.get("components", {})

    missing_paths = [p for p in REQUIRED_ENDPOINTS if p not in paths]

    security_schemes = components.get("securitySchemes", {})
    has_api_key_scheme = any(
        isinstance(v, dict) and v.get("type") == "apiKey" for v in security_schemes.values()
    )

    return missing_paths, has_api_key_scheme


def check_db(db_path: Path, min_rows: int):
    if not db_path.exists():
        return {"error": f"Database file not found: {db_path}"}

    with sqlite3.connect(db_path) as conn:
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        existing_tables = {r[0] for r in cur.fetchall()}

        missing_tables = [t for t in REQUIRED_TABLES if t not in existing_tables]
        row_counts = {}
        for table in REQUIRED_TABLES:
            if table in existing_tables:
                cur.execute(f"SELECT COUNT(*) FROM {table}")
                row_counts[table] = int(cur.fetchone()[0])

        below_min = {k: v for k, v in row_counts.items() if v < min_rows}

    return {
        "missing_tables": missing_tables,
        "row_counts": row_counts,
        "below_min": below_min,
    }


def main():
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[1]

    print("Validating repository files...")
    missing_files = check_files(repo_root)

    print("Validating OpenAPI schema...")
    missing_paths, has_api_key_scheme = check_openapi(repo_root)

    print("Validating database content...")
    db_report = check_db(repo_root / args.db, args.min_rows)

    failed = False

    if missing_files:
        failed = True
        print("Missing required files:")
        for f in missing_files:
            print(f"  - {f}")

    if missing_paths:
        failed = True
        print("Missing required API paths:")
        for p in missing_paths:
            print(f"  - {p}")

    if not has_api_key_scheme:
        failed = True
        print("Missing API key security scheme in OpenAPI components.")

    if "error" in db_report:
        failed = True
        print(db_report["error"])
    else:
        if db_report["missing_tables"]:
            failed = True
            print("Missing DB tables:")
            for t in db_report["missing_tables"]:
                print(f"  - {t}")

        print("Row counts:")
        for table, count in db_report["row_counts"].items():
            print(f"  - {table}: {count}")

        if db_report["below_min"]:
            failed = True
            print(f"Tables below minimum rows ({args.min_rows}):")
            for table, count in db_report["below_min"].items():
                print(f"  - {table}: {count}")

    if failed:
        print("\nValidation: FAILED")
        raise SystemExit(1)

    print("\nValidation: PASSED")


if __name__ == "__main__":
    main()
