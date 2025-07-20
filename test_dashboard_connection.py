
import requests
import json
import time

def test_dashboard_connection():
    """Test dashboard API endpoints"""
    base_url = "http://localhost:5000"
    
    print("🔍 Testing Dashboard Connection...")
    
    # Test basic endpoints
    endpoints = [
        "/",
        "/api/bot_status", 
        "/api/balance",
        "/api/strategies"
    ]
    
    for endpoint in endpoints:
        try:
            print(f"\n📡 Testing {endpoint}...")
            response = requests.get(f"{base_url}{endpoint}", timeout=5)
            
            if endpoint == "/":
                if response.status_code == 200:
                    print("✅ Dashboard home page accessible")
                else:
                    print(f"❌ Dashboard home page error: {response.status_code}")
            else:
                if response.status_code == 200:
                    data = response.json()
                    print(f"✅ {endpoint} working - Response: {json.dumps(data, indent=2)}")
                else:
                    print(f"❌ {endpoint} error: {response.status_code}")
                    
        except requests.exceptions.ConnectionError:
            print(f"❌ Connection refused for {endpoint}")
        except requests.exceptions.Timeout:
            print(f"❌ Timeout for {endpoint}")
        except Exception as e:
            print(f"❌ Error testing {endpoint}: {e}")
    
    # Test bot start/stop
    print(f"\n🤖 Testing Bot Control...")
    try:
        # Test bot status
        response = requests.get(f"{base_url}/api/bot_status", timeout=5)
        if response.status_code == 200:
            status = response.json()
            print(f"📊 Bot Status: {status}")
            
            if not status.get('running', False):
                print("🚀 Testing bot start...")
                start_response = requests.post(f"{base_url}/api/bot/start", timeout=10)
                if start_response.status_code == 200:
                    result = start_response.json()
                    print(f"✅ Start response: {result}")
                    
                    # Wait and check status
                    time.sleep(2)
                    status_response = requests.get(f"{base_url}/api/bot_status", timeout=5)
                    if status_response.status_code == 200:
                        new_status = status_response.json()
                        print(f"📊 New Status: {new_status}")
                else:
                    print(f"❌ Start failed: {start_response.status_code} - {start_response.text}")
            else:
                print("✅ Bot is already running")
                
        else:
            print(f"❌ Status check failed: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Bot control test error: {e}")
    
    print(f"\n🏁 Connection test completed")

if __name__ == "__main__":
    test_dashboard_connection()
