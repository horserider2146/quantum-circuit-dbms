"""
Pydantic models for request/response validation.
"""
from pydantic import BaseModel
from typing import Optional


class CircuitCreate(BaseModel):
    circuit_id: str
    job_id: Optional[str] = None
    circuit_name: Optional[str] = None
    algorithm: Optional[str] = None
    category: Optional[str] = None
    backend: Optional[str] = None
    architecture: Optional[str] = None
    quantum_volume: Optional[int] = None
    experiment_date: Optional[str] = None
    qiskit_version: Optional[str] = None
    is_simulator: Optional[str] = None
    optimization_level: Optional[int] = None
    transpiler_pass: Optional[str] = None
    connectivity: Optional[str] = None
    clops: Optional[float] = None
    shots: Optional[int] = None
    execution_time_ms: Optional[float] = None
    mitigation_technique: Optional[str] = None
    circuit_fidelity: Optional[float] = None
    success_rate: Optional[float] = None
    dominant_state: Optional[str] = None


class CircuitUpdate(BaseModel):
    circuit_name: Optional[str] = None
    algorithm: Optional[str] = None
    category: Optional[str] = None
    backend: Optional[str] = None
    quantum_volume: Optional[int] = None
    optimization_level: Optional[int] = None
    circuit_fidelity: Optional[float] = None
    success_rate: Optional[float] = None
    mitigation_technique: Optional[str] = None
    shots: Optional[int] = None


class CircuitResponse(BaseModel):
    circuit_id: str
    algorithm: Optional[str]
    backend: Optional[str]
    circuit_fidelity: Optional[float]
    success_rate: Optional[float]


class QubitUpdate(BaseModel):
    num_qubits_used: Optional[int] = None
    t1_relaxation_us: Optional[float] = None
    t2_decoherence_us: Optional[float] = None
    readout_error: Optional[float] = None
    qubit_frequency_ghz: Optional[float] = None
    coupling_strength_mhz: Optional[float] = None


class GateUpdate(BaseModel):
    total_gate_count: Optional[int] = None
    circuit_depth: Optional[int] = None
    cnot_count: Optional[int] = None
    optimization_level: Optional[int] = None


class ResultUpdate(BaseModel):
    success_rate: Optional[float] = None
    circuit_fidelity: Optional[float] = None
    expected_value: Optional[float] = None
    measured_value: Optional[float] = None
    hellinger_fidelity: Optional[float] = None


class NoiseModelUpdate(BaseModel):
    noise_model: Optional[str] = None
    single_qubit_error_rate: Optional[float] = None
    two_qubit_error_rate: Optional[float] = None
    readout_error_rate: Optional[float] = None
    depolarizing_prob_1q: Optional[float] = None
    depolarizing_prob_2q: Optional[float] = None
    total_circuit_error: Optional[float] = None


class SearchResponse(BaseModel):
    query: str
    count: int
    results: list


class StatsResponse(BaseModel):
    total_circuits: int
    avg_fidelity: float
    avg_success_rate: float