import pytest
from app import create_app

@pytest.fixture
def app():
    # Enforce testing configuration
    app = create_app()
    app.config.update({
        "TESTING": True,
        "WTF_CSRF_ENABLED": True,      # Ensure CSRF is active during tests
        "WTF_CSRF_METHODS": ['POST'], # Only validate CSRF on POST
    })
    yield app

@pytest.fixture
def client(app):
    return app.test_client()

def test_security_headers(client):
    """Verify that Talisman injects expected secure HTTP headers."""
    response = client.get('/')
    assert response.status_code == 200
    headers = response.headers
    
    # Check for crucial security headers
    assert 'X-Content-Type-Options' in headers
    assert headers['X-Content-Type-Options'] == 'nosniff'
    assert 'Content-Security-Policy' in headers
    assert 'default-src \'self\'' in headers['Content-Security-Policy']

def test_csrf_protection_missing_token(client):
    """Verify that posting to /match without a CSRF token returns a 400 Bad Request."""
    response = client.post('/match', json={"evidence": "Test data", "level_context": ""})
    
    # Flask-WTF CSRF returns a 400 Bad Request when missing/invalid
    assert response.status_code == 400
    assert b"CSRF token" in response.data or b"The CSRF session token is missing" in response.data or b"CSRF token missing" in response.data or b"The CSRF token is missing" in response.data

def test_rate_limiting(client):
    """Verify that hitting the /match endpoint > 5 times per minute triggers a 429 Too Many Requests."""
    
    # Get a valid CSRF token first
    resp = client.get('/csrf-token')
    assert resp.status_code == 200
    csrf_token = resp.json.get('csrf_token')
    
    headers = {'X-CSRFToken': csrf_token}
    data = {"evidence": "Test evidence", "level_context": "Test context"}
    
    # Hit the limit (5 per minute)
    for _ in range(5):
        # We might occasionally get a 400 if validation fails, but let's just make the request
        res = client.post('/match', json=data, headers=headers)
        # Should be 200 OK or 400 Bad Request (evidence validation), but NOT 429 yet
        assert res.status_code in [200, 400, 500] 
        
    # The 6th request should be rate limited
    limited_response = client.post('/match', json=data, headers=headers)
    assert limited_response.status_code == 429
    assert b"Too Many Requests" in limited_response.data
