import sys
sys.path.insert(0, '/home/nutanix/dev/ndk-dashboard')

from app import create_app
app = create_app()

with app.test_client() as client:
    with client.session_transaction() as sess:
        sess['user_id'] = 'test'
    
    response = client.get('/api/taskapp/db/status')
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.get_json()}")
