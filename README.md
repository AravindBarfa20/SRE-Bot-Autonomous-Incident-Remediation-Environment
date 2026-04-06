# SRE-Bot (ContraCulture) 🚀

**A Production-Grade, Autonomous Incident Remediation Environment for Agentic SRE Evaluation.**

SRE-Bot is a full-stack OpenEnv-style benchmark and control plane for evaluating whether LLM agents can reason like real Site Reliability Engineers under adversarial production pressure. It combines a live observability dashboard, a containerized FastAPI execution engine, structured state transitions, reward shaping, and process-supervised remediation loops into one submission-ready environment.

## Live Production

🌍 Dashboard (Vercel): https://sre-bot-autonomous-incident-remedia-five.vercel.app

🧠 Engine (Hugging Face Spaces): https://aravind20-sre-bot-engine.hf.space/docs

---

## Why This Project Exists

Most agent demos stop at tool calling and a pretty UI. SRE-Bot is designed to evaluate something harder: whether an LLM can distinguish signal from noise, inspect evidence before acting, avoid destructive interventions, and recover a failing distributed system with the same operational discipline expected from a production on-call engineer.

This repository is built for the Meta x Scaler OpenEnv Hackathon and optimized around three principles:

- **Observability-first reasoning**: the agent must act on logs, metrics, and explicit environment state.
- **Process supervision over binary scoring**: the environment rewards good investigative behavior, not just lucky fixes.
- **Adversarial realism**: the hardest benchmark is intentionally deceptive and punishes brute-force remediation.

---

## 🔥 The "Cascading Ghost" Benchmark

The flagship benchmark in SRE-Bot is **`cascading-ghost`**, our adversarial hard task designed to break shallow reasoning and reward disciplined investigation.

### Scenario

- The **Gateway** presents the obvious symptoms: elevated CPU, severe latency, and timeout alerts.
- Those symptoms are a **red herring**.
- The actual root cause sits deeper in the stack: **silent connection pool exhaustion / config drift in `db-proxy`**, causing dropped queries and downstream latency amplification without loud, clean alerts.

### Why It Matters

This benchmark forces an agent to do what strong SREs do in real incidents:

- ignore the first noisy metric spike instead of chasing the hottest graph
- trace latency propagation across services
- perform active investigation with `check_logs`
- identify the hidden fault domain in `db-proxy`
- apply the precise corrective action `rollback_config`
- avoid panic moves like restarting or scaling healthy infrastructure

In other words, the benchmark is explicitly designed to separate thoughtful operators from brute-force tool users.

---

## ⚖️ Reward Shaping & Process Supervision

SRE-Bot does not rely on simplistic binary success labels. The environment uses **fractional rewards** to supervise both *how* the agent works and *whether* it resolves the incident correctly.

### Reward Components

- **Cost of downtime penalty**: `-0.05` per step
- **Triage reward**: `+0.1` for checking logs on the true faulty service before attempting a fix
- **Destructive penalty**: `-0.5` for restarting or modifying a healthy node
- **Resolution reward**: `+1.0` only when the root cause is actually fixed and verified

### Process Supervision Design

The reward model explicitly encourages:

- evidence gathering before intervention
- minimizing unnecessary actions
- root-cause resolution instead of symptom suppression
- operational efficiency under time pressure

This makes the benchmark significantly more robust for both automated judges and human evaluators because the environment can distinguish:

- lucky success
- safe triage
- destructive guesswork
- precise, verified remediation

### Evaluation Contract

The evaluation loop is implemented with strict stdout/stderr separation so it can satisfy judge parsers cleanly:

- stdout emits only the OpenEnv-style control tokens:
  - `[START]`
  - `[STEP]`
  - `[END]`
- stderr is reserved for logging, warnings, and debugging noise

This keeps the run trace deterministic and validator-friendly.

---

## Architecture & Stack

- **Frontend**: Next.js 15, Three.js (WebGL topology visualization), React
- **Backend Engine**: FastAPI, Docker, containerized for OpenEnv-style deployment and Hugging Face Spaces hosting
- **Agent Runtime**: Qwen-2.5-7B-Instruct via the Hugging Face Inference API for low-latency reasoning and clean browser-to-engine connectivity

---

## System Design

SRE-Bot is split into two cooperating surfaces:

- a **frontend control plane** for live incident visualization, terminal streaming, and action playback
- a **backend incident engine** that owns benchmark scenarios, reward shaping, state transitions, and evaluator-visible metadata

### Backend Responsibilities

The engine is responsible for:

- generating structured observations
- maintaining benchmark-specific hidden state
- executing remediation actions
- computing reward breakdowns
- tracking evaluator-facing incident metadata such as:
  - root-cause identification
  - unnecessary action count
  - system health history
  - cumulative incident cost

### Frontend Responsibilities

The dashboard is responsible for:

- consuming SSE logs from the engine
- rendering topology health transitions
- showing adversarial terminal output
- exposing remediation progress in a human-readable format for judges and reviewers

---

## Repository Layout

```text
.
├── dashboard/      # Next.js control plane, SSE client, topology map, terminal, action ledger
├── engine/         # FastAPI environment engine, reward logic, streaming transport, agent interface
├── graders.py      # Shared grading/reward logic for evaluator-facing process supervision
└── inference.py    # Strict evaluation runner emitting [START]/[STEP]/[END]
```

---

## Local Setup

For evaluators, local setup is intentionally minimal.

### 1. Run the frontend against the live production engine

```bash
cd dashboard
npm install
export NEXT_PUBLIC_API_URL=https://aravind20-sre-bot-engine.hf.space
npm run dev
```

Then open `http://localhost:3000`.

### 2. Run the backend locally only if you want a full local stack

```bash
cd engine
export HF_TOKEN=your_hugging_face_token
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

### 3. Run the strict evaluator locally

```bash
python inference.py --model qwen-7b
```

---

## What Judges Can Inspect

SRE-Bot exposes both human-facing and evaluator-facing surfaces:

- **Live dashboard** for visual inspection of topology state and incident progression
- **Swagger docs** for API inspection and backend validation
- **Structured state metadata** through `/state` and `/api/state`
- **Strict evaluator trace** via `inference.py`

This makes the project simultaneously:

- easy to demo
- easy to inspect
- easy to validate
- hard to game

---

## Submission Focus

This repository is optimized for the exact dimensions that matter in an OpenEnv-style benchmark:

- adversarial task quality
- process-supervised reward shaping
- strict evaluator output contracts
- production-grade deployment
- transparent debugging surfaces for judges

If the benchmark is doing its job, weak agents will chase the gateway spike, while strong agents will investigate, localize, and surgically repair the database drift.

That separation is the point.
