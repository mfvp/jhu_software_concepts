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
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Tuple

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


def _load_llm() -> Llama:
    """Download (or reuse) the GGUF file and initialize llama.cpp."""
    global _LLM
    if _LLM is not None:
        return _LLM

    model_path = hf_hub_download(
        repo_id=MODEL_REPO,
        filename=MODEL_FILE,
        local_dir="models",
        local_dir_use_symlinks=False,
        force_filename=MODEL_FILE,
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
) -> None:
    """Process a JSON file and write JSONL incrementally.

    When n_workers > 1, rows are dispatched to a ThreadPoolExecutor so that
    I/O and message-building overlap even though inference is serialised by
    _LLM_LOCK. Output is written in completion order (not input order) which
    is fine for downstream analysis but preserves all records.
    """
    with open(in_path, "r", encoding="utf-8") as f:
        rows = _normalize_input(json.load(f))

    sink = sys.stdout if to_stdout else None
    if not to_stdout:
        out_path = out_path or (in_path + ".jsonl")
        mode = "a" if append else "w"
        sink = open(out_path, mode, encoding="utf-8")

    assert sink is not None  # for type-checkers
    # protect the output stream when multiple threads write concurrently
    sink_lock = threading.Lock()

    def _write(row: Dict[str, Any]) -> None:
        with sink_lock:
            json.dump(row, sink, ensure_ascii=False)
            sink.write("\n")
            sink.flush()

    try:
        if n_workers <= 1:
            # simple sequential path (original behaviour)
            for row in rows:
                _write(_process_row(row))
        else:
            with ThreadPoolExecutor(max_workers=n_workers) as pool:
                futures = [pool.submit(_process_row, row) for row in rows]
                for fut in as_completed(futures):
                    _write(fut.result())
    finally:
        if sink is not sys.stdout:
            sink.close()


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
        )
