#!/usr/bin/env python3
"""
Test script for NDK Dashboard new features
"""
import requests
import json
import time

BASE_URL = "http://localhost:5000"
USERNAME = "admin"
PASSWORD = "admin"

def test_features():
    print("🧪 Testing NDK Dashboard Features\n")
    
    # Create session
    session = requests.Session()
    
    # Test 1: Login
    print("1️⃣ Testing Login...")
    login_response = session.post(f"{BASE_URL}/login", data={
        'username': USERNAME,
        'password': PASSWORD
    }, allow_redirects=False)
    
    if login_response.status_code in [200, 302]:
        print("   ✅ Login successful\n")
    else:
        print(f"   ❌ Login failed: {login_response.status_code}\n")
        return
    
    # Test 2: Get Applications
    print("2️⃣ Testing Get Applications...")
    apps_response = session.get(f"{BASE_URL}/api/applications")
    if apps_response.status_code == 200:
        apps = apps_response.json()
        print(f"   ✅ Found {len(apps)} application(s)")
        for app in apps:
            print(f"      - {app['name']} ({app['namespace']}) - {app['state']}")
        print()
    else:
        print(f"   ❌ Failed: {apps_response.status_code}\n")
        return
    
    # Test 3: Get Snapshots
    print("3️⃣ Testing Get Snapshots...")
    snaps_response = session.get(f"{BASE_URL}/api/snapshots")
    if snaps_response.status_code == 200:
        snapshots = snaps_response.json()
        print(f"   ✅ Found {len(snapshots)} snapshot(s)")
        for snap in snapshots:
            print(f"      - {snap['name']} ({snap['namespace']}) - {snap['state']}")
        print()
    else:
        print(f"   ❌ Failed: {snaps_response.status_code}\n")
        return
    
    # Test 4: Create Snapshot with Custom Expiration
    if apps:
        app = apps[0]
        print(f"4️⃣ Testing Create Snapshot for {app['name']}...")
        create_response = session.post(f"{BASE_URL}/api/snapshots", json={
            'applicationName': app['name'],
            'namespace': app['namespace'],
            'expiresAfter': '168h'  # 7 days
        })
        
        if create_response.status_code == 201:
            result = create_response.json()
            print(f"   ✅ Snapshot created: {result['snapshot']['name']}")
            new_snapshot = result['snapshot']
            print()
            
            # Wait a bit for snapshot to be created
            time.sleep(2)
            
            # Test 5: Delete Snapshot
            print(f"5️⃣ Testing Delete Snapshot...")
            delete_response = session.delete(
                f"{BASE_URL}/api/snapshots/{new_snapshot['namespace']}/{new_snapshot['name']}"
            )
            
            if delete_response.status_code == 200:
                print(f"   ✅ Snapshot deleted successfully\n")
            else:
                print(f"   ❌ Delete failed: {delete_response.status_code}\n")
        else:
            print(f"   ❌ Create failed: {create_response.status_code}")
            print(f"   Error: {create_response.text}\n")
    
    # Test 6: Bulk Create Snapshots
    if len(apps) > 0:
        print(f"6️⃣ Testing Bulk Snapshot Creation...")
        bulk_apps = [{'name': app['name'], 'namespace': app['namespace']} for app in apps[:1]]
        
        bulk_response = session.post(f"{BASE_URL}/api/snapshots/bulk", json={
            'applications': bulk_apps,
            'expiresAfter': '24h'
        })
        
        if bulk_response.status_code in [201, 207]:
            result = bulk_response.json()
            print(f"   ✅ Bulk operation completed")
            print(f"      Success: {len(result['results']['success'])}")
            print(f"      Failed: {len(result['results']['failed'])}")
            print()
        else:
            print(f"   ❌ Bulk create failed: {bulk_response.status_code}\n")
    
    # Test 7: Get Stats
    print("7️⃣ Testing Dashboard Stats...")
    stats_response = session.get(f"{BASE_URL}/api/stats")
    if stats_response.status_code == 200:
        stats = stats_response.json()
        print(f"   ✅ Stats retrieved:")
        print(f"      Applications: {stats['applications']}")
        print(f"      Snapshots: {stats['snapshots']}")
        print(f"      Storage Clusters: {stats['storageClusters']}")
        print(f"      Protection Plans: {stats['protectionPlans']}")
        print()
    else:
        print(f"   ❌ Failed: {stats_response.status_code}\n")
    
    print("✨ All tests completed!\n")

if __name__ == "__main__":
    try:
        test_features()
    except requests.exceptions.ConnectionError:
        print("❌ Error: Cannot connect to dashboard at http://localhost:5000")
        print("   Make sure the dashboard is running: python app.py")
    except Exception as e:
        print(f"❌ Error: {e}")