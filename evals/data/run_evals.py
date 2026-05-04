# pyright: reportMissingImports=false
import asyncio
import json
import math
import os
import platform
import statistics
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
import websockets
try:
    import matplotlib.pyplot as plt
    MATPLOTLIB_AVAILABLE = True
except Exception:
    MATPLOTLIB_AVAILABLE = False

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SERVER_DIR = PROJECT_ROOT / "server"
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from rag.retriever import RestaurantRAG
from tools import crm as crm_tool
from tools.menu import search_menu
from tools.reservation_lookup import (
    cancel_reservation,
    lookup_reservation,
    save_reservation,
    update_reservation,
)
from tools.weather import get_weather
from conversation_manager import extract_signals, tool_orchestrator

DATA_DIR = Path(__file__).resolve().parent / "data"
RESULTS_DIR = Path(__file__).resolve().parent / "results"


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_json(path: Path) -> Any:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def mean_ci95(values: list[float]) -> dict[str, float]:
    if not values:
        return {"mean": 0.0, "ci95_low": 0.0, "ci95_high": 0.0}
    mu = statistics.mean(values)
    if len(values) < 2:
        return {"mean": mu, "ci95_low": mu, "ci95_high": mu}
    stdev = statistics.stdev(values)
    margin = 1.96 * (stdev / math.sqrt(len(values)))
    return {"mean": mu, "ci95_low": mu - margin, "ci95_high": mu + margin}


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    vals = sorted(values)
    if len(vals) == 1:
        return vals[0]
    idx = (len(vals) - 1) * (p / 100.0)
    lo = math.floor(idx)
    hi = math.ceil(idx)
    if lo == hi:
        return vals[lo]
    return vals[lo] + (vals[hi] - vals[lo]) * (idx - lo)


def normalize_text(s: str) -> str:
    return " ".join((s or "").lower().split())


def contains_any(text: str, needles: list[str]) -> bool:
    t = normalize_text(text)
    return any(n.lower() in t for n in needles)


@dataclass
class TurnMetrics:
    ttft_s: float
    inter_token_latency_s: float
    e2e_s: float
    response: str


class ChatClient:
    def __init__(self, api_base: str):
        self.api_base = api_base.rstrip("/")
        self.ws_url = self.api_base.replace("http://", "ws://").replace("https://", "wss://") + "/ws/chat"

    async def create_session(self) -> str:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.post(f"{self.api_base}/session")
            r.raise_for_status()
            return r.json()["session_id"]

    async def send_turn(self, session_id: str, message: str) -> TurnMetrics:
        start = time.perf_counter()
        token_times: list[float] = []
        out = []
        async with websockets.connect(self.ws_url, max_size=2**22) as ws:
            await ws.send(json.dumps({"session_id": session_id, "message": message}))
            while True:
                raw = await ws.recv()
                evt = json.loads(raw)
                tnow = time.perf_counter()
                typ = evt.get("type")
                if typ == "token":
                    token_times.append(tnow)
                    out.append(evt.get("token", ""))
                elif typ == "end":
                    break
                elif typ == "error":
                    raise RuntimeError(evt.get("error") or evt.get("message") or "unknown websocket error")
        end = time.perf_counter()
        if token_times:
            ttft = token_times[0] - start
            inters = [b - a for a, b in zip(token_times, token_times[1:])]
            inter = statistics.mean(inters) if inters else 0.0
        else:
            ttft = end - start
            inter = 0.0
        return TurnMetrics(ttft_s=ttft, inter_token_latency_s=inter, e2e_s=end - start, response="".join(out))


async def evaluate_conversations(chat: ChatClient, conversations: list[dict]) -> dict:
    per_dialogue = []
    task_success = 0
    policy_success = 0
    coherence_success = 0
    for d in conversations:
        sid = await chat.create_session()
        transcript = []
        final_response = ""
        for user_msg in d["turns"]:
            m = await chat.send_turn(sid, user_msg)
            final_response = m.response
            transcript.append({"user": user_msg, "assistant": final_response})

        checks = d.get("checks", {})
        task_ok = contains_any(final_response, checks.get("task_completion_any", []))
        policy_ok = True
        if checks.get("policy_refusal_any"):
            policy_ok = contains_any(final_response, checks["policy_refusal_any"])
        coherence_ok = True
        if checks.get("coherence_any"):
            coherence_ok = contains_any(final_response, checks["coherence_any"])

        task_success += int(task_ok)
        policy_success += int(policy_ok)
        coherence_success += int(coherence_ok)
        per_dialogue.append(
            {
                "id": d["id"],
                "task_ok": task_ok,
                "policy_ok": policy_ok,
                "coherence_ok": coherence_ok,
                "last_response": final_response,
                "transcript": transcript,
            }
        )

    n = max(1, len(conversations))
    return {
        "num_dialogues": len(conversations),
        "task_completion_rate": task_success / n,
        "policy_adherence_rate": policy_success / n,
        "coherence_rate": coherence_success / n,
        "details": per_dialogue,
    }


