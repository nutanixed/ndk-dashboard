"""
Restore service - Manage ApplicationSnapshotRestore resources
"""
from kubernetes.client.rest import ApiException
from app.extensions import k8s_api, with_auth_retry
from config import Config


def list_restore_jobs(namespace=None):
    """
    List all ApplicationSnapshotRestore resources
    
    Args:
        namespace: Optional namespace filter. If None, lists all namespaces.
        
    Returns:
        List of restore job objects with metadata
    """
    if not k8s_api:
        return []
    
    @with_auth_retry
    def _fetch():
        if namespace:
            return k8s_api.list_namespaced_custom_object(
                group=Config.NDK_API_GROUP,
                version=Config.NDK_API_VERSION,
                namespace=namespace,
                plural='applicationsnapshotrestores'
            )
        else:
            return k8s_api.list_cluster_custom_object(
                group=Config.NDK_API_GROUP,
                version=Config.NDK_API_VERSION,
                plural='applicationsnapshotrestores'
            )
    
    try:
        result = _fetch()
        items = result.get('items', [])
        
        # Process and enrich restore job data
        restore_jobs = []
        for item in items:
            metadata = item.get('metadata', {})
            spec = item.get('spec', {})
            status = item.get('status', {})
            
            restore_job = {
                'name': metadata.get('name', 'Unknown'),
                'namespace': metadata.get('namespace', 'Unknown'),
                'created': metadata.get('creationTimestamp', 'Unknown'),
                'snapshot_name': spec.get('applicationSnapshotName', 'Unknown'),
                'target_namespace': spec.get('targetNamespace', metadata.get('namespace', 'Unknown')),
                'completed': status.get('completed', False),
                'conditions': status.get('conditions', []),
                'raw': item
            }
            
            # Determine status
            if restore_job['completed']:
                restore_job['status'] = 'Completed'
            else:
                restore_job['status'] = 'In Progress'
            
            restore_jobs.append(restore_job)
        
        return restore_jobs
    except ApiException as e:
        print(f"Error fetching restore jobs: {e}")
        return []


def delete_restore_job(name, namespace):
    """
    Delete an ApplicationSnapshotRestore resource
    
    Args:
        name: Name of the restore job
        namespace: Namespace of the restore job
        
    Returns:
        Tuple of (success: bool, message: str)
    """
    if not k8s_api:
        return False, "Kubernetes API not available"
    
    @with_auth_retry
    def _delete():
        return k8s_api.delete_namespaced_custom_object(
            group=Config.NDK_API_GROUP,
            version=Config.NDK_API_VERSION,
            namespace=namespace,
            plural='applicationsnapshotrestores',
            name=name
        )
    
    try:
        _delete()
        return True, f"Restore job '{name}' deleted successfully"
    except ApiException as e:
        error_msg = f"Failed to delete restore job: {e.reason}"
        if e.body:
            error_msg += f" - {e.body}"
        return False, error_msg


def delete_completed_restore_jobs(namespace=None):
    """
    Delete all completed restore jobs
    
    Args:
        namespace: Optional namespace filter. If None, deletes from all namespaces.
        
    Returns:
        Tuple of (success_count: int, failed_count: int, messages: list)
    """
    restore_jobs = list_restore_jobs(namespace)
    completed_jobs = [job for job in restore_jobs if job['completed']]
    
    success_count = 0
    failed_count = 0
    messages = []
    
    for job in completed_jobs:
        success, message = delete_restore_job(job['name'], job['namespace'])
        if success:
            success_count += 1
            messages.append(f"✓ {job['namespace']}/{job['name']}")
        else:
            failed_count += 1
            messages.append(f"✗ {job['namespace']}/{job['name']}: {message}")
    
    return success_count, failed_count, messages