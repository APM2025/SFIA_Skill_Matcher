# SFIA Skill Matcher - Developer Guide

## Overview

The SFIA Skill Matcher is a Flask-based web application that performs semantic matching between user-provided STAR evidence and SFIA 9 skills using sentence transformers and RDF knowledge graph parsing.

**Tech Stack:**
- **Backend**: Flask 3.x with Gunicorn
- **NLP**: sentence-transformers (`all-MiniLM-L6-v2` model)
- **Data**: RDFLib for parsing SFIA 9 TTL ontology
- **Security**: Flask-Talisman (CSP, HSTS), Flask-WTF (CSRF), Flask-Limiter (rate limiting)
- **Testing**: pytest

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                      CLIENT (Browser)                    │
│                   Single-Page Application                │
│                     (Vanilla JS + D3.js)                 │
└────────────────────┬────────────────────────────────────┘
                     │ HTTPS + CSRF Token
                     ▼
┌─────────────────────────────────────────────────────────┐
│                    FLASK APPLICATION                     │
│  ┌──────────────────────────────────────────────────┐  │
│  │ routes.py                                         │  │
│  │  - GET  /              (serve UI)                 │  │
│  │  - GET  /csrf-token    (token endpoint)           │  │
│  │  - POST /match         (main matching)            │  │
│  │  - POST /refine        (refined matching)         │  │
│  └──────────────────┬───────────────────────────────┘  │
│                     │                                   │
│  ┌──────────────────▼───────────────────────────────┐  │
│  │ services/matching.py                              │  │
│  │  - NLP pipeline (encode, search, score, rank)    │  │
│  │  - Level detection                                │  │
│  │  - Keyword boosting                               │  │
│  └──────────────────┬───────────────────────────────┘  │
│                     │                                   │
│  ┌──────────────────▼───────────────────────────────┐  │
│  │ services/sfia.py                                  │  │
│  │  - Parse SFIA_9_*.ttl (RDF graph)                │  │
│  │  - Extract skills, levels, descriptions          │  │
│  └───────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│                     DATA LAYER                           │
│  - SFIA_9_2025-02-27.ttl (RDF ontology)                 │
│  - job_roles_mapping.json (keyword hints)                │
│  - .embedding_cache/ (cached embeddings)                 │
└─────────────────────────────────────────────────────────┘
```

---

## Core Components

### 1. Application Factory (`app/__init__.py`)

**Responsibilities:**
- Flask app initialization
- Security middleware setup (CSRF, Talisman, rate limiting)
- Service initialization (SFIA parser + NLP model)
- Blueprint registration

**Key Pattern**: Services are eagerly loaded at startup and stored in `app.extensions`:
```python
app.extensions["sfia_service"] = SfiaService(...)
app.extensions["matching_service"] = MatchingService(...)
```

**Security Hardening:**
- CSP headers restrict inline scripts (with `unsafe-inline` temporarily for embedded JS)
- CSRF protection on all POST endpoints
- Rate limiting (5/min for `/match`, 10/min for `/refine`)
- Session cookies: `Secure`, `HttpOnly`, `SameSite=Lax`

### 2. SFIA Service (`app/services/sfia.py`)

**Responsibilities:**
- Parse `SFIA_9_*.ttl` using RDFLib
- Extract skill metadata (title, code, description, subcategory)
- Parse level-of-responsibility text for each SFIA level (1-7)

**Data Structure:**
```python
{
    "PROG": {
        "title": "Programming/software development",
        "code": "PROG",
        "description": "Develops software components...",
        "subcategory": "Development and implementation",
        "full_text": "Programming/software development (PROG). Develops..."
    },
    ...
}
```

**Level Descriptors:**
```python
{
    1: "Follow. Work under direct supervision...",
    2: "Assist. Work under general supervision...",
    ...
}
```

### 3. Matching Service (`app/services/matching.py`)

**Core Pipeline:**

1. **Parsing**: `_parse_star_sections()` splits evidence into S/T/A/R
2. **Encoding**: 
   - Action text → action vector
   - (Situation + Task + Result) → context vector
3. **Retrieval**: 
   - Semantic search: top 60 by action similarity + top 40 by context similarity
   - Combine and deduplicate
4. **Level Detection**: `_analyze_level()` compares responsibility text to 7 level descriptors
5. **Keyword Boosting**: Skills containing key terms from job roles mapping get +5% score
6. **Scoring**: 
   ```
   score = (0.6 * action_sim) + (0.4 * context_sim) + keyword_boost + level_modifier
   ```
7. **Ranking**: Sort by score, deduplicate to top 5 unique skills
8. **Evidence Extraction**: AI-based snippet extraction showing relevant text

**Caching Strategy:**
- Skill embeddings cached to `.embedding_cache/` (keyed by skill data hash)
- Model downloads cached by HuggingFace transformers (~90MB)
- Cache invalidation: manual (delete cache dir)

**Key Hyperparameters:**
```python
TOP_K_ACTION = 60          # Action-based retrieval
TOP_K_CONTEXT = 40         # Context-based retrieval
ACTION_WEIGHT = 0.6        # Action importance
CONTEXT_WEIGHT = 0.4       # Context importance
KEYWORD_BOOST = 0.05       # Bonus for keyword matches
LEVEL_MODIFIER = ±0.15     # Penalty/bonus for level mismatch
```

### 4. Routes (`app/routes.py`)

**Endpoints:**

| Endpoint | Method | Purpose | Rate Limit |
|----------|--------|---------|------------|
| `/` | GET | Serve index.html | None |
| `/csrf-token` | GET | Return CSRF token | None |
| `/match` | POST | Main matching pipeline | 5/min |
| `/refine` | POST | Re-match with clarification | 10/min |

**Input Validation:**
- Max evidence length: 5000 chars (configurable via `config.py`)
- Control character sanitization: strips `\x00-\x08`, `\x0b`, `\x0c`, `\x0e-\x1f`, `\x7f`
- CSRF token required on all POST requests

**Response Format:**
```json
{
  "matches": [
    {
      "skill_code": "PROG",
      "skill_title": "Programming/software development",
      "score": 0.78,
      "justification": "matched on: software design, debugging",
      "evidence_snippet": "I wrote Python scripts...",
      "level_match": true,
      "raw_score": 0.73,
      "level_modifier": 0.05
    }
  ],
  "detected_level": 3,
  "level_breakdown": {...},
  "best_fit_summary": {
    "skill_code": "PROG",
    "skill_title": "...",
    "evidence_snippet": "...",
    "job_roles": ["Software Developer", "Python Engineer"]
  }
}
```

---

## Deployment

### Local Development

```bash
cd sfia-rdf/sfia_app_v2
pip install -r requirements.txt
python run.py
```

Opens on `http://localhost:5000`. Debug mode can be enabled:
```bash
FLASK_DEBUG=true python run.py
```

