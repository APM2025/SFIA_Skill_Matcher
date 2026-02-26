import pytest
from app import create_app

@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    with app.test_client() as client:
        yield client

def test_full_match_pipeline(client):
    """Test the end-to-end /match endpoint with a full STAR string."""
    payload = {
        "situation": "Our legacy payment system was dropping 5% of transactions during peak load.",
        "task": "I needed to investigate the root cause and implement a reliable solution.",
        "action": "I led a team of 3 developers to rewrite the core transaction engine in Python. "
                  "I designed a new messaging queue architecture using Redis and RabbitMQ. "
                  "I mentored the junior developers through the code review process.",
        "result": "The new system handled 10x the load with zero dropped transactions.",
        "level_context": "I managed a small team and designed complex solutions autonomously."
    }
    
    response = client.post('/match', json=payload)
    
    assert response.status_code == 200
    data = response.get_json()
    
    # Assert successful match structure
    assert "matches" in data
    assert "detected_level" in data
    assert "best_fit_summary" in data
    assert "level_breakdown" in data
    
    matches = data["matches"]
    assert len(matches) > 0
    
    top_skill = matches[0]
    assert "code" in top_skill
    assert "label" in top_skill
    assert "score" in top_skill
    assert top_skill["score"] <= 1.0
    
    # The summary should be a dictionary now, not HTML
    assert isinstance(data["best_fit_summary"], dict)

def test_refine_pipeline(client):
    """Test the /refine endpoint."""
    payload = {
        "situation": "",
        "task": "",
        "action": "I configured the firewall rules.",
        "result": "",
        "level_context": "",
        "clarification": "I did security audits and advanced penetration testing."
    }
    
    response = client.post('/refine', json=payload)
    assert response.status_code == 200
    data = response.get_json()
    assert data.get("refined") is True
    assert len(data["matches"]) > 0
    
def test_input_validation(client):
    """Test input validation with an integer instead of a string."""
    payload = {
        "situation": 12345,
        "task": None,
        "action": "Valid action text",
        "result": ["invalid", "type"]
    }
    
    response = client.post('/match', json=payload)
    assert response.status_code == 200
    data = response.get_json()
    assert "matches" in data
