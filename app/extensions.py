"""
Flask extensions and Kubernetes client initialization
"""
from datetime import datetime
from functools import wraps
from kubernetes import client, config as k8s_config
from kubernetes.client.rest import ApiException
from config import Config

# Kubernetes API clients (initialized on app startup)
k8s_api = None
k8s_core_api = None
k8s_apps_api = None
k8s_storage_api = None

# Cache for API responses
cache = {
    'applicationcrds': {'data': None, 'timestamp': None},
    'snapshots': {'data': None, 'timestamp': None},
    'storageclusters': {'data': None, 'timestamp': None},
    'protectionplans': {'data': None, 'timestamp': None},
    'applicationsnapshotrestores': {'data': None, 'timestamp': None},
    'persistentvolumeclaims': {'data': None, 'timestamp': None},
    'persistentvolumes': {'data': None, 'timestamp': None},
    'volumesnapshots': {'data': None, 'timestamp': None}
}

# Cache buster for static files
CACHE_BUST_VERSION = str(int(datetime.now().timestamp()))

# Track last successful authentication
_last_auth_time = None
_auth_retry_count = 0
_max_auth_retries = 3


def init_kubernetes_client(force_reload=False):
    """
    Initialize Kubernetes API clients
    
    Args:
        force_reload: Force reload of kubeconfig (useful for credential refresh)
    """
    global k8s_api, k8s_core_api, k8s_apps_api, k8s_storage_api, _last_auth_time, _auth_retry_count
    
    try:
        if Config.IN_CLUSTER:
            k8s_config.load_incluster_config()
            print("✓ Loaded in-cluster Kubernetes configuration")
        else:
            # Force reload kubeconfig to pick up refreshed credentials
            k8s_config.load_kube_config()
            print(f"✓ Loaded kubeconfig from local system{' (refreshed)' if force_reload else ''}")
        
        k8s_api = client.CustomObjectsApi()
        k8s_core_api = client.CoreV1Api()
        k8s_apps_api = client.AppsV1Api()
        k8s_storage_api = client.StorageV1Api()
        print("✓ Kubernetes API client initialized")
        
        _last_auth_time = datetime.now()
        _auth_retry_count = 0
        
        return True
    except Exception as e:
        print(f"✗ Failed to initialize Kubernetes client: {e}")
        k8s_api = None
        k8s_core_api = None
        k8s_apps_api = None
        k8s_storage_api = None
        return False


def is_auth_error(exception):
    """Check if an exception is an authentication/authorization error"""
    if isinstance(exception, ApiException):
        # 401 Unauthorized or 403 Forbidden
        return exception.status in [401, 403]
    return False


def handle_auth_error():
    """
    Handle authentication errors by attempting to reinitialize the Kubernetes client
    
    Returns:
        bool: True if reinitialization was successful, False otherwise
    """
    global _auth_retry_count
    
    if _auth_retry_count >= _max_auth_retries:
        print(f"✗ Max authentication retry attempts ({_max_auth_retries}) reached")
        return False
    
    _auth_retry_count += 1
    print(f"⚠ Authentication error detected. Attempting to refresh credentials (attempt {_auth_retry_count}/{_max_auth_retries})...")
    
    # Reinitialize the client to pick up refreshed credentials
    success = init_kubernetes_client(force_reload=True)
    
    if success:
        print("✓ Kubernetes client reinitialized successfully")
    else:
        print("✗ Failed to reinitialize Kubernetes client")
    
    return success


def with_auth_retry(func):
    """
    Decorator to automatically retry API calls with credential refresh on auth errors
    
    Usage:
        @with_auth_retry
        def my_api_call():
            return k8s_api.list_cluster_custom_object(...)
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ApiException as e:
            if is_auth_error(e):
                print(f"⚠ Authentication error in {func.__name__}: {e.status} {e.reason}")
                
                # Try to refresh credentials and retry once
                if handle_auth_error():
                    print(f"↻ Retrying {func.__name__} after credential refresh...")
                    try:
                        return func(*args, **kwargs)
                    except Exception as retry_error:
                        print(f"✗ Retry failed for {func.__name__}: {retry_error}")
                        raise
                else:
                    print(f"✗ Could not refresh credentials for {func.__name__}")
                    raise
            else:
                # Not an auth error, re-raise
                raise
    return wrapper


def init_extensions(app):
    """Initialize Flask extensions"""
    # Initialize Kubernetes client
    init_kubernetes_client()
    
    # Make cache bust version available in templates
    @app.context_processor
    def inject_cache_bust():
        return {'cache_bust': CACHE_BUST_VERSION}