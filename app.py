"""
NDK Dashboard - Flask Application
Displays Nutanix Data Services for Kubernetes resources
"""
from flask import Flask, render_template, jsonify, session, redirect, url_for, request
from functools import wraps
from datetime import datetime, timedelta
import os
import re
import time
from kubernetes import client, config as k8s_config
from kubernetes.client.rest import ApiException
from config import Config

app = Flask(__name__)
app.config.from_object(Config)

# Cache buster for static files (timestamp when app starts)
CACHE_BUST_VERSION = str(int(datetime.now().timestamp()))

# Initialize Kubernetes client
try:
    if Config.IN_CLUSTER:
        k8s_config.load_incluster_config()
        print("✓ Loaded in-cluster Kubernetes configuration")
    else:
        k8s_config.load_kube_config()
        print("✓ Loaded kubeconfig from local system")
    
    k8s_api = client.CustomObjectsApi()
    k8s_core_api = client.CoreV1Api()
    print("✓ Kubernetes API client initialized")
except Exception as e:
    print(f"✗ Failed to initialize Kubernetes client: {e}")
    k8s_api = None
    k8s_core_api = None

# Cache for API responses
cache = {
    'applications': {'data': None, 'timestamp': None},
    'snapshots': {'data': None, 'timestamp': None},
    'storageclusters': {'data': None, 'timestamp': None},
    'protectionplans': {'data': None, 'timestamp': None}
}

def login_required(f):
    """Decorator to require login for routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            # For API endpoints, return JSON error instead of redirect
            if request.path.startswith('/api/'):
                return jsonify({'error': 'Authentication required'}), 401
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def get_cached_or_fetch(cache_key, fetch_function):
    """Get data from cache or fetch if expired"""
    now = datetime.now()
    cached = cache.get(cache_key)
    
    if cached['data'] is not None and cached['timestamp'] is not None:
        age = (now - cached['timestamp']).total_seconds()
        if age < Config.CACHE_TTL:
            return cached['data']
    
    # Fetch fresh data
    try:
        data = fetch_function()
        cache[cache_key] = {'data': data, 'timestamp': now}
        return data
    except Exception as e:
        print(f"Error fetching {cache_key}: {e}")
        # Return cached data even if expired, or empty list
        return cached['data'] if cached['data'] is not None else []

@app.route('/')
@login_required
def index():
    """Main dashboard page"""
    return render_template('index.html', cache_bust=CACHE_BUST_VERSION)

@app.route('/admin')
@login_required
def admin():
    """Admin page for managing applications and protection plans"""
    return render_template('admin.html', cache_bust=CACHE_BUST_VERSION)

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page"""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if username == Config.DASHBOARD_USERNAME and password == Config.DASHBOARD_PASSWORD:
            session['logged_in'] = True
            session.permanent = True
            return redirect(url_for('index'))
        else:
            return render_template('login.html', error='Invalid credentials')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    """Logout"""
    session.clear()
    return redirect(url_for('login'))

@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'kubernetes': k8s_api is not None,
        'timestamp': datetime.now().isoformat()
    })

# API Routes for NDK resources

@app.route('/api/applications')
@login_required
def get_applications():
    """Get all NDK Applications from non-system namespaces"""
    def fetch():
        if not k8s_api:
            return []
        
        # System namespaces to exclude
        SYSTEM_NAMESPACES = {
            'kube-system', 'kube-public', 'kube-node-lease', 
            'ntnx-system'
        }
        
        try:
            result = k8s_api.list_cluster_custom_object(
                group=Config.NDK_API_GROUP,
                version=Config.NDK_API_VERSION,
                plural='applications'
            )
            
            applications = []
            all_namespaces = set()
            
            for item in result.get('items', []):
                metadata = item.get('metadata', {})
                spec = item.get('spec', {})
                status = item.get('status', {})
                
                namespace = metadata.get('namespace', 'default')
                all_namespaces.add(namespace)
                
                # Skip system namespaces
                if namespace in SYSTEM_NAMESPACES:
                    continue
                
                # Extract state from conditions
                state = 'Unknown'
                message = ''
                conditions = status.get('conditions', [])
                if conditions:
                    # Get the first condition (usually Active)
                    condition = conditions[0]
                    if condition.get('status') == 'True':
                        state = condition.get('type', 'Unknown')
                    else:
                        state = f"Not {condition.get('type', 'Unknown')}"
                    message = condition.get('message', '')
                
                # Extract labels (excluding system labels)
                all_labels = metadata.get('labels', {})
                # Filter out common system labels
                system_label_prefixes = ['kubectl.kubernetes.io/', 'kubernetes.io/', 'k8s.io/']
                user_labels = {k: v for k, v in all_labels.items() 
                              if not any(k.startswith(prefix) for prefix in system_label_prefixes)}
                
                applications.append({
                    'name': metadata.get('name', 'Unknown'),
                    'namespace': namespace,
                    'created': metadata.get('creationTimestamp', ''),
                    'selector': spec.get('applicationSelector', {}),
                    'state': state,
                    'message': message,
                    'lastSnapshot': status.get('lastSnapshotTime', 'Never'),
                    'labels': user_labels
                })
            
            print(f"✓ Found {len(applications)} applications across {len(all_namespaces)} namespaces")
            print(f"  All namespaces: {sorted(all_namespaces)}")
            print(f"  Non-system apps: {len(applications)}")
            
            return applications
        except ApiException as e:
            print(f"✗ Error fetching applications: {e}")
            return []
    
    return jsonify(get_cached_or_fetch('applications', fetch))

