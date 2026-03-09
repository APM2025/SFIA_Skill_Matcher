"""
Framework-to-SFIA Matching Service

This module implements dual-embedding semantic matching for mapping professional 
framework competencies (e.g., UK-SPEC) to SFIA skills.

Architecture:
1. Evidence Validation: Match evidence against framework competency to validate relevance
2. SFIA Mapping: Map competency context + evidence to SFIA skills
3. Dual Embedding: Both framework competencies and SFIA skills are embedded for matching
"""

import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

import re
import torch
import requests
from sentence_transformers import SentenceTransformer, util
from flask import current_app

from app.services.framework_parser import FrameworkParser, Competency
from app.services.llm_rag import get_llm_rag_service

logger = logging.getLogger(__name__)


@dataclass
class CompetencyMatch:
    """Result of matching evidence to a framework competency."""
    competency_code: str
    competency_title: str
    match_score: float
    evidence_relevance: str  # "high", "medium", "low"
    keyword_matches: List[str]


@dataclass
class FrameworkSfiaMatch:
    """Result of mapping framework competency to SFIA skills."""
    skill_code: str
    skill_name: str
    skill_description: str
    overall_score: float
    competency_alignment_score: float  # How well SFIA skill aligns with framework competency
    evidence_score: float  # How well evidence demonstrates SFIA skill
    suggested_level: int
    level_confidence: float
    rationale: str


