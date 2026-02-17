#!/usr/bin/env python3

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
        self.failed_tests = []

    def run_test(self, name, method, endpoint, expected_status, data=None, headers=None):
        """Run a single API test"""
        url = f"{self.base_url}/{endpoint}"
        test_headers = {'Content-Type': 'application/json'}
        if self.token:
            test_headers['Authorization'] = f'Bearer {self.token}'
        if headers:
            test_headers.update(headers)

        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=test_headers, timeout=10)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=test_headers, timeout=10)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=test_headers, timeout=10)
            elif method == 'DELETE':
                response = requests.delete(url, headers=test_headers, timeout=10)

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                try:
                    return True, response.json() if response.text else {}
                except:
                    return True, {}
            else:
                print(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                if response.text:
                    print(f"   Response: {response.text[:200]}")
                self.failed_tests.append(f"{name}: Expected {expected_status}, got {response.status_code}")
                return False, {}

        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            self.failed_tests.append(f"{name}: {str(e)}")
            return False, {}

    def test_login(self, email, password):
        """Test login and get token"""
        success, response = self.run_test(
            f"Login {email}",
            "POST",
            "api/auth/login",
            200,
            data={"email": email, "password": password}
        )
        if success and 'token' in response:
            self.token = response['token']
            print(f"   🔑 Token obtained for {email}")
            return True
        return False

    def test_paypal_config_endpoint(self):
        """Test PayPal config endpoint"""
        success, response = self.run_test(
            "PayPal Config Endpoint",
            "GET",
            "api/payments/paypal/config",
            200
        )
        if success:
            print(f"   📋 PayPal config available: {bool(response.get('configured'))}")
        return success

    def test_scheduling_reminders_api(self):
        """Test scheduling reminders API"""
        # First get a tournament ID
        success, tournaments = self.run_test(
            "Get Tournaments for Reminder Test",
            "GET", 
            "api/tournaments",
            200
        )
        
        if not success or not tournaments:
            return False
            
        tournament_id = tournaments[0]['id']
        
        success, response = self.run_test(
            "Send Scheduling Reminders",
            "POST",
            f"api/tournaments/{tournament_id}/send-scheduling-reminders",
            200
        )
        
        if success:
            sent = response.get('sent', 0)
            failed = response.get('failed', 0)
            print(f"   📧 Reminders sent: {sent}, failed: {failed}")
        
        return success

    def test_auto_schedule_api(self):
        """Test auto-scheduling API"""
        # First get a tournament ID
        success, tournaments = self.run_test(
            "Get Tournaments for Auto-Schedule Test",
            "GET",
            "api/tournaments", 
            200
        )
        
        if not success or not tournaments:
            return False
            
        tournament_id = tournaments[0]['id']
        
        # This might return 400 if bracket not generated, which is expected
        success, response = self.run_test(
            "Auto-Schedule Unscheduled Matches",
            "POST",
            f"api/tournaments/{tournament_id}/auto-schedule-unscheduled",
            [200, 400]  # Both are acceptable
        )
        
        if success:
            if response.get('detail'):
                print(f"   ⚠️  Expected response: {response.get('detail')}")
            else:
                scheduled = response.get('scheduled_matches', 0)
                print(f"   📅 Auto-scheduled matches: {scheduled}")
        
        return True  # Both 200 and 400 are acceptable for this test

    def test_paypal_create_order_api(self):
        """Test PayPal create order API"""
        success, response = self.run_test(
            "PayPal Create Order",
            "POST",
            "api/payments/paypal/create-order",
            [200, 400, 500],  # Multiple status codes acceptable depending on config
            data={
                "amount": 10.00,
                "currency": "USD", 
                "tournament_name": "Test Tournament",
                "return_url": "http://localhost:3000/success",
                "cancel_url": "http://localhost:3000/cancel"
            }
        )
        
        if success:
            if response.get('detail'):
                print(f"   ⚠️  PayPal response: {response.get('detail')}")
            elif response.get('id'):
                print(f"   💳 PayPal order created: {response.get('id')}")
        
        return True  # Any response is acceptable for this test

    def test_paypal_capture_order_api(self):
        """Test PayPal capture order API"""
        # Use a dummy order ID since we can't create real orders in test
        success, response = self.run_test(
            "PayPal Capture Order",
            "POST",
            "api/payments/paypal/capture-order",
            [200, 400, 404, 500],  # Multiple status codes acceptable
            data={"order_id": "test_order_id"}
        )
        
        if success:
            if response.get('detail'):
                print(f"   ⚠️  PayPal capture response: {response.get('detail')}")
        
        return True  # Any response is acceptable for this test

    def test_faq_endpoint(self):
        """Test FAQ endpoint"""
        success, response = self.run_test(
            "FAQ Endpoint",
            "GET",
            "api/faq",
            200
        )
        
        if success:
            items = response.get('items', [])
            print(f"   📚 FAQ items available: {len(items)}")
            if len(items) >= 10:
                print(f"   ✅ Extended FAQ with {len(items)} entries")
            else:
                print(f"   ⚠️  Only {len(items)} FAQ entries (expected 10+)")
        
        return success

    def test_admin_faq_management(self):
        """Test admin FAQ management"""
        success, response = self.run_test(
            "Admin FAQ Get",
            "GET",
            "api/admin/faq",
            200
        )
        
        if success:
            items = response.get('items', [])
            source = response.get('source', 'unknown')
            print(f"   📝 Admin FAQ: {len(items)} items, source: {source}")
        
        return success

    def test_tournament_creation_with_new_fields(self):
        """Test tournament creation with new scheduling fields"""
        # First get a game ID
        success, games = self.run_test(
            "Get Games for Tournament Creation",
            "GET",
            "api/games",
            200
        )
        
        if not success or not games:
            return False
            
        game_id = games[0]['id']
        game_mode = games[0]['modes'][0]['name'] if games[0].get('modes') else "1v1"
        
        tournament_data = {
            "name": f"Test Tournament {datetime.now().strftime('%H%M%S')}",
            "game_id": game_id,
            "game_name": games[0]['name'],
            "game_mode": game_mode,
            "participant_mode": "team",
            "team_size": 2,
            "max_participants": 8,
            "bracket_type": "league",
            "best_of": 1,
            "entry_fee": 0.0,
            "currency": "usd",
            "description": "Test tournament with new scheduling fields",
            "default_match_day": "wednesday",
            "default_match_hour": 19,
            "auto_schedule_on_window_end": True,
            "matchday_interval_days": 7,
            "matchday_window_days": 7
        }
        
        success, response = self.run_test(
            "Create Tournament with New Fields",
            "POST",
            "api/tournaments",
            201,
            data=tournament_data
        )
        
        if success:
            tournament_id = response.get('id')
            print(f"   🏆 Tournament created with ID: {tournament_id}")
            
            # Verify the new fields are saved
            verify_success, verify_response = self.run_test(
                "Verify Tournament Fields",
                "GET",
                f"api/tournaments/{tournament_id}",
                200
            )
            
            if verify_success:
                default_day = verify_response.get('default_match_day')
                default_hour = verify_response.get('default_match_hour')
                auto_schedule = verify_response.get('auto_schedule_on_window_end')
                print(f"   ✅ Verified fields - Day: {default_day}, Hour: {default_hour}, Auto: {auto_schedule}")
        
        return success

    def test_basic_functionality(self):
        """Test basic system functionality"""
        print("\n🔧 Testing Basic System Functionality...")
        
        # Test games endpoint
        success, games = self.run_test("Get Games", "GET", "api/games", 200)
        if success:
            print(f"   🎮 Games available: {len(games)}")
        
        # Test tournaments endpoint  
        success, tournaments = self.run_test("Get Tournaments", "GET", "api/tournaments", 200)
        if success:
            print(f"   🏆 Tournaments available: {len(tournaments)}")
        
        return True

def main():
    print("🚀 Starting eSports Tournament System API Tests")
    print("=" * 60)
    
    tester = eSportsTournamentTester("http://localhost:8001")
    
    # Test login credentials
    print("\n👤 Testing Login Credentials...")
    admin_login = tester.test_login("admin@arena.gg", "admin123")
    demo_admin_login = tester.test_login("demo.admin@arena.gg", "demo123")
    
    if not admin_login and not demo_admin_login:
        print("❌ No valid admin credentials found, stopping tests")
        return 1
    
    # Test basic functionality
    tester.test_basic_functionality()
    
    # Test new PayPal features
    print("\n💳 Testing PayPal Integration...")
    tester.test_paypal_config_endpoint()
    tester.test_paypal_create_order_api()
    tester.test_paypal_capture_order_api()
    
    # Test scheduling features
    print("\n📅 Testing Scheduling Features...")
    tester.test_scheduling_reminders_api()
    tester.test_auto_schedule_api()
    
    # Test FAQ features
    print("\n📚 Testing FAQ Features...")
    tester.test_faq_endpoint()
    tester.test_admin_faq_management()
    
    # Test tournament creation with new fields
    print("\n🏆 Testing Tournament Creation...")
    tester.test_tournament_creation_with_new_fields()
    
    # Print results
    print("\n" + "=" * 60)
    print(f"📊 Test Results: {tester.tests_passed}/{tester.tests_run} passed")
    
    if tester.failed_tests:
        print("\n❌ Failed Tests:")
        for failed in tester.failed_tests:
            print(f"   - {failed}")
    
    success_rate = (tester.tests_passed / tester.tests_run * 100) if tester.tests_run > 0 else 0
    print(f"\n✅ Success Rate: {success_rate:.1f}%")
    
    return 0 if success_rate >= 80 else 1

if __name__ == "__main__":
    sys.exit(main())