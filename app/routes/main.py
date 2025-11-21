"""
Main routes - Dashboard pages and health check
"""
from flask import Blueprint, render_template, jsonify, request
from datetime import datetime
from kubernetes.client.rest import ApiException
from app.utils import login_required, get_cached_or_fetch
from app.extensions import k8s_api, k8s_core_api, k8s_apps_api, with_auth_retry
from config import Config
import json
import os
import time

main_bp = Blueprint('main', __name__)

SETTINGS_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'instance', 'settings.json')
CONFIGMAP_NAME = 'ndk-dashboard-settings'
CONFIGMAP_NAMESPACE = 'ndk-dev'

def ensure_settings_file():
    """Ensure settings file exists with defaults"""
    os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
    if not os.path.exists(SETTINGS_FILE):
        default_settings = {
            'features': {
                'deploy': True
            },
            'taskapp_db': {
                'host': 'mysql-0.mysql.ndk-dev.svc.cluster.local',
                'database_name': 'mydb',
                'password': 'password',
                'pod': 'task-web-app'
            }
        }
        with open(SETTINGS_FILE, 'w') as f:
            json.dump(default_settings, f, indent=2)
    return SETTINGS_FILE

def load_settings_from_configmap():
    """Load settings from Kubernetes ConfigMap"""
    try:
        if not k8s_core_api:
            return None
        
        configmap = k8s_core_api.read_namespaced_config_map(CONFIGMAP_NAME, CONFIGMAP_NAMESPACE)
        data = configmap.data or {}
        settings_json = data.get('settings.json', '{}')
        return json.loads(settings_json)
    except ApiException as e:
        if e.status != 404:
            print(f"Error reading ConfigMap: {e}")
        return None
    except Exception as e:
        print(f"Error loading settings from ConfigMap: {e}")
        return None

def save_settings_to_configmap(settings):
    """Save settings to Kubernetes ConfigMap"""
    try:
        if not k8s_core_api:
            return False
        
        settings_json = json.dumps(settings, indent=2)
        
        try:
            configmap = k8s_core_api.read_namespaced_config_map(CONFIGMAP_NAME, CONFIGMAP_NAMESPACE)
            configmap.data = {'settings.json': settings_json}
            k8s_core_api.patch_namespaced_config_map(CONFIGMAP_NAME, CONFIGMAP_NAMESPACE, configmap)
        except ApiException as e:
            if e.status == 404:
                from kubernetes.client import models as k8s_models
                configmap = k8s_models.V1ConfigMap(
                    metadata=k8s_models.V1ObjectMeta(name=CONFIGMAP_NAME, namespace=CONFIGMAP_NAMESPACE),
                    data={'settings.json': settings_json}
                )
                k8s_core_api.create_namespaced_config_map(CONFIGMAP_NAMESPACE, configmap)
            else:
                raise
        
        return True
    except Exception as e:
        print(f"Error saving settings to ConfigMap: {e}")
        return False

def load_settings():
    """Load settings from ConfigMap or fall back to file"""
    settings = load_settings_from_configmap()
    if settings:
        return settings
    
    ensure_settings_file()
    try:
        with open(SETTINGS_FILE, 'r') as f:
            return json.load(f)
    except:
        return {'features': {'deploy': True}}

def save_settings(settings):
    """Save settings to ConfigMap and file"""
    save_settings_to_configmap(settings)
    
    ensure_settings_file()
    with open(SETTINGS_FILE, 'w') as f:
        json.dump(settings, f, indent=2)