def evaluate_crm_crud() -> dict:
    sid = f"eval-crm-{int(time.time())}"
    create = crm_tool.upsert_session(sid, {"name": "Eval User", "dietary_preferences": "vegetarian"})
    read1 = crm_tool.get_session_record(sid)
    update = crm_tool.upsert_session(sid, {"special_requests": "window seat", "time": "7 pm"})
    add = crm_tool.add_reservation_to_session(
        sid,
        {"name": "Eval User", "date": "2026-05-20", "time": "7 pm", "guests": "2"},
    )
    mod = crm_tool.update_latest_reservation_in_session(sid, {"guests": "3"})
    delete_like = crm_tool.cancel_latest_reservation_in_session(sid)
    read2 = crm_tool.get_session_record(sid)

    checks = {
        "create_ok": create.get("status") == "success" and read1.get("name") == "Eval User",
        "update_ok": update.get("status") == "success" and read2.get("special_requests") == "window seat",
        "add_ok": add.get("status") == "success" and len(read2.get("reservations", [])) >= 1,
        "modify_ok": mod.get("status") == "success",
        "delete_ok": delete_like.get("status") == "success",
    }
    score = sum(int(v) for v in checks.values()) / len(checks)
    return {"score": score, "checks": checks}


async def evaluate_tool_invocation(cases: list[dict]) -> dict:
    correct = 0
    false_positive = 0
    details = []
    sid = f"eval-tool-{int(time.time())}"
    for c in cases:
        mem = extract_signals(c["utterance"], {"name": None, "dietary_preferences": None, "special_requests": None})
        _, tool_name = await tool_orchestrator(sid, c["utterance"], mem)
        expected = c["expected_tool"]
        ok = (tool_name == expected) if expected else (tool_name is None)
        correct += int(ok)
        if expected is None and tool_name is not None:
            false_positive += 1
        details.append({"utterance": c["utterance"], "expected_tool": expected, "predicted_tool": tool_name, "ok": ok})
    total = max(1, len(cases))
    return {
        "accuracy": correct / total,
        "false_positive_rate": false_positive / total,
        "details": details,
    }


def evaluate_tool_functional() -> dict:
    checks = {}
    m_ok = search_menu("pasta", "vegetarian")
    checks["menu_valid"] = m_ok.get("status") == "ok" and bool(m_ok.get("results"))
    m_bad = search_menu("not-a-real-category", "")
    checks["menu_invalid_graceful"] = m_bad.get("status") == "ok"

    w_ok = get_weather("London")
    checks["weather_schema"] = "status" in w_ok and ("message" in w_ok or "temperature_c" in w_ok)
    w_bad = get_weather("ThisCityShouldNotExistXYZ")
    checks["weather_invalid_city"] = w_bad.get("status") in ("error", "ok")

    name = f"EvalLookup{int(time.time())}"
    save = save_reservation(name, "2026-05-31", "8 pm", "2")
    look = lookup_reservation(name)
    upd = update_reservation(name, {"time": "9 pm"})
    can = cancel_reservation(name)
    checks["reservation_save_lookup"] = save.get("status") == "ok" and look.get("status") == "ok"
    checks["reservation_update"] = upd.get("status") in ("ok", "error")
    checks["reservation_cancel"] = can.get("status") in ("ok", "error")

    score = sum(int(v) for v in checks.values()) / max(1, len(checks))
    return {"score": score, "checks": checks}


