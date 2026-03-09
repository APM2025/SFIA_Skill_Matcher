"""
Framework-to-SFIA Mapper - Flask Application Entry Point

This application maps professional framework competencies (e.g., UK Engineering Council)
to SFIA skills using dual-embedding semantic matching.
"""

import logging
import sys
from pathlib import Path

from flask import Flask
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_talisman import Talisman

# Add parent directory to path to import sfia_service from sfia_app_v2
parent_dir = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(parent_dir / 'sfia_app_v2'))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_app():
    """Create and configure Flask application."""
    app = Flask('app')
    
    # Configuration
    import os
    config_path = os.path.join(os.path.dirname(__file__), 'config.py')
    app.config.from_pyfile(config_path)
    # Fallbacks array
    app.config.setdefault('SECRET_KEY', 'dev-key-change-in-production')
    app.config['JSON_SORT_KEYS'] = False
    app.config['RATELIMIT_STORAGE_URI'] = 'memory://'  # Can be overridden with redis:// in production

    # Security headers
    csp = {
        'default-src': ["'self'"],
        'style-src': ["'self'", "'unsafe-inline'"],
        'script-src': ["'self'", "https://cdnjs.cloudflare.com", "'unsafe-eval'"],
        'img-src': ["'self'", "data:"]
    }
    Talisman(app, content_security_policy=csp, force_https=False)

    # Rate limiting
    limiter = Limiter(
        key_func=get_remote_address,
        default_limits=["1000 per day", "200 per hour"],  # Relaxed for local LLM usage
        storage_uri=app.config['RATELIMIT_STORAGE_URI']
    )
    limiter.init_app(app)
    
    # Enable CORS for API endpoints
    CORS(app, resources={r"/api/*": {"origins": "*"}})
    
    # Register blueprints
    from app.routes import bp as main_bp
    app.register_blueprint(main_bp)
    
    logger.info("Framework Mapper application created successfully")
    
    return app


# Create app instance
app = create_app()


if __name__ == '__main__':
    logger.info("Starting Framework-to-SFIA Mapper development server")
    app.run(debug=True, host='0.0.0.0', port=5001, threaded=True)
