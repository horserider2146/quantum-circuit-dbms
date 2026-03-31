"""Generate a synthetic quantum_circuits.db for local testing and demos.

This is a fallback when the original Excel dataset is not available.
"""

import argparse
import random
import sqlite3
from datetime import date, timedelta
from pathlib import Path


ALGORITHMS = ["QFT", "VQE", "QAOA", "Grover", "Shor", "QNN"]
CATEGORIES = ["optimization", "chemistry", "search", "education", "benchmark"]
BACKENDS = ["ibm_kolkata", "ibm_seattle", "ibm_torino", "ibm_kyiv", "ibm_brisbane"]
ARCHITECTURES = ["heavy-hex", "linear", "grid"]
NOISE_MODELS = ["depolarizing", "amplitude_damping", "phase_damping", "ibm_calibrated"]
MITIGATION = ["none", "TREX", "ZNE", "PEC"]
TRANSPILE = ["layout", "routing", "optimization", "scheduling"]


def parse_args():
    parser = argparse.ArgumentParser(description="Generate synthetic DB for project demos")
    parser.add_argument("--db", default="db/quantum_circuits.db", help="Output sqlite file path")
    parser.add_argument("--rows", type=int, default=5000, help="Rows per table")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    return parser.parse_args()


def create_schema(conn: sqlite3.Connection):
    conn.executescript(
        """
        DROP TABLE IF EXISTS noise_models;
        DROP TABLE IF EXISTS results;
        DROP TABLE IF EXISTS gates;
        DROP TABLE IF EXISTS qubits;
        DROP TABLE IF EXISTS circuits;

        CREATE TABLE circuits (
            circuit_id TEXT PRIMARY KEY,
            job_id TEXT,
            circuit_name TEXT,
            algorithm TEXT,
            category TEXT,
            backend TEXT,
            architecture TEXT,
            quantum_volume INTEGER,
            experiment_date TEXT,
            qiskit_version TEXT,
            is_simulator TEXT,
            optimization_level INTEGER,
            transpiler_pass TEXT,
            connectivity TEXT,
            clops REAL,
            shots INTEGER,
            execution_time_ms REAL,
            mitigation_technique TEXT,
            circuit_fidelity REAL,
            success_rate REAL,
            dominant_state TEXT
        );

        CREATE TABLE qubits (
            circuit_id TEXT PRIMARY KEY,
            num_qubits_used INTEGER,
            t1_relaxation_us REAL,
            t2_decoherence_us REAL,
            readout_error REAL,
            qubit_frequency_ghz REAL,
            coupling_strength_mhz REAL,
            crosstalk_coefficient REAL,
            leakage_rate REAL,
            FOREIGN KEY (circuit_id) REFERENCES circuits(circuit_id)
        );

        CREATE TABLE gates (
            circuit_id TEXT PRIMARY KEY,
            total_gate_count INTEGER,
            circuit_depth INTEGER,
            cnot_count INTEGER,
            h_gate_count INTEGER,
            rz_gate_count INTEGER,
            two_qubit_gates INTEGER,
            transpiled_depth INTEGER,
            two_qubit_gate_ratio REAL,
            gate_depth_ratio REAL,
            gate_cancellation_ratio REAL,
            clifford_gates INTEGER,
            FOREIGN KEY (circuit_id) REFERENCES circuits(circuit_id)
        );

        CREATE TABLE results (
            circuit_id TEXT PRIMARY KEY,
            success_rate REAL,
            circuit_fidelity REAL,
            expected_value REAL,
            measured_value REAL,
            hellinger_fidelity REAL,
            kl_divergence REAL,
            mitigation_overhead_ms REAL,
            FOREIGN KEY (circuit_id) REFERENCES circuits(circuit_id)
        );

        CREATE TABLE noise_models (
            circuit_id TEXT PRIMARY KEY,
            noise_model TEXT,
            single_qubit_error_rate REAL,
            two_qubit_error_rate REAL,
            readout_error_rate REAL,
            depolarizing_prob_1q REAL,
            depolarizing_prob_2q REAL,
            total_circuit_error REAL,
            amplitude_damping_rate REAL,
            spam_error_rate REAL,
            FOREIGN KEY (circuit_id) REFERENCES circuits(circuit_id)
        );

        CREATE INDEX idx_circuits_circuit_id ON circuits(circuit_id);
        CREATE INDEX idx_circuits_algorithm ON circuits(algorithm);
        CREATE INDEX idx_circuits_backend ON circuits(backend);
        CREATE INDEX idx_circuits_experiment_date ON circuits(experiment_date);
        CREATE INDEX idx_circuits_fidelity ON circuits(circuit_fidelity);
        CREATE INDEX idx_qubits_circuit_id ON qubits(circuit_id);
        CREATE INDEX idx_gates_circuit_id ON gates(circuit_id);
        CREATE INDEX idx_results_circuit_id ON results(circuit_id);
        CREATE INDEX idx_noise_models_circuit_id ON noise_models(circuit_id);
        """
    )


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def generate(conn: sqlite3.Connection, rows: int):
    base_date = date(2023, 1, 1)

    for i in range(1, rows + 1):
        cid = f"CIR-{i:05d}"
        algo = random.choice(ALGORITHMS)
        backend = random.choice(BACKENDS)
        cat = random.choice(CATEGORIES)

        fidelity = clamp(random.gauss(0.86, 0.07))
        success = clamp(fidelity - random.uniform(0.0, 0.08))
        shots = random.choice([512, 1024, 2048, 4096, 8192])
        depth = random.randint(40, 1200)
        cnot = random.randint(5, max(8, depth // 5))
        total_gates = random.randint(max(60, cnot * 2), max(90, depth * 2))
        exp_date = base_date + timedelta(days=random.randint(0, 1100))

        conn.execute(
            """
            INSERT INTO circuits (
                circuit_id, job_id, circuit_name, algorithm, category,
                backend, architecture, quantum_volume, experiment_date, qiskit_version,
                is_simulator, optimization_level, transpiler_pass, connectivity,
                clops, shots, execution_time_ms, mitigation_technique,
                circuit_fidelity, success_rate, dominant_state
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                cid,
                f"JOB-{i:07d}",
                f"{algo}-Circuit-{i:05d}",
                algo,
                cat,
                backend,
                random.choice(ARCHITECTURES),
                random.choice([16, 32, 64, 128]),
                str(exp_date),
                random.choice(["0.43.1", "0.44.2", "1.0.0"]),
                random.choice(["True", "False"]),
                random.choice([0, 1, 2, 3]),
                random.choice(TRANSPILE),
                random.choice(["all-to-all", "nearest-neighbor", "heavy-hex"]),
                round(random.uniform(20000, 180000), 2),
                shots,
                round(random.uniform(20.0, 650.0), 3),
                random.choice(MITIGATION),
                round(fidelity, 6),
                round(success, 6),
                random.choice(["00", "11", "1010", "1100", "1111"]),
            ),
        )

        conn.execute(
            """
            INSERT INTO qubits (
                circuit_id, num_qubits_used, t1_relaxation_us, t2_decoherence_us,
                readout_error, qubit_frequency_ghz, coupling_strength_mhz,
                crosstalk_coefficient, leakage_rate
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                cid,
                random.randint(2, 127),
                round(random.uniform(30.0, 220.0), 4),
                round(random.uniform(20.0, 180.0), 4),
                round(random.uniform(0.005, 0.09), 6),
                round(random.uniform(4.5, 6.5), 6),
                round(random.uniform(0.8, 12.0), 6),
                round(random.uniform(0.0, 0.05), 6),
                round(random.uniform(0.0, 0.02), 6),
            ),
        )

        conn.execute(
            """
            INSERT INTO gates (
                circuit_id, total_gate_count, circuit_depth, cnot_count,
                h_gate_count, rz_gate_count, two_qubit_gates, transpiled_depth,
                two_qubit_gate_ratio, gate_depth_ratio, gate_cancellation_ratio,
                clifford_gates
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                cid,
                total_gates,
                depth,
                cnot,
                random.randint(1, max(2, total_gates // 7)),
                random.randint(3, max(4, total_gates // 2)),
                random.randint(2, max(3, total_gates // 3)),
                random.randint(max(10, depth // 2), depth + 80),
                round(cnot / max(total_gates, 1), 6),
                round(depth / max(total_gates, 1), 6),
                round(random.uniform(0.0, 0.28), 6),
                random.randint(1, total_gates),
            ),
        )

        conn.execute(
            """
            INSERT INTO results (
                circuit_id, success_rate, circuit_fidelity, expected_value,
                measured_value, hellinger_fidelity, kl_divergence, mitigation_overhead_ms
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                cid,
                round(success, 6),
                round(fidelity, 6),
                round(random.uniform(-1.0, 1.0), 6),
                round(random.uniform(-1.0, 1.0), 6),
                round(clamp(random.gauss(0.88, 0.08)), 6),
                round(random.uniform(0.0001, 0.12), 6),
                round(random.uniform(1.0, 25.0), 6),
            ),
        )

        total_err = clamp(random.uniform(0.005, 0.22), 0.0, 0.4)
        conn.execute(
            """
            INSERT INTO noise_models (
                circuit_id, noise_model, single_qubit_error_rate, two_qubit_error_rate,
                readout_error_rate, depolarizing_prob_1q, depolarizing_prob_2q,
                total_circuit_error, amplitude_damping_rate, spam_error_rate
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                cid,
                random.choice(NOISE_MODELS),
                round(random.uniform(0.0001, 0.02), 6),
                round(random.uniform(0.001, 0.08), 6),
                round(random.uniform(0.001, 0.08), 6),
                round(random.uniform(0.0001, 0.02), 6),
                round(random.uniform(0.001, 0.08), 6),
                round(total_err, 6),
                round(random.uniform(0.0001, 0.03), 6),
                round(random.uniform(0.0001, 0.03), 6),
            ),
        )

        if i % 1000 == 0:
            print(f"Inserted {i} circuits...")

    conn.commit()


def main():
    args = parse_args()
    random.seed(args.seed)

    db_path = Path(args.db)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        create_schema(conn)
        generate(conn, args.rows)

    print(f"Synthetic DB ready at: {db_path}")
    print(f"Rows per table: {args.rows}")


if __name__ == "__main__":
    main()
