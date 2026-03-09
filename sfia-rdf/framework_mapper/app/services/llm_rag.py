import logging
import json
import requests
from pathlib import Path
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)

# --- SFIA Cybersecurity Job Role Knowledge ---
# SFIA skill codes that are strongly associated with cybersecurity/IT job families
CYBER_SFIA_CODES = {
    "SCTY", "GOVN", "ITSP", "ISMS", "SCAD", "VULN", "INAS",
    "PENT", "DTAN", "INAN", "IFDN", "DATM", "NTDS", "ISCO",
    "RSKM", "USUP", "CFMG", "EMRG", "RELM", "BPRE"
}

def _load_cyber_job_roles() -> Dict[str, List[str]]:
    """Load the SFIA job roles mapping and return only cybersecurity-relevant entries."""
    json_path = Path(__file__).resolve().parent.parent.parent.parent / 'sfia_app_v2' / 'job_roles_mapping.json'
    if not json_path.exists():
        logger.warning(f"job_roles_mapping.json not found at {json_path}")
        return {}
    try:
        with open(json_path, 'r') as f:
            all_roles = json.load(f)
        return {code: roles for code, roles in all_roles.items() if code in CYBER_SFIA_CODES}
    except Exception as e:
        logger.warning(f"Failed to load job_roles_mapping.json: {e}")
        return {}

CYBER_JOB_ROLES_BY_SKILL = _load_cyber_job_roles()

class LlmRagService:
    """
    Retrieval-Augmented Generation (RAG) service using a local open-source LLM via Ollama.
    
    This service takes the matched SFIA skill data (the "Retrieval" step) and the
    user's target framework competency, then prompts a local LLM to generate a customized,
    intelligent explanation of why they match.
    """
    
    def __init__(self, ollama_url: str = "http://localhost:11434/api/generate", model: str = "llama3"):
        self.ollama_url = ollama_url
        self.model = model
        self.timeout = 120  # Seconds to wait for the LLM to respond before falling back
        
    def generate_rationale(
        self, 
        framework_competency_text: str, 
        sfia_skill_name: str, 
        sfia_skill_desc: str,
        cyber_context: bool = False
    ) -> Optional[str]:
        """
        Ask the LLM to explain why the SFIA skill matches the framework competency.
        """
        prompt = (
            f"You are an expert assessor mapping professional engineering frameworks to SFIA skills.\n"
            f"A user needs to demonstrate the following professional competency:\n"
            f"'{framework_competency_text}'\n\n"
            f"The system has suggested the following SFIA Skill as a strong match:\n"
            f"Skill Name: {sfia_skill_name}\n"
            f"Skill Description: {sfia_skill_desc}\n\n"
        )
        
        if cyber_context:
            prompt += (
                "CRITICAL CONTEXT: The user specifically requested this mapping with an Information and Cyber Security focus. "
                "In your explanation, you MUST explicitly highlight how this SFIA skill applies to cybersecurity, risk, or governance.\n\n"
            )
            
        prompt += (
            "Write a concise, intelligent 2-sentence explanation of EXACTLY why this SFIA skill is the correct match "
            "for demonstrating that professional competency. Do not use generic filler words like 'This skill is a good match because'.\n"
            "Finally, you MUST make a final comment specifically regarding type 5 skills."
        )
        
        try:
            response = requests.post(
                self.ollama_url,
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False
                },
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get("response", "").strip()
            else:
                logger.warning(f"Ollama returned status {response.status_code}")
                return None
                
        except requests.exceptions.RequestException as e:
            logger.warning(f"Failed to connect to local Ollama LLM for RAG generation: {e}")
            return None

    def recommend_best_fit(
        self,
        framework_competency_text: str,
        candidate_skills: list,
        cyber_context: bool = False
    ) -> Optional[str]:
        """
        Act as an expert judge. Given a list of candidate SFIA skills, recommend the 
        single best fit and write a comprehensive rationale for that decision.
        
        candidate_skills: list of dicts with keys 'name', 'description', 'score'
        """
        skill_list_text = ""
        for i, skill in enumerate(candidate_skills):
            skill_list_text += (
                f"  Candidate {i+1}: {skill['name']} (semantic similarity: {skill['score']:.0%})\n"
                f"    Description: {skill['description']}\n\n"
            )

        prompt = (
            f"You are a senior SFIA assessor and an expert career adviser for IT and cybersecurity professionals.\n"
            f"A practitioner with an IT or cybersecurity background needs to satisfy the following UK-SPEC competency requirement:\n"
            f"'{framework_competency_text}'\n\n"
            f"A semantic search has retrieved the following {len(candidate_skills)} SFIA skills as the strongest structural matches:\n\n"
            f"{skill_list_text}"
        )
        
        # Cross-reference matched skills against the SFIA cybersecurity job role data
        cyber_role_context = ""
        for skill in candidate_skills:
            skill_code = skill.get('code', '')
            if skill_code and skill_code in CYBER_JOB_ROLES_BY_SKILL:
                roles = CYBER_JOB_ROLES_BY_SKILL[skill_code]
                cyber_role_context += f"  - {skill['name']} ({skill_code}): Mapped to cyber/IT roles: {', '.join(roles[:5])}\n"
        
        if cyber_role_context:
            prompt += (
                f"\nSFIA CYBERSECURITY JOB ROLE DATA (from official SFIA job role mappings):\n"
                f"The following matched skills have confirmed mappings to cybersecurity and IT job families:\n"
                f"{cyber_role_context}\n"
                "Use this data to ground your recommendations in the actual SFIA cybersecurity job family structure.\n\n"
            )
        
        if cyber_context:
            prompt += (
                "CRITICAL CONTEXT: This practitioner works specifically in Information and Cyber Security. "
                "Frame all advice through the lens of security operations, governance, risk management, and compliance.\n\n"
            )
            
        prompt += (
            "Carefully consider all the SFIA skills listed above in relation to the UK-SPEC competency.\n"
            "Provide an expert strategic advisory in this format:\n\n"
            "SKILLS TO PRIORITISE: [Name the most relevant SFIA skills from the list that this practitioner should actively pursue and evidence — they may need more than one, so name all that genuinely apply. If SFIA job role data is provided above, weight your answer towards those skills.]\n"
            "STRATEGIC RATIONALE: [Write 3-4 sentences explaining which combination of SFIA skills will best satisfy the UK-SPEC requirement, and why someone with a cyber/IT background is well-positioned to demonstrate them.]\n"
            "TYPE 5 SKILLS COMMENT: [Specifically comment on what demonstrating these skills at a SFIA level 5 means in practice for a senior cybersecurity professional — what evidence, responsibilities or outputs would be expected.]"
        )

        try:
            response = requests.post(
                self.ollama_url,
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False
                },
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get("response", "").strip()
            else:
                logger.warning(f"Ollama returned status {response.status_code} for best-fit recommendation")
                return None
                
        except requests.exceptions.RequestException as e:
            logger.warning(f"Failed to get best-fit recommendation from Ollama: {e}")
            return None

# Singleton instance
_llm_rag_service: Optional[LlmRagService] = None

def get_llm_rag_service() -> LlmRagService:
    global _llm_rag_service
    if _llm_rag_service is None:
        _llm_rag_service = LlmRagService()
    return _llm_rag_service
