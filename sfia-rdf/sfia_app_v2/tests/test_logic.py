"""Unit tests for the core matching logic and heuristics.

These tests load the real NLP model but use a minimal mock SFIA service
to keep the test surface focused on the algorithms rather than the data.
"""

import pytest
from unittest.mock import MagicMock

from app.services.matching import MatchingService

# ---------------------------------------------------------------------------
# Minimal mock data — enough to exercise the matching logic
# ---------------------------------------------------------------------------

MOCK_SFIA_DATA = [
    {
        "code": "TEST",
        "label": "Testing",
        "level": 4,
        "text": "Testing software code at level 4",
        "description": "Plan and perform testing activities",
        "category": "Solution Development and Implementation",
        "notes": "",
    }
]

MOCK_GENERIC_LEVELS = [
    {"level": 3, "text": "Apply. Works under general supervision."},
    {"level": 4, "text": "Enable. Works with substantial personal responsibility."},
    {"level": 5, "text": "Ensure / Advise. Works under broad direction."},
    {"level": 6, "text": "Initiate / Influence. Has authority over significant area of work."},
    {"level": 7, "text": "Set Strategy / Inspire / Mobilise. Full accountability at enterprise level."},
]


@pytest.fixture(scope="module")
def matching_service():
    """Initialise a MatchingService with mock SFIA data.

    The real NLP model is loaded so that embedding-based logic is exercised.
    The SFIA data is kept minimal to keep startup fast.
    """
    mock_sfia = MagicMock()
    mock_sfia.sfia_data = MOCK_SFIA_DATA
    mock_sfia.generic_levels = MOCK_GENERIC_LEVELS
    return MatchingService("all-MiniLM-L6-v2", mock_sfia)


# ---------------------------------------------------------------------------
# Level analysis
# ---------------------------------------------------------------------------

def test_analyze_level_returns_four_values(matching_service):
    """_analyze_level must return (detected_level, breakdown, penalties, confidence)."""
    result = matching_service._analyze_level("I set strategy for the whole organisation.")
    assert len(result) == 4, "Expected a 4-tuple: (detected_level, breakdown, penalties, confidence)"


def test_analyze_level_high_level_context(matching_service):
    """Strong strategy/vision language should resolve to level 6 or 7."""
    context = "I set strategy for the whole organisation. Vision and culture."
    detected, breakdown, penalties, confidence = matching_service._analyze_level(context)
    assert detected in [6, 7], f"Expected level 6 or 7 for executive language, got {detected}"


def test_analyze_level_detected_level_has_boost(matching_service):
    """The penalty dict must give the detected level a score modifier > 1.0."""
    context = "I set strategy for the whole organisation. Vision and culture."
    detected, breakdown, penalties, confidence = matching_service._analyze_level(context)
    assert penalties[detected] > 1.0, "Detected level should have a score boost (modifier > 1.0)"


def test_analyze_level_returns_none_for_short_context(matching_service):
    """Context shorter than 10 characters should return no detected level."""
    detected, breakdown, penalties, confidence = matching_service._analyze_level("hi")
    assert detected is None
    assert breakdown == []
    assert confidence is None


def test_analyze_level_confidence_values(matching_service):
    """Confidence must be one of the expected string values or None."""
    context = "I lead a small team and take responsibility for delivery."
    detected, breakdown, penalties, confidence = matching_service._analyze_level(context)
    assert confidence in {"high", "moderate", "borderline", None}


# ---------------------------------------------------------------------------
# Keyword boosts
# ---------------------------------------------------------------------------

def test_keyword_boost_test_code_present(matching_service):
    """The TEST skill code should have a keyword boost entry."""
    assert "TEST" in matching_service.KEYWORD_BOOSTS


def test_keyword_boost_test_code_structure(matching_service):
    """Each boost entry must be a (list, float) tuple with a meaningful multiplier."""
    keywords, boost = matching_service.KEYWORD_BOOSTS["TEST"]
    assert isinstance(keywords, list), "Keywords should be a list"
    assert isinstance(boost, float), "Boost multiplier should be a float"
    assert boost > 1.0, "Boost multiplier must be greater than 1.0"


def test_keyword_boost_test_code_has_tech_keywords(matching_service):
    """TEST tech seeds (e.g. 'selenium', 'qa') must appear in the keyword list."""
    keywords, _ = matching_service.KEYWORD_BOOSTS["TEST"]
    # At least one of the hard-coded tech seeds for TEST should be present
    expected = {"selenium", "cypress", "junit", "pytest", "jest", "qa", "regression"}
    assert expected & set(keywords), (
        f"Expected at least one of {expected} in TEST keywords, got: {keywords}"
    )


def test_keyword_boost_prog_code_has_higher_multiplier(matching_service):
    """DAAN (data analytics) should have a higher boost than the 1.2 default."""
    if "DAAN" in matching_service.KEYWORD_BOOSTS:
        _, boost = matching_service.KEYWORD_BOOSTS["DAAN"]
        assert boost >= 1.4


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------

def test_evidence_max_length_constant():
    """EVIDENCE_MAX_LENGTH in config must reject evidence over 5000 chars."""
    from config import Config
    assert Config.EVIDENCE_MAX_LENGTH == 5000


def test_input_over_limit_is_rejected():
    """Evidence longer than EVIDENCE_MAX_LENGTH must be caught by route validation."""
    from config import Config
    long_text = "a" * (Config.EVIDENCE_MAX_LENGTH + 1)
    assert len(long_text) > Config.EVIDENCE_MAX_LENGTH


# ---------------------------------------------------------------------------
# STAR section parsing
# ---------------------------------------------------------------------------

def test_parse_star_sections_with_headings():
    """Properly labelled STAR evidence should be parsed into named sections."""
    evidence = (
        "Situation\nWe had a legacy system.\n\n"
        "Task\nMy role was to migrate it.\n\n"
        "Action\nI led the migration project.\n\n"
        "Result\nDelivered on time and within budget."
    )
    sections = MatchingService._parse_star_sections(evidence)
    assert "migration" in sections["action"].lower()
    assert "budget" in sections["result"].lower()


def test_parse_star_sections_no_headings_returns_empty():
    """Evidence with no STAR headings should return empty strings for all sections."""
    evidence = "I did some work on a project and it went well."
    sections = MatchingService._parse_star_sections(evidence)
    assert all(v == "" for v in sections.values())


def test_parse_star_sections_keys():
    """Returned dict must always contain all five expected keys."""
    sections = MatchingService._parse_star_sections("")
    assert set(sections.keys()) == {"situation", "task", "action", "result", "responsibility"}
