"""
Flask extensions and Kubernetes client initialization
"""
from datetime import datetime
from kubernetes import client, config as k8s_config
from kubernetes.client.rest import ApiException
from config import Config

# Kubernetes API clients (initialized on app startup)
k8s_api = None
k8s_core_api = None
k8s_apps_api = None

# Cache for API responses
cache = {
    'applications': {'data': None, 'timestamp': None},
    'snapshots': {'data': None, 'timestamp': None},
    'storageclusters': {'data': None, 'timestamp': None},
    'protectionplans': {'data': None, 'timestamp': None}
}

# Cache buster for static files
CACHE_BUST_VERSION = str(int(datetime.now().timestamp()))


def init_kubernetes_client():
    """Initialize Kubernetes API clients"""
    global k8s_api, k8s_core_api, k8s_apps_api
    
    try:
        if Config.IN_CLUSTER:
            k8s_config.load_incluster_config()
            print("✓ Loaded in-cluster Kubernetes configuration")
        else:
            k8s_config.load_kube_config()
            print("✓ Loaded kubeconfig from local system")
        
        k8s_api = client.CustomObjectsApi()
        k8s_core_api = client.CoreV1Api()
        k8s_apps_api = client.AppsV1Api()
        print("✓ Kubernetes API client initialized")
        
        return True
    except Exception as e:
        print(f"✗ Failed to initialize Kubernetes client: {e}")
        k8s_api = None
        k8s_core_api = None
        k8s_apps_api = None
        return False


def init_extensions(app):
    """Initialize Flask extensions"""
    # Initialize Kubernetes client
    init_kubernetes_client()
    
    # Make cache bust version available in templates
    @app.context_processor
    def inject_cache_bust():
        return {'cache_bust': CACHE_BUST_VERSION}