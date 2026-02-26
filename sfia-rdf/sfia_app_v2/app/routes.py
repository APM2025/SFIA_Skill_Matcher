"""Flask route handlers for the SFIA Matcher application.

Endpoints:
    GET  /             — Serve the single-page UI
    GET  /csrf-token   — Return a fresh CSRF token for the frontend
    POST /match        — Run the full semantic matching pipeline
    POST /refine       — Re-run matching with a user-supplied clarification
"""

import logging
import re
from typing import Any

from flask import Blueprint, current_app, jsonify, render_template, request
from flask_wtf.csrf import generate_csrf

from app import limiter

logger = logging.getLogger(__name__)
main = Blueprint("main", __name__)

# Control characters and null bytes have no legitimate use in evidence text
# and can cause unpredictable behaviour in downstream NLP processing.
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _sanitise(text: str) -> str:
    """Strip null bytes and ASCII control characters from user-supplied text.

    Printable characters, newlines (``\\n``), and tabs (``\\t``) are preserved.

    Args:
        text: Raw string from the request body.

    Returns:
        Cleaned string safe to pass to the NLP pipeline.
    """
    return _CONTROL_CHAR_RE.sub("", text)


def _safe_get_string(data: dict[str, Any], key: str, default: str = "") -> str:
    """Safely extract a value from a dict and ensure it is a string."""
    val = data.get(key, default)
    if val is None:
        return default
    return str(val).strip()


def _build_evidence(data: dict[str, Any]) -> str:
    """Assemble a labelled STAR evidence string from a request payload.

    Accepts individual STAR fields (``situation``, ``task``, ``action``,
    ``result``) and joins them with clear headings so the backend parser
    always receives consistently formatted input.

    Falls back to a legacy ``evidence`` field when ``action`` is absent
    (for backwards-compatibility with any old API clients).

    Args:
        data: Parsed JSON body from the request.

    Returns:
        A multi-line string with STAR section headings, or a plain text blob.
    """
    situation = _sanitise(_safe_get_string(data, "situation"))
    task = _sanitise(_safe_get_string(data, "task"))
    action = _sanitise(_safe_get_string(data, "action"))
    result_text = _sanitise(_safe_get_string(data, "result"))

    if action:
        return "\n\n".join(
            filter(
                None,
                [
                    f"Situation\n{situation}" if situation else "",
                    f"Task\n{task}" if task else "",
                    f"Action\n{action}",
                    f"Result\n{result_text}" if result_text else "",
                ],
            )
        )
    # Legacy fallback: single blob of text
    return _sanitise(_safe_get_string(data, "evidence"))


def _get_matcher():
    """Return the shared MatchingService from the app extension registry."""
    return current_app.extensions["matching_service"]


@main.route("/")
def home():
    """Serve the single-page application."""
    return render_template("index.html")


@main.route("/csrf-token", methods=["GET"])
def get_csrf_token():
    """Return a fresh CSRF token for use in subsequent POST requests.

    The frontend fetches this on load and attaches the token as the
    ``X-CSRFToken`` header on every state-changing request.
    """
    return jsonify({"csrf_token": generate_csrf()})


@main.route("/match", methods=["POST"])
@limiter.limit(lambda: current_app.config["MATCH_RATE_LIMIT"])
def match():
    """Run the full SFIA semantic matching pipeline against submitted evidence.

    Expected JSON body fields:
        situation (str):      STAR Situation section
        task (str):           STAR Task section
        action (str):         STAR Action section — **required**
        result (str):         STAR Result section
        level_context (str):  Optional level of responsibility description

    Returns:
        200 JSON payload with ``matches``, ``detected_level``,
        ``level_breakdown``, and ``best_fit_summary``.
        400 if the action field is missing or input exceeds length limits.
        500 on unexpected errors.
    """
    data = request.json
    max_len = current_app.config["EVIDENCE_MAX_LENGTH"]

    evidence = _build_evidence(data)
    level_context = _sanitise(_safe_get_string(data, "level_context"))

    if not evidence:
        return jsonify({"error": "Please fill in at least the Action field"}), 400
    if len(evidence) > max_len:
        return jsonify({"error": f"Evidence too long (max {max_len} characters)"}), 400
    if len(level_context) > max_len:
        return jsonify({"error": f"Level context too long (max {max_len} characters)"}), 400

    try:
        result = _get_matcher().match(evidence, level_context)
        return jsonify(result)
    except Exception:
        logger.exception("Error processing /match request.")
        return jsonify({"error": "Internal Server Error"}), 500


@main.route("/refine", methods=["POST"])
@limiter.limit(lambda: current_app.config["REFINE_RATE_LIMIT"])
def refine():
    """Re-run matching with a user-supplied clarification blended into the query.

    Accepts the same STAR fields as ``/match`` plus a ``clarification`` field
    that steers the re-match toward the user's intended meaning.

    Expected JSON body fields:
        situation, task, action, result, level_context: same as /match
        clarification (str): One-sentence correction, e.g. "It was more about
            root cause analysis than governance." — **required**

    Returns:
        200 JSON payload identical to /match, plus ``refined: true``.
        400 if evidence or clarification is missing or too long.
        500 on unexpected errors.
    """
    data = request.json
    max_len = current_app.config["EVIDENCE_MAX_LENGTH"]

    evidence = _build_evidence(data)
    level_context = _sanitise(_safe_get_string(data, "level_context"))
    clarification = _sanitise(_safe_get_string(data, "clarification"))

    if not evidence:
        return jsonify({"error": "No evidence provided"}), 400
    if not clarification:
        return jsonify({"error": "No clarification provided"}), 400
    if len(clarification) > 500:
        return jsonify({"error": "Clarification too long (max 500 characters)"}), 400

    try:
        result = _get_matcher().match(evidence, level_context, clarification=clarification)
        result["refined"] = True
        return jsonify(result)
    except Exception:
        logger.exception("Error processing /refine request.")
        return jsonify({"error": "Internal Server Error"}), 500
