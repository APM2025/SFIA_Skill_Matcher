"""Flask application factory for the SFIA Matcher.

Call ``create_app()`` to build and return a configured Flask application.
All security middleware, extension initialisation, and eager service loading
happen here so the app is fully ready before accepting its first request.
"""

import logging

from flask import Flask
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_talisman import Talisman
from flask_wtf.csrf import CSRFProtect

from config import Config

logger = logging.getLogger(__name__)

csrf = CSRFProtect()
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
)


def create_app(config_class=Config) -> Flask:
    """Create and configure the Flask application.

    Steps performed:
    1. Load configuration from *config_class*
    2. Initialise CSRF protection and rate limiting
    3. Attach Talisman security headers (CSP, HSTS, etc.)
    4. Register the main Blueprint (routes)
    5. Eagerly load the SFIA RDF data and NLP model so that the first
       request is not delayed by a cold-start (~30 s without cache)

    Args:
        config_class: A config object compatible with ``app.config.from_object``.
            Defaults to ``Config`` (from ``config.py``).

    Returns:
        A fully initialised Flask application instance.
    """
    app = Flask(__name__)
    app.config.from_object(config_class)

    # CSRF protection — applied to all state-changing requests automatically
    csrf.init_app(app)

    # Rate limiting — per-IP, backed by in-memory storage by default
    limiter.init_app(app)

    # Content Security Policy
    # NOTE: 'unsafe-inline' is required while script and style blocks are
    # embedded directly in index.html.  Moving them to external files and
    # using CSP nonces would allow these to be removed.
    csp = {
        "default-src": ["'self'"],
        "script-src": ["'self'", "'unsafe-inline'", "https://d3js.org"],
        "style-src": ["'self'", "'unsafe-inline'"],
    }
    Talisman(app, content_security_policy=csp, force_https=False)

    # Register routes
    from app.routes import main as main_blueprint
    app.register_blueprint(main_blueprint)

    # Eagerly initialise the NLP services inside the app context so they are
    # ready before the first request arrives.  Stored in app.extensions so
    # route handlers can retrieve them without re-importing.
    with app.app_context():
        logger.info(
            "Initialising SFIA service and NLP model at startup "
            "(this may take ~30 s on first run without a warm cache)..."
        )
        from app.services.matching import MatchingService
        from app.services.sfia import SfiaService

        sfia_svc = SfiaService(app.config["SFIA_TTL_FILE"])
        matching_svc = MatchingService(app.config["MODEL_NAME"], sfia_svc)
        app.extensions["sfia_service"] = sfia_svc
        app.extensions["matching_service"] = matching_svc
        logger.info("Ready — SFIA service and NLP model loaded.")

    return app
