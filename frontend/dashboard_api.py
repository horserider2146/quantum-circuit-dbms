"""
API-first Streamlit dashboard for the DBMS course project.

This frontend talks only to the FastAPI backend (no direct DB access)
so API authentication and endpoint usage are explicit for evaluation.
"""

import os
import importlib
import importlib.util
import sys
import time
import atexit
import socket
import subprocess
from pathlib import Path
from datetime import date

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st

st_autorefresh = None
if importlib.util.find_spec("streamlit_autorefresh"):
    st_autorefresh = importlib.import_module("streamlit_autorefresh").st_autorefresh


st.set_page_config(page_title="Quantum Circuit DBMS", layout="wide")

DEFAULT_API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000")
DEFAULT_API_KEY = os.getenv("API_KEY", "dev-api-key")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


_AUTO_BACKEND_PROCESS = None
_AUTO_BACKEND_BASE_URL = None


class ApiClient:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    @classmethod
    def remote(cls, base_url: str, api_key: str):
        return cls(base_url=base_url, api_key=api_key)

    def request(self, method: str, endpoint: str, params=None, payload=None):
        headers = {"X-API-Key": self.api_key}
        url = f"{self.base_url}{endpoint}"
        response = requests.request(
            method=method,
            url=url,
            params=params,
            json=payload,
            headers=headers,
            timeout=25,
        )

        if response.status_code >= 400:
            detail = ""
            try:
                detail = response.json().get("detail", "")
            except Exception:
                detail = response.text
            raise RuntimeError(f"{response.status_code} {response.reason}: {detail}")

        if response.headers.get("content-type", "").startswith("application/json"):
            return response.json()
        return response.text


def fetch_stats(client: ApiClient):
    return client.request("GET", "/stats")


def fetch_top_performers(client: ApiClient, limit: int):
    return client.request("GET", "/stats/top-performers", params={"limit": limit})


def fetch_meta(client: ApiClient, endpoint: str):
    return client.request("GET", endpoint)


def _to_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _to_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _api_is_ready(base_url: str, api_key: str) -> bool:
    probe = ApiClient.remote(base_url, api_key)
    try:
        probe.request("GET", "/health")
        probe.request("GET", "/stats")
        return True
    except Exception:
        return False


def _stop_auto_backend():
    global _AUTO_BACKEND_PROCESS
    if _AUTO_BACKEND_PROCESS and _AUTO_BACKEND_PROCESS.poll() is None:
        _AUTO_BACKEND_PROCESS.terminate()
        try:
            _AUTO_BACKEND_PROCESS.wait(timeout=3)
        except Exception:
            _AUTO_BACKEND_PROCESS.kill()
    _AUTO_BACKEND_PROCESS = None


atexit.register(_stop_auto_backend)


def _get_or_start_managed_fastapi(api_key: str) -> str:
    global _AUTO_BACKEND_PROCESS, _AUTO_BACKEND_BASE_URL

    if (
        _AUTO_BACKEND_PROCESS
        and _AUTO_BACKEND_PROCESS.poll() is None
        and _AUTO_BACKEND_BASE_URL
        and _api_is_ready(_AUTO_BACKEND_BASE_URL, api_key)
    ):
        return _AUTO_BACKEND_BASE_URL

    _stop_auto_backend()
    port = _find_free_port()
    base_url = f"http://127.0.0.1:{port}"

    env = os.environ.copy()
    env["API_KEY"] = api_key

    _AUTO_BACKEND_PROCESS = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "backend.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=str(PROJECT_ROOT),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    for _ in range(40):
        if _AUTO_BACKEND_PROCESS.poll() is not None:
            break
        if _api_is_ready(base_url, api_key):
            _AUTO_BACKEND_BASE_URL = base_url
            return base_url
        time.sleep(0.25)

    code = _AUTO_BACKEND_PROCESS.poll()
    _stop_auto_backend()
    raise RuntimeError(f"Managed FastAPI failed to start (exit code: {code})")


def build_api_client(api_mode: str, api_base: str, api_key: str):
    errors = []

    if api_mode in {"Auto", "Remote API"}:
        remote_client = ApiClient.remote(api_base, api_key)
        try:
            # Validate both service identity and required dashboard endpoint.
            remote_client.request("GET", "/health")
            remote_client.request("GET", "/stats")
            return remote_client, "Remote API"
        except Exception as exc:
            errors.append(f"Remote API failed: {exc}")
            if api_mode == "Remote API":
                raise RuntimeError(errors[-1])

    if api_mode in {"Auto", "Managed FastAPI"}:
        try:
            managed_base = _get_or_start_managed_fastapi(api_key)
            managed_client = ApiClient.remote(managed_base, api_key)
            return managed_client, f"Managed FastAPI ({managed_base})"
        except Exception as exc:
            errors.append(f"Managed FastAPI failed: {exc}")
            if api_mode == "Managed FastAPI":
                raise RuntimeError(errors[-1])

    raise RuntimeError(" | ".join(errors) if errors else "Unable to initialize API client")


def ensure_builder_state():
    if "builder_steps" not in st.session_state:
        st.session_state.builder_steps = []
    if "builder_preview" not in st.session_state:
        st.session_state.builder_preview = None
    if "builder_saved_list" not in st.session_state:
        st.session_state.builder_saved_list = []


