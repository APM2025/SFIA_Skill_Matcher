"""Semantic matching service for SFIA skill detection.

This module implements the core NLP pipeline that maps a user's STAR evidence
statement to the most relevant SFIA 9 skills and levels.

Pipeline overview (see ``MatchingService.match`` for full detail):
    1.  Parse the evidence into STAR sections (Situation / Task / Action / Result)
    2.  Encode Action and Context into separate embedding vectors
    3.  Retrieve candidate skills via dual semantic search (Action + Context)
    4.  Detect the user's SFIA level from their responsibility description
    5.  Extract evidence chunks for per-skill snippet citation
    6.  Score every candidate using weighted multi-vector scoring + keyword boost
        + level modifier
    7.  Deduplicate, rank, and assemble the final result payload
"""

import hashlib
import json
import logging
import os
import re
from collections import defaultdict
from typing import Any, Optional

from sentence_transformers import SentenceTransformer, util
import torch
from flask import current_app

from app.services.sfia import SfiaService
from app.services.llm_rag import get_verdict_service

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_SERVICES_DIR = os.path.dirname(os.path.abspath(__file__))
_APP_DIR = os.path.dirname(_SERVICES_DIR)
_ROLES_MAPPING_PATH = os.path.join(_APP_DIR, "job_roles_mapping.json")
_EMBEDDING_CACHE_DIR = os.path.join(_APP_DIR, ".embedding_cache")