class FrameworkMatchingService:
    """
    Orchestrates dual-embedding matching between professional frameworks and SFIA.
    
    Workflow:
    1. User selects framework (e.g., UK Eng Council), registration (e.g., CEng), 
       and competency (e.g., Competency A)
    2. User provides STAR evidence demonstrating that competency
    3. System validates: evidence → competency match (quality check)
    4. System maps: (competency context + evidence) → SFIA skills
    """
    
    # Set default values
    COMPETENCY_MATCH_HIGH_THRESHOLD = 0.65
    COMPETENCY_MATCH_MEDIUM_THRESHOLD = 0.50
    
    # SFIA mapping weights
    COMPETENCY_CONTEXT_WEIGHT = 0.60  # Framework competency provides primary context
    EVIDENCE_WEIGHT = 0.40  # User's evidence provides demonstration specifics
    
    def __init__(
        self,
        model_name: str = 'sentence-transformers/all-MiniLM-L6-v2',
        framework_parser: Optional[FrameworkParser] = None,
        sfia_service: Optional['SfiaService'] = None,
        sfia_ttl_path: Optional[str] = None
    ):
        """
        Initialize the framework matching service.
        
        Args:
            model_name: Sentence transformer model for embeddings
            framework_parser: Parser for loading framework standards
            sfia_service: Service for accessing SFIA data
            sfia_ttl_path: Path to SFIA TTL file
        """
        import sys
        from pathlib import Path
        
        # Add sfia_app_v2 to path if needed
        parent_dir = Path(__file__).resolve().parent.parent.parent.parent
        sfia_app_path = parent_dir / 'sfia_app_v2'
        # Dynamically import SFIA service without clashing with the local 'app' module
        import importlib.util
        import sys
        
        sfia_service_path = sfia_app_path / 'app' / 'services' / 'sfia.py'
        if sfia_service_path.exists():
            spec = importlib.util.spec_from_file_location("sfia_v2_service", sfia_service_path)
            sfia_module = importlib.util.module_from_spec(spec)
            sys.modules["sfia_v2_service"] = sfia_module
            spec.loader.exec_module(sfia_module)
            SfiaServiceV2 = sfia_module.SfiaService
        else:
            logger.error(f"Could not find SFIA service at {sfia_service_path}")
            SfiaServiceV2 = None
        
        self.model = SentenceTransformer(model_name)
        self.framework_parser = framework_parser or FrameworkParser()
        
        # Initialize SFIA service if not provided
        if sfia_service is None:
            if sfia_ttl_path is None:
                # Default path to SFIA TTL file
                sfia_ttl_path = str(parent_dir / 'SFIA_9_2025-02-27.ttl')
            self.sfia_service = SfiaServiceV2(sfia_ttl_path)
        else:
            self.sfia_service = sfia_service
        
        # Pre-load UK Engineering Council framework
        try:
            self.framework_parser.load_ukeng_framework()
        except Exception as e:
            logger.error(f"Failed to load UK Eng framework: {e}")
        
        # Cache for competency embeddings
        self.competency_embeddings: Dict[str, torch.Tensor] = {}
        
        # Compute SFIA skill embeddings
        self.sfia_embeddings = None
        self._compute_sfia_embeddings()
        
        logger.info(f"Framework matching service initialized with model: {model_name}")
    
    def _get_text_embedding(
        self,
        text: str,
        cyber_context: bool = False
    ) -> torch.Tensor:
        """Get or compute embedding for any text."""
        # Inject Cyber Security Context if requested
        if cyber_context:
            text = "In the context of Information and Cyber Security job families, security operations, governance, risk, and compliance: " + text
        
        # Encode
        embedding = self.model.encode(text, convert_to_tensor=True, normalize_embeddings=True)
        return embedding
    
    def map_indicator_to_sfia_skills(
        self,
        indicator_text: str,
        competency_title: str,
        sfia_level_range: Tuple[int, int],
        cyber_context: bool = False,
        top_k: int = 10
    ) -> List[FrameworkSfiaMatch]:
        """
        Map a single framework indicator string directly to SFIA skills, deduplicated by name.
        """
        comp_embedding = self._get_text_embedding(indicator_text, cyber_context)
        
        # Get all SFIA skills with embeddings from sfia_service
        sfia_skills = self._get_sfia_skills_with_embeddings()
        
        # Score each SFIA skill
        matches = []
        for skill in sfia_skills:
            # Competency alignment: how well SFIA skill matches framework competency directly
            comp_score = util.pytorch_cos_sim(
                skill['embedding'], 
                comp_embedding
            ).item()
            
            # Level suggestion based on registration range
            suggested_level = int((sfia_level_range[0] + sfia_level_range[1]) / 2)
            
            # Always generate basic rationale first for all skills for speed
            rationale = self._generate_rationale(
                skill['name'],
                competency_title,
                comp_score
            )
            
            # Generate qualitative confidence level based on score
            if comp_score > 0.6:
                confidence_label = "High"
            elif comp_score > 0.45:
                confidence_label = "Medium"
            else:
                confidence_label = "Low"
            
            matches.append(FrameworkSfiaMatch(
                skill_code=skill['code'],
                skill_name=skill['name'],
                skill_description=skill['description'],
                overall_score=comp_score,
                competency_alignment_score=comp_score,
                evidence_score=0.0, # N/A for standard-to-standard
                suggested_level=suggested_level,
                level_confidence=confidence_label,
                rationale=rationale
            ))
        
        # Sort by overall score
        matches.sort(key=lambda x: x.overall_score, reverse=True)
        
        # Deduplicate by skill_name
        deduped_matches = []
        seen_skills = set()
        
        for match in matches:
            if match.skill_name not in seen_skills:
                deduped_matches.append(match)
                seen_skills.add(match.skill_name)
            if len(deduped_matches) >= top_k:
                break
                
        # --- GRAPH RAG: Individual rationales for all top matches ---
        for match in deduped_matches:
            llm_service = get_llm_rag_service()
            custom_rationale = llm_service.generate_rationale(
                framework_competency_text=indicator_text,
                sfia_skill_name=match.skill_name,
                sfia_skill_desc=match.skill_description,
                cyber_context=cyber_context
            )
            if custom_rationale:
                match.rationale = custom_rationale
        
        # --- GRAPH RAG: LLM Judge Step ---
        # Feed all top candidates to the LLM and ask it to decide which is the best fit
        # and write a comprehensive, structured rationale with a type 5 skills comment.
        best_fit_recommendation = None
        if deduped_matches:
            llm_service = get_llm_rag_service()
            candidate_skills = [
                {
                    'code': m.skill_code,
                    'name': m.skill_name,
                    'description': m.skill_description,
                    'score': m.overall_score
                }
                for m in deduped_matches
            ]
            best_fit_recommendation = llm_service.recommend_best_fit(
                framework_competency_text=indicator_text,
                candidate_skills=candidate_skills,
                cyber_context=cyber_context
            )
        
        return deduped_matches, best_fit_recommendation
    
    def _compute_sfia_embeddings(self):
        """Compute embeddings for all SFIA skills."""
        logger.info("Computing SFIA skill embeddings...")
        
        # Get all skills from SFIA service
        skill_texts = [skill['text'] for skill in self.sfia_service.sfia_data]
        
        # Encode all skills
        self.sfia_embeddings = self.model.encode(
            skill_texts,
            convert_to_tensor=True,
            normalize_embeddings=True,
            show_progress_bar=False
        )
        
        logger.info(f"Computed embeddings for {len(skill_texts)} SFIA skills")
    
    def _get_sfia_skills_with_embeddings(self) -> List[Dict]:
        """
        Get SFIA skills with their embeddings.
        
        Returns:
            List of dicts with keys: code, name, description, embedding
        """
        if self.sfia_embeddings is None:
            logger.error("SFIA embeddings not computed")
            return []
        
        skills_with_embeddings = []
        for i, skill in enumerate(self.sfia_service.sfia_data):
            skills_with_embeddings.append({
                'code': skill['code'],
                'name': skill['label'],
                'description': skill['description'],
                'category': skill.get('category', ''),
                'embedding': self.sfia_embeddings[i]
            })
        
        return skills_with_embeddings
    
    def _generate_rationale(
        self,
        skill_name: str,
        competency_title: str,
        comp_score: float
    ) -> str:
        """Generate human-readable explanation for the mapping."""
        if comp_score > 0.6:
            strength = "Strong"
        elif comp_score > 0.45:
            strength = "Good"
        else:
            strength = "Moderate"
        
        return (
            f"{strength} conceptual alignment between SFIA {skill_name} and "
            f"UK-SPEC {competency_title}. "
            f"(Match score: {comp_score:.0%})"
        )
    
    def get_full_mapping_workflow(
        self,
        framework_id: str,
        registration_code: str,
        competency_code: str,
        cyber_context: bool = False,
        top_k: int = 10
    ) -> Dict:
        """
        Execute complete workflow mapping standard-to-standard by indicators.
        
        Returns:
            Dictionary with conceptual context and SFIA indicator mappings
        """
        # Get the context for display
        context = self.framework_parser.get_competency_context(
            framework_id, registration_code, competency_code
        )
        
        if not context:
            return {}
            
        comp = context['competency']
        sfia_level_range = context['registration']['sfia_level_range']
        
        indicator_mappings = []
        
        if comp.get('sub_competencies'):
            for sc in comp['sub_competencies']:
                indicator_id = sc['code']
                indicator_text = f"{comp['title']}. {sc['semantic_text']}"
                
                sfia_matches, best_fit = self.map_indicator_to_sfia_skills(
                    indicator_text, comp['title'], sfia_level_range, cyber_context, top_k
                )
                
                indicator_mappings.append({
                    'indicator_id': indicator_id,
                    'indicator_text': sc['description'],
                    'best_fit_recommendation': best_fit,
                    'sfia_mappings': [
                        {
                            'skill_code': match.skill_code,
                            'skill_name': match.skill_name,
                            'skill_description': match.skill_description,
                            'overall_score': match.overall_score,
                            'competency_alignment': match.competency_alignment_score,
                            'evidence_score': match.evidence_score,
                            'suggested_level': match.suggested_level,
                            'level_confidence': match.level_confidence,
                            'rationale': match.rationale
                        }
                        for match in sfia_matches
                    ]
                })
        else:
            for i, indicator in enumerate(comp.get('indicators', [])):
                indicator_id = f"{competency_code}{i+1}"
                indicator_text = f"{comp['title']}. {indicator}"
                
                sfia_matches, best_fit = self.map_indicator_to_sfia_skills(
                    indicator_text, comp['title'], sfia_level_range, cyber_context, top_k
                )
                
                indicator_mappings.append({
                    'indicator_id': indicator_id,
                    'indicator_text': indicator,
                    'best_fit_recommendation': best_fit,
                    'sfia_mappings': [
                        {
                            'skill_code': match.skill_code,
                            'skill_name': match.skill_name,
                            'skill_description': match.skill_description,
                            'overall_score': match.overall_score,
                            'competency_alignment': match.competency_alignment_score,
                            'evidence_score': match.evidence_score,
                            'suggested_level': match.suggested_level,
                            'level_confidence': match.level_confidence,
                            'rationale': match.rationale
                        }
                        for match in sfia_matches
                    ]
                })
        
        return {
            'validation': {
                'competency_code': competency_code,
                'competency_title': comp['title'],
                'match_score': 1.0,  # Legacy field placeholder
                'relevance': 'high', # Legacy field placeholder
                'keyword_matches': [],
                'cyber_context_applied': cyber_context
            },
            'indicator_mappings': indicator_mappings
        }


