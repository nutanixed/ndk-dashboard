"""
Protection Plans routes - API endpoints for NDK Protection Plans
"""
from flask import Blueprint, jsonify, request
from kubernetes.client.rest import ApiException
from datetime import datetime
import json
from app.utils import login_required, get_cached_or_fetch, invalidate_cache
from app.services import ProtectionPlanService
from app.extensions import k8s_api
from config import Config

protectionplans_bp = Blueprint('protectionplans', __name__)


@protectionplans_bp.route('/protectionplans', methods=['GET', 'POST'])
@login_required
def manage_protectionplans():
    """Get all NDK Protection Plans or create a new one"""
    if request.method == 'POST':
        # Create a new protection plan
        try:
            data = request.get_json()
            name = data.get('name')
            namespace = data.get('namespace')
            schedule = data.get('schedule')
            retention = data.get('retention')
            applications = data.get('applications', [])
            selection_mode = data.get('selectionMode', 'by-name')
            
            # Handle label selector - can be nested object or separate fields
            label_selector = data.get('labelSelector', {})
            label_selector_key = label_selector.get('key') if label_selector else data.get('labelSelectorKey')
            label_selector_value = label_selector.get('value') if label_selector else data.get('labelSelectorValue')
            
            if not all([name, namespace, schedule, retention]):
                return jsonify({'error': 'Missing required fields'}), 400
            
            plan_info = ProtectionPlanService.create_protection_plan(
                namespace, name, schedule, retention, applications,
                selection_mode, label_selector_key, label_selector_value
            )
            
            # Invalidate cache
            invalidate_cache('protectionplans')
            
            return jsonify({
                'success': True,
                'message': f'Protection plan {name} created successfully',
                'plan': plan_info
            }), 201
            
        except ApiException as e:
            error_msg = f"Failed to create protection plan: {e.reason}"
            if e.body:
                try:
                    error_body = json.loads(e.body)
                    error_msg = error_body.get('message', error_msg)
                except:
                    pass
            return jsonify({'error': error_msg}), e.status
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    # GET request - list protection plans
    plans = get_cached_or_fetch('protectionplans', ProtectionPlanService.list_protection_plans)
    return jsonify(plans)


@protectionplans_bp.route('/protectionplans/<namespace>/<name>', methods=['GET', 'DELETE', 'PUT'])
@login_required
def manage_protection_plan(namespace, name):
    """Get, update, or delete a specific protection plan"""
    if request.method == 'GET':
        try:
            plan = ProtectionPlanService.get_protection_plan(namespace, name)
            return jsonify(plan), 200
        except ApiException as e:
            return jsonify({'error': f'Failed to get protection plan: {e.reason}'}), e.status
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    elif request.method == 'DELETE':
        try:
            force = request.args.get('force', 'false').lower() == 'true'
            message = ProtectionPlanService.delete_protection_plan(namespace, name, force)
            
            # Invalidate cache
            invalidate_cache('protectionplans')
            
            return jsonify({'message': message}), 200
        except ApiException as e:
            return jsonify({'error': f'Failed to delete protection plan: {e.reason}'}), e.status
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    elif request.method == 'PUT':
        try:
            data = request.get_json()
            updates = {}
            
            # Handle suspend/resume
            if 'suspend' in data:
                updates['suspend'] = data['suspend']
            
            result = ProtectionPlanService.update_protection_plan(namespace, name, updates)
            
            # Invalidate cache
            invalidate_cache('protectionplans')
            
            return jsonify({
                'message': 'Protection plan updated successfully',
                'plan': result
            }), 200
        except ApiException as e:
            return jsonify({'error': f'Failed to update protection plan: {e.reason}'}), e.status
        except Exception as e:
            return jsonify({'error': str(e)}), 500


