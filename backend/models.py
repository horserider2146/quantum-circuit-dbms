"""Pydantic models for request/response validation."""

from pydantic import BaseModel, Field
from typing import Optional, Any, Literal


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
    results: list[dict[str, Any]]


class StatsResponse(BaseModel):
    total_circuits: int
    avg_fidelity: Optional[float] = None
    avg_success_rate: Optional[float] = None
    top_algorithms: list[dict[str, Any]]
    top_backends: list[dict[str, Any]]
    categories: list[dict[str, Any]]
    fidelity_distribution: list[dict[str, Any]]
    simulator_vs_real: list[dict[str, Any]]
    monthly_experiments: list[dict[str, Any]]


class BuilderStep(BaseModel):
    gate: str
    target_qubit: int
    control_qubit: Optional[int] = None
    parameter: Optional[float] = None


class BuilderPreviewRequest(BaseModel):
    num_qubits: int
    steps: list[BuilderStep]


class BuilderPreviewResponse(BaseModel):
    num_qubits: int
    depth: int
    gate_count: int
    preview_lines: list[str]


class BuilderSaveRequest(BaseModel):
    circuit_name: str
    num_qubits: int
    created_by: Optional[str] = None
    notes: Optional[str] = None
    steps: list[BuilderStep]


class BuilderSaveResponse(BaseModel):
    message: str
    user_circuit_id: str
    step_count: int


class BulkCircuitUploadRequest(BaseModel):
    records: list[CircuitCreate] = Field(default_factory=list)
    conflict_strategy: Literal["skip", "update", "error"] = "skip"
    created_by: Optional[str] = None


class BulkCircuitUploadResponse(BaseModel):
    received: int
    inserted: int
    updated: int
    skipped: int
    failed: int
    errors: list[dict[str, Any]]


class SavedFilterCreate(BaseModel):
    name: str
    algorithm: Optional[str] = None
    backend: Optional[str] = None
    category: Optional[str] = None
    min_fidelity: Optional[float] = None
    max_fidelity: Optional[float] = None
    is_simulator: Optional[str] = None
    experiment_date_start: Optional[str] = None
    experiment_date_end: Optional[str] = None
    created_by: Optional[str] = None


class SavedFilterResponse(BaseModel):
    filter_id: int
    name: str
    created_at: str
    created_by: Optional[str] = None
    params: dict[str, Any]


class SoftDeleteRequest(BaseModel):
    deleted_by: Optional[str] = None


class RestoreCircuitRequest(BaseModel):
    restored_by: Optional[str] = None


class HardwareRecommendRequest(BaseModel):
    num_qubits_used: int
    circuit_depth: int
    cnot_count: Optional[int] = None
    min_samples: int = 5


class QuantumWhatIfRequest(BaseModel):
    circuit_id: Optional[str] = None
    algorithm: Optional[str] = None
    backend: Optional[str] = None
    mitigation_technique: Optional[str] = None
    optimization_level: Optional[int] = None
    shots: Optional[int] = None
    circuit_depth: Optional[int] = None
    num_qubits_used: Optional[int] = None
    total_circuit_error: Optional[float] = None
    min_samples: int = 12


class QuantumWhatIfRecommendationRequest(QuantumWhatIfRequest):
    top_k: int = 3