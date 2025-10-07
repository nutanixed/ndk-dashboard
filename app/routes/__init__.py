"""
Route blueprints for NDK Dashboard
"""
from .main import main_bp
from .auth import auth_bp
from .applications import applications_bp
from .snapshots import snapshots_bp
from .storage import storage_bp
from .protectionplans import protectionplans_bp
from .deployment import deployment_bp

__all__ = [
    'main_bp',
    'auth_bp',
    'applications_bp',
    'snapshots_bp',
    'storage_bp',
    'protectionplans_bp',
    'deployment_bp'
]