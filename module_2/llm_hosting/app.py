# -*- coding: utf-8 -*-
"""Flask + tiny local LLM standardizer with incremental JSONL CLI output.

Modified for Module 2 assignment:
- Added threading for parallel row processing
- Expanded abbreviation maps with common Grad Cafe abbreviations
- Added --workers CLI argument
"""

from __future__ import annotations

import json
import os
import re
import sys
import difflib
import threading
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
from typing import Any, Dict, List, Tuple

from pathlib import Path

from flask import Flask, jsonify, request
from huggingface_hub import hf_hub_download
from llama_cpp import Llama  # CPU-only by default if N_GPU_LAYERS=0

app = Flask(__name__)

# ---------------- Model config ----------------
MODEL_REPO = os.getenv(
    "MODEL_REPO",
    "TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF",
)
MODEL_FILE = os.getenv(
    "MODEL_FILE",
    "tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf",
)

N_THREADS = int(os.getenv("N_THREADS", str(os.cpu_count() or 2)))
N_CTX = int(os.getenv("N_CTX", "2048"))
N_GPU_LAYERS = int(os.getenv("N_GPU_LAYERS", "0"))  # 0 → CPU-only
# Number of parallel worker threads for CLI processing (default = cpu count)
N_WORKERS = int(os.getenv("N_WORKERS", str(max(1, os.cpu_count() or 2))))

CANON_UNIS_PATH = os.getenv("CANON_UNIS_PATH", "canon_universities.txt")
CANON_PROGS_PATH = os.getenv("CANON_PROGS_PATH", "canon_programs.txt")

# Precompiled, non-greedy JSON object matcher to tolerate chatter around JSON
JSON_OBJ_RE = re.compile(r"\{.*?\}", re.DOTALL)

