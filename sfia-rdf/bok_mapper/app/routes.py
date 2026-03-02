import os
from pathlib import Path
from flask import Blueprint, jsonify, request, render_template

from .services.bok_parser import BokParser
from .services.bok_matching import BokMatchingService

# Initialize Blueprint
bp = Blueprint('main', __name__)

# Initialize singletons for services
_parser = None
_matcher = None

def get_parser():
    global _parser
    if _parser is None:
        # Load JSON definition from the 'bods_of_knowledge' directory
        bok_dir = Path(__file__).parent.parent / 'bods_of_knowledge'
        _parser = BokParser(str(bok_dir))
    return _parser

def get_matcher():
    global _matcher
    if _matcher is None:
        _matcher = BokMatchingService(get_parser())
    return _matcher


@bp.route('/')
def index():
    """Serves the main application page."""
    return render_template('index.html')


@bp.route('/api/boks', methods=['GET'])
def get_boks():
    """Returns a list of all available Bodies of Knowledge."""
    try:
        parser = get_parser()
        boks = parser.get_bok_summaries()
        return jsonify({
            "success": True,
            "boks": boks
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@bp.route('/api/boks/<bok_id>/knowledge_areas', methods=['GET'])
def get_knowledge_areas(bok_id):
    """Returns KAs for a specific BoK."""
    try:
        parser = get_parser()
        kas = parser.get_knowledge_areas(bok_id)
        if kas is None:
            return jsonify({
                "success": False,
                "error": f"BoK '{bok_id}' not found"
            }), 404
            
        return jsonify({
            "success": True,
            "knowledge_areas": kas
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@bp.route('/api/map', methods=['POST'])
def map_knowledge_area():
    """Endpoint for mapping a specific Knowledge Area to SFIA."""
    try:
        data = request.json
        if not data:
            return jsonify({"success": False, "error": "No JSON data provided"}), 400

        bok_id = data.get('bok_id')
        ka_id = data.get('ka_id')
        cyber_context = data.get('cyber_context', False)
        top_k = data.get('top_k', 10)

        if not bok_id or not ka_id:
            return jsonify({"success": False, "error": "Missing bok_id or ka_id parameter"}), 400

        matcher = get_matcher()
        result = matcher.get_full_mapping_workflow(
            bok_id=bok_id,
            ka_id=ka_id,
            cyber_context=cyber_context,
            top_k=top_k
        )
        
        return jsonify(result)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
