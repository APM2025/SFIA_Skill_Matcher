"""SFIA RDF knowledge graph loader.

Parses the SFIA 9 Turtle (.ttl) ontology file and exposes two datasets:

- ``sfia_data``: list of dicts, one entry per skill×level combination, with
  fields: code, label, level, description, category, notes, text.
- ``generic_levels``: list of dicts describing each of the 7 SFIA levels of
  responsibility (used for level detection during matching).
"""

import gc
import logging
import os
from typing import Any

from rdflib import Graph

logger = logging.getLogger(__name__)

# SFIA 9 ontology base URI — all level-of-responsibility resources live here
_SFIA_LOR_BASE = "https://rdf.sfia-online.org/9/lor/"
_SFIA_ONTOLOGY_NS = "https://rdf.sfia-online.org/9/ontology/"


class SfiaService:
    """Loads and exposes SFIA skill and level data from the RDF ontology."""

    # Plain-English summaries that complement the formal ontology descriptors.
    # These are injected into each level's text so the NLP model gets richer
    # signal when matching a user's described responsibility to a SFIA level.
    _LEVEL_SUMMARIES: dict[int, str] = {
        1: (
            "Follow. Performs routine tasks under close supervision, follows instructions, "
            "and requires guidance to complete their work. Learns and applies basic skills "
            "and knowledge. Works under direct supervision with little autonomy. Influences "
            "nobody beyond their immediate task. Requires constant checking and direction."
        ),
        2: (
            "Assist. Provides assistance to others, works under routine supervision, and uses "
            "their discretion to address routine problems. Actively learns through training and "
            "on-the-job experiences. Works with some independence on familiar tasks. Influence "
            "is limited to immediate work area. Escalates non-routine issues."
        ),
        3: (
            "Apply. Performs varied tasks, sometimes complex and non-routine, using standard "
            "methods and procedures. Works under general direction, exercises discretion, and "
            "manages own work within deadlines. Proactively enhances skills and impact in the "
            "workplace. Influences immediate colleagues. My influence was primarily within my "
            "local team, and I operated within agreed procedures and guidance. "
            "Think: competent practitioner delivering assigned work."
        ),
        4: (
            "Enable. Performs diverse complex activities, supports and guides others, delegates "
            "tasks when appropriate, works autonomously under general direction, and contributes "
            "expertise to deliver team objectives. Works with substantial personal responsibility. "
            "Influences team and peers. Handles complex tasks within a defined scope. "
            "Focus: Delivering and improving work. Leads small teams, designs solutions, "
            "implements improvements."
        ),
        5: (
            "Ensure, advise. Provides authoritative guidance in their field and works under broad "
            "direction. Accountable for delivering significant work outcomes, from analysis through "
            "execution to evaluation. Influences customers, suppliers, and stakeholders beyond own "
            "team. Tackles broad, non-routine problems. You advise decision-makers, define "
            "standards, balance risk, cost, and business impact. Your decisions affect multiple "
            "teams. You are not just doing the work — you are ensuring it is done correctly."
        ),
        6: (
            "Initiate, influence. Has significant organisational influence, makes high-level "
            "decisions, shapes policies, demonstrates leadership, promotes organisational "
            "collaboration, and accepts accountability in key areas. Senior leadership level. "
            "Influences policy and strategy at organisational level. Resolves highly complex, "
            "cross-functional issues. You shape strategy. You define organisational policy. "
            "You influence executive decisions. You manage large-scale capability. "
            "This is enterprise-level thinking for senior managers and directors."
        ),
        7: (
            "Set strategy, inspire, mobilise. Operates at the highest organisational level, "
            "determines overall organisational vision and strategy, and assumes accountability "
            "for overall success. Full accountability at enterprise level. Influences the whole "
            "organisation or industry. Focus: Vision, culture, long-term direction. "
            "This is CEO, CISO, CIO, CTO territory."
        ),
    }

    def __init__(self, ttl_file: str) -> None:
        """Initialise and eagerly load all SFIA data from the ontology file.

        Args:
            ttl_file: Absolute path to the SFIA 9 Turtle (.ttl) file.

        Raises:
            FileNotFoundError: If *ttl_file* does not exist at startup.
        """
        self.ttl_file = ttl_file
        self.sfia_data: list[dict[str, Any]] = []
        self.generic_levels: list[dict[str, Any]] = []
        self.load_data()

    def load_generic_levels(self, graph: Graph) -> list[dict[str, Any]]:
        """Extract the seven SFIA levels of responsibility from the graph.

        For each level 1–7 the method combines the formal ontology attributes
        (Autonomy, Influence, Complexity, Knowledge, Business Skills) with the
        plain-English summary stored in ``_LEVEL_SUMMARIES``.

        Args:
            graph: A parsed rdflib Graph containing the SFIA ontology.

        Returns:
            A list of dicts with keys ``level`` (int) and ``text`` (str),
            ordered from level 1 to level 7.
        """
        logger.info("Loading Generic Level Descriptors...")
        levels = []
        for i in range(1, 8):
            level_uri = f"{_SFIA_LOR_BASE}{i}"
            sparql = (
                f"PREFIX sfia: <{_SFIA_ONTOLOGY_NS}> "
                f"SELECT ?p ?o WHERE {{ <{level_uri}> ?p ?o }}"
            )
            desc_parts = []
            if i in self._LEVEL_SUMMARIES:
                desc_parts.append(self._LEVEL_SUMMARIES[i])

            for row in graph.query(sparql):
                pred = str(row.p)
                obj = str(row.o)
                if "ontology/AUTO" in pred:
                    desc_parts.append(f"Autonomy: {obj}")
                elif "ontology/INFL" in pred:
                    desc_parts.append(f"Influence: {obj}")
                elif "ontology/COMP" in pred:
                    desc_parts.append(f"Complexity: {obj}")
                elif "ontology/KNGE" in pred:
                    desc_parts.append(f"Knowledge: {obj}")
                elif "ontology/BUSS" in pred:
                    desc_parts.append(f"Business Skills: {obj}")

            levels.append(
                {"level": i, "text": f"Level {i} Responsibility: " + " ".join(desc_parts)}
            )
        return levels

    def load_data(self) -> None:
        """Parse the TTL file and populate ``sfia_data`` and ``generic_levels``.

        Raises:
            FileNotFoundError: If the configured TTL file path does not exist.
        """
        if not os.path.exists(self.ttl_file):
            raise FileNotFoundError(
                f"SFIA ontology file not found: {self.ttl_file}. "
                "Ensure SFIA_9_2025-02-27.ttl is present in the repository root, "
                "or set the SFIA_TTL_FILE environment variable to its location."
            )

        logger.info("Loading SFIA graph from %s...", self.ttl_file)
        graph = Graph()
        graph.parse(self.ttl_file, format="turtle")
        self.generic_levels = self.load_generic_levels(graph)

        query = """
            PREFIX sfia: <https://rdf.sfia-online.org/9/ontology/>
            PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            SELECT ?skill ?skillCode ?skillLabel ?skillLevel ?levelNotation
                   ?description ?categoryLabel ?notes ?guidance
            WHERE {
                ?skill a sfia:Skill ;
                       skos:notation ?skillCode ;
                       rdfs:label ?skillLabel ;
                       sfia:definedAtLevel ?skillLevel .
                OPTIONAL { ?skill sfia:skillCategory ?cat . ?cat rdfs:label ?categoryLabel . }
                OPTIONAL { ?skill sfia:skillNotes ?notes . }
                OPTIONAL { ?skill sfia:attributeGuidanceNotes ?guidance . }
                ?skillLevel sfia:level ?levelNode ;
                            sfia:skillLevelDescription ?description .
                ?levelNode skos:notation ?levelNotation .
            }
        """
        seen = set()
        for row in graph.query(query):
            skill_code = str(row.skillCode)
            try:
                level_val = int(str(row.levelNotation))
            except ValueError:
                continue  # skip rows with non-integer level notations

            dedup_key = f"{skill_code}_{level_val}"
            if dedup_key in seen:
                continue
            seen.add(dedup_key)

            description = str(row.description)
            category = str(row.categoryLabel) if row.categoryLabel else ""
            notes = str(row.notes) if row.notes else ""
            guidance = str(row.guidance) if row.guidance else ""

            # Composite text field fed to the NLP model — richer = better matches
            text = f"{str(row.skillLabel)} (Level {level_val}): {description}"
            if category:
                text += f" | Category: {category}"
            if notes:
                text += f" | Activities: {notes}"
            if guidance:
                text += f" | Guidance: {guidance}"

            self.sfia_data.append(
                {
                    "code": skill_code,
                    "label": str(row.skillLabel),
                    "level": level_val,
                    "description": description,
                    "category": category,
                    "notes": notes,
                    "text": text,
                }
            )

        logger.info("Loaded %d skill×level entries.", len(self.sfia_data))

        # Explicitly release the rdflib graph — it can occupy ~80 MB and is no
        # longer needed once sfia_data and generic_levels are populated.
        del graph
        gc.collect()
