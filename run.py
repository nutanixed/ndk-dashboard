"""
NDK Dashboard - Application Entry Point
"""
from app import create_app
from config import Config

# Create the Flask application
app = create_app()

if __name__ == '__main__':
    print("=" * 60)
    print("NDK Dashboard Starting...")
    print("=" * 60)
    print(f"Environment: {Config.FLASK_ENV}")
    print(f"In-cluster mode: {Config.IN_CLUSTER}")
    print(f"Cache TTL: {Config.CACHE_TTL} seconds")
    print("=" * 60)
    
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=(Config.FLASK_ENV == 'development')
    )