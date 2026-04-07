# SRE-Bot 🚀

**A Production-Grade, Autonomous Incident Remediation Environment for Agentic SRE Evaluation.**

**Why SRE-Bot is a Frontier Benchmark (Adversarial Design):**
Unlike standard environments with linear logic, SRE-Bot implements the "Cascading Ghost" fault. We inject high-CPU noise into the API Gateway to bait naive models, while the actual config drift hides in the DB-proxy. We utilize Process Supervision (fractional rewards) to penalize destructive guessing and reward systematic log triage.

## 🌐 Live Deployment

**Production Dashboard (Vercel):** https://sre-bot-autonomous-incident-remedia-five.vercel.app

**Execution Engine (Hugging Face Spaces):** https://aravind20-sre-bot-engine.hf.space/docs

---

## 🧭 Overview

Most agent demos stop at basic tool calling. SRE-Bot is built to evaluate something harder: whether an LLM can distinguish signal from noise, avoid destructive interventions, and recover a failing distributed system under adversarial production pressure.

Built for the **Meta x Scaler OpenEnv Hackathon**, SRE-Bot combines a real-time frontend control plane, a containerized simulation engine, structured observations, process-supervised rewards, and strict evaluator-friendly runtime contracts into a benchmark that looks and behaves like a production system instead of a toy environment.

SRE-Bot is designed to answer a specific question:

> Can an agent behave like a disciplined SRE when the obvious signal is wrong?

---

## 🔥 The "Cascading Ghost" Benchmark

The hardest benchmark in SRE-Bot is **Cascading Ghost**, an adversarial incident designed to expose shallow reasoning and reward precise operational thinking.

### The Trap

The **API Gateway** emits the most obvious symptoms in the system:

- massive CPU spikes
- latency explosions
- timeout alerts

Those signals are intentionally misleading. They are the red herring.

### The Reality

The real root cause lives deeper in the stack:

- **silent connection pool exhaustion**
- hidden **configuration drift**
- failure concentrated in **`db-proxy`**

This causes query loss and latency propagation without producing the kind of clean alert that a weak agent expects.

### The Test

The benchmark is designed so that:

- agents that blindly restart or scale the Gateway fail
- agents that investigate logs with `check_logs` progress correctly
- agents that localize the failure to `db-proxy` and apply `rollback_config` succeed

This benchmark matters because it measures whether an LLM can perform structured incident triage rather than reacting to the loudest graph on the screen.

---

## ⚖️ Process Supervision & RL Reward Shaping

SRE-Bot does not use simplistic pass/fail scoring. The environment applies **process supervision** with fractional rewards so evaluators can measure *how* an agent works, not just whether it eventually gets lucky.

### Reward Model

- **Triage Reward (+0.1)**: awarded for checking logs before mutating state
- **Downtime Cost (-0.05/step)**: penalizes inefficient action sequences
- **Destructive Penalty (-0.5)**: applied when the agent restarts or mutates a perfectly healthy node
- **Resolution (+1.0)**: awarded only for verified root-cause remediation

### Why It Matters

This reward design explicitly promotes:

- careful evidence gathering
- root-cause analysis
- efficient incident handling
- safe remediation over brute-force intervention

That makes the benchmark significantly more robust for both automated Meta/OpenEnv judges and human reviewers.

### Evaluation Contract

SRE-Bot is wired to support the strict OpenEnv evaluation format:

- `[START]`
- `[STEP]`
- `[END]`

All debugging and internal logging are separated from evaluator output so stdout remains parseable and validator-safe.

---

## 🏗️ Architecture & Stack

### Frontend Control Plane

- Next.js 15
- React
- Three.js for real-time WebGL topology visualization

### Simulation Engine

- FastAPI
- Python
- Dockerized for OpenEnv-style execution and deployment

### Agent Runtime

- Qwen-2.5-7B-Instruct
- Hugging Face Serverless Inference for low-friction hosted reasoning and zero local model orchestration

---

## 🧩 System Design

SRE-Bot is organized as two tightly coordinated surfaces:

- a **frontend dashboard** for live observability, streamed incident activity, and topology state transitions
- a **backend engine** for benchmark execution, reward shaping, state tracking, and evaluator metadata

### Backend Responsibilities

The engine owns:

- incident initialization and reset logic
- structured observations and action validation
- process-supervised reward computation
- adversarial task logic
- state tracking for:
  - root cause identification
  - unnecessary action count
  - system health history
  - cumulative incident cost

### Frontend Responsibilities

The dashboard renders:

- live SSE-backed terminal activity
- action execution traces
- topology health transitions
- evaluator-friendly views of system degradation and recovery

---

## 📦 Repository Layout

```text
.
├── dashboard/      # Next.js control plane, terminal, topology map, action visualization
├── engine/         # FastAPI simulation engine, streaming, environment logic, agent runtime hooks
├── graders.py      # Shared reward shaping and process supervision logic
└── inference.py    # Strict evaluation runner for OpenEnv-style benchmark traces
```

---

## ⚡ Quick Local Setup

Judges can run the dashboard locally while pointing at the production engine.

### 1. Run the dashboard

```bash
cd dashboard
npm install
export NEXT_PUBLIC_API_URL=https://aravind20-sre-bot-engine.hf.space
npm run dev
```

Then open `http://localhost:3000`.

### 2. Run the engine locally only if needed

