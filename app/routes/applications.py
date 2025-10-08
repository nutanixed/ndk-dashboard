"""
Application routes - API endpoints for NDK Applications
"""
from flask import Blueprint, jsonify, request
from app.utils import login_required, get_cached_or_fetch, invalidate_cache
from app.services import ApplicationService

applications_bp = Blueprint('applications', __name__)


@applications_bp.route('/applications')
@login_required
def list_applications():
    """Get all NDK Applications from non-system namespaces"""
    applications = get_cached_or_fetch('applications', ApplicationService.list_applications)
    return jsonify(applications)


@applications_bp.route('/applications/<namespace>/<name>', methods=['GET'])
@login_required
def get_application(namespace, name):
    """Get a single NDK Application"""
    try:
        application = ApplicationService.get_application(namespace, name)
        return jsonify(application)
    except Exception as e:
        return jsonify({'error': str(e)}), 404


@applications_bp.route('/applications/<namespace>/<name>', methods=['DELETE'])
@login_required
def delete_application(namespace, name):
    """Delete an NDK Application"""
    try:
        force = request.args.get('force', 'false').lower() == 'true'
        app_only = request.args.get('app_only', 'false').lower() == 'true'
        
        message, cleanup_log = ApplicationService.delete_application(
            namespace, name, force, app_only
        )
        
        # Invalidate all relevant caches
        invalidate_cache('applications', 'snapshots', 'protectionplans')
        
        return jsonify({
            'success': True,
            'message': message,
            'cleanup_log': cleanup_log
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@applications_bp.route('/applications/<namespace>/<name>/labels', methods=['PUT'])
@login_required
def update_labels(namespace, name):
    """Update labels on an NDK Application"""
    try:
        data = request.get_json()
        new_labels = data.get('labels', {})
        labels_to_remove = data.get('labels_to_remove', [])
        
        print(f"[DEBUG] Received labels update request:")
        print(f"[DEBUG] - new_labels: {new_labels}")
        print(f"[DEBUG] - labels_to_remove: {labels_to_remove}")
        
        updated_labels = ApplicationService.update_labels(
            namespace, name, new_labels, labels_to_remove
        )
        
        # Clear cache to force refresh
        invalidate_cache('applications')
        
        return jsonify({
            'message': 'Labels updated successfully',
            'labels': updated_labels
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@applications_bp.route('/applications/<namespace>/<name>/debug', methods=['GET'])
@login_required
def debug_application(namespace, name):
    """Debug endpoint to see application details"""
    try:
        debug_info = ApplicationService.get_debug_info(namespace, name)
        return jsonify(debug_info)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@applications_bp.route('/applications/<namespace>/<name>/pods', methods=['GET'])
@login_required
def get_pods(namespace, name):
    """Get pod information for an NDK Application"""
    try:
        pods_info = ApplicationService.get_pods(namespace, name)
        return jsonify(pods_info)
    except Exception as e:
        print(f"Error fetching pods for {namespace}/{name}: {e}")
        return jsonify({'error': str(e)}), 500


@applications_bp.route('/applications/<namespace>/<name>/pvcs', methods=['GET'])
@login_required
def get_pvcs(namespace, name):
    """Get PVC and Volume Group information for an NDK Application"""
    try:
        pvcs_info = ApplicationService.get_pvcs(namespace, name)
        return jsonify(pvcs_info)
    except Exception as e:
        print(f"Error fetching PVCs for {namespace}/{name}: {e}")
        return jsonify({'error': str(e)}), 500


@applications_bp.route('/applications/<namespace>/<name>/restore-progress', methods=['GET'])
@login_required
def get_restore_progress(namespace, name):
    """Get restore progress for an application"""
    try:
        progress_info = ApplicationService.get_restore_progress(namespace, name)
        return jsonify(progress_info)
    except Exception as e:
        print(f"Error fetching restore progress for {namespace}/{name}: {e}")
        return jsonify({'error': str(e)}), 500