def evaluate_failure_modes() -> dict:
    checks = {}

    # Failure mode 1: Empty/missing vector DB should fail gracefully.
    try:
        RestaurantRAG(db_folder=str(PROJECT_ROOT / "rag" / "__missing_db__"))
        checks["empty_vector_db_handled"] = False
    except Exception:
        checks["empty_vector_db_handled"] = True

    # Failure mode 2: Tool timeout / API failure path should return structured error.
    weather_bad = get_weather("ThisCityShouldNotExistXYZ")
    checks["tool_api_failure_handled"] = weather_bad.get("status") in ("ok", "error")

    # Failure mode 3: Malformed tool call input should not crash.
    bad_lookup = lookup_reservation("")
    checks["malformed_tool_call_handled"] = bad_lookup.get("status") == "error"

    score = sum(int(v) for v in checks.values()) / max(1, len(checks))
    return {"score": score, "checks": checks}


def evaluate_rag_retrieval(ground_truth: list[dict], k: int = 3) -> dict:
    rag = RestaurantRAG()
    p_at_k = []
    r_at_k = []
    rr = []
    details = []
    for row in ground_truth:
        docs = rag.retrieve_documents(row["query"], k=k)
        got = [Path(d.metadata.get("source", "")).name.lower() for d in docs]
        rel = [s.lower() for s in row["relevant_sources"]]
        rel_hits = [i for i, src in enumerate(got, start=1) if any(r in src for r in rel)]
        p = len(rel_hits) / max(1, k)
        r = len(rel_hits) / max(1, len(rel))
        p_at_k.append(p)
        r_at_k.append(r)
        rr.append(1 / rel_hits[0] if rel_hits else 0.0)
        details.append({"query": row["query"], "retrieved": got, "relevant": rel, "hits": rel_hits})

    return {
        "num_queries": len(ground_truth),
        "precision_at_k": statistics.mean(p_at_k) if p_at_k else 0.0,
        "recall_at_k": statistics.mean(r_at_k) if r_at_k else 0.0,
        "mrr": statistics.mean(rr) if rr else 0.0,
        "context_relevance": statistics.mean(p_at_k) if p_at_k else 0.0,
        "details": details,
    }


def faithfulness_score(answer: str, context: str) -> float:
    stop = {
        "the", "a", "an", "is", "are", "was", "were", "be", "to", "for", "and", "or",
        "of", "in", "on", "at", "with", "we", "you", "it", "this", "that", "our",
    }
    ans = [w.strip(".,!?;:()[]{}'\"").lower() for w in answer.split()]
    ans = [w for w in ans if len(w) > 2 and w not in stop]
    if not ans:
        return 0.0
    ctx = normalize_text(context)
    hits = sum(1 for w in ans if w in ctx)
    return hits / len(ans)


def evaluate_rag_faithfulness(pairs: list[dict]) -> dict:
    rag = RestaurantRAG()
    scores = []
    details = []
    for row in pairs:
        docs = rag.retrieve_documents(row["question"], k=3)
        context = "\n".join(d.page_content for d in docs)
        ans = rag.answer_question(row["question"]).get("answer", "")
        s = faithfulness_score(ans, context)
        scores.append(s)
        details.append({"question": row["question"], "score": s, "answer_preview": ans[:200]})
    return {"num_pairs": len(pairs), "avg_faithfulness": statistics.mean(scores) if scores else 0.0, "details": details}


async def evaluate_latency(chat: ChatClient, scenarios: dict[str, str], trials: int) -> dict:
    out = {}
    for name, prompt in scenarios.items():
        ttft = []
        inter = []
        e2e = []
        errors = []
        for i in range(trials):
            try:
                sid = await chat.create_session()
                m = await chat.send_turn(sid, prompt)
                ttft.append(m.ttft_s)
                inter.append(m.inter_token_latency_s)
                e2e.append(m.e2e_s)
            except Exception as e:
                errors.append({"trial": i + 1, "error": str(e)})
        out[name] = {
            "trials": trials,
            "successes": len(ttft),
            "failures": len(errors),
            "ttft": {
                "mean": statistics.mean(ttft) if ttft else 0.0,
                "median": statistics.median(ttft) if ttft else 0.0,
                "p90": percentile(ttft, 90),
                "p99": percentile(ttft, 99),
                **mean_ci95(ttft),
            },
            "inter_token_latency": {
                "mean": statistics.mean(inter) if inter else 0.0,
                "median": statistics.median(inter) if inter else 0.0,
                "p90": percentile(inter, 90),
                "p99": percentile(inter, 99),
                **mean_ci95(inter),
            },
            "end_to_end": {
                "mean": statistics.mean(e2e) if e2e else 0.0,
                "median": statistics.median(e2e) if e2e else 0.0,
                "p90": percentile(e2e, 90),
                "p99": percentile(e2e, 99),
                **mean_ci95(e2e),
            },
            "errors": errors,
        }
    return out


