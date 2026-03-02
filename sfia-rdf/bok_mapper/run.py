"""
Body of Knowledge (BoK) Mapper - Flask Application Entry Point
"""

import logging
import sys
from pathlib import Path

# Make sure THIS directory is first on path so 'app' resolves to bok_mapper/app
_bok_mapper_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(_bok_mapper_dir))

# Also add sfia_app_v2 so bok_matching can import SfiaService
_sfia_app_dir = _bok_mapper_dir.parent / 'sfia_app_v2'
sys.path.insert(1, str(_sfia_app_dir))

from flask import Flask
from flask_cors import CORS

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_app():
    """Create and configure Flask application."""
    app = Flask('app')
    app.config['JSON_SORT_KEYS'] = False

    CORS(app, resources={r"/api/*": {"origins": "*"}})

    from app.routes import bp as main_bp
    app.register_blueprint(main_bp)

    logger.info("BoK Mapper application created successfully")
    return app


app = create_app()

if __name__ == '__main__':
    logger.info("Starting BoK Mapper development server on port 5002")
    app.run(debug=True, host='0.0.0.0', port=5002)
