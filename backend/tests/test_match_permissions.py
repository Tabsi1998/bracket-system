"""
Test file for Match Permission Security Fix (Iteration 10)
Tests that non-participants and guests only see read-only match info.
Participants and admins see action controls.
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test IDs from the review request
TOURNAMENT_ID = "039182cb-ea39-565a-982f-15142fb386bf"
MATCH_ID = "4c6fe761-6aa0-5fe1-b259-afcb1c268d50"  # ARES Alpha vs NOVA Prime

# Test credentials
ADMIN_EMAIL = "admin@arena.gg"
ADMIN_PASSWORD = "admin123"
PARTICIPANT_EMAIL = "demo.alpha1@arena.gg"  # ARES Alpha owner
PARTICIPANT_PASSWORD = "demo123"
NON_PARTICIPANT_EMAIL = "demo.charlie1@arena.gg"  # CharlieOne - NOT in this match
NON_PARTICIPANT_PASSWORD = "demo123"


@pytest.fixture
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


def login(api_client, email, password):
    """Helper to login and get token"""
    response = api_client.post(f"{BASE_URL}/api/auth/login", json={
        "email": email,
        "password": password
    })
    if response.status_code == 200:
        return response.json().get("token")
    return None


class TestMatchPermissionsGuest:
    """Test match permissions for guest (unauthenticated) users"""
    
    def test_guest_public_endpoint_returns_can_manage_false(self, api_client):
        """GET /api/matches/{matchId}/public returns can_manage_match: false for guests"""
        response = api_client.get(f"{BASE_URL}/api/matches/{MATCH_ID}/public")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "viewer" in data, "Response should have viewer field"
        assert data["viewer"]["can_manage_match"] == False, "Guest should have can_manage_match: false"
        assert data["viewer"]["is_admin"] == False, "Guest should have is_admin: false"
        assert data["viewer"]["side"] is None, "Guest should have side: null"
        print("PASS: Guest sees can_manage_match: false via /public endpoint")
    
    def test_guest_public_endpoint_returns_match_data(self, api_client):
        """GET /api/matches/{matchId}/public returns match data for guests"""
        response = api_client.get(f"{BASE_URL}/api/matches/{MATCH_ID}/public")
        assert response.status_code == 200
        
        data = response.json()
        assert "match" in data, "Response should have match field"
        assert "tournament" in data, "Response should have tournament field"
        assert data["match"].get("id") == MATCH_ID, "Match ID should match"
        print(f"PASS: Guest can see match data - {data['match'].get('team1_name')} vs {data['match'].get('team2_name')}")
    
    def test_guest_authenticated_endpoint_requires_auth(self, api_client):
        """GET /api/matches/{matchId} (authenticated endpoint) requires auth"""
        response = api_client.get(f"{BASE_URL}/api/matches/{MATCH_ID}")
        # Should return 401 or 403 for unauthenticated users
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("PASS: Authenticated match endpoint requires auth")


class TestMatchPermissionsNonParticipant:
    """Test match permissions for logged-in but non-participating users"""
    
    def test_non_participant_returns_can_manage_false(self, api_client):
        """GET /api/matches/{matchId} as non-participant returns can_manage_match: false (not 403)"""
        token = login(api_client, NON_PARTICIPANT_EMAIL, NON_PARTICIPANT_PASSWORD)
        assert token, f"Failed to login as {NON_PARTICIPANT_EMAIL}"
        
        api_client.headers.update({"Authorization": f"Bearer {token}"})
        response = api_client.get(f"{BASE_URL}/api/matches/{MATCH_ID}")
        
        # CRITICAL: Should NOT return 403, should return 200 with can_manage_match: false
        assert response.status_code == 200, f"Expected 200 (not 403), got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "viewer" in data, "Response should have viewer field"
        assert data["viewer"]["can_manage_match"] == False, "Non-participant should have can_manage_match: false"
        assert data["viewer"]["side"] is None, "Non-participant should have side: null"
        print(f"PASS: Non-participant ({NON_PARTICIPANT_EMAIL}) sees can_manage_match: false")
    
    def test_non_participant_cannot_schedule(self, api_client):
        """POST /api/matches/{matchId}/schedule requires team membership"""
        token = login(api_client, NON_PARTICIPANT_EMAIL, NON_PARTICIPANT_PASSWORD)
        assert token, f"Failed to login as {NON_PARTICIPANT_EMAIL}"
        
        api_client.headers.update({"Authorization": f"Bearer {token}"})
        response = api_client.post(f"{BASE_URL}/api/matches/{MATCH_ID}/schedule", json={
            "proposed_time": "2026-02-01T15:00:00Z"
        })
        
        # Should be 403 Forbidden - non-participant cannot propose schedule
        assert response.status_code == 403, f"Expected 403, got {response.status_code}: {response.text}"
        print("PASS: Non-participant cannot propose schedule (403)")
    
    def test_non_participant_cannot_map_veto(self, api_client):
        """POST /api/matches/{matchId}/map-veto requires team membership"""
        token = login(api_client, NON_PARTICIPANT_EMAIL, NON_PARTICIPANT_PASSWORD)
        assert token, f"Failed to login as {NON_PARTICIPANT_EMAIL}"
        
        api_client.headers.update({"Authorization": f"Bearer {token}"})
        response = api_client.post(f"{BASE_URL}/api/matches/{MATCH_ID}/map-veto", json={
            "action": "ban",
            "map_id": "test-map"
        })
        
        # Should be 403 Forbidden - non-participant cannot do map veto
        assert response.status_code == 403, f"Expected 403, got {response.status_code}: {response.text}"
        print("PASS: Non-participant cannot perform map veto (403)")


class TestMatchPermissionsParticipant:
    """Test match permissions for team member/owner (participant)"""
    
    def test_participant_returns_can_manage_true(self, api_client):
        """GET /api/matches/{matchId} as participant returns can_manage_match: true"""
        token = login(api_client, PARTICIPANT_EMAIL, PARTICIPANT_PASSWORD)
        assert token, f"Failed to login as {PARTICIPANT_EMAIL}"
        
        api_client.headers.update({"Authorization": f"Bearer {token}"})
        response = api_client.get(f"{BASE_URL}/api/matches/{MATCH_ID}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "viewer" in data, "Response should have viewer field"
        assert data["viewer"]["can_manage_match"] == True, "Participant should have can_manage_match: true"
        assert data["viewer"]["side"] in ["team1", "team2"], f"Participant should have side: team1 or team2, got {data['viewer']['side']}"
        print(f"PASS: Participant ({PARTICIPANT_EMAIL}) sees can_manage_match: true, side: {data['viewer']['side']}")
    
    def test_participant_has_setup_data(self, api_client):
        """GET /api/matches/{matchId} as participant returns setup data"""
        token = login(api_client, PARTICIPANT_EMAIL, PARTICIPANT_PASSWORD)
        assert token, f"Failed to login as {PARTICIPANT_EMAIL}"
        
        api_client.headers.update({"Authorization": f"Bearer {token}"})
        response = api_client.get(f"{BASE_URL}/api/matches/{MATCH_ID}")
        
        assert response.status_code == 200
        data = response.json()
        
        # Participant should see setup data
        assert "setup" in data, "Participant should see setup field"
        print(f"PASS: Participant sees setup data in response")


class TestMatchPermissionsAdmin:
    """Test match permissions for admin users"""
    
    def test_admin_returns_can_manage_true(self, api_client):
        """GET /api/matches/{matchId} as admin returns can_manage_match: true and is_admin: true"""
        token = login(api_client, ADMIN_EMAIL, ADMIN_PASSWORD)
        assert token, f"Failed to login as {ADMIN_EMAIL}"
        
        api_client.headers.update({"Authorization": f"Bearer {token}"})
        response = api_client.get(f"{BASE_URL}/api/matches/{MATCH_ID}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "viewer" in data, "Response should have viewer field"
        assert data["viewer"]["can_manage_match"] == True, "Admin should have can_manage_match: true"
        assert data["viewer"]["is_admin"] == True, "Admin should have is_admin: true"
        print(f"PASS: Admin sees can_manage_match: true and is_admin: true")
    
    def test_admin_can_access_match_setup(self, api_client):
        """GET /api/matches/{matchId}/setup - admin can access setup endpoint"""
        token = login(api_client, ADMIN_EMAIL, ADMIN_PASSWORD)
        assert token, f"Failed to login as {ADMIN_EMAIL}"
        
        api_client.headers.update({"Authorization": f"Bearer {token}"})
        response = api_client.get(f"{BASE_URL}/api/matches/{MATCH_ID}/setup")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print("PASS: Admin can access /setup endpoint")


class TestScheduleEndpointSecurity:
    """Test POST /api/matches/{matchId}/schedule security"""
    
    def test_schedule_requires_auth(self, api_client):
        """POST /api/matches/{matchId}/schedule requires authentication"""
        response = api_client.post(f"{BASE_URL}/api/matches/{MATCH_ID}/schedule", json={
            "proposed_time": "2026-02-01T15:00:00Z"
        })
        
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("PASS: Schedule endpoint requires authentication")


class TestMapVetoEndpointSecurity:
    """Test POST /api/matches/{matchId}/map-veto security"""
    
    def test_map_veto_requires_auth(self, api_client):
        """POST /api/matches/{matchId}/map-veto requires authentication"""
        response = api_client.post(f"{BASE_URL}/api/matches/{MATCH_ID}/map-veto", json={
            "action": "ban",
            "map_id": "test-map"
        })
        
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("PASS: Map veto endpoint requires authentication")