class MatchingService:
    """Encapsulates the full SFIA semantic-matching pipeline.

    On construction the service:
    - Loads the sentence-transformer NLP model
    - Builds discriminative keyword boosts from the job-roles mapping
    - Computes (or restores from disk cache) embeddings for all SFIA skills
      and the seven levels of responsibility
    """

    # ------------------------------------------------------------------
    # Scoring weights
    # ------------------------------------------------------------------
    # Action text (what the user *did*) is the primary skill signal.
    # Context text (Situation + Task) provides domain disambiguation.
    ACTION_WEIGHT: float = 0.70
    CONTEXT_WEIGHT: float = 0.30

    # When the user provides a clarification, blend it with the original
    # action embedding so it steers the re-match without discarding context.
    CLARIFICATION_WEIGHT: float = 0.80
    BASE_ACTION_WEIGHT: float = 0.20

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------
    # Wider Action search catches primary skill matches.
    # Narrower Context search supplements with domain-adjacent skills.
    TOP_K_ACTION: int = 60
    TOP_K_CONTEXT: int = 40

    # ------------------------------------------------------------------
    # Evidence chunking (for snippet citation)
    # ------------------------------------------------------------------
    # Ignore very short paragraph fragments — they rarely cite a full skill.
    MIN_CHUNK_CHARS: int = 40
    MIN_CHUNK_WORDS: int = 6

    # ------------------------------------------------------------------
    # Level detection
    # ------------------------------------------------------------------
    # If the top-2 levels are within this margin, prefer the lower (safer) level.
    TIEBREAK_MARGIN: float = 0.05

    # Score modifiers applied to candidate skills based on their distance from
    # the detected SFIA level.  A boost (+15%) rewards exact matches; penalties
    # grow with distance so clearly-wrong levels rank well below correct ones.
    LEVEL_DISTANCE_PENALTIES: dict[int, float] = {
        0: 1.15,   # exact match → boost
        1: 1.00,   # one level off → neutral
        2: 0.90,   # two levels off → mild penalty
    }
    LEVEL_FAR_PENALTY: float = 0.70   # three or more levels away

    # Multi-factor level detection: distinctive keywords for each level
    # These provide discriminative signals beyond semantic similarity
    _LEVEL_INDICATORS: dict[int, dict[str, list[str]]] = {
        1: {
            "supervision": ["close supervision", "direct supervision", "constant supervision", 
                          "closely supervised", "step by step", "detailed guidance"],
            "authority": ["following instructions", "instructed to", "told to", "guidance", 
                         "learning", "observing", "shadowing"],
            "scope": ["routine tasks", "simple tasks", "basic tasks", "assigned tasks"],
        },
        2: {
            "supervision": ["general supervision", "routine supervision", "regular supervision",
                          "supervised", "oversight"],
            "authority": ["some discretion", "limited independence", "escalate", "refer to",
                         "assist", "support", "help"],
            "scope": ["familiar tasks", "routine problems", "standard procedures"],
        },
        3: {
            "supervision": ["general direction", "minimal supervision", "work independently",
                          "autonomous", "self-directed"],
            "authority": ["own initiative", "discretion", "manage own work", "proactive",
                         "make decisions", "solve problems", "improve"],
            "scope": ["varied tasks", "non-routine", "complex", "team", "colleagues"],
        },
        4: {
            "supervision": ["broad direction", "strategically directed", "minimal oversight"],
            "authority": ["lead", "guide others", "delegate", "coordinate", "mentor",
                         "design solutions", "influence team", "small team"],
            "scope": ["diverse activities", "team objectives", "multiple projects",
                     "cross-functional", "3-10 people", "team of"],
        },
        5: {
            "supervision": ["broad direction", "fully autonomous", "strategic autonomy"],
            "authority": ["accountable", "ensure", "advise", "authoritative guidance",
                         "define standards", "significant decisions", "advise decision makers",
                         "stakeholders", "customers", "suppliers", "multiple teams"],
            "scope": ["significant outcomes", "organisational impact", "department",
                     "strategic", "policy", "10-30 people", "several teams"],
        },
        6: {
            "supervision": ["complete autonomy", "enterprise leadership"],
            "authority": ["executive", "director", "senior leadership", "shape policy",
                         "influence organisation", "high-level decisions", "strategic planning",
                         "organisational collaboration", "enterprise-wide", "boardroom"],
            "scope": ["organisational level", "enterprise", "whole organisation",
                     "cross-organisational", "30+ people", "multiple departments"],
        },
        7: {
            "supervision": ["ultimate authority", "full accountability"],
            "authority": ["ceo", "cio", "cto", "ciso", "c-suite", "chief", "vision",
                         "set strategy", "inspire", "mobilise", "industry influence",
                         "organisational success"],
            "scope": ["entire organisation", "enterprise-wide", "industry", "sector",
                     "100+ people", "executive board"],
        },
    }

    # ------------------------------------------------------------------
    # Keyword boost builder
    # ------------------------------------------------------------------
    # Maximum number of SFIA codes a word may appear in before it is
    # considered too generic to be a useful discriminative keyword.
    MAX_CODES_FOR_KEYWORD: int = 5

    # Default boost multiplier for job-role-derived keywords.
    DEFAULT_KEYWORD_BOOST: float = 1.20

    # Hard-coded tech/tool keywords with higher multipliers.  These terms are
    # strongly domain-specific and rarely appear in the ontology text itself.
    _TECH_SEEDS: dict[str, tuple[list[str], float]] = {
        "PROG": (
            ["python", "java", "c++", "c#", "javascript", "html", "css",
             "react", "node", "sql", "bash", "ruby", "kotlin", "swift"],
            1.25,
        ),
        "DAAN": (
            ["tableau", "powerbi", "looker", "machine learning", "pandas",
             "numpy", "sql", "python", "r studio", "dashboard", "kpi", "metric"],
            1.40,
        ),
        "TEST": (
            ["selenium", "cypress", "junit", "pytest", "jest", "postman",
             "jira", "qa", "regression", "functional test"],
            1.25,
        ),
        "SCTY": (
            ["siem", "soc", "penetration", "pen test", "vulnerability",
             "gdpr", "infosec", "owasp", "encryption", "zero trust"],
            1.30,
        ),
        "DESN": (
            ["figma", "sketch", "invision", "wireframe", "prototype",
             "ux", "ui", "user journey", "axure"],
            1.20,
        ),
    }

    # Words that appear in many job titles but carry no discriminative value.
    _STOP_WORDS: set[str] = {
        "and", "or", "the", "of", "in", "for", "a", "an", "to", "with",
        "at", "by", "on", "as", "is", "it", "be", "this", "that", "from",
        "lead", "head", "senior", "junior", "principal", "associate", "executive",
        "officer", "director", "vp", "assistant", "deputy", "chief",
        "manager", "management", "specialist", "analyst", "professional",
        "consultant", "advisor", "expert", "team", "group", "digital", "global",
        "technical", "technology", "service", "services", "business", "enterprise",
    }

    # ------------------------------------------------------------------

    def __init__(self, model_name: str, sfia_service: SfiaService) -> None:
        """Load the NLP model and prepare all embeddings.

        Args:
            model_name: Sentence-transformer model identifier
                (e.g. ``"all-MiniLM-L6-v2"``).
            sfia_service: An already-initialised ``SfiaService`` instance that
                provides ``sfia_data`` and ``generic_levels``.
        """
        # Limit PyTorch to one inter-op thread — reduces per-thread memory
        # overhead significantly on memory-constrained hosts (e.g. Render free tier).
        torch.set_num_threads(1)

        logger.info("Loading NLP model: %s...", model_name)
        self.model = SentenceTransformer(model_name)
        self._model_name = model_name
        self.sfia_service = sfia_service
        self.sfia_embeddings: Optional[torch.Tensor] = None
        self.level_embeddings: Optional[torch.Tensor] = None

        self.KEYWORD_BOOSTS = self._build_keyword_boosts()
        self.compute_embeddings()

    # ------------------------------------------------------------------
    # Keyword boost builder
    # ------------------------------------------------------------------

    def _build_keyword_boosts(self) -> dict[str, tuple[list[str], float]]:
        """Build per-SFIA-code discriminative keyword boost entries.

        Reads ``job_roles_mapping.json`` and applies a TF-IDF-style filter:
        words that appear across more than ``MAX_CODES_FOR_KEYWORD`` codes are
        too generic (e.g. "manager", "analyst") and are discarded.  Only words
        specific to a small number of codes are kept as boost triggers.

        The hard-coded ``_TECH_SEEDS`` entries are merged in afterwards, using
        whichever boost multiplier is higher.

        Returns:
            A dict mapping SFIA code → ``(keyword_list, boost_multiplier)``.
            During matching, if any keyword is found in the user's action text,
            the candidate's score is multiplied by the multiplier.
        """
        roles_mapping: dict[str, list[str]] = {}
        if os.path.exists(_ROLES_MAPPING_PATH):
            try:
                with open(_ROLES_MAPPING_PATH, encoding="utf-8") as fh:
                    roles_mapping = json.load(fh)
            except Exception:
                logger.exception("Auto-boost builder: could not load roles mapping.")

        # Step 1: tokenise job titles per code, excluding stop words
        code_words: dict[str, set[str]] = {}
        for code, job_titles in roles_mapping.items():
            keywords: set[str] = set()
            for title in job_titles:
                for word in re.split(r"[\s/,\-\(\)]+", title.lower()):
                    word = word.strip()
                    if len(word) >= 4 and word not in self._STOP_WORDS:
                        keywords.add(word)
            if keywords:
                code_words[code] = keywords

        # Step 2: compute document frequency (how many codes contain each word)
        word_doc_freq: dict[str, int] = defaultdict(int)
        for words in code_words.values():
            for word in words:
                word_doc_freq[word] += 1

        # Step 3: keep only words that are specific to ≤ MAX_CODES_FOR_KEYWORD codes
        boosts: dict[str, tuple[list[str], float]] = {}
        for code, words in code_words.items():
            distinctive = sorted(
                w for w in words if word_doc_freq[w] <= self.MAX_CODES_FOR_KEYWORD
            )
            if distinctive:
                boosts[code] = (distinctive, self.DEFAULT_KEYWORD_BOOST)

        # Step 4: merge in hard tech-seed boosts (higher multiplier wins)
        for code, (seed_keywords, seed_multiplier) in self._TECH_SEEDS.items():
            if code in boosts:
                merged_keywords = sorted(set(boosts[code][0]) | set(seed_keywords))
                merged_multiplier = max(boosts[code][1], seed_multiplier)
                boosts[code] = (merged_keywords, merged_multiplier)
            else:
                boosts[code] = (seed_keywords, seed_multiplier)

        logger.info(
            "Auto-Boost: built discriminative keyword boosts for %d SFIA codes.", len(boosts)
        )
        return boosts

    # ------------------------------------------------------------------
    # Embedding computation & caching
    # ------------------------------------------------------------------

    def compute_embeddings(self) -> None:
        """Encode all SFIA skill texts and level descriptors into tensors.

        Results are persisted to ``app/.embedding_cache/`` so subsequent
        starts load from disk (~1 s) instead of recomputing (~30 s).

        The cache key includes the model name, corpus sizes, and the
        modification time of ``job_roles_mapping.json``.  Any change to the
        roles file automatically invalidates the cache.
        """
        # Load job-role augmentation map (used to enrich the skill corpus)
        roles_mapping: dict[str, list[str]] = {}
        if os.path.exists(_ROLES_MAPPING_PATH):
            try:
                with open(_ROLES_MAPPING_PATH, encoding="utf-8") as fh:
                    roles_mapping = json.load(fh)
                logger.info(
                    "Loaded job-roles augmentation map (%d codes).", len(roles_mapping)
                )
            except Exception:
                logger.exception("Could not load job-roles map.")

        # Build the corpus: each skill's composite text, optionally augmented
        # with illustrative job titles from the roles mapping
        skill_texts: list[str] = []
        for item in self.sfia_service.sfia_data:
            code = item["code"]
            if code in roles_mapping and roles_mapping[code]:
                role_str = ", ".join(roles_mapping[code])
                skill_texts.append(
                    f"{item['text']}\nIllustrative Job Roles for this skill: {role_str}."
                )
            else:
                skill_texts.append(item["text"])

        level_texts = [lvl["text"] for lvl in self.sfia_service.generic_levels]

        # Cache key: model name + corpus sizes + MD5 of roles file content.
        # Content-based (not mtime-based) so the key is identical on any machine
        # that has the same data — including after a fresh git clone or deployment.
        if os.path.exists(_ROLES_MAPPING_PATH):
            with open(_ROLES_MAPPING_PATH, "rb") as fh:
                roles_hash = hashlib.md5(fh.read()).hexdigest()[:8]
        else:
            roles_hash = "absent"
        levels_hash = hashlib.md5("|".join(level_texts).encode()).hexdigest()[:8]
        raw_key = f"{self._model_name}|{len(skill_texts)}|{len(level_texts)}|{roles_hash}|{levels_hash}"
        cache_key = hashlib.md5(raw_key.encode()).hexdigest()[:12]

        os.makedirs(_EMBEDDING_CACHE_DIR, exist_ok=True)
        cache_file = os.path.join(_EMBEDDING_CACHE_DIR, f"embeddings_{cache_key}.pt")

        if os.path.exists(cache_file):
            logger.info("Loading cached embeddings from %s...", cache_file)
            cached = torch.load(cache_file, weights_only=True)
            self.sfia_embeddings = cached["sfia"]
            self.level_embeddings = cached["levels"]
            logger.info("Embeddings loaded from cache.")
        else:
            logger.info(
                "Computing embeddings for %d skills + %d levels "
                "(first run — will be cached)...",
                len(skill_texts),
                len(level_texts),
            )
            self.sfia_embeddings = self.model.encode(skill_texts, convert_to_tensor=True)
            self.level_embeddings = self.model.encode(level_texts, convert_to_tensor=True)
            torch.save(
                {"sfia": self.sfia_embeddings, "levels": self.level_embeddings},
                cache_file,
            )
            logger.info("Embeddings cached to %s.", cache_file)

    # ------------------------------------------------------------------
    # STAR section parser
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_star_sections(evidence: str) -> dict[str, str]:
        """Parse a free-text STAR evidence statement into labelled sections.

        Recognises headings such as "Situation:", "Task", "Action —",
        "Result", and "Level of Responsibility" (case-insensitive, optional
        trailing punctuation).  Any unrecognised or missing sections default
        to an empty string; the caller is responsible for falling back to the
        full text when needed.

        Args:
            evidence: The raw evidence text submitted by the user.

        Returns:
            A dict with keys ``situation``, ``task``, ``action``, ``result``,
            and ``responsibility``.  Missing sections are empty strings.

        Edge cases:
            - Evidence with no STAR headings → all values are empty strings
            - Only some sections present → missing ones are empty strings
            - Duplicate headings → last occurrence wins
        """
        sections: dict[str, str] = {
            "situation": "",
            "task": "",
            "action": "",
            "result": "",
            "responsibility": "",
        }

        heading_pattern = re.compile(
            r"(?:^|\n)\s*(?P<heading>"
            r"situation|task|action|result|level\s+of\s+responsibility|responsibility"
            r")\s*[:.\-]?\s*\n",
            re.IGNORECASE,
        )

        heading_positions = [
            (m.group("heading").lower().split()[0], m.end())
            for m in heading_pattern.finditer(evidence)
        ]

        for i, (name, start) in enumerate(heading_positions):
            if i + 1 < len(heading_positions):
                # End just before the next heading's keyword
                next_name, next_start = heading_positions[i + 1]
                end = next_start - len(next_name) - 5
            else:
                end = len(evidence)

            key = "responsibility" if "respon" in name else name
            if key in sections:
                sections[key] = evidence[start:end].strip()

        return sections

    # ------------------------------------------------------------------
    # Main matching pipeline
    # ------------------------------------------------------------------

    def match(
        self,
        evidence: str,
        level_context: str,
        clarification: Optional[str] = None,
    ) -> dict[str, Any]:
        """Map a STAR evidence statement to the top SFIA skill×level matches.

        Pipeline steps:
            1. Parse evidence into STAR sections (Situation, Task, Action, Result)
            2. Encode Action and Context as separate embedding vectors.
               If *clarification* is provided, blend it with the Action embedding
               (``CLARIFICATION_WEIGHT`` : ``BASE_ACTION_WEIGHT``) so the re-match
               is steered without discarding the original intent.
            3. Retrieve candidates via dual semantic search — Action (primary,
               wider) and Context (secondary, narrower).  Take the union.
            4. Detect the user's SFIA level from *level_context* using the
               ``_analyze_level`` helper.
            5. Split evidence into paragraph chunks and embed them for snippet
               citation (the chunk with highest cosine similarity to each skill
               embedding is surfaced as the "why this match" quote).
            6. Score every candidate:
               ``score = ACTION_WEIGHT × action_sim + CONTEXT_WEIGHT × context_sim``
               then apply keyword boost (if any distinctive keyword found in
               action text) and a level modifier based on distance from the
               detected level.
            7. Sort, deduplicate to ≤ 5 unique skills, and build the result dict.

        Args:
            evidence: Full STAR text assembled from the four form fields.
            level_context: The user's optional "Level of Responsibility" text.
            clarification: Optional free-text correction from the refine flow.

        Returns:
            A dict with:
            - ``matches``: list of up to 5 skill dicts (code, label, level,
              description, category, notes, score, boost_reason, evidence_snippet)
            - ``detected_level``: int or None
            - ``level_breakdown``: top-3 level candidates with scores and snippets
            - ``best_fit_summary``: HTML string with the overall conclusion
        """
        # ----------------------------------------------------------------
        # Step 1 — Parse STAR sections
        # ----------------------------------------------------------------
        sections = self._parse_star_sections(evidence)

        # Context text establishes *domain and problem space*
        context_text = " ".join(
            filter(None, [sections["situation"], sections["task"]])
        ).strip()
        # Action text establishes *what functional skill was demonstrated*
        action_text = " ".join(
            filter(None, [sections["action"], sections["result"]])
        ).strip()

        # Fallback: if no STAR headings were detected, use the full text for both
        if not action_text:
            action_text = evidence
        if not context_text:
            context_text = evidence

        # ----------------------------------------------------------------
        # Step 2 — Encode embeddings
        # ----------------------------------------------------------------
        action_weight = current_app.config.get("ACTION_WEIGHT", self.ACTION_WEIGHT)
        context_weight = current_app.config.get("CONTEXT_WEIGHT", self.CONTEXT_WEIGHT)
        clarification_weight = current_app.config.get("CLARIFICATION_WEIGHT", self.CLARIFICATION_WEIGHT)
        base_action_weight = current_app.config.get("BASE_ACTION_WEIGHT", self.BASE_ACTION_WEIGHT)
        
        action_embedding = self.model.encode(action_text, convert_to_tensor=True)
        if clarification and clarification.strip():
            clarification_embedding = self.model.encode(
                clarification.strip(), convert_to_tensor=True
            )
            # Blend: clarification dominates so the re-match steers meaningfully
            action_embedding = (
                clarification_weight * clarification_embedding
                + base_action_weight * action_embedding
            )

        context_embedding = self.model.encode(context_text, convert_to_tensor=True)

        # ----------------------------------------------------------------
        # Step 3 — Dual semantic search (retrieve candidates)
        # ----------------------------------------------------------------
        top_k_action = current_app.config.get("TOP_K_ACTION", self.TOP_K_ACTION)
        top_k_context = current_app.config.get("TOP_K_CONTEXT", self.TOP_K_CONTEXT)
        
        action_hits = {
            hit["corpus_id"]: hit["score"]
            for hit in util.semantic_search(
                action_embedding, self.sfia_embeddings, top_k=top_k_action
            )[0]
        }
        context_hits = {
            hit["corpus_id"]: hit["score"]
            for hit in util.semantic_search(
                context_embedding, self.sfia_embeddings, top_k=top_k_context
            )[0]
        }
        all_corpus_ids = set(action_hits.keys()) | set(context_hits.keys())

        # ----------------------------------------------------------------
        # Step 4 — Level analysis
        # ----------------------------------------------------------------
        detected_level, level_breakdown, level_penalties, level_confidence, beaten_level = (
            self._analyze_level(level_context)
        )

        # ----------------------------------------------------------------
        # Step 5 — Build evidence chunks for snippet citation
        # ----------------------------------------------------------------
        paragraph_chunks = [
            evidence[m.start() : m.end()].strip()
            for m in re.finditer(r"[^\n]+(?:\n[^\n]+)*", evidence)
        ]
        valid_chunks = [
            chunk
            for chunk in paragraph_chunks
            if len(chunk) > self.MIN_CHUNK_CHARS
            and len(chunk.split()) >= self.MIN_CHUNK_WORDS
        ]
        # Deduplicate while preserving order; fall back to full evidence
        unique_chunks = list(dict.fromkeys(valid_chunks)) or [evidence.strip()]
        chunk_embeddings = self.model.encode(unique_chunks, convert_to_tensor=True)

        # ----------------------------------------------------------------
        # Step 6 — Score candidates
        # ----------------------------------------------------------------
        candidates: list[dict[str, Any]] = []
        action_lower = action_text.lower()

        for corpus_id in all_corpus_ids:
            item = self.sfia_service.sfia_data[corpus_id]

            # Weighted multi-vector score
            action_score = action_hits.get(corpus_id, 0.0)
            context_score = context_hits.get(corpus_id, 0.0)
            score = action_weight * action_score + context_weight * context_score

            reasons: list[str] = []

            # Keyword boost — checked against action text only to avoid
            # spurious boosts triggered by Situation/Task domain words
            if item["code"] in self.KEYWORD_BOOSTS:
                boost_keywords, boost_multiplier = self.KEYWORD_BOOSTS[item["code"]]
                for keyword in boost_keywords:
                    # Regex word boundaries to avoid matching substrings incorrectly
                    if re.search(rf'(?:^|\W){re.escape(keyword)}(?:$|\W)', action_lower):
                        score *= boost_multiplier
                        reasons.append(
                            f"Keyword '{keyword}' (+{int((boost_multiplier - 1) * 100)}%)"
                        )
                        break  # one boost per skill

            # Level modifier — reward exact level match, penalise distance
            modifier = level_penalties.get(item["level"], 1.0)
            score *= modifier
            if modifier != 1.0:
                direction = "+" if modifier > 1.0 else "-"
                pct = abs(int((modifier - 1) * 100))
                reasons.append(
                    f"Level {detected_level} "
                    f"{'Match' if modifier > 1.0 else 'Mismatch'} "
                    f"({direction}{pct}%)"
                )
                
            # Normalise the score so it does not exceed 1.0
            score = min(float(score), 1.0)

            # Find the evidence chunk most similar to this skill's embedding
            skill_embedding = self.sfia_embeddings[corpus_id]
            chunk_scores = util.cos_sim(skill_embedding.unsqueeze(0), chunk_embeddings)[0]
            best_chunk_idx = int(chunk_scores.argmax())
            best_chunk = unique_chunks[best_chunk_idx]

            candidates.append(
                {
                    "code": item["code"],
                    "label": item["label"],
                    "level": item["level"],
                    "description": item["description"],
                    "category": item.get("category", ""),
                    "notes": item.get("notes", ""),
                    "text": item["text"],
                    "score": score,
                    "boost_reason": ", ".join(reasons),
                    "evidence_snippet": best_chunk,
                }
            )

        candidates.sort(key=lambda x: x["score"], reverse=True)
        top_matches = self._deduplicate(candidates, detected_level)

        # ----------------------------------------------------------------
        # Step 7 — Assemble result payload
        # ----------------------------------------------------------------
        best_fit_summary = "We couldn't confidently formulate a match."
        if top_matches:
            top = top_matches[0]
            level_explanation = ""

            if detected_level and level_breakdown:
                top_level_info = next(
                    (lvl for lvl in level_breakdown if lvl["level"] == detected_level),
                    level_breakdown[0],
                )
                triggering_snippet = top_level_info.get("snippet", "")

                if level_confidence == "borderline" and beaten_level:
                    confidence_note = (
                        f" ⚠️ This was a borderline call — "
                        f"Level {beaten_level} and Level {detected_level} "
                        f"scored within {int(self.TIEBREAK_MARGIN * 100)}% of each other, "
                        f"so the lower level has been selected as the safer option."
                    )
                elif level_confidence == "borderline":
                    confidence_note = (
                        f" ⚠️ This was a borderline call — "
                        f"the lower level has been selected as the safer option."
                    )
                elif level_confidence == "moderate":
                    confidence_note = (
                        " (moderate confidence — consider reviewing the Level of "
                        "Responsibility description for precision)"
                    )
                else:
                    confidence_note = ""

                snippet_text = (
                    f' The phrase "{triggering_snippet}" most strongly '
                    f"indicated this level."
                    if triggering_snippet
                    and triggering_snippet != "Analysis of overall context string."
                    else ""
                )
                level_explanation = (
                    f" Your Level of Responsibility description aligns most closely "
                    f"with SFIA Level {detected_level}."
                    f"{snippet_text}{confidence_note}"
                )

            best_fit_summary = {
                "label": top["label"],
                "level": top["level"],
                "explanation": level_explanation.strip() if level_explanation else ""
            }

        result = {
            "matches": top_matches,
            "detected_level": detected_level,
            "level_breakdown": level_breakdown,
            "best_fit_summary": best_fit_summary,
        }

        # ----------------------------------------------------------------
        # Step 8 — LLM Final Verdict (optional, graceful fallback)
        # ----------------------------------------------------------------
        try:
            # Extract the Action section from the evidence for the LLM prompt
            action_text = evidence
            action_match = re.search(r"Action\n(.+?)(?=\n\n|Result\n|$)", evidence, re.DOTALL)
            if action_match:
                action_text = action_match.group(1).strip()

            llm_verdict = get_verdict_service().generate_verdict(
                action_text=action_text,
                top_matches=top_matches,
                detected_level=detected_level,
            )
            if llm_verdict:
                result["llm_verdict"] = llm_verdict
        except Exception:
            logger.debug("LLM verdict step skipped — Ollama unavailable or error.")

        return result

    # ------------------------------------------------------------------
    # Level analysis
    # ------------------------------------------------------------------

    def _calculate_level_keyword_scores(self, context: str) -> dict[int, float]:
        """Calculate keyword-based scores for each level.
        
        Provides discriminative signal beyond semantic similarity by looking
        for distinctive phrases that indicate specific responsibility levels.
        
        Args:
            context: The user's responsibility description text (lowercase).
            
        Returns:
            Dict mapping level (1-7) -> keyword match score (0.0-1.0)
        """
        context_lower = context.lower()
        scores = {}
        
        for level, indicators in self._LEVEL_INDICATORS.items():
            matches = 0
            total_indicators = 0
            
            for category, phrases in indicators.items():
                for phrase in phrases:
                    total_indicators += 1
                    if phrase.lower() in context_lower:
                        matches += 1
                        # Give extra weight to longer, more specific phrases
                        if len(phrase.split()) > 2:
                            matches += 0.5
            
            # Normalize to 0-1 range
            scores[level] = matches / total_indicators if total_indicators > 0 else 0.0
        
        return scores

    def _analyze_level(
        self, context: str
    ) -> tuple[Optional[int], list[dict], dict[int, float], Optional[str], Optional[int]]:
        """Detect the most likely SFIA level from a responsibility description.

        Uses a multi-factor approach combining:
        1. Semantic similarity (70% weight) - compares meaning to level descriptions
        2. Keyword indicators (30% weight) - looks for level-specific phrases
        
        This ensemble approach better distinguishes between adjacent levels
        (e.g., Level 4 vs 5 vs 6) which have semantically similar but
        contextually different descriptions.

        Each of the seven SFIA levels of responsibility is represented by a
        pre-computed embedding.  The user's context string is encoded and its
        cosine similarity to every level embedding is calculated.  Individual
        sentences are also scored to identify the phrase most strongly
        associated with the top level (used as the explanatory snippet).

        Tie-breaking: if the top-2 levels are within ``TIEBREAK_MARGIN``,
        the lower level is preferred (conservative for professional evidence).

        Level modifiers are computed as a function of distance from the
        detected level using ``LEVEL_DISTANCE_PENALTIES``.

        Args:
            context: The user's optional "Level of Responsibility" text.

        Returns:
            A 4-tuple of:
            - ``detected_level``: int (1-7) or None if context is too short
            - ``level_breakdown``: top-3 level candidates, each with ``level``,
              ``score``, and ``snippet`` keys
            - ``level_penalties``: dict mapping level int → score modifier float
            - ``level_confidence``: ``"high"``, ``"moderate"``, ``"borderline"``,
              or None
            - ``beaten_level``: int or None — when borderline, the higher-scoring level
              that was overridden by the conservative tie-breaker
        """
        detected_level: Optional[int] = None
        breakdown: list[dict] = []
        level_penalties: dict[int, float] = {i: 1.0 for i in range(1, 8)}
        level_confidence: Optional[str] = None
        beaten_level: Optional[int] = None

        if not context or len(context.strip()) <= 10:
            return detected_level, breakdown, level_penalties, level_confidence, beaten_level

        context_embedding = self.model.encode(context, convert_to_tensor=True)
        level_scores = util.cos_sim(context_embedding, self.level_embeddings)[0]
        
        # Calculate keyword-based scores for additional discriminative power
        keyword_scores = self._calculate_level_keyword_scores(context)

        # Encode individual sentences to find the one most responsible for the
        # top-level match (surfaced as an explanatory snippet in the UI)
        sentences = [
            s.strip()
            for s in re.split(r"[.!?\n]", context)
            if len(s.strip()) > 10
        ]
        sentence_embeddings = (
            self.model.encode(sentences, convert_to_tensor=True) if sentences else None
        )

        all_levels: list[dict] = []
        for i, score in enumerate(level_scores):
            if i >= len(self.sfia_service.generic_levels):
                break
            level_val = self.sfia_service.generic_levels[i]["level"]

            snippet = "Analysis of overall context string."
            if sentence_embeddings is not None:
                level_embedding = self.level_embeddings[i].unsqueeze(0)
                chunk_scores = util.cos_sim(sentence_embeddings, level_embedding)
                best_sentence_idx = int(chunk_scores.argmax())
                snippet = sentences[best_sentence_idx]

            # Combine semantic similarity (70%) with keyword matching (30%)
            semantic_score = float(score)
            keyword_score = keyword_scores.get(level_val, 0.0)
            combined_score = (0.70 * semantic_score) + (0.30 * keyword_score)

            all_levels.append(
                {
                    "level": level_val, 
                    "score": combined_score,
                    "semantic_score": semantic_score,
                    "keyword_score": keyword_score,
                    "snippet": snippet
                }
            )

        if not all_levels:
            return detected_level, breakdown, level_penalties, level_confidence, beaten_level

        all_levels.sort(key=lambda x: x["score"], reverse=True)

        top_score = all_levels[0]["score"]
        top_level = all_levels[0]["level"]

        # Conservative tie-breaking: prefer the lower (safer) level when the
        # margin between the top two is within TIEBREAK_MARGIN
        tiebreak_margin = current_app.config.get("TIEBREAK_MARGIN", self.TIEBREAK_MARGIN)
        if len(all_levels) > 1:
            runner_score = all_levels[1]["score"]
            runner_level = all_levels[1]["level"]
            margin = top_score - runner_score
            if margin < tiebreak_margin and runner_level < top_level:
                detected_level = runner_level
                level_confidence = "borderline"
                beaten_level = top_level
            else:
                detected_level = top_level
                level_confidence = "high" if margin > tiebreak_margin else "moderate"
        else:
            detected_level = top_level
            level_confidence = "high"

        # Build display breakdown: detected level first, then adjacent levels by score.
        # This ensures the Level Analysis UI always shows sensible nearby levels rather
        # than distant levels that happened to score highly via coincidental similarity.
        breakdown = sorted(
            all_levels,
            key=lambda x: (abs(x["level"] - detected_level), -x["score"]),
        )[:3]

        # Build level modifier dict using distance-based penalties
        for lvl in range(1, 8):
            distance = abs(lvl - detected_level)
            level_penalties[lvl] = self.LEVEL_DISTANCE_PENALTIES.get(
                distance, self.LEVEL_FAR_PENALTY
            )

        return detected_level, breakdown, level_penalties, level_confidence, beaten_level

    # ------------------------------------------------------------------
    # Deduplication
    # ------------------------------------------------------------------

    def _deduplicate(self, candidates: list[dict], detected_level: Optional[int]) -> list[dict]:
        """Return at most 5 candidates, keeping only the top result per skill code.
        If a detected_level is provided, pick the candidate for each skill code whose
        level is closest to the detected_level.

        Args:
            candidates: Score-sorted list of candidate dicts.
            detected_level: The user's detected level of responsibility.

        Returns:
            Deduplicated list of up to 5 entries.
        """
        by_code: dict[str, list[dict]] = defaultdict(list)
        for candidate in candidates:
            by_code[candidate["code"]].append(candidate)
            
        unique: list[dict] = []
        for code, group in by_code.items():
            if detected_level is not None:
                group.sort(key=lambda x: (abs(x["level"] - detected_level), -x["score"]))
            else:
                group.sort(key=lambda x: -x["score"])
            unique.append(group[0])
            
        unique.sort(key=lambda x: x["score"], reverse=True)
        return unique[:5]
