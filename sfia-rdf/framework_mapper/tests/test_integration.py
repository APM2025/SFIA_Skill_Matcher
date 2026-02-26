import pytest
from run import create_app

@pytest.fixture
def app():
    """Create and configure a new app instance for each test."""
    # Create the app
    app = create_app()
    app.config.update({
        "TESTING": True,
        "RATELIMIT_ENABLED": False,
    })
    yield app

@pytest.fixture
def client(app):
    """A test client for the app."""
    return app.test_client()

def test_index_page(client):
    """Test that the index page loads correctly."""
    response = client.get('/')
    assert response.status_code == 200
    assert b'Framework to SFIA Mapper' in response.data

def test_api_get_frameworks(client):
    """Test that the frameworks API returns the expected data."""
    response = client.get('/api/frameworks')
    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] is True
    assert 'ukeng' in data['frameworks']
    assert 'UK Engineering Council' in data['frameworks']['ukeng']['name']

def test_api_get_registrations(client):
    """Test getting registrations for a specific framework."""
    response = client.get('/api/frameworks/ukeng/registrations')
    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] is True
    assert 'CEng' in data['registrations']
    assert 'IEng' in data['registrations']

def test_api_map_missing_fields(client):
    """Test mapping endpoint with missing required fields."""
    response = client.post('/api/map', json={
        "framework_id": "ukeng",
    })
    assert response.status_code == 400
    data = response.get_json()
    assert data['success'] is False

def test_api_map_valid_request_no_context(client):
    """Test standard mapping endpoint without cyber context."""
    response = client.post('/api/map', json={
        "framework_id": "ukeng",
        "registration_code": "CEng",
        "competency_code": "A",
        "cyber_context": False,
        "top_k": 3
    })
    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] is True
    assert 'result' in data
    assert 'indicator_mappings' in data['result']
    assert len(data['result']['indicator_mappings']) > 0
    
    indicator = data['result']['indicator_mappings'][0]
    assert len(indicator['sfia_mappings']) <= 3
    
    # Verify deduplication
    skill_names = [m['skill_name'] for m in indicator['sfia_mappings']]
    assert len(skill_names) == len(set(skill_names))
    
    assert data['result']['validation']['cyber_context_applied'] is False

def test_api_map_valid_request_with_context(client):
    """Test standard mapping endpoint with cyber context."""
    response = client.post('/api/map', json={
        "framework_id": "ukeng",
        "registration_code": "CEng",
        "competency_code": "A",
        "cyber_context": True,
        "top_k": 3
    })
    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] is True
    assert 'result' in data
    assert 'indicator_mappings' in data['result']
    assert len(data['result']['indicator_mappings']) > 0
    
    indicator = data['result']['indicator_mappings'][0]
    assert len(indicator['sfia_mappings']) <= 3
    
    # Verify deduplication
    skill_names = [m['skill_name'] for m in indicator['sfia_mappings']]
    assert len(skill_names) == len(set(skill_names))
    
    assert data['result']['validation']['cyber_context_applied'] is True