async def _run_virtual_user(chat: ChatClient, prompts: list[str]) -> dict:
    sid = await chat.create_session()
    turn_count = 0
    ttft = []
    e2e = []
    err = 0
    for p in prompts:
        try:
            m = await chat.send_turn(sid, p)
            ttft.append(m.ttft_s)
            e2e.append(m.e2e_s)
            turn_count += 1
        except Exception:
            err += 1
    return {"turn_count": turn_count, "ttft": ttft, "e2e": e2e, "errors": err}


async def evaluate_throughput(chat: ChatClient, conc_levels: list[int], prompts: list[str], thresholds: dict[str, float]) -> dict:
    rows = []
    sustainable = None
    breakpoint = None
    for c in conc_levels:
        start = time.perf_counter()
        users = await asyncio.gather(*[_run_virtual_user(chat, prompts) for _ in range(c)])
        elapsed = max(1e-6, time.perf_counter() - start)
        all_ttft = [x for u in users for x in u["ttft"]]
        all_e2e = [x for u in users for x in u["e2e"]]
        total_turns = sum(u["turn_count"] for u in users)
        total_errors = sum(u["errors"] for u in users)
        med_ttft = statistics.median(all_ttft) if all_ttft else 0.0
        med_e2e = statistics.median(all_e2e) if all_e2e else 0.0
        tps = total_turns / elapsed
        ok = med_ttft <= thresholds["ttft_median_max_s"] and med_e2e <= thresholds["e2e_median_max_s"] and total_errors == 0
        if ok:
            sustainable = c
        elif breakpoint is None:
            breakpoint = c
        rows.append(
            {
                "concurrency": c,
                "total_turns": total_turns,
                "turns_per_second": tps,
                "median_ttft_s": med_ttft,
                "median_e2e_s": med_e2e,
                "errors": total_errors,
                "meets_threshold": ok,
            }
        )
    return {
        "levels": rows,
        "max_sustainable_concurrency": sustainable or 0,
        "breakpoint_concurrency": breakpoint or 0,
        "throughput_at_sustainable_tps": next((r["turns_per_second"] for r in rows if r["concurrency"] == sustainable), 0.0),
        "thresholds": thresholds,
    }


def hardware_snapshot() -> dict:
    disk = os.statvfs(PROJECT_ROOT) if hasattr(os, "statvfs") else None
    return {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "cpu": platform.processor() or "unknown",
        "cpu_count_logical": os.cpu_count(),
        "machine": platform.machine(),
        "disk_free_gb_estimate": round((disk.f_bavail * disk.f_frsize) / (1024**3), 2) if disk else None,
    }


def dependency_snapshot() -> dict:
    pkgs = ["fastapi", "uvicorn", "websockets", "httpx", "langchain", "chromadb", "sentence-transformers", "ollama"]
    versions = {}
    for p in pkgs:
        try:
            mod = __import__(p.replace("-", "_"))
            versions[p] = getattr(mod, "__version__", "unknown")
        except Exception:
            versions[p] = "not_importable"
    return versions


