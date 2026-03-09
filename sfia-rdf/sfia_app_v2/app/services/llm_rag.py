"""
LLM RAG Service for sfia_app_v2.

Calls a local Ollama LLM to generate a single final verdict after the semantic
matching pipeline has already identified the top SFIA skill candidates.

The verdict is a one-paragraph 'on balance' statement:
  "On balance, this evidence best aligns to [skill] at SFIA Level [n] because..."
"""

import logging
import requests
from typing import Optional

logger = logging.getLogger(__name__)


class LlmVerdictService:
    """Generate a final LLM verdict for SFIA evidence matching."""

    def __init__(
        self,
        ollama_url: str = "http://localhost:11434/api/generate",
        model: str = "llama3",
        timeout: int = 120,
    ):
        self.ollama_url = ollama_url
        self.model = model
        self.timeout = timeout

    def generate_verdict(
        self,
        action_text: str,
        top_matches: list,
        detected_level: Optional[int] = None,
    ) -> Optional[str]:
        """
        Generate a final 'on balance' verdict given the top SFIA matches.

        Args:
            action_text: The user's Action section from their STAR evidence.
            top_matches: List of match dicts as returned by MatchingService.match().
                         Each dict has keys: label, code, level, score, description.
            detected_level: The SFIA level detected from the user's responsibility text.

        Returns:
            A verdict string, or None if the LLM is unavailable.
        """
        if not top_matches:
            return None

        # Build a summary of the top candidates for the LLM
        candidates_text = ""
        for i, m in enumerate(top_matches[:5]):
            candidates_text += (
                f"  {i+1}. {m.get('label', 'Unknown')} ({m.get('code', '?')}) "
                f"at SFIA Level {m.get('level', '?')} — "
                f"semantic match score: {m.get('score', 0):.0%}\n"
                f"     Description: {m.get('description', '')[:200]}\n\n"
            )

        level_note = (
            f"The system has detected that the user operates at approximately SFIA Level {detected_level}.\n"
            if detected_level
            else ""
        )

        prompt = (
            "You are a senior SFIA assessor reviewing a professional's evidence statement.\n\n"
            "The user submitted the following STAR Action evidence:\n"
            f"\"{action_text}\"\n\n"
            f"{level_note}"
            "The semantic matching system has identified these top SFIA skill candidates:\n\n"
            f"{candidates_text}"
            "Based on the evidence and the candidate list, write a single concise paragraph "
            "in this format:\n\n"
            "\"On balance, this evidence best aligns to [SFIA skill name] at SFIA Level [n] "
            "because [2-3 sentence reason grounded in what the evidence actually demonstrates]. "
            "The other candidates are plausible but [brief note on why the top pick is strongest].\"\n\n"
            "Be direct, specific, and assessor-like in tone. Do not be generic."
        )

        try:
            response = requests.post(
                self.ollama_url,
                json={"model": self.model, "prompt": prompt, "stream": False},
                timeout=self.timeout,
            )
            if response.status_code == 200:
                return response.json().get("response", "").strip()
            else:
                logger.warning(f"Ollama returned HTTP {response.status_code} for verdict")
                return None
        except requests.exceptions.RequestException as e:
            logger.warning(f"Ollama LLM verdict unavailable: {e}")
            return None


# Singleton
_verdict_service: Optional[LlmVerdictService] = None


def get_verdict_service() -> LlmVerdictService:
    global _verdict_service
    if _verdict_service is None:
        _verdict_service = LlmVerdictService()
    return _verdict_service
