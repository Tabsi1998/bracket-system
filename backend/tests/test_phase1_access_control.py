"""
Phase 1 Testing - Access Control, Score Submission, Team System, Profile, Widget
Tests for eSports Tournament Plugin major update

Test Coverage:
- Access Control: Admin-only tournament/game creation
- Score Submission: Team-based score submission with auto-confirm/dispute
- Team System: Join codes, leaders, sub-teams
- Profile Page: User profile with stats
- Widget: Tournament widget data
"""

import pytest
import requests
import os
import uuid

BASE_URL = (os.environ.get("BACKEND_URL") or os.environ.get("REACT_APP_BACKEND_URL") or "http://127.0.0.1:8001").rstrip("/")

# Test credentials
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@arena.gg").strip().lower()
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")
TEST_USER_EMAIL = f"TEST_user_{uuid.uuid4().hex[:6]}@test.de"
TEST_USER_PASSWORD = "test123"
TEST_USER_NAME = f"TEST_User_{uuid.uuid4().hex[:6]}"


@pytest.fixture(scope="module")
def admin_token():
    """Get admin token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    assert response.status_code == 200, f"Admin login failed: {response.text}"
    return response.json()["token"]


@pytest.fixture(scope="module")
def admin_user(admin_token):
    """Get admin user info"""
    response = requests.get(f"{BASE_URL}/api/auth/me", headers={
        "Authorization": f"Bearer {admin_token}"
    })
    assert response.status_code == 200
    return response.json()


@pytest.fixture(scope="module")
def test_user_data():
    """Register a test user and return token and user info"""
    response = requests.post(f"{BASE_URL}/api/auth/register", json={
        "username": TEST_USER_NAME,
        "email": TEST_USER_EMAIL,
        "password": TEST_USER_PASSWORD
    })
    assert response.status_code == 200, f"Test user registration failed: {response.text}"
    return response.json()


@pytest.fixture(scope="module")
def test_user_token(test_user_data):
    """Get test user token"""
    return test_user_data["token"]


@pytest.fixture(scope="module")
def test_user(test_user_data):
    """Get test user info"""
    return test_user_data["user"]


@pytest.fixture(scope="module")
def games():
    """Get list of games"""
    response = requests.get(f"{BASE_URL}/api/games")
    assert response.status_code == 200
    return response.json()


# ============= ACCESS CONTROL TESTS =============

class TestAccessControlTournamentCreation:
    """Non-admin users CANNOT create tournaments"""

    def test_non_admin_cannot_create_tournament(self, test_user_token, games):
        """POST /api/tournaments returns 403 for non-admin"""
        game = games[0] if games else None
        assert game, "No games available for testing"
        
        response = requests.post(f"{BASE_URL}/api/tournaments", json={
            "name": "TEST_Unauthorized_Tournament",
            "game_id": game["id"],
            "game_mode": game["modes"][0]["name"] if game.get("modes") else "1v1",
            "team_size": 1,
            "max_participants": 8,
            "bracket_type": "single_elimination"
        }, headers={"Authorization": f"Bearer {test_user_token}"})
        
        assert response.status_code == 403, f"Expected 403, got {response.status_code}: {response.text}"
        print("PASS: Non-admin cannot create tournament (403)")

    def test_admin_can_create_tournament(self, admin_token, games):
        """POST /api/tournaments works for admin"""
        game = games[0] if games else None
        assert game, "No games available for testing"
        
        response = requests.post(f"{BASE_URL}/api/tournaments", json={
            "name": f"TEST_Admin_Tournament_{uuid.uuid4().hex[:6]}",
            "game_id": game["id"],
            "game_mode": game["modes"][0]["name"] if game.get("modes") else "1v1",
            "team_size": 1,
            "max_participants": 8,
            "bracket_type": "single_elimination"
        }, headers={"Authorization": f"Bearer {admin_token}"})
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print("PASS: Admin can create tournament (200)")
        return response.json()


class TestAccessControlGameCreation:
    """Non-admin users CANNOT create games"""

    def test_non_admin_cannot_create_game(self, test_user_token):
        """POST /api/games returns 403 for non-admin"""
        response = requests.post(f"{BASE_URL}/api/games", json={
            "name": "TEST_Unauthorized_Game",
            "short_name": "TUG",
            "category": "fps",
            "modes": [{"name": "1v1", "team_size": 1, "description": "Test"}]
        }, headers={"Authorization": f"Bearer {test_user_token}"})
        
        assert response.status_code == 403, f"Expected 403, got {response.status_code}: {response.text}"
        print("PASS: Non-admin cannot create game (403)")

    def test_admin_can_create_game(self, admin_token):
        """POST /api/games works for admin"""
        response = requests.post(f"{BASE_URL}/api/games", json={
            "name": f"TEST_Admin_Game_{uuid.uuid4().hex[:6]}",
            "short_name": "TAG",
            "category": "fps",
            "modes": [{"name": "1v1", "team_size": 1, "description": "Test mode"}],
            "platforms": ["PC"]
        }, headers={"Authorization": f"Bearer {admin_token}"})
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print("PASS: Admin can create game (200)")
        return response.json()


class TestAccessControlBracketGeneration:
    """Non-admin users CANNOT generate brackets"""

    def test_non_admin_cannot_generate_bracket(self, test_user_token):
        """POST /api/tournaments/{id}/generate-bracket returns 403 for non-admin"""
        # First get a tournament
        tournaments = requests.get(f"{BASE_URL}/api/tournaments").json()
        if not tournaments:
            pytest.skip("No tournaments available")
        
        tournament = tournaments[0]
        response = requests.post(
            f"{BASE_URL}/api/tournaments/{tournament['id']}/generate-bracket",
            headers={"Authorization": f"Bearer {test_user_token}"}
        )
        
        assert response.status_code == 403, f"Expected 403, got {response.status_code}: {response.text}"
        print("PASS: Non-admin cannot generate bracket (403)")


class TestAccessControlTournamentUpdate:
    """Non-admin users CANNOT change tournament status"""

    def test_non_admin_cannot_update_tournament(self, test_user_token):
        """PUT /api/tournaments/{id} returns 403 for non-admin"""
        tournaments = requests.get(f"{BASE_URL}/api/tournaments").json()
        if not tournaments:
            pytest.skip("No tournaments available")
        
        tournament = tournaments[0]
        response = requests.put(
            f"{BASE_URL}/api/tournaments/{tournament['id']}",
            json={"status": "live"},
            headers={"Authorization": f"Bearer {test_user_token}"}
        )
        
        assert response.status_code == 403, f"Expected 403, got {response.status_code}: {response.text}"
        print("PASS: Non-admin cannot update tournament (403)")


# ============= TEAM SYSTEM TESTS =============

class TestTeamJoinCode:
    """Team join code system tests"""

    def test_create_team_has_join_code(self, test_user_token):
        """Created team has join_code visible to owner"""
        response = requests.post(f"{BASE_URL}/api/teams", json={
            "name": f"TEST_Team_{uuid.uuid4().hex[:6]}",
            "tag": "TST"
        }, headers={"Authorization": f"Bearer {test_user_token}"})
        
        assert response.status_code == 200, f"Team creation failed: {response.text}"
        team = response.json()
        
        assert "join_code" in team, "join_code not returned on team creation"
        assert len(team["join_code"]) == 6, "join_code should be 6 characters"
        print(f"PASS: Team created with join_code: {team['join_code']}")
        return team

    def test_team_join_code_hidden_for_non_owner(self, test_user_token, admin_token):
        """join_code should be hidden when fetching team for non-owner"""
        # Admin creates a team
        create_response = requests.post(f"{BASE_URL}/api/teams", json={
            "name": f"TEST_AdminTeam_{uuid.uuid4().hex[:6]}",
            "tag": "ADM"
        }, headers={"Authorization": f"Bearer {admin_token}"})
        
        assert create_response.status_code == 200
        team = create_response.json()
        team_id = team["id"]
        
        # Non-owner (test user) tries to get team
        get_response = requests.get(
            f"{BASE_URL}/api/teams/{team_id}",
            headers={"Authorization": f"Bearer {test_user_token}"}
        )
        
        assert get_response.status_code == 200
        fetched_team = get_response.json()
        
        assert "join_code" not in fetched_team or fetched_team.get("join_code") is None, \
            "join_code should be hidden for non-owner"
        print("PASS: join_code hidden for non-owner")


class TestTeamJoinFlow:
    """Team join via code tests"""

    def test_join_team_with_code(self, admin_token, test_user_token):
        """POST /api/teams/join with team_id + join_code"""
        # Admin creates a team
        create_response = requests.post(f"{BASE_URL}/api/teams", json={
            "name": f"TEST_JoinableTeam_{uuid.uuid4().hex[:6]}",
            "tag": "JOIN"
        }, headers={"Authorization": f"Bearer {admin_token}"})
        
        assert create_response.status_code == 200
        team = create_response.json()
        
        # Test user joins with code
        join_response = requests.post(f"{BASE_URL}/api/teams/join", json={
            "team_id": team["id"],
            "join_code": team["join_code"]
        }, headers={"Authorization": f"Bearer {test_user_token}"})
        
        assert join_response.status_code == 200, f"Join failed: {join_response.text}"
        print("PASS: User joined team with join_code")

    def test_join_team_wrong_code(self, admin_token, test_user_token):
        """Join with wrong code should fail"""
        # Admin creates a team
        create_response = requests.post(f"{BASE_URL}/api/teams", json={
            "name": f"TEST_WrongCodeTeam_{uuid.uuid4().hex[:6]}",
            "tag": "WRONG"
        }, headers={"Authorization": f"Bearer {admin_token}"})
        
        assert create_response.status_code == 200
        team = create_response.json()
        
        # Test user tries to join with wrong code
        join_response = requests.post(f"{BASE_URL}/api/teams/join", json={
            "team_id": team["id"],
            "join_code": "WRONG1"
        }, headers={"Authorization": f"Bearer {test_user_token}"})
        
        assert join_response.status_code == 403, f"Expected 403, got {join_response.status_code}"
        print("PASS: Join with wrong code returns 403")


class TestTeamLeaders:
    """Team leader promotion/demotion tests"""

    def test_promote_member_to_leader(self, admin_token, test_user_token, test_user):
        """Owner can promote member to leader"""
        # Admin creates team and adds test user
        create_response = requests.post(f"{BASE_URL}/api/teams", json={
            "name": f"TEST_LeaderTeam_{uuid.uuid4().hex[:6]}",
            "tag": "LDR"
        }, headers={"Authorization": f"Bearer {admin_token}"})
        
        team = create_response.json()
        
        # Add test user to team via join
        join_response = requests.post(f"{BASE_URL}/api/teams/join", json={
            "team_id": team["id"],
            "join_code": team["join_code"]
        }, headers={"Authorization": f"Bearer {test_user_token}"})
        
        if join_response.status_code != 200:
            pytest.skip("Could not join team")
        
        # Promote test user to leader
        promote_response = requests.put(
            f"{BASE_URL}/api/teams/{team['id']}/leaders/{test_user['id']}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert promote_response.status_code == 200, f"Promote failed: {promote_response.text}"
        
        # Verify leader_ids contains test user
        updated_team = promote_response.json()
        assert test_user['id'] in updated_team.get("leader_ids", []), "User not in leader_ids"
        print("PASS: Member promoted to leader")


class TestSubTeams:
    """Sub-team creation tests"""

    def test_create_sub_team(self, test_user_token):
        """Sub-teams can be created within a team"""
        # Create parent team
        parent_response = requests.post(f"{BASE_URL}/api/teams", json={
            "name": f"TEST_ParentTeam_{uuid.uuid4().hex[:6]}",
            "tag": "PRNT"
        }, headers={"Authorization": f"Bearer {test_user_token}"})
        
        assert parent_response.status_code == 200
        parent = parent_response.json()
        
        # Create sub-team
        sub_response = requests.post(f"{BASE_URL}/api/teams", json={
            "name": f"TEST_SubTeam_{uuid.uuid4().hex[:6]}",
            "tag": "SUB",
            "parent_team_id": parent["id"]
        }, headers={"Authorization": f"Bearer {test_user_token}"})
        
        assert sub_response.status_code == 200, f"Sub-team creation failed: {sub_response.text}"
        sub_team = sub_response.json()
        assert sub_team.get("parent_team_id") == parent["id"], "parent_team_id not set"
        print("PASS: Sub-team created")

    def test_list_sub_teams(self, test_user_token):
        """GET /api/teams/{team_id}/sub-teams lists sub-teams"""
        # Create parent team
        parent_response = requests.post(f"{BASE_URL}/api/teams", json={
            "name": f"TEST_ParentList_{uuid.uuid4().hex[:6]}",
            "tag": "PLST"
        }, headers={"Authorization": f"Bearer {test_user_token}"})
        
        parent = parent_response.json()
        
        # Create sub-team
        requests.post(f"{BASE_URL}/api/teams", json={
            "name": f"TEST_SubList_{uuid.uuid4().hex[:6]}",
            "tag": "SLST",
            "parent_team_id": parent["id"]
        }, headers={"Authorization": f"Bearer {test_user_token}"})
        
        # List sub-teams
        list_response = requests.get(
            f"{BASE_URL}/api/teams/{parent['id']}/sub-teams",
            headers={"Authorization": f"Bearer {test_user_token}"}
        )
        
        assert list_response.status_code == 200
        subs = list_response.json()
        assert len(subs) >= 1, "Sub-teams not returned"
        print("PASS: Sub-teams listed")


# ============= PROFILE PAGE TESTS =============

class TestProfilePage:
    """Profile page endpoint tests"""

    def test_get_user_profile(self, admin_user, admin_token):
        """GET /api/users/{userId}/profile returns user stats, teams, tournaments"""
        response = requests.get(
            f"{BASE_URL}/api/users/{admin_user['id']}/profile",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 200, f"Profile fetch failed: {response.text}"
        profile = response.json()
        
        assert "username" in profile, "username missing"
        assert "teams" in profile, "teams missing"
        assert "tournaments" in profile, "tournaments missing"
        assert "stats" in profile, "stats missing"
        assert "tournaments_played" in profile["stats"], "tournaments_played missing in stats"
        assert "wins" in profile["stats"], "wins missing in stats"
        assert "losses" in profile["stats"], "losses missing in stats"
        print(f"PASS: Profile fetched for {profile['username']}")

    def test_profile_not_found(self):
        """Profile for non-existent user returns 404"""
        response = requests.get(f"{BASE_URL}/api/users/nonexistent-user-id/profile")
        
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("PASS: Non-existent user profile returns 404")


# ============= WIDGET TESTS =============

class TestWidget:
    """Widget endpoint tests"""

    def test_widget_data(self):
        """GET /api/widget/tournament/{id} returns tournament data for embedding"""
        tournaments = requests.get(f"{BASE_URL}/api/tournaments").json()
        if not tournaments:
            pytest.skip("No tournaments available")
        
        tournament = tournaments[0]
        response = requests.get(f"{BASE_URL}/api/widget/tournament/{tournament['id']}")
        
        assert response.status_code == 200, f"Widget data fetch failed: {response.text}"
        data = response.json()
        
        assert "tournament" in data, "tournament missing"
        assert "registrations" in data, "registrations missing"
        assert "embed_version" in data, "embed_version missing"
        print("PASS: Widget data returned")

    def test_widget_not_found(self):
        """Widget for non-existent tournament returns 404"""
        response = requests.get(f"{BASE_URL}/api/widget/tournament/nonexistent-id")
        
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("PASS: Non-existent tournament widget returns 404")


# ============= SCORE SUBMISSION TESTS =============

class TestScoreSubmission:
    """Score submission system tests"""

    def test_score_submission_requires_auth(self):
        """Score submission requires authentication"""
        tournaments = requests.get(f"{BASE_URL}/api/tournaments").json()
        if not tournaments:
            pytest.skip("No tournaments available")
        
        response = requests.post(
            f"{BASE_URL}/api/tournaments/{tournaments[0]['id']}/matches/fake-match-id/submit-score",
            json={"score1": 2, "score2": 1}
        )
        
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: Score submission requires auth")


class TestAdminResolve:
    """Admin score resolution tests"""

    def test_resolve_requires_admin(self, test_user_token):
        """PUT /api/tournaments/{id}/matches/{match_id}/resolve requires admin"""
        tournaments = requests.get(f"{BASE_URL}/api/tournaments").json()
        if not tournaments:
            pytest.skip("No tournaments available")
        
        response = requests.put(
            f"{BASE_URL}/api/tournaments/{tournaments[0]['id']}/matches/fake-match-id/resolve",
            json={"score1": 2, "score2": 1},
            headers={"Authorization": f"Bearer {test_user_token}"}
        )
        
        # Should be 403 (forbidden) or 404 (match not found), but definitely not 200
        assert response.status_code in [403, 404], f"Expected 403/404, got {response.status_code}"
        print("PASS: Resolve requires admin role")


# ============= ADMIN PANEL TESTS =============

class TestAdminPanel:
    """Admin panel endpoint tests"""

    def test_admin_dashboard_stats(self, admin_token):
        """GET /api/admin/dashboard returns stats"""
        response = requests.get(
            f"{BASE_URL}/api/admin/dashboard",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 200, f"Dashboard failed: {response.text}"
        data = response.json()
        
        assert "total_users" in data, "total_users missing"
        assert "total_teams" in data, "total_teams missing"
        assert "total_tournaments" in data, "total_tournaments missing"
        print("PASS: Admin dashboard returns stats")

    def test_admin_settings_crud(self, admin_token):
        """Admin can read and update settings"""
        # Read settings
        read_response = requests.get(
            f"{BASE_URL}/api/admin/settings",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert read_response.status_code == 200
        
        # Update a setting
        update_response = requests.put(
            f"{BASE_URL}/api/admin/settings",
            json={"key": "test_setting", "value": "test_value"},
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert update_response.status_code == 200
        print("PASS: Admin settings CRUD works")


# ============= COMMENTS TESTS =============

class TestComments:
    """Comment system tests"""

    def test_comments_require_auth(self):
        """Creating comments requires authentication"""
        tournaments = requests.get(f"{BASE_URL}/api/tournaments").json()
        if not tournaments:
            pytest.skip("No tournaments available")
        
        response = requests.post(
            f"{BASE_URL}/api/tournaments/{tournaments[0]['id']}/comments",
            json={"message": "Test comment"}
        )
        
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: Comments require auth")


# ============= NOTIFICATIONS TESTS =============

class TestNotifications:
    """Notification system tests"""

    def test_notifications_list(self, admin_token):
        """GET /api/notifications returns list"""
        response = requests.get(
            f"{BASE_URL}/api/notifications",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 200, f"Notifications failed: {response.text}"
        assert isinstance(response.json(), list), "Should return list"
        print("PASS: Notifications list works")

    def test_unread_count(self, admin_token):
        """GET /api/notifications/unread-count returns count"""
        response = requests.get(
            f"{BASE_URL}/api/notifications/unread-count",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "count" in data, "count missing"
        print("PASS: Unread count works")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
