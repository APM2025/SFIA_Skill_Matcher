# SFIA Matcher

A local web app that takes STAR-format evidence (Situation, Task, Action, Result) and maps it to the most relevant [SFIA 9](https://sfia-online.org) skills and levels using semantic NLP matching.

---

## What it does

1. Paste your STAR evidence into the four form fields
2. The app encodes it as a semantic vector and searches the SFIA 9 knowledge graph
3. It returns the top 5 skill matches with scores, justifications, and a highlighted evidence snippet
4. Optionally enter your level of responsibility — the app detects which SFIA level (1–7) your description most closely matches and re-weights results accordingly
5. If a match isn't quite right, use "Refine this match" to steer it with a one-sentence correction

---

## Requirements

- Python 3.10+
- `SFIA_9_2025-02-27.ttl` in the repository root (already included)

---

## Setup

```bash
cd sfia_app_v2
pip install -r requirements.txt
```

On first run the app downloads `all-MiniLM-L6-v2` (~90 MB) and computes embeddings for all SFIA skills (~30 s). Results are cached to `app/.embedding_cache/` so subsequent starts take ~1–2 s.

---

## Running

```bash
python run.py
```

Open [http://localhost:5000](http://localhost:5000) in your browser.

Debug mode:

```bash
FLASK_DEBUG=true python run.py
```

---

## Environment variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `SECRET_KEY` | In production | random (changes on restart) | Flask session signing key. Generate one with: `python -c "import secrets; print(secrets.token_hex(32))"` |
| `FLASK_ENV` | No | `development` | Set to `production` to enforce `SECRET_KEY` being set |
| `SFIA_TTL_FILE` | No | `../SFIA_9_2025-02-27.ttl` | Override path to the SFIA ontology file |

---

## Architecture

```
run.py
  └── app/__init__.py         Flask application factory
        ├── config.py         Configuration (keys, paths, rate limits)
        ├── app/routes.py     HTTP endpoints
        ├── app/services/
        │   ├── sfia.py       Parses SFIA_9_*.ttl → skill data + level descriptors
        │   └── matching.py   NLP matching pipeline
        └── app/templates/
            └── index.html    Single-page UI

Data files (repository root):
  SFIA_9_2025-02-27.ttl           SFIA 9 ontology
  sfia_app_v2/
    job_roles_mapping.json        Illustrative job titles per SFIA code
    app/.embedding_cache/         Cached embedding tensors (auto-generated)
```

### Matching pipeline (matching.py)

```
STAR evidence
    │
    ▼
_parse_star_sections()      Split into Situation / Task / Action / Result
    │
    ▼
model.encode()              Action embedding + Context embedding
    │                       (if clarification provided, blended 80/20)
    ▼
semantic_search()           Dual retrieval: top-60 (action) ∪ top-40 (context)
    │
    ▼
_analyze_level()            Detect SFIA level 1–7 from responsibility text
    │
    ▼
Scoring loop                weighted score + keyword boost + level modifier
    │
    ▼
_deduplicate()              Top 5 unique skills
    │
    ▼
JSON response               matches, detected_level, best_fit_summary
```

---

## API

### `GET /`
Serves the web UI.

### `GET /csrf-token`
Returns a CSRF token for use in subsequent POST requests.

### `POST /match`
Run the matching pipeline.

Headers: `X-CSRFToken: <token>`

Body:
```json
{
  "situation": "...",
  "task": "...",
  "action": "...",
  "result": "...",
  "level_context": "I work independently and lead testing standards."
}
```

Rate limit: 5 requests per minute.

### `POST /refine`
Re-run matching with a clarification hint. Same body as `/match` plus:
```json
{ "clarification": "It was more about root cause analysis than governance." }
```

Rate limit: 10 requests per minute.

---

## Tests

```bash
pytest tests/ -v
```

- `tests/test_logic.py` — keyword boosting, level detection, input validation
- `tests/test_security.py` — CSRF enforcement, rate limiting, security headers
