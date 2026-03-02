import logging
import sys
import importlib.util
from pathlib import Path
from typing import Optional, List, Dict

import torch
from sentence_transformers import SentenceTransformer, util

from .bok_parser import BokParser

logger = logging.getLogger(__name__)

# Dynamically load SfiaService to avoid 'app' namespace conflicts
_bok_dir = Path(__file__).resolve().parent.parent.parent.parent
_sfia_service_path = _bok_dir / 'sfia_app_v2' / 'app' / 'services' / 'sfia.py'
_SfiaService = None

if _sfia_service_path.exists():
    spec = importlib.util.spec_from_file_location("sfia_v2_service", _sfia_service_path)
    sfia_module = importlib.util.module_from_spec(spec)
    sys.modules["sfia_v2_service"] = sfia_module
    spec.loader.exec_module(sfia_module)
    _SfiaService = sfia_module.SfiaService
else:
    logger.error(f"Could not find SFIA service at {_sfia_service_path}")


class BokMatchingService:
    """
    Semantic matcher that maps BoK chapters to SFIA skills using cosine similarity.
    Loads SFIA data from the RDF ontology (via SfiaService) and pre-builds
    embeddings for fast repeated querying.
    """

    def __init__(self, parser: BokParser, sfia_ttl_path: Optional[str] = None):
        self.parser = parser

        if _SfiaService is None:
            raise RuntimeError("SfiaService could not be loaded. Ensure sfia_app_v2 is present.")

        if sfia_ttl_path is None:
            sfia_ttl_path = str(_bok_dir / 'SFIA_9_2025-02-27.ttl')

        logger.info("Initialising SFIA service and building embeddings index...")
        self.model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
        self.sfia_service = _SfiaService(sfia_ttl_path)

        # Pre-build the corpus embeddings from sfia_data at startup
        self.sfia_data: List[Dict] = self.sfia_service.sfia_data
        logger.info(f"Building embeddings for {len(self.sfia_data)} SFIA skill×level entries...")
        sfia_texts = [entry['text'] for entry in self.sfia_data]
        self.sfia_embeddings = self.model.encode(sfia_texts, convert_to_tensor=True, show_progress_bar=False)
        logger.info("SFIA embeddings index ready.")

    def _get_query_embedding(self, text: str, cyber_context: bool = False) -> torch.Tensor:
        """Encode a query string, optionally prepending a cyber security context prefix."""
        if cyber_context:
            text = f"In the context of cyber security, information security, and risk management: {text}"
        return self.model.encode(text, convert_to_tensor=True)

    def _match_text_to_sfia(self, text: str, label: str, cyber_context: bool = False, top_k: int = 7) -> list:
        """
        Embed a query and return the top-k deduplicated SFIA skill matches
        using cosine similarity against the pre-built index.
        """
        query_emb = self._get_query_embedding(text, cyber_context)

        # Cosine similarity against all SFIA skill×level embeddings
        scores = util.cos_sim(query_emb, self.sfia_embeddings)[0]
        top_results = torch.topk(scores, k=min(top_k * 5, len(self.sfia_data)))

        unique_matches = []
        seen_skills = set()

        for score, idx in zip(top_results.values.tolist(), top_results.indices.tolist()):
            if len(unique_matches) >= top_k:
                break

            entry = self.sfia_data[idx]
            skill_name = entry['label']

            # Deduplicate by skill name (keep highest-scoring level)
            if skill_name not in seen_skills:
                seen_skills.add(skill_name)
                rounded_score = round(score, 4)
                unique_matches.append({
                    'skill_code': entry['code'],
                    'skill_name': skill_name,
                    'skill_description': entry['description'],
                    'skill_category': entry.get('category', ''),
                    'suggested_level': entry['level'],
                    'level_confidence': rounded_score,
                    'competency_alignment': rounded_score,
                    'rationale': (
                        f"Semantic match between '{label}' and SFIA skill "
                        f"'{skill_name}' Level {entry['level']} "
                        f"(similarity: {rounded_score:.2f})."
                    )
                })

        return unique_matches

    def get_full_mapping_workflow(self, bok_id: str, ka_id: str,
                                  cyber_context: bool = False, top_k: int = 7) -> dict:
        """
        Full pipeline: parse all chapters for a KA, embed each chapter
        independently, and return chapter_mappings with deduplicated SFIA matches.
        """
        ka_context = self.parser.get_ka_context(bok_id, ka_id)
        if not ka_context:
            return {"success": False, "error": f"Knowledge Area '{ka_id}' not found in BoK '{bok_id}'."}

        ka_title = ka_context['ka_title']
        chapters = ka_context.get('ka_chapters', [])

        if not chapters:
            return {"success": False, "error": f"No chapters found for KA '{ka_id}'."}

        logger.info(f"Mapping {len(chapters)} chapters for KA '{ka_title}'...")

        chapter_mappings = []
        for chapter in chapters:
            chapter_text = f"{chapter['title']}: {chapter['description']}"
            chapter_label = f"{chapter['id']} – {chapter['title']}"
            sfia_matches = self._match_text_to_sfia(
                text=chapter_text,
                label=chapter_label,
                cyber_context=cyber_context,
                top_k=top_k
            )
            chapter_mappings.append({
                "chapter_id": chapter['id'],
                "chapter_title": chapter['title'],
                "chapter_description": chapter['description'],
                "sfia_mappings": sfia_matches
            })

        top_score = (
            chapter_mappings[0]['sfia_mappings'][0]['competency_alignment']
            if chapter_mappings and chapter_mappings[0]['sfia_mappings'] else 0.0
        )

        return {
            "success": True,
            "result": {
                "bok_name": ka_context['bok_name'],
                "ka_id": ka_id,
                "ka_title": ka_title,
                "ka_category": ka_context.get('ka_category', ''),
                "chapter_mappings": chapter_mappings,
                "validation": {
                    "relevance": "strong" if top_score > 0.5 else "moderate",
                    "match_score": top_score,
                    "feedback": f"Chapter-level mapping completed for '{ka_title}' ({len(chapter_mappings)} chapters).",
                    "keyword_matches": []
                }
            }
        }