def render_overview_tab(client: ApiClient):
    stats = fetch_stats(client)

    k1, k2, k3 = st.columns(3)
    k1.metric("Total circuits", f"{stats.get('total_circuits', 0):,}")
    k2.metric("Average fidelity", f"{float(stats.get('avg_fidelity') or 0):.2%}")
    k3.metric("Average success rate", f"{float(stats.get('avg_success_rate') or 0):.2%}")

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Top algorithms")
        algo_df = pd.DataFrame(stats.get("top_algorithms", []))
        if not algo_df.empty:
            st.plotly_chart(px.bar(algo_df, x="algorithm", y="count"), use_container_width=True)
        else:
            st.info("No algorithm data available.")

    with c2:
        st.subheader("Top backends")
        backend_df = pd.DataFrame(stats.get("top_backends", []))
        if not backend_df.empty:
            st.plotly_chart(px.bar(backend_df, x="backend", y="count"), use_container_width=True)
        else:
            st.info("No backend data available.")

    st.subheader("Fidelity distribution")
    fidelity_df = pd.DataFrame(stats.get("fidelity_distribution", []))
    if not fidelity_df.empty:
        st.plotly_chart(px.bar(fidelity_df, x="range", y="count"), use_container_width=True)
    else:
        st.info("No fidelity distribution available.")

    st.subheader("Top performers")
    top_limit = st.slider("Rows in top performers table", min_value=5, max_value=30, value=10)
    top_payload = fetch_top_performers(client, top_limit)
    top_df = pd.DataFrame(top_payload.get("data", []))
    st.dataframe(top_df, use_container_width=True, hide_index=True)


def render_search_filter_tab(client: ApiClient):
    st.subheader("Interactive search")
    search_term = st.text_input(
        "Search by circuit id, name, algorithm, backend, or category",
        placeholder="Example: QFT",
    )
    if st.button("Run search"):
        if not search_term.strip():
            st.warning("Enter a search term first.")
        else:
            try:
                search_payload = client.request(
                    "GET", "/search", params={"q": search_term.strip(), "limit": 100}
                )
                search_df = pd.DataFrame(search_payload.get("results", []))
                st.write(f"Matches: {search_payload.get('count', 0)}")
                st.dataframe(search_df, use_container_width=True, hide_index=True)
            except Exception as exc:
                st.error(f"Search failed: {exc}")

    st.divider()

    st.subheader("Filter circuits")
    algorithm_options = ["All"] + fetch_meta(client, "/meta/algorithms")
    backend_options = ["All"] + fetch_meta(client, "/meta/backends")
    category_options = ["All"] + fetch_meta(client, "/meta/categories")

    f1, f2, f3 = st.columns(3)
    selected_algorithm = f1.selectbox("Algorithm", options=algorithm_options)
    selected_backend = f2.selectbox("Backend", options=backend_options)
    selected_category = f3.selectbox("Category", options=category_options)

    f4, f5, f6 = st.columns(3)
    min_fidelity = f4.number_input("Min fidelity", min_value=0.0, max_value=1.0, value=0.0, step=0.01)
    max_fidelity = f5.number_input("Max fidelity", min_value=0.0, max_value=1.0, value=1.0, step=0.01)
    is_simulator = f6.selectbox("Simulator", options=["All", "True", "False"])

    f7, f8 = st.columns(2)
    experiment_date_start = f7.date_input("Start date", value=None)
    experiment_date_end = f8.date_input("End date", value=None)

    filter_limit = st.slider("Result size", min_value=10, max_value=200, value=50)
    a1, a2 = st.columns(2)
    apply_now = a1.button("Apply filters", use_container_width=True)
    save_filter = a2.button("Save this filter", use_container_width=True)

    params = {"page": 1, "limit": filter_limit, "min_fidelity": min_fidelity, "max_fidelity": max_fidelity}
    if selected_algorithm != "All":
        params["algorithm"] = selected_algorithm
    if selected_backend != "All":
        params["backend"] = selected_backend
    if selected_category != "All":
        params["category"] = selected_category
    if is_simulator != "All":
        params["is_simulator"] = is_simulator
    if experiment_date_start:
        params["experiment_date_start"] = str(experiment_date_start)
    if experiment_date_end:
        params["experiment_date_end"] = str(experiment_date_end)

    if apply_now:
        params = {"page": 1, "limit": filter_limit, "min_fidelity": min_fidelity, "max_fidelity": max_fidelity}
        if selected_algorithm != "All":
            params["algorithm"] = selected_algorithm
        if selected_backend != "All":
            params["backend"] = selected_backend
        if selected_category != "All":
            params["category"] = selected_category
        if is_simulator != "All":
            params["is_simulator"] = is_simulator
        if experiment_date_start:
            params["experiment_date_start"] = str(experiment_date_start)
        if experiment_date_end:
            params["experiment_date_end"] = str(experiment_date_end)

        try:
            filtered_payload = client.request("GET", "/circuits", params=params)
            filtered_df = pd.DataFrame(filtered_payload.get("data", []))
            st.write(
                f"Showing {len(filtered_df)} rows out of {filtered_payload.get('total', 0)} matching circuits"
            )
            st.dataframe(filtered_df, use_container_width=True, hide_index=True)
        except Exception as exc:
            st.error(f"Filter query failed: {exc}")

    if save_filter:
        try:
            save_payload = {
                "name": f"{selected_algorithm}-{selected_backend}-{selected_category}".replace("All", "any"),
                "algorithm": params.get("algorithm"),
                "backend": params.get("backend"),
                "category": params.get("category"),
                "min_fidelity": params.get("min_fidelity"),
                "max_fidelity": params.get("max_fidelity"),
                "is_simulator": params.get("is_simulator"),
                "experiment_date_start": params.get("experiment_date_start"),
                "experiment_date_end": params.get("experiment_date_end"),
                "created_by": "dashboard-user",
            }
            out = client.request("POST", "/filters", payload=save_payload)
            st.success(f"Saved filter #{out.get('filter_id')}: {out.get('name')}")
        except Exception as exc:
            st.error(f"Save filter failed: {exc}")

    st.markdown("**Saved filters**")
    s1, s2 = st.columns(2)
    if s1.button("Load saved filters", use_container_width=True):
        try:
            saved = client.request("GET", "/filters", params={"limit": 50})
            st.session_state.saved_filters_cache = saved.get("data", [])
        except Exception as exc:
            st.error(f"Failed to load saved filters: {exc}")

    cached_filters = st.session_state.get("saved_filters_cache", [])
    if cached_filters:
        saved_df = pd.DataFrame(cached_filters)
        st.dataframe(saved_df, use_container_width=True, hide_index=True)

    apply_filter_id = s2.number_input("Apply filter ID", min_value=0, value=0, step=1)
    if apply_filter_id > 0 and st.button("Run saved filter", use_container_width=True):
        try:
            payload = client.request(
                "GET",
                f"/filters/{int(apply_filter_id)}/circuits",
                params={"page": 1, "limit": filter_limit},
            )
            result_df = pd.DataFrame(payload.get("data", []))
            st.write(f"Saved filter {apply_filter_id}: {payload.get('total', 0)} rows")
            st.dataframe(result_df, use_container_width=True, hide_index=True)
        except Exception as exc:
            st.error(f"Run saved filter failed: {exc}")