### Production (Render / Cloud)

**Environment Variables:**
- `SECRET_KEY` (required): Flask session key - generate with `python -c "import secrets; print(secrets.token_hex(32))"`
- `FLASK_ENV=production` (optional): Enforces SECRET_KEY requirement
- `SFIA_TTL_FILE` (optional): Override path to SFIA ontology

**Build Command:**
```bash
pip install -r requirements.txt
```

**Start Command:**
```bash
gunicorn run:app --bind 0.0.0.0:$PORT
```

**Resource Requirements:**
- RAM: ~600MB at startup (sentence-transformers model + SFIA embeddings)
- CPU: Initial embedding computation takes ~30s on first run
- Disk: ~150MB (model cache + embedding cache)

**Known Issue - Memory on Free Tiers:**
Render free tier (512MB RAM) is borderline insufficient. Solutions:
1. Upgrade to Starter plan ($7/mo for 512MB+ RAM)
2. Use lazy loading (load model on first request, not at startup)
3. Try Railway/Fly.io with better free tier memory

---

## Testing

```bash
pytest tests/ -v
```

**Test Coverage:**

| File | Tests | Coverage |
|------|-------|----------|
| `test_logic.py` | Keyword boosting, level detection, input validation | Core logic |
| `test_security.py` | CSRF enforcement, rate limits, security headers | Security |

**Adding Tests:**
```python
def test_new_feature(client):
    """Test description."""
    response = client.get('/endpoint')
    assert response.status_code == 200
    data = response.get_json()
    assert 'expected_key' in data
```

---

## Improvement Opportunities

### 1. **Performance Optimization**

**Current Bottlenecks:**
- Startup time: ~30s on first run (embedding computation)
- Memory usage: ~600MB (model + embeddings)
- Per-request latency: ~2-3s (encoding + search)

**Improvements:**