@app.route('/api/applications/<namespace>/<name>', methods=['GET', 'DELETE'])
@login_required
def manage_application(namespace, name):
    """Get or delete a single NDK Application"""
    if request.method == 'GET':
        if not k8s_api:
            return jsonify({'error': 'Kubernetes API not available'}), 500
        
        try:
            result = k8s_api.get_namespaced_custom_object(
                group=Config.NDK_API_GROUP,
                version=Config.NDK_API_VERSION,
                namespace=namespace,
                plural='applications',
                name=name
            )
            
            metadata = result.get('metadata', {})
            labels = metadata.get('labels', {})
            
            # Filter out system labels
            filtered_labels = {k: v for k, v in labels.items() 
                              if not k.startswith('kubectl.kubernetes.io/')}
            
            return jsonify({
                'name': metadata.get('name'),
                'namespace': metadata.get('namespace'),
                'labels': filtered_labels
            })
        except ApiException as e:
            return jsonify({'error': f'Application not found: {e}'}), 404
    
    elif request.method == 'DELETE':
        if not k8s_api:
            return jsonify({'error': 'Kubernetes API not available'}), 500
        
        try:
            import time
            force = request.args.get('force', 'false').lower() == 'true'
            app_only = request.args.get('app_only', 'false').lower() == 'true'
            cleanup_log = []
            
            # If app_only mode, skip all cleanup and just delete the Application CRD
            if app_only:
                print(f"🔄 Deleting Application CRD only (preserving snapshots & data): {namespace}/{name}")
                
                # Remove finalizers if present
                try:
                    app = k8s_api.get_namespaced_custom_object(
                        group=Config.NDK_API_GROUP,
                        version=Config.NDK_API_VERSION,
                        namespace=namespace,
                        plural='applications',
                        name=name
                    )
                    
                    if app.get('metadata', {}).get('finalizers'):
                        k8s_api.patch_namespaced_custom_object(
                            group=Config.NDK_API_GROUP,
                            version=Config.NDK_API_VERSION,
                            namespace=namespace,
                            plural='applications',
                            name=name,
                            body={'metadata': {'finalizers': []}}
                        )
                        cleanup_log.append("Removed finalizers from Application")
                except ApiException as e:
                    if e.status != 404:
                        cleanup_log.append(f"Warning: Could not remove finalizers: {e.reason}")
                
                # Delete the Application CRD
                k8s_api.delete_namespaced_custom_object(
                    group=Config.NDK_API_GROUP,
                    version=Config.NDK_API_VERSION,
                    namespace=namespace,
                    plural='applications',
                    name=name
                )
                
                cleanup_log.append(f"✓ Deleted Application CRD: {name}")
                cleanup_log.append("✓ Preserved all snapshots")
                cleanup_log.append("✓ Preserved all PVCs and data")
                cleanup_log.append("✓ Preserved protection plans")
                
                print(f"✓ Application CRD deleted (restore test mode): {namespace}/{name}")
                
                # Invalidate cache
                cache['applications'] = {'data': None, 'timestamp': None}
                
                return jsonify({
                    'message': 'Application deleted (snapshots & data preserved)',
                    'cleanup_log': cleanup_log
                }), 200
            
            # Step 1: Delete all snapshots associated with this application
            try:
                snapshots = k8s_api.list_namespaced_custom_object(
                    group=Config.NDK_API_GROUP,
                    version=Config.NDK_API_VERSION,
                    namespace=namespace,
                    plural='applicationsnapshots'
                )
                
                deleted_snapshots = 0
                for snapshot in snapshots.get('items', []):
                    snapshot_metadata = snapshot.get('metadata', {})
                    snapshot_spec = snapshot.get('spec', {})
                    snapshot_name = snapshot_metadata.get('name')
                    
                    # Check if this snapshot belongs to the application
                    app_ref = snapshot_spec.get('source', {}).get('applicationRef', {})
                    if app_ref.get('name') == name:
                        try:
                            # Remove finalizers if force delete
                            if force and snapshot_metadata.get('finalizers'):
                                k8s_api.patch_namespaced_custom_object(
                                    group=Config.NDK_API_GROUP,
                                    version=Config.NDK_API_VERSION,
                                    namespace=namespace,
                                    plural='applicationsnapshots',
                                    name=snapshot_name,
                                    body={'metadata': {'finalizers': []}}
                                )
                            
                            k8s_api.delete_namespaced_custom_object(
                                group=Config.NDK_API_GROUP,
                                version=Config.NDK_API_VERSION,
                                namespace=namespace,
                                plural='applicationsnapshots',
                                name=snapshot_name
                            )
                            deleted_snapshots += 1
                            cleanup_log.append(f"Deleted snapshot: {snapshot_name}")
                        except ApiException as e:
                            if e.status != 404:
                                cleanup_log.append(f"Warning: Failed to delete snapshot {snapshot_name}: {e.reason}")
                
                if deleted_snapshots > 0:
                    print(f"✓ Deleted {deleted_snapshots} snapshots for application {name}")
                    time.sleep(1)  # Give Kubernetes time to process
            except ApiException as e:
                cleanup_log.append(f"Warning: Could not list snapshots: {e.reason}")
            
            # Step 2: Delete or update protection plans that target this application
            try:
                plans = k8s_api.list_namespaced_custom_object(
                    group=Config.NDK_API_GROUP,
                    version=Config.NDK_API_VERSION,
                    namespace=namespace,
                    plural='protectionplans'
                )
                
                deleted_plans = 0
                for plan in plans.get('items', []):
                    plan_metadata = plan.get('metadata', {})
                    plan_spec = plan.get('spec', {})
                    plan_name = plan_metadata.get('name')
                    
                    # Check if this plan targets the application
                    app_selector = plan_spec.get('applicationSelector', {})
                    match_labels = app_selector.get('matchLabels', {})
                    
                    # Check if the plan's selector matches our application
                    # This is a simplified check - in reality, you might need more sophisticated matching
                    should_delete = False
                    if match_labels.get('app') == name or match_labels.get('application') == name:
                        should_delete = True
                    
                    # Also check if plan name suggests it's dedicated to this app
                    if name in plan_name:
                        should_delete = True
                    
                    if should_delete:
                        try:
                            # Remove finalizers if force delete
                            if force and plan_metadata.get('finalizers'):
                                k8s_api.patch_namespaced_custom_object(
                                    group=Config.NDK_API_GROUP,
                                    version=Config.NDK_API_VERSION,
                                    namespace=namespace,
                                    plural='protectionplans',
                                    name=plan_name,
                                    body={'metadata': {'finalizers': []}}
                                )
                            
                            k8s_api.delete_namespaced_custom_object(
                                group=Config.NDK_API_GROUP,
                                version=Config.NDK_API_VERSION,
                                namespace=namespace,
                                plural='protectionplans',
                                name=plan_name
                            )
                            deleted_plans += 1
                            cleanup_log.append(f"Deleted protection plan: {plan_name}")
                        except ApiException as e:
                            if e.status != 404:
                                cleanup_log.append(f"Warning: Failed to delete protection plan {plan_name}: {e.reason}")
                
                if deleted_plans > 0:
                    print(f"✓ Deleted {deleted_plans} protection plans for application {name}")
                    time.sleep(1)
            except ApiException as e:
                cleanup_log.append(f"Warning: Could not list protection plans: {e.reason}")
            
            # Step 3: Delete PVCs and PVs that belong to this application
            try:
                if k8s_core_api:
                    deleted_pvcs = 0
                    pv_names_to_delete = []
                    pvcs_to_delete = []
                    
                    # Method 1: Try to get PVCs based on NDK Application labels (if CRD exists)
                    try:
                        app = k8s_api.get_namespaced_custom_object(
                            group=Config.NDK_API_GROUP,
                            version=Config.NDK_API_VERSION,
                            namespace=namespace,
                            plural='applications',
                            name=name
                        )
                        
                        app_spec = app.get('spec', {})
                        app_selector = app_spec.get('applicationSelector', {})
                        match_labels = app_selector.get('matchLabels', {})
                        
                        if match_labels:
                            # Build label selector string
                            label_selector = ','.join([f"{k}={v}" for k, v in match_labels.items()])
                            
                            # List PVCs with matching labels
                            pvcs = k8s_core_api.list_namespaced_persistent_volume_claim(
                                namespace=namespace,
                                label_selector=label_selector
                            )
                            
                            for pvc in pvcs.items:
                                pvcs_to_delete.append(pvc)
                            
                            if pvcs_to_delete:
                                cleanup_log.append(f"Found {len(pvcs_to_delete)} PVC(s) via NDK Application labels")
                    except ApiException as e:
                        if e.status != 404:
                            cleanup_log.append(f"Info: Could not get NDK Application details (CRD may not exist): {e.reason}")
                    
                    # Method 2: Fallback - Find StatefulSet PVCs by naming pattern (data-{name}-*)
                    # This catches PVCs created by StatefulSets that may not have proper labels
                    try:
                        all_pvcs = k8s_core_api.list_namespaced_persistent_volume_claim(namespace=namespace)
                        
                        # Pattern for StatefulSet PVCs: data-{statefulset-name}-{ordinal}
                        pvc_pattern = re.compile(rf'^data-{re.escape(name)}-\d+$')
                        
                        for pvc in all_pvcs.items:
                            pvc_name = pvc.metadata.name
                            # Check if this PVC matches the StatefulSet pattern and isn't already in our list
                            if pvc_pattern.match(pvc_name):
                                # Avoid duplicates
                                if not any(p.metadata.name == pvc_name for p in pvcs_to_delete):
                                    pvcs_to_delete.append(pvc)
                                    cleanup_log.append(f"Found StatefulSet PVC via naming pattern: {pvc_name}")
                    except ApiException as e:
                        cleanup_log.append(f"Warning: Could not list all PVCs for pattern matching: {e.reason}")
                    
                    # Method 3: Check for scale-down orphans (ordinals beyond current replica count)
                    # This catches PVCs left behind when StatefulSet was scaled down
                    try:
                        apps_api = client.AppsV1Api()
                        try:
                            statefulset = apps_api.read_namespaced_stateful_set(
                                name=name,
                                namespace=namespace
                            )
                            current_replicas = statefulset.spec.replicas
                            
                            # Check all PVCs for this StatefulSet
                            all_pvcs = k8s_core_api.list_namespaced_persistent_volume_claim(namespace=namespace)
                            pvc_pattern = re.compile(rf'^data-{re.escape(name)}-(\d+)$')
                            
                            for pvc in all_pvcs.items:
                                pvc_name = pvc.metadata.name
                                match = pvc_pattern.match(pvc_name)
                                if match:
                                    ordinal = int(match.group(1))
                                    # If ordinal >= current replicas, it's an orphan from scale-down
                                    if ordinal >= current_replicas:
                                        if not any(p.metadata.name == pvc_name for p in pvcs_to_delete):
                                            pvcs_to_delete.append(pvc)
                                            cleanup_log.append(f"Found scale-down orphan PVC: {pvc_name} (ordinal {ordinal} >= replicas {current_replicas})")
                        except ApiException as e:
                            if e.status != 404:
                                cleanup_log.append(f"Info: Could not check StatefulSet for scale-down orphans: {e.reason}")
                    except Exception as e:
                        cleanup_log.append(f"Info: Could not check for scale-down orphans: {str(e)}")
                    
                    # Now delete all identified PVCs
                    for pvc in pvcs_to_delete:
                        pvc_name = pvc.metadata.name
                        
                        # Store the PV name before deleting PVC
                        if pvc.spec.volume_name:
                            pv_names_to_delete.append(pvc.spec.volume_name)
                        
                        try:
                            # Remove finalizers if force delete
                            if force and pvc.metadata.finalizers:
                                pvc.metadata.finalizers = []
                                k8s_core_api.patch_namespaced_persistent_volume_claim(
                                    name=pvc_name,
                                    namespace=namespace,
                                    body=pvc
                                )
                            
                            k8s_core_api.delete_namespaced_persistent_volume_claim(
                                name=pvc_name,
                                namespace=namespace
                            )
                            deleted_pvcs += 1
                            cleanup_log.append(f"Deleted PVC: {pvc_name}")
                        except ApiException as e:
                            if e.status != 404:
                                cleanup_log.append(f"Warning: Failed to delete PVC {pvc_name}: {e.reason}")
                    
                    if deleted_pvcs > 0:
                        print(f"✓ Deleted {deleted_pvcs} PVC(s) for application {name}")
                        time.sleep(2)  # Give PVCs time to be deleted
                    
                    # Now delete the associated PVs
                    deleted_pvs = 0
                    for pv_name in pv_names_to_delete:
                        try:
                            # Get the PV to check if it still exists
                            pv = k8s_core_api.read_persistent_volume(name=pv_name)
                            
                            # Remove finalizers if force delete
                            if force and pv.metadata.finalizers:
                                pv.metadata.finalizers = []
                                k8s_core_api.patch_persistent_volume(
                                    name=pv_name,
                                    body=pv
                                )
                            
                            # Delete the PV
                            k8s_core_api.delete_persistent_volume(name=pv_name)
                            deleted_pvs += 1
                            cleanup_log.append(f"Deleted PV: {pv_name}")
                        except ApiException as e:
                            if e.status == 404:
                                # PV was already deleted (possibly by reclaim policy)
                                cleanup_log.append(f"PV {pv_name} was already deleted or reclaimed")
                            else:
                                cleanup_log.append(f"Warning: Failed to delete PV {pv_name}: {e.reason}")
                    
                    if deleted_pvs > 0:
                        print(f"✓ Deleted {deleted_pvs} PV(s) for application {name}")
                        time.sleep(1)
            except Exception as e:
                cleanup_log.append(f"Warning: Could not process PVCs/PVs: {str(e)}")
            
            # Step 4: Try to delete Volume Groups (if they exist as NDK resources)
            try:
                # Check if volumegroups CRD exists
                volume_groups = k8s_api.list_namespaced_custom_object(
                    group=Config.NDK_API_GROUP,
                    version=Config.NDK_API_VERSION,
                    namespace=namespace,
                    plural='volumegroups'
                )
                
                deleted_vgs = 0
                for vg in volume_groups.get('items', []):
                    vg_metadata = vg.get('metadata', {})
                    vg_name = vg_metadata.get('name')
                    vg_labels = vg_metadata.get('labels', {})
                    
                    # Check if this volume group belongs to the application
                    if vg_labels.get('app') == name or vg_labels.get('application') == name or name in vg_name:
                        try:
                            # Remove finalizers if force delete
                            if force and vg_metadata.get('finalizers'):
                                k8s_api.patch_namespaced_custom_object(
                                    group=Config.NDK_API_GROUP,
                                    version=Config.NDK_API_VERSION,
                                    namespace=namespace,
                                    plural='volumegroups',
                                    name=vg_name,
                                    body={'metadata': {'finalizers': []}}
                                )
                            
                            k8s_api.delete_namespaced_custom_object(
                                group=Config.NDK_API_GROUP,
                                version=Config.NDK_API_VERSION,
                                namespace=namespace,
                                plural='volumegroups',
                                name=vg_name
                            )
                            deleted_vgs += 1
                            cleanup_log.append(f"Deleted volume group: {vg_name}")
                        except ApiException as e:
                            if e.status != 404:
                                cleanup_log.append(f"Warning: Failed to delete volume group {vg_name}: {e.reason}")
                
                if deleted_vgs > 0:
                    print(f"✓ Deleted {deleted_vgs} volume groups for application {name}")
                    time.sleep(1)
            except ApiException as e:
                # Volume groups might not exist or CRD might not be installed
                if e.status != 404:
                    cleanup_log.append(f"Info: Volume groups not found or not applicable")
            
            # Step 5: Delete StatefulSet (if it exists)
            try:
                if k8s_core_api:
                    apps_api = client.AppsV1Api()
                    
                    try:
                        # Try to get the StatefulSet with the same name as the application
                        statefulset = apps_api.read_namespaced_stateful_set(
                            name=name,
                            namespace=namespace
                        )
                        
                        # Delete the StatefulSet
                        apps_api.delete_namespaced_stateful_set(
                            name=name,
                            namespace=namespace,
                            body=client.V1DeleteOptions(
                                propagation_policy='Foreground'
                            )
                        )
                        cleanup_log.append(f"Deleted StatefulSet: {name}")
                        print(f"✓ Deleted StatefulSet {name}")
                        time.sleep(2)  # Give time for pods to terminate
                    except ApiException as e:
                        if e.status == 404:
                            cleanup_log.append(f"Info: StatefulSet {name} not found (may not exist)")
                        else:
                            cleanup_log.append(f"Warning: Failed to delete StatefulSet {name}: {e.reason}")
            except Exception as e:
                cleanup_log.append(f"Warning: Could not process StatefulSet: {str(e)}")
            
            # Step 6: Delete Service (if it exists)
            try:
                if k8s_core_api:
                    try:
                        # Try to get the Service with the same name as the application
                        service = k8s_core_api.read_namespaced_service(
                            name=name,
                            namespace=namespace
                        )
                        
                        # Delete the Service
                        k8s_core_api.delete_namespaced_service(
                            name=name,
                            namespace=namespace
                        )
                        cleanup_log.append(f"Deleted Service: {name}")
                        print(f"✓ Deleted Service {name}")
                    except ApiException as e:
                        if e.status == 404:
                            cleanup_log.append(f"Info: Service {name} not found (may not exist)")
                        else:
                            cleanup_log.append(f"Warning: Failed to delete Service {name}: {e.reason}")
            except Exception as e:
                cleanup_log.append(f"Warning: Could not process Service: {str(e)}")
            
            # Step 7: Delete Secret (if it exists)
            try:
                if k8s_core_api:
                    secret_name = f"{name}-credentials"  # Fixed: was "-secret", should be "-credentials"
                    try:
                        # Try to get the Secret
                        secret = k8s_core_api.read_namespaced_secret(
                            name=secret_name,
                            namespace=namespace
                        )
                        
                        # Delete the Secret
                        k8s_core_api.delete_namespaced_secret(
                            name=secret_name,
                            namespace=namespace
                        )
                        cleanup_log.append(f"Deleted Secret: {secret_name}")
                        print(f"✓ Deleted Secret {secret_name}")
                    except ApiException as e:
                        if e.status == 404:
                            cleanup_log.append(f"Info: Secret {secret_name} not found (may not exist)")
                        else:
                            cleanup_log.append(f"Warning: Failed to delete Secret {secret_name}: {e.reason}")
            except Exception as e:
                cleanup_log.append(f"Warning: Could not process Secret: {str(e)}")
            
            # Step 8: Delete any orphaned Pods with matching labels (cleanup stragglers)
            try:
                if k8s_core_api:
                    try:
                        # Delete pods with app label matching the application name
                        pods = k8s_core_api.list_namespaced_pod(
                            namespace=namespace,
                            label_selector=f"app={name}"
                        )
                        
                        deleted_pods = 0
                        for pod in pods.items:
                            pod_name = pod.metadata.name
                            try:
                                k8s_core_api.delete_namespaced_pod(
                                    name=pod_name,
                                    namespace=namespace,
                                    body=client.V1DeleteOptions(
                                        grace_period_seconds=0
                                    )
                                )
                                deleted_pods += 1
                            except ApiException as e:
                                if e.status != 404:
                                    cleanup_log.append(f"Warning: Failed to delete pod {pod_name}: {e.reason}")
                        
                        if deleted_pods > 0:
                            cleanup_log.append(f"Deleted {deleted_pods} orphaned pod(s)")
                            print(f"✓ Deleted {deleted_pods} orphaned pods")
                    except ApiException as e:
                        if e.status != 404:
                            cleanup_log.append(f"Warning: Could not list pods: {e.reason}")
            except Exception as e:
                cleanup_log.append(f"Warning: Could not process Pods: {str(e)}")
            
            # Step 9: Finally, delete the application itself
            try:
                # If force delete, remove finalizers first
                if force:
                    try:
                        app = k8s_api.get_namespaced_custom_object(
                            group=Config.NDK_API_GROUP,
                            version=Config.NDK_API_VERSION,
                            namespace=namespace,
                            plural='applications',
                            name=name
                        )
                        
                        metadata = app.get('metadata', {})
                        if metadata.get('finalizers'):
                            # Remove all finalizers
                            patch = {
                                'metadata': {
                                    'finalizers': []
                                }
                            }
                            k8s_api.patch_namespaced_custom_object(
                                group=Config.NDK_API_GROUP,
                                version=Config.NDK_API_VERSION,
                                namespace=namespace,
                                plural='applications',
                                name=name,
                                body=patch
                            )
                            print(f"✓ Removed finalizers from application {name}")
                            time.sleep(0.5)
                            
                            # Check if the resource still exists
                            try:
                                k8s_api.get_namespaced_custom_object(
                                    group=Config.NDK_API_GROUP,
                                    version=Config.NDK_API_VERSION,
                                    namespace=namespace,
                                    plural='applications',
                                    name=name
                                )
                            except ApiException as e:
                                if e.status == 404:
                                    # Resource was already deleted
                                    print(f"✓ Application {name} was automatically deleted after finalizer removal")
                                    cleanup_log.append(f"Application {name} deleted (auto-deleted after finalizer removal)")
                                    cache['applications'] = {'data': None, 'timestamp': None}
                                    cache['snapshots'] = {'data': None, 'timestamp': None}
                                    cache['protectionplans'] = {'data': None, 'timestamp': None}
                                    
                                    return jsonify({
                                        'success': True,
                                        'message': f'Application {name} and all associated resources deleted successfully',
                                        'cleanup_log': cleanup_log
                                    }), 200
                                raise
                    except ApiException as e:
                        if e.status != 404:
                            raise
                
                # Delete the application
                k8s_api.delete_namespaced_custom_object(
                    group=Config.NDK_API_GROUP,
                    version=Config.NDK_API_VERSION,
                    namespace=namespace,
                    plural='applications',
                    name=name
                )
                cleanup_log.append(f"Application {name} deleted")
                print(f"✓ Application {name} deleted")
                
            except ApiException as e:
                if e.status == 404:
                    print(f"✓ Application {name} was already deleted")
                    cleanup_log.append(f"Application {name} was already deleted")
                else:
                    raise
            
            # Invalidate all relevant caches
            cache['applications'] = {'data': None, 'timestamp': None}
            cache['snapshots'] = {'data': None, 'timestamp': None}
            cache['protectionplans'] = {'data': None, 'timestamp': None}
            
            return jsonify({
                'success': True,
                'message': f'Application {name} and all associated resources deleted successfully',
                'cleanup_log': cleanup_log
            }), 200
            
        except ApiException as e:
            return jsonify({'error': f'Failed to delete application: {e.reason}'}), e.status
        except Exception as e:
            return jsonify({'error': str(e)}), 500