def render_crud_tab(client: ApiClient):
    st.subheader("CRUD via API")
    crud_tab_1, crud_tab_2, crud_tab_3 = st.tabs(["Create", "Update", "Delete"])

    with crud_tab_1:
        st.caption("Create a new circuit row in the circuits table.")
        with st.form("create_circuit_form"):
            new_circuit_id = st.text_input("Circuit ID", value="")
            new_name = st.text_input("Circuit name", value="")
            new_algorithm = st.text_input("Algorithm", value="")
            new_backend = st.text_input("Backend", value="")
            new_category = st.text_input("Category", value="")
            new_date = st.date_input("Experiment date", value=date.today())
            new_shots = st.number_input("Shots", min_value=1, value=1024)
            new_fidelity = st.slider("Fidelity", min_value=0.0, max_value=1.0, value=0.85, step=0.001)
            new_success = st.slider("Success rate", min_value=0.0, max_value=1.0, value=0.8, step=0.001)
            create_submit = st.form_submit_button("Create circuit")

        if create_submit:
            payload = {
                "circuit_id": new_circuit_id.strip(),
                "circuit_name": new_name.strip() or None,
                "algorithm": new_algorithm.strip() or None,
                "backend": new_backend.strip() or None,
                "category": new_category.strip() or None,
                "experiment_date": str(new_date),
                "shots": int(new_shots),
                "circuit_fidelity": float(new_fidelity),
                "success_rate": float(new_success),
            }
            try:
                out = client.request("POST", "/circuits", payload=payload)
                st.success(str(out))
                st.cache_data.clear()
            except Exception as exc:
                st.error(f"Create failed: {exc}")

    with crud_tab_2:
        st.caption("Update selected fields for an existing circuit.")
        with st.form("update_circuit_form"):
            edit_circuit_id = st.text_input("Circuit ID to update", value="")
            edit_name = st.text_input("New circuit name (optional)", value="")
            edit_backend = st.text_input("New backend (optional)", value="")
            edit_fidelity = st.text_input("New fidelity (optional, 0-1)", value="")
            update_submit = st.form_submit_button("Update circuit")

        if update_submit:
            payload = {}
            if edit_name.strip():
                payload["circuit_name"] = edit_name.strip()
            if edit_backend.strip():
                payload["backend"] = edit_backend.strip()
            if edit_fidelity.strip():
                payload["circuit_fidelity"] = float(edit_fidelity)

            if not payload:
                st.warning("Provide at least one field to update.")
            else:
                try:
                    out = client.request("PATCH", f"/circuits/{edit_circuit_id.strip()}", payload=payload)
                    st.success(str(out))
                    st.cache_data.clear()
                except Exception as exc:
                    st.error(f"Update failed: {exc}")

    with crud_tab_3:
        st.caption("Delete a circuit and related records.")
        with st.form("delete_circuit_form"):
            delete_circuit_id = st.text_input("Circuit ID to delete", value="")
            confirm_text = st.text_input("Type DELETE to confirm", value="")
            delete_submit = st.form_submit_button("Delete circuit")

        if delete_submit:
            if confirm_text != "DELETE":
                st.warning("Type DELETE exactly to confirm removal.")
            else:
                try:
                    out = client.request("DELETE", f"/circuits/{delete_circuit_id.strip()}")
                    st.success(str(out))
                    st.cache_data.clear()
                except Exception as exc:
                    st.error(f"Delete failed: {exc}")


