"""
Configuration file for Framework-to-SFIA Mapper

Contains application settings, paths, and constants.
"""

import os
from pathlib import Path

# Base directories
BASE_DIR = Path(__file__).resolve().parent
FRAMEWORKS_DIR = BASE_DIR / 'frameworks'
SFIA_APP_DIR = BASE_DIR.parent / 'sfia_app_v2'
SFIA_TTL_PATH = BASE_DIR.parent / 'SFIA_9_2025-02-27.ttl'

# Model configuration
MODEL_NAME = 'sentence-transformers/all-MiniLM-L6-v2'

# Flask configuration
SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-key-change-in-production')
DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'

# Matching thresholds
COMPETENCY_MATCH_HIGH_THRESHOLD = 0.65
COMPETENCY_MATCH_MEDIUM_THRESHOLD = 0.50

# Scoring weights
COMPETENCY_CONTEXT_WEIGHT = 0.60  # Framework competency importance
EVIDENCE_WEIGHT = 0.40  # User evidence importance

# API settings
MAX_RESULTS = 20
DEFAULT_RESULTS = 10

# Logging
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
