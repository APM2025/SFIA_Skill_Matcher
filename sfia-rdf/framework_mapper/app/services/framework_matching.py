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

import torch
from sentence_transformers import SentenceTransformer, util

from app.services.framework_parser import FrameworkParser, Competency

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
    
    # Validation thresholds
    COMPETENCY_MATCH_HIGH_THRESHOLD = 0.65
    COMPETENCY_MATCH_MEDIUM_THRESHOLD = 0.50
    
    # SFIA mapping weights
    COMPETENCY_CONTEXT_WEIGHT = 0.60  # Framework competency provides primary context
    EVIDENCE_WEIGHT = 0.40  # User's evidence provides demonstration specifics
    
    def __init__(
        self,
        model_name: str = 'sentence-transformers/all-MiniLM-L6-v2',
        framework_parser: Optional[FrameworkParser] = None,
        sfia_service: Optional[SfiaService] = None,
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
        if str(sfia_app_path) not in sys.path:
            sys.path.insert(0, str(sfia_app_path))
        
        # Import SFIA service from sfia_app_v2
        from app.services.sfia import SfiaService as SfiaServiceV2
        
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
    
    def _get_competency_embedding(
        self,
        framework_id: str,
        registration_code: str,
        competency_code: str
    ) -> Optional[torch.Tensor]:
        """Get or compute embedding for a framework competency."""
        cache_key = f"{framework_id}_{registration_code}_{competency_code}"
        
        if cache_key in self.competency_embeddings:
            return self.competency_embeddings[cache_key]
        
        # Get competency context
        context = self.framework_parser.get_competency_context(
            framework_id, registration_code, competency_code
        )
        
        if not context:
            logger.warning(f"Competency not found: {cache_key}")
            return None
        
        # Create rich text representation for embedding
        comp = context['competency']
        text = comp['full_text']
        
        # Encode
        embedding = self.model.encode(text, convert_to_tensor=True, normalize_embeddings=True)
        self.competency_embeddings[cache_key] = embedding
        
        logger.debug(f"Computed embedding for {cache_key}")
        return embedding
    
    def validate_evidence_for_competency(
        self,
        evidence: str,
        framework_id: str,
        registration_code: str,
        competency_code: str
    ) -> CompetencyMatch:
        """
        Validate that provided evidence is relevant to the claimed competency.
        
        This is the first step: before mapping to SFIA, ensure the evidence
        actually demonstrates the framework competency the user selected.
        
        Args:
            evidence: User's STAR evidence text
            framework_id: Framework identifier (e.g., 'ukeng')
            registration_code: Registration level (e.g., 'CEng')
            competency_code: Competency code (e.g., 'A')
        
        Returns:
            CompetencyMatch with validation score and details
        """
        # Get competency embedding
        comp_embedding = self._get_competency_embedding(
            framework_id, registration_code, competency_code
        )
        
        if comp_embedding is None:
            return CompetencyMatch(
                competency_code=competency_code,
                competency_title="Unknown",
                match_score=0.0,
                evidence_relevance="low",
                keyword_matches=[]
            )
        
        # Get competency context for keywords
        context = self.framework_parser.get_competency_context(
            framework_id, registration_code, competency_code
        )
        comp_keywords = context['competency']['keywords']
        comp_title = context['competency']['title']
        
        # Encode evidence
        evidence_embedding = self.model.encode(
            evidence, 
            convert_to_tensor=True, 
            normalize_embeddings=True
        )
        
        # Semantic similarity
        semantic_score = util.pytorch_cos_sim(evidence_embedding, comp_embedding).item()
        
        # Keyword matching (binary: present or not)
        evidence_lower = evidence.lower()
        keyword_matches = [kw for kw in comp_keywords if kw in evidence_lower]
        keyword_boost = min(len(keyword_matches) * 0.03, 0.15)  # Up to +15%
        
        # Combined score
        total_score = semantic_score + keyword_boost
        
        # Determine relevance level
        if total_score >= self.COMPETENCY_MATCH_HIGH_THRESHOLD:
            relevance = "high"
        elif total_score >= self.COMPETENCY_MATCH_MEDIUM_THRESHOLD:
            relevance = "medium"
        else:
            relevance = "low"
        
        logger.info(
            f"Competency validation: {competency_code} - "
            f"semantic={semantic_score:.3f}, keywords={len(keyword_matches)}, "
            f"total={total_score:.3f}, relevance={relevance}"
        )
        
        return CompetencyMatch(
            competency_code=competency_code,
            competency_title=comp_title,
            match_score=total_score,
            evidence_relevance=relevance,
            keyword_matches=keyword_matches
        )
    
    def map_to_sfia_skills(
        self,
        evidence: str,
        framework_id: str,
        registration_code: str,
        competency_code: str,
        top_k: int = 10
    ) -> List[FrameworkSfiaMatch]:
        """
        Map framework competency + evidence to SFIA skills.
        
        This is the second step: given validated evidence for a framework competency,
        find the most relevant SFIA skills that align with both the competency
        context and the specific evidence provided.
        
        Args:
            evidence: User's STAR evidence text
            framework_id: Framework identifier
            registration_code: Registration level
            competency_code: Competency code
            top_k: Number of top SFIA skill matches to return
        
        Returns:
            List of FrameworkSfiaMatch objects ranked by relevance
        """
        # Get competency context and embedding
        comp_embedding = self._get_competency_embedding(
            framework_id, registration_code, competency_code
        )
        
        context = self.framework_parser.get_competency_context(
            framework_id, registration_code, competency_code
        )
        
        if comp_embedding is None or context is None:
            logger.error(f"Failed to get competency context: {competency_code}")
            return []
        
        # Encode evidence
        evidence_embedding = self.model.encode(
            evidence,
            convert_to_tensor=True,
            normalize_embeddings=True
        )
        
        # Get all SFIA skills with embeddings from sfia_service
        # Note: We'll need to adapt this based on actual sfia_service interface
        sfia_skills = self._get_sfia_skills_with_embeddings()
        
        # Score each SFIA skill
        matches = []
        for skill in sfia_skills:
            # Competency alignment: how well SFIA skill matches framework competency
            comp_score = util.pytorch_cos_sim(
                skill['embedding'], 
                comp_embedding
            ).item()
            
            # Evidence alignment: how well SFIA skill matches user's evidence
            ev_score = util.pytorch_cos_sim(
                skill['embedding'],
                evidence_embedding
            ).item()
            
            # Weighted combination
            overall_score = (
                self.COMPETENCY_CONTEXT_WEIGHT * comp_score + 
                self.EVIDENCE_WEIGHT * ev_score
            )
            
            # Level suggestion based on registration range
            sfia_level_range = context['registration']['sfia_level_range']
            suggested_level = int((sfia_level_range[0] + sfia_level_range[1]) / 2)
            
            # Generate rationale
            rationale = self._generate_rationale(
                skill['name'],
                context['competency']['title'],
                comp_score,
                ev_score
            )
            
            matches.append(FrameworkSfiaMatch(
                skill_code=skill['code'],
                skill_name=skill['name'],
                skill_description=skill['description'],
                overall_score=overall_score,
                competency_alignment_score=comp_score,
                evidence_score=ev_score,
                suggested_level=suggested_level,
                level_confidence=0.7,  # Placeholder for now
                rationale=rationale
            ))
        
        # Sort by overall score and return top-k
        matches.sort(key=lambda x: x.overall_score, reverse=True)
        
        logger.info(
            f"Mapped {competency_code} to {len(matches)} SFIA skills, "
            f"returning top {top_k}"
        )
        
        return matches[:top_k]
    
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
        comp_score: float,
        ev_score: float
    ) -> str:
        """Generate human-readable explanation for the mapping."""
        if comp_score > 0.7 and ev_score > 0.7:
            strength = "Strong"
        elif comp_score > 0.6 or ev_score > 0.6:
            strength = "Good"
        else:
            strength = "Moderate"
        
        return (
            f"{strength} alignment between {skill_name} and {competency_title}. "
            f"Competency match: {comp_score:.0%}, Evidence match: {ev_score:.0%}."
        )
    
    def get_full_mapping_workflow(
        self,
        evidence: str,
        framework_id: str,
        registration_code: str,
        competency_code: str,
        top_k: int = 10
    ) -> Dict:
        """
        Execute complete workflow: validate evidence → map to SFIA.
        
        Returns:
            Dictionary with validation results and SFIA mappings
        """
        # Step 1: Validate evidence
        validation = self.validate_evidence_for_competency(
            evidence, framework_id, registration_code, competency_code
        )
        
        # Step 2: Map to SFIA (proceed regardless of validation for now)
        sfia_matches = self.map_to_sfia_skills(
            evidence, framework_id, registration_code, competency_code, top_k
        )
        
        return {
            'validation': {
                'competency_code': validation.competency_code,
                'competency_title': validation.competency_title,
                'match_score': validation.match_score,
                'relevance': validation.evidence_relevance,
                'keyword_matches': validation.keyword_matches
            },
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
