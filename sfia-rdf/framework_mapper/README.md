# SFIA Framework Mapper

Maps competencies from other professional frameworks to SFIA 9 skills using dual-embedding semantic matching.

## Quick Start

```bash
cd framework_mapper
pip install -r requirements.txt
python run.py
```

Navigate to `http://localhost:5001` to use the application.

## What This Does

Instead of mapping individual evidence directly to SFIA skills (like sfia_app_v2), this app maps **professional framework competencies** to SFIA skills. 

**Use Case**: You hold a professional registration (e.g., Chartered Engineer from UK Eng Council) and want to know which SFIA skills align with your competencies.

**Workflow**:
1. Select your professional framework (e.g., UK Engineering Council)
2. Select your registration level (e.g., CEng - Chartered Engineer)
3. Select a specific competency (e.g., Competency A: Engineering Knowledge)
4. Provide STAR evidence demonstrating that competency
5. Get matched SFIA skills that align with both the competency and your evidence

---

## Supported Frameworks

### UK Engineering Council (UK-SPEC) ✅ **Available Now**
- **Chartered Engineer (CEng)** - 5 competencies (A-E) + 4 commitment standards
- **Incorporated Engineer (IEng)** - 5 competencies (A-E) + 4 commitment standards  
- **Engineering Technician (EngTech)** - 5 competencies (A-E) + 4 commitment standards

### Coming Soon
- NICE Cybersecurity Framework 🔜
- ITIL Service Management Framework 🔜

---

## How It Works

### Dual-Embedding Architecture

Unlike the direct evidence→SFIA matching in `sfia_app_v2`, this app uses **two-stage matching**:

**Stage 1: Evidence Validation**
- Your evidence is matched against the selected framework competency
- Validation score indicates how well your evidence demonstrates the competency
- Keyword matching identifies specific indicators you've addressed

**Stage 2: SFIA Mapping**
- Framework competency context (60% weight) + Your evidence (40% weight)
- Semantic similarity computed against all SFIA skills
- Results ranked by alignment strength
- Suggested SFIA level based on your registration level

### Scoring Formula

```
Overall Match = (0.60 × Competency-SFIA Alignment) + (0.40 × Evidence-SFIA Match)
```

---

## Architecture Difference from sfia_app_v2

**sfia_app_v2**: `User Evidence → SFIA Skills`
- Direct semantic matching
- No framework context
- Focus: Individual competency demonstration

**framework_mapper**: `Framework Competency + User Evidence → SFIA Skills`
- Dual-embedding matching
- Framework-aware  
- Focus: Mapping between professional standards

### Key Changes:
1. **Dual embeddings**: Both source framework competencies and SFIA skills are embedded
2. **Framework parsers**: Modular parsers for each framework (UK Eng, NICE, ITIL)
3. **Competency-first matching**: Validate evidence against framework, then map to SFIA
4. **Bidirectional mapping**: Can show SFIA→Framework or Framework→SFIA

---

## Project Structure

```
framework_mapper/
├── frameworks/
│   └── ukeng_standards.json          # UK Eng Council competency data
├── app/
│   ├── routes.py                     # Flask API endpoints
│   ├── templates/
│   │   └── index.html               # Frontend UI
│   └── services/
│       ├── framework_parser.py       # Load framework standards
│       └── framework_matching.py     # Dual-embedding matching logic
├── run.py                           # Flask app entry point
├── requirements.txt                 # Python dependencies
├── config.py                        # Application configuration
└── README.md
```

---

## API Endpoints

### GET `/api/frameworks`
List all available frameworks

### GET `/api/frameworks/<framework_id>/registrations`
Get registration levels for a framework (e.g., CEng, IEng, EngTech)

### GET `/api/frameworks/<framework_id>/<registration_code>/<competency_code>`
Get detailed information about a specific competency

### POST `/api/validate`
Validate evidence against a framework competency

**Request**:
```json
{
  "evidence": "STAR evidence text...",
  "framework_id": "ukeng",
  "registration_code": "CEng",
  "competency_code": "A"
}
```

**Response**:
```json
{
  "success": true,
  "validation": {
    "competency_code": "A",
    "competency_title": "Use engineering knowledge...",
    "match_score": 0.72,
    "relevance": "high",
    "keyword_matches": ["analysis", "engineering principles", "standards"],
    "feedback": "✓ Strong match! Your evidence demonstrates..."
  }
}
```

### POST `/api/map`
Map framework competency + evidence to SFIA skills

**Request**:
```json
{
  "evidence": "STAR evidence text...",
  "framework_id": "ukeng",
  "registration_code": "CEng",
  "competency_code": "A",
  "top_k": 10
}
```