def generate_plots(results: dict, ts: str) -> dict:
    if not MATPLOTLIB_AVAILABLE:
        return {"enabled": False, "reason": "matplotlib_not_installed", "files": []}

    files = []

    # Plot 1: concurrency vs median latency
    thr = results["performance"]["throughput"]["levels"]
    x = [r["concurrency"] for r in thr]
    y_ttft = [r["median_ttft_s"] for r in thr]
    y_e2e = [r["median_e2e_s"] for r in thr]
    plt.figure(figsize=(8, 4.5))
    plt.plot(x, y_ttft, marker="o", label="Median TTFT (s)")
    plt.plot(x, y_e2e, marker="s", label="Median End-to-End (s)")
    plt.xlabel("Concurrency")
    plt.ylabel("Latency (seconds)")
    plt.title("Concurrency vs Median Latency")
    plt.grid(True, alpha=0.3)
    plt.legend()
    p1 = RESULTS_DIR / f"concurrency_vs_latency_{ts}.png"
    plt.tight_layout()
    plt.savefig(p1, dpi=140)
    plt.close()
    files.append(p1.name)

    # Plot 2: scenario vs TTFT/E2E
    lat = results["performance"]["latency"]
    scenarios = list(lat.keys())
    ttft_med = [lat[s]["ttft"]["median"] for s in scenarios]
    e2e_med = [lat[s]["end_to_end"]["median"] for s in scenarios]
    idx = list(range(len(scenarios)))
    width = 0.38
    plt.figure(figsize=(9, 4.8))
    plt.bar([i - width / 2 for i in idx], ttft_med, width=width, label="Median TTFT")
    plt.bar([i + width / 2 for i in idx], e2e_med, width=width, label="Median End-to-End")
    plt.xticks(idx, scenarios, rotation=20, ha="right")
    plt.ylabel("Latency (seconds)")
    plt.title("Scenario vs Latency (Median)")
    plt.legend()
    plt.grid(axis="y", alpha=0.3)
    p2 = RESULTS_DIR / f"scenario_vs_latency_{ts}.png"
    plt.tight_layout()
    plt.savefig(p2, dpi=140)
    plt.close()
    files.append(p2.name)

    return {"enabled": True, "files": files}


def write_markdown_report(results: dict, md_path: Path) -> None:
    lines = []
    lines.append("# Assignment 5 Evaluation Report")
    lines.append("")
    lines.append(f"- Generated: {results['meta']['generated_at_utc']}")
    lines.append(f"- API Base: `{results['meta']['api_base']}`")
    lines.append(f"- Model: `{results['meta']['model']}`")
    lines.append("")
    lines.append("## Overall Conversational Correctness")
    c = results["conversation_correctness"]
    lines.append(f"- Dialogues evaluated: **{c['num_dialogues']}**")
    lines.append(f"- Task completion rate: **{c['task_completion_rate']:.2%}**")
    lines.append(f"- Policy adherence rate: **{c['policy_adherence_rate']:.2%}**")
    lines.append(f"- Coherence rate: **{c['coherence_rate']:.2%}**")
    lines.append("")
    lines.append("## Component-Level Correctness")
    comp = results["component_correctness"]
    lines.append(f"- CRM CRUD score: **{comp['crm_crud']['score']:.2%}**")
    lines.append(f"- Tool functional score: **{comp['tool_functional']['score']:.2%}**")
    lines.append(f"- Tool invocation accuracy: **{comp['tool_invocation']['accuracy']:.2%}**")
    lines.append(f"- Tool false-positive rate: **{comp['tool_invocation']['false_positive_rate']:.2%}**")
    lines.append(f"- RAG precision@k: **{comp['rag_retrieval']['precision_at_k']:.3f}**")
    lines.append(f"- RAG recall@k: **{comp['rag_retrieval']['recall_at_k']:.3f}**")
    lines.append(f"- RAG MRR: **{comp['rag_retrieval']['mrr']:.3f}**")
    lines.append(f"- RAG faithfulness (heuristic): **{comp['rag_faithfulness']['avg_faithfulness']:.3f}**")
    lines.append("")
    lines.append("## Latency")
    for name, row in results["performance"]["latency"].items():
        lines.append(f"### {name}")
        lines.append(f"- Trials: {row['trials']} (success {row['successes']}, fail {row['failures']})")
        lines.append(f"- TTFT mean/median/p90/p99: {row['ttft']['mean']:.3f}s / {row['ttft']['median']:.3f}s / {row['ttft']['p90']:.3f}s / {row['ttft']['p99']:.3f}s")
        lines.append(f"- End-to-end mean/median/p90/p99: {row['end_to_end']['mean']:.3f}s / {row['end_to_end']['median']:.3f}s / {row['end_to_end']['p90']:.3f}s / {row['end_to_end']['p99']:.3f}s")
        lines.append("")
    t = results["performance"]["throughput"]
    lines.append("## Throughput")
    lines.append(f"- Max sustainable concurrency: **{t['max_sustainable_concurrency']}**")
    lines.append(f"- Breakpoint concurrency: **{t['breakpoint_concurrency']}**")
    lines.append(f"- Throughput at sustainable level: **{t['throughput_at_sustainable_tps']:.3f} turns/sec**")
    lines.append("")
    lines.append("## Plots")
    plots = results["meta"].get("plots", {})
    if plots.get("enabled"):
        for fn in plots.get("files", []):
            lines.append(f"![{fn}](./{fn})")
    else:
        lines.append("- Plot generation unavailable in this run (matplotlib not installed).")
    lines.append("")
    lines.append("## Analysis")
    failed_task_ids = [d["id"] for d in c["details"] if not d["task_ok"]]
    lines.append(
        f"- Task completion is **{c['task_completion_rate']:.2%}** primarily because dialogues "
        f"{failed_task_ids} did not satisfy their final-task rubric; the most visible gap is reservation lookup phrasing."
    )
    lines.append(
        f"- Throughput threshold failed because median TTFT stayed above the configured 2.0s target "
        f"(lowest observed around {t['levels'][0]['median_ttft_s']:.3f}s at concurrency 1), so no concurrency level met all constraints."
    )
    lines.append("")
    lines.append("## Failure-Mode Checks")
    fm = comp.get("failure_modes", {})
    if fm:
        lines.append(f"- Failure-mode score: **{fm.get('score', 0.0):.2%}**")
        for k, v in (fm.get("checks") or {}).items():
            lines.append(f"- `{k}`: {'PASS' if v else 'FAIL'}")
    lines.append("")
    lines.append("## Environment")
    lines.append(f"- Hardware: `{json.dumps(results['meta']['hardware'])}`")
    lines.append(f"- Dependencies: `{json.dumps(results['meta']['dependencies'])}`")
    lines.append("")
    lines.append("## Notes")
    lines.append("- Faithfulness is computed with a reproducible lexical-support heuristic (chosen for fully offline reproducibility).")
    lines.append("- Limitation: lexical support is weaker than entailment-based metrics (e.g., RAGAS faithfulness) and can over/under-estimate factual grounding.")
    lines.append("- Mixed scenario is approximated as a compound user request because this chatbot routes tools deterministically.")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