def render_compare_tab(client: ApiClient):
    st.subheader("Circuit Comparison")
    st.caption("Compare two circuits side-by-side across key metrics and related table values.")

    cmp1, cmp2 = st.columns(2)
    compare_id_1 = cmp1.text_input("Circuit ID #1", value="", key="compare_id_1")
    compare_id_2 = cmp2.text_input("Circuit ID #2", value="", key="compare_id_2")

    if st.button("Compare circuits", key="compare_btn", use_container_width=True):
        cid_1 = compare_id_1.strip().upper()
        cid_2 = compare_id_2.strip().upper()

        if not cid_1 or not cid_2:
            st.warning("Enter both circuit IDs to compare.")
        elif cid_1 == cid_2:
            st.warning("Please choose two different circuit IDs.")
        else:
            try:
                full_1 = client.request("GET", f"/circuits/{cid_1}")
                full_2 = client.request("GET", f"/circuits/{cid_2}")
            except Exception as exc:
                st.error(f"Comparison failed: {exc}")
            else:
                c1 = full_1.get("circuit") or {}
                c2 = full_2.get("circuit") or {}
                g1 = full_1.get("gates") or {}
                g2 = full_2.get("gates") or {}
                n1 = full_1.get("noise_model") or {}
                n2 = full_2.get("noise_model") or {}

                fid1 = _to_float(c1.get("circuit_fidelity"))
                fid2 = _to_float(c2.get("circuit_fidelity"))
                suc1 = _to_float(c1.get("success_rate"))
                suc2 = _to_float(c2.get("success_rate"))
                sh1 = _to_int(c1.get("shots"))
                sh2 = _to_int(c2.get("shots"))

                m1, m2, m3, m4 = st.columns(4)
                m1.metric(f"Fidelity ({cid_1})", f"{fid1:.2%}", f"{fid1 - fid2:+.2%}")
                m2.metric(f"Fidelity ({cid_2})", f"{fid2:.2%}", f"{fid2 - fid1:+.2%}")
                m3.metric(f"Success ({cid_1})", f"{suc1:.2%}", f"{suc1 - suc2:+.2%}")
                m4.metric(f"Success ({cid_2})", f"{suc2:.2%}", f"{suc2 - suc1:+.2%}")

                if fid1 > fid2:
                    st.success(f"{cid_1} has higher fidelity by {fid1 - fid2:.2%}")
                elif fid2 > fid1:
                    st.success(f"{cid_2} has higher fidelity by {fid2 - fid1:.2%}")
                else:
                    st.info("Both circuits have equal fidelity.")

                st.markdown("**Circuit details**")
                fields = [
                    "circuit_name",
                    "algorithm",
                    "category",
                    "backend",
                    "is_simulator",
                    "shots",
                    "optimization_level",
                    "mitigation_technique",
                    "circuit_fidelity",
                    "success_rate",
                    "experiment_date",
                ]
                detail_rows = []
                for field in fields:
                    detail_rows.append({
                        "field": field,
                        cid_1: c1.get(field),
                        cid_2: c2.get(field),
                    })
                st.dataframe(pd.DataFrame(detail_rows), use_container_width=True, hide_index=True)

                st.markdown("**Gate metrics comparison**")
                gate_cols = [
                    "total_gate_count",
                    "circuit_depth",
                    "cnot_count",
                    "h_gate_count",
                    "rz_gate_count",
                    "two_qubit_gates",
                    "transpiled_depth",
                ]
                gate_rows = []
                for col in gate_cols:
                    gate_rows.append({
                        "metric": col,
                        cid_1: g1.get(col),
                        cid_2: g2.get(col),
                    })
                st.dataframe(pd.DataFrame(gate_rows), use_container_width=True, hide_index=True)

                gate_chart = pd.DataFrame(
                    {
                        "metric": gate_cols,
                        cid_1: [_to_float(g1.get(col)) for col in gate_cols],
                        cid_2: [_to_float(g2.get(col)) for col in gate_cols],
                    }
                )
                st.plotly_chart(
                    px.bar(gate_chart, x="metric", y=[cid_1, cid_2], barmode="group"),
                    use_container_width=True,
                )

                st.markdown("**Noise metrics comparison**")
                noise_cols = [
                    "noise_model",
                    "single_qubit_error_rate",
                    "two_qubit_error_rate",
                    "readout_error_rate",
                    "depolarizing_prob_1q",
                    "depolarizing_prob_2q",
                    "total_circuit_error",
                ]
                noise_rows = []
                for col in noise_cols:
                    noise_rows.append({
                        "metric": col,
                        cid_1: n1.get(col),
                        cid_2: n2.get(col),
                    })
                st.dataframe(pd.DataFrame(noise_rows), use_container_width=True, hide_index=True)

                st.markdown("**Auto verdict**")
                verdicts = []
                if fid1 >= fid2:
                    verdicts.append(f"Fidelity winner: {cid_1} ({fid1:.2%} vs {fid2:.2%})")
                else:
                    verdicts.append(f"Fidelity winner: {cid_2} ({fid2:.2%} vs {fid1:.2%})")

                if suc1 >= suc2:
                    verdicts.append(f"Success-rate winner: {cid_1} ({suc1:.2%} vs {suc2:.2%})")
                else:
                    verdicts.append(f"Success-rate winner: {cid_2} ({suc2:.2%} vs {suc1:.2%})")

                if sh1 >= sh2:
                    verdicts.append(f"Higher shots: {cid_1} ({sh1:,} vs {sh2:,})")
                else:
                    verdicts.append(f"Higher shots: {cid_2} ({sh2:,} vs {sh1:,})")

                for verdict in verdicts:
                    st.write(f"- {verdict}")


