"""
Test Suite for Sub-Games, Maps, and Tournament Integration
Testing the complete Games/Sub-Games/Maps system as per iteration 8 requirements
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@arena.gg"
ADMIN_PASSWORD = "admin123"


class TestSetup:
    """Setup fixtures for authentication"""

    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Admin login failed: {response.text}"
        data = response.json()
        assert "token" in data, "No token in response"
        return data["token"]

    @pytest.fixture(scope="class")
    def admin_headers(self, admin_token):
        """Headers with admin auth token"""
        return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


class TestGamesEndpoint(TestSetup):
    """Test games listing and structure"""

    def test_get_games_list(self):
        """GET /api/games - Should return list of games with sub-games"""
        response = requests.get(f"{BASE_URL}/api/games")
        assert response.status_code == 200
        
        games = response.json()
        assert isinstance(games, list)
        assert len(games) > 0, "No games found in database"
        
        # Check game structure
        for game in games:
            assert "id" in game
            assert "name" in game
            print(f"Found game: {game['name']} with {len(game.get('sub_games', []))} sub-games")

    def test_cod_game_has_subgames(self):
        """Verify CoD has sub-games (BO6, MW3, BOCW)"""
        response = requests.get(f"{BASE_URL}/api/games")
        assert response.status_code == 200
        
        games = response.json()
        cod_game = next((g for g in games if g['name'] == 'Call of Duty'), None)
        assert cod_game is not None, "Call of Duty game not found"
        
        sub_games = cod_game.get('sub_games', [])
        assert len(sub_games) >= 3, f"Expected 3+ sub-games for CoD, got {len(sub_games)}"
        
        # Verify expected sub-games exist
        sub_game_names = [sg['name'] for sg in sub_games]
        expected_names = ['Black Ops 6', 'Modern Warfare 3', 'Black Ops Cold War']
        for name in expected_names:
            assert name in sub_game_names, f"Missing sub-game: {name}"
        
        # Verify maps exist in sub-games
        total_maps = sum(len(sg.get('maps', [])) for sg in sub_games)
        assert total_maps >= 18, f"Expected 18+ maps for CoD, got {total_maps}"

    def test_cs2_game_has_subgame(self):
        """Verify CS2 has sub-game with 7 maps"""
        response = requests.get(f"{BASE_URL}/api/games")
        assert response.status_code == 200
        
        games = response.json()
        cs2_game = next((g for g in games if g['name'] == 'Counter-Strike 2'), None)
        assert cs2_game is not None, "CS2 game not found"
        
        sub_games = cs2_game.get('sub_games', [])
        assert len(sub_games) >= 1, f"Expected 1+ sub-games for CS2, got {len(sub_games)}"
        
        # Check Premier sub-game
        premier = sub_games[0]
        maps = premier.get('maps', [])
        assert len(maps) >= 7, f"Expected 7+ maps for CS2 Premier, got {len(maps)}"

    def test_valorant_game_has_subgame(self):
        """Verify Valorant has sub-game with 9 maps"""
        response = requests.get(f"{BASE_URL}/api/games")
        assert response.status_code == 200
        
        games = response.json()
        valorant = next((g for g in games if g['name'] == 'Valorant'), None)
        assert valorant is not None, "Valorant game not found"
        
        sub_games = valorant.get('sub_games', [])
        assert len(sub_games) >= 1, f"Expected 1+ sub-games for Valorant"
        
        maps = sub_games[0].get('maps', [])
        assert len(maps) >= 9, f"Expected 9+ maps for Valorant, got {len(maps)}"


class TestSubGamesCRUD(TestSetup):
    """Test Sub-Game CRUD operations"""

    @pytest.fixture(scope="class")
    def test_game_id(self):
        """Get a game ID for testing"""
        response = requests.get(f"{BASE_URL}/api/games")
        assert response.status_code == 200
        games = response.json()
        # Get CoD game
        cod = next((g for g in games if g['name'] == 'Call of Duty'), None)
        assert cod is not None
        return cod['id']

    def test_create_sub_game(self, admin_headers, test_game_id):
        """POST /api/games/{game_id}/sub-games - Create new sub-game"""
        unique_name = f"TEST_SubGame_{uuid.uuid4().hex[:6]}"
        payload = {
            "name": unique_name,
            "short_name": "TSG",
            "release_year": 2025,
            "active": True
        }
        
        response = requests.post(
            f"{BASE_URL}/api/games/{test_game_id}/sub-games",
            headers=admin_headers,
            json=payload
        )
        assert response.status_code == 200, f"Create sub-game failed: {response.text}"
        
        data = response.json()
        assert data['name'] == unique_name
        assert 'id' in data
        
        # Store for cleanup
        self.__class__.created_sub_game_id = data['id']
        print(f"Created sub-game: {data['id']}")

    def test_update_sub_game(self, admin_headers, test_game_id):
        """PUT /api/games/{game_id}/sub-games/{sub_game_id} - Update sub-game"""
        sub_game_id = getattr(self.__class__, 'created_sub_game_id', None)
        if not sub_game_id:
            pytest.skip("No sub-game created to update")
        
        payload = {
            "name": f"TEST_Updated_{uuid.uuid4().hex[:4]}",
            "active": False
        }
        
        response = requests.put(
            f"{BASE_URL}/api/games/{test_game_id}/sub-games/{sub_game_id}",
            headers=admin_headers,
            json=payload
        )
        assert response.status_code == 200, f"Update sub-game failed: {response.text}"

    def test_delete_sub_game(self, admin_headers, test_game_id):
        """DELETE /api/games/{game_id}/sub-games/{sub_game_id} - Delete sub-game"""
        sub_game_id = getattr(self.__class__, 'created_sub_game_id', None)
        if not sub_game_id:
            pytest.skip("No sub-game created to delete")
        
        response = requests.delete(
            f"{BASE_URL}/api/games/{test_game_id}/sub-games/{sub_game_id}",
            headers=admin_headers
        )
        assert response.status_code == 200, f"Delete sub-game failed: {response.text}"
        print(f"Deleted sub-game: {sub_game_id}")


class TestMapsCRUD(TestSetup):
    """Test Map CRUD operations"""

    @pytest.fixture(scope="class")
    def test_game_and_subgame(self):
        """Get game and sub-game IDs for testing"""
        response = requests.get(f"{BASE_URL}/api/games")
        assert response.status_code == 200
        games = response.json()
        
        cod = next((g for g in games if g['name'] == 'Call of Duty'), None)
        assert cod is not None
        
        # Get first sub-game
        sub_games = cod.get('sub_games', [])
        assert len(sub_games) > 0
        
        return {"game_id": cod['id'], "sub_game_id": sub_games[0]['id']}

    def test_create_map(self, admin_headers, test_game_and_subgame):
        """POST /api/games/{game_id}/sub-games/{sub_game_id}/maps - Create new map"""
        game_id = test_game_and_subgame['game_id']
        sub_game_id = test_game_and_subgame['sub_game_id']
        
        unique_name = f"TEST_Map_{uuid.uuid4().hex[:6]}"
        payload = {
            "name": unique_name,
            "image_url": "",
            "game_modes": ["S&D", "Hardpoint"]
        }
        
        response = requests.post(
            f"{BASE_URL}/api/games/{game_id}/sub-games/{sub_game_id}/maps",
            headers=admin_headers,
            json=payload
        )
        assert response.status_code == 200, f"Create map failed: {response.text}"
        
        data = response.json()
        assert data['name'] == unique_name
        assert 'id' in data
        
        # Store for cleanup
        self.__class__.created_map_id = data['id']
        self.__class__.test_game_id = game_id
        self.__class__.test_sub_game_id = sub_game_id
        print(f"Created map: {data['id']}")

    def test_update_map(self, admin_headers):
        """PUT /api/games/{game_id}/sub-games/{sub_game_id}/maps/{map_id} - Update map"""
        map_id = getattr(self.__class__, 'created_map_id', None)
        game_id = getattr(self.__class__, 'test_game_id', None)
        sub_game_id = getattr(self.__class__, 'test_sub_game_id', None)
        
        if not all([map_id, game_id, sub_game_id]):
            pytest.skip("No map created to update")
        
        payload = {
            "name": f"TEST_UpdatedMap_{uuid.uuid4().hex[:4]}",
            "game_modes": ["S&D"]
        }
        
        response = requests.put(
            f"{BASE_URL}/api/games/{game_id}/sub-games/{sub_game_id}/maps/{map_id}",
            headers=admin_headers,
            json=payload
        )
        assert response.status_code == 200, f"Update map failed: {response.text}"

    def test_delete_map(self, admin_headers):
        """DELETE /api/games/{game_id}/sub-games/{sub_game_id}/maps/{map_id} - Delete map"""
        map_id = getattr(self.__class__, 'created_map_id', None)
        game_id = getattr(self.__class__, 'test_game_id', None)
        sub_game_id = getattr(self.__class__, 'test_sub_game_id', None)
        
        if not all([map_id, game_id, sub_game_id]):
            pytest.skip("No map created to delete")
        
        response = requests.delete(
            f"{BASE_URL}/api/games/{game_id}/sub-games/{sub_game_id}/maps/{map_id}",
            headers=admin_headers
        )
        assert response.status_code == 200, f"Delete map failed: {response.text}"
        print(f"Deleted map: {map_id}")


class TestImageUpload(TestSetup):
    """Test image upload endpoint"""

    def test_upload_requires_admin(self):
        """POST /api/upload/image - Should require admin auth"""
        response = requests.post(f"{BASE_URL}/api/upload/image")
        assert response.status_code in [401, 403, 422], f"Should reject unauthenticated: {response.status_code}"

    def test_upload_without_file_fails(self, admin_headers):
        """POST /api/upload/image - Should fail without file"""
        response = requests.post(
            f"{BASE_URL}/api/upload/image",
            headers={"Authorization": admin_headers["Authorization"]}
        )
        # Should return error for missing file
        assert response.status_code in [400, 422], f"Should reject without file: {response.status_code}"


class TestMapVeto(TestSetup):
    """Test Map Veto endpoint"""

    def test_map_veto_endpoint_exists(self):
        """GET /api/matches/{match_id}/map-veto - Endpoint should exist"""
        # Using a fake match ID should return 404 (not 500 or 404 for missing route)
        response = requests.get(f"{BASE_URL}/api/matches/nonexistent-match/map-veto")
        assert response.status_code == 404, f"Expected 404 for non-existent match, got {response.status_code}"
        data = response.json()
        # Should contain German error message
        assert "detail" in data or "error" in data


class TestSMTPEndpoint(TestSetup):
    """Test SMTP test endpoint"""

    def test_smtp_test_requires_admin(self):
        """POST /api/admin/smtp-test - Should require admin auth"""
        response = requests.post(
            f"{BASE_URL}/api/admin/smtp-test",
            json={"test_email": "test@example.com"}
        )
        assert response.status_code in [401, 403], f"Should reject unauthenticated: {response.status_code}"

    def test_smtp_test_with_admin(self, admin_headers):
        """POST /api/admin/smtp-test - Should return detailed results"""
        response = requests.post(
            f"{BASE_URL}/api/admin/smtp-test",
            headers=admin_headers,
            json={"test_email": "test@example.com"}
        )
        assert response.status_code == 200, f"SMTP test failed: {response.text}"
        
        data = response.json()
        # Should have detailed structure
        assert "success" in data
        assert "config_status" in data or "details" in data
        print(f"SMTP test result: success={data.get('success')}, config_status={data.get('config_status')}")


class TestTeamTournamentHistory(TestSetup):
    """Test Team tournament history endpoint"""

    def test_team_tournaments_endpoint(self):
        """GET /api/teams/{id}/tournaments - Should return tournaments"""
        # First get a team
        response = requests.get(f"{BASE_URL}/api/teams")
        if response.status_code == 200:
            teams = response.json()
            if teams and isinstance(teams, list) and len(teams) > 0:
                team_id = teams[0].get('id')
                if team_id:
                    tourn_response = requests.get(f"{BASE_URL}/api/teams/{team_id}/tournaments")
                    assert tourn_response.status_code == 200, f"Team tournaments failed: {tourn_response.text}"
                    data = tourn_response.json()
                    assert isinstance(data, list), "Should return list of tournaments"
                    print(f"Team {team_id} has {len(data)} tournament participations")
                    return
        print("No teams found to test tournament history")


class TestSubGameGetEndpoints(TestSetup):
    """Test sub-game GET endpoints"""

    def test_get_game_sub_games(self):
        """GET /api/games/{game_id}/sub-games - Get sub-games list"""
        # First get a game
        response = requests.get(f"{BASE_URL}/api/games")
        assert response.status_code == 200
        
        games = response.json()
        cod = next((g for g in games if g['name'] == 'Call of Duty'), None)
        assert cod is not None
        
        # Get sub-games
        sg_response = requests.get(f"{BASE_URL}/api/games/{cod['id']}/sub-games")
        assert sg_response.status_code == 200, f"Get sub-games failed: {sg_response.text}"
        
        data = sg_response.json()
        assert "sub_games" in data
        assert len(data["sub_games"]) >= 3

    def test_get_sub_game_maps(self):
        """GET /api/games/{game_id}/sub-games/{sub_game_id}/maps - Get maps list"""
        # First get a game
        response = requests.get(f"{BASE_URL}/api/games")
        assert response.status_code == 200
        
        games = response.json()
        cod = next((g for g in games if g['name'] == 'Call of Duty'), None)
        assert cod is not None
        
        sub_games = cod.get('sub_games', [])
        assert len(sub_games) > 0
        
        # Get maps for first sub-game
        sub_game_id = sub_games[0]['id']
        maps_response = requests.get(f"{BASE_URL}/api/games/{cod['id']}/sub-games/{sub_game_id}/maps")
        assert maps_response.status_code == 200, f"Get maps failed: {maps_response.text}"
        
        data = maps_response.json()
        assert "maps" in data
        print(f"Sub-game {sub_game_id} has {len(data['maps'])} maps")
