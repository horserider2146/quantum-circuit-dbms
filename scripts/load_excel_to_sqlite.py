"""Create and populate the SQLite database from an Excel workbook.

Usage:
    python scripts/load_excel_to_sqlite.py \
        --excel C:/path/to/quantum_circuit_database.xlsx \
        --db db/quantum_circuits.db
"""

import argparse
import sqlite3
from pathlib import Path

import pandas as pd


SHEET_TO_TABLE = {
    "Circuits": "circuits",
    "Qubits": "qubits",
    "Gates": "gates",
    "Results": "results",
    "Noise_Models": "noise_models",
}

INDEX_QUERIES = [
    "CREATE INDEX IF NOT EXISTS idx_circuits_circuit_id ON circuits(circuit_id)",
    "CREATE INDEX IF NOT EXISTS idx_circuits_algorithm ON circuits(algorithm)",
    "CREATE INDEX IF NOT EXISTS idx_circuits_backend ON circuits(backend)",
    "CREATE INDEX IF NOT EXISTS idx_circuits_experiment_date ON circuits(experiment_date)",
    "CREATE INDEX IF NOT EXISTS idx_circuits_fidelity ON circuits(circuit_fidelity)",
    "CREATE INDEX IF NOT EXISTS idx_qubits_circuit_id ON qubits(circuit_id)",
    "CREATE INDEX IF NOT EXISTS idx_gates_circuit_id ON gates(circuit_id)",
    "CREATE INDEX IF NOT EXISTS idx_results_circuit_id ON results(circuit_id)",
    "CREATE INDEX IF NOT EXISTS idx_noise_models_circuit_id ON noise_models(circuit_id)",
]


def normalize_columns(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.copy()
    frame.columns = [c.strip().lower().replace(" ", "_") for c in frame.columns]
    return frame


def parse_args():
    parser = argparse.ArgumentParser(description="Load quantum workbook into SQLite")
    parser.add_argument("--excel", required=True, help="Path to the source .xlsx file")
    parser.add_argument("--db", default="db/quantum_circuits.db", help="Path to output .db file")
    return parser.parse_args()


def main():
    args = parse_args()
    excel_path = Path(args.excel)
    db_path = Path(args.db)

    if not excel_path.exists():
        raise FileNotFoundError(f"Excel file not found: {excel_path}")

    db_path.parent.mkdir(parents=True, exist_ok=True)

    workbook = pd.read_excel(excel_path, sheet_name=None)

    with sqlite3.connect(db_path) as conn:
        for sheet_name, table_name in SHEET_TO_TABLE.items():
            if sheet_name not in workbook:
                raise KeyError(f"Missing sheet '{sheet_name}' in workbook")
            df = normalize_columns(workbook[sheet_name])
            df.to_sql(table_name, conn, if_exists="replace", index=False)
            print(f"Loaded {table_name}: {len(df):,} rows")

        for query in INDEX_QUERIES:
            conn.execute(query)

    print(f"Done. Database created at: {db_path}")


if __name__ == "__main__":
    main()
