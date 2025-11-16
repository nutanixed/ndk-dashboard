"""
Main routes - Dashboard pages and health check
"""
from flask import Blueprint, render_template, jsonify, request
from datetime import datetime
from kubernetes.client.rest import ApiException
from app.utils import login_required, get_cached_or_fetch
from app.extensions import k8s_api, k8s_core_api, with_auth_retry
from config import Config
import json
import os

main_bp = Blueprint('main', __name__)

SETTINGS_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'instance', 'settings.json')

def ensure_settings_file():
    """Ensure settings file exists with defaults"""
    os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
    if not os.path.exists(SETTINGS_FILE):
        default_settings = {
            'features': {
                'deploy': True
            }
        }
        with open(SETTINGS_FILE, 'w') as f:
            json.dump(default_settings, f, indent=2)
    return SETTINGS_FILE

def load_settings():
    """Load settings from file"""
    ensure_settings_file()
    try:
        with open(SETTINGS_FILE, 'r') as f:
            return json.load(f)
    except:
        return {'features': {'deploy': True}}

def save_settings(settings):
    """Save settings to file"""
    ensure_settings_file()
    with open(SETTINGS_FILE, 'w') as f:
        json.dump(settings, f, indent=2)


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
    """Update feature settings"""
    try:
        data = request.get_json()
        settings = load_settings()
        if 'features' in data:
            settings['features'].update(data['features'])
        save_settings(settings)
        return jsonify({'success': True, 'settings': settings})
    except Exception as e:
        return jsonify({'error': str(e)}), 400


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
        import mysql.connector
        
        conn = mysql.connector.connect(
            host='mysql-0.mysql.ndk-dev.svc.cluster.local',
            user='root',
            password='password',
            database='mydb'
        )
        cursor = conn.cursor()
        
        cursor.execute("SHOW TABLES LIKE 'tasks'")
        table_exists = cursor.fetchone() is not None
        
        if table_exists:
            cursor.execute("SELECT COUNT(*) FROM tasks")
            task_count = cursor.fetchone()[0]
        else:
            task_count = 0
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'connected': True,
            'database': 'mydb',
            'table_exists': table_exists,
            'task_count': task_count,
            'status': 'Ready' if table_exists else 'Table Not Found'
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
        
        conn = mysql.connector.connect(
            host='mysql-0.mysql.ndk-dev.svc.cluster.local',
            user='root',
            password='password'
        )
        cursor = conn.cursor()
        
        cursor.execute("CREATE DATABASE IF NOT EXISTS mydb")
        
        conn.close()
        
        conn = mysql.connector.connect(
            host='mysql-0.mysql.ndk-dev.svc.cluster.local',
            user='root',
            password='password',
            database='mydb'
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
        
        conn = mysql.connector.connect(
            host='mysql-0.mysql.ndk-dev.svc.cluster.local',
            user='root',
            password='password',
            database='mydb'
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
        
        conn = mysql.connector.connect(
            host='mysql-0.mysql.ndk-dev.svc.cluster.local',
            user='root',
            password='password',
            database='mydb'
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