def render_builder_tab(client: ApiClient):
    st.subheader("Qubit Builder")
    st.caption(
        "Create custom circuits by composing gate steps. This is a no-code alternative to drag-and-drop."
    )

    builder_num_qubits = st.number_input(
        "Number of qubits",
        min_value=1,
        max_value=16,
        value=3,
        step=1,
        key="builder_num_qubits",
    )
    max_qubit_index = int(builder_num_qubits) - 1

    builder_gates = [
        "I", "X", "Y", "Z", "H", "S", "T",
        "RX", "RY", "RZ",
        "CNOT", "CZ", "CRX", "CRY", "CRZ", "SWAP",
    ]
    gates_with_second_qubit = {"CNOT", "CZ", "CRX", "CRY", "CRZ", "SWAP"}
    gates_with_parameter = {"RX", "RY", "RZ", "CRX", "CRY", "CRZ"}

    q1, q2, q3 = st.columns(3)
    selected_gate = q1.selectbox("Gate", options=builder_gates, key="builder_gate")
    target_qubit = q2.number_input(
        "Target qubit index",
        min_value=0,
        max_value=max_qubit_index,
        value=0,
        step=1,
        key="builder_target_qubit",
    )

    second_qubit = None
    if selected_gate in gates_with_second_qubit:
        second_default = 1 if max_qubit_index >= 1 else 0
        second_qubit = q3.number_input(
            "Control / second qubit index",
            min_value=0,
            max_value=max_qubit_index,
            value=second_default,
            step=1,
            key="builder_second_qubit",
        )
    else:
        q3.caption("Selected gate does not use a second qubit.")

    gate_parameter = None
    if selected_gate in gates_with_parameter:
        gate_parameter = st.number_input(
            "Rotation parameter (radians)",
            value=1.5708,
            format="%.4f",
            key="builder_gate_parameter",
        )

    b1, b2, b3 = st.columns(3)
    if b1.button("Add gate step", use_container_width=True, key="builder_add_step"):
        if selected_gate in gates_with_second_qubit and int(second_qubit) == int(target_qubit):
            st.error("Target and control/second qubit must be different.")
        else:
            st.session_state.builder_steps.append(
                {
                    "gate": selected_gate,
                    "target_qubit": int(target_qubit),
                    "control_qubit": int(second_qubit) if selected_gate in gates_with_second_qubit else None,
                    "parameter": float(gate_parameter) if selected_gate in gates_with_parameter else None,
                }
            )
            st.success("Gate step added.")

    if b2.button("Remove last step", use_container_width=True, key="builder_pop_step"):
        if st.session_state.builder_steps:
            st.session_state.builder_steps.pop()
            st.success("Last step removed.")
        else:
            st.info("No steps to remove.")

    if b3.button("Clear all steps", use_container_width=True, key="builder_clear_steps"):
        st.session_state.builder_steps = []
        st.session_state.builder_preview = None
        st.success("Builder reset.")

    invalid_positions = []
    for idx, step in enumerate(st.session_state.builder_steps, start=1):
        if step["target_qubit"] > max_qubit_index:
            invalid_positions.append(idx)
            continue
        if step.get("control_qubit") is not None and step["control_qubit"] > max_qubit_index:
            invalid_positions.append(idx)

    if invalid_positions:
        st.warning(
            f"Current qubit count invalidates step(s): {invalid_positions}. "
            "Clear steps or increase qubit count before preview/save."
        )

    if st.session_state.builder_steps:
        step_rows = []
        for idx, step in enumerate(st.session_state.builder_steps, start=1):
            step_rows.append(
                {
                    "step": idx,
                    "gate": step["gate"],
                    "target": step["target_qubit"],
                    "control_or_second": step.get("control_qubit"),
                    "parameter": step.get("parameter"),
                }
            )
        st.dataframe(pd.DataFrame(step_rows), use_container_width=True, hide_index=True)
    else:
        st.info("No gate steps yet. Add one to start building a circuit.")

    p1, p2 = st.columns(2)
    if p1.button("Preview circuit layout", use_container_width=True, key="builder_preview_btn"):
        preview_payload = {
            "num_qubits": int(builder_num_qubits),
            "steps": st.session_state.builder_steps,
        }
        try:
            st.session_state.builder_preview = client.request(
                "POST",
                "/builder/preview",
                payload=preview_payload,
            )
        except Exception as exc:
            st.error(f"Preview failed: {exc}")

    with p2:
        with st.form("builder_save_form"):
            save_circuit_name = st.text_input("Circuit name", value="My Custom Circuit")
            save_created_by = st.text_input("Created by", value="")
            save_notes = st.text_area("Notes", value="")
            save_submit = st.form_submit_button("Save custom circuit", use_container_width=True)

        if save_submit:
            save_payload = {
                "circuit_name": save_circuit_name,
                "num_qubits": int(builder_num_qubits),
                "created_by": save_created_by or None,
                "notes": save_notes or None,
                "steps": st.session_state.builder_steps,
            }
            try:
                save_result = client.request("POST", "/builder/save", payload=save_payload)
                st.success(
                    f"Saved as {save_result.get('user_circuit_id')} "
                    f"with {save_result.get('step_count')} steps"
                )
                st.cache_data.clear()
            except Exception as exc:
                st.error(f"Save failed: {exc}")

    if st.session_state.builder_preview:
        preview = st.session_state.builder_preview
        st.markdown("**Circuit Preview**")
        st.code("\n".join(preview.get("preview_lines", [])), language="text")
        pm1, pm2 = st.columns(2)
        pm1.metric("Depth", preview.get("depth", 0))
        pm2.metric("Gate count", preview.get("gate_count", 0))

    st.markdown("**Saved custom circuits**")
    l1, l2 = st.columns(2)
    if l1.button("Load recent saved circuits", use_container_width=True, key="builder_list_btn"):
        try:
            list_result = client.request("GET", "/builder/circuits", params={"limit": 25})
            st.session_state.builder_saved_list = list_result.get("data", [])
        except Exception as exc:
            st.error(f"Loading saved circuits failed: {exc}")

    if st.session_state.builder_saved_list:
        st.dataframe(
            pd.DataFrame(st.session_state.builder_saved_list),
            use_container_width=True,
            hide_index=True,
        )

    saved_circuit_id = st.text_input("Saved circuit ID", value="", key="builder_saved_id")
    d1, d2 = st.columns(2)
    if d1.button("View saved circuit", use_container_width=True, key="builder_view_btn"):
        if not saved_circuit_id.strip():
            st.warning("Enter a saved circuit ID first.")
        else:
            try:
                detail_result = client.request("GET", f"/builder/circuits/{saved_circuit_id.strip()}")
                st.json(detail_result.get("circuit", {}))
                st.dataframe(
                    pd.DataFrame(detail_result.get("steps", [])),
                    use_container_width=True,
                    hide_index=True,
                )
            except Exception as exc:
                st.error(f"View failed: {exc}")

    if d2.button("Delete saved circuit", use_container_width=True, key="builder_delete_btn"):
        if not saved_circuit_id.strip():
            st.warning("Enter a saved circuit ID first.")
        else:
            try:
                delete_result = client.request("DELETE", f"/builder/circuits/{saved_circuit_id.strip()}")
                st.success(str(delete_result))
                st.cache_data.clear()
                st.session_state.builder_saved_list = [
                    row for row in st.session_state.builder_saved_list
                    if row.get("user_circuit_id") != saved_circuit_id.strip()
                ]
            except Exception as exc:
                st.error(f"Delete failed: {exc}")


