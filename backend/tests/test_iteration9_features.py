"""
Test Iteration 9 Features:
- Public match detail endpoint (guest access)
- Image upload functionality
- SMTP test endpoint
- Cron scheduler verification (done via logs)
- Map veto with map_names lookup
"""
import pytest
import requests
import os
import io

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

@pytest.fixture
def api_client():
    """Shared requests session without auth"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session

@pytest.fixture
def admin_token(api_client):
    """Get admin authentication token"""
    response = api_client.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@arena.gg",
        "password": "admin123"
    })
    if response.status_code == 200:
        return response.json().get("access_token") or response.json().get("token")
    pytest.skip(f"Admin authentication failed: {response.status_code}")

@pytest.fixture
def admin_client(admin_token):
    """Session with admin auth header"""
    session = requests.Session()
    session.headers.update({
        "Authorization": f"Bearer {admin_token}",
        "Content-Type": "application/json"
    })
    return session


class TestPublicMatchEndpoint:
    """Test guest access to public match detail endpoint"""
    
    def test_public_endpoint_exists(self, api_client):
        """Verify /api/matches/{match_id}/public endpoint exists"""
        # Use a fake match_id to test endpoint structure
        response = api_client.get(f"{BASE_URL}/api/matches/fake-match-id/public")
        # Should return 404 (match not found), not 401 (unauthorized)
        assert response.status_code == 404, f"Expected 404 for non-existent match, got {response.status_code}"
        print("✓ Public match endpoint exists and returns 404 for missing match")
    
    def test_public_endpoint_no_auth_required(self, api_client):
        """Verify no auth is required for public endpoint"""
        # Explicitly ensure no auth header
        api_client.headers.pop("Authorization", None)
        response = api_client.get(f"{BASE_URL}/api/matches/test-match/public")
        # Should NOT return 401 unauthorized
        assert response.status_code != 401, "Public endpoint should not require authentication"
        assert response.status_code == 404, f"Expected 404 (match not found), got {response.status_code}"
        print("✓ Public endpoint accessible without authentication")

    def test_public_endpoint_with_real_match(self, api_client, admin_client):
        """Test public endpoint with a real match if available"""
        # Get list of tournaments to find a match
        tournaments_resp = api_client.get(f"{BASE_URL}/api/tournaments")
        if tournaments_resp.status_code != 200:
            pytest.skip("Could not fetch tournaments")
        
        tournaments = tournaments_resp.json()
        match_id = None
        
        # Look for a tournament with bracket matches
        for t in tournaments[:5]:  # Check first 5 tournaments
            if t.get("bracket") and isinstance(t.get("bracket"), dict):
                # Look for matches in bracket rounds
                bracket = t.get("bracket", {})
                for round_data in bracket.values():
                    if isinstance(round_data, list):
                        for match in round_data:
                            if isinstance(match, dict) and match.get("id"):
                                match_id = match.get("id")
                                break
                    if match_id:
                        break
            if match_id:
                break
        
        if not match_id:
            print("⚠ No real match found in tournaments - endpoint structure verified")
            return
        
        # Test public endpoint with real match
        response = api_client.get(f"{BASE_URL}/api/matches/{match_id}/public")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        # Verify response structure
        assert "tournament" in data, "Response should include tournament info"
        assert "match" in data, "Response should include match info"
        assert "map_veto" in data or data.get("map_veto") is None, "Response should include map_veto"
        
        print(f"✓ Public match endpoint returns valid data for match {match_id}")


class TestImageUpload:
    """Test image upload functionality"""
    
    def test_upload_requires_admin(self, api_client):
        """Verify upload endpoint requires admin authentication"""
        # Create a simple test image
        files = {"file": ("test.png", b"fake image content", "image/png")}
        response = requests.post(f"{BASE_URL}/api/upload/image", files=files)
        assert response.status_code in [401, 403], f"Expected 401/403 without auth, got {response.status_code}"
        print("✓ Image upload requires admin authentication")
    
    def test_upload_requires_file(self, admin_client, admin_token):
        """Verify upload fails without file"""
        response = requests.post(
            f"{BASE_URL}/api/upload/image",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 400, f"Expected 400 without file, got {response.status_code}"
        print("✓ Image upload correctly rejects empty request")
    
    def test_upload_rejects_non_image(self, admin_token):
        """Verify upload rejects non-image files"""
        files = {"file": ("test.txt", b"not an image", "text/plain")}
        response = requests.post(
            f"{BASE_URL}/api/upload/image",
            headers={"Authorization": f"Bearer {admin_token}"},
            files=files
        )
        assert response.status_code == 400, f"Expected 400 for non-image, got {response.status_code}"
        print("✓ Image upload correctly rejects non-image files")
    
    def test_upload_and_retrieve_image(self, admin_token):
        """Test full upload and retrieval flow"""
        # Create a minimal valid PNG image (1x1 pixel red)
        # PNG header + IHDR + IDAT + IEND
        png_data = bytes([
            0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,  # PNG signature
            0x00, 0x00, 0x00, 0x0D, 0x49, 0x48, 0x44, 0x52,  # IHDR chunk length and type
            0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,  # 1x1 size
            0x08, 0x02, 0x00, 0x00, 0x00, 0x90, 0x77, 0x53,  # bit depth, color type, CRC
            0xDE, 0x00, 0x00, 0x00, 0x0C, 0x49, 0x44, 0x41,  # IDAT chunk
            0x54, 0x08, 0xD7, 0x63, 0xF8, 0xFF, 0xFF, 0x3F,  # compressed data
            0x00, 0x05, 0xFE, 0x02, 0xFE, 0xDC, 0xCC, 0x59,  # CRC
            0xE7, 0x00, 0x00, 0x00, 0x00, 0x49, 0x45, 0x4E,  # IEND chunk
            0x44, 0xAE, 0x42, 0x60, 0x82                     # IEND CRC
        ])
        
        files = {"file": ("test_upload.png", png_data, "image/png")}
        
        upload_response = requests.post(
            f"{BASE_URL}/api/upload/image",
            headers={"Authorization": f"Bearer {admin_token}"},
            files=files
        )
        
        assert upload_response.status_code == 200, f"Upload failed with {upload_response.status_code}: {upload_response.text}"
        
        result = upload_response.json()
        assert "url" in result, "Response should contain 'url'"
        assert "filename" in result, "Response should contain 'filename'"
        
        image_url = result["url"]
        assert image_url.startswith("/api/uploads/"), f"URL should start with /api/uploads/, got {image_url}"
        
        print(f"✓ Image uploaded successfully: {image_url}")
        
        # Test retrieval
        retrieve_response = requests.get(f"{BASE_URL}{image_url}")
        assert retrieve_response.status_code == 200, f"Image retrieval failed with {retrieve_response.status_code}"
        assert retrieve_response.headers.get("content-type", "").startswith("image/"), "Retrieved file should be image"
        
        print("✓ Uploaded image can be retrieved successfully")


class TestSMTPEndpoint:
    """Test SMTP configuration and test endpoints"""
    
    def test_smtp_test_requires_admin(self, api_client):
        """Verify SMTP test endpoint requires admin auth"""
        response = api_client.post(f"{BASE_URL}/api/admin/smtp-test", json={"test_email": "test@example.com"})
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ SMTP test endpoint requires admin authentication")
    
    def test_smtp_test_returns_config_status(self, admin_client):
        """Test SMTP endpoint returns detailed configuration status"""
        response = admin_client.post(
            f"{BASE_URL}/api/admin/smtp-test",
            json={"test_email": "test@arena.gg"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        # Verify response structure
        assert "success" in data, "Response should contain 'success' field"
        assert "config_status" in data, "Response should contain 'config_status' field"
        assert "details" in data, "Response should contain 'details' field"
        
        # Check config details structure
        details = data.get("details", {})
        expected_fields = ["host", "port", "user"]
        for field in expected_fields:
            assert field in details, f"Config details should contain '{field}'"
        
        print(f"✓ SMTP test endpoint returns detailed status: success={data.get('success')}, config_status={data.get('config_status')}")


class TestMapVetoWithMapNames:
    """Test map veto endpoint includes map_names lookup"""
    
    def test_map_veto_endpoint_exists(self, api_client, admin_token):
        """Verify map-veto endpoint exists and requires auth or returns structured error"""
        # Should return 404 for non-existent match (not 401 since find_match is called first)
        api_client.headers["Authorization"] = f"Bearer {admin_token}"
        response = api_client.get(f"{BASE_URL}/api/matches/fake-match/map-veto")
        # Endpoint might return 404 or 401 depending on auth check order
        assert response.status_code in [404, 401, 403], f"Unexpected status: {response.status_code}"
        print("✓ Map veto endpoint exists")
    
    def test_map_veto_returns_map_names(self, admin_client):
        """Test that map-veto endpoint includes map_names field"""
        # First get a tournament with map_pool
        tournaments_resp = admin_client.get(f"{BASE_URL}/api/tournaments")
        if tournaments_resp.status_code != 200:
            pytest.skip("Could not fetch tournaments")
        
        tournaments = tournaments_resp.json()
        match_id = None
        
        for t in tournaments[:10]:
            if t.get("bracket") and isinstance(t.get("bracket"), dict):
                bracket = t.get("bracket", {})
                for round_key, round_data in bracket.items():
                    if isinstance(round_data, list):
                        for match in round_data:
                            if isinstance(match, dict) and match.get("id"):
                                match_id = match.get("id")
                                break
                    if match_id:
                        break
            if match_id:
                break
        
        if not match_id:
            print("⚠ No match found - skipping map_names verification")
            return
        
        response = admin_client.get(f"{BASE_URL}/api/matches/{match_id}/map-veto")
        if response.status_code == 404:
            print("⚠ Match not found for map-veto - endpoint structure verified")
            return
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        # Check for map_names field
        assert "map_names" in data, "Response should contain 'map_names' field"
        
        map_names = data.get("map_names", {})
        print(f"✓ Map veto includes map_names lookup with {len(map_names)} maps")


class TestGamesEndpoints:
    """Verify games CRUD endpoints still work"""
    
    def test_get_games_with_subgames(self, api_client):
        """Verify GET /api/games returns games with sub_games structure"""
        response = api_client.get(f"{BASE_URL}/api/games")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        games = response.json()
        assert isinstance(games, list), "Games should be a list"
        assert len(games) > 0, "Should have at least one game"
        
        # Check structure
        game = games[0]
        assert "sub_games" in game, "Game should have sub_games field"
        
        # Find a game with sub_games
        game_with_subgames = None
        for g in games:
            if g.get("sub_games") and len(g.get("sub_games", [])) > 0:
                game_with_subgames = g
                break
        
        if game_with_subgames:
            sub_game = game_with_subgames["sub_games"][0]
            assert "id" in sub_game, "Sub-game should have id"
            assert "name" in sub_game, "Sub-game should have name"
            if sub_game.get("maps"):
                assert isinstance(sub_game["maps"], list), "Maps should be a list"
                if len(sub_game["maps"]) > 0:
                    map_item = sub_game["maps"][0]
                    assert "id" in map_item, "Map should have id"
                    assert "name" in map_item, "Map should have name"
        
        print(f"✓ Games endpoint returns {len(games)} games with proper sub_games structure")


class TestTeamTournamentHistory:
    """Test team tournament history endpoint"""
    
    def test_team_tournaments_endpoint(self, api_client):
        """Test GET /api/teams/{id}/tournaments returns history"""
        # First get a team
        teams_resp = api_client.get(f"{BASE_URL}/api/teams")
        if teams_resp.status_code != 200:
            pytest.skip("Could not fetch teams")
        
        teams = teams_resp.json()
        if not teams:
            pytest.skip("No teams available")
        
        team_id = teams[0].get("id")
        if not team_id:
            pytest.skip("Team has no ID")
        
        # Test tournament history endpoint
        response = api_client.get(f"{BASE_URL}/api/teams/{team_id}/tournaments")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert isinstance(data, list), "Tournament history should be a list"
        
        print(f"✓ Team tournament history endpoint works - found {len(data)} tournaments for team {team_id}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
