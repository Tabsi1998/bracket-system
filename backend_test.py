import requests
import sys
import json
from datetime import datetime

class eSportsTournamentAPITester:
    def __init__(self, base_url="https://dynamic-esports-pro.preview.emergentagent.com/api"):
        self.base_url = base_url
        self.tests_run = 0
        self.tests_passed = 0
        self.failed_tests = []
        self.session = requests.Session()

    def run_test(self, name, method, endpoint, expected_status, data=None, headers=None):
        """Run a single API test"""
        url = f"{self.base_url}/{endpoint}"
        if not headers:
            headers = {'Content-Type': 'application/json'}

        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
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
                print(f"✅ PASSED - {name}")
                try:
                    response_data = response.json() if response.content else {}
                    if response_data and isinstance(response_data, (list, dict)):
                        print(f"   Response data type: {type(response_data)}")
                        if isinstance(response_data, list):
                            print(f"   Response count: {len(response_data)}")
                        elif isinstance(response_data, dict):
                            print(f"   Response keys: {list(response_data.keys())}")
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
                print(f"❌ FAILED - {name} - Expected {expected_status}, got {response.status_code}")
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
            print(f"❌ FAILED - {name} - Error: {str(e)}")
            return False, {}

    def test_games_api(self):
        """Test games API endpoints"""
        print("\n" + "="*50)
        print("TESTING GAMES API")
        print("="*50)
        
        # Test get all games
        success, games = self.run_test("GET /api/games", "GET", "games", 200)
        if success:
            print(f"   Found {len(games)} games")
            if len(games) >= 14:
                print("✅ At least 14 seeded games found")
            else:
                print(f"⚠️  Expected at least 14 games, found {len(games)}")
        
        # Test games by category
        self.run_test("GET /api/games?category=fps", "GET", "games?category=fps", 200)
        
        # Test create custom game
        custom_game_data = {
            "name": "Test Game",
            "short_name": "TG",
            "category": "fps",
            "image_url": "https://example.com/test.jpg",
            "modes": [
                {"name": "1v1", "team_size": 1, "description": "1v1 Test"},
                {"name": "2v2", "team_size": 2, "description": "2v2 Test"}
            ],
            "platforms": ["PC", "PS5"]
        }
        success, created_game = self.run_test("POST /api/games", "POST", "games", 200, custom_game_data)
        
        if success and created_game:
            game_id = created_game.get('id')
            # Test get specific game
            self.run_test(f"GET /api/games/{game_id}", "GET", f"games/{game_id}", 200)
            
            # Test update game
            updated_data = {"name": "Updated Test Game", "short_name": "UTG", "category": "sports", "modes": [], "platforms": []}
            self.run_test(f"PUT /api/games/{game_id}", "PUT", f"games/{game_id}", 200, updated_data)
            
            # Test delete game
            self.run_test(f"DELETE /api/games/{game_id}", "DELETE", f"games/{game_id}", 200)
        
        return games if success else []

    def test_stats_api(self):
        """Test stats API"""
        print("\n" + "="*50)
        print("TESTING STATS API")
        print("="*50)
        
        success, stats = self.run_test("GET /api/stats", "GET", "stats", 200)
        if success and stats:
            expected_keys = ['total_tournaments', 'live_tournaments', 'total_registrations', 'total_games']
            for key in expected_keys:
                if key in stats:
                    print(f"✅ {key}: {stats[key]}")
                else:
                    print(f"❌ Missing stat key: {key}")
        return stats if success else {}

    def test_tournaments_api(self, games):
        """Test tournaments API endpoints"""
        print("\n" + "="*50)
        print("TESTING TOURNAMENTS API")
        print("="*50)
        
        if not games:
            print("⚠️  No games available for tournament testing")
            return None
            
        # Test get all tournaments
        self.run_test("GET /api/tournaments", "GET", "tournaments", 200)
        
        # Create a test tournament
        test_game = games[0] if games else None
        if not test_game:
            print("❌ No games available for tournament creation")
            return None
            
        tournament_data = {
            "name": "Test Tournament",
            "game_id": test_game['id'],
            "game_name": test_game['name'],
            "game_mode": test_game.get('modes', [{'name': '1v1'}])[0]['name'],
            "team_size": test_game.get('modes', [{'team_size': 1}])[0]['team_size'],
            "max_participants": 8,
            "bracket_type": "single_elimination",
            "best_of": 1,
            "entry_fee": 0.0,
            "currency": "usd",
            "prize_pool": "Test Prize",
            "description": "Test tournament description",
            "rules": "Test rules",
            "start_date": "2024-12-31T12:00:00"
        }
        
        success, tournament = self.run_test("POST /api/tournaments", "POST", "tournaments", 200, tournament_data)
        
        if success and tournament:
            tournament_id = tournament['id']
            print(f"✅ Created tournament with ID: {tournament_id}")
            
            # Test get specific tournament
            self.run_test(f"GET /api/tournaments/{tournament_id}", "GET", f"tournaments/{tournament_id}", 200)
            
            # Test update tournament
            update_data = {"name": "Updated Test Tournament", "description": "Updated description"}
            self.run_test(f"PUT /api/tournaments/{tournament_id}", "PUT", f"tournaments/{tournament_id}", 200, update_data)
            
            return tournament
        
        return None

    def test_registration_api(self, tournament):
        """Test registration API endpoints"""
        print("\n" + "="*50)
        print("TESTING REGISTRATION API")
        print("="*50)
        
        if not tournament:
            print("⚠️  No tournament available for registration testing")
            return []
            
        tournament_id = tournament['id']
        
        # Test get registrations (should be empty)
        self.run_test(f"GET /api/tournaments/{tournament_id}/registrations", "GET", f"tournaments/{tournament_id}/registrations", 200)
        
        # Test register for tournament
        registrations = []
        for i in range(4):  # Register 4 teams
            reg_data = {
                "team_name": f"Test Team {i+1}",
                "players": [
                    {"name": f"Player {i+1}-1", "email": f"player{i+1}-1@test.com"}
                ]
            }
            if tournament['team_size'] > 1:
                for j in range(1, tournament['team_size']):
                    reg_data["players"].append({
                        "name": f"Player {i+1}-{j+1}", 
                        "email": f"player{i+1}-{j+1}@test.com"
                    })
            
            success, registration = self.run_test(f"POST /api/tournaments/{tournament_id}/register", "POST", f"tournaments/{tournament_id}/register", 200, reg_data)
            
            if success and registration:
                registrations.append(registration)
                reg_id = registration['id']
                
                # Test check-in
                self.run_test(f"POST /api/tournaments/{tournament_id}/checkin/{reg_id}", "POST", f"tournaments/{tournament_id}/checkin/{reg_id}", 200)
        
        return registrations

    def test_bracket_api(self, tournament, registrations):
        """Test bracket generation and match scoring"""
        print("\n" + "="*50)
        print("TESTING BRACKET API")
        print("="*50)
        
        if not tournament or len(registrations) < 2:
            print("⚠️  Need at least 2 registrations for bracket testing")
            return False
            
        tournament_id = tournament['id']
        
        # Test generate bracket
        success, updated_tournament = self.run_test(f"POST /api/tournaments/{tournament_id}/generate-bracket", "POST", f"tournaments/{tournament_id}/generate-bracket", 200)
        
        if success and updated_tournament:
            bracket = updated_tournament.get('bracket')
            if bracket and bracket.get('rounds'):
                print("✅ Bracket generated successfully")
                
                # Test score update
                first_round = bracket['rounds'][0]
                if first_round.get('matches'):
                    first_match = first_round['matches'][0]
                    match_id = first_match['id']
                    
                    # Update match score
                    score_data = {"score1": 2, "score2": 1}
                    self.run_test(f"PUT /api/tournaments/{tournament_id}/matches/{match_id}/score", "PUT", f"tournaments/{tournament_id}/matches/{match_id}/score", 200, score_data)
                    
                return True
            else:
                print("❌ Bracket generation failed - no bracket structure found")
        
        return False

    def test_payment_api(self, tournament):
        """Test payment API endpoints (basic validation)"""
        print("\n" + "="*50)
        print("TESTING PAYMENT API")
        print("="*50)
        
        if not tournament:
            print("⚠️  No tournament available for payment testing")
            return
            
        # Note: We're testing with test data only, not real payments
        # Test payment creation (this will fail but we can test the endpoint exists)
        payment_data = {
            "tournament_id": tournament['id'],
            "registration_id": "test-reg-id",
            "origin_url": "https://test.com"
        }
        
        # This might fail but should return a proper error response
        self.run_test("POST /api/payments/create-checkout", "POST", "payments/create-checkout", 404, payment_data)
        
        # Test payment status check (also expected to fail gracefully)
        self.run_test("GET /api/payments/status/test-session-id", "GET", "payments/status/test-session-id", 500)

    def cleanup_test_data(self, tournament):
        """Clean up test data"""
        print("\n" + "="*50)
        print("CLEANING UP TEST DATA")
        print("="*50)
        
        if tournament:
            tournament_id = tournament['id']
            self.run_test(f"DELETE /api/tournaments/{tournament_id}", "DELETE", f"tournaments/{tournament_id}", 200)
            print(f"✅ Cleaned up tournament: {tournament_id}")

    def run_all_tests(self):
        """Run all API tests"""
        print("🚀 Starting eSports Tournament API Tests")
        print(f"Testing against: {self.base_url}")
        
        # Test games API
        games = self.test_games_api()
        
        # Test stats API
        stats = self.test_stats_api()
        
        # Test tournaments API
        tournament = self.test_tournaments_api(games)
        
        # Test registration API
        registrations = self.test_registration_api(tournament)
        
        # Test bracket API
        bracket_success = self.test_bracket_api(tournament, registrations)
        
        # Test payment API
        self.test_payment_api(tournament)
        
        # Cleanup
        self.cleanup_test_data(tournament)
        
        # Print summary
        print("\n" + "="*60)
        print("TEST SUMMARY")
        print("="*60)
        print(f"📊 Tests passed: {self.tests_passed}/{self.tests_run}")
        print(f"📊 Success rate: {(self.tests_passed/self.tests_run*100):.1f}%")
        
        if self.failed_tests:
            print("\n❌ FAILED TESTS:")
            for failed in self.failed_tests:
                print(f"   - {failed.get('test', 'Unknown')}: {failed.get('error', failed.get('actual_status', 'Unknown error'))}")
        
        return self.tests_passed, self.tests_run, self.failed_tests

def main():
    tester = eSportsTournamentAPITester()
    passed, total, failed = tester.run_all_tests()
    return 0 if passed == total else 1

if __name__ == "__main__":
    sys.exit(main())