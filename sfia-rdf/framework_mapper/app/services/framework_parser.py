"""
Framework Parser Service for UK Engineering Council Standards

This module provides functionality to load and parse professional framework competency
standards (starting with UK-SPEC) into a format suitable for semantic matching with SFIA.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class Competency:
    """Represents a single competency within a framework."""
    code: str
    title: str
    full_description: str
    indicators: List[str]
    keywords: List[str]
    
    def get_full_text(self) -> str:
        """Get complete text for embedding generation."""
        return f"{self.title}. {self.full_description} " + " ".join(self.indicators)


@dataclass
class Registration:
    """Represents a professional registration level (e.g., CEng, IEng, EngTech)."""
    code: str
    title: str
    description: str
    typical_roles: List[str]
    sfia_level_range: tuple[int, int]
    competencies: Dict[str, Competency]
    commitment_standards: Dict[str, dict]
    
    def get_all_competencies(self) -> List[Competency]:
        """Returns list of all competencies for this registration."""
        return list(self.competencies.values())
    
    def get_competency(self, code: str) -> Optional[Competency]:
        """Get specific competency by code."""
        return self.competencies.get(code)


@dataclass
class Framework:
    """Represents a complete professional framework (e.g., UK-SPEC)."""
    name: str
    version: str
    description: str
    source_url: str
    registrations: Dict[str, Registration]
    
    def get_registration(self, code: str) -> Optional[Registration]:
        """Get specific registration by code (e.g., 'CEng')."""
        return self.registrations.get(code)
    
    def get_all_competencies(self) -> List[tuple[str, str, Competency]]:
        """Returns all competencies across all registrations.
        
        Returns:
            List of tuples: (registration_code, competency_code, Competency)
        """
        all_comps = []
        for reg_code, registration in self.registrations.items():
            for comp_code, competency in registration.competencies.items():
                all_comps.append((reg_code, comp_code, competency))
        return all_comps


class FrameworkParser:
    """Parses and manages professional framework standards."""
    
    def __init__(self, frameworks_dir: Optional[Path] = None):
        """
        Initialize the framework parser.
        
        Args:
            frameworks_dir: Directory containing framework JSON files.
                           Defaults to frameworks/ subdirectory.
        """
        if frameworks_dir is None:
            # Default to frameworks directory relative to this file
            frameworks_dir = Path(__file__).parent.parent / 'frameworks'
        
        self.frameworks_dir = Path(frameworks_dir)
        self.loaded_frameworks: Dict[str, Framework] = {}
        
        logger.info(f"Framework parser initialized with directory: {self.frameworks_dir}")
    
    def load_ukeng_framework(self) -> Framework:
        """Load UK Engineering Council framework."""
        framework_file = self.frameworks_dir / 'ukeng_standards.json'
        
        if not framework_file.exists():
            raise FileNotFoundError(
                f"UK Engineering Council framework file not found: {framework_file}"
            )
        
        with open(framework_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Parse registrations
        registrations = {}
        for reg_code, reg_data in data['registrations'].items():
            # Parse competencies
            competencies = {}
            for comp_code, comp_data in reg_data['competencies'].items():
                competencies[comp_code] = Competency(
                    code=comp_data['code'],
                    title=comp_data['title'],
                    full_description=comp_data['full_description'],
                    indicators=comp_data['indicators'],
                    keywords=comp_data['keywords']
                )
            
            registrations[reg_code] = Registration(
                code=reg_code,
                title=reg_data['title'],
                description=reg_data['description'],
                typical_roles=reg_data['typical_roles'],
                sfia_level_range=tuple(reg_data['sfia_level_range']),
                competencies=competencies,
                commitment_standards=reg_data['commitment_standards']
            )
        
        framework = Framework(
            name=data['framework_name'],
            version=data['framework_version'],
            description=data['description'],
            source_url=data['source_url'],
            registrations=registrations
        )
        
        self.loaded_frameworks['ukeng'] = framework
        logger.info(f"Loaded UK Engineering Council framework: {framework.name} ({framework.version})")
        logger.info(f"  Registrations: {list(registrations.keys())}")
        
        return framework
    
    def get_framework(self, framework_id: str) -> Optional[Framework]:
        """Get a loaded framework by ID."""
        return self.loaded_frameworks.get(framework_id)
    
    def get_competency_context(
        self,
        framework_id: str,
        registration_code: str,
        competency_code: str
    ) -> Optional[dict]:
        """
        Get complete context for a specific competency.
        
        Args:
            framework_id: Framework identifier (e.g., 'ukeng')
            registration_code: Registration code (e.g., 'CEng')
            competency_code: Competency code (e.g., 'A')
        
        Returns:
            Dictionary with competency details and context, or None if not found
        """
        framework = self.get_framework(framework_id)
        if not framework:
            return None
        
        registration = framework.get_registration(registration_code)
        if not registration:
            return None
        
        competency = registration.get_competency(competency_code)
        if not competency:
            return None
        
        return {
            'framework': framework.name,
            'registration': {
                'code': registration.code,
                'title': registration.title,
                'description': registration.description,
                'sfia_level_range': registration.sfia_level_range
            },
            'competency': {
                'code': competency.code,
                'title': competency.title,
                'full_description': competency.full_description,
                'indicators': competency.indicators,
                'keywords': competency.keywords,
                'full_text': competency.get_full_text()
            }
        }
    
    def get_registration_summary(self, framework_id: str) -> Optional[Dict]:
        """Get summary of all registrations in a framework.
        
        Returns:
            Dictionary mapping registration codes to their details
        """
        framework = self.get_framework(framework_id)
        if not framework:
            return None
        
        summary = {}
        for reg_code, registration in framework.registrations.items():
            summary[reg_code] = {
                'title': registration.title,
                'description': registration.description,
                'typical_roles': registration.typical_roles,
                'sfia_level_range': registration.sfia_level_range,
                'competencies': list(registration.competencies.keys()),
                'num_competencies': len(registration.competencies)
            }
        
        return summary


# Singleton instance
_framework_parser: Optional[FrameworkParser] = None


def get_framework_parser() -> FrameworkParser:
    """Get or create the singleton framework parser instance."""
    global _framework_parser
    if _framework_parser is None:
        _framework_parser = FrameworkParser()
        # Pre-load UK Engineering Council framework
        try:
            _framework_parser.load_ukeng_framework()
        except Exception as e:
            logger.error(f"Failed to load UK Engineering Council framework: {e}")
    
    return _framework_parser


if __name__ == "__main__":
    # Test the parser
    logging.basicConfig(level=logging.INFO)
    
    parser = FrameworkParser()
    framework = parser.load_ukeng_framework()
    
    print(f"\n=== {framework.name} ===")
    print(f"Version: {framework.version}")
    print(f"Description: {framework.description}")
    print(f"\nRegistrations:")
    
    for reg_code, registration in framework.registrations.items():
        print(f"\n  {reg_code} - {registration.title}")
        print(f"  SFIA Level Range: {registration.sfia_level_range}")
        print(f"  Competencies: {list(registration.competencies.keys())}")
        
        # Show first competency as example
        comp_a = registration.get_competency('A')
        if comp_a:
            print(f"\n  Example Competency A:")
            print(f"    Title: {comp_a.title}")
            print(f"    Indicators: {len(comp_a.indicators)}")
            print(f"    Keywords: {', '.join(comp_a.keywords[:5])}...")