#### A. Use a Smaller Model
Replace `all-MiniLM-L6-v2` with `paraphrase-MiniLM-L3-v2`:
- Size: 60MB vs 90MB
- Speed: 40% faster encoding
- Trade-off: ~5% accuracy loss

```python
# config.py
MODEL_NAME = "paraphrase-MiniLM-L3-v2"
```

#### B. Implement GPU Support
```python
# matching.py
device = 'cuda' if torch.cuda.is_available() else 'cpu'
model = SentenceTransformer(model_name, device=device)
```

#### C. Add Redis for Embedding Cache
Current file-based cache doesn't scale across multiple instances:
```python
import redis
r = redis.Redis(host='localhost', port=6379)

def get_cached_embedding(key):
    cached = r.get(f"emb:{key}")
    if cached:
        return torch.load(io.BytesIO(cached))
    return None
```

#### D. Lazy Load Services
Move model initialization to first request (reduces startup memory):
```python
def _get_matcher():
    if current_app.extensions["matching_service"] is None:
        # Initialize on first call
        sfia_svc = SfiaService(...)
        current_app.extensions["matching_service"] = MatchingService(...)
    return current_app.extensions["matching_service"]
```

### 2. **Accuracy Improvements**

**Current Limitations:**
- Generic evidence matches multiple skills with similar scores
- Level detection relies on keyword matching (not semantic understanding)
- No handling of ambiguous/multi-skill evidence

**Improvements:**

#### A. Fine-Tune Model on SFIA Data
Train a custom sentence-transformer on SFIA skill pairs:
```python
from sentence_transformers import InputExample, losses
from torch.utils.data import DataLoader

# Create training pairs
train_examples = [
    InputExample(texts=['evidence text', 'SFIA skill description'], label=0.9),
    ...
]

# Fine-tune
train_dataloader = DataLoader(train_examples, shuffle=True, batch_size=16)
model.fit(train_objectives=[(train_dataloader, losses.CosineSimilarityLoss(model))])
```

#### B. Add Re-Ranking Layer
After retrieval, use a cross-encoder for more accurate scoring:
```python
from sentence_transformers import CrossEncoder

reranker = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')
scores = reranker.predict([(evidence, skill_desc) for skill_desc in candidates])
```

#### C. Implement Multi-Skill Detection
Allow evidence to match multiple skills equally:
```python
# Instead of top 5, cluster high-scoring skills
def detect_skill_clusters(matches, threshold=0.7):
    primary = [m for m in matches if m['score'] >= threshold]
    secondary = [m for m in matches if 0.5 <= m['score'] < threshold]
    return {'primary': primary, 'secondary': secondary}
```

#### D. Improve Level Detection
Replace keyword-based level detection with semantic comparison:
```python
def _analyze_level_semantic(self, responsibility_text):
    """Compare responsibility semantically to all 7 levels."""
    resp_embedding = self.model.encode(responsibility_text)
    level_embeddings = self.model.encode(list(self.level_descriptors.values()))
    scores = util.cos_sim(resp_embedding, level_embeddings)[0]
    return int(torch.argmax(scores)) + 1
```

### 3. **User Experience**

#### A. Add Skill Explanations
Include SFIA level descriptions in response:
```python
"matches": [{
    ...
    "level_description": "Level 3: Works independently, guides others",
    "next_level": "To reach Level 4, demonstrate: team leadership, ..."
}]
```

#### B. Save Results / History
Add user accounts or local storage:
```javascript
// Frontend
localStorage.setItem('match_history', JSON.stringify(results));
```

#### C. Batch Upload
Allow CSV upload with multiple STAR examples:
```python
@main.route("/batch", methods=["POST"])
def batch_match():
    csv_file = request.files['file']
    results = []
    for row in csv.DictReader(csv_file):
        result = _get_matcher().match(row['evidence'], ...)
        results.append(result)
    return jsonify({"results": results})
```

#### D. Export to PDF/CV Format
Generate formatted PDF reports:
```python
from weasyprint import HTML

@main.route("/export-pdf", methods=["POST"])
def export_pdf():
    html_content = render_template('pdf_template.html', matches=data['matches'])
    pdf = HTML(string=html_content).write_pdf()
    return Response(pdf, mimetype='application/pdf')
```

### 4. **Data & Scalability**

#### A. Update SFIA Ontology
Currently uses SFIA 9 (2025). When SFIA 10 releases:
1. Replace `SFIA_9_*.ttl` file
2. Delete `.embedding_cache/` folder
3. Restart app (embeddings will recompute)

