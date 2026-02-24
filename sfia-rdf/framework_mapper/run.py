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
    app = Flask(__name__)
    
    # Configuration
    app.config['SECRET_KEY'] = 'dev-key-change-in-production'
    app.config['JSON_SORT_KEYS'] = False
    
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
    app.run(debug=True, host='0.0.0.0', port=5001)
