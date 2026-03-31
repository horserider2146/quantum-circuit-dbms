# ER Diagram

The project uses a relational schema with one central table (`circuits`) and four related tables connected by `circuit_id`.

## Mermaid ER Diagram

```mermaid
erDiagram
    circuits {
        TEXT circuit_id PK
        TEXT job_id
        TEXT circuit_name
        TEXT algorithm
        TEXT category
        TEXT backend
        TEXT architecture
        INTEGER quantum_volume
        TEXT experiment_date
        INTEGER shots
        REAL circuit_fidelity
        REAL success_rate
    }

    qubits {
        TEXT circuit_id PK,FK
        INTEGER num_qubits_used
        REAL t1_relaxation_us
        REAL t2_decoherence_us
        REAL readout_error
        REAL qubit_frequency_ghz
        REAL coupling_strength_mhz
        REAL crosstalk_coefficient
        REAL leakage_rate
    }

    gates {
        TEXT circuit_id PK,FK
        INTEGER total_gate_count
        INTEGER circuit_depth
        INTEGER cnot_count
        INTEGER h_gate_count
        INTEGER rz_gate_count
        INTEGER transpiled_depth
        REAL two_qubit_gate_ratio
        REAL gate_cancellation_ratio
    }

    results {
        TEXT circuit_id PK,FK
        REAL success_rate
        REAL circuit_fidelity
        REAL expected_value
        REAL measured_value
        REAL hellinger_fidelity
        REAL kl_divergence
        REAL mitigation_overhead_ms
    }

    noise_models {
        TEXT circuit_id PK,FK
        TEXT noise_model
        REAL single_qubit_error_rate
        REAL two_qubit_error_rate
        REAL readout_error_rate
        REAL depolarizing_prob_1q
        REAL depolarizing_prob_2q
        REAL total_circuit_error
    }

    circuits ||--|| qubits : "circuit_id"
    circuits ||--|| gates : "circuit_id"
    circuits ||--|| results : "circuit_id"
    circuits ||--|| noise_models : "circuit_id"
```

## Design Notes

- `circuits` stores core metadata and experiment-level KPIs.
- Related tables split domain-specific attributes (hardware, gate composition, run outcomes, and noise profiles).
- This structure reduces duplication and supports efficient joins for analytics.
- Indexes are created for `circuit_id` plus common filter fields (`algorithm`, `backend`, `experiment_date`, `circuit_fidelity`).
