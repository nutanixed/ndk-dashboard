"""
Snapshot routes - API endpoints for NDK Application Snapshots
"""
from flask import Blueprint, jsonify, request
from kubernetes.client.rest import ApiException
import json
from app.utils import login_required, get_cached_or_fetch, invalidate_cache
from app.services import SnapshotService

snapshots_bp = Blueprint('snapshots', __name__)


@snapshots_bp.route('/snapshots', methods=['GET', 'POST'])
@login_required
def manage_snapshots():
    """Get all NDK Application Snapshots or create a new one"""
    if request.method == 'POST':
        # Create a new snapshot
        try:
            data = request.get_json()
            app_name = data.get('applicationName')
            app_namespace = data.get('namespace')
            expires_after = data.get('expiresAfter', '720h')  # Default 30 days
            
            snapshot_info = SnapshotService.create_snapshot(
                app_name, app_namespace, expires_after
            )
            
            # Invalidate cache
            invalidate_cache('snapshots')
            
            return jsonify({
                'success': True,
                'message': f'Snapshot {snapshot_info["name"]} created successfully',
                'snapshot': snapshot_info
            }), 201
            
        except ValueError as e:
            return jsonify({'error': str(e)}), 400
        except ApiException as e:
            error_msg = f"Failed to create snapshot: {e.reason}"
            if e.body:
                try:
                    error_body = json.loads(e.body)
                    error_msg = error_body.get('message', error_msg)
                except:
                    pass
            return jsonify({'error': error_msg}), e.status
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    # GET request - list snapshots
    snapshots = get_cached_or_fetch('snapshots', SnapshotService.list_snapshots)
    return jsonify(snapshots)


@snapshots_bp.route('/snapshots/<namespace>/<name>', methods=['DELETE'])
@login_required
def delete_snapshot(namespace, name):
    """Delete an NDK Application Snapshot"""
    try:
        message = SnapshotService.delete_snapshot(namespace, name)
        
        # Invalidate cache
        invalidate_cache('snapshots')
        
        return jsonify({'message': message}), 200
    except ApiException as e:
        return jsonify({'error': f'Failed to delete snapshot: {e.reason}'}), e.status
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@snapshots_bp.route('/snapshots/<namespace>/<name>/restore', methods=['POST'])
@login_required
def restore_snapshot(namespace, name):
    """Restore an application from a snapshot"""
    try:
        data = request.get_json() or {}
        target_namespace = data.get('targetNamespace')
        
        restore_info = SnapshotService.restore_snapshot(namespace, name, target_namespace)
        
        # Invalidate cache to show new application
        invalidate_cache('applications')
        
        return jsonify({
            'success': True,
            'message': f'Application restored as {restore_info["name"]}',
            'application': restore_info
        }), 201
        
    except ApiException as e:
        error_msg = f"Failed to restore snapshot: {e.reason}"
        if e.body:
            try:
                error_body = json.loads(e.body)
                error_msg = error_body.get('message', error_msg)
            except:
                pass
        return jsonify({'error': error_msg}), e.status
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@snapshots_bp.route('/snapshots/bulk', methods=['POST'])
@login_required
def bulk_create_snapshots():
    """Create snapshots for multiple applications"""
    try:
        data = request.get_json()
        applications = data.get('applications', [])
        expires_after = data.get('expiresAfter', '720h')
        
        if not applications:
            return jsonify({'error': 'No applications provided'}), 400
        
        results = SnapshotService.bulk_create_snapshots(applications, expires_after)
        
        # Invalidate cache
        invalidate_cache('snapshots')
        
        return jsonify({
            'message': f'Created {len(results["successful"])} snapshots, {len(results["failed"])} failed',
            'results': results
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500