#### B. Add More Domains
SFIA covers IT skills. To expand:
- Parse additional ontologies (e.g., O*NET for general skills)
- Combine embeddings from multiple frameworks
- Allow user to select domain

#### C. Multi-Language Support
```python
# Use multilingual model
MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"

# In routes.py
@main.route("/match", methods=["POST"])
def match():
    language = request.json.get('language', 'en')
    # Process based on language
```

### 5. **Security Enhancements**

#### A. Add Authentication
```python
from flask_login import LoginManager, login_required

login_manager = LoginManager()
login_manager.init_app(app)

@main.route("/match", methods=["POST"])
@login_required
def match():
    ...
```

#### B. Implement Audit Logging
```python
import logging

audit_logger = logging.getLogger('audit')
audit_logger.addHandler(logging.FileHandler('audit.log'))

@main.route("/match", methods=["POST"])
def match():
    audit_logger.info(f"Match request from {request.remote_addr}")
    ...
```

#### C. Add Content Filtering
Prevent injection of malicious content:
```python
import re

def sanitize_evidence(text):
    # Remove URLs
    text = re.sub(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+])+', '', text)
    # Remove potential SQL
    text = re.sub(r'(DROP|DELETE|INSERT|UPDATE)\s+TABLE', '', text, flags=re.I)
    return text
```

### 6. **Monitoring & Observability**

#### A. Add Application Metrics
```python
from prometheus_flask_exporter import PrometheusMetrics

metrics = PrometheusMetrics(app)

@metrics.counter('match_requests', 'Number of match requests')
def match():
    ...
```

#### B. Add Structured Logging
```python
import structlog

logger = structlog.get_logger()
logger.info("match_request", user_id=user_id, evidence_length=len(evidence))
```

#### C. Add Error Tracking
```python
import sentry_sdk
from sentry_sdk.integrations.flask import FlaskIntegration

sentry_sdk.init(
    dsn="your-sentry-dsn",
    integrations=[FlaskIntegration()]
)
```

---

## Code Style & Conventions

**Python:**
- PEP 8 compliance
- Type hints where applicable
- Docstrings for all public functions (Google style)
- Max line length: 88 (Black formatter)

**Linting:**
```bash
pip install black flake8 mypy
black app/ tests/
flake8 app/ tests/
mypy app/
```

**Pre-commit Hook:**
```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/psf/black
    rev: 23.3.0
    hooks:
      - id: black
  - repo: https://github.com/pycqa/flake8
    rev: 6.0.0
    hooks:
      - id: flake8
```

---

## Common Issues & Troubleshooting

### Issue: "Out of memory" on deployment

**Cause**: sentence-transformers model + SFIA embeddings exceed available RAM

**Solutions:**
1. Use lazy loading (load model on first request)
2. Switch to smaller model (`paraphrase-MiniLM-L3-v2`)
3. Upgrade hosting plan
4. Use model quantization:
```python
model = SentenceTransformer(model_name)
model.half()  # FP16 precision (reduces memory by 50%)
```

### Issue: Slow first request (~30s)

**Cause**: Embedding computation on first run

**Solution**: Pre-compute embeddings in build step:
```bash
# In Dockerfile or build script
RUN python -c "from app import create_app; create_app()"
```

### Issue: CSRF token errors

**Cause**: Token not being sent with POST requests

**Solution**: Ensure frontend includes token:
```javascript
fetch('/match', {
    method: 'POST',
    headers: {
        'X-CSRFToken': csrfToken,
        'Content-Type': 'application/json'
    },
    body: JSON.stringify(data)
})
```

### Issue: Rate limit false positives

**Cause**: Multiple users behind same IP (NAT/proxy)

**Solution**: Use user-based limits instead of IP:
```python
@limiter.limit("5/minute", key_func=lambda: current_user.id)
```

### Issue: Inaccurate skill matches

**Cause**: Evidence too generic or model bias

**Solution:**
1. Prompt users to be more specific (frontend guidance)
2. Implement confidence thresholds (only show matches >60%)
3. Fine-tune model on domain data

---

## CI/CD Pipeline

**Recommended Setup (GitHub Actions):**

