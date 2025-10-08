"""
Main routes - Dashboard pages and health check
"""
from flask import Blueprint, render_template, jsonify
from datetime import datetime
from kubernetes.client.rest import ApiException
from app.utils import login_required, get_cached_or_fetch
from app.extensions import k8s_api
from config import Config

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
@login_required
def index():
    """Main dashboard page"""
    return render_template('index.html')


@main_bp.route('/admin')
@login_required
def admin():
    """Admin page for managing applications and protection plans"""
    return render_template('admin.html')


@main_bp.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'version': '3.0.0',
        'kubernetes': k8s_api is not None,
        'timestamp': datetime.now().isoformat()
    })


@main_bp.route('/api/stats')
@login_required
def get_stats():
    """Get dashboard statistics"""
    try:
        # Fetch applications
        def fetch_apps():
            if not k8s_api:
                return []
            try:
                result = k8s_api.list_cluster_custom_object(
                    group=Config.NDK_API_GROUP,
                    version=Config.NDK_API_VERSION,
                    plural='applications'
                )
                return result.get('items', [])
            except ApiException as e:
                print(f"Error fetching applications for stats: {e}")
                return []
        
        # Fetch snapshots
        def fetch_snapshots():
            if not k8s_api:
                return []
            try:
                result = k8s_api.list_cluster_custom_object(
                    group=Config.NDK_API_GROUP,
                    version=Config.NDK_API_VERSION,
                    plural='applicationsnapshots'
                )
                return result.get('items', [])
            except ApiException as e:
                print(f"Error fetching snapshots for stats: {e}")
                return []
        
        # Fetch storage clusters
        def fetch_clusters():
            if not k8s_api:
                return []
            try:
                result = k8s_api.list_cluster_custom_object(
                    group=Config.NDK_API_GROUP,
                    version=Config.NDK_API_VERSION,
                    plural='storageclusters'
                )
                return result.get('items', [])
            except ApiException as e:
                print(f"Error fetching storage clusters for stats: {e}")
                return []
        
        # Fetch protection plans
        def fetch_plans():
            if not k8s_api:
                return []
            try:
                result = k8s_api.list_cluster_custom_object(
                    group=Config.NDK_API_GROUP,
                    version=Config.NDK_API_VERSION,
                    plural='protectionplans'
                )
                return result.get('items', [])
            except ApiException as e:
                print(f"Error fetching protection plans for stats: {e}")
                return []
        
        apps = get_cached_or_fetch('applications', fetch_apps)
        snapshots = get_cached_or_fetch('snapshots', fetch_snapshots)
        clusters = get_cached_or_fetch('storageclusters', fetch_clusters)
        plans = get_cached_or_fetch('protectionplans', fetch_plans)
        
        return jsonify({
            'applications': len(apps),
            'snapshots': len(snapshots),
            'storageClusters': len(clusters),
            'protectionPlans': len(plans)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500