# Singleton instance
_framework_matching_service: Optional[FrameworkMatchingService] = None


def get_framework_matching_service() -> FrameworkMatchingService:
    """Get or create the singleton framework matching service."""
    global _framework_matching_service
    if _framework_matching_service is None:
        _framework_matching_service = FrameworkMatchingService()
    
    return _framework_matching_service


if __name__ == "__main__":
    # Test the service
    logging.basicConfig(level=logging.INFO)
    
    service = FrameworkMatchingService()
    
    # Test evidence validation
    test_evidence = """
    Situation: Leading a complex infrastructure migration project
    Task: Design and implement cloud migration strategy for legacy systems
    Action: Applied engineering analysis to assess system dependencies, created 
    detailed technical specifications, and designed scalable cloud architecture
    Result: Successfully migrated 15 systems with 99.9% uptime
    """
    
    validation = service.validate_evidence_for_competency(
        test_evidence,
        framework_id='ukeng',
        registration_code='CEng',
        competency_code='A'
    )
    
    print(f"\n=== Competency Validation ===")
    print(f"Competency: {validation.competency_title}")
    print(f"Match Score: {validation.match_score:.3f}")
    print(f"Relevance: {validation.evidence_relevance}")
    print(f"Keywords Matched: {', '.join(validation.keyword_matches)}")