def patch_deployment_env(pod_name, host, database_name, password):
    """Patch deployment with new environment variables"""
    try:
        if not k8s_apps_api:
            return False, "Kubernetes API not available"
        
        deployment = k8s_apps_api.read_namespaced_deployment(
            name=pod_name,
            namespace=CONFIGMAP_NAMESPACE
        )
        
        if not deployment:
            return False, f"Deployment '{pod_name}' not found"
        
        from kubernetes.client import models as k8s_models
        
        container = deployment.spec.template.spec.containers[0]
        new_env = []
        env_names_found = set()
        
        if container.env:
            for env_var in container.env:
                if env_var.name == 'MYSQL_HOST':
                    new_env.append(k8s_models.V1EnvVar(name='MYSQL_HOST', value=host))
                    env_names_found.add('MYSQL_HOST')
                elif env_var.name == 'MYSQL_PASSWORD':
                    new_env.append(k8s_models.V1EnvVar(name='MYSQL_PASSWORD', value=password))
                    env_names_found.add('MYSQL_PASSWORD')
                elif env_var.name == 'MYSQL_DATABASE':
                    new_env.append(k8s_models.V1EnvVar(name='MYSQL_DATABASE', value=database_name))
                    env_names_found.add('MYSQL_DATABASE')
                else:
                    new_env.append(env_var)
        
        if 'MYSQL_HOST' not in env_names_found:
            new_env.append(k8s_models.V1EnvVar(name='MYSQL_HOST', value=host))
        if 'MYSQL_PASSWORD' not in env_names_found:
            new_env.append(k8s_models.V1EnvVar(name='MYSQL_PASSWORD', value=password))
        if 'MYSQL_DATABASE' not in env_names_found:
            new_env.append(k8s_models.V1EnvVar(name='MYSQL_DATABASE', value=database_name))
        
        deployment.spec.template.spec.containers[0].env = new_env
        
        k8s_apps_api.replace_namespaced_deployment(
            name=pod_name,
            namespace=CONFIGMAP_NAMESPACE,
            body=deployment
        )
        
        return True, "Deployment environment variables updated"
    except ApiException as e:
        error_msg = f"Kubernetes API error: {e.status} {e.reason}"
        return False, error_msg
    except Exception as e:
        error_msg = f"Error patching deployment: {str(e)}"
        return False, error_msg


def rollout_restart_deployment(pod_name):
    """Trigger rollout restart for a deployment"""
    try:
        if not k8s_apps_api:
            return False, "Kubernetes API not available"
        
        deployment = k8s_apps_api.read_namespaced_deployment(
            name=pod_name,
            namespace=CONFIGMAP_NAMESPACE
        )
        
        from kubernetes.client import models as k8s_models
        now = datetime.utcnow()
        deployment.spec.template.metadata.annotations = {
            'kubectl.kubernetes.io/restartedAt': now.isoformat() + 'Z'
        }
        
        k8s_apps_api.patch_namespaced_deployment(
            name=pod_name,
            namespace=CONFIGMAP_NAMESPACE,
            body=deployment
        )
        
        return True, "Rollout restart triggered"
    except ApiException as e:
        error_msg = f"Kubernetes API error: {e.status} {e.reason}"
        return False, error_msg
    except Exception as e:
        error_msg = f"Error triggering rollout restart: {str(e)}"
        return False, error_msg


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


@main_bp.route('/resources')
@login_required
def resources():
    """NDK Resources listing page"""
    return render_template('resources.html')


@main_bp.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'version': '3.0.0',
        'kubernetes': k8s_api is not None,
        'timestamp': datetime.now().isoformat()
    })


@main_bp.route('/api/settings', methods=['GET'])
@login_required
def get_settings():
    """Get feature settings"""
    settings = load_settings()
    return jsonify(settings)


