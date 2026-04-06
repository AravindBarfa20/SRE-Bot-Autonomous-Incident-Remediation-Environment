# SRE-Bot 🚀

**A Production-Grade, Autonomous Incident Remediation Environment for Agentic SRE Evaluation.**

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
