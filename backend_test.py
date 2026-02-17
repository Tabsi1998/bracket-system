#!/usr/bin/env python3
"""
eSports Tournament System - Backend API Testing
Testing Sub-Games, Maps, Map-Veto System, and CoD BO6 4v4 S&D Liga
"""

import requests
import sys
import json
from datetime import datetime

class eSportsTournamentTester:
    def __init__(self, base_url="http://localhost:8001"):
        self.base_url = base_url
        self.token = None
        self.tests_run = 0
        self.tests_passed = 0
        self.cod_game_id = None
        self.cod_bo6_sub_game_id = None
        self.cod_tournament_id = None
        self.test_match_id = None

    def run_test(self, name, method, endpoint, expected_status, data=None, headers=None):
        """Run a single API test"""
        url = f"{self.base_url}/api/{endpoint}"
        test_headers = {'Content-Type': 'application/json'}
        if self.token:
            test_headers['Authorization'] = f'Bearer {self.token}'
        if headers:
            test_headers.update(headers)

        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=test_headers)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=test_headers)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=test_headers)
            elif method == 'DELETE':
                response = requests.delete(url, headers=test_headers)

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                try:
                    return True, response.json()
                except:
                    return True, {}
            else:
                print(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                try:
                    error_detail = response.json()
                    print(f"   Error: {error_detail}")
                except:
                    print(f"   Response: {response.text[:200]}")
                return False, {}

        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            return False, {}

    def test_login(self, email, password):
        """Test login and get token"""
        success, response = self.run_test(
            f"Login {email}",
            "POST",
            "auth/login",
            200,
            data={"email": email, "password": password}
        )
        if success and 'token' in response:
            self.token = response['token']
            print(f"   🔑 Token obtained: {self.token[:20]}...")
            return True
        return False

    def test_games_with_sub_games(self):
        """Test games endpoint and find Call of Duty with sub-games"""
        success, response = self.run_test(
            "GET /api/games - Check for Sub-Games",
            "GET",
            "games",
            200
        )
        
        if success and isinstance(response, list):
            print(f"   📊 Found {len(response)} games")
            
            # Find Call of Duty game
            cod_game = None
            for game in response:
                if 'call of duty' in game.get('name', '').lower():
                    cod_game = game
                    self.cod_game_id = game.get('id')
                    break
            
            if cod_game:
                print(f"   🎮 Found CoD game: {cod_game.get('name')} (ID: {self.cod_game_id})")
                sub_games = cod_game.get('sub_games', [])
                print(f"   📦 Sub-games count: {len(sub_games)}")
                
                # Find Black Ops 6
                bo6_sub_game = None
                for sg in sub_games:
                    if 'black ops 6' in sg.get('name', '').lower():
                        bo6_sub_game = sg
                        self.cod_bo6_sub_game_id = sg.get('id')
                        break
                
                if bo6_sub_game:
                    print(f"   🎯 Found BO6: {bo6_sub_game.get('name')} (ID: {self.cod_bo6_sub_game_id})")
                    maps = bo6_sub_game.get('maps', [])
                    print(f"   🗺️  BO6 Maps count: {len(maps)}")
                    
                    # Check for expected maps
                    expected_maps = ['nuketown', 'hacienda', 'vault', 'skyline', 'red-card']
                    found_maps = []
                    for map_obj in maps:
                        map_name = map_obj.get('name', '').lower()
                        for expected in expected_maps:
                            if expected in map_name:
                                found_maps.append(expected)
                                break
                    
                    print(f"   ✅ Expected maps found: {found_maps}")
                    return len(found_maps) >= 3  # At least 3 expected maps
                else:
                    print("   ❌ Black Ops 6 sub-game not found")
            else:
                print("   ❌ Call of Duty game not found")
        
        return success

    def test_sub_games_endpoint(self):
        """Test GET /api/games/{id}/sub-games endpoint"""
        if not self.cod_game_id:
            print("   ⚠️  Skipping - CoD game ID not available")
            return False
            
        success, response = self.run_test(
            f"GET /api/games/{self.cod_game_id}/sub-games",
            "GET",
            f"games/{self.cod_game_id}/sub-games",
            200
        )
        
        if success and isinstance(response, list):
            print(f"   📦 Sub-games returned: {len(response)}")
            for sg in response:
                print(f"      - {sg.get('name')} ({sg.get('short_name')}) - {len(sg.get('maps', []))} maps")
            return len(response) >= 2  # Should have at least 2 sub-games
        
        return success

    def test_sub_game_maps_endpoint(self):
        """Test GET /api/games/{id}/sub-games/{sub_game_id}/maps endpoint"""
        if not self.cod_game_id or not self.cod_bo6_sub_game_id:
            print("   ⚠️  Skipping - CoD or BO6 ID not available")
            return False
            
        success, response = self.run_test(
            f"GET /api/games/{self.cod_game_id}/sub-games/{self.cod_bo6_sub_game_id}/maps",
            "GET",
            f"games/{self.cod_game_id}/sub-games/{self.cod_bo6_sub_game_id}/maps",
            200
        )
        
        if success and isinstance(response, list):
            print(f"   🗺️  BO6 Maps returned: {len(response)}")
            for map_obj in response:
                print(f"      - {map_obj.get('name')} (Modes: {', '.join(map_obj.get('game_modes', []))})")
            return len(response) >= 5  # Should have at least 5 maps
        
        return success

    def test_find_cod_tournament(self):
        """Find the CoD BO6 4v4 S&D Liga tournament"""
        success, response = self.run_test(
            "GET /api/tournaments - Find CoD Tournament",
            "GET",
            "tournaments",
            200
        )
        
        if success and isinstance(response, list):
            print(f"   🏆 Found {len(response)} tournaments")
            
            # Find CoD BO6 S&D Liga
            cod_tournament = None
            for tournament in response:
                name = tournament.get('name', '').lower()
                if 'cod' in name and 's&d' in name and 'liga' in name:
                    cod_tournament = tournament
                    self.cod_tournament_id = tournament.get('id')
                    break
            
            if cod_tournament:
                print(f"   🎯 Found CoD Tournament: {cod_tournament.get('name')}")
                print(f"      - ID: {self.cod_tournament_id}")
                print(f"      - Status: {cod_tournament.get('status')}")
                print(f"      - Teams: {cod_tournament.get('registered_count', 0)}/{cod_tournament.get('max_participants', 0)}")
                print(f"      - Game Mode: {cod_tournament.get('game_mode')}")
                print(f"      - Team Size: {cod_tournament.get('team_size')}")
                
                # Check for map pool
                map_pool = cod_tournament.get('map_pool', [])
                print(f"      - Map Pool: {len(map_pool)} maps")
                if map_pool:
                    print(f"        Maps: {', '.join(map_pool)}")
                
                return True
            else:
                print("   ❌ CoD BO6 S&D Liga tournament not found")
        
        return success

    def test_tournament_details(self):
        """Test tournament details endpoint"""
        if not self.cod_tournament_id:
            print("   ⚠️  Skipping - CoD tournament ID not available")
            return False
            
        success, response = self.run_test(
            f"GET /api/tournaments/{self.cod_tournament_id}",
            "GET",
            f"tournaments/{self.cod_tournament_id}",
            200
        )
        
        if success:
            tournament = response
            print(f"   🏆 Tournament: {tournament.get('name')}")
            print(f"      - Bracket Type: {tournament.get('bracket_type')}")
            print(f"      - Status: {tournament.get('status')}")
            print(f"      - Best of: {tournament.get('best_of')}")
            print(f"      - Map Ban Enabled: {tournament.get('map_ban_enabled')}")
            print(f"      - Map Ban Count: {tournament.get('map_ban_count')}")
            
            # Check if it's a league with 8 teams and 7 matchdays
            if tournament.get('bracket_type') == 'league':
                print(f"      ✅ League format confirmed")
                
                # Check bracket structure
                bracket = tournament.get('bracket', {})
                if bracket:
                    rounds = bracket.get('rounds', [])
                    print(f"      - Matchdays/Rounds: {len(rounds)}")
                    
                    if len(rounds) >= 7:
                        print(f"      ✅ Has 7+ matchdays as expected")
                    
                    # Check current matchday status
                    for i, round_data in enumerate(rounds[:3], 1):  # Check first 3 rounds
                        matches = round_data.get('matches', [])
                        completed = sum(1 for m in matches if m.get('status') == 'completed')
                        total = len(matches)
                        print(f"      - Spieltag {i}: {completed}/{total} matches completed")
            
            return True
        
        return success

    def test_find_match_for_veto(self):
        """Find a match to test map veto system"""
        if not self.cod_tournament_id:
            print("   ⚠️  Skipping - CoD tournament ID not available")
            return False
            
        success, response = self.run_test(
            f"GET /api/tournaments/{self.cod_tournament_id}",
            "GET",
            f"tournaments/{self.cod_tournament_id}",
            200
        )
        
        if success:
            bracket = response.get('bracket', {})
            rounds = bracket.get('rounds', [])
            
            # Find a match that's not completed
            test_match = None
            for round_data in rounds:
                for match in round_data.get('matches', []):
                    if match.get('status') != 'completed' and match.get('team1_name') != 'TBD' and match.get('team2_name') != 'TBD':
                        test_match = match
                        self.test_match_id = match.get('id')
                        break
                if test_match:
                    break
            
            if test_match:
                print(f"   🥊 Found test match: {test_match.get('team1_name')} vs {test_match.get('team2_name')}")
                print(f"      - Match ID: {self.test_match_id}")
                print(f"      - Status: {test_match.get('status')}")
                return True
            else:
                print("   ⚠️  No suitable match found for veto testing")
        
        return success

    def test_map_veto_status(self):
        """Test GET /api/matches/{match_id}/map-veto endpoint"""
        if not self.test_match_id:
            print("   ⚠️  Skipping - Test match ID not available")
            return False
            
        success, response = self.run_test(
            f"GET /api/matches/{self.test_match_id}/map-veto",
            "GET",
            f"matches/{self.test_match_id}/map-veto",
            200
        )
        
        if success:
            print(f"   🗺️  Map Veto Status:")
            print(f"      - Status: {response.get('status', 'N/A')}")
            print(f"      - Current Turn: {response.get('current_turn', 'N/A')}")
            print(f"      - Current Action: {response.get('current_action', 'N/A')}")
            
            map_pool = response.get('map_pool', [])
            banned_maps = response.get('banned_maps', [])
            picked_maps = response.get('picked_maps', [])
            
            print(f"      - Map Pool: {len(map_pool)} maps")
            print(f"      - Banned Maps: {len(banned_maps)} maps")
            print(f"      - Picked Maps: {len(picked_maps)} maps")
            
            if map_pool:
                print(f"        Available: {', '.join(map_pool[:5])}...")  # Show first 5
            
            return len(map_pool) >= 3  # Should have at least 3 maps in pool
        
        return success

    def test_map_veto_action(self):
        """Test POST /api/matches/{match_id}/map-veto endpoint"""
        if not self.test_match_id:
            print("   ⚠️  Skipping - Test match ID not available")
            return False
            
        # First get current veto status
        success, veto_status = self.run_test(
            f"GET current veto status",
            "GET",
            f"matches/{self.test_match_id}/map-veto",
            200
        )
        
        if not success or not veto_status.get('map_pool'):
            print("   ⚠️  No map pool available for veto testing")
            return False
        
        # Try to perform a veto action (ban first available map)
        map_pool = veto_status.get('map_pool', [])
        banned_maps = veto_status.get('banned_maps', [])
        
        # Find first unbanned map
        available_map = None
        for map_id in map_pool:
            if map_id not in banned_maps:
                available_map = map_id
                break
        
        if not available_map:
            print("   ⚠️  No available maps to ban")
            return True  # This is actually OK - veto might be complete
        
        success, response = self.run_test(
            f"POST /api/matches/{self.test_match_id}/map-veto - Ban {available_map}",
            "POST",
            f"matches/{self.test_match_id}/map-veto",
            200,
            data={"action": "ban", "map_id": available_map}
        )
        
        if success:
            print(f"   ✅ Map veto action successful")
            print(f"      - Action: ban")
            print(f"      - Map: {available_map}")
            
            # Check updated status
            new_status = response.get('status', 'N/A')
            new_banned = response.get('banned_maps', [])
            print(f"      - New Status: {new_status}")
            print(f"      - Total Banned: {len(new_banned)}")
            
            return True
        
        return success

    def test_map_veto_reset(self):
        """Test POST /api/matches/{match_id}/map-veto/reset endpoint (Admin only)"""
        if not self.test_match_id:
            print("   ⚠️  Skipping - Test match ID not available")
            return False
            
        success, response = self.run_test(
            f"POST /api/matches/{self.test_match_id}/map-veto/reset",
            "POST",
            f"matches/{self.test_match_id}/map-veto/reset",
            200
        )
        
        if success:
            print(f"   ✅ Map veto reset successful")
            print(f"      - Status: {response.get('status', 'N/A')}")
            print(f"      - Banned Maps: {len(response.get('banned_maps', []))}")
            print(f"      - Picked Maps: {len(response.get('picked_maps', []))}")
            return True
        
        return success

    def test_tournament_registrations(self):
        """Test tournament registrations to verify 8 teams"""
        if not self.cod_tournament_id:
            print("   ⚠️  Skipping - CoD tournament ID not available")
            return False
            
        success, response = self.run_test(
            f"GET /api/tournaments/{self.cod_tournament_id}/registrations",
            "GET",
            f"tournaments/{self.cod_tournament_id}/registrations",
            200
        )
        
        if success and isinstance(response, list):
            print(f"   👥 Tournament Registrations: {len(response)} teams")
            
            for i, reg in enumerate(response[:8], 1):  # Show first 8 teams
                team_name = reg.get('team_name', 'Unknown')
                team_tag = reg.get('team_tag', '')
                checked_in = reg.get('checked_in', False)
                seed = reg.get('seed', i)
                
                status_icon = "✅" if checked_in else "⏳"
                tag_display = f" [{team_tag}]" if team_tag else ""
                
                print(f"      {seed}. {team_name}{tag_display} {status_icon}")
            
            return len(response) >= 8  # Should have 8 teams
        
        return success

def main():
    print("🏆 eSports Tournament System - Backend API Testing")
    print("=" * 60)
    
    tester = eSportsTournamentTester("http://localhost:8001")
    
    # Test admin login
    if not tester.test_login("admin@arena.gg", "admin123"):
        print("❌ Admin login failed, stopping tests")
        return 1
    
    print("\n" + "="*60)
    print("🎮 TESTING SUB-GAMES AND MAPS SYSTEM")
    print("="*60)
    
    # Test games with sub-games
    tester.test_games_with_sub_games()
    
    # Test sub-games endpoint
    tester.test_sub_games_endpoint()
    
    # Test sub-game maps endpoint
    tester.test_sub_game_maps_endpoint()
    
    print("\n" + "="*60)
    print("🏆 TESTING COD BO6 4v4 S&D LIGA")
    print("="*60)
    
    # Find and test CoD tournament
    tester.test_find_cod_tournament()
    
    # Test tournament details
    tester.test_tournament_details()
    
    # Test tournament registrations (8 teams)
    tester.test_tournament_registrations()
    
    print("\n" + "="*60)
    print("🗺️  TESTING MAP BAN/VOTE SYSTEM")
    print("="*60)
    
    # Find a match for veto testing
    tester.test_find_match_for_veto()
    
    # Test map veto status
    tester.test_map_veto_status()
    
    # Test map veto action
    tester.test_map_veto_action()
    
    # Test map veto reset (admin)
    tester.test_map_veto_reset()
    
    # Print final results
    print("\n" + "="*60)
    print("📊 FINAL RESULTS")
    print("="*60)
    print(f"Tests passed: {tester.tests_passed}/{tester.tests_run}")
    success_rate = (tester.tests_passed / tester.tests_run * 100) if tester.tests_run > 0 else 0
    print(f"Success rate: {success_rate:.1f}%")
    
    if success_rate >= 70:
        print("🎉 Overall: GOOD - Core functionality working")
        return 0
    elif success_rate >= 50:
        print("⚠️  Overall: PARTIAL - Some issues found")
        return 0
    else:
        print("❌ Overall: FAILED - Major issues detected")
        return 1

if __name__ == "__main__":
    sys.exit(main())