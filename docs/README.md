# ⚛️ Quantum Circuit DBMS

A full-stack **Database Management System** built on **15,000 IBM Quantum circuit experiments**, featuring a relational SQLite database, a FastAPI REST backend, and an interactive Streamlit dashboard with search, CRUD operations, circuit comparison, and built-in lessons.

---

## 📌 Table of Contents

- [Project Overview](#-project-overview)
- [Tech Stack](#-tech-stack)
- [File Structure](#-file-structure)
- [Database Schema](#-database-schema)
- [Setup & Installation](#-setup--installation)
- [Running the Project](#-running-the-project)
- [API Endpoints](#-api-endpoints)
- [Dashboard Pages](#-dashboard-pages)
- [Example API Usage](#-example-api-usage)
- [Pushing to GitHub](#-pushing-to-github)
- [Lessons Covered](#-lessons-covered)

---

## 📖 Project Overview

This project demonstrates a complete DBMS pipeline using real-world quantum computing data:

- **15,000 IBM Quantum circuit experiments** loaded from Excel into a relational SQLite database
- **5 normalized tables** linked by a `circuit_id` primary key
- **FastAPI backend** exposing 18+ REST endpoints for full CRUD, search, and analytics
- **Streamlit dashboard** with 6 interactive pages including a search engine and circuit comparison tool
- **Step-by-step lessons** and a live SQL playground built directly into the dashboard

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Database | SQLite 3 |
| Backend API | FastAPI + Pydantic |
| Frontend | Streamlit |
| Data Processing | pandas + openpyxl |
| ASGI Server | Uvicorn |
| Language | Python 3.10+ |

---

## 📁 File Structure

```
quantum_dbms/
├── backend/
│   ├── main.py            ← FastAPI routes & all endpoints
│   └── models.py          ← Pydantic request/response schemas
├── frontend/
│   ├── dashboard.py       ← Original Streamlit dashboard (direct DB)
│   └── dashboard_api.py   ← API-driven dashboard for course requirements
├── db/
│   └── quantum_circuits.db  ← SQLite database (auto-generated)
├── docs/
│   └── README.md          ← This file
└── requirements.txt       ← Python dependencies
```

---

## 🗄️ Database Schema

All 5 tables are linked via `circuit_id` as the primary key.

### `circuits` — Main table (21 columns)
| Column | Type | Description |
|--------|------|-------------|
| circuit_id | TEXT | Unique identifier e.g. CIR-00001 |
| job_id | TEXT | IBM Quantum job ID |
| circuit_name | TEXT | Human-readable name |
| algorithm | TEXT | QFT, VQE, QAOA, Grover, etc. |
| category | TEXT | Circuit category |
| backend | TEXT | ibm_seattle, ibm_kolkata, etc. |
| architecture | TEXT | Hardware architecture |
| quantum_volume | INTEGER | IBM Quantum Volume metric |
| experiment_date | TEXT | ISO date of experiment |
| qiskit_version | TEXT | Qiskit SDK version used |
| is_simulator | TEXT | True / False |
| optimization_level | INTEGER | Transpiler optimization (0–3) |
| shots | INTEGER | Number of measurement shots |
| circuit_fidelity | REAL | Quality score (0.0 – 1.0) |
| success_rate | REAL | Success rate (0.0 – 1.0) |

### `qubits` — Hardware parameters (20 columns)
Qubit frequencies (GHz), T1 relaxation (µs), T2 decoherence (µs), readout errors, coupling strengths (MHz), crosstalk, leakage rates, and calibration dates.

### `gates` — Circuit composition (23 columns)
Total gate count, circuit depth, CNOT count, H/RZ/X/T gate counts, two-qubit gate ratio, Clifford vs non-Clifford gates, transpiled depth, and gate cancellation ratio.

### `results` — Execution outcomes (22 columns)
Success rate, Hellinger fidelity, TVD, KL divergence, cross entropy, expected vs measured values, mitigation overhead, memory usage, and retry counts.

### `noise_models` — Error profiles (23 columns)
Depolarizing probabilities (1Q/2Q), amplitude/phase damping rates, SPAM errors, crosstalk error, coherent error rate, gate errors (CX, U3), and total circuit error.

---

## ⚙️ Setup & Installation

### 1. Clone the repository
```bash
git clone https://github.com/YOUR_USERNAME/quantum-circuit-dbms.git
cd quantum-circuit-dbms
```

### 2. Install dependencies
```powershell
pip install -r requirements.txt
```

> If pandas fails to install on Windows, run this first:
> ```powershell
> pip install pandas --prefer-binary
> ```

### 3. Generate the database
Place your `quantum_circuit_database.xlsx` file somewhere accessible, then run:

```powershell
python -c "
import pandas as pd, sqlite3
xl = pd.read_excel('C:/path/to/quantum_circuit_database.xlsx', sheet_name=None)
conn = sqlite3.connect('db/quantum_circuits.db')
for sheet, table in [('Circuits','circuits'),('Qubits','qubits'),('Gates','gates'),('Results','results'),('Noise_Models','noise_models')]:
    df = xl[sheet].copy()
    df.columns = [c.strip().lower().replace(' ','_') for c in df.columns]
    df.to_sql(table, conn, if_exists='replace', index=False)
    print(f'Loaded {table}')
conn.close()
print('Done!')
"
```

You should see:
```
Loaded circuits
Loaded qubits
Loaded gates
Loaded results
Loaded noise_models
Done!
```

---

## 🚀 Running the Project

Open **two separate terminals** inside the `quantum_dbms/` folder.

### Terminal 1 — Start the FastAPI backend
```powershell
set API_KEY=dev-api-key
python -m uvicorn backend.main:app --reload --port 8000
```

### Terminal 2 — Start the Streamlit dashboard
```powershell
set API_KEY=dev-api-key
set API_BASE_URL=http://localhost:8000
python -m streamlit run frontend/dashboard_api.py
```

`frontend/dashboard_api.py` is the API-first dashboard used for course requirement compliance (authenticated calls to FastAPI endpoints).

### Access the app
| What | URL |
|------|-----|
| 📊 Dashboard | http://localhost:8501 |
| 📚 API Docs (Swagger) | http://localhost:8000/docs |
| 📖 API ReDoc | http://localhost:8000/redoc |
| ❤️ Health Check | http://localhost:8000/health |

---

## 🌐 API Endpoints

### Circuits
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/circuits` | List circuits (paginated + filtered) |
| GET | `/circuits/{id}` | Full detail across all 5 tables |
| POST | `/circuits` | Create a new circuit |
| PATCH | `/circuits/{id}` | Update specific fields |
| DELETE | `/circuits/{id}` | Soft delete circuit (recoverable) |
| POST | `/circuits/{id}/restore` | Restore a soft-deleted circuit |
| DELETE | `/circuits/{id}/hard` | Permanent delete + related records |

### Search & Stats
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/search?q=QFT` | Full-text search across 5 fields |
| GET | `/stats` | Aggregated dashboard statistics |
| GET | `/stats/top-performers` | Top circuits ranked by fidelity |

### Metadata
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/meta/algorithms` | All distinct algorithm names |
| GET | `/meta/backends` | All distinct backend names |
| GET | `/meta/categories` | All distinct categories |

### Related Tables
| Method | Endpoint | Description |
|--------|----------|-------------|
| PATCH | `/qubits/{id}` | Update qubit parameters |
| PATCH | `/noise/{id}` | Update noise model values |

### DBMS Enhancements
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/bulk/circuits` | Bulk insert/update with conflict handling |
| POST | `/filters` | Save filter preset |
| GET | `/filters` | List saved filters |
| GET | `/filters/{filter_id}/circuits` | Run saved filter |
| GET | `/audit/logs` | Audit trail events |
| GET | `/quality/report` | Data-quality checks |
| GET | `/benchmark/compare` | Algorithm benchmark comparison |

### Quantum Extensions
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/quantum/noise-aware-score` | Composite quality ranking |
| GET | `/quantum/mitigation/effectiveness` | Mitigation analytics |
| POST | `/quantum/hardware/recommend` | Backend recommendation |

### Filter Parameters for `GET /circuits`
| Parameter | Type | Example |
|-----------|------|---------|
| `algorithm` | string (partial match) | `?algorithm=QFT` |
| `backend` | string (partial match) | `?backend=ibm_seattle` |
| `category` | string (partial match) | `?category=variational` |
| `min_fidelity` | float | `?min_fidelity=0.9` |
| `max_fidelity` | float | `?max_fidelity=1.0` |
| `is_simulator` | string | `?is_simulator=False` |
| `page` | int | `?page=2` |
| `limit` | int | `?limit=50` |

---

## 📊 Dashboard Pages

| Page | Features |
|------|----------|
| 🏠 Overview | KPI metrics, algorithm/backends charts, fidelity distribution, top performers |
| 🔍 Search & Filter | Full-text search and advanced filtering via API |
| ✏️ CRUD | Create, update, soft delete records through API forms |
| 📊 Compare | Side-by-side circuit comparison with verdict and metric tables |
| 🧪 Qubit Builder | Build, preview, save, list, view, and delete custom circuits |

---

## 💻 Example API Usage

```python
import requests

BASE = "http://localhost:8000"

# Required auth header
headers = {"X-API-Key": "dev-api-key"}

# Search for Grover circuits
r = requests.get(f"{BASE}/search", params={"q": "Grover"}, headers=headers)
print(r.json()["count"], "results found")

# Get high-fidelity real hardware circuits
r = requests.get(f"{BASE}/circuits", params={
    "min_fidelity": 0.95,
    "is_simulator": "False",
    "limit": 10
}, headers=headers)
for c in r.json()["data"]:
    print(c["circuit_id"], c["backend"], c["circuit_fidelity"])

# Get full detail for one circuit (all 5 tables)
r = requests.get(f"{BASE}/circuits/CIR-00001", headers=headers)
data = r.json()
print(data["circuit"]["algorithm"])
print(data["qubits"]["t1_relaxation_us"])
print(data["noise_model"]["total_circuit_error"])

# Update a circuit
r = requests.patch(f"{BASE}/circuits/CIR-00001", json={
    "circuit_fidelity": 0.97,
    "mitigation_technique": "TREX"
}, headers=headers)
print(r.json())

# Soft delete a circuit (recoverable)
r = requests.delete(f"{BASE}/circuits/CIR-99999", headers=headers)
print(r.json())

# Restore soft-deleted circuit
r = requests.post(f"{BASE}/circuits/CIR-99999/restore", headers=headers)
print(r.json())

# Get dashboard stats
r = requests.get(f"{BASE}/stats", headers=headers)
stats = r.json()
print(f"Total: {stats['total_circuits']:,} circuits")
print(f"Avg Fidelity: {stats['avg_fidelity']:.2%}")
```

---

## 🐙 Pushing to GitHub

```powershell
# Initialize git inside quantum_dbms/
git init
git add .
git commit -m "Initial commit - Quantum Circuit DBMS"

# Link to your GitHub repo
git remote add origin https://github.com/YOUR_USERNAME/quantum-circuit-dbms.git
git branch -M main
git push -u origin main
```

> The `.db` database file is excluded via `.gitignore` because of its size.
> Anyone cloning the repo should follow the **Generate the database** step above.

---

## 🎓 Notes

The API-driven dashboard focuses on course requirements and includes direct operational workflows:

- analytics overview
- search and filter interactions
- CRUD operations
- side-by-side circuit comparison
- custom circuit builder

---

## 👤 Author

**Ritarshi Roy**  
Quantum Circuit DBMS — College DBMS Project  

---

## 📄 License

This project is for educational purposes.  
Quantum circuit data sourced from IBM Quantum experiments.
