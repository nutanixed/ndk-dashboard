"""
Storage routes - API endpoints for NDK Storage Clusters
"""
from flask import Blueprint, jsonify
from app.utils import login_required, get_cached_or_fetch
from app.services import StorageService

storage_bp = Blueprint('storage', __name__)


@storage_bp.route('/storageclusters')
@login_required
def get_storageclusters():
    """Get all NDK Storage Clusters"""
    clusters = get_cached_or_fetch('storageclusters', StorageService.list_storage_clusters)
    return jsonify(clusters)