@app.route('/api/applications/<namespace>/<name>/labels', methods=['PUT'])
@login_required
def update_application_labels(namespace, name):
    """Update labels on an NDK Application"""
    if not k8s_api:
        return jsonify({'error': 'Kubernetes API not available'}), 500
    
    try:
        data = request.get_json()
        new_labels = data.get('labels', {})
        
        # Get current application
        app = k8s_api.get_namespaced_custom_object(
            group=Config.NDK_API_GROUP,
            version=Config.NDK_API_VERSION,
            namespace=namespace,
            plural='applications',
            name=name
        )
        
        # Get all existing labels
        current_labels = app.get('metadata', {}).get('labels', {})
        
        # Merge existing labels with new labels (new labels will override existing ones with same key)
        # This ensures we only add/update labels, never delete them
        merged_labels = {**current_labels, **new_labels}
        
        # Update the application with new labels
        patch = {
            'metadata': {
                'labels': merged_labels
            }
        }
        
        k8s_api.patch_namespaced_custom_object(
            group=Config.NDK_API_GROUP,
            version=Config.NDK_API_VERSION,
            namespace=namespace,
            plural='applications',
            name=name,
            body=patch
        )
        
        # Clear cache to force refresh
        cache['applications'] = {'data': None, 'timestamp': None}
        
        return jsonify({'message': 'Labels updated successfully', 'labels': new_labels})
    except ApiException as e:
        return jsonify({'error': f'Failed to update labels: {e}'}), 500

@app.route('/api/applications/<namespace>/<name>/debug', methods=['GET'])
@login_required
def debug_application(namespace, name):
    """Debug endpoint to see application details"""
    if not k8s_api:
        return jsonify({'error': 'Kubernetes API not available'}), 500
    
    try:
        app = k8s_api.get_namespaced_custom_object(
            group=Config.NDK_API_GROUP,
            version=Config.NDK_API_VERSION,
            namespace=namespace,
            plural='applications',
            name=name
        )
        
        return jsonify({
            'metadata': app.get('metadata', {}),
            'spec': app.get('spec', {}),
            'status': app.get('status', {})
        })
    except ApiException as e:
        return jsonify({'error': f'Failed to get application: {e}'}), 500