@main_bp.route('/api/settings', methods=['POST'])
@login_required
def update_settings():
    """Update feature settings and patch deployments if taskapp_db changes"""
    try:
        data = request.get_json()
        settings = load_settings()
        deployment_patch_results = []
        
        if 'features' in data:
            settings['features'].update(data['features'])
        
        if 'taskapp_db' in data:
            if 'taskapp_db' not in settings:
                settings['taskapp_db'] = {}
            
            new_taskapp_db = data['taskapp_db']
            old_pod = settings['taskapp_db'].get('pod')
            new_pod = new_taskapp_db.get('pod')
            
            settings['taskapp_db'].update(new_taskapp_db)
            
            pod_name = new_taskapp_db.get('pod')
            if pod_name:
                host = new_taskapp_db.get('host', 'mysql-0.mysql.ndk-dev.svc.cluster.local')
                database_name = new_taskapp_db.get('database_name', 'mydb')
                password = new_taskapp_db.get('password', 'password')
                
                patch_success, patch_msg = patch_deployment_env(
                    pod_name, host, database_name, password
                )
                deployment_patch_results.append({
                    'pod': pod_name,
                    'success': patch_success,
                    'message': patch_msg
                })
                
                if patch_success:
                    restart_success, restart_msg = rollout_restart_deployment(pod_name)
                    deployment_patch_results.append({
                        'pod': pod_name,
                        'action': 'restart',
                        'success': restart_success,
                        'message': restart_msg
                    })
        
        save_settings(settings)
        response = {'success': True, 'settings': settings}
        if deployment_patch_results:
            response['deployment_updates'] = deployment_patch_results
        
        return jsonify(response)
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@main_bp.route('/api/public/taskapp-db-settings/<pod_name>', methods=['GET'])
def get_taskapp_db_settings(pod_name):
    """Public endpoint for other pods to fetch taskapp_db settings"""
    try:
        settings = load_settings()
        taskapp_db = settings.get('taskapp_db', {})
        
        if taskapp_db.get('pod') == pod_name:
            return jsonify({
                'success': True,
                'settings': {
                    'host': taskapp_db.get('host', 'mysql-0.mysql.ndk-dev.svc.cluster.local'),
                    'database_name': taskapp_db.get('database_name', 'mydb'),
                    'password': taskapp_db.get('password', 'password')
                }
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Settings not configured for this pod'
            }), 404
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@main_bp.route('/api/stats')
@login_required
def get_stats():
    """Get dashboard statistics"""
    try:
        # Fetch application CRDs
        def fetch_applicationcrds_stats():
            if not k8s_api:
                return []
            
            @with_auth_retry
            def _fetch():
                return k8s_api.list_cluster_custom_object(
                    group=Config.NDK_API_GROUP,
                    version=Config.NDK_API_VERSION,
                    plural='applications'
                )
            
            try:
                result = _fetch()
                return result.get('items', [])
            except ApiException as e:
                print(f"Error fetching application CRDs for stats: {e}")
                return []
        
        # Fetch snapshots
        def fetch_snapshots():
            if not k8s_api:
                return []
            
            @with_auth_retry
            def _fetch():
                return k8s_api.list_cluster_custom_object(
                    group=Config.NDK_API_GROUP,
                    version=Config.NDK_API_VERSION,
                    plural='applicationsnapshots'
                )
            
            try:
                result = _fetch()
                return result.get('items', [])
            except ApiException as e:
                print(f"Error fetching snapshots for stats: {e}")
                return []
        
        # Fetch storage clusters
        def fetch_clusters():
            if not k8s_api:
                return []
            
            @with_auth_retry
            def _fetch():
                return k8s_api.list_cluster_custom_object(
                    group=Config.NDK_API_GROUP,
                    version=Config.NDK_API_VERSION,
                    plural='storageclusters'
                )
            
            try:
                result = _fetch()
                return result.get('items', [])
            except ApiException as e:
                print(f"Error fetching storage clusters for stats: {e}")
                return []
        
        # Fetch protection plans
        def fetch_plans():
            if not k8s_api:
                return []
            
            @with_auth_retry
            def _fetch():
                return k8s_api.list_cluster_custom_object(
                    group=Config.NDK_API_GROUP,
                    version=Config.NDK_API_VERSION,
                    plural='protectionplans'
                )
            
            try:
                result = _fetch()
                return result.get('items', [])
            except ApiException as e:
                print(f"Error fetching protection plans for stats: {e}")
                return []
        
        applicationcrds = get_cached_or_fetch('applicationcrds', fetch_applicationcrds_stats)
        snapshots = get_cached_or_fetch('snapshots', fetch_snapshots)
        clusters = get_cached_or_fetch('storageclusters', fetch_clusters)
        plans = get_cached_or_fetch('protectionplans', fetch_plans)
        
        return jsonify({
            'applications': len(applicationcrds),
            'snapshots': len(snapshots),
            'storageClusters': len(clusters),
            'protectionPlans': len(plans)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@main_bp.route('/api/resources')
@login_required
def resources_api():
    """Get all NDK resources"""
    try:
        def fetch_applicationcrds():
            if not k8s_api:
                return []
            
            @with_auth_retry
            def _fetch():
                return k8s_api.list_cluster_custom_object(
                    group=Config.NDK_API_GROUP,
                    version=Config.NDK_API_VERSION,
                    plural='applications'
                )
            
            try:
                result = _fetch()
                items = []
                for item in result.get('items', []):
                    metadata = item.get('metadata', {})
                    spec = item.get('spec', {})
                    status = item.get('status', {})
                    
                    namespace = metadata.get('namespace', 'default')
                    if namespace in ['kube-system', 'kube-public', 'kube-node-lease', 'ntnx-system']:
                        continue
                    
                    state = 'Unknown'
                    conditions = status.get('conditions', [])
                    for condition in conditions:
                        if condition.get('type') == 'Active':
                            state = 'Active' if condition.get('status') == 'True' else 'Inactive'
                            break
                        elif condition.get('type') == 'Ready':
                            state = 'Ready' if condition.get('status') == 'True' else 'NotReady'
                            break
                    
                    items.append({
                        'type': 'Application',
                        'name': metadata.get('name', 'Unknown'),
                        'namespace': namespace,
                        'created': metadata.get('creationTimestamp', ''),
                        'state': state,
                        'message': status.get('message', '')
                    })
                return items
            except ApiException as e:
                print(f"Error fetching application CRDs: {e}")
                return []
        
        def fetch_snapshots():
            if not k8s_api:
                return []
            
            @with_auth_retry
            def _fetch():
                return k8s_api.list_cluster_custom_object(
                    group=Config.NDK_API_GROUP,
                    version=Config.NDK_API_VERSION,
                    plural='applicationsnapshots'
                )
            
            try:
                result = _fetch()
                items = []
                for item in result.get('items', []):
                    metadata = item.get('metadata', {})
                    status = item.get('status', {})
                    
                    namespace = metadata.get('namespace', 'default')
                    if namespace in ['kube-system', 'kube-public', 'kube-node-lease', 'ntnx-system']:
                        continue
                    
                    ready_to_use = status.get('readyToUse', False)
                    if ready_to_use:
                        state = 'Ready'
                    elif 'readyToUse' in status:
                        state = 'Not Ready'
                    else:
                        state = 'Unknown'
                    
                    items.append({
                        'type': 'ApplicationSnapshot',
                        'name': metadata.get('name', 'Unknown'),
                        'namespace': namespace,
                        'created': metadata.get('creationTimestamp', ''),
                        'state': state,
                        'message': status.get('message', '')
                    })
                return items
            except ApiException as e:
                print(f"Error fetching snapshots: {e}")
                return []
        
        def fetch_plans():
            if not k8s_api:
                return []
            
            @with_auth_retry
            def _fetch():
                return k8s_api.list_cluster_custom_object(
                    group=Config.NDK_API_GROUP,
                    version=Config.NDK_API_VERSION,
                    plural='protectionplans'
                )
            
            try:
                result = _fetch()
                items = []
                for item in result.get('items', []):
                    metadata = item.get('metadata', {})
                    spec = item.get('spec', {})
                    status = item.get('status', {})
                    
                    namespace = metadata.get('namespace', 'default')
                    if namespace in ['kube-system', 'kube-public', 'kube-node-lease', 'ntnx-system']:
                        continue
                    
                    items.append({
                        'type': 'ProtectionPlan',
                        'name': metadata.get('name', 'Unknown'),
                        'namespace': namespace,
                        'created': metadata.get('creationTimestamp', ''),
                        'state': 'Ready',
                        'message': ''
                    })
                return items
            except ApiException as e:
                print(f"Error fetching protection plans: {e}")
                return []
        
        def fetch_clusters():
            if not k8s_api:
                return []
            
            @with_auth_retry
            def _fetch():
                return k8s_api.list_cluster_custom_object(
                    group=Config.NDK_API_GROUP,
                    version=Config.NDK_API_VERSION,
                    plural='storageclusters'
                )
            
            try:
                result = _fetch()
                items = []
                for item in result.get('items', []):
                    metadata = item.get('metadata', {})
                    status = item.get('status', {})
                    
                    namespace = metadata.get('namespace', 'default')
                    if namespace in ['kube-system', 'kube-public', 'kube-node-lease', 'ntnx-system']:
                        continue
                    
                    state = 'Unknown'
                    
                    available = status.get('available', False)
                    if available:
                        state = 'Ready'
                    else:
                        state = 'Not Ready'
                    
                    items.append({
                        'type': 'StorageCluster',
                        'name': metadata.get('name', 'Unknown'),
                        'namespace': namespace,
                        'created': metadata.get('creationTimestamp', ''),
                        'state': state,
                        'message': status.get('message', '')
                    })
                return items
            except ApiException as e:
                print(f"Error fetching storage clusters: {e}")
                return []
        
        def fetch_restores():
            if not k8s_api:
                return []
            
            @with_auth_retry
            def _fetch():
                return k8s_api.list_cluster_custom_object(
                    group=Config.NDK_API_GROUP,
                    version=Config.NDK_API_VERSION,
                    plural='applicationsnapshotrestores'
                )
            
            try:
                result = _fetch()
                items = []
                for item in result.get('items', []):
                    metadata = item.get('metadata', {})
                    spec = item.get('spec', {})
                    status = item.get('status', {})
                    
                    namespace = metadata.get('namespace', 'default')
                    if namespace in ['kube-system', 'kube-public', 'kube-node-lease', 'ntnx-system']:
                        continue
                    
                    is_completed = status.get('completed', False)
                    conditions = status.get('conditions', [])
                    state = 'Unknown'
                    
                    if is_completed:
                        failed = False
                        for condition in conditions:
                            if condition.get('type') == 'Failed' and condition.get('status') == 'True':
                                state = 'Failed'
                                failed = True
                                break
                        
                        if not failed:
                            for condition in conditions:
                                if condition.get('type') == 'ApplicationRestoreFinalised':
                                    if condition.get('status') == 'True':
                                        state = 'Successful'
                                    break
                            if state == 'Unknown':
                                state = 'Successful'
                    else:
                        state = 'InProgress'
                    
                    snapshot_ref = spec.get('snapshotName', '')
                    
                    items.append({
                        'type': 'ApplicationSnapshotRestore',
                        'name': metadata.get('name', 'Unknown'),
                        'namespace': namespace,
                        'snapshot': snapshot_ref,
                        'created': metadata.get('creationTimestamp', ''),
                        'state': state,
                        'message': ''
                    })
                return items
            except ApiException as e:
                print(f"Error fetching application snapshot restores: {e}")
                return []
        
        def fetch_pvcs():
            if not k8s_core_api:
                return []
            
            items = []
            try:
                @with_auth_retry
                def _fetch_all_pvcs():
                    return k8s_core_api.list_persistent_volume_claim_for_all_namespaces()
                
                pvcs = _fetch_all_pvcs()
                for pvc in (pvcs.items if hasattr(pvcs, 'items') else []):
                    namespace = pvc.metadata.namespace
                    if namespace in ['kube-system', 'kube-public', 'kube-node-lease', 'ntnx-system']:
                        continue
                    
                    volume_name = pvc.spec.volume_name or 'Pending' if pvc.spec else 'Pending'
                    capacity = pvc.status.capacity.get('storage', 'Unknown') if pvc.status and pvc.status.capacity else 'Pending'
                    storage_class = pvc.spec.storage_class_name or 'default' if pvc.spec else 'default'
                    status = pvc.status.phase if pvc.status else 'Unknown'
                    
                    items.append({
                        'type': 'PVC',
                        'name': pvc.metadata.name,
                        'namespace': namespace,
                        'status': status,
                        'volume': volume_name,
                        'capacity': capacity,
                        'storageClass': storage_class,
                        'age': pvc.metadata.creation_timestamp.isoformat() if pvc.metadata.creation_timestamp else ''
                    })
                
                return items
            except ApiException as e:
                print(f"Error fetching PVCs: {e}")
                return []
        
        def fetch_volume_snapshots():
            if not k8s_api:
                return []
            
            @with_auth_retry
            def _fetch():
                return k8s_api.list_cluster_custom_object(
                    group='snapshot.storage.k8s.io',
                    version='v1',
                    plural='volumesnapshots'
                )
            
            try:
                result = _fetch()
                items = []
                for item in result.get('items', []):
                    metadata = item.get('metadata', {})
                    spec = item.get('spec', {})
                    status = item.get('status', {})
                    
                    namespace = metadata.get('namespace', 'default')
                    if namespace in ['kube-system', 'kube-public', 'kube-node-lease', 'ntnx-system']:
                        continue
                    
                    ready_to_use = status.get('readyToUse', False)
                    state = 'Ready' if ready_to_use else 'Pending'
                    
                    items.append({
                        'type': 'VolumeSnapshot',
                        'name': metadata.get('name', 'Unknown'),
                        'namespace': namespace,
                        'created': metadata.get('creationTimestamp', ''),
                        'state': state,
                        'message': ''
                    })
                return items
            except ApiException as e:
                print(f"Error fetching volume snapshots: {e.status} {e.reason}")
                return []
            except Exception as e:
                print(f"Error fetching volume snapshots: {e}")
                return []
        
        def fetch_pvs():
            if not k8s_core_api:
                return []
            
            items = []
            try:
                @with_auth_retry
                def _fetch_all_pvs():
                    return k8s_core_api.list_persistent_volume()
                
                pvs = _fetch_all_pvs()
                for pv in (pvs.items if hasattr(pvs, 'items') else []):
                    capacity = pv.spec.capacity.get('storage', 'Unknown') if pv.spec and pv.spec.capacity else 'Unknown'
                    access_modes = ','.join(pv.spec.access_modes) if pv.spec and pv.spec.access_modes else ''
                    reclaim_policy = pv.spec.persistent_volume_reclaim_policy or 'Unknown' if pv.spec else 'Unknown'
                    storage_class = pv.spec.storage_class_name or 'default' if pv.spec else 'default'
                    status = pv.status.phase if pv.status else 'Unknown'
                    
                    claim_name = pv.spec.claim_ref.name if pv.spec and pv.spec.claim_ref else '-'
                    
                    items.append({
                        'name': pv.metadata.name,
                        'capacity': capacity,
                        'accessModes': access_modes,
                        'reclaimPolicy': reclaim_policy,
                        'status': status,
                        'claim': claim_name,
                        'storageClass': storage_class,
                        'age': pv.metadata.creation_timestamp.isoformat() if pv.metadata.creation_timestamp else ''
                    })
                
                return items
            except ApiException as e:
                print(f"Error fetching PVs: {e}")
                return []
        
        applicationcrds = get_cached_or_fetch('applicationcrds', fetch_applicationcrds)
        snapshots = get_cached_or_fetch('snapshots', fetch_snapshots)
        plans = get_cached_or_fetch('protectionplans', fetch_plans)
        clusters = get_cached_or_fetch('storageclusters', fetch_clusters)
        restores = get_cached_or_fetch('applicationsnapshotrestores', fetch_restores)
        pvcs = get_cached_or_fetch('persistentvolumeclaims', fetch_pvcs)
        pvs = get_cached_or_fetch('persistentvolumes', fetch_pvs)
        volume_snapshots = get_cached_or_fetch('volumesnapshots', fetch_volume_snapshots)
        
        return jsonify({
            'applicationCRDs': applicationcrds,
            'snapshots': snapshots,
            'protectionPlans': plans,
            'storageClusters': clusters,
            'applicationSnapshotRestores': restores,
            'persistentVolumeClaims': pvcs,
            'persistentVolumes': pvs,
            'volumeSnapshots': volume_snapshots
        })
    except Exception as e:
        print(f"Error in resources_api: {e}")
        return jsonify({'error': str(e)}), 500


@main_bp.route('/api/taskapp/db/status', methods=['GET'])
@login_required
def get_taskapp_db_status():
    """Check Task App database connection and schema status"""
    try:
        settings = load_settings()
        db_config = settings.get('taskapp_db', {})
        pod_name = db_config.get('pod', 'task-web-app')
        db_name = db_config.get('database_name', 'mydb')
        
        if k8s_apps_api and pod_name:
            try:
                deployment = k8s_apps_api.read_namespaced_deployment(pod_name, CONFIGMAP_NAMESPACE)
                if not (deployment.status.ready_replicas and deployment.status.ready_replicas > 0):
                    ready = deployment.status.ready_replicas or 0
                    desired = deployment.spec.replicas or 0
                    return jsonify({
                        'connected': False,
                        'error': f'Deployment "{pod_name}" not ready: {ready}/{desired} replicas',
                        'status': 'Error'
                    }), 500
            except ApiException:
                return jsonify({
                    'connected': False,
                    'error': f'Deployment "{pod_name}" not found',
                    'status': 'Error'
                }), 500
        else:
            return jsonify({
                'connected': False,
                'error': f'Deployment "{pod_name}" not configured',
                'status': 'Error'
            }), 500
        
        return jsonify({
            'connected': True,
            'database': db_name,
            'status': 'Pod Ready'
        })
    except Exception as e:
        return jsonify({
            'connected': False,
            'error': str(e),
            'status': 'Error'
        }), 500


@main_bp.route('/api/taskapp/db/create', methods=['POST'])
@login_required
def create_taskapp_db():
    """Create Task App database and tasks table"""
    try:
        import mysql.connector
        
        settings = load_settings()
        db_config = settings.get('taskapp_db', {})
        db_host = db_config.get('host', 'mysql-0.mysql.ndk-dev.svc.cluster.local')
        db_user = db_config.get('username', 'root')
        db_name = db_config.get('database_name', 'mydb')
        db_pass = db_config.get('password', 'password')
        
        conn = mysql.connector.connect(
            host=db_host,
            user=db_user,
            password=db_pass
        )
        cursor = conn.cursor()
        
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {db_name}")
        
        conn.close()
        
        conn = mysql.connector.connect(
            host=db_host,
            user=db_user,
            password=db_pass,
            database=db_name
        )
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tasks (
                id INT AUTO_INCREMENT PRIMARY KEY,
                title VARCHAR(255) NOT NULL,
                description TEXT,
                priority ENUM('low', 'medium', 'high', 'critical') DEFAULT 'medium',
                status ENUM('todo', 'in_progress', 'completed', 'cancelled') DEFAULT 'todo',
                category VARCHAR(100),
                due_date DATE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_status (status),
                INDEX idx_priority (priority),
                INDEX idx_due_date (due_date)
            )
        ''')
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Database and tasks table created successfully'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@main_bp.route('/api/taskapp/db/clear', methods=['POST'])
@login_required
def clear_taskapp_db():
    """Clear all tasks from the database"""
    try:
        import mysql.connector
        
        settings = load_settings()
        db_config = settings.get('taskapp_db', {})
        db_host = db_config.get('host', 'mysql-0.mysql.ndk-dev.svc.cluster.local')
        db_user = db_config.get('username', 'root')
        db_name = db_config.get('database_name', 'mydb')
        db_pass = db_config.get('password', 'password')
        
        conn = mysql.connector.connect(
            host=db_host,
            user=db_user,
            password=db_pass,
            database=db_name
        )
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM tasks")
        conn.commit()
        
        cursor.execute("SELECT COUNT(*) FROM tasks")
        remaining = cursor.fetchone()[0]
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'All tasks cleared successfully',
            'remaining': remaining
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@main_bp.route('/api/taskapp/db/stats', methods=['GET'])
@login_required
def get_taskapp_db_stats():
    """Get Task App database statistics"""
    try:
        import mysql.connector
        
        settings = load_settings()
        db_config = settings.get('taskapp_db', {})
        db_host = db_config.get('host', 'mysql-0.mysql.ndk-dev.svc.cluster.local')
        db_user = db_config.get('username', 'root')
        db_name = db_config.get('database_name', 'mydb')
        db_pass = db_config.get('password', 'password')
        
        conn = mysql.connector.connect(
            host=db_host,
            user=db_user,
            password=db_pass,
            database=db_name
        )
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM tasks")
        total = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM tasks WHERE status = 'completed'")
        completed = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM tasks WHERE status IN ('todo', 'in_progress')")
        pending = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM tasks WHERE status != 'completed' AND due_date < CURDATE()")
        overdue = cursor.fetchone()[0]
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'total': total,
            'completed': completed,
            'pending': pending,
            'overdue': overdue
        })
    except Exception as e:
        return jsonify({
            'error': str(e)
        }), 500

@main_bp.route('/api/deployments', methods=['GET'])
def get_deployments():
    try:
        if not k8s_apps_api:
            return jsonify({'error': 'Kubernetes API not available'}), 503
        
        deployments = k8s_apps_api.list_namespaced_deployment('ndk-dev')
        apps = [dep.metadata.name for dep in deployments.items]
        
        return jsonify({'deployments': sorted(apps)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@main_bp.route('/api/protectionplans/<namespace>/<name>/applications', methods=['GET'])
def get_protection_plan_applications(namespace, name):
    try:
        from app.services.protection_plans import ProtectionPlanService
        plan = ProtectionPlanService.get_protection_plan(namespace, name)
        
        applications = plan.get('applications', [])
        formatted_apps = []
        
        for app in applications:
            if isinstance(app, dict):
                formatted_apps.append({
                    'name': app.get('name', 'Unknown'),
                    'namespace': app.get('namespace', namespace)
                })
            else:
                formatted_apps.append({
                    'name': app,
                    'namespace': namespace
                })
        
        return jsonify({'applications': formatted_apps})
    except Exception as e:
        return jsonify({'error': str(e)}), 500