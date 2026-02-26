import os


class Config:
    """Application configuration.

    Sensitive values (SECRET_KEY) must be set via environment variables in
    production. The app will raise at startup if they are missing.
    """

    # --- Security ---
    _raw_secret = os.environ.get("SECRET_KEY")
    if not _raw_secret:
        if os.environ.get("FLASK_ENV") == "production":
            raise RuntimeError(
                "SECRET_KEY environment variable must be set in production. "
                "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
            )
        # Dev/test fallback: random key per process (sessions won't survive restart)
        _raw_secret = os.urandom(24)
    SECRET_KEY = _raw_secret

    # Secure session cookies — all three flags should always be on
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    # --- Paths ---
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    # Override via SFIA_TTL_FILE env var to point at a different ontology file
    SFIA_TTL_FILE = os.environ.get(
        "SFIA_TTL_FILE",
        os.path.join(BASE_DIR, "SFIA_9_2025-02-27.ttl"),
    )

    # --- NLP model ---
    # Sentence-transformer model used for semantic matching
    MODEL_NAME = "all-MiniLM-L6-v2"

    # --- Request limits ---
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB max upload payload

    # Maximum characters accepted in a single STAR evidence submission
    EVIDENCE_MAX_LENGTH = 5000

    # --- Rate limits (applied per route via Flask-Limiter) ---
    MATCH_RATE_LIMIT = "5 per minute"
    REFINE_RATE_LIMIT = "10 per minute"
    RATELIMIT_STORAGE_URI = os.environ.get("RATELIMIT_STORAGE_URI", "memory://")

    # --- ML Matching Magic Numbers ---
    ACTION_WEIGHT = 0.70
    CONTEXT_WEIGHT = 0.30
    CLARIFICATION_WEIGHT = 0.80
    BASE_ACTION_WEIGHT = 0.20
    TOP_K_ACTION = 60
    TOP_K_CONTEXT = 40
    TIEBREAK_MARGIN = 0.05
