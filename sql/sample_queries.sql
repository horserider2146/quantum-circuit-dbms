-- SQL commands used by the project for analytics and CRUD support.

-- 1) Top algorithms by number of experiments.
SELECT algorithm, COUNT(*) AS runs
FROM circuits
GROUP BY algorithm
ORDER BY runs DESC
LIMIT 10;

-- 2) Average fidelity by backend.
SELECT backend,
       COUNT(*) AS runs,
       ROUND(AVG(circuit_fidelity), 4) AS avg_fidelity
FROM circuits
GROUP BY backend
ORDER BY avg_fidelity DESC;

-- 3) Join across three tables to inspect quality and complexity.
SELECT c.circuit_id,
       c.algorithm,
       c.backend,
       c.circuit_fidelity,
       g.total_gate_count,
       g.circuit_depth,
       n.total_circuit_error
FROM circuits c
JOIN gates g ON c.circuit_id = g.circuit_id
JOIN noise_models n ON c.circuit_id = n.circuit_id
WHERE c.circuit_fidelity >= 0.9
ORDER BY c.circuit_fidelity DESC
LIMIT 20;

-- 4) Monthly experiment volume trend.
SELECT strftime('%Y-%m', experiment_date) AS month,
       COUNT(*) AS run_count
FROM circuits
WHERE experiment_date IS NOT NULL
GROUP BY month
ORDER BY month;

-- 5) Insert sample circuit (adjust values as needed).
INSERT INTO circuits (
    circuit_id,
    circuit_name,
    algorithm,
    category,
    backend,
    experiment_date,
    shots,
    circuit_fidelity,
    success_rate,
    is_simulator
) VALUES (
    'CIR-DEMO-0001',
    'Demo Circuit',
    'QFT',
    'education',
    'ibm_kolkata',
    '2026-03-20',
    1024,
    0.9100,
    0.8800,
    'False'
);

-- 6) Update sample circuit.
UPDATE circuits
SET mitigation_technique = 'TREX',
    circuit_fidelity = 0.9300
WHERE circuit_id = 'CIR-DEMO-0001';

-- 7) Delete sample circuit.
DELETE FROM circuits
WHERE circuit_id = 'CIR-DEMO-0001';