def render_what_if_tab(client: ApiClient):
    st.subheader("Quantum What-If Lab")
    st.caption(
        "Estimate expected fidelity/success for a scenario and get top recommended parameter changes."
    )

    c1, c2, c3 = st.columns(3)
    circuit_id = c1.text_input("Base circuit ID (optional)", value="")
    algorithm = c2.text_input("Algorithm", value="")
    backend = c3.text_input("Scenario backend (optional)", value="")

    c4, c5, c6 = st.columns(3)
    mitigation = c4.text_input("Scenario mitigation (optional)", value="")
    optimization_level = c5.number_input(
        "Optimization level",
        min_value=0,
        max_value=3,
        value=1,
        step=1,
    )
    use_opt = c6.checkbox("Use optimization level", value=False)

    c7, c8, c9 = st.columns(3)
    shots = c7.number_input("Shots", min_value=1, value=1024, step=128)
    depth = c8.number_input("Circuit depth", min_value=1, value=250, step=10)
    qubits = c9.number_input("Qubits used", min_value=1, value=12, step=1)

    c10, c11 = st.columns(2)
    total_error = c10.number_input("Total circuit error", min_value=0.0, max_value=1.0, value=0.05, step=0.005)
    min_samples = c11.slider("Minimum samples for confidence", min_value=3, max_value=40, value=12)

    payload = {
        "circuit_id": circuit_id.strip() or None,
        "algorithm": algorithm.strip() or None,
        "backend": backend.strip() or None,
        "mitigation_technique": mitigation.strip() or None,
        "optimization_level": int(optimization_level) if use_opt else None,
        "shots": int(shots),
        "circuit_depth": int(depth),
        "num_qubits_used": int(qubits),
        "total_circuit_error": float(total_error),
        "min_samples": int(min_samples),
    }

    b1, b2 = st.columns(2)
    if b1.button("Run what-if prediction", use_container_width=True):
        try:
            result = client.request("POST", "/quantum/what-if", payload=payload)
            baseline = result.get("baseline", {})
            scenario = result.get("scenario", {})
            delta = result.get("delta", {})

            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Baseline fidelity", f"{_to_float(baseline.get('predicted_fidelity')):.2%}")
            m2.metric("Scenario fidelity", f"{_to_float(scenario.get('predicted_fidelity')):.2%}", f"{_to_float(delta.get('fidelity')):+.2%}")
            m3.metric("Baseline success", f"{_to_float(baseline.get('predicted_success_rate')):.2%}")
            m4.metric("Scenario success", f"{_to_float(scenario.get('predicted_success_rate')):.2%}", f"{_to_float(delta.get('success_rate')):+.2%}")

            low_sample_msg = []
            if baseline.get("is_low_sample"):
                low_sample_msg.append("baseline")
            if scenario.get("is_low_sample"):
                low_sample_msg.append("scenario")
            if low_sample_msg:
                st.warning(f"Low sample confidence for: {', '.join(low_sample_msg)}")

            st.json(result)
        except Exception as exc:
            st.error(f"What-if prediction failed: {exc}")

    if b2.button("Get top recommendations", use_container_width=True):
        try:
            rec_payload = payload.copy()
            rec_payload["top_k"] = 3
            rec_result = client.request(
                "POST",
                "/quantum/what-if/recommendations",
                payload=rec_payload,
            )
            recs = pd.DataFrame(rec_result.get("recommendations", []))
            if recs.empty:
                st.info("No recommendations available for the selected constraints.")
            else:
                st.dataframe(recs, use_container_width=True, hide_index=True)
        except Exception as exc:
            st.error(f"Recommendation request failed: {exc}")


