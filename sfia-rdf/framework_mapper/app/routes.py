"""
Flask Routes for Framework-to-SFIA Mapper

Provides endpoints for:
- Framework metadata (registrations, competencies)
- Evidence validation against framework competencies
- Mapping framework competencies to SFIA skills
"""

from flask import Blueprint, request, jsonify, render_template
import logging

from app.services.framework_parser import get_framework_parser
from app.services.framework_matching import get_framework_matching_service

logger = logging.getLogger(__name__)

# Create blueprint
bp = Blueprint('main', __name__)


def _safe_get_string(data: dict, key: str, default: str = "") -> str:
    """Safely extract and convert a value to a stripped string."""
    val = data.get(key)
    if val is None:
        return default
    return str(val).strip()


@bp.route('/')
def index():
    """Main page for framework-to-SFIA mapping."""
    return render_template('index.html')


@bp.route('/api/frameworks', methods=['GET'])
def get_frameworks():
    """Get list of available frameworks.
    
    Returns:
        JSON with framework metadata
    """
    try:
        parser = get_framework_parser()
        
        # For now, only UK Engineering Council is supported
        frameworks = {
            'ukeng': {
                'id': 'ukeng',
                'name': 'UK Engineering Council',
                'full_name': 'UK Standard for Professional Engineering Competence (UK-SPEC)',
                'description': 'Professional standards for Chartered Engineers, Incorporated Engineers, and Engineering Technicians',
                'version': 'Fourth Edition 2020'
            }
        }
        
        return jsonify({
            'success': True,
            'frameworks': frameworks
        })
    
    except Exception as e:
        logger.error(f"Error getting frameworks: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/api/frameworks/<framework_id>/registrations', methods=['GET'])
def get_registrations(framework_id: str):
    """Get registration levels for a framework.
    
    Args:
        framework_id: Framework identifier (e.g., 'ukeng')
    
    Returns:
        JSON with registration details
    """
    try:
        parser = get_framework_parser()
        summary = parser.get_registration_summary(framework_id)
        
        if summary is None:
            return jsonify({
                'success': False,
                'error': 'Framework not found'
            }), 404
        
        return jsonify({
            'success': True,
            'framework_id': framework_id,
            'registrations': summary
        })
    
    except Exception as e:
        logger.error(f"Error getting registrations: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/api/frameworks/<framework_id>/<registration_code>/<competency_code>', methods=['GET'])
def get_competency_details(framework_id: str, registration_code: str, competency_code: str):
    """Get detailed information about a specific competency.
    
    Args:
        framework_id: Framework identifier
        registration_code: Registration code (e.g., 'CEng')
        competency_code: Competency code (e.g., 'A')
    
    Returns:
        JSON with competency details
    """
    try:
        parser = get_framework_parser()
        context = parser.get_competency_context(
            framework_id, registration_code, competency_code
        )
        
        if context is None:
            return jsonify({
                'success': False,
                'error': 'Competency not found'
            }), 404
        
        return jsonify({
            'success': True,
            'competency': context
        })
    
    except Exception as e:
        logger.error(f"Error getting competency details: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/api/map', methods=['POST'])
def map_to_sfia():
    """Map framework competency directly to SFIA skills.
    
    Request JSON:
        {
            "framework_id": "ukeng",
            "registration_code": "CEng",
            "competency_code": "A",
            "cyber_context": true,
            "top_k": 10
        }
    
    Returns:
        JSON with SFIA skill mappings
    """
    try:
        data = request.get_json()
        
        # Validate input
        required_fields = ['framework_id', 'registration_code', 'competency_code']
        for field in required_fields:
            if field not in data:
                return jsonify({
                    'success': False,
                    'error': f'Missing required field: {field}'
                }), 400
        
        top_k = data.get('top_k', 10)
        try:
            top_k = int(top_k)
        except (ValueError, TypeError):
            top_k = 10
            
        cyber_context = bool(data.get('cyber_context', False))
        framework_id_str = _safe_get_string(data, 'framework_id')
        reg_code_str = _safe_get_string(data, 'registration_code')
        comp_code_str = _safe_get_string(data, 'competency_code')
        
        # Execute full mapping workflow
        service = get_framework_matching_service()
        result = service.get_full_mapping_workflow(
            framework_id=framework_id_str,
            registration_code=reg_code_str,
            competency_code=comp_code_str,
            cyber_context=cyber_context,
            top_k=top_k
        )
        
        return jsonify({
            'success': True,
            'result': result
        })
    
    except Exception as e:
        logger.error(f"Error mapping to SFIA: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