**Response**:
```json
{
  "success": true,
  "result": {
    "validation": { ... },
    "sfia_mappings": [
      {
        "skill_code": "TECH",
        "skill_name": "Solution Design",
        "skill_description": "...",
        "overall_score": 0.85,
        "competency_alignment": 0.88,
        "evidence_score": 0.80,
        "suggested_level": 5,
        "level_confidence": 0.75,
        "rationale": "Strong alignment between Solution Design and..."
      }
    ]
  }
}
```

---

## Setup

```bash
cd framework_mapper
pip install -r requirements.txt
python run.py
```

Open http://localhost:5001

---

## Usage Example - UK Engineering Council

### Scenario
You're registered as a **Chartered Engineer (CEng)** with evidence for competency **A: Use a combination of general and specialist engineering knowledge and understanding**.

### Input:
- **Framework**: UK Engineering Council (CEng)
- **Competency**: A - Engineering Knowledge
- **Your Evidence**: "I designed a structural analysis system using FEA principles, combining mechanical engineering theory with computational methods. I selected appropriate materials based on stress analysis, developed custom algorithms for load distribution, and validated results against industry standards like Eurocode."

### Output:
The app shows which SFIA skills map to this competency:

1. **EMRG (Emerging technology monitoring)** - 78% match
   - *Why*: Applying new computational methods in engineering
   
2. **METL (Methods and tools)** - 85% match
   - *Why*: Selecting and applying appropriate engineering methods (FEA)
   
3. **ARCH (Solution architecture)** - 72% match
   - *Why*: Designing system structure based on engineering requirements

4. **TEST (Testing)** - 68% match
   - *Why*: Validation against standards

You can now claim these SFIA skills on your profile/CV, backed by your UK-SPEC evidence.

---

## Framework Data Files

### UK Engineering Council (`frameworks/ukeng_standards.json`)

```json
{
  "CEng": {
    "title": "Chartered Engineer",
    "description": "...",
    "competencies": {
      "A": {
        "code": "A",
        "title": "Engineering Knowledge and Understanding",
        "description": "Use a combination of general and specialist engineering knowledge...",
        "indicators": ["...", "..."]
      },
      ...
    }
  }
}
```

### Adding New Frameworks

1. Create `frameworks/{framework_name}.json` with competency data
2. Create `frameworks/{framework_name}_parser.py` to parse it
3. Add framework to the UI dropdown
4. The matching logic remains the same (semantic similarity)

---

## API Differences

### Main Endpoint: `POST /map`

```json
{
  "framework": "ukeng_council",
  "registration": "CEng",
  "competency_code": "A",
  "evidence": "I designed a structural analysis system...",
  "level_context": "I worked independently as lead engineer"
}
```

Response:
```json
{
  "framework_competency": {
    "code": "A",
    "title": "Engineering Knowledge and Understanding",
    "match_confidence": 0.92
  },
  "sfia_matches": [
    {
      "skill_code": "METL",
      "skill_title": "Methods and tools",
      "score": 0.85,
      "justification": "...",
      "evidence_snippet": "...",
      "framework_alignment": 0.78
    }
  ],
  "detected_level": 4,
  "mapping_summary": "Your CEng competency A evidence maps to 4 SFIA skills at Level 3-4"
}
```

---

## Benefits Over Individual Evidence Matching

### For Users:
- ✅ Leverage existing professional registrations (CEng, CISSP, etc.)
- ✅ One piece of evidence can map to multiple SFIA skills
- ✅ Framework-validated competency structure provides consistency
- ✅ Build SFIA portfolio from existing professional development records

### For Organizations:
- ✅ Map existing staff qualifications to SFIA framework
- ✅ Understand skills gaps using familiar frameworks
- ✅ Bridge between engineering/cybersecurity standards and IT competencies

---

## Development Roadmap

### Phase 1: UK Engineering Council ✅
- [x] Parse UK-SPEC standards (CEng, IEng, EngTech)
- [ ] Core matching pipeline
- [ ] UI for framework selection
- [ ] Competency → SFIA mapping algorithm

### Phase 2: NICE Framework
- [ ] Parse NICE Cybersecurity Workforce Framework
- [ ] Map 52 specialty areas to SFIA
- [ ] Add KSA (Knowledge, Skills, Abilities) matching

### Phase 3: ITIL
- [ ] Parse ITIL 4 practices
- [ ] Map service management competencies to SFIA
- [ ] Add organization-specific customization

### Phase 4: Reverse Mapping
- [ ] SFIA → Other frameworks (show which competencies a SFIA skill covers)
- [ ] Batch mapping (upload CPD records, get SFIA portfolio)
- [ ] Framework crosswalk (e.g., CEng competency A = NICE specialty area X)

---

## License

Same as parent project - see LICENSE file.

---

## Questions?

See `DEVELOPER_GUIDE.md` for technical implementation details.