def render_quality_tab(client: ApiClient):
    st.subheader("Data Quality Dashboard")
    st.caption("Monitor out-of-range values, orphan rows, and null-heavy columns.")

    try:
        report = client.request("GET", "/quality/report")
    except Exception as exc:
        st.error(f"Failed to load quality report: {exc}")
        return

    m1, m2, m3 = st.columns(3)
    m1.metric("Total circuits", f"{_to_int(report.get('total_circuits')):,}")
    m2.metric("Soft-deleted circuits", f"{_to_int(report.get('soft_deleted_circuits')):,}")
    m3.metric("Out-of-range metrics", f"{_to_int(report.get('out_of_range_metrics')):,}")

    st.markdown("**Orphan rows by table**")
    orphan_df = pd.DataFrame(
        [
            {"table": k, "orphan_rows": v}
            for k, v in (report.get("orphan_rows") or {}).items()
        ]
    )
    if not orphan_df.empty:
        st.dataframe(orphan_df, use_container_width=True, hide_index=True)

    st.markdown("**High-null columns (>= 30%)**")
    high_null_df = pd.DataFrame(report.get("high_null_columns") or [])
    if high_null_df.empty:
        st.success("No high-null columns detected at the current threshold.")
    else:
        st.dataframe(high_null_df, use_container_width=True, hide_index=True)

    st.markdown("**Null profile details**")
    null_profile = report.get("null_profile") or {}
    table_choice = st.selectbox("Table", options=list(null_profile.keys()) if null_profile else ["circuits"])
    selected = null_profile.get(table_choice, {})
    selected_cols = selected.get("columns") or {}
    detail_df = pd.DataFrame(
        [
            {
                "column": col,
                "null_count": info.get("null_count"),
                "null_ratio": info.get("null_ratio"),
            }
            for col, info in selected_cols.items()
        ]
    )
    if not detail_df.empty:
        st.dataframe(detail_df, use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("Data Lineage and SQL Used")
    st.caption("Shows how quality metrics are computed from the database and PostgreSQL-equivalent SQL.")

    try:
        lineage = client.request("GET", "/quality/lineage")
    except Exception as exc:
        st.warning(f"Could not load SQL lineage details: {exc}")
        return

    source_db = lineage.get("source_database") or {}
    target_db = lineage.get("target_database") or {}

    d1, d2 = st.columns(2)
    d1.info(
        "\n".join(
            [
                f"Source DB Engine: {source_db.get('engine', 'unknown')}",
                f"Driver: {source_db.get('driver', 'unknown')}",
                f"Path: {source_db.get('path', 'unknown')}",
            ]
        )
    )
    d2.info(
        "\n".join(
            [
                f"Target DB Engine: {target_db.get('engine', 'unknown')}",
                str(target_db.get("note", "")),
            ]
        )
    )

    checks = lineage.get("quality_checks") or []
    if not checks:
        st.info("No SQL lineage checks returned by backend.")
        return

    st.markdown("**Database transition view**")
    flow_labels = [
        "SQLite DB",
        "Quality SQL checks",
        "FastAPI /quality/report",
        "Data Quality tab",
        "PostgreSQL equivalent SQL",
    ]
    flow_sources = [0, 1, 2, 1]
    flow_targets = [1, 2, 3, 4]
    flow_values = [len(checks), len(checks), len(checks), len(checks)]
    transition_fig = go.Figure(
        data=[
            go.Sankey(
                arrangement="snap",
                node={
                    "label": flow_labels,
                    "pad": 16,
                    "thickness": 18,
                },
                link={
                    "source": flow_sources,
                    "target": flow_targets,
                    "value": flow_values,
                },
            )
        ]
    )
    transition_fig.update_layout(margin={"l": 10, "r": 10, "t": 10, "b": 10}, height=300)
    st.plotly_chart(transition_fig, use_container_width=True)

    st.markdown("**Quality checks covered**")
    st.dataframe(
        pd.DataFrame([{"check": c.get("name", "") } for c in checks]),
        use_container_width=True,
        hide_index=True,
    )

    selected_check = st.selectbox(
        "Choose a quality check to inspect SQL",
        options=[c.get("name", "") for c in checks],
        key="quality_sql_check_select",
    )

    selected_payload = next((c for c in checks if c.get("name", "") == selected_check), {})
    sql_tab, pg_tab = st.tabs(["SQLite SQL", "PostgreSQL SQL"])
    with sql_tab:
        st.code(selected_payload.get("sqlite", ""), language="sql")
    with pg_tab:
        st.code(selected_payload.get("postgresql", ""), language="sql")

    test_queries = lineage.get("test_queries") or {}
    sqlite_tests = test_queries.get("sqlite") or []
    postgres_tests = test_queries.get("postgresql") or []

    st.markdown("**Test queries you can run**")
    tq_sqlite_tab, tq_postgres_tab = st.tabs(["SQLite test queries", "PostgreSQL test queries"])

    with tq_sqlite_tab:
        if not sqlite_tests:
            st.info("No SQLite test queries available.")
        else:
            sqlite_title = st.selectbox(
                "Pick a SQLite query",
                options=[q.get("title", "") for q in sqlite_tests],
                key="quality_sqlite_test_query_select",
            )
            sqlite_query = next((q for q in sqlite_tests if q.get("title", "") == sqlite_title), {})
            st.code(sqlite_query.get("sql", ""), language="sql")

    with tq_postgres_tab:
        if not postgres_tests:
            st.info("No PostgreSQL test queries available.")
        else:
            postgres_title = st.selectbox(
                "Pick a PostgreSQL query",
                options=[q.get("title", "") for q in postgres_tests],
                key="quality_postgres_test_query_select",
            )
            postgres_query = next((q for q in postgres_tests if q.get("title", "") == postgres_title), {})
            st.code(postgres_query.get("sql", ""), language="sql")

    st.markdown("**Run query and view output (SQLite live DB)**")
    if sqlite_tests:
        runner_options = [q.get("title", "") for q in sqlite_tests] + ["Custom query"]
        selected_runner_query = st.selectbox(
            "Pick a query to run",
            options=runner_options,
            key="quality_query_runner_select",
        )
        if selected_runner_query == "Custom query":
            default_runner_sql = "SELECT * FROM circuits LIMIT 20;"
        else:
            selected_runner_payload = next(
                (q for q in sqlite_tests if q.get("title", "") == selected_runner_query),
                {},
            )
            default_runner_sql = selected_runner_payload.get("sql", "")
    else:
        default_runner_sql = "SELECT * FROM circuits LIMIT 20;"

    runner_sql = st.text_area(
        "SQLite SQL (read-only SELECT/WITH only)",
        value=default_runner_sql,
        height=180,
        key="quality_query_runner_sql",
    )
    runner_limit = st.slider("Maximum rows to return", min_value=10, max_value=500, value=100)

    if st.button("Run quality query", key="quality_query_runner_run", use_container_width=True):
        try:
            runner_out = client.request(
                "POST",
                "/quality/query/execute",
                payload={"sql": runner_sql, "limit": runner_limit},
            )
            st.success(f"Returned {runner_out.get('row_count', 0)} rows")
            if runner_out.get("truncated"):
                st.caption(f"Result truncated at {runner_out.get('limit')} rows.")

            out_df = pd.DataFrame(runner_out.get("rows") or [])
            if out_df.empty:
                st.info("Query ran successfully but returned no rows.")
            else:
                st.dataframe(out_df, use_container_width=True, hide_index=True)
        except Exception as exc:
            st.error(f"Query execution failed: {exc}")


def main():
    st.sidebar.title("Dashboard Settings")
    api_base = st.sidebar.text_input("FastAPI base URL", value=DEFAULT_API_BASE)
    api_key = st.sidebar.text_input("API key", value=DEFAULT_API_KEY, type="password")
    api_mode = st.sidebar.selectbox(
        "API mode",
        ["Auto", "Remote API", "Managed FastAPI"],
        index=0,
        help="Auto tries remote first and falls back to a managed local FastAPI started by Streamlit.",
    )

    refresh_mode = st.sidebar.selectbox("Refresh mode", ["Manual", "Auto"])
    refresh_seconds = st.sidebar.selectbox("Auto refresh interval", [10, 15, 30], index=1)
    st.sidebar.caption(
        "Refresh logic: use Manual for slower-changing data and Auto for near-real-time updates."
    )

    if st.sidebar.button("Refresh now"):
        st.cache_data.clear()
        st.rerun()

    if refresh_mode == "Auto":
        if st_autorefresh is None:
            st.sidebar.warning("Install streamlit-autorefresh for auto polling support.")
        else:
            st_autorefresh(interval=refresh_seconds * 1000, key="dashboard_api_refresh")

    try:
        client, resolved_mode = build_api_client(api_mode, api_base, api_key)
    except Exception as exc:
        st.error(f"API initialization failed: {exc}")
        st.stop()

    st.sidebar.caption(f"Connected mode: {resolved_mode}")
    ensure_builder_state()

    st.title("Quantum Circuit DBMS Dashboard (API-driven)")
    st.caption("All dashboard data is fetched from authenticated FastAPI endpoints.")

    try:
        health = client.request("GET", "/health")
        st.success(
            f"Connected to API. Total circuits in DB: {health.get('total_circuits', 'unknown')}"
        )
    except Exception as exc:
        st.error(f"API connection failed: {exc}")
        st.stop()

    tab_overview, tab_search, tab_crud, tab_compare, tab_builder, tab_what_if, tab_quality = st.tabs(
        [
            "Overview",
            "Search & Filter",
            "CRUD",
            "Compare",
            "Qubit Builder",
            "What-If Lab",
            "Data Quality",
        ]
    )

    with tab_overview:
        render_overview_tab(client)

    with tab_search:
        render_search_filter_tab(client)

    with tab_crud:
        render_crud_tab(client)

    with tab_compare:
        render_compare_tab(client)

    with tab_builder:
        render_builder_tab(client)

    with tab_what_if:
        render_what_if_tab(client)

    with tab_quality:
        render_quality_tab(client)


if __name__ == "__main__":
    main()
