# CS 4063 - Natural Language Processing
## Assignment 5: Evaluation Suite for Conversational AI

### Project
**La Bella Tavola Conversational Reservation Assistant**

### Group Members
1. Mohammad Haider Abbas (23i-2558)  
2. Hamdul Haq (23i-0081)  
3. Ayesha Ikram (23i-0109)

## Links
- **GitHub Repository:** `<ADD_GITHUB_REPO_LINK>`
- **Vercel Deployment:** `<ADD_VERCEL_LINK>`
- **Demo Video (Unlisted YouTube, optional but recommended):** `<ADD_VIDEO_LINK>`

## Overview
This repository contains:
- A restaurant-domain conversational assistant (chat + tools + RAG),
- And a complete **Assignment 5 evaluation pipeline** that measures:
  - overall conversational correctness,
  - component-level correctness (RAG, CRM, tools),
  - latency and throughput performance.

Domain: **La Bella Tavola** (restaurant reservations, menu/weather/helpdesk queries).

---

## System Architecture
- **Frontend:** React (`src/`)  
- **Backend API:** FastAPI + WebSocket (`server/api.py`)  
- **Dialogue Orchestration:** `server/conversation_manager.py`  
- **Prompting Logic:** `server/prompt_templates.py`  
- **RAG:** Chroma + sentence-transformers (`rag/`)  
- **Tools:** CRM JSON store, menu search, weather API, SQLite reservation lookup (`server/tools/`)
- **Model Runtime:** Ollama local inference (`qwen2.5:3b-instruct`)

---

## Assignment 5 Deliverables Implemented

### 1) Source code of evaluation suite
- `run_evals.py` (entry point)
- `evals/run_evals.py` (main evaluation pipeline)

### 2) Test data
- `evals/data/conversations.json` (10 multi-turn dialogues)
- `evals/data/rag_ground_truth.json` (20 retrieval queries + relevance labels)
- `evals/data/tool_invocation_cases.json` (tool-call accuracy set)
- `evals/data/rag_faithfulness_questions.json` (30 faithfulness prompts)

### 3) Auto-generated report artifacts
Generated per run inside `evals/results/`:
- `eval_report_<timestamp>.json`
- `eval_report_<timestamp>.md`
- `concurrency_vs_latency_<timestamp>.png`
- `scenario_vs_latency_<timestamp>.png`

### 4) README documentation
This file provides setup, execution, metrics definitions, assumptions, and interpretation guidance.

### 5) Demo video
Add the unlisted YouTube URL in the Links section above.

---

## Setup

### Prerequisites
- Python 3.11+ (project currently tested on Python 3.12)
- Node.js 18+
- Ollama installed and running
- Model pulled locally:

```bash
ollama pull qwen2.5:3b-instruct
```

### Install dependencies

Backend/eval dependencies:
```bash
cd server
python -m venv .venv
.venv\Scripts\activate
pip install -r "..\requirements.txt"
```

Frontend dependencies:
```bash
cd ..
npm install
```

---

## Run the Assistant

### Terminal 1: Backend
```bash
cd server
.venv\Scripts\activate
uvicorn api:app --host 0.0.0.0 --port 8000
```

### Terminal 2: Frontend
```bash
npm run dev
```

Frontend default URL: `http://localhost:5173`  
Backend health check: `http://localhost:8000/health`

---

## Run Assignment 5 Evaluations

### Terminal 3: Evals
```bash
cd server
.venv\Scripts\activate
cd ..
set OLLAMA_MODEL=qwen2.5:3b-instruct
python run_evals.py
```

Optional env vars:
- `EVAL_API_BASE` (default: `http://localhost:8000`)
- `EVAL_TRIALS` (default: `30`)

---

## Metrics Computed

### Overall Conversational Correctness
- **Task Completion Rate** = successful_dialogues / total_dialogues
- **Policy Adherence Rate** = policy-compliant_dialogues / total_dialogues
- **Coherence Rate** = coherence-passing_dialogues / total_dialogues

### Component-Level Correctness
- **RAG Retrieval:** precision@k, recall@k, MRR, context relevance
- **RAG Faithfulness:** lexical-support heuristic score over 30 Q/A pairs
- **CRM CRUD correctness:** create/read/update/cancel checks
- **Tool functional correctness:** valid/invalid input handling checks
- **Tool invocation accuracy:** expected tool vs predicted tool + false positives

### Performance
- **TTFT:** first token time from request start
- **Inter-token latency:** mean delta between streamed tokens
- **End-to-end latency:** request start to final token/end event
- **Throughput:** turns per second under increasing concurrency
- Includes mean, median, p90, p99 and 95% confidence intervals (for means).

---

## Failure-Mode Coverage
The suite includes explicit negative-path checks for:
- missing/empty vector DB handling,
- external tool API failure handling,
- malformed tool-call input handling.

---

## Interpretation Guide
- High correctness + low latency = reliable user experience.
- If throughput shows low sustainable concurrency, CPU/model inference is likely the bottleneck.
- If task completion is lower than policy/coherence, prioritize intent and tool-routing fixes.
- If faithfulness drops, improve retrieval relevance and prompt grounding.

---

## Assumptions and Limitations
- Faithfulness is measured with an offline lexical-support heuristic for reproducibility.
- This heuristic is weaker than entailment metrics (e.g., RAGAS faithfulness).
- Mixed RAG+tool scenario is approximated via a compound query.
- Performance numbers are hardware-dependent; run on a quiet machine.

---

## Repository Structure (Key Paths)
- `server/` - backend API and orchestration
- `rag/` - vector retrieval components
- `server/tools/` - CRM/menu/weather/lookup tools
- `evals/` - evaluation harness + data + results
- `run_evals.py` - one-command evaluation entry point

---

## Notes for Grading
- The evaluation suite is fully automated and reproducible via `python run_evals.py`.
- Reports include metrics, failure logs, hardware/dependency snapshots, and plots required for analysis.
- Any known model/system weaknesses are surfaced transparently in report analysis.
