"""
NDK Dashboard - Flask Application
Displays Nutanix Data Services for Kubernetes resources
"""
from flask import Flask, render_template, jsonify, session, redirect, url_for, request
from functools import wraps
from datetime import datetime, timedelta
import os
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
                
                applications.append({
                    'name': metadata.get('name', 'Unknown'),
                    'namespace': namespace,
                    'created': metadata.get('creationTimestamp', ''),
                    'selector': spec.get('applicationSelector', {}),
                    'state': state,
                    'message': message,
                    'lastSnapshot': status.get('lastSnapshotTime', 'Never')
                })
            
            print(f"✓ Found {len(applications)} applications across {len(all_namespaces)} namespaces")
            print(f"  All namespaces: {sorted(all_namespaces)}")
            print(f"  Non-system apps: {len(applications)}")
            
            return applications
        except ApiException as e:
            print(f"✗ Error fetching applications: {e}")
            return []
    
    return jsonify(get_cached_or_fetch('applications', fetch))

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
                
                # Determine state from readyToUse
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
                    'application': app_name,
                    'expiresAfter': spec.get('expiresAfter', 'Not set'),
                    'state': state,
                    'consistencyType': status.get('consistencyType', 'Unknown'),
                    'expirationTime': status.get('expirationTime', 'Not set')
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
        
        # Create ApplicationRestore manifest
        restore_manifest = {
            'apiVersion': f'{Config.NDK_API_GROUP}/{Config.NDK_API_VERSION}',
            'kind': 'ApplicationRestore',
            'metadata': {
                'name': restore_name,
                'namespace': target_namespace
            },
            'spec': {
                'source': {
                    'snapshotRef': {
                        'name': name,
                        'namespace': namespace
                    }
                }
            }
        }
        
        # Create the restore
        result = k8s_api.create_namespaced_custom_object(
            group=Config.NDK_API_GROUP,
            version=Config.NDK_API_VERSION,
            namespace=target_namespace,
            plural='applicationrestores',
            body=restore_manifest
        )
        
        # Invalidate cache
        cache['applications'] = {'data': None, 'timestamp': None}
        
        return jsonify({
            'success': True,
            'message': f'Restore {restore_name} initiated successfully',
            'restore': {
                'name': restore_name,
                'namespace': target_namespace,
                'snapshot': name
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
                
                plans.append({
                    'name': plan_name,
                    'namespace': plan_namespace,
                    'created': metadata.get('creationTimestamp', ''),
                    'schedule': schedule,
                    'retention': retention,
                    'applications': spec.get('applications', []),
                    'suspend': spec.get('suspend', False),
                    'state': status.get('state', 'Unknown'),
                    'lastExecution': last_execution
                })
            
            return plans
        except ApiException as e:
            print(f"Error fetching protection plans: {e}")
            return []
    
    return jsonify(get_cached_or_fetch('protectionplans', fetch))

@app.route('/api/protectionplans/<namespace>/<name>', methods=['GET', 'DELETE'])
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
            except:
                # If we can't get the plan details, continue with deletion anyway
                pass
            
            # Delete the protection plan
            k8s_api.delete_namespaced_custom_object(
                group=Config.NDK_API_GROUP,
                version=Config.NDK_API_VERSION,
                namespace=namespace,
                plural='protectionplans',
                name=name
            )
            
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
        selector = data.get('selector', {})
        enabled = data.get('enabled', True)
        
        if not plan_name or not schedule or not retention:
            return jsonify({'error': 'Name, schedule, and retention are required'}), 400
        
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
        
        # Build retention policy based on type
        if isinstance(retention, int):
            retention_policy = {
                'retentionCount': retention
            }
        else:
            # Duration-based retention
            retention_policy = {
                'maxAge': retention
            }
        
        # Create protection plan manifest
        plan_manifest = {
            'apiVersion': f'{Config.NDK_API_GROUP}/{Config.NDK_API_VERSION}',
            'kind': 'ProtectionPlan',
            'metadata': {
                'name': plan_name,
                'namespace': plan_namespace
            },
            'spec': {
                'scheduleName': schedule_name,  # Reference the JobScheduler
                'protectionType': 'async',
                'retentionPolicy': retention_policy,
                'applicationSelector': selector,
                'suspend': not enabled  # NDK uses 'suspend' instead of 'enabled'
            }
        }
        
        # Create the protection plan
        result = k8s_api.create_namespaced_custom_object(
            group=Config.NDK_API_GROUP,
            version=Config.NDK_API_VERSION,
            namespace=plan_namespace,
            plural='protectionplans',
            body=plan_manifest
        )
        
        # Invalidate cache
        cache['protectionplans'] = {'data': None, 'timestamp': None}
        
        return jsonify({
            'success': True,
            'message': f'Protection plan {plan_name} created successfully',
            'plan': {
                'name': plan_name,
                'namespace': plan_namespace
            }
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
        if not k8s_api:
            return jsonify({'error': 'Kubernetes API not available'}), 503
        
        # Get the protection plan
        plan = k8s_api.get_namespaced_custom_object(
            group=Config.NDK_API_GROUP,
            version=Config.NDK_API_VERSION,
            namespace=namespace,
            plural='protectionplans',
            name=name
        )
        
        spec = plan.get('spec', {})
        selector = spec.get('applicationSelector', {})
        retention = spec.get('retention', '720h')
        
        # Convert retention to expiresAfter format
        if isinstance(retention, int):
            # If retention is a count, use default 30 days
            expires_after = '720h'
        else:
            expires_after = retention
        
        # Find applications matching the selector
        apps_result = k8s_api.list_cluster_custom_object(
            group=Config.NDK_API_GROUP,
            version=Config.NDK_API_VERSION,
            plural='applications'
        )
        
        matching_apps = []
        match_labels = selector.get('matchLabels', {})
        
        for app in apps_result.get('items', []):
            app_metadata = app.get('metadata', {})
            app_labels = app_metadata.get('labels', {})
            
            # Check if all selector labels match
            matches = all(
                app_labels.get(key) == value 
                for key, value in match_labels.items()
            )
            
            if matches:
                matching_apps.append({
                    'name': app_metadata.get('name'),
                    'namespace': app_metadata.get('namespace')
                })
        
        if not matching_apps:
            return jsonify({'error': 'No applications match the protection plan selector'}), 404
        
        # Create snapshots for matching applications
        timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        created_snapshots = []
        
        for app in matching_apps:
            snapshot_name = f"{app['name']}-{name}-{timestamp}"
            
            snapshot_manifest = {
                'apiVersion': f'{Config.NDK_API_GROUP}/{Config.NDK_API_VERSION}',
                'kind': 'ApplicationSnapshot',
                'metadata': {
                    'name': snapshot_name,
                    'namespace': app['namespace'],
                    'labels': {
                        'protectionplan': name
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
                created_snapshots.append(snapshot_name)
            except Exception as e:
                print(f"Failed to create snapshot for {app['name']}: {e}")
        
        # Invalidate caches
        cache['snapshots'] = {'data': None, 'timestamp': None}
        cache['protectionplans'] = {'data': None, 'timestamp': None}
        
        return jsonify({
            'success': True,
            'message': f'Created {len(created_snapshots)} snapshot(s)',
            'snapshots': created_snapshots
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
        
        # Handle protection plan (can be nested object or flat fields)
        protection_plan = data.get('protectionPlan', {})
        create_protection_plan = bool(protection_plan)
        schedule = protection_plan.get('schedule', '0 2 * * *') if protection_plan else '0 2 * * *'
        retention = protection_plan.get('retention', 7) if protection_plan else 7
        
        # Validate required fields
        if not all([app_type, app_name, namespace, storage_size, docker_image]):
            return jsonify({'error': 'Missing required fields'}), 400
        
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
            ndk_app_manifest = {
                'apiVersion': f'{Config.NDK_API_GROUP}/{Config.NDK_API_VERSION}',
                'kind': 'Application',
                'metadata': {
                    'name': app_name,
                    'namespace': namespace
                },
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
            k8s_api.create_namespaced_custom_object(
                group='scheduler.nutanix.com',
                version='v1alpha1',
                namespace=namespace,
                plural='jobschedulers',
                body=schedule_manifest
            )
            app.logger.info(f"JobScheduler {schedule_name} created successfully")
            
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
            k8s_api.create_namespaced_custom_object(
                group=Config.NDK_API_GROUP,
                version=Config.NDK_API_VERSION,
                namespace=namespace,
                plural='protectionplans',
                body=protection_plan_manifest
            )
            app.logger.info(f"ProtectionPlan {protection_plan_name} created successfully")
            
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
            k8s_api.create_namespaced_custom_object(
                group=Config.NDK_API_GROUP,
                version=Config.NDK_API_VERSION,
                namespace=namespace,
                plural='appprotectionplans',
                body=app_protection_plan_manifest
            )
            app.logger.info(f"AppProtectionPlan {app_protection_plan_name} created successfully")
        
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