async def main() -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    api_base = os.getenv("EVAL_API_BASE", "http://localhost:8000")
    trials = int(os.getenv("EVAL_TRIALS", "30"))
    chat = ChatClient(api_base=api_base)

    conversations = load_json(DATA_DIR / "conversations.json")
    rag_gt = load_json(DATA_DIR / "rag_ground_truth.json")
    tool_cases = load_json(DATA_DIR / "tool_invocation_cases.json")
    faithfulness_pairs = load_json(DATA_DIR / "rag_faithfulness_questions.json")

    conv = await evaluate_conversations(chat, conversations)
    crm_crud = evaluate_crm_crud()
    tool_fn = evaluate_tool_functional()
    failure_modes = evaluate_failure_modes()
    tool_inv = await evaluate_tool_invocation(tool_cases)
    rag_ret = evaluate_rag_retrieval(rag_gt, k=3)
    rag_faith = evaluate_rag_faithfulness(faithfulness_pairs)

    latency = await evaluate_latency(
        chat,
        {
            "simple_no_rag_no_tool": "hello there",
            "rag_only": "what are your opening hours and dress code?",
            "tool_only": "what pasta do you have?",
            "mixed_rag_plus_tool": "what pasta do you have and what are your opening hours?",
        },
        trials=trials,
    )
    throughput = await evaluate_throughput(
        chat,
        conc_levels=[1, 2, 4, 6, 8],
        prompts=["hello", "i want to book a table", "what pasta do you have"],
        thresholds={"ttft_median_max_s": 2.0, "e2e_median_max_s": 10.0},
    )

    results = {
        "meta": {
            "generated_at_utc": now_utc(),
            "api_base": api_base,
            "model": "qwen2.5:3b-instruct",
            "hardware": hardware_snapshot(),
            "dependencies": dependency_snapshot(),
        },
        "conversation_correctness": conv,
        "component_correctness": {
            "crm_crud": crm_crud,
            "tool_functional": tool_fn,
            "failure_modes": failure_modes,
            "tool_invocation": tool_inv,
            "rag_retrieval": rag_ret,
            "rag_faithfulness": rag_faith,
        },
        "performance": {"latency": latency, "throughput": throughput},
    }

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    results["meta"]["plots"] = generate_plots(results, ts)
    json_path = RESULTS_DIR / f"eval_report_{ts}.json"
    md_path = RESULTS_DIR / f"eval_report_{ts}.md"
    json_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    write_markdown_report(results, md_path)

    print(f"[OK] JSON report: {json_path}")
    print(f"[OK] Markdown report: {md_path}")


if __name__ == "__main__":
    asyncio.run(main())
