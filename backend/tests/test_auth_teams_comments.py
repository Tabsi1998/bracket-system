"""
Backend API Tests for eSports Tournament System - Phase 1
Features: Auth (JWT), Teams, Comments, Notifications, Admin Panel

Credentials:
- Admin: admin@arena.gg / admin123
- Test: test@test.de / test123
"""
import pytest
import requests
import os
import uuid
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestAuthEndpoints:
    """Authentication endpoint tests - /api/auth/*"""
    
    def test_login_admin_success(self):
        """Test admin login with valid credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@arena.gg",
            "password": "admin123"
        })
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert "user" in data
        assert data["user"]["email"] == "admin@arena.gg"
        assert data["user"]["role"] == "admin"
        assert data["user"]["username"] == "admin"

    def test_login_invalid_credentials(self):
        """Test login with wrong credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "wrong@email.de",
            "password": "wrongpass"
        })
        assert response.status_code == 401
        data = response.json()
        assert "detail" in data

    def test_register_new_user(self):
        """Test user registration with new credentials"""
        unique_id = str(uuid.uuid4())[:8]
        response = requests.post(f"{BASE_URL}/api/auth/register", json={
            "username": f"TEST_user_{unique_id}",
            "email": f"test_{unique_id}@test.de",
            "password": "test123456"
        })
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert "user" in data
        assert data["user"]["role"] == "user"
        assert f"TEST_user_{unique_id}" == data["user"]["username"]

    def test_register_duplicate_email(self):
        """Test registration with already registered email"""
        response = requests.post(f"{BASE_URL}/api/auth/register", json={
            "username": "newadmin",
            "email": "admin@arena.gg",
            "password": "test123"
        })
        assert response.status_code == 400
        assert "registriert" in response.json().get("detail", "").lower() or "email" in response.json().get("detail", "").lower()

    def test_auth_me_with_token(self):
        """Test /api/auth/me with valid token"""
        # First login to get token
        login_res = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@arena.gg",
            "password": "admin123"
        })
        token = login_res.json()["token"]
        
        # Then call /me endpoint
        response = requests.get(f"{BASE_URL}/api/auth/me", headers={
            "Authorization": f"Bearer {token}"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "admin@arena.gg"
        assert "password_hash" not in data

    def test_auth_me_without_token(self):
        """Test /api/auth/me without token returns 401"""
        response = requests.get(f"{BASE_URL}/api/auth/me")
        assert response.status_code == 401


class TestTeamEndpoints:
    """Team management endpoint tests - /api/teams/*"""

    @pytest.fixture
    def auth_headers(self):
        """Get auth headers with admin token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@arena.gg",
            "password": "admin123"
        })
        token = response.json()["token"]
        return {"Authorization": f"Bearer {token}"}

    def test_list_teams_requires_auth(self):
        """Test GET /api/teams requires authentication"""
        response = requests.get(f"{BASE_URL}/api/teams")
        assert response.status_code == 401

    def test_create_team(self, auth_headers):
        """Test POST /api/teams creates a team"""
        unique_id = str(uuid.uuid4())[:8]
        response = requests.post(f"{BASE_URL}/api/teams", json={
            "name": f"TEST_Team_{unique_id}",
            "tag": "TEST"
        }, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == f"TEST_Team_{unique_id}"
        assert data["tag"] == "TEST"
        assert "owner_id" in data
        assert "members" in data
        # Store team ID for cleanup
        return data["id"]

    def test_create_team_and_verify_in_list(self, auth_headers):
        """Test create team then verify it appears in list"""
        unique_id = str(uuid.uuid4())[:8]
        create_res = requests.post(f"{BASE_URL}/api/teams", json={
            "name": f"TEST_VerifyTeam_{unique_id}",
            "tag": "VT"
        }, headers=auth_headers)
        assert create_res.status_code == 200
        team_id = create_res.json()["id"]
        
        # Verify in list
        list_res = requests.get(f"{BASE_URL}/api/teams", headers=auth_headers)
        assert list_res.status_code == 200
        teams = list_res.json()
        team_ids = [t["id"] for t in teams]
        assert team_id in team_ids

    def test_get_team_by_id(self, auth_headers):
        """Test GET /api/teams/{team_id}"""
        # First create a team
        unique_id = str(uuid.uuid4())[:8]
        create_res = requests.post(f"{BASE_URL}/api/teams", json={
            "name": f"TEST_GetTeam_{unique_id}",
            "tag": "GT"
        }, headers=auth_headers)
        team_id = create_res.json()["id"]
        
        # Get the team
        response = requests.get(f"{BASE_URL}/api/teams/{team_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == team_id
        assert data["name"] == f"TEST_GetTeam_{unique_id}"

    def test_delete_team(self, auth_headers):
        """Test DELETE /api/teams/{team_id}"""
        unique_id = str(uuid.uuid4())[:8]
        create_res = requests.post(f"{BASE_URL}/api/teams", json={
            "name": f"TEST_DeleteTeam_{unique_id}",
            "tag": "DT"
        }, headers=auth_headers)
        team_id = create_res.json()["id"]
        
        # Delete the team
        del_res = requests.delete(f"{BASE_URL}/api/teams/{team_id}", headers=auth_headers)
        assert del_res.status_code == 200
        
        # Verify deleted
        get_res = requests.get(f"{BASE_URL}/api/teams/{team_id}")
        assert get_res.status_code == 404


class TestCommentEndpoints:
    """Comment endpoint tests - /api/tournaments/{id}/comments"""

    @pytest.fixture
    def auth_headers(self):
        """Get auth headers with admin token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@arena.gg",
            "password": "admin123"
        })
        token = response.json()["token"]
        return {"Authorization": f"Bearer {token}"}

    @pytest.fixture
    def tournament_id(self, auth_headers):
        """Get a tournament ID for testing comments"""
        # First get games
        games_res = requests.get(f"{BASE_URL}/api/games")
        game_id = games_res.json()[0]["id"]
        
        # Create a tournament
        unique_id = str(uuid.uuid4())[:8]
        create_res = requests.post(f"{BASE_URL}/api/tournaments", json={
            "name": f"TEST_CommentTournament_{unique_id}",
            "game_id": game_id,
            "max_participants": 8
        })
        return create_res.json()["id"]

    def test_list_comments_empty(self, tournament_id):
        """Test GET /api/tournaments/{id}/comments returns empty list"""
        response = requests.get(f"{BASE_URL}/api/tournaments/{tournament_id}/comments")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_create_comment_requires_auth(self, tournament_id):
        """Test POST /api/tournaments/{id}/comments requires auth"""
        response = requests.post(f"{BASE_URL}/api/tournaments/{tournament_id}/comments", json={
            "message": "Test comment"
        })
        assert response.status_code == 401

    def test_create_comment(self, tournament_id, auth_headers):
        """Test POST /api/tournaments/{id}/comments creates a comment"""
        response = requests.post(f"{BASE_URL}/api/tournaments/{tournament_id}/comments", json={
            "message": "TEST_Comment - Das ist ein Testkommentar!"
        }, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "TEST_Comment - Das ist ein Testkommentar!"
        assert data["author_name"] == "admin"
        assert "created_at" in data

    def test_create_comment_and_verify_in_list(self, tournament_id, auth_headers):
        """Test create comment then verify it appears in list"""
        unique_id = str(uuid.uuid4())[:8]
        create_res = requests.post(f"{BASE_URL}/api/tournaments/{tournament_id}/comments", json={
            "message": f"TEST_Comment_{unique_id}"
        }, headers=auth_headers)
        comment_id = create_res.json()["id"]
        
        # Verify in list
        list_res = requests.get(f"{BASE_URL}/api/tournaments/{tournament_id}/comments")
        assert list_res.status_code == 200
        comments = list_res.json()
        comment_ids = [c["id"] for c in comments]
        assert comment_id in comment_ids


class TestNotificationEndpoints:
    """Notification endpoint tests - /api/notifications/*"""

    @pytest.fixture
    def auth_headers(self):
        """Get auth headers with admin token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@arena.gg",
            "password": "admin123"
        })
        token = response.json()["token"]
        return {"Authorization": f"Bearer {token}"}

    def test_list_notifications_requires_auth(self):
        """Test GET /api/notifications requires auth"""
        response = requests.get(f"{BASE_URL}/api/notifications")
        assert response.status_code == 401

    def test_list_notifications(self, auth_headers):
        """Test GET /api/notifications returns list"""
        response = requests.get(f"{BASE_URL}/api/notifications", headers=auth_headers)
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_unread_count(self, auth_headers):
        """Test GET /api/notifications/unread-count"""
        response = requests.get(f"{BASE_URL}/api/notifications/unread-count", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "count" in data
        assert isinstance(data["count"], int)

    def test_mark_all_read(self, auth_headers):
        """Test PUT /api/notifications/read-all"""
        response = requests.put(f"{BASE_URL}/api/notifications/read-all", headers=auth_headers)
        assert response.status_code == 200


class TestAdminEndpoints:
    """Admin panel endpoint tests - /api/admin/*"""

    @pytest.fixture
    def admin_headers(self):
        """Get auth headers with admin token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@arena.gg",
            "password": "admin123"
        })
        token = response.json()["token"]
        return {"Authorization": f"Bearer {token}"}

    @pytest.fixture
    def user_headers(self):
        """Get auth headers with regular user token"""
        unique_id = str(uuid.uuid4())[:8]
        response = requests.post(f"{BASE_URL}/api/auth/register", json={
            "username": f"TEST_regular_{unique_id}",
            "email": f"regular_{unique_id}@test.de",
            "password": "test123456"
        })
        token = response.json()["token"]
        return {"Authorization": f"Bearer {token}"}

    def test_admin_dashboard_requires_auth(self):
        """Test GET /api/admin/dashboard requires auth"""
        response = requests.get(f"{BASE_URL}/api/admin/dashboard")
        assert response.status_code == 401

    def test_admin_dashboard_requires_admin_role(self, user_headers):
        """Test GET /api/admin/dashboard requires admin role"""
        response = requests.get(f"{BASE_URL}/api/admin/dashboard", headers=user_headers)
        assert response.status_code == 403

    def test_admin_dashboard(self, admin_headers):
        """Test GET /api/admin/dashboard returns stats"""
        response = requests.get(f"{BASE_URL}/api/admin/dashboard", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert "total_users" in data
        assert "total_teams" in data
        assert "total_tournaments" in data
        assert "total_registrations" in data
        assert "live_tournaments" in data
        assert "total_payments" in data

    def test_admin_users_list(self, admin_headers):
        """Test GET /api/admin/users returns user list"""
        response = requests.get(f"{BASE_URL}/api/admin/users", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        # Verify admin user is in list
        emails = [u["email"] for u in data]
        assert "admin@arena.gg" in emails
        # Verify password_hash is NOT exposed
        for user in data:
            assert "password_hash" not in user

    def test_admin_settings_list(self, admin_headers):
        """Test GET /api/admin/settings"""
        response = requests.get(f"{BASE_URL}/api/admin/settings", headers=admin_headers)
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_admin_settings_update(self, admin_headers):
        """Test PUT /api/admin/settings updates a setting"""
        unique_val = f"test_value_{uuid.uuid4().hex[:8]}"
        response = requests.put(f"{BASE_URL}/api/admin/settings", json={
            "key": "test_setting",
            "value": unique_val
        }, headers=admin_headers)
        assert response.status_code == 200
        
        # Verify setting was saved
        get_res = requests.get(f"{BASE_URL}/api/admin/settings", headers=admin_headers)
        settings = get_res.json()
        test_setting = next((s for s in settings if s["key"] == "test_setting"), None)
        assert test_setting is not None
        assert test_setting["value"] == unique_val


class TestProtectedRoutes:
    """Test that protected routes require authentication"""

    def test_teams_protected(self):
        """Test /api/teams requires auth"""
        response = requests.get(f"{BASE_URL}/api/teams")
        assert response.status_code == 401

    def test_notifications_protected(self):
        """Test /api/notifications requires auth"""
        response = requests.get(f"{BASE_URL}/api/notifications")
        assert response.status_code == 401

    def test_admin_dashboard_protected(self):
        """Test /api/admin/dashboard requires auth"""
        response = requests.get(f"{BASE_URL}/api/admin/dashboard")
        assert response.status_code == 401

    def test_admin_users_protected(self):
        """Test /api/admin/users requires auth"""
        response = requests.get(f"{BASE_URL}/api/admin/users")
        assert response.status_code == 401


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
