
#!/usr/bin/env python3
"""
VPN Connection Status Checker
Check if VPN/proxy is active and working properly
"""

import requests
import json
import os
from datetime import datetime

def check_vpn_status():
    """Check VPN/proxy connection status"""
    print("🔍 VPN/PROXY CONNECTION STATUS CHECK")
    print("=" * 50)
    
    # Test 1: Check current IP address
    print("\n📡 Testing current IP address...")
    try:
        # Use multiple IP check services for reliability
        ip_services = [
            "https://api.ipify.org?format=json",
            "https://httpbin.org/ip",
            "https://api.myip.com"
        ]
        
        current_ip = None
        for service in ip_services:
            try:
                response = requests.get(service, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    current_ip = data.get('ip') or data.get('origin')
                    if current_ip:
                        print(f"✅ Current IP: {current_ip}")
                        break
            except Exception as e:
                print(f"⚠️ {service} failed: {e}")
                continue
        
        if not current_ip:
            print("❌ Could not determine current IP")
            return False
            
    except Exception as e:
        print(f"❌ IP check failed: {e}")
        return False
    
    # Test 2: Check geolocation
    print("\n🌍 Testing geolocation...")
    try:
        response = requests.get("https://ipapi.co/json/", timeout=10)
        if response.status_code == 200:
            geo_data = response.json()
            country = geo_data.get('country_name', 'Unknown')
            city = geo_data.get('city', 'Unknown')
            isp = geo_data.get('org', 'Unknown')
            
            print(f"📍 Location: {city}, {country}")
            print(f"🏢 ISP: {isp}")
            
            # Check if this looks like a VPN/proxy
            vpn_indicators = ['vpn', 'proxy', 'hosting', 'datacenter', 'cloud']
            is_likely_vpn = any(indicator in isp.lower() for indicator in vpn_indicators)
            
            if is_likely_vpn:
                print("✅ ISP suggests VPN/proxy connection")
            else:
                print("⚠️ ISP suggests direct connection")
                
        else:
            print("❌ Could not get geolocation data")
            
    except Exception as e:
        print(f"❌ Geolocation check failed: {e}")
    
    # Test 3: Check proxy configuration
    print("\n🔧 Checking proxy configuration...")
    try:
        from src.config.global_config import global_config
        
        print(f"PROXY_ENABLED: {global_config.PROXY_ENABLED}")
        
        if global_config.PROXY_ENABLED:
            print("✅ Proxy is enabled in bot configuration")
            
            if global_config.PROXY_URLS:
                print(f"🔗 Configured proxy URLs: {len(global_config.PROXY_URLS)}")
                for i, url in enumerate(global_config.PROXY_URLS, 1):
                    # Hide credentials in display
                    display_url = url.split('@')[-1] if '@' in url else url
                    print(f"   {i}. {display_url}")
            else:
                print("⚠️ No proxy URLs configured")
                
        else:
            print("⚠️ Proxy is disabled in bot configuration")
            
    except Exception as e:
        print(f"❌ Proxy config check failed: {e}")
    
    # Test 4: Test Binance connectivity
    print("\n🔗 Testing Binance connectivity...")
    try:
        # Test both regular and VPN scenarios
        test_urls = [
            "https://api.binance.com/api/v3/ping",
            "https://fapi.binance.com/fapi/v1/ping"
        ]
        
        for url in test_urls:
            try:
                response = requests.get(url, timeout=10)
                if response.status_code == 200:
                    exchange_type = "Spot" if "api.binance.com" in url else "Futures"
                    print(f"✅ Binance {exchange_type} API accessible")
                else:
                    print(f"❌ Binance API returned status {response.status_code}")
            except Exception as e:
                print(f"❌ Binance API test failed: {e}")
                
    except Exception as e:
        print(f"❌ Binance connectivity test failed: {e}")
    
    # Test 5: Environment detection
    print("\n🌐 Environment detection...")
    is_deployment = os.environ.get('REPLIT_DEPLOYMENT') == '1'
    replit_user = os.environ.get('REPL_OWNER')
    
    print(f"Deployment mode: {'Yes' if is_deployment else 'No'}")
    print(f"Replit user: {replit_user or 'Not detected'}")
    
    if is_deployment:
        print("📍 Running in Replit deployment - geographic restrictions may apply")
        if not global_config.PROXY_ENABLED:
            print("⚠️ Consider enabling proxy for deployment mode")
    
    # Summary
    print("\n📋 SUMMARY:")
    print("=" * 30)
    print(f"Current IP: {current_ip}")
    print(f"Proxy configured: {global_config.PROXY_ENABLED}")
    print(f"Deployment mode: {is_deployment}")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    return True

if __name__ == "__main__":
    try:
        check_vpn_status()
    except Exception as e:
        print(f"❌ VPN status check failed: {e}")
        import traceback
        traceback.print_exc()