@app.route('/api/applications/<namespace>/<name>/pods', methods=['GET'])
@login_required
def get_application_pods(namespace, name):
    """Get pod information for an NDK Application"""
    if not k8s_api or not k8s_core_api:
        return jsonify({'error': 'Kubernetes API not available'}), 500
    
    try:
        # Get the application to retrieve its selector
        app = k8s_api.get_namespaced_custom_object(
            group=Config.NDK_API_GROUP,
            version=Config.NDK_API_VERSION,
            namespace=namespace,
            plural='applications',
            name=name
        )
        
        # Get the application selector
        spec = app.get('spec', {})
        app_selector = spec.get('applicationSelector', {})
        
        # Try to build label selector from matchLabels or matchExpressions
        label_selector = None
        match_labels = app_selector.get('matchLabels', {})
        match_expressions = app_selector.get('matchExpressions', [])
        
        if match_labels:
            # Convert matchLabels to label selector string
            label_selector = ','.join([f"{k}={v}" for k, v in match_labels.items()])
        elif match_expressions:
            # Convert matchExpressions to label selector string
            selector_parts = []
            for expr in match_expressions:
                key = expr.get('key')
                operator = expr.get('operator', 'In')
                values = expr.get('values', [])
                
                if operator == 'In' and values:
                    selector_parts.append(f"{key} in ({','.join(values)})")
                elif operator == 'NotIn' and values:
                    selector_parts.append(f"{key} notin ({','.join(values)})")
                elif operator == 'Exists':
                    selector_parts.append(key)
                elif operator == 'DoesNotExist':
                    selector_parts.append(f"!{key}")
            
            if selector_parts:
                label_selector = ','.join(selector_parts)
        
        # If no selector found, try to find pods by common patterns
        if not label_selector:
            # Try to find pods with app name as label
            label_selector = f"app={name}"
            print(f"No explicit selector found for {namespace}/{name}, trying app={name}")
        
        print(f"Fetching pods for {namespace}/{name} with selector: {label_selector}")
        
        # Get pods matching the selector
        pods = k8s_core_api.list_namespaced_pod(
            namespace=namespace,
            label_selector=label_selector
        )
        
        print(f"Found {len(pods.items)} pods for {namespace}/{name}")
        
        pod_info = []
        for pod in pods.items:
            pod_name = pod.metadata.name
            node_name = pod.spec.node_name or 'Pending'
            phase = pod.status.phase
            
            # Get container statuses
            ready_containers = 0
            total_containers = len(pod.spec.containers)
            if pod.status.container_statuses:
                ready_containers = sum(1 for cs in pod.status.container_statuses if cs.ready)
            
            pod_info.append({
                'name': pod_name,
                'node': node_name,
                'phase': phase,
                'ready': f"{ready_containers}/{total_containers}"
            })
        
        return jsonify({
            'replicas': len(pod_info),
            'pods': pod_info,
            'selector': label_selector
        })
        
    except ApiException as e:
        print(f"API error fetching pods for {namespace}/{name}: {e}")
        return jsonify({'error': f'Failed to get pod information: {e}'}), 500
    except Exception as e:
        print(f"Error fetching pods for {namespace}/{name}: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/applications/<namespace>/<name>/pvcs', methods=['GET'])
@login_required
def get_application_pvcs(namespace, name):
    """Get PVC and Volume Group information for an NDK Application"""
    if not k8s_api or not k8s_core_api:
        return jsonify({'error': 'Kubernetes API not available'}), 500
    
    try:
        # Get the application to retrieve its selector
        app = k8s_api.get_namespaced_custom_object(
            group=Config.NDK_API_GROUP,
            version=Config.NDK_API_VERSION,
            namespace=namespace,
            plural='applications',
            name=name
        )
        
        # Get the application selector
        spec = app.get('spec', {})
        app_selector = spec.get('applicationSelector', {})
        
        # Try to build label selector from matchLabels or matchExpressions
        label_selector = None
        match_labels = app_selector.get('matchLabels', {})
        match_expressions = app_selector.get('matchExpressions', [])
        
        if match_labels:
            # Convert matchLabels to label selector string
            label_selector = ','.join([f"{k}={v}" for k, v in match_labels.items()])
        elif match_expressions:
            # Convert matchExpressions to label selector string
            selector_parts = []
            for expr in match_expressions:
                key = expr.get('key')
                operator = expr.get('operator', 'In')
                values = expr.get('values', [])
                
                if operator == 'In' and values:
                    selector_parts.append(f"{key} in ({','.join(values)})")
                elif operator == 'NotIn' and values:
                    selector_parts.append(f"{key} notin ({','.join(values)})")
                elif operator == 'Exists':
                    selector_parts.append(key)
                elif operator == 'DoesNotExist':
                    selector_parts.append(f"!{key}")
            
            if selector_parts:
                label_selector = ','.join(selector_parts)
        
        print(f"Fetching PVCs for {namespace}/{name} with selector: {label_selector}")
        
        # Get PVCs - try with selector first, then fallback to all PVCs in namespace
        pvcs_list = []
        if label_selector:
            try:
                pvcs = k8s_core_api.list_namespaced_persistent_volume_claim(
                    namespace=namespace,
                    label_selector=label_selector
                )
                pvcs_list = pvcs.items
            except ApiException as e:
                print(f"Could not list PVCs with selector: {e}")
        
        # Fallback: Get all PVCs in namespace and filter by naming pattern
        if not pvcs_list:
            print(f"No PVCs found with selector, trying naming pattern for {name}")
            all_pvcs = k8s_core_api.list_namespaced_persistent_volume_claim(namespace=namespace)
            # Pattern for StatefulSet PVCs: data-{name}-{ordinal} or {name}-{suffix}
            pvc_pattern = re.compile(rf'(data-)?{re.escape(name)}(-\d+)?')
            pvcs_list = [pvc for pvc in all_pvcs.items if pvc_pattern.search(pvc.metadata.name)]
        
        print(f"Found {len(pvcs_list)} PVCs for {namespace}/{name}")
        
        pvc_info = []
        total_capacity_bytes = 0
        
        for pvc in pvcs_list:
            pvc_name = pvc.metadata.name
            pv_name = pvc.spec.volume_name if pvc.spec.volume_name else 'Pending'
            status = pvc.status.phase
            
            # Get capacity
            capacity = 'Unknown'
            if pvc.status.capacity and 'storage' in pvc.status.capacity:
                capacity = pvc.status.capacity['storage']
                # Convert to bytes for total calculation
                try:
                    capacity_str = capacity.replace('Gi', '').replace('Mi', '').replace('Ki', '')
                    if 'Gi' in capacity:
                        total_capacity_bytes += int(capacity_str) * 1024 * 1024 * 1024
                    elif 'Mi' in capacity:
                        total_capacity_bytes += int(capacity_str) * 1024 * 1024
                    elif 'Ki' in capacity:
                        total_capacity_bytes += int(capacity_str) * 1024
                except:
                    pass
            
            storage_class = pvc.spec.storage_class_name or 'default'
            
            # Get PV details if bound
            volume_handle = None
            volume_group_name = pv_name  # Default to PV name
            pv_description = None
            
            if pv_name != 'Pending':
                try:
                    pv = k8s_core_api.read_persistent_volume(name=pv_name)
                    
                    # Get Nutanix CSI specific details
                    if pv.spec.csi and pv.spec.csi.driver == 'csi.nutanix.com':
                        volume_handle = pv.spec.csi.volume_handle
                        volume_attributes = pv.spec.csi.volume_attributes or {}
                        pv_description = volume_attributes.get('description', '')
                        
                        # Extract VG UUID from volume handle (e.g., "NutanixVolumes-8682863c-...")
                        if volume_handle and volume_handle.startswith('NutanixVolumes-'):
                            vg_uuid = volume_handle.replace('NutanixVolumes-', '')
                            volume_group_name = vg_uuid
                
                except ApiException as e:
                    print(f"Could not read PV {pv_name}: {e}")
            
            pvc_info.append({
                'name': pvc_name,
                'pvName': pv_name,
                'volumeGroup': volume_group_name,
                'volumeHandle': volume_handle,
                'capacity': capacity,
                'storageClass': storage_class,
                'status': status,
                'description': pv_description
            })
        
        # Format total capacity
        total_capacity = 'Unknown'
        if total_capacity_bytes > 0:
            if total_capacity_bytes >= 1024 * 1024 * 1024 * 1024:  # TB
                total_capacity = f"{total_capacity_bytes / (1024**4):.1f}Ti"
            elif total_capacity_bytes >= 1024 * 1024 * 1024:  # GB
                total_capacity = f"{total_capacity_bytes / (1024**3):.1f}Gi"
            elif total_capacity_bytes >= 1024 * 1024:  # MB
                total_capacity = f"{total_capacity_bytes / (1024**2):.1f}Mi"
            else:
                total_capacity = f"{total_capacity_bytes / 1024:.1f}Ki"
        
        return jsonify({
            'count': len(pvc_info),
            'totalCapacity': total_capacity,
            'pvcs': pvc_info,
            'selector': label_selector
        })
        
    except ApiException as e:
        print(f"API error fetching PVCs for {namespace}/{name}: {e}")
        return jsonify({'error': f'Failed to get PVC information: {e}'}), 500
    except Exception as e:
        print(f"Error fetching PVCs for {namespace}/{name}: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/snapshots', methods=['GET', 'POST'])
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
            
            if not app_name or not app_namespace:
                return jsonify({'error': 'Application name and namespace are required'}), 400
            
            # Generate snapshot name with timestamp
            timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
            snapshot_name = f"{app_name}-snapshot-{timestamp}"
            
            # Create snapshot manifest
            snapshot_manifest = {
                'apiVersion': f'{Config.NDK_API_GROUP}/{Config.NDK_API_VERSION}',
                'kind': 'ApplicationSnapshot',
                'metadata': {
                    'name': snapshot_name,
                    'namespace': app_namespace
                },
                'spec': {
                    'source': {
                        'applicationRef': {
                            'name': app_name
                        }
                    },
                    'expiresAfter': expires_after
                }
            }
            
            # Create the snapshot
            result = k8s_api.create_namespaced_custom_object(
                group=Config.NDK_API_GROUP,
                version=Config.NDK_API_VERSION,
                namespace=app_namespace,
                plural='applicationsnapshots',
                body=snapshot_manifest
            )
            
            # Invalidate cache
            cache['snapshots'] = {'data': None, 'timestamp': None}
            
            return jsonify({
                'success': True,
                'message': f'Snapshot {snapshot_name} created successfully',
                'snapshot': {
                    'name': snapshot_name,
                    'namespace': app_namespace,
                    'application': app_name
                }
            }), 201
            
        except ApiException as e:
            error_msg = f"Failed to create snapshot: {e.reason}"
            if e.body:
                try:
                    import json
                    error_body = json.loads(e.body)
                    error_msg = error_body.get('message', error_msg)
                except:
                    pass
            return jsonify({'error': error_msg}), e.status
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    # GET request - list snapshots
    def fetch():
        if not k8s_api:
            return []
        
        try:
            result = k8s_api.list_cluster_custom_object(
                group=Config.NDK_API_GROUP,
                version=Config.NDK_API_VERSION,
                plural='applicationsnapshots'
            )
            
            snapshots = []
            for item in result.get('items', []):
                metadata = item.get('metadata', {})
                spec = item.get('spec', {})
                status = item.get('status', {})
                
                # Extract application name from source
                source = spec.get('source', {})
                app_ref = source.get('applicationRef', {})
                app_name = app_ref.get('name', 'Unknown')
                
                # Extract protection plan from labels
                labels = metadata.get('labels', {})
                protection_plan = labels.get('protectionplan', None)
                
                # Get creation time for grouping snapshots from same execution
                creation_time = status.get('creationTime', metadata.get('creationTimestamp', ''))
                
                # Determine state - check for deletion first
                if metadata.get('deletionTimestamp'):
                    state = 'Deleting'
                else:
                    ready_to_use = status.get('readyToUse', False)
                    if ready_to_use:
                        state = 'Ready'
                    elif status:
                        state = 'Creating'
                    else:
                        state = 'Unknown'
                
                snapshots.append({
                    'name': metadata.get('name', 'Unknown'),
                    'namespace': metadata.get('namespace', 'default'),
                    'created': metadata.get('creationTimestamp', ''),
                    'creationTime': creation_time,
                    'application': app_name,
                    'expiresAfter': spec.get('expiresAfter', 'Not set'),
                    'state': state,
                    'consistencyType': status.get('consistencyType', 'Unknown'),
                    'expirationTime': status.get('expirationTime', 'Not set'),
                    'protectionPlan': protection_plan
                })
            
            return snapshots
        except ApiException as e:
            print(f"Error fetching snapshots: {e}")
            return []
    
    return jsonify(get_cached_or_fetch('snapshots', fetch))

@app.route('/api/snapshots/<namespace>/<name>', methods=['DELETE'])
@login_required
def delete_snapshot(namespace, name):
    """Delete an NDK Application Snapshot"""
    try:
        if not k8s_api:
            return jsonify({'error': 'Kubernetes API not available'}), 503
        
        # Delete the snapshot
        k8s_api.delete_namespaced_custom_object(
            group=Config.NDK_API_GROUP,
            version=Config.NDK_API_VERSION,
            namespace=namespace,
            plural='applicationsnapshots',
            name=name
        )
        
        # Invalidate cache
        cache['snapshots'] = {'data': None, 'timestamp': None}
        
        return jsonify({
            'success': True,
            'message': f'Snapshot {name} deleted successfully'
        }), 200
        
    except ApiException as e:
        error_msg = f"Failed to delete snapshot: {e.reason}"
        if e.body:
            try:
                import json
                error_body = json.loads(e.body)
                error_msg = error_body.get('message', error_msg)
            except:
                pass
        return jsonify({'error': error_msg}), e.status
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/snapshots/<namespace>/<name>/restore', methods=['POST'])
@login_required
def restore_snapshot(namespace, name):
    """Restore an application from a snapshot"""
    try:
        if not k8s_api:
            return jsonify({'error': 'Kubernetes API not available'}), 503
        
        data = request.get_json() or {}
        target_namespace = data.get('targetNamespace', namespace)
        restore_name = data.get('restoreName')
        
        if not restore_name:
            return jsonify({'error': 'Restore name is required'}), 400
        
        # Get the snapshot to extract the application name
        try:
            snapshot = k8s_api.get_namespaced_custom_object(
                group=Config.NDK_API_GROUP,
                version=Config.NDK_API_VERSION,
                namespace=namespace,
                plural='applicationsnapshots',
                name=name
            )
            app_name = snapshot.get('spec', {}).get('source', {}).get('applicationRef', {}).get('name')
            if not app_name:
                return jsonify({'error': 'Could not determine application name from snapshot'}), 400
        except ApiException as e:
            return jsonify({'error': f'Failed to get snapshot: {e.reason}'}), e.status
        
        # Create ApplicationSnapshotRestore manifest
        restore_manifest = {
            'apiVersion': f'{Config.NDK_API_GROUP}/{Config.NDK_API_VERSION}',
            'kind': 'ApplicationSnapshotRestore',
            'metadata': {
                'name': restore_name,
                'namespace': target_namespace
            },
            'spec': {
                'applicationSnapshotName': name,
                'applicationSnapshotNamespace': namespace
            }
        }
        
        # Create the restore
        print(f"📝 Creating ApplicationSnapshotRestore: {restore_name} in namespace {target_namespace}")
        result = k8s_api.create_namespaced_custom_object(
            group=Config.NDK_API_GROUP,
            version=Config.NDK_API_VERSION,
            namespace=target_namespace,
            plural='applicationsnapshotrestores',
            body=restore_manifest
        )
        print(f"✓ ApplicationSnapshotRestore created: {restore_name}")
        
        # Poll for restore completion (max 5 minutes)
        print(f"⏳ Waiting for restore operation to complete...")
        max_wait_time = 300  # 5 minutes
        poll_interval = 5  # 5 seconds
        elapsed_time = 0
        restore_completed = False
        restore_failed = False
        failure_reason = None
        
        while elapsed_time < max_wait_time:
            try:
                restore_status = k8s_api.get_namespaced_custom_object(
                    group=Config.NDK_API_GROUP,
                    version=Config.NDK_API_VERSION,
                    namespace=target_namespace,
                    plural='applicationsnapshotrestores',
                    name=restore_name
                )
                
                status = restore_status.get('status', {})
                
                # Check if restore is completed
                if status.get('completed') == True:
                    restore_completed = True
                    print(f"✓ Restore operation completed successfully")
                    break
                
                # Check for failure conditions
                conditions = status.get('conditions', [])
                for condition in conditions:
                    if condition.get('type') == 'Failed' and condition.get('status') == 'True':
                        restore_failed = True
                        failure_reason = condition.get('message', 'Unknown failure')
                        print(f"✗ Restore operation failed: {failure_reason}")
                        break
                
                if restore_failed:
                    break
                
                # Still in progress
                print(f"⏳ Restore in progress... ({elapsed_time}s elapsed)")
                time.sleep(poll_interval)
                elapsed_time += poll_interval
                
            except ApiException as e:
                if e.status == 404:
                    # Restore resource was deleted - might indicate completion or failure
                    print(f"⚠ Restore resource no longer exists (may have been cleaned up)")
                    break
                else:
                    print(f"⚠ Error checking restore status: {e.reason}")
                    break
        
        if elapsed_time >= max_wait_time:
            print(f"⚠ Restore polling timeout reached ({max_wait_time}s) - proceeding with Application CRD creation")
        
        # Create Application CRD so the restored app is discoverable in the dashboard
        # This is necessary because NDK snapshots don't include the Application CRD itself
        print(f"📝 Creating Application CRD for restored app: {app_name}")
        application_manifest = {
            'apiVersion': f'{Config.NDK_API_GROUP}/{Config.NDK_API_VERSION}',
            'kind': 'Application',
            'metadata': {
                'name': app_name,
                'namespace': target_namespace,
                'labels': {
                    'restored-from-snapshot': name,
                    'restore-operation': restore_name
                }
            },
            'spec': {
                'start': True,
                'useExistingConfig': False  # Let controller discover existing resources
            }
        }
        
        try:
            k8s_api.create_namespaced_custom_object(
                group=Config.NDK_API_GROUP,
                version=Config.NDK_API_VERSION,
                namespace=target_namespace,
                plural='applications',
                body=application_manifest
            )
            print(f"✓ Application CRD created: {app_name}")
        except ApiException as e:
            # If Application already exists, that's okay - log it but don't fail
            if e.status == 409:  # 409 = Conflict (already exists)
                print(f"⚠ Application CRD already exists: {app_name}")
            else:
                print(f"✗ Failed to create Application CRD: {e.reason}")
                raise
        
        # Invalidate cache
        cache['applications'] = {'data': None, 'timestamp': None}
        
        completion_status = 'completed' if restore_completed else ('failed' if restore_failed else 'timeout')
        
        return jsonify({
            'success': True,
            'message': f'Restore {restore_name} completed successfully. Application {app_name} is now visible in the dashboard.',
            'restore': {
                'name': restore_name,
                'namespace': target_namespace,
                'snapshot': name,
                'application': app_name,
                'status': completion_status,
                'failure_reason': failure_reason if restore_failed else None
            }
        }), 201
        
    except ApiException as e:
        error_msg = f"Failed to restore snapshot: {e.reason}"
        if e.body:
            try:
                import json
                error_body = json.loads(e.body)
                error_msg = error_body.get('message', error_msg)
            except:
                pass
        return jsonify({'error': error_msg}), e.status
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/snapshots/bulk', methods=['POST'])
@login_required
def bulk_create_snapshots():
    """Create snapshots for multiple applications"""
    try:
        if not k8s_api:
            return jsonify({'error': 'Kubernetes API not available'}), 503
        
        data = request.get_json()
        applications = data.get('applications', [])
        expires_after = data.get('expiresAfter', '720h')
        
        if not applications:
            return jsonify({'error': 'No applications specified'}), 400
        
        results = {
            'success': [],
            'failed': []
        }
        
        timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        
        for app in applications:
            app_name = app.get('name')
            app_namespace = app.get('namespace')
            
            if not app_name or not app_namespace:
                results['failed'].append({
                    'application': app_name or 'Unknown',
                    'error': 'Missing name or namespace'
                })
                continue
            
            try:
                snapshot_name = f"{app_name}-snapshot-{timestamp}"
                
                snapshot_manifest = {
                    'apiVersion': f'{Config.NDK_API_GROUP}/{Config.NDK_API_VERSION}',
                    'kind': 'ApplicationSnapshot',
                    'metadata': {
                        'name': snapshot_name,
                        'namespace': app_namespace
                    },
                    'spec': {
                        'source': {
                            'applicationRef': {
                                'name': app_name
                            }
                        },
                        'expiresAfter': expires_after
                    }
                }
                
                k8s_api.create_namespaced_custom_object(
                    group=Config.NDK_API_GROUP,
                    version=Config.NDK_API_VERSION,
                    namespace=app_namespace,
                    plural='applicationsnapshots',
                    body=snapshot_manifest
                )
                
                results['success'].append({
                    'application': app_name,
                    'snapshot': snapshot_name,
                    'namespace': app_namespace
                })
                
            except ApiException as e:
                error_msg = e.reason
                if e.body:
                    try:
                        import json
                        error_body = json.loads(e.body)
                        error_msg = error_body.get('message', error_msg)
                    except:
                        pass
                results['failed'].append({
                    'application': app_name,
                    'error': error_msg
                })
        
        # Invalidate cache
        cache['snapshots'] = {'data': None, 'timestamp': None}
        
        return jsonify({
            'success': True,
            'message': f'Created {len(results["success"])} snapshots, {len(results["failed"])} failed',
            'results': results
        }), 201 if results['success'] else 207
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/storageclusters')
@login_required
def get_storageclusters():
    """Get all NDK Storage Clusters"""
    def fetch():
        if not k8s_api:
            return []
        
        # Try to get Prism Central endpoint from secret
        pc_endpoint = 'Unknown'
        try:
            if k8s_core_api:
                secret = k8s_core_api.read_namespaced_secret(
                    name='pc-secret',
                    namespace='ndk-operator'
                )
                if secret.data and 'endpoint' in secret.data:
                    import base64
                    endpoint = base64.b64decode(secret.data['endpoint']).decode('utf-8')
                    port = '9440'
                    if 'port' in secret.data:
                        port = base64.b64decode(secret.data['port']).decode('utf-8')
                    pc_endpoint = f"{endpoint}:{port}"
        except Exception as e:
            print(f"Warning: Could not read PC secret: {e}")
        
        try:
            result = k8s_api.list_cluster_custom_object(
                group=Config.NDK_API_GROUP,
                version=Config.NDK_API_VERSION,
                plural='storageclusters'
            )
            
            clusters = []
            for item in result.get('items', []):
                metadata = item.get('metadata', {})
                spec = item.get('spec', {})
                status = item.get('status', {})
                
                # Get availability status
                available = status.get('available', False)
                state = 'Available' if available else 'Unavailable'
                
                clusters.append({
                    'name': metadata.get('name', 'Unknown'),
                    'created': metadata.get('creationTimestamp', ''),
                    'prismCentral': pc_endpoint,
                    'managementServerUUID': spec.get('managementServerUuid', 'Unknown'),
                    'storageServerUUID': spec.get('storageServerUuid', 'Unknown'),
                    'state': state,
                    'available': available
                })
            
            return clusters
        except ApiException as e:
            print(f"Error fetching storage clusters: {e}")
            return []
    
    return jsonify(get_cached_or_fetch('storageclusters', fetch))

@app.route('/api/protectionplans')
@login_required
def get_protectionplans():
    """Get all NDK Protection Plans"""
    def fetch():
        if not k8s_api:
            return []
        
        try:
            result = k8s_api.list_cluster_custom_object(
                group=Config.NDK_API_GROUP,
                version=Config.NDK_API_VERSION,
                plural='protectionplans'
            )
            
            plans = []
            for item in result.get('items', []):
                metadata = item.get('metadata', {})
                spec = item.get('spec', {})
                status = item.get('status', {})
                
                # Extract retention from retentionPolicy object
                retention_policy = spec.get('retentionPolicy', {})
                if retention_policy.get('retentionCount'):
                    retention = retention_policy.get('retentionCount')
                elif retention_policy.get('maxAge'):
                    retention = retention_policy.get('maxAge')
                else:
                    retention = 'Not set'
                
                # Extract schedule from JobScheduler reference
                schedule = 'Not set'
                schedule_name = spec.get('scheduleName')
                if schedule_name:
                    try:
                        # Fetch the JobScheduler resource
                        scheduler = k8s_api.get_namespaced_custom_object(
                            group='scheduler.nutanix.com',
                            version='v1alpha1',
                            namespace=metadata.get('namespace', 'default'),
                            plural='jobschedulers',
                            name=schedule_name
                        )
                        schedule = scheduler.get('spec', {}).get('cronSchedule', schedule_name)
                    except:
                        # If we can't fetch the scheduler, just show the name
                        schedule = schedule_name
                
                # Get last execution time from most recent snapshot
                last_execution = 'Never'
                plan_name = metadata.get('name', 'Unknown')
                plan_namespace = metadata.get('namespace', 'default')
                try:
                    # Fetch snapshots with label selector for this protection plan
                    snapshots = k8s_api.list_namespaced_custom_object(
                        group=Config.NDK_API_GROUP,
                        version=Config.NDK_API_VERSION,
                        namespace=plan_namespace,
                        plural='applicationsnapshots',
                        label_selector=f'protectionplan={plan_name}'
                    )
                    
                    # Find the most recent snapshot creation time
                    latest_time = None
                    for snap in snapshots.get('items', []):
                        snap_status = snap.get('status', {})
                        creation_time = snap_status.get('creationTime')
                        if creation_time:
                            if latest_time is None or creation_time > latest_time:
                                latest_time = creation_time
                    
                    if latest_time:
                        last_execution = latest_time
                except:
                    # If we can't fetch snapshots, keep 'Never'
                    pass
                
                # Check if the plan is stuck in deletion (has deletionTimestamp)
                deletion_timestamp = metadata.get('deletionTimestamp')
                finalizers = metadata.get('finalizers', [])
                is_deleting = deletion_timestamp is not None
                
                # Extract selection mode and label selector from annotations
                annotations = metadata.get('annotations', {})
                selection_mode = annotations.get('ndk-dashboard/selection-mode', 'by-name')
                label_selector_key = annotations.get('ndk-dashboard/label-selector-key')
                label_selector_value = annotations.get('ndk-dashboard/label-selector-value')
                
                plans.append({
                    'name': plan_name,
                    'namespace': plan_namespace,
                    'created': metadata.get('creationTimestamp', ''),
                    'schedule': schedule,
                    'retention': retention,
                    'applications': spec.get('applications', []),
                    'suspend': spec.get('suspend', False),
                    'state': status.get('state', 'Unknown'),
                    'lastExecution': last_execution,
                    'isDeleting': is_deleting,
                    'hasFinalizers': len(finalizers) > 0,
                    'selectionMode': selection_mode,
                    'labelSelectorKey': label_selector_key,
                    'labelSelectorValue': label_selector_value
                })
            
            return plans
        except ApiException as e:
            print(f"Error fetching protection plans: {e}")
            return []
    
    return jsonify(get_cached_or_fetch('protectionplans', fetch))

@app.route('/api/protectionplans/<namespace>/<name>', methods=['GET', 'DELETE', 'PUT'])
@login_required
def manage_protection_plan(namespace, name):
    """Get or delete a specific protection plan"""
    if request.method == 'GET':
        # Get single protection plan
        try:
            if not k8s_api:
                return jsonify({'error': 'Kubernetes API not available'}), 503
            
            result = k8s_api.get_namespaced_custom_object(
                group=Config.NDK_API_GROUP,
                version=Config.NDK_API_VERSION,
                namespace=namespace,
                plural='protectionplans',
                name=name
            )
            
            metadata = result.get('metadata', {})
            spec = result.get('spec', {})
            status = result.get('status', {})
            
            plan = {
                'name': metadata.get('name', 'Unknown'),
                'namespace': metadata.get('namespace', 'default'),
                'created': metadata.get('creationTimestamp', ''),
                'schedule': spec.get('schedule', 'Not set'),
                'retention': spec.get('retention', 'Not set'),
                'selector': spec.get('applicationSelector', {}),
                'suspend': spec.get('suspend', False),
                'state': status.get('state', 'Unknown'),
                'lastExecution': status.get('lastExecutionTime', 'Never')
            }
            
            return jsonify(plan), 200
            
        except ApiException as e:
            return jsonify({'error': f'Failed to get protection plan: {e.reason}'}), e.status
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    elif request.method == 'DELETE':
        # Delete protection plan
        try:
            if not k8s_api:
                return jsonify({'error': 'Kubernetes API not available'}), 503
            
            # Check if force delete is requested
            force = request.args.get('force', 'false').lower() == 'true'
            
            # First, get the protection plan to find the associated scheduler
            try:
                plan = k8s_api.get_namespaced_custom_object(
                    group=Config.NDK_API_GROUP,
                    version=Config.NDK_API_VERSION,
                    namespace=namespace,
                    plural='protectionplans',
                    name=name
                )
                schedule_name = plan.get('spec', {}).get('scheduleName')
                
                # Delete the associated JobScheduler if it exists
                if schedule_name:
                    try:
                        k8s_api.delete_namespaced_custom_object(
                            group='scheduler.nutanix.com',
                            version='v1alpha1',
                            namespace=namespace,
                            plural='jobschedulers',
                            name=schedule_name
                        )
                    except:
                        # If scheduler doesn't exist or can't be deleted, continue anyway
                        pass
                
                # If force delete, remove finalizers first
                if force:
                    metadata = plan.get('metadata', {})
                    if metadata.get('finalizers'):
                        # Remove all finalizers
                        patch = {
                            'metadata': {
                                'finalizers': []
                            }
                        }
                        k8s_api.patch_namespaced_custom_object(
                            group=Config.NDK_API_GROUP,
                            version=Config.NDK_API_VERSION,
                            namespace=namespace,
                            plural='protectionplans',
                            name=name,
                            body=patch
                        )
                        print(f"✓ Removed finalizers from protection plan {name}")
                        
                        # After removing finalizers, if the resource had a deletionTimestamp,
                        # Kubernetes will delete it automatically. Wait a moment and check.
                        import time
                        time.sleep(0.5)
                        
                        # Check if the resource still exists
                        try:
                            k8s_api.get_namespaced_custom_object(
                                group=Config.NDK_API_GROUP,
                                version=Config.NDK_API_VERSION,
                                namespace=namespace,
                                plural='protectionplans',
                                name=name
                            )
                            # Resource still exists, proceed with deletion
                        except ApiException as e:
                            if e.status == 404:
                                # Resource was already deleted by Kubernetes after finalizer removal
                                print(f"✓ Protection plan {name} was automatically deleted after finalizer removal")
                                cache['protectionplans'] = {'data': None, 'timestamp': None}
                                return jsonify({
                                    'success': True,
                                    'message': f'Protection plan {name} deleted successfully (finalizers removed)'
                                }), 200
                            raise
            except:
                # If we can't get the plan details, continue with deletion anyway
                pass
            
            # Delete the protection plan (if it still exists)
            try:
                k8s_api.delete_namespaced_custom_object(
                    group=Config.NDK_API_GROUP,
                    version=Config.NDK_API_VERSION,
                    namespace=namespace,
                    plural='protectionplans',
                    name=name
                )
            except ApiException as e:
                if e.status == 404:
                    # Already deleted, that's fine
                    print(f"✓ Protection plan {name} was already deleted")
                else:
                    raise
            
            # Invalidate cache
            cache['protectionplans'] = {'data': None, 'timestamp': None}
            
            return jsonify({
                'success': True,
                'message': f'Protection plan {name} deleted successfully'
            }), 200
            
        except ApiException as e:
            return jsonify({'error': f'Failed to delete protection plan: {e.reason}'}), e.status
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    elif request.method == 'PUT':
        # Update protection plan
        try:
            if not k8s_api:
                return jsonify({'error': 'Kubernetes API not available'}), 503
            
            data = request.get_json()
            schedule = data.get('schedule')
            retention = data.get('retention')
            suspend = data.get('suspend')
            
            # Get current protection plan
            plan = k8s_api.get_namespaced_custom_object(
                group=Config.NDK_API_GROUP,
                version=Config.NDK_API_VERSION,
                namespace=namespace,
                plural='protectionplans',
                name=name
            )
            
            # Build patch object with only provided fields
            patch = {'spec': {}}
            
            if schedule is not None:
                patch['spec']['schedule'] = schedule
            
            if retention is not None:
                # Validate retention (can be count or duration)
                if isinstance(retention, int):
                    # Count-based retention (NDK requires 1-15)
                    if retention < 1 or retention > 15:
                        return jsonify({'error': 'Retention count must be between 1 and 15'}), 400
                    patch['spec']['retention'] = retention
                elif isinstance(retention, str):
                    # Duration-based retention (e.g., "168h", "720h")
                    # Validate format: should end with 'h', 'd', 'm', or 's' and have a number before it
                    import re
                    if not re.match(r'^\d+[hdms]$', retention):
                        return jsonify({'error': 'Retention duration must be in format like "168h", "7d", "30d", etc.'}), 400
                    patch['spec']['retention'] = retention
                else:
                    return jsonify({'error': 'Retention must be a number (for count) or duration string (for time-based)'}), 400
            
            if suspend is not None:
                patch['spec']['suspend'] = suspend
            
            # Apply the patch
            k8s_api.patch_namespaced_custom_object(
                group=Config.NDK_API_GROUP,
                version=Config.NDK_API_VERSION,
                namespace=namespace,
                plural='protectionplans',
                name=name,
                body=patch
            )
            
            # Invalidate cache
            cache['protectionplans'] = {'data': None, 'timestamp': None}
            
            return jsonify({
                'success': True,
                'message': f'Protection plan {name} updated successfully'
            }), 200
            
        except ApiException as e:
            return jsonify({'error': f'Failed to update protection plan: {e.reason}'}), e.status
        except Exception as e:
            return jsonify({'error': str(e)}), 500

@app.route('/api/protectionplans', methods=['POST'])
@login_required
def create_protection_plan():
    """Create a new protection plan"""
    try:
        if not k8s_api:
            return jsonify({'error': 'Kubernetes API not available'}), 503
        
        data = request.get_json()
        plan_name = data.get('name')
        plan_namespace = data.get('namespace', 'default')
        schedule = data.get('schedule')
        retention = data.get('retention')
        selection_mode = data.get('selectionMode', 'by-name')
        applications = data.get('applications', [])  # List of application names to protect (for by-name mode)
        label_selector = data.get('labelSelector', {})  # Label selector (for by-label mode)
        enabled = data.get('enabled', True)
        
        if not plan_name or not schedule or not retention:
            return jsonify({'error': 'Name, schedule, and retention are required'}), 400
        
        # Validate selection mode
        if selection_mode == 'by-name':
            if not applications or len(applications) == 0:
                return jsonify({'error': 'At least one application must be selected'}), 400
            
            # Validate that all applications are in the same namespace as the plan
            # AppProtectionPlan resources are namespace-scoped and must be in the same namespace as the application
            for app_info in applications:
                app_namespace = app_info.get('namespace', 'default')
                if app_namespace != plan_namespace:
                    return jsonify({
                        'error': f'Application "{app_info.get("name")}" is in namespace "{app_namespace}" but the plan is in "{plan_namespace}". AppProtectionPlan resources must be in the same namespace as the application they protect.'
                    }), 400
        elif selection_mode == 'by-label':
            if not label_selector or not label_selector.get('key') or not label_selector.get('value'):
                return jsonify({'error': 'Label key and value are required for label-based selection'}), 400
        else:
            return jsonify({'error': 'Invalid selection mode'}), 400
        
        # Validate retention (must be count-based, NDK requires 1-15)
        if not isinstance(retention, int):
            return jsonify({'error': 'Retention must be a number between 1 and 15'}), 400
        
        if retention < 1 or retention > 15:
            return jsonify({'error': 'Retention count must be between 1 and 15'}), 400
        
        # First, create a JobScheduler resource
        schedule_name = f'{plan_name}-schedule'
        scheduler_manifest = {
            'apiVersion': 'scheduler.nutanix.com/v1alpha1',
            'kind': 'JobScheduler',
            'metadata': {
                'name': schedule_name,
                'namespace': plan_namespace
            },
            'spec': {
                'cronSchedule': schedule
            }
        }
        
        # Create the JobScheduler
        k8s_api.create_namespaced_custom_object(
            group='scheduler.nutanix.com',
            version='v1alpha1',
            namespace=plan_namespace,
            plural='jobschedulers',
            body=scheduler_manifest
        )
        
        # Build retention policy (NDK only supports count-based retention)
        retention_policy = {
            'retentionCount': retention
        }
        
        # Create protection plan manifest
        # NOTE: ProtectionPlans define the schedule and retention policy.
        # For by-name mode: AppProtectionPlan resources (created below) link specific applications to this plan.
        # For by-label mode: Applications are dynamically selected at trigger time based on labels.
        # Both the ProtectionPlan and AppProtectionPlan must be in the same namespace as the application.
        plan_manifest = {
            'apiVersion': f'{Config.NDK_API_GROUP}/{Config.NDK_API_VERSION}',
            'kind': 'ProtectionPlan',
            'metadata': {
                'name': plan_name,
                'namespace': plan_namespace,
                'annotations': {
                    'ndk-dashboard/selection-mode': selection_mode
                }
            },
            'spec': {
                'scheduleName': schedule_name,  # Reference the JobScheduler
                'protectionType': 'async',
                'retentionPolicy': retention_policy,
                'suspend': not enabled  # NDK uses 'suspend' instead of 'enabled'
            }
        }
        
        # Store label selector in annotations if using by-label mode
        if selection_mode == 'by-label':
            plan_manifest['metadata']['annotations']['ndk-dashboard/label-selector-key'] = label_selector['key']
            plan_manifest['metadata']['annotations']['ndk-dashboard/label-selector-value'] = label_selector['value']
        
        # Create the protection plan
        result = k8s_api.create_namespaced_custom_object(
            group=Config.NDK_API_GROUP,
            version=Config.NDK_API_VERSION,
            namespace=plan_namespace,
            plural='protectionplans',
            body=plan_manifest
        )
        
        # Create AppProtectionPlan for each selected application (only for by-name mode)
        app_protection_plans_created = []
        app_protection_plans_failed = []
        
        if selection_mode == 'by-name':
            for app_info in applications:
                app_name = app_info.get('name')
                app_namespace = app_info.get('namespace', plan_namespace)
                
                try:
                    app_protection_plan_manifest = {
                        'apiVersion': f'{Config.NDK_API_GROUP}/{Config.NDK_API_VERSION}',
                        'kind': 'AppProtectionPlan',
                        'metadata': {
                            'name': f'{app_name}-{plan_name}',
                            'namespace': app_namespace
                        },
                        'spec': {
                            'applicationName': app_name,
                            'protectionPlanNames': [plan_name]
                        }
                    }
                    
                    k8s_api.create_namespaced_custom_object(
                        group=Config.NDK_API_GROUP,
                        version=Config.NDK_API_VERSION,
                        namespace=app_namespace,
                        plural='appprotectionplans',
                        body=app_protection_plan_manifest
                    )
                    
                    app_protection_plans_created.append(f'{app_name} ({app_namespace})')
                except ApiException as e:
                    app_protection_plans_failed.append(f'{app_name} ({app_namespace}): {e.reason}')
        
        # Invalidate cache
        cache['protectionplans'] = {'data': None, 'timestamp': None}
        
        message = f'Protection plan {plan_name} created successfully'
        if selection_mode == 'by-label':
            message += f' with label selector {label_selector["key"]}={label_selector["value"]}'
        if app_protection_plans_created:
            message += f'. Protected applications: {", ".join(app_protection_plans_created)}'
        if app_protection_plans_failed:
            message += f'. Failed to protect: {", ".join(app_protection_plans_failed)}'
        
        return jsonify({
            'success': True,
            'message': message,
            'plan': {
                'name': plan_name,
                'namespace': plan_namespace
            },
            'protectedApplications': app_protection_plans_created,
            'failedApplications': app_protection_plans_failed
        }), 201
        
    except ApiException as e:
        error_msg = f"Failed to create protection plan: {e.reason}"
        if e.body:
            try:
                import json
                error_body = json.loads(e.body)
                error_msg = error_body.get('message', error_msg)
            except:
                pass
        return jsonify({'error': error_msg}), e.status
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/protectionplans/<namespace>/<name>/enable', methods=['POST'])
@login_required
def enable_protection_plan(namespace, name):
    """Enable a protection plan"""
    try:
        if not k8s_api:
            return jsonify({'error': 'Kubernetes API not available'}), 503
        
        # Get existing plan
        existing = k8s_api.get_namespaced_custom_object(
            group=Config.NDK_API_GROUP,
            version=Config.NDK_API_VERSION,
            namespace=namespace,
            plural='protectionplans',
            name=name
        )
        
        # Update suspend status (suspend=False means enabled)
        existing['spec']['suspend'] = False
        
        # Update the plan
        k8s_api.replace_namespaced_custom_object(
            group=Config.NDK_API_GROUP,
            version=Config.NDK_API_VERSION,
            namespace=namespace,
            plural='protectionplans',
            name=name,
            body=existing
        )
        
        # Invalidate cache
        cache['protectionplans'] = {'data': None, 'timestamp': None}
        
        return jsonify({
            'success': True,
            'message': f'Protection plan {name} enabled successfully'
        }), 200
        
    except ApiException as e:
        return jsonify({'error': f'Failed to enable protection plan: {e.reason}'}), e.status
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/protectionplans/<namespace>/<name>/disable', methods=['POST'])
@login_required
def disable_protection_plan(namespace, name):
    """Disable a protection plan"""
    try:
        if not k8s_api:
            return jsonify({'error': 'Kubernetes API not available'}), 503
        
        # Get existing plan
        existing = k8s_api.get_namespaced_custom_object(
            group=Config.NDK_API_GROUP,
            version=Config.NDK_API_VERSION,
            namespace=namespace,
            plural='protectionplans',
            name=name
        )
        
        # Update suspend status (suspend=True means disabled)
        existing['spec']['suspend'] = True
        
        # Update the plan
        k8s_api.replace_namespaced_custom_object(
            group=Config.NDK_API_GROUP,
            version=Config.NDK_API_VERSION,
            namespace=namespace,
            plural='protectionplans',
            name=name,
            body=existing
        )
        
        # Invalidate cache
        cache['protectionplans'] = {'data': None, 'timestamp': None}
        
        return jsonify({
            'success': True,
            'message': f'Protection plan {name} disabled successfully'
        }), 200
        
    except ApiException as e:
        return jsonify({'error': f'Failed to disable protection plan: {e.reason}'}), e.status
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/protectionplans/<namespace>/<name>/trigger', methods=['POST'])
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
        cache['snapshots'] = {'data': None, 'timestamp': None}
        cache['protectionplans'] = {'data': None, 'timestamp': None}
        
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

@app.route('/api/protectionplans/<namespace>/<name>/history')
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

@app.route('/api/stats')
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

@app.route('/api/namespaces', methods=['GET'])
@login_required
def get_namespaces():
    """Get list of all namespaces"""
    if not k8s_core_api:
        return jsonify({'error': 'Kubernetes API not available'}), 500
    
    try:
        namespaces = k8s_core_api.list_namespace()
        namespace_list = [ns.metadata.name for ns in namespaces.items]
        return jsonify({'namespaces': sorted(namespace_list)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/workerpools', methods=['GET'])
@login_required
def get_worker_pools():
    """Get list of available worker pools from node labels and names"""
    if not k8s_core_api:
        return jsonify({'error': 'Kubernetes API not available'}), 500
    
    try:
        import re
        nodes = k8s_core_api.list_node()
        worker_pools = set()
        
        # Extract worker pool labels from nodes
        # Priority: 1) Node name pattern (NKP), 2) Explicit labels
        for node in nodes.items:
            labels = node.metadata.labels or {}
            node_name = node.metadata.name
            
            # First, try to extract worker pool from node name (for NKP/Karbon clusters)
            # Pattern: nkp-{cluster}-{id}-{POOL_NAME}-worker-{N}
            # Example: nkp-dev01-a8970c-nkp-dev-worker-pool-worker-0 -> nkp-dev-worker-pool
            match = re.search(r'nkp-[^-]+-[^-]+-(.+?)-worker-\d+$', node_name)
            if match:
                pool_name = match.group(1)
                worker_pools.add(pool_name)
            else:
                # If no node name pattern, fall back to label-based detection
                # Check for Nutanix Karbon/NKP label
                if 'karbon.nutanix.com/workerpool' in labels:
                    pool_name = labels['karbon.nutanix.com/workerpool']
                    if pool_name:
                        worker_pools.add(pool_name)
                # Check for nodepool label (common in NKP)
                elif 'nodepool' in labels:
                    pool_name = labels['nodepool']
                    if pool_name:
                        worker_pools.add(pool_name)
                # Check for common worker pool label patterns
                elif 'node-role.kubernetes.io/worker-pool' in labels:
                    pool_name = labels['node-role.kubernetes.io/worker-pool']
                    if pool_name:
                        worker_pools.add(pool_name)
                elif 'worker-pool' in labels:
                    pool_name = labels['worker-pool']
                    if pool_name:
                        worker_pools.add(pool_name)
                elif 'pool' in labels:
                    pool_name = labels['pool']
                    if pool_name:
                        worker_pools.add(pool_name)
        
        return jsonify({'workerPools': sorted(list(worker_pools))})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/deploy', methods=['POST'])
@login_required
def deploy_application():
    """Deploy a new application with NDK capabilities"""
    if not k8s_api or not k8s_core_api:
        return jsonify({'error': 'Kubernetes API not available'}), 500
    
    try:
        import secrets
        import string
        
        data = request.get_json()
        
        # Extract deployment configuration
        app_type = data.get('appType')
        app_name = data.get('name')  # Frontend sends 'name'
        namespace = data.get('namespace')
        replicas = int(data.get('replicas', 1))
        storage_class = data.get('storageClass')
        storage_size = data.get('storageSize')
        password = data.get('password')
        database_name = data.get('database')  # Frontend sends 'database'
        docker_image = data.get('image')  # Frontend sends 'image'
        port = int(data.get('port', 3306))
        create_ndk_app = data.get('createNDKApp', False)  # Frontend sends 'createNDKApp'
        custom_labels = data.get('labels', {})  # Custom labels from user
        worker_pool = data.get('workerPool')  # Worker pool selection
        
        # Handle protection plan (can be nested object or flat fields)
        protection_plan = data.get('protectionPlan', {})
        create_protection_plan = bool(protection_plan)
        schedule = protection_plan.get('schedule', '0 2 * * *') if protection_plan else '0 2 * * *'
        retention = protection_plan.get('retention', 7) if protection_plan else 7
        
        # Validate required fields
        if not all([app_type, app_name, namespace, storage_size, docker_image]):
            return jsonify({'error': 'Missing required fields'}), 400
        
        # Validate retention count if protection plan is enabled
        if create_protection_plan:
            try:
                retention_int = int(retention)
                if retention_int < 1 or retention_int > 15:
                    return jsonify({'error': 'Retention count must be between 1 and 15'}), 400
            except (ValueError, TypeError):
                return jsonify({'error': 'Retention count must be a valid number between 1 and 15'}), 400
        
        # Use default storage class if not specified or set to 'default'
        if not storage_class or storage_class == 'default':
            storage_class = None
        
        # Generate password if not provided
        if not password:
            alphabet = string.ascii_letters + string.digits
            password = ''.join(secrets.choice(alphabet) for i in range(16))
        
        # Step 1: Create namespace if it doesn't exist
        try:
            k8s_core_api.read_namespace(namespace)
        except ApiException as e:
            if e.status == 404:
                namespace_manifest = {
                    'apiVersion': 'v1',
                    'kind': 'Namespace',
                    'metadata': {'name': namespace}
                }
                k8s_core_api.create_namespace(body=namespace_manifest)
        
        # Step 2: Create Secret for credentials
        secret_name = f"{app_name}-credentials"
        secret_data = {
            'password': password
        }
        if database_name:
            secret_data['database'] = database_name
        
        # Encode secret data to base64
        import base64
        encoded_secret_data = {k: base64.b64encode(v.encode()).decode() for k, v in secret_data.items()}
        
        secret_manifest = {
            'apiVersion': 'v1',
            'kind': 'Secret',
            'metadata': {
                'name': secret_name,
                'namespace': namespace
            },
            'type': 'Opaque',
            'data': encoded_secret_data
        }
        
        try:
            k8s_core_api.create_namespaced_secret(namespace=namespace, body=secret_manifest)
        except ApiException as e:
            if e.status != 409:  # Ignore if already exists
                raise
        
        # Step 3: Create StatefulSet
        apps_api = client.AppsV1Api()
        
        # Build environment variables based on app type
        env_vars = []
        if app_type == 'mysql':
            env_vars = [
                {'name': 'MYSQL_ROOT_PASSWORD', 'valueFrom': {'secretKeyRef': {'name': secret_name, 'key': 'password'}}},
            ]
            if database_name:
                env_vars.append({'name': 'MYSQL_DATABASE', 'value': database_name})
        elif app_type == 'postgresql':
            env_vars = [
                {'name': 'POSTGRES_PASSWORD', 'valueFrom': {'secretKeyRef': {'name': secret_name, 'key': 'password'}}},
            ]
            if database_name:
                env_vars.append({'name': 'POSTGRES_DB', 'value': database_name})
        elif app_type == 'mongodb':
            env_vars = [
                {'name': 'MONGO_INITDB_ROOT_USERNAME', 'value': 'admin'},
                {'name': 'MONGO_INITDB_ROOT_PASSWORD', 'valueFrom': {'secretKeyRef': {'name': secret_name, 'key': 'password'}}},
            ]
        elif app_type == 'redis':
            env_vars = [
                {'name': 'REDIS_PASSWORD', 'valueFrom': {'secretKeyRef': {'name': secret_name, 'key': 'password'}}},
            ]
        elif app_type == 'elasticsearch':
            env_vars = [
                {'name': 'ELASTIC_PASSWORD', 'valueFrom': {'secretKeyRef': {'name': secret_name, 'key': 'password'}}},
                {'name': 'discovery.type', 'value': 'single-node'},
                {'name': 'xpack.security.enabled', 'value': 'true'},
            ]
        elif app_type == 'cassandra':
            env_vars = [
                {'name': 'CASSANDRA_PASSWORD', 'valueFrom': {'secretKeyRef': {'name': secret_name, 'key': 'password'}}},
            ]
        
        statefulset_manifest = {
            'apiVersion': 'apps/v1',
            'kind': 'StatefulSet',
            'metadata': {
                'name': app_name,
                'namespace': namespace,
                'labels': {
                    'app': app_name,
                    'app.kubernetes.io/name': app_type,
                    'app.kubernetes.io/managed-by': 'ndk-dashboard'
                }
            },
            'spec': {
                'serviceName': app_name,
                'replicas': replicas,
                'selector': {
                    'matchLabels': {
                        'app': app_name
                    }
                },
                'template': {
                    'metadata': {
                        'labels': {
                            'app': app_name,
                            'app.kubernetes.io/name': app_type
                        }
                    },
                    'spec': {
                        'containers': [{
                            'name': app_type,
                            'image': docker_image,
                            'ports': [{'containerPort': port, 'name': app_type}],
                            'env': env_vars,
                            'volumeMounts': [{
                                'name': 'data',
                                'mountPath': '/var/lib/mysql' if app_type == 'mysql' else
                                            '/var/lib/postgresql/data' if app_type == 'postgresql' else
                                            '/data/db' if app_type == 'mongodb' else
                                            '/data' if app_type == 'redis' else
                                            '/usr/share/elasticsearch/data' if app_type == 'elasticsearch' else
                                            '/var/lib/cassandra'
                            }]
                        }]
                    }
                },
                'volumeClaimTemplates': [{
                    'metadata': {
                        'name': 'data'
                    },
                    'spec': {
                        'accessModes': ['ReadWriteOnce'],
                        'storageClassName': storage_class,
                        'resources': {
                            'requests': {
                                'storage': storage_size
                            }
                        }
                    }
                }]
            }
        }
        
        # Add nodeSelector if worker pool is specified
        if worker_pool:
            import re
            # Try common worker pool label patterns
            node_selector = {}
            pool_label_key = None
            pool_label_value = None
            
            # Check which label pattern is used in the cluster
            nodes = k8s_core_api.list_node()
            for node in nodes.items:
                labels = node.metadata.labels or {}
                node_name = node.metadata.name
                
                # Check if this node matches the selected worker pool
                node_matches = False
                
                # Check label-based matching (direct label value match)
                if 'karbon.nutanix.com/workerpool' in labels and labels['karbon.nutanix.com/workerpool'] == worker_pool:
                    pool_label_key = 'karbon.nutanix.com/workerpool'
                    pool_label_value = worker_pool
                    node_matches = True
                elif 'nodepool' in labels and labels['nodepool'] == worker_pool:
                    pool_label_key = 'nodepool'
                    pool_label_value = worker_pool
                    node_matches = True
                elif 'node-role.kubernetes.io/worker-pool' in labels and labels['node-role.kubernetes.io/worker-pool'] == worker_pool:
                    pool_label_key = 'node-role.kubernetes.io/worker-pool'
                    pool_label_value = worker_pool
                    node_matches = True
                elif 'worker-pool' in labels and labels['worker-pool'] == worker_pool:
                    pool_label_key = 'worker-pool'
                    pool_label_value = worker_pool
                    node_matches = True
                elif 'pool' in labels and labels['pool'] == worker_pool:
                    pool_label_key = 'pool'
                    pool_label_value = worker_pool
                    node_matches = True
                
                # Check node name-based matching (for NKP/Karbon clusters)
                # If worker pool name is in the node name, find the actual label to use
                if not node_matches:
                    match = re.search(r'nkp-[^-]+-[^-]+-(.+?)-worker-\d+$', node_name)
                    if match and match.group(1) == worker_pool:
                        # Found a node with this pool name - use its nodepool label if available
                        if 'nodepool' in labels:
                            pool_label_key = 'nodepool'
                            pool_label_value = labels['nodepool']
                            node_matches = True
                        elif 'karbon.nutanix.com/workerpool' in labels:
                            pool_label_key = 'karbon.nutanix.com/workerpool'
                            pool_label_value = labels['karbon.nutanix.com/workerpool']
                            node_matches = True
                
                if node_matches:
                    break
            
            if pool_label_key and pool_label_value:
                node_selector = {pool_label_key: pool_label_value}
                statefulset_manifest['spec']['template']['spec']['nodeSelector'] = node_selector
        
        apps_api.create_namespaced_stateful_set(namespace=namespace, body=statefulset_manifest)
        
        # Step 4: Create Service
        service_manifest = {
            'apiVersion': 'v1',
            'kind': 'Service',
            'metadata': {
                'name': app_name,
                'namespace': namespace,
                'labels': {
                    'app': app_name
                }
            },
            'spec': {
                'ports': [{
                    'port': port,
                    'name': app_type
                }],
                'clusterIP': 'None',
                'selector': {
                    'app': app_name
                }
            }
        }
        
        k8s_core_api.create_namespaced_service(namespace=namespace, body=service_manifest)
        
        # Step 5: Create NDK Application CR if requested
        if create_ndk_app:
            # Build metadata with custom labels
            metadata = {
                'name': app_name,
                'namespace': namespace
            }
            
            # Add custom labels if provided
            if custom_labels:
                metadata['labels'] = custom_labels
            
            ndk_app_manifest = {
                'apiVersion': f'{Config.NDK_API_GROUP}/{Config.NDK_API_VERSION}',
                'kind': 'Application',
                'metadata': metadata,
                'spec': {
                    'selector': {
                        'matchLabels': {
                            'app': app_name
                        }
                    }
                }
            }
            
            k8s_api.create_namespaced_custom_object(
                group=Config.NDK_API_GROUP,
                version=Config.NDK_API_VERSION,
                namespace=namespace,
                plural='applications',
                body=ndk_app_manifest
            )
        
        # Step 6: Create Protection Plan if requested
        if create_protection_plan and create_ndk_app:
            app.logger.info(f"Creating protection plan for {app_name} with schedule={schedule}, retention={retention}")
            schedule_name = f"{app_name}-schedule"
            protection_plan_name = f"{app_name}-plan"
            app_protection_plan_name = f"{app_name}-protection"
            
            # Parse retention to get count (can be int or string like "7d")
            if isinstance(retention, str):
                retention_count = int(retention.rstrip('dDwWmMyY'))
            else:
                retention_count = int(retention)
            
            # Step 6a: Create JobScheduler
            schedule_manifest = {
                'apiVersion': 'scheduler.nutanix.com/v1alpha1',
                'kind': 'JobScheduler',
                'metadata': {
                    'name': schedule_name,
                    'namespace': namespace
                },
                'spec': {
                    'cronSchedule': schedule
                }
            }
            
            app.logger.info(f"Creating JobScheduler: {schedule_name}")
            try:
                k8s_api.create_namespaced_custom_object(
                    group='scheduler.nutanix.com',
                    version='v1alpha1',
                    namespace=namespace,
                    plural='jobschedulers',
                    body=schedule_manifest
                )
                app.logger.info(f"JobScheduler {schedule_name} created successfully")
            except ApiException as e:
                if e.status == 409:
                    app.logger.warning(f"JobScheduler {schedule_name} already exists, reusing it")
                else:
                    raise
            
            # Step 6b: Create ProtectionPlan
            protection_plan_manifest = {
                'apiVersion': f'{Config.NDK_API_GROUP}/{Config.NDK_API_VERSION}',
                'kind': 'ProtectionPlan',
                'metadata': {
                    'name': protection_plan_name,
                    'namespace': namespace
                },
                'spec': {
                    'scheduleName': schedule_name,
                    'protectionType': 'async',
                    'retentionPolicy': {
                        'retentionCount': retention_count
                    }
                }
            }
            
            app.logger.info(f"Creating ProtectionPlan: {protection_plan_name}")
            try:
                k8s_api.create_namespaced_custom_object(
                    group=Config.NDK_API_GROUP,
                    version=Config.NDK_API_VERSION,
                    namespace=namespace,
                    plural='protectionplans',
                    body=protection_plan_manifest
                )
                app.logger.info(f"ProtectionPlan {protection_plan_name} created successfully")
            except ApiException as e:
                if e.status == 409:
                    app.logger.warning(f"ProtectionPlan {protection_plan_name} already exists, reusing it")
                else:
                    raise
            
            # Step 6c: Create AppProtectionPlan
            app_protection_plan_manifest = {
                'apiVersion': f'{Config.NDK_API_GROUP}/{Config.NDK_API_VERSION}',
                'kind': 'AppProtectionPlan',
                'metadata': {
                    'name': app_protection_plan_name,
                    'namespace': namespace
                },
                'spec': {
                    'applicationName': app_name,
                    'protectionPlanNames': [protection_plan_name]
                }
            }
            
            app.logger.info(f"Creating AppProtectionPlan: {app_protection_plan_name}")
            try:
                k8s_api.create_namespaced_custom_object(
                    group=Config.NDK_API_GROUP,
                    version=Config.NDK_API_VERSION,
                    namespace=namespace,
                    plural='appprotectionplans',
                    body=app_protection_plan_manifest
                )
                app.logger.info(f"AppProtectionPlan {app_protection_plan_name} created successfully")
            except ApiException as e:
                if e.status == 409:
                    app.logger.warning(f"AppProtectionPlan {app_protection_plan_name} already exists, reusing it")
                else:
                    raise
        
        # Invalidate cache
        cache['applications'] = {'data': None, 'timestamp': None}
        cache['protectionplans'] = {'data': None, 'timestamp': None}
        
        return jsonify({
            'success': True,
            'message': f'Application {app_name} deployed successfully',
            'deployment': {
                'name': app_name,
                'namespace': namespace,
                'type': app_type,
                'replicas': replicas,
                'password': password,
                'ndkEnabled': create_ndk_app,
                'protectionEnabled': create_protection_plan
            }
        }), 201
        
    except ApiException as e:
        error_msg = f"Failed to deploy application: {e.reason}"
        if e.body:
            try:
                import json
                error_body = json.loads(e.body)
                error_msg = error_body.get('message', error_msg)
            except:
                pass
        app.logger.error(f"ApiException during deployment: {error_msg}", exc_info=True)
        return jsonify({'error': error_msg}), e.status
    except Exception as e:
        app.logger.error(f"Exception during deployment: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.errorhandler(404)
def not_found(e):
    """404 error handler"""
    return render_template('404.html'), 404

@app.errorhandler(500)
def server_error(e):
    """500 error handler"""
    return render_template('500.html'), 500

if __name__ == '__main__':
    print("=" * 60)
    print("NDK Dashboard Starting...")
    print("=" * 60)
    print(f"Environment: {Config.FLASK_ENV}")
    print(f"In-cluster mode: {Config.IN_CLUSTER}")
    print(f"Cache TTL: {Config.CACHE_TTL} seconds")
    print("=" * 60)
    
    app.run(host='0.0.0.0', port=5000, debug=(Config.FLASK_ENV == 'development'))