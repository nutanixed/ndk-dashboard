"""
Configuration management for NDK Dashboard
"""
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    """Application configuration"""
    
    # Flask configuration
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    FLASK_ENV = os.getenv('FLASK_ENV', 'development')
    
    # Dashboard authentication
    DASHBOARD_USERNAME = os.getenv('DASHBOARD_USERNAME', 'admin')
    DASHBOARD_PASSWORD = os.getenv('DASHBOARD_PASSWORD', 'admin')
    
    # Session configuration
    SESSION_TIMEOUT_HOURS = int(os.getenv('SESSION_TIMEOUT_HOURS', '24'))
    PERMANENT_SESSION_LIFETIME = SESSION_TIMEOUT_HOURS * 3600
    
    # Kubernetes configuration
    IN_CLUSTER = os.getenv('IN_CLUSTER', 'false').lower() == 'true'
    
    # Cache configuration
    CACHE_TTL = int(os.getenv('CACHE_TTL', '30'))  # seconds
    
    # NDK API configuration
    NDK_API_GROUP = 'dataservices.nutanix.com'
    NDK_API_VERSION = 'v1alpha1'
    
    @staticmethod
    def init_app(app):
        """Initialize application with configuration"""
        pass