# ---------------- Canonical lists + abbrev maps ----------------
def _read_lines(path: str) -> List[str]:
    """Read non-empty, stripped lines from a file (UTF-8)."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return [ln.strip() for ln in f if ln.strip()]
    except FileNotFoundError:
        return []


CANON_UNIS = _read_lines(CANON_UNIS_PATH)
CANON_PROGS = _read_lines(CANON_PROGS_PATH)

ABBREV_UNI: Dict[str, str] = {
    r"(?i)^mcg(\.|ill)?$": "McGill University",
    r"(?i)^(ubc|u\.?b\.?c\.?)$": "University of British Columbia",
    r"(?i)^uoft$": "University of Toronto",
    # added common Grad Cafe abbreviations
    r"(?i)^jhu$": "Johns Hopkins University",
    r"(?i)^mit$": "Massachusetts Institute of Technology",
    r"(?i)^(cmu|carnegie\s*mellon)$": "Carnegie Mellon University",
    r"(?i)^(uiuc|u\.?i\.?u\.?c\.?)$": "University of Illinois Urbana-Champaign",
    r"(?i)^(umich|u\.?\s*of\s*michigan)$": "University of Michigan, Ann Arbor",
    r"(?i)^(unc|u\.?n\.?c\.?)$": "University of North Carolina at Chapel Hill",
    r"(?i)^(ut\s*austin|u\.?\s*texas)$": "University of Texas at Austin",
    r"(?i)^(ucla|u\.?c\.?\s*la)$": "University of California, Los Angeles",
    r"(?i)^(ucb|uc\s*berkeley|u\.?c\.?\s*berkeley)$": "University of California, Berkeley",
    r"(?i)^(ucsd|uc\s*san\s*diego)$": "University of California, San Diego",
    r"(?i)^(usc|u\.?s\.?c\.?)$": "University of Southern California",
    r"(?i)^(nyu|n\.?y\.?u\.?)$": "New York University",
    r"(?i)^(gatech|georgia\s*tech)$": "Georgia Institute of Technology",
    r"(?i)^(upenn|u\.?\s*penn)$": "University of Pennsylvania",
    r"(?i)^(bu|boston\s*u\.?)$": "Boston University",
    r"(?i)^(psu|penn\s*state)$": "Pennsylvania State University",
}

COMMON_UNI_FIXES: Dict[str, str] = {
    "McGiill University": "McGill University",
    "Mcgill University": "McGill University",
    # Normalize 'Of' → 'of'
    "University Of British Columbia": "University of British Columbia",
}

COMMON_PROG_FIXES: Dict[str, str] = {
    "Mathematic": "Mathematics",
    "Info Studies": "Information Studies",
}

# ---------------- Few-shot prompt ----------------
SYSTEM_PROMPT = (
    "You are a data cleaning assistant. Standardize degree program and university "
    "names.\n\n"
    "Rules:\n"
    "- Input provides a single string under key `program` that may contain both "
    "program and university.\n"
    "- Split into (program name, university name).\n"
    "- Trim extra spaces and commas.\n"
    '- Expand obvious abbreviations (e.g., "McG" -> "McGill University", '
    '"UBC" -> "University of British Columbia").\n'
    "- Use Title Case for program; use official capitalization for university "
    "names (e.g., \"University of X\").\n"
    '- Ensure correct spelling (e.g., "McGill", not "McGiill").\n'
    '- If university cannot be inferred, return "Unknown".\n\n'
    "Return JSON ONLY with keys:\n"
    "  standardized_program, standardized_university\n"
)

FEW_SHOTS: List[Tuple[Dict[str, str], Dict[str, str]]] = [
    (
        {"program": "Information Studies, McGill University"},
        {
            "standardized_program": "Information Studies",
            "standardized_university": "McGill University",
        },
    ),
    (
        {"program": "Information, McG"},
        {
            "standardized_program": "Information Studies",
            "standardized_university": "McGill University",
        },
    ),
    (
        {"program": "Mathematics, University Of British Columbia"},
        {
            "standardized_program": "Mathematics",
            "standardized_university": "University of British Columbia",
        },
    ),
]

_LLM: Llama | None = None
# Lock so multiple threads don't call the model at the same time (not thread-safe)
_LLM_LOCK: threading.Lock = threading.Lock()

# ------------ Multiprocessing model (one instance per worker process) ------------
# Each worker process gets its own copy of the model so inference runs truly in parallel.
# No lock needed here because each process is single-threaded.
_PROC_LLM: Llama | None = None
_THREADS_PER_WORKER: int = N_THREADS  # overridden by _worker_init


def _worker_init(n_threads: int) -> None:
    """Called once when each worker process starts - pre-loads the model."""
    global _THREADS_PER_WORKER
    _THREADS_PER_WORKER = n_threads
    _get_proc_llm()  # warm up now so the first row isn't slow


def _get_proc_llm() -> Llama:
    """Load the model once per worker process and cache it as a process-local global."""
    global _PROC_LLM
    if _PROC_LLM is not None:
        return _PROC_LLM
    script_dir = Path(__file__).parent
    candidates = [script_dir / "models" / MODEL_FILE, Path("models") / MODEL_FILE]
    local_path = next((p for p in candidates if p.exists()), None)
    if local_path:
        model_path = str(local_path)
    else:
        model_path = hf_hub_download(
            repo_id=MODEL_REPO,
            filename=MODEL_FILE,
            local_dir=str(script_dir / "models"),
        )
    _PROC_LLM = Llama(
        model_path=model_path,
        n_ctx=N_CTX,
        n_threads=_THREADS_PER_WORKER,
        n_gpu_layers=N_GPU_LAYERS,
        verbose=False,
    )
    return _PROC_LLM


def _process_row_mp(row: Dict[str, Any]) -> Dict[str, Any]:
    """Process one row using the process-local model.
    Called in worker processes - no lock needed since each process owns its model.
    """
    llm = _get_proc_llm()
    program_text = (row or {}).get("program") or ""

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for x_in, x_out in FEW_SHOTS:
        messages.append({"role": "user", "content": json.dumps(x_in, ensure_ascii=False)})
        messages.append({"role": "assistant", "content": json.dumps(x_out, ensure_ascii=False)})
    messages.append({"role": "user", "content": json.dumps({"program": program_text}, ensure_ascii=False)})

    try:
        out = llm.create_chat_completion(messages=messages, temperature=0.0, max_tokens=128, top_p=1.0)
        text = (out["choices"][0]["message"]["content"] or "").strip()
        m = JSON_OBJ_RE.search(text)
        obj = json.loads(m.group(0) if m else text)
        std_prog = _post_normalize_program(str(obj.get("standardized_program", "")).strip())
        std_uni = _post_normalize_university(str(obj.get("standardized_university", "")).strip())
    except Exception:
        std_prog, std_uni = _split_fallback(program_text)
        std_prog = _post_normalize_program(std_prog)
        std_uni = _post_normalize_university(std_uni)

    row["llm-generated-program"] = std_prog
    row["llm-generated-university"] = std_uni
    return row


def _load_llm() -> Llama:
    """Load the GGUF file and initialize llama.cpp.
    Checks local models/ folder first to avoid unnecessary HF Hub network calls.
    """
    global _LLM
    if _LLM is not None:
        return _LLM

    # look next to the script first, then in the CWD models/ folder
    script_dir = Path(__file__).parent
    candidates = [
        script_dir / "models" / MODEL_FILE,
        Path("models") / MODEL_FILE,
    ]
    local_path = next((p for p in candidates if p.exists()), None)

    if local_path:
        model_path = str(local_path)
    else:
        # model not found locally - download it from HuggingFace
        model_path = hf_hub_download(
            repo_id=MODEL_REPO,
            filename=MODEL_FILE,
            local_dir=str(script_dir / "models"),
        )

    _LLM = Llama(
        model_path=model_path,
        n_ctx=N_CTX,
        n_threads=N_THREADS,
        n_gpu_layers=N_GPU_LAYERS,
        verbose=False,
    )
    return _LLM


def _split_fallback(text: str) -> Tuple[str, str]:
    """Simple, rules-first parser if the model returns non-JSON."""
    s = re.sub(r"\s+", " ", (text or "")).strip().strip(",")
    parts = [p.strip() for p in re.split(r",| at | @ ", s) if p.strip()]
    prog = parts[0] if parts else ""
    uni = parts[1] if len(parts) > 1 else ""

    # High-signal expansions
    if re.fullmatch(r"(?i)mcg(ill)?(\.)?", uni or ""):
        uni = "McGill University"
    if re.fullmatch(
        r"(?i)(ubc|u\.?b\.?c\.?|university of british columbia)",
        uni or "",
    ):
        uni = "University of British Columbia"

    # Title-case program; normalize 'Of' → 'of' for universities
    prog = prog.title()
    if uni:
        uni = re.sub(r"\bOf\b", "of", uni.title())
    else:
        uni = "Unknown"
    return prog, uni


def _best_match(name: str, candidates: List[str], cutoff: float = 0.86) -> str | None:
    """Fuzzy match via difflib (lightweight, Replit-friendly)."""
    if not name or not candidates:
        return None
    matches = difflib.get_close_matches(name, candidates, n=1, cutoff=cutoff)
    return matches[0] if matches else None


def _post_normalize_program(prog: str) -> str:
    """Apply common fixes, title case, then canonical/fuzzy mapping."""
    p = (prog or "").strip()
    p = COMMON_PROG_FIXES.get(p, p)
    p = p.title()
    if p in CANON_PROGS:
        return p
    match = _best_match(p, CANON_PROGS, cutoff=0.84)
    return match or p


def _post_normalize_university(uni: str) -> str:
    """Expand abbreviations, apply common fixes, capitalization, and canonical map."""
    u = (uni or "").strip()

    # Abbreviations
    for pat, full in ABBREV_UNI.items():
        if re.fullmatch(pat, u):
            u = full
            break

    # Common spelling fixes
    u = COMMON_UNI_FIXES.get(u, u)

    # Normalize 'Of' → 'of'
    if u:
        u = re.sub(r"\bOf\b", "of", u.title())

    # Canonical or fuzzy map
    if u in CANON_UNIS:
        return u
    match = _best_match(u, CANON_UNIS, cutoff=0.86)
    return match or u or "Unknown"


def _call_llm(program_text: str) -> Dict[str, str]:
    """Query the tiny LLM and return standardized fields (thread-safe via lock).

    Message building is done outside the lock (pure Python, no shared state).
    Only model load + inference is serialized so threads don't corrupt llama.cpp.
    """
    # build the chat messages outside the lock - this is just Python list ops
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for x_in, x_out in FEW_SHOTS:
        messages.append(
            {"role": "user", "content": json.dumps(x_in, ensure_ascii=False)}
        )
        messages.append(
            {
                "role": "assistant",
                "content": json.dumps(x_out, ensure_ascii=False),
            }
        )
    messages.append(
        {
            "role": "user",
            "content": json.dumps({"program": program_text}, ensure_ascii=False),
        }
    )

    # serialize model load + inference - llama_cpp is not thread-safe
    with _LLM_LOCK:
        llm = _load_llm()
        out = llm.create_chat_completion(
            messages=messages,
            temperature=0.0,
            max_tokens=128,
            top_p=1.0,
        )

    text = (out["choices"][0]["message"]["content"] or "").strip()
    try:
        match = JSON_OBJ_RE.search(text)
        obj = json.loads(match.group(0) if match else text)
        std_prog = str(obj.get("standardized_program", "")).strip()
        std_uni = str(obj.get("standardized_university", "")).strip()
    except Exception:
        std_prog, std_uni = _split_fallback(program_text)

    std_prog = _post_normalize_program(std_prog)
    std_uni = _post_normalize_university(std_uni)
    return {
        "standardized_program": std_prog,
        "standardized_university": std_uni,
    }


def _normalize_input(payload: Any) -> List[Dict[str, Any]]:
    """Accept either a list of rows or {'rows': [...]}."""
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and isinstance(payload.get("rows"), list):
        return payload["rows"]
    return []


@app.get("/")
def health() -> Any:
    """Simple liveness check."""
    return jsonify({"ok": True})


@app.post("/standardize")
def standardize() -> Any:
    """Standardize rows from an HTTP request and return JSON."""
    payload = request.get_json(force=True, silent=True)
    rows = _normalize_input(payload)

    out: List[Dict[str, Any]] = []
    for row in rows:
        program_text = (row or {}).get("program") or ""
        result = _call_llm(program_text)
        row["llm-generated-program"] = result["standardized_program"]
        row["llm-generated-university"] = result["standardized_university"]
        out.append(row)

    return jsonify({"rows": out})


def _process_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """Enrich one row with LLM-generated fields. Used by the thread pool."""
    program_text = (row or {}).get("program") or ""
    result = _call_llm(program_text)
    row["llm-generated-program"] = result["standardized_program"]
    row["llm-generated-university"] = result["standardized_university"]
    return row


def _cli_process_file(
    in_path: str,
    out_path: str | None,
    append: bool,
    to_stdout: bool,
    n_workers: int = 1,
    limit: int | None = None,
    checkpoint_path: str | None = None,
) -> None:
    """Process a JSON file and write a JSON array output.

    Checkpoint/resume: if checkpoint_path is given, each completed row is
    appended to that file immediately. On the next run, already-processed rows
    (matched by 'url') are loaded from the checkpoint and skipped, so only
    the remaining rows are sent to the LLM. This prevents losing hours of work
    if the process crashes at the end.

    limit: if set, only process the first N rows (useful for large datasets)
    """
    with open(in_path, "r", encoding="utf-8") as f:
        rows = _normalize_input(json.load(f))

    if limit is not None:
        rows = rows[:limit]

    # --- resume from checkpoint if available ---
    done_by_url: Dict[str, Dict[str, Any]] = {}
    if checkpoint_path and Path(checkpoint_path).exists():
        with open(checkpoint_path, "r", encoding="utf-8") as ck:
            for line in ck:
                line = line.strip()
                if line:
                    try:
                        r = json.loads(line)
                        url = r.get("url") or ""
                        if url:
                            done_by_url[url] = r
                    except json.JSONDecodeError:
                        pass
        if done_by_url:
            print(f"Resuming: found {len(done_by_url)} already-processed rows in checkpoint.", file=sys.stderr)

    already_done = [done_by_url[r.get("url", "")] for r in rows if r.get("url", "") in done_by_url]
    pending = [r for r in rows if r.get("url", "") not in done_by_url]
    total = len(rows)
    print(f"Processing {len(pending)} remaining rows ({len(already_done)} already done)...", file=sys.stderr)

    # open checkpoint file for appending new results
    ck_sink = open(checkpoint_path, "a", encoding="utf-8") if checkpoint_path else None

    results: List[Dict[str, Any]] = list(already_done)
    results_lock = threading.Lock()
    done_count = len(already_done)

    def _collect(row: Dict[str, Any]) -> None:
        nonlocal done_count
        with results_lock:
            results.append(row)
            done_count += 1
            # save to checkpoint immediately so progress survives a crash
            if ck_sink:
                ck_sink.write(json.dumps(row, ensure_ascii=False) + "\n")
                ck_sink.flush()
            if done_count % 10 == 0 or done_count == total:
                print(f"  {done_count}/{total} done", file=sys.stderr, flush=True)

    try:
        if not pending:
            print("Nothing left to process.", file=sys.stderr)
        elif n_workers <= 1:
            for row in pending:
                _collect(_process_row(row))
        else:
            # divide CPU threads evenly across worker processes
            # e.g. 8 cores / 4 workers = 2 threads per model instance
            n_threads_per_worker = max(1, (os.cpu_count() or 4) // n_workers)
            print(
                f"Starting {n_workers} worker processes "
                f"({n_threads_per_worker} threads each)...",
                file=sys.stderr,
            )
            # ProcessPoolExecutor gives each worker its own Python process and its own
            # model instance - inference runs truly in parallel, no lock contention
            with ProcessPoolExecutor(
                max_workers=n_workers,
                initializer=_worker_init,
                initargs=(n_threads_per_worker,),
            ) as pool:
                futures = [pool.submit(_process_row_mp, row) for row in pending]
                for fut in as_completed(futures):
                    _collect(fut.result())
    finally:
        if ck_sink:
            ck_sink.close()

    # write final output as a proper JSON array to match assignment format
    output = json.dumps(results, indent=2, ensure_ascii=False)

    if to_stdout:
        # write bytes directly to avoid Windows cp1252 encoding errors on Unicode chars
        sys.stdout.buffer.write(output.encode("utf-8"))
        sys.stdout.buffer.write(b"\n")
        sys.stdout.buffer.flush()
    else:
        out_path = out_path or (in_path + ".out.json")
        mode = "a" if append else "w"
        with open(out_path, mode, encoding="utf-8") as f:
            f.write(output)
            f.write("\n")

    print(f"Done! Wrote {len(results)} enriched entries.", file=sys.stderr)

    # checkpoint is no longer needed once the final file is written successfully
    if checkpoint_path and Path(checkpoint_path).exists():
        Path(checkpoint_path).unlink()
        print(f"Checkpoint deleted: {checkpoint_path}", file=sys.stderr)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Standardize program/university with a tiny local LLM.",
    )
    parser.add_argument(
        "--file",
        help="Path to JSON input (list of rows or {'rows': [...]})",
        default=None,
    )
    parser.add_argument(
        "--serve",
        action="store_true",
        help="Run the HTTP server instead of CLI.",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Output path for JSON Lines (ndjson). "
        "Defaults to <input>.jsonl when --file is set.",
    )
    parser.add_argument(
        "--append",
        action="store_true",
        help="Append to the output file instead of overwriting.",
    )
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="Write JSON Lines to stdout instead of a file.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=N_WORKERS,
        help=f"Number of parallel worker threads (default: {N_WORKERS} = cpu count).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Only process the first N rows (useful for large datasets).",
    )
    parser.add_argument(
        "--checkpoint",
        default="llm_checkpoint.jsonl",
        help="Path to checkpoint file for resume support (default: llm_checkpoint.jsonl). "
             "Each completed row is saved here immediately; re-running resumes from where it left off.",
    )
    args = parser.parse_args()

    if args.serve or args.file is None:
        port = int(os.getenv("PORT", "8000"))
        app.run(host="0.0.0.0", port=port, debug=False)
    else:
        _cli_process_file(
            in_path=args.file,
            out_path=args.out,
            append=bool(args.append),
            to_stdout=bool(args.stdout),
            n_workers=args.workers,
            limit=args.limit,
            checkpoint_path=args.checkpoint,
        )