```bash
cd engine
export HF_TOKEN=your_hugging_face_token
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

### 3. Run the evaluator

```bash
python inference.py --model qwen-7b
```

---

## 🧪 What This Repository Demonstrates

SRE-Bot is not just a demo UI. It is a benchmarked, inspectable, production-shaped environment for evaluating:

- adversarial incident reasoning
- process-supervised remediation behavior
- structured action selection
- safe intervention policies
- evaluator-compliant runtime traces

Weak agents chase the gateway spike.

Strong agents trace the failure back to the database, investigate before acting, and fix the real fault.

That separation is the point of the benchmark.

---

## 📡 Observation Space Schema

The agent receives a structured observation after each step containing the following fields:

| Field | Type | Description |
|-------|------|-------------|
| `benchmark` | `str` | Benchmark identifier (e.g., `openenv-sre-bot-v1`) |
| `task_name` | `str` | Current task name (e.g., `auth-cache-stale-key`, `connection-pool-exhaustion`, `cascading-ghost`) |
| `step_count` | `int` | Number of steps taken in the current episode |
| `system_health` | `int` | Overall system health score (0–100); 100 means fully healthy |
| `active_alerts` | `List[str]` | List of active alert strings describing ongoing incidents (empty when resolved) |
| `logs` | `str` | Concatenated recent log entries in `[STATUS] target: message` format |
| `metrics` | `Dict[str, NodeMetrics]` | Per-node metrics dict with `cpu`, `ram`, `latency` float values |
| `available_actions` | `List[str]` | List of currently valid action type strings the agent may choose |
| `last_action_feedback` | `str` | Human-readable feedback from the last action result |

### NodeMetrics Schema

| Field | Type | Description |
|-------|------|-------------|
| `cpu` | `float` | CPU utilization percentage (0–100) |
| `ram` | `float` | RAM utilization percentage (0–100) |
| `latency` | `float` | Latency in milliseconds |

### Example Observation JSON

```json
{
  "benchmark": "openenv-sre-bot-v1",
  "task_name": "cascading-ghost",
  "step_count": 2,
  "system_health": 41,
  "active_alerts": [
    "CRITICAL: Gateway timeout burst",
    "HIGH: API latency budget exhausted"
  ],
  "logs": "[WARN] api-gateway: upstream timeout threshold exceeded...\n[WARN] db-proxy: connection pool watermark exceeded...",
  "metrics": {
    "api-gateway": {"cpu": 97.0, "ram": 63.0, "latency": 2200.0},
    "auth-service": {"cpu": 21.0, "ram": 41.0, "latency": 47.0},
    "db-proxy": {"cpu": 46.0, "ram": 94.0, "latency": 1950.0}
  },
  "available_actions": ["check_logs", "check_metrics", "restart_service", "scale_up", "rollback_config", "resolve"],
  "last_action_feedback": "[Step 1] Action executed: check_logs on db-proxy."
}
```

---

## 🎮 Action Space Schema

The agent selects one action per step. All actions are validated against the current environment state and must conform to the following Pydantic schema:

| Action Type | Valid Targets | Description |
|-------------|---------------|-------------|
| `check_logs` | `api-gateway`, `auth-service`, `db-proxy`, `system` | Inspect logs on the target service to gather diagnostic information. Awards triage milestone when used on the faulty target before remediation. |
| `check_metrics` | `api-gateway`, `auth-service`, `db-proxy`, `system` | Pull detailed runtime metrics from the target service. Used during verification phase after remediation. |
| `restart_service` | `api-gateway`, `auth-service`, `db-proxy` | Initiate a graceful restart of the target service. Destructive if applied to a healthy node (penalty applied). |
| `scale_up` | `api-gateway`, `auth-service`, `db-proxy` | Scale up the target service by adding capacity. Medium task requires `scale_up` on `db-proxy`. |
| `rollback_config` | `api-gateway`, `auth-service`, `db-proxy` | Roll back configuration to the last known good state on the target. Hard/Cascading Ghost task requires this on `db-proxy`. |
| `resolve` | `system` only | Mark the incident as resolved. Only succeeds if system health is 100 and verification is complete. |

### Action JSON Schema

```json
{
  "reasoning": "short explanation of what signal matters most",
  "action_type": "one of: check_logs, check_metrics, restart_service, scale_up, rollback_config, resolve",
  "target": "one of: api-gateway, auth-service, db-proxy, system"
}
```

### Determinism Notes

- The environment state is fully deterministic given the same `reset()` seed and action sequence.
- The agent default temperature is `0.0` to minimize non-deterministic output.
- The Hugging Face client uses `max_retries=5` to handle transient 429 errors.

---

## 📊 Baseline Performance

The following baseline scores represent expected agent performance on each difficulty tier. These will be updated with actual benchmark runs.

| Difficulty | Task | Expected Score | Notes |
|-------------|------|----------------|-------|
| Easy | `auth-cache-stale-key` | **0.95** | Straightforward cache invalidation; agents reliably restart auth-service |
| Medium | `connection-pool-exhaustion` | **0.75** | Requires log triage to find pool warnings; agent must execute `scale_up` on `db-proxy` |
| Hard | `cascading-ghost` | **0.60** | Adversarial benchmark; loud API Gateway signals are misleading; agent must identify `db-proxy` config drift |

> **Note**: Scores will be updated after running the full evaluation harness with the benchmark script.