```yaml
# .github/workflows/ci.yml
name: CI

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest black flake8
      - name: Lint
        run: |
          black --check app/ tests/
          flake8 app/ tests/
      - name: Test
        run: pytest tests/ -v
      
  deploy:
    needs: test
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    steps:
      - name: Deploy to Render
        run: |
          curl -X POST ${{ secrets.RENDER_DEPLOY_HOOK }}
```

---

## API Integration Examples

For external systems wanting to integrate:

### Python Client

```python
import requests

class SFIAMatcher:
    def __init__(self, base_url, secret_key=None):
        self.base_url = base_url
        self.session = requests.Session()
        self._get_csrf_token()
    
    def _get_csrf_token(self):
        resp = self.session.get(f"{self.base_url}/csrf-token")
        self.csrf_token = resp.json()['csrf_token']
    
    def match(self, evidence, level_context=None):
        data = {
            'situation': evidence.get('situation', ''),
            'task': evidence.get('task', ''),
            'action': evidence.get('action', ''),
            'result': evidence.get('result', ''),
            'level_context': level_context or ''
        }
        resp = self.session.post(
            f"{self.base_url}/match",
            json=data,
            headers={'X-CSRFToken': self.csrf_token}
        )
        return resp.json()

# Usage
matcher = SFIAMatcher('https://your-app.onrender.com')
result = matcher.match({
    'action': 'I developed a Python web scraper...',
    'result': 'Successfully collected 10k records'
})
print(result['matches'][0]['skill_code'])
```

### JavaScript Client

```javascript
class SFIAMatcher {
    constructor(baseURL) {
        this.baseURL = baseURL;
        this.csrfToken = null;
    }
    
    async init() {
        const resp = await fetch(`${this.baseURL}/csrf-token`);
        const data = await resp.json();
        this.csrfToken = data.csrf_token;
    }
    
    async match(evidence) {
        const resp = await fetch(`${this.baseURL}/match`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': this.csrfToken
            },
            body: JSON.stringify(evidence)
        });
        return await resp.json();
    }
}

// Usage
const matcher = new SFIAMatcher('https://your-app.onrender.com');
await matcher.init();
const result = await matcher.match({
    action: 'I developed a Python web scraper...',
    result: 'Successfully collected 10k records'
});
console.log(result.matches[0].skill_code);
```

---

## Database Schema (Future Enhancement)

If you add user accounts and history:

```sql
-- Users table
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Match history
CREATE TABLE match_history (
    id SERIAL PRIMARY KEY,
    user_id INT REFERENCES users(id),
    evidence_text TEXT NOT NULL,
    level_context TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    INDEX idx_user_created (user_id, created_at)
);

-- Match results (denormalized for quick retrieval)
CREATE TABLE match_results (
    id SERIAL PRIMARY KEY,
    match_history_id INT REFERENCES match_history(id),
    skill_code VARCHAR(10) NOT NULL,
    skill_title VARCHAR(255) NOT NULL,
    score FLOAT NOT NULL,
    rank INT NOT NULL,
    justification TEXT,
    evidence_snippet TEXT
);
```

---

## Contributing

**Workflow:**
1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make changes and add tests
4. Run tests and linting (`pytest && black . && flake8`)
5. Commit changes (`git commit -m 'Add amazing feature'`)
6. Push to branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

**Pull Request Checklist:**
- [ ] Tests pass (`pytest tests/ -v`)
- [ ] Code is formatted (`black app/ tests/`)
- [ ] No linting errors (`flake8 app/ tests/`)
- [ ] Documentation updated (if applicable)
- [ ] CHANGELOG.md updated (if applicable)

---

## Resources

**SFIA Framework:**
- Official site: https://sfia-online.org
- SFIA 9 documentation: https://sfia-online.org/en/sfia-9
- RDF/OWL ontology: Check SFIA downloads page

**Sentence Transformers:**
- Documentation: https://www.sbert.net
- Model hub: https://huggingface.co/sentence-transformers
- Training guide: https://www.sbert.net/docs/training/overview.html

**Flask Security:**
- Flask security checklist: https://flask.palletsprojects.com/en/3.0.x/security/
- OWASP Top 10: https://owasp.org/www-project-top-ten/

---

## License

Check the LICENSE file in the repository root. Note that SFIA content is subject to SFIA Foundation licensing - see `SFIA_LICENSE_NOTE`.

---

## Contact & Support

For technical questions or contributions, open an issue on the GitHub repository or contact the maintainer.

---

**Happy coding! 🚀**
