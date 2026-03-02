# SFIA Level Matching — How It Works

This document explains the technical pipeline used to detect a user's **SFIA Level of Responsibility** (1–7) from their written evidence, and how that detected level influences the final skill ranking.

---

## Overview

Level matching is a **two-stage process**:

1. **Detection** — Determine which SFIA level (1–7) the user's responsibility description most strongly aligns with.
2. **Scoring Modifier** — Boost or penalise candidate SFIA skill×level entries based on how close they are to the detected level.

---

## Stage 1: Level Detection

The `_analyze_level()` method in `matching.py` performs an **ensemble** of two complementary signals.

### Signal A — Semantic Similarity (70% weight)

Each of the 7 SFIA levels of responsibility is represented by a pre-computed embedding vector. These are built from a rich composite text for each level, combining:

- The **formal SFIA ontology descriptors** (Autonomy, Influence, Complexity, Knowledge, Business Skills)
- A plain-English **summary label** (e.g. *"Enable — leads small teams, designs solutions..."*)

At match time, the user's responsibility description is encoded into the same embedding space. The cosine similarity between the user's vector and each of the 7 level vectors determines the **semantic score** for that level.

```
context_embedding = model.encode(user_responsibility_text)
level_scores = cosine_similarity(context_embedding, level_embeddings)   # shape: (7,)
```

### Signal B — Keyword Indicators (30% weight)

To disambiguate adjacent levels (e.g. Level 4 vs 5, which are semantically similar), the system also pattern-matches **level-specific indicator phrases** across three categories:

| Category | Example Indicators |
|---|---|
| **Supervision** | *"close supervision"* (L1) · *"broad direction"* (L4–5) · *"full autonomy"* (L7) |
| **Authority** | *"following instructions"* (L1) · *"accountable for outcomes"* (L5) · *"set strategy"* (L7) |
| **Scope** | *"routine tasks"* (L1) · *"cross-functional"* (L4) · *"enterprise-wide"* (L6–7) |

Longer, more specific phrases are weighted 1.5× vs. shorter ones.

### Combined Score

```
final_level_score = 0.70 × semantic_score + 0.30 × keyword_score
```

The level with the highest combined score is selected as `detected_level`.

### Tie-breaking

If the top two levels score within **5%** of each other, the **lower level is always preferred**. This is a deliberate conservative bias — for professional competency evidence it is safer to under-claim than over-claim.

When a tie-break occurs, the UI displays a ⚠️ borderline warning explaining which two levels were close.

### Confidence Bands

| Label | Meaning |
|---|---|
| `high` | Clear winner, >5% margin above the next level |
| `moderate` | Winner, but margin is relatively narrow |
| `borderline` | Top-2 within 5% — lower level selected as safer option |

---

## Stage 2: Level Scoring Modifier

Once `detected_level` is known, each candidate SFIA skill entry (which has its own level, 1–7) is multiplied by a **level modifier** based on its distance from the detected level.

| Distance from detected level | Modifier | Effect |
|---|---|---|
| **0** (exact match) | **×1.15** | +15% boost |
| **1** (one level off) | **×1.00** | Neutral |
| **2** (two levels off) | **×0.90** | −10% penalty |
| **≥3** (far off) | **×0.70** | −30% penalty |

This means a skill like *"Security Administration (SCAD) Level 4"* that perfectly matches a detected Level 4 user will rank significantly higher than the same skill entered at Level 6, even if the semantic text similarity is identical.

---

## Evidence Snippet Citation

In parallel with scoring, each paragraph chunk of the user's evidence is embedded independently. For each matched skill, the **paragraph most semantically similar** to that skill's embedding is surfaced as the *"evidence snippet"* — the extract most strongly justifying why that skill was matched.

---

## Full Pipeline Summary

```
User STAR Evidence
        │
        ├─► Parse into STAR sections (Situation / Task / Action / Result)
        │
        ├─► Encode Action embedding  ─────────────────────────────────────┐
        │   Encode Context embedding                                      │
        │                                                                 ▼
        │                                              Dual semantic search against
        │                                              SFIA skill corpus embeddings
        │                                              (Action ×70, Context ×40 top-k)
        │
        ├─► Encode Level-of-Responsibility text
        │       │
        │       ├─► Cosine sim vs. 7 level embeddings  (70% weight)
        │       └─► Keyword indicator matching          (30% weight)
        │               └─► detected_level (1–7)
        │
        └─► For every candidate skill×level:
                score = (0.70 × action_sim) + (0.30 × context_sim)
                score *= keyword_boost   (if applicable)
                score *= level_modifier  (based on distance from detected_level)
                score = min(score, 1.0)
        │
        └─► Deduplicate, rank, return top 5 unique skills
```

---

## Key Files

| File | Role |
|---|---|
| `sfia_app_v2/app/services/matching.py` | Full pipeline — `MatchingService.match()`, `_analyze_level()`, `_calculate_level_keyword_scores()` |
| `sfia_app_v2/app/services/sfia.py` | Loads SFIA skill×level data from RDF (`.ttl`), builds `generic_levels` with level descriptor texts |
| `sfia_app_v2/app/.embedding_cache/` | Cached PyTorch tensors for skill and level embeddings (invalidated if data changes) |
| `sfia_app_v2/app/job_roles_mapping.json` | Job title → SFIA code mapping used for keyword boost building |
