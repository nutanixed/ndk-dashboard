"""
Restore routes - API endpoints for managing restore jobs
"""
from flask import Blueprint, jsonify, request
from app.utils import login_required
from app.services.restores import (
    list_restore_jobs,
    delete_restore_job,
    delete_completed_restore_jobs
)

restores_bp = Blueprint('restores', __name__)


@restores_bp.route('/restores', methods=['GET'])
@login_required
def get_restore_jobs():
    """Get all restore jobs"""
    namespace = request.args.get('namespace')
    restore_jobs = list_restore_jobs(namespace)
    return jsonify(restore_jobs)


@restores_bp.route('/restores/<namespace>/<name>', methods=['DELETE'])
@login_required
def delete_restore(namespace, name):
    """Delete a specific restore job"""
    success, message = delete_restore_job(name, namespace)
    
    if success:
        return jsonify({'success': True, 'message': message})
    else:
        return jsonify({'success': False, 'error': message}), 500


@restores_bp.route('/restores/cleanup', methods=['POST'])
@login_required
def cleanup_completed_restores():
    """Delete all completed restore jobs"""
    data = request.get_json() or {}
    namespace = data.get('namespace')
    
    success_count, failed_count, messages = delete_completed_restore_jobs(namespace)
    
    return jsonify({
        'success': True,
        'deleted': success_count,
        'failed': failed_count,
        'messages': messages
    })