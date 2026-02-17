#!/usr/bin/env python3
"""
Specific tests for eSports Tournament System improvements:
- SMTP settings and help
- Demo data with extended rules/descriptions  
- Auto-scheduling system with default times
- Match hub scheduling features
- New tournament creation fields
"""

import requests
import sys
import json
import os
from datetime import datetime

class eSportsSpecificTester:
    def __init__(self, base_url=None):
        resolved_base = base_url or os.environ.get("REACT_APP_BACKEND_URL") or "http://127.0.0.1:8001"
        self.base_url = resolved_base.rstrip("/")
        if self.base_url.endswith("/api"):
            self.base_url = self.base_url[:-4]
        self.tests_run = 0
        self.tests_passed = 0
        self.failed_tests = []
        self.session = requests.Session()
        
        # Test credentials from review request
        self.admin_email = "admin@arena.gg"
        self.admin_password = "admin123"
        self.demo_admin_email = "demo.admin@arena.gg"
        self.demo_admin_password = "demo123"
        self.demo_user_email = "demo.alpha1@arena.gg"
        self.demo_user_password = "demo123"
        
        self._admin_headers = None
        self._demo_admin_headers = None
        self._demo_user_headers = None

    def get_admin_headers(self):
        if self._admin_headers:
            return self._admin_headers
        response = self.session.post(f"{self.base_url}/api/auth/login", json={
            "email": self.admin_email,
            "password": self.admin_password
        })
        if response.status_code != 200:
            raise RuntimeError(f"Admin login failed ({response.status_code}): {response.text[:200]}")
        token = response.json().get("token")
        self._admin_headers = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
        return self._admin_headers

    def get_demo_admin_headers(self):
        if self._demo_admin_headers:
            return self._demo_admin_headers
        response = self.session.post(f"{self.base_url}/api/auth/login", json={
            "email": self.demo_admin_email,
            "password": self.demo_admin_password
        })
        if response.status_code != 200:
            raise RuntimeError(f"Demo admin login failed ({response.status_code}): {response.text[:200]}")
        token = response.json().get("token")
        self._demo_admin_headers = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
        return self._demo_admin_headers

    def get_demo_user_headers(self):
        if self._demo_user_headers:
            return self._demo_user_headers
        response = self.session.post(f"{self.base_url}/api/auth/login", json={
            "email": self.demo_user_email,
            "password": self.demo_user_password
        })
        if response.status_code != 200:
            raise RuntimeError(f"Demo user login failed ({response.status_code}): {response.text[:200]}")
        token = response.json().get("token")
        self._demo_user_headers = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
        return self._demo_user_headers

    def run_test(self, name, method, endpoint, expected_status, data=None, headers=None):
        """Run a single API test"""
        url = f"{self.base_url}/api/{endpoint}"
        if not headers:
            headers = {'Content-Type': 'application/json'}

        self.tests_run += 1
        print(f"\n-> Testing {name}...")
        print(f"   URL: {url}")
        
        try:
            if method == 'GET':
                response = self.session.get(url, headers=headers)
            elif method == 'POST':
                response = self.session.post(url, json=data, headers=headers)
            elif method == 'PUT':
                response = self.session.put(url, json=data, headers=headers)
            elif method == 'DELETE':
                response = self.session.delete(url, headers=headers)

            print(f"   Status: {response.status_code}")
            success = response.status_code == expected_status
            
            if success:
                self.tests_passed += 1
                print(f"[PASS] {name}")
                try:
                    response_data = response.json() if response.content else {}
                    return True, response_data
                except:
                    return True, {}
            else:
                self.failed_tests.append({
                    'test': name,
                    'expected_status': expected_status,
                    'actual_status': response.status_code,
                    'response': response.text[:200] if response.text else ''
                })
                print(f"[FAIL] {name} - Expected {expected_status}, got {response.status_code}")
                try:
                    error_data = response.json()
                    print(f"   Error: {error_data}")
                except:
                    print(f"   Error response: {response.text[:100]}")
                return False, {}

        except Exception as e:
            self.failed_tests.append({
                'test': name,
                'error': str(e)
            })
            print(f"[FAIL] {name} - Error: {str(e)}")
            return False, {}

    def test_login_credentials(self):
        """Test all login credentials from review request"""
        print("\n" + "="*60)
        print("TESTING LOGIN CREDENTIALS")
        print("="*60)
        
        # Test admin@arena.gg / admin123
        success, _ = self.run_test(
            "Login admin@arena.gg",
            "POST",
            "auth/login",
            200,
            {"email": self.admin_email, "password": self.admin_password}
        )
        
        # Test demo.admin@arena.gg / demo123
        success, _ = self.run_test(
            "Login demo.admin@arena.gg",
            "POST", 
            "auth/login",
            200,
            {"email": self.demo_admin_email, "password": self.demo_admin_password}
        )
        
        # Test demo.alpha1@arena.gg / demo123
        success, _ = self.run_test(
            "Login demo.alpha1@arena.gg",
            "POST",
            "auth/login", 
            200,
            {"email": self.demo_user_email, "password": self.demo_user_password}
        )

    def test_demo_tournaments(self):
        """Test that we have 13+ demo tournaments with extended rules/descriptions"""
        print("\n" + "="*60)
        print("TESTING DEMO TOURNAMENTS")
        print("="*60)
        
        success, tournaments = self.run_test(
            "GET /api/tournaments (13+ tournaments)",
            "GET",
            "tournaments",
            200
        )
        
        if success and tournaments:
            print(f"   Found {len(tournaments)} tournaments")
            if len(tournaments) >= 13:
                print("[PASS] At least 13 tournaments found")
                
                # Check for extended rules and descriptions
                tournaments_with_rules = 0
                tournaments_with_descriptions = 0
                
                for tournament in tournaments[:5]:  # Check first 5 tournaments
                    if tournament.get('rules') and len(tournament['rules']) > 50:
                        tournaments_with_rules += 1
                    if tournament.get('description') and len(tournament['description']) > 50:
                        tournaments_with_descriptions += 1
                
                print(f"   Tournaments with extended rules: {tournaments_with_rules}/5")
                print(f"   Tournaments with extended descriptions: {tournaments_with_descriptions}/5")
                
                if tournaments_with_rules >= 3:
                    print("[PASS] Found tournaments with extended rules")
                    self.tests_passed += 1
                else:
                    print("[FAIL] Not enough tournaments with extended rules")
                    self.failed_tests.append({'test': 'Extended rules check', 'error': 'Insufficient extended rules'})
                self.tests_run += 1
                
                if tournaments_with_descriptions >= 3:
                    print("[PASS] Found tournaments with extended descriptions")
                    self.tests_passed += 1
                else:
                    print("[FAIL] Not enough tournaments with extended descriptions")
                    self.failed_tests.append({'test': 'Extended descriptions check', 'error': 'Insufficient extended descriptions'})
                self.tests_run += 1
                
            else:
                print(f"[FAIL] Expected at least 13 tournaments, found {len(tournaments)}")
                self.failed_tests.append({'test': '13+ tournaments', 'error': f'Only {len(tournaments)} found'})
                self.tests_run += 1
        
        return tournaments if success else []

    def test_scheduling_apis(self, tournaments):
        """Test new scheduling-related APIs"""
        print("\n" + "="*60)
        print("TESTING SCHEDULING APIs")
        print("="*60)
        
        if not tournaments:
            print("[WARN] No tournaments available for scheduling tests")
            return
        
        # Find a tournament to test with
        test_tournament = tournaments[0] if tournaments else None
        if not test_tournament:
            print("[FAIL] No tournament available for scheduling tests")
            return
            
        tournament_id = test_tournament['id']
        
        # Test scheduling-status API
        success, status_data = self.run_test(
            f"GET /api/tournaments/{tournament_id}/scheduling-status",
            "GET",
            f"tournaments/{tournament_id}/scheduling-status",
            200,
            headers=self.get_admin_headers()
        )
        
        if success and status_data:
            print(f"   Scheduling status keys: {list(status_data.keys())}")
        
        # Test auto-schedule API
        success, schedule_result = self.run_test(
            f"POST /api/tournaments/{tournament_id}/auto-schedule-unscheduled",
            "POST",
            f"tournaments/{tournament_id}/auto-schedule-unscheduled",
            200,
            headers=self.get_admin_headers()
        )
        
        if success and schedule_result:
            print(f"   Auto-schedule result: {schedule_result}")

    def test_tournament_creation_fields(self):
        """Test new tournament creation fields"""
        print("\n" + "="*60)
        print("TESTING NEW TOURNAMENT CREATION FIELDS")
        print("="*60)
        
        # Get a game to use for tournament creation
        success, games = self.run_test("GET /api/games", "GET", "games", 200)
        if not success or not games:
            print("[FAIL] No games available for tournament creation test")
            return
            
        test_game = games[0]
        
        # Create tournament with new scheduling fields
        tournament_data = {
            "name": "Test Auto-Schedule Tournament",
            "game_id": test_game['id'],
            "game_name": test_game['name'],
            "game_mode": test_game.get('modes', [{'name': '1v1'}])[0]['name'],
            "team_size": 2,
            "max_participants": 8,
            "bracket_type": "league",
            "best_of": 1,
            "entry_fee": 0.0,
            "currency": "usd",
            "prize_pool": "Test Prize",
            "description": "Test tournament with auto-scheduling",
            "rules": "Test rules for auto-scheduling",
            "start_date": "2024-12-31T12:00:00",
            # New scheduling fields
            "default_match_day": "wednesday",
            "default_match_hour": 19,
            "auto_schedule_on_window_end": True,
            "matchday_interval_days": 7,
            "matchday_window_days": 7
        }
        
        success, tournament = self.run_test(
            "POST /api/tournaments (with scheduling fields)",
            "POST",
            "tournaments",
            200,
            tournament_data,
            headers=self.get_admin_headers()
        )
        
        if success and tournament:
            print(f"   Created tournament with ID: {tournament['id']}")
            
            # Verify the new fields are present
            required_fields = ['default_match_day', 'default_match_hour', 'auto_schedule_on_window_end']
            missing_fields = []
            
            for field in required_fields:
                if field not in tournament:
                    missing_fields.append(field)
                else:
                    print(f"   {field}: {tournament[field]}")
            
            if missing_fields:
                print(f"[FAIL] Missing fields: {missing_fields}")
                self.failed_tests.append({'test': 'New tournament fields', 'error': f'Missing: {missing_fields}'})
                self.tests_run += 1
            else:
                print("[PASS] All new tournament fields present")
                self.tests_passed += 1
                self.tests_run += 1
            
            # Clean up
            self.run_test(
                f"DELETE /api/tournaments/{tournament['id']}",
                "DELETE",
                f"tournaments/{tournament['id']}",
                200,
                headers=self.get_admin_headers()
            )

    def test_match_hub_scheduling(self, tournaments):
        """Test match hub scheduling features"""
        print("\n" + "="*60)
        print("TESTING MATCH HUB SCHEDULING")
        print("="*60)
        
        if not tournaments:
            print("[WARN] No tournaments available for match hub tests")
            return
        
        # Find a live tournament with matches
        live_tournament = None
        for tournament in tournaments:
            if tournament.get('status') == 'live' and tournament.get('bracket'):
                live_tournament = tournament
                break
        
        if not live_tournament:
            print("[WARN] No live tournament with bracket found for match hub tests")
            return
        
        tournament_id = live_tournament['id']
        
        # Try to get matches for the tournament
        success, tournament_detail = self.run_test(
            f"GET /api/tournaments/{tournament_id}",
            "GET",
            f"tournaments/{tournament_id}",
            200
        )
        
        if success and tournament_detail:
            bracket = tournament_detail.get('bracket', {})
            matches = []
            
            # Extract matches from bracket structure
            if bracket.get('type') == 'league' and bracket.get('rounds'):
                for round_data in bracket['rounds']:
                    matches.extend(round_data.get('matches', []))
            
            if matches:
                test_match = matches[0]
                match_id = test_match['id']
                
                print(f"   Testing with match ID: {match_id}")
                
                # Test match detail endpoint
                success, match_detail = self.run_test(
                    f"GET /api/matches/{match_id}",
                    "GET",
                    f"matches/{match_id}",
                    200,
                    headers=self.get_demo_user_headers()
                )
                
                if success and match_detail:
                    print(f"   Match detail keys: {list(match_detail.keys())}")
                
                # Test schedule proposal
                proposal_data = {
                    "proposed_time": "2024-12-25T19:00:00Z"
                }
                
                success, proposal_result = self.run_test(
                    f"POST /api/matches/{match_id}/schedule",
                    "POST",
                    f"matches/{match_id}/schedule",
                    200,
                    proposal_data,
                    headers=self.get_demo_user_headers()
                )
                
                if success:
                    print("[PASS] Schedule proposal created")
                
                # Test getting schedule proposals
                success, schedule_list = self.run_test(
                    f"GET /api/matches/{match_id}/schedule",
                    "GET",
                    f"matches/{match_id}/schedule",
                    200,
                    headers=self.get_demo_user_headers()
                )
                
                if success and schedule_list:
                    print(f"   Found {len(schedule_list)} schedule proposals")
            else:
                print("[WARN] No matches found in live tournament for testing")

    def test_admin_smtp_settings(self):
        """Test admin SMTP settings access"""
        print("\n" + "="*60)
        print("TESTING ADMIN SMTP SETTINGS")
        print("="*60)
        
        # Test admin settings endpoint
        success, settings = self.run_test(
            "GET /api/admin/settings",
            "GET",
            "admin/settings",
            200,
            headers=self.get_admin_headers()
        )
        
        if success and settings:
            print(f"   Found {len(settings)} admin settings")
            
            # Look for SMTP-related settings
            smtp_settings = [s for s in settings if 'smtp' in s.get('key', '').lower()]
            print(f"   SMTP settings found: {len(smtp_settings)}")
            
            for setting in smtp_settings[:5]:  # Show first 5 SMTP settings
                print(f"   - {setting.get('key', 'unknown')}")
            
            if len(smtp_settings) >= 3:
                print("[PASS] SMTP settings accessible in admin panel")
                self.tests_passed += 1
            else:
                print("[FAIL] Insufficient SMTP settings found")
                self.failed_tests.append({'test': 'SMTP settings', 'error': 'Not enough SMTP settings'})
            self.tests_run += 1

    def run_all_tests(self):
        """Run all specific eSports tests"""
        print("Starting eSports Tournament System Specific Tests")
        print(f"Testing against: {self.base_url}")
        
        # Test login credentials
        self.test_login_credentials()
        
        # Test demo tournaments
        tournaments = self.test_demo_tournaments()
        
        # Test scheduling APIs
        self.test_scheduling_apis(tournaments)
        
        # Test new tournament creation fields
        self.test_tournament_creation_fields()
        
        # Test match hub scheduling
        self.test_match_hub_scheduling(tournaments)
        
        # Test admin SMTP settings
        self.test_admin_smtp_settings()
        
        # Print summary
        print("\n" + "="*60)
        print("SPECIFIC TESTS SUMMARY")
        print("="*60)
        print(f"Tests passed: {self.tests_passed}/{self.tests_run}")
        if self.tests_run > 0:
            print(f"Success rate: {(self.tests_passed/self.tests_run*100):.1f}%")
        
        if self.failed_tests:
            print("\nFAILED TESTS:")
            for failed in self.failed_tests:
                print(f"   - {failed.get('test', 'Unknown')}: {failed.get('error', failed.get('actual_status', 'Unknown error'))}")
        
        return self.tests_passed, self.tests_run, self.failed_tests

def main():
    tester = eSportsSpecificTester()
    passed, total, failed = tester.run_all_tests()
    return 0 if passed == total else 1

if __name__ == "__main__":
    sys.exit(main())