@protectionplans_bp.route('/protectionplans/<namespace>/<name>/enable', methods=['POST'])
@login_required
def enable_protection_plan(namespace, name):
    """Enable (resume) a protection plan"""
    try:
        ProtectionPlanService.update_protection_plan(namespace, name, {'suspend': False})
        
        # Invalidate cache
        invalidate_cache('protectionplans')
        
        return jsonify({'message': f'Protection plan {name} enabled'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@protectionplans_bp.route('/protectionplans/<namespace>/<name>/disable', methods=['POST'])
@login_required
def disable_protection_plan(namespace, name):
    """Disable (suspend) a protection plan"""
    try:
        ProtectionPlanService.update_protection_plan(namespace, name, {'suspend': True})
        
        # Invalidate cache
        invalidate_cache('protectionplans')
        
        return jsonify({'message': f'Protection plan {name} disabled'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@protectionplans_bp.route('/protectionplans/<namespace>/<name>/trigger', methods=['POST'])
@login_required
def trigger_protection_plan(namespace, name):
    """Manually trigger a protection plan to create a snapshot now"""
    try:
        print(f"\n=== Triggering Protection Plan: {name} in namespace {namespace} ===")
        
        if not k8s_api:
            return jsonify({'error': 'Kubernetes API not available'}), 503
        
        # Get the protection plan to extract retention policy
        plan = k8s_api.get_namespaced_custom_object(
            group=Config.NDK_API_GROUP,
            version=Config.NDK_API_VERSION,
            namespace=namespace,
            plural='protectionplans',
            name=name
        )
        
        spec = plan.get('spec', {})
        retention_policy = spec.get('retentionPolicy', {})
        metadata = plan.get('metadata', {})
        annotations = metadata.get('annotations', {})
        
        import sys
        print(f"DEBUG: Plan metadata: {metadata}", file=sys.stderr, flush=True)
        print(f"DEBUG: Annotations: {annotations}", file=sys.stderr, flush=True)
        
        # Convert retention to expiresAfter format
        # If retentionCount is specified, use default 30 days
        # If maxAge is specified, use that value
        if 'maxAge' in retention_policy:
            expires_after = retention_policy['maxAge']
        else:
            # Default to 30 days for count-based retention
            expires_after = '720h'
        
        # Determine selection mode from annotations
        selection_mode = annotations.get('ndk-dashboard/selection-mode', 'by-name')
        print(f"  Selection mode: {selection_mode}")
        
        # Find applications protected by this plan
        # Use a set to track unique app+namespace combinations to avoid duplicates
        protected_apps = []
        seen_apps = set()
        
        if selection_mode == 'by-label':
            # Label-based selection: query applications with matching labels
            label_key = annotations.get('ndk-dashboard/label-selector-key')
            label_value = annotations.get('ndk-dashboard/label-selector-value')
            
            if not label_key or not label_value:
                return jsonify({
                    'error': f'Protection plan is configured for label-based selection but label selector is missing'
                }), 400
            
            print(f"  Using label selector: {label_key}={label_value}")
            
            # Get all applications in the namespace
            applications = k8s_api.list_namespaced_custom_object(
                group=Config.NDK_API_GROUP,
                version=Config.NDK_API_VERSION,
                namespace=namespace,
                plural='applications'
            )
            
            # Filter applications by label
            for app in applications.get('items', []):
                app_metadata = app.get('metadata', {})
                app_labels = app_metadata.get('labels', {})
                app_name = app_metadata.get('name')
                app_namespace = app_metadata.get('namespace')
                
                # Check if application has matching label
                if app_labels.get(label_key) == label_value:
                    app_key = f"{app_namespace}/{app_name}"
                    if app_key not in seen_apps:
                        seen_apps.add(app_key)
                        protected_apps.append({
                            'name': app_name,
                            'namespace': app_namespace
                        })
                        print(f"  Found matching app: {app_name} in namespace {app_namespace}")
        else:
            # By-name selection: use AppProtectionPlan resources
            app_protection_plans = k8s_api.list_namespaced_custom_object(
                group=Config.NDK_API_GROUP,
                version=Config.NDK_API_VERSION,
                namespace=namespace,
                plural='appprotectionplans'
            )
            
            for app_plan in app_protection_plans.get('items', []):
                app_plan_spec = app_plan.get('spec', {})
                plan_names = app_plan_spec.get('protectionPlanNames', [])
                
                # Check if this AppProtectionPlan references our ProtectionPlan
                if name in plan_names:
                    app_name = app_plan_spec.get('applicationName')
                    app_namespace = app_plan.get('metadata', {}).get('namespace')
                    
                    if app_name and app_namespace:
                        # Create unique key to prevent duplicates
                        app_key = f"{app_namespace}/{app_name}"
                        
                        if app_key not in seen_apps:
                            seen_apps.add(app_key)
                            protected_apps.append({
                                'name': app_name,
                                'namespace': app_namespace
                            })
                            print(f"  Found protected app: {app_name} in namespace {app_namespace}")
                        else:
                            print(f"  Skipping duplicate: {app_name} in namespace {app_namespace}")
        
        if not protected_apps:
            if selection_mode == 'by-label':
                label_key = annotations.get('ndk-dashboard/label-selector-key')
                label_value = annotations.get('ndk-dashboard/label-selector-value')
                return jsonify({
                    'error': f'No applications found with label {label_key}={label_value} in namespace {namespace}'
                }), 404
            else:
                return jsonify({
                    'error': f'No applications are protected by this plan. Create AppProtectionPlan resources to link applications to this protection plan.'
                }), 404
        
        # Create snapshots for protected applications
        timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        created_snapshots = []
        failed_snapshots = []
        
        for app in protected_apps:
            snapshot_name = f"{app['name']}-{name}-{timestamp}"
            
            snapshot_manifest = {
                'apiVersion': f'{Config.NDK_API_GROUP}/{Config.NDK_API_VERSION}',
                'kind': 'ApplicationSnapshot',
                'metadata': {
                    'name': snapshot_name,
                    'namespace': app['namespace'],
                    'labels': {
                        'protectionplan': name,
                        'triggered-manually': 'true'
                    }
                },
                'spec': {
                    'source': {
                        'applicationRef': {
                            'name': app['name']
                        }
                    },
                    'expiresAfter': expires_after
                }
            }
            
            try:
                k8s_api.create_namespaced_custom_object(
                    group=Config.NDK_API_GROUP,
                    version=Config.NDK_API_VERSION,
                    namespace=app['namespace'],
                    plural='applicationsnapshots',
                    body=snapshot_manifest
                )
                created_snapshots.append(f"{app['name']} ({app['namespace']})")
                print(f"✓ Created snapshot {snapshot_name} for {app['name']} in {app['namespace']}")
            except Exception as e:
                error_msg = f"{app['name']} ({app['namespace']}): {str(e)}"
                failed_snapshots.append(error_msg)
                print(f"✗ Failed to create snapshot for {app['name']}: {e}")
        
        # Invalidate caches
        invalidate_cache('snapshots', 'protectionplans')
        
        message = f'Created {len(created_snapshots)} snapshot(s) for protection plan "{name}"'
        if created_snapshots:
            message += f': {", ".join(created_snapshots)}'
        if failed_snapshots:
            message += f'. Failed: {", ".join(failed_snapshots)}'
        
        return jsonify({
            'success': True,
            'message': message,
            'snapshots': created_snapshots,
            'failed': failed_snapshots
        }), 201
        
    except ApiException as e:
        return jsonify({'error': f'Failed to trigger protection plan: {e.reason}'}), e.status
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@protectionplans_bp.route('/protectionplans/<namespace>/<name>/history')
@login_required
def get_protection_plan_history(namespace, name):
    """Get snapshots created by a protection plan"""
    try:
        if not k8s_api:
            return jsonify({'error': 'Kubernetes API not available'}), 503
        
        # Get all snapshots with the protection plan label
        result = k8s_api.list_cluster_custom_object(
            group=Config.NDK_API_GROUP,
            version=Config.NDK_API_VERSION,
            plural='applicationsnapshots',
            label_selector=f'protectionplan={name}'
        )
        
        snapshots = []
        for item in result.get('items', []):
            metadata = item.get('metadata', {})
            spec = item.get('spec', {})
            status = item.get('status', {})
            
            # Only include snapshots from the same namespace
            if metadata.get('namespace') == namespace:
                ready_to_use = status.get('readyToUse', False)
                state = 'Ready' if ready_to_use else 'Creating'
                
                snapshots.append({
                    'name': metadata.get('name', 'Unknown'),
                    'namespace': metadata.get('namespace', 'default'),
                    'created': metadata.get('creationTimestamp', ''),
                    'expiresAfter': spec.get('expiresAfter', 'Not set'),
                    'state': state
                })
        
        # Sort by creation time (newest first)
        snapshots.sort(key=lambda x: x['created'], reverse=True)
        
        return jsonify(snapshots), 200
        
    except ApiException as e:
        return jsonify({'error': f'Failed to get history: {e.reason}'}), e.status
    except Exception as e:
        return jsonify({'error': str(e)}), 500