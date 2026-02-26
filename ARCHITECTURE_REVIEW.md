# Architecture Review: SFIA Skill Matcher

**Reviewed:** 2026-02-24
**Reviewer:** Claude (claude-sonnet-4-6)
**Repository:** https://github.com/APM2025/SFIA_Skill_Matcher
**Overall Rating: 7.5 / 10** — Impressive community contribution; genuinely thoughtful design

---

## Summary Table

| Dimension | Score |
|---|---|
| Security | 8/10 |
| Code quality / structure | 8/10 |
| NLP pipeline design | 7.5/10 |
| Scalability | 4/10 |
| Maintainability | 8/10 |
| Completeness | 6/10 |
| **Overall** | **7.5/10** |

---

## Strengths

### Security (8/10)
- Flask-Talisman (CSP/HSTS), CSRF on all POSTs, per-IP rate limiting, session cookie hardening (`Secure`, `HttpOnly`, `SameSite=Lax`), control-char sanitisation — well above average for a personal project

### NLP Pipeline (7.5/10)
- Dual-vector retrieval (action embedding + context embedding separately) is a smart design — avoids losing the "what I did" signal to "where I worked" noise
- Clarification blending (80/20 weighting) for the refine flow is clean
- TF-IDF-style discriminative keyword boost builder from `job_roles_mapping.json` shows real understanding of retrieval systems
- Conservative level tie-breaking (lower = safer) is the right call for a professional evidence tool

### Code Quality (8/10)
- Proper Flask app factory, clean service layer separation (`SfiaService` = data, `MatchingService` = NLP), blueprint registration — textbook structure
- Content-addressable embedding cache (MD5 of corpus, not mtime) means the cache invalidates correctly after a `git pull` on a different machine
- Explicit `del graph; gc.collect()` after RDF parse frees ~80MB — developer knows what they're doing
- Docstrings are thorough throughout

---

## Weaknesses

### Scalability (4/10) — biggest issue
- `SentenceTransformer.encode()` is synchronous/blocking. A single slow inference call blocks the entire Flask process. No async, no background workers, no task queue
- `app.run()` in `run.py` uses the Flask dev server — gunicorn is in `requirements.txt` but never invoked. Multi-user load would require a proper WSGI setup
- In-memory rate limiting: `Flask-Limiter` itself warns about this — limits wouldn't be shared across gunicorn workers

### ML Design Fragility (6/10)
- Keyword boost is a raw substring match: `"I didn't use Python"` would still trigger the PROG boost
- Score isn't normalised — cosine similarity × boost multiplier × level modifier can exceed 1.0, making the score field misleading
- `_deduplicate` keeps the highest-scoring *level* per skill code, not the detected level — a user at Level 5 could get MGMT shown at Level 3 if that happened to score higher
- Magic numbers (`ACTION_WEIGHT=0.70`, `TOP_K_ACTION=60`, `TIEBREAK_MARGIN=0.05`) are class attributes — can't be tuned without touching source

### Presentation / Design (6/10)
- `best_fit_summary` returns raw HTML (`<strong>`, `<em>`, `⚠️`) from the service layer — mixes presentation into business logic
- `unsafe-inline` CSP is a known gap (developer comments this themselves)
- No input type validation: `data.get("situation", "").strip()` would crash if a field is sent as an integer

### Missing Features
- No result persistence, history, or export (PDF/JSON)
- No multi-user sessions or saved evidence
- Tests cover logic + security only — no integration test for the full pipeline end-to-end

---

## Conclusion

The developer clearly knows Flask, NLP fundamentals, and security. The main risk for anything beyond personal/demo use is the blocking inference model with no concurrency strategy. For a single-user local tool (which is the stated intent), it's well-built.
