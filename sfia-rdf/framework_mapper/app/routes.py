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


@bp.route('/api/validate', methods=['POST'])
def validate_evidence():
    """Validate evidence against a framework competency.
    
    Request JSON:
        {
            "evidence": "STAR evidence text",
            "framework_id": "ukeng",
            "registration_code": "CEng",
            "competency_code": "A"
        }
    
    Returns:
        JSON with validation results
    """
    try:
        data = request.get_json()
        
        # Validate input
        required_fields = ['evidence', 'framework_id', 'registration_code', 'competency_code']
        for field in required_fields:
            if field not in data:
                return jsonify({
                    'success': False,
                    'error': f'Missing required field: {field}'
                }), 400
        
        # Perform validation
        service = get_framework_matching_service()
        validation = service.validate_evidence_for_competency(
            evidence=data['evidence'],
            framework_id=data['framework_id'],
            registration_code=data['registration_code'],
            competency_code=data['competency_code']
        )
        
        return jsonify({
            'success': True,
            'validation': {
                'competency_code': validation.competency_code,
                'competency_title': validation.competency_title,
                'match_score': validation.match_score,
                'relevance': validation.evidence_relevance,
                'keyword_matches': validation.keyword_matches,
                'feedback': _get_validation_feedback(validation)
            }
        })
    
    except Exception as e:
        logger.error(f"Error validating evidence: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/api/map', methods=['POST'])
def map_to_sfia():
    """Map framework competency + evidence to SFIA skills.
    
    Request JSON:
        {
            "evidence": "STAR evidence text",
            "framework_id": "ukeng",
            "registration_code": "CEng",
            "competency_code": "A",
            "top_k": 10
        }
    
    Returns:
        JSON with validation + SFIA skill mappings
    """
    try:
        data = request.get_json()
        
        # Validate input
        required_fields = ['evidence', 'framework_id', 'registration_code', 'competency_code']
        for field in required_fields:
            if field not in data:
                return jsonify({
                    'success': False,
                    'error': f'Missing required field: {field}'
                }), 400
        
        top_k = data.get('top_k', 10)
        
        # Execute full mapping workflow
        service = get_framework_matching_service()
        result = service.get_full_mapping_workflow(
            evidence=data['evidence'],
            framework_id=data['framework_id'],
            registration_code=data['registration_code'],
            competency_code=data['competency_code'],
            top_k=top_k
        )
        
        # Add feedback to validation
        result['validation']['feedback'] = _get_validation_feedback_from_dict(
            result['validation']
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


def _get_validation_feedback(validation) -> str:
    """Generate user-friendly feedback based on validation results."""
    relevance = validation.evidence_relevance
    score = validation.match_score
    
    if relevance == 'high':
        return (
            f"✓ Strong match! Your evidence demonstrates {validation.competency_title} well. "
            f"({score:.0%} match with {len(validation.keyword_matches)} key indicators)"
        )
    elif relevance == 'medium':
        return (
            f"⚠ Moderate match. Your evidence shows some alignment with {validation.competency_title}, "
            f"but could be strengthened. ({score:.0%} match)"
        )
    else:
        return (
            f"✗ Weak match. Your evidence may not strongly demonstrate {validation.competency_title}. "
            f"Consider providing more specific examples. ({score:.0%} match)"
        )


def _get_validation_feedback_from_dict(validation_dict: dict) -> str:
    """Generate feedback from validation dict."""
    relevance = validation_dict['relevance']
    score = validation_dict['match_score']
    title = validation_dict['competency_title']
    keywords = len(validation_dict['keyword_matches'])
    
    if relevance == 'high':
        return (
            f"✓ Strong match! Your evidence demonstrates {title} well. "
            f"({score:.0%} match with {keywords} key indicators)"
        )
    elif relevance == 'medium':
        return (
            f"⚠ Moderate match. Your evidence shows some alignment with {title}, "
            f"but could be strengthened. ({score:.0%} match)"
        )
    else:
        return (
            f"✗ Weak match. Your evidence may not strongly demonstrate {title}. "
            f"Consider providing more specific examples. ({score:.0%} match)"
        )
