"""
Storage service - Business logic for NDK Storage Clusters
"""
import base64
from kubernetes.client.rest import ApiException
from app.extensions import k8s_api, k8s_core_api, with_auth_retry
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
        
        @with_auth_retry
        def _fetch_pc_secret():
            return k8s_core_api.read_namespaced_secret(
                name='ntnx-pc-secret',
                namespace='ndk-operator'
            )
        
        try:
            if k8s_core_api:
                secret = _fetch_pc_secret()
                if secret.data and 'key' in secret.data:
                    key_data = base64.b64decode(secret.data['key']).decode('utf-8')
                    parts = key_data.split(':')
                    if len(parts) >= 2:
                        pc_endpoint = f"{parts[0]}:{parts[1]}"
        except Exception as e:
            print(f"Warning: Could not read PC secret: {e}")
        
        @with_auth_retry
        def _fetch_storage_clusters():
            return k8s_api.list_cluster_custom_object(
                group=Config.NDK_API_GROUP,
                version=Config.NDK_API_VERSION,
                plural='storageclusters'
            )
        
        try:
            result = _fetch_storage_clusters()
            
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