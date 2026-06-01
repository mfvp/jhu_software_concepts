# Mini LLM Standardizer — Flask (Replit-friendly)

Tiny Flask API that runs a small local LLM (TinyLlama 1.1B, GGUF) via `llama-cpp-python` to standardize
degree program + university names. It appends two new fields to each row:
- `llm-generated-program`
- `llm-generated-university`

## Changes from original (Module 2 assignment)

### Expanded abbreviation map (`ABBREV_UNI` in `app.py`)
Added 15 new university abbreviations common in Grad Cafe data, on top of the original 3 (McGill, UBC, UofT):

| Abbreviation | Expands to |
|---|---|
| `JHU` | Johns Hopkins University |
| `MIT` | Massachusetts Institute of Technology |
| `CMU`, `Carnegie Mellon` | Carnegie Mellon University |
| `UIUC` | University of Illinois Urbana-Champaign |
| `UMich` | University of Michigan, Ann Arbor |
| `UNC` | University of North Carolina at Chapel Hill |
| `UT Austin` | University of Texas at Austin |
| `UCLA` | University of California, Los Angeles |
| `UCB`, `UC Berkeley` | University of California, Berkeley |
| `UCSD`, `UC San Diego` | University of California, San Diego |
| `USC` | University of Southern California |
| `NYU` | New York University |
| `GaTech`, `Georgia Tech` | Georgia Institute of Technology |
| `UPenn`, `U Penn` | University of Pennsylvania |
| `BU`, `Boston U` | Boston University |
| `PSU`, `Penn State` | Pennsylvania State University |

### Common spelling/capitalization fixes
Added `COMMON_UNI_FIXES` dict for known misspellings:
- `"McGiill University"` → `"McGill University"`
- `"University Of British Columbia"` → `"University of British Columbia"` (wrong capitalization of "Of")

Added `COMMON_PROG_FIXES` dict for program name variants:
- `"Mathematic"` → `"Mathematics"`
- `"Info Studies"` → `"Information Studies"`

### Parallel processing (`--workers`)
Added `--workers N` CLI argument. When `N > 1`, the script spawns `N` worker **processes** (not threads), each loading its own copy of the model. This gives true parallel inference with no lock contention.

- Each worker uses `cpu_count // N` threads internally so total CPU usage stays flat.
- Workers pre-load the model at startup (`_worker_init`) so the first row per worker isn't slow.
- The Flask `/standardize` endpoint still uses the original single-model + `_LLM_LOCK` path (unchanged).

### Limit processing (`--limit`)
Added `--limit N` to process only the first N rows. Useful for large datasets where a full run would take many hours.

### Output format
CLI output is now a JSON array (not JSONL) to match the assignment's expected `llm_extend_applicant_data.json` format. Progress is printed to stderr so it remains visible even when stdout is redirected to a file.

### Local model cache
`_load_llm()` now checks for the model file in `llm_hosting/models/` before contacting Hugging Face. This avoids unnecessary network calls on repeat runs.

---

## Quickstart (Replit)

1. Create a new **Python** Repl.
2. Upload these files (or import the zip).
3. Install deps:
   ```bash
   pip install -r requirements.txt
   ```
4. Run the API server:
   ```bash
   python app.py --serve
   ```
   The first run downloads a small GGUF model from Hugging Face (defaults to TinyLlama 1.1B Chat Q4_K_M).

5. Test locally (replace the URL with your Replit web URL when deployed):
   ```bash
   curl -s -X POST http://localhost:8000/standardize \
     -H "Content-Type: application/json" \
     -d @sample_data.json | jq .
   ```

## CLI mode (no server)

Process a file and write a JSON array to stdout:
```bash
python app.py --file applicant_data.json --stdout > llm_extend_applicant_data.json
```

With parallel workers and a row limit (recommended for large datasets):
```bash
python app.py --file applicant_data.json --stdout --workers 4 --limit 1000 > llm_extend_applicant_data.json
```

Progress is printed to stderr while JSON output goes to the file:
```
Processing 1000 rows...
Starting 4 worker processes (2 threads each)...
  10/1000 done
  20/1000 done
  ...
Done! Wrote 1000 enriched entries.
```

## Config (env vars)

| Variable | Default | Description |
|---|---|---|
| `MODEL_REPO` | `TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF` | Hugging Face repo |
| `MODEL_FILE` | `tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf` | GGUF filename |
| `N_THREADS` | CPU count | Threads per model instance |
| `N_CTX` | `2048` | Context window size |
| `N_GPU_LAYERS` | `0` | GPU layers (0 = CPU only) |

If memory is tight on Replit, try a smaller quantization:
```bash
export MODEL_FILE=tinyllama-1.1b-chat-v1.0.Q3_K_M.gguf
```

## Notes
- Strict JSON prompting + a rules-first fallback keep tiny models on task.
- Extend the few-shots and the fallback patterns in `app.py` for higher accuracy on your dataset.
- With 4 workers on an 8-core CPU, expect ~2–3 seconds per entry. Processing 1,000 entries takes roughly 30–45 minutes.
