"""
Storage service - Business logic for NDK Storage Clusters
"""
import base64
from kubernetes.client.rest import ApiException
from app.extensions import k8s_api, k8s_core_api
from config import Config


class StorageService:
    """Service class for managing NDK Storage Clusters"""
    
    @staticmethod
    def list_storage_clusters():
        """Get all NDK Storage Clusters"""
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