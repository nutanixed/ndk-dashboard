"""
Snapshot service - Business logic for NDK Application Snapshots
"""
from datetime import datetime
from kubernetes.client.rest import ApiException
from app.extensions import k8s_api, with_auth_retry
from config import Config


class SnapshotService:
    """Service class for managing NDK Application Snapshots"""
    
    @staticmethod
    def list_snapshots():
        """Get all NDK Application Snapshots"""
        if not k8s_api:
            return []
        
        @with_auth_retry
        def _fetch_snapshots():
            return k8s_api.list_cluster_custom_object(
                group=Config.NDK_API_GROUP,
                version=Config.NDK_API_VERSION,
                plural='applicationsnapshots'
            )
        
        try:
            result = _fetch_snapshots()
            
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
    
    @staticmethod
    def create_snapshot(app_name, app_namespace, expires_after='720h'):
        """Create a new snapshot for an application"""
        if not k8s_api:
            raise Exception('Kubernetes API not available')
        
        if not app_name or not app_namespace:
            raise ValueError('Application name and namespace are required')
        
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
        
        return {
            'name': snapshot_name,
            'namespace': app_namespace,
            'application': app_name
        }
    
    @staticmethod
    def delete_snapshot(namespace, name):
        """Delete an NDK Application Snapshot"""
        if not k8s_api:
            raise Exception('Kubernetes API not available')
        
        k8s_api.delete_namespaced_custom_object(
            group=Config.NDK_API_GROUP,
            version=Config.NDK_API_VERSION,
            namespace=namespace,
            plural='applicationsnapshots',
            name=name
        )
        
        return f'Snapshot {name} deleted successfully'
    
    @staticmethod
    def restore_snapshot(namespace, name, target_namespace=None):
        """Restore an application from a snapshot using ApplicationSnapshotRestore CRD"""
        if not k8s_api:
            raise Exception('Kubernetes API not available')
        
        import time
        
        # Get the snapshot to find the application name
        snapshot = k8s_api.get_namespaced_custom_object(
            group=Config.NDK_API_GROUP,
            version=Config.NDK_API_VERSION,
            namespace=namespace,
            plural='applicationsnapshots',
            name=name
        )
        
        # Extract application name from snapshot
        spec = snapshot.get('spec', {})
        source = spec.get('source', {})
        app_ref = source.get('applicationRef', {})
        original_app_name = app_ref.get('name', 'unknown')
        
        # Use target namespace if provided, otherwise use original namespace
        restore_namespace = target_namespace if target_namespace else namespace
        
        # Generate a unique name for the restore operation
        timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        restore_name = f"{original_app_name}-restore-{timestamp}"
        
        # Create ApplicationSnapshotRestore manifest (NDK 1.3.0+)
        restore_manifest = {
            'apiVersion': f'{Config.NDK_API_GROUP}/{Config.NDK_API_VERSION}',
            'kind': 'ApplicationSnapshotRestore',
            'metadata': {
                'name': restore_name,
                'namespace': restore_namespace
            },
            'spec': {
                'applicationSnapshotName': name,
                'applicationSnapshotNamespace': namespace
            }
        }
        
        # Create the restore operation
        result = k8s_api.create_namespaced_custom_object(
            group=Config.NDK_API_GROUP,
            version=Config.NDK_API_VERSION,
            namespace=restore_namespace,
            plural='applicationsnapshotrestores',
            body=restore_manifest
        )
        
        print(f"✓ Restore operation {restore_name} initiated (non-blocking)")
        
        # Create an Application CRD immediately to manage the restored resources
        # The frontend will poll the restore progress API to track completion
        app_manifest = {
            'apiVersion': f'{Config.NDK_API_GROUP}/{Config.NDK_API_VERSION}',
            'kind': 'Application',
            'metadata': {
                'name': original_app_name,
                'namespace': restore_namespace,
                'labels': {
                    'restored-from': name,
                    'app.kubernetes.io/managed-by': 'ndk-dashboard'
                }
            },
            'spec': {
                'restoreFrom': {
                    'snapshot': name,
                    'restoreName': restore_name
                },
                'applicationSelector': {
                    'resourceLabelSelectors': [
                        {
                            'labelSelector': {
                                'matchLabels': {
                                    'app': original_app_name
                                }
                            }
                        }
                    ]
                }
            }
        }
        
        try:
            # Create the Application CRD
            k8s_api.create_namespaced_custom_object(
                group=Config.NDK_API_GROUP,
                version=Config.NDK_API_VERSION,
                namespace=restore_namespace,
                plural='applications',
                body=app_manifest
            )
            print(f"✓ Created Application CRD '{original_app_name}' in namespace '{restore_namespace}'")
        except ApiException as e:
            if e.status == 409:
                print(f"  Application CRD '{original_app_name}' already exists")
            else:
                print(f"✗ Error creating Application CRD: {e}")
                raise
        
        # The restored application will have the same name as the original
        # but will be created by the ApplicationSnapshotRestore controller
        return {
            'name': original_app_name,  # The application name will be the original name
            'namespace': restore_namespace,
            'snapshot': name,
            'original_application': original_app_name,
            'restore_name': restore_name  # The restore CRD name
        }
    
    @staticmethod
    def bulk_create_snapshots(applications, expires_after='720h'):
        """Create snapshots for multiple applications"""
        if not k8s_api:
            raise Exception('Kubernetes API not available')
        
        results = {
            'success': [],
            'failed': []
        }
        
        for app in applications:
            app_name = app.get('name')
            app_namespace = app.get('namespace')
            
            if not app_name or not app_namespace:
                results['failed'].append({
                    'application': app_name or 'Unknown',
                    'namespace': app_namespace or 'Unknown',
                    'error': 'Missing name or namespace'
                })
                continue
            
            try:
                snapshot_info = SnapshotService.create_snapshot(
                    app_name, app_namespace, expires_after
                )
                results['success'].append({
                    'application': app_name,
                    'namespace': app_namespace,
                    'snapshot': snapshot_info['name']
                })
            except Exception as e:
                results['failed'].append({
                    'application': app_name,
                    'namespace': app_namespace,
                    'error': str(e)
                })
        
        return results