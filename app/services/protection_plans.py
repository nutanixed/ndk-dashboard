"""
Protection Plans service - Business logic for NDK Protection Plans
"""
from kubernetes.client.rest import ApiException
from app.extensions import k8s_api, with_auth_retry
from config import Config


class ProtectionPlanService:
    """Service class for managing NDK Protection Plans"""
    
    @staticmethod
    def list_protection_plans():
        """Get all NDK Protection Plans"""
        if not k8s_api:
            return []
        
        @with_auth_retry
        def _fetch_protection_plans():
            return k8s_api.list_cluster_custom_object(
                group=Config.NDK_API_GROUP,
                version=Config.NDK_API_VERSION,
                plural='protectionplans'
            )
        
        try:
            result = _fetch_protection_plans()
            
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
    
    @staticmethod
    def get_protection_plan(namespace, name):
        """Get a single protection plan"""
        if not k8s_api:
            raise Exception('Kubernetes API not available')
        
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
        
        return {
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
    
    @staticmethod
    def delete_protection_plan(namespace, name, force=False):
        """Delete a protection plan"""
        if not k8s_api:
            raise Exception('Kubernetes API not available')
        
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
                    pass  # Scheduler might already be deleted
            
            # If force delete, remove finalizers first
            if force:
                try:
                    k8s_api.patch_namespaced_custom_object(
                        group=Config.NDK_API_GROUP,
                        version=Config.NDK_API_VERSION,
                        namespace=namespace,
                        plural='protectionplans',
                        name=name,
                        body={'metadata': {'finalizers': []}}
                    )
                except:
                    pass  # Might already be deleted
        except ApiException as e:
            if e.status != 404:
                raise
        
        # Delete the protection plan
        k8s_api.delete_namespaced_custom_object(
            group=Config.NDK_API_GROUP,
            version=Config.NDK_API_VERSION,
            namespace=namespace,
            plural='protectionplans',
            name=name
        )
        
        return f'Protection plan {name} deleted successfully'
    
    @staticmethod
    def update_protection_plan(namespace, name, updates):
        """Update a protection plan (e.g., suspend/resume)"""
        if not k8s_api:
            raise Exception('Kubernetes API not available')
        
        # Get current plan
        plan = k8s_api.get_namespaced_custom_object(
            group=Config.NDK_API_GROUP,
            version=Config.NDK_API_VERSION,
            namespace=namespace,
            plural='protectionplans',
            name=name
        )
        
        # Update spec with new values
        spec = plan.get('spec', {})
        spec.update(updates)
        
        # Patch the plan
        result = k8s_api.patch_namespaced_custom_object(
            group=Config.NDK_API_GROUP,
            version=Config.NDK_API_VERSION,
            namespace=namespace,
            plural='protectionplans',
            name=name,
            body={'spec': spec}
        )
        
        return result
    
    @staticmethod
    def create_protection_plan(namespace, name, schedule, retention, applications, 
                              selection_mode='by-name', label_selector_key=None, 
                              label_selector_value=None):
        """Create a new protection plan"""
        if not k8s_api:
            raise Exception('Kubernetes API not available')
        
        # Create JobScheduler first
        scheduler_name = f"{name}-scheduler"
        scheduler_manifest = {
            'apiVersion': 'scheduler.nutanix.com/v1alpha1',
            'kind': 'JobScheduler',
            'metadata': {
                'name': scheduler_name,
                'namespace': namespace
            },
            'spec': {
                'cronSchedule': schedule
            }
        }
        
        k8s_api.create_namespaced_custom_object(
            group='scheduler.nutanix.com',
            version='v1alpha1',
            namespace=namespace,
            plural='jobschedulers',
            body=scheduler_manifest
        )
        
        # Parse retention value
        retention_policy = {}
        # Handle both string and integer types
        if isinstance(retention, int):
            retention_policy['retentionCount'] = retention
        elif isinstance(retention, str) and retention.isdigit():
            retention_policy['retentionCount'] = int(retention)
        else:
            retention_policy['maxAge'] = str(retention)
        
        # Build annotations for selection mode
        annotations = {
            'ndk-dashboard/selection-mode': selection_mode
        }
        if selection_mode == 'by-label' and label_selector_key and label_selector_value:
            annotations['ndk-dashboard/label-selector-key'] = label_selector_key
            annotations['ndk-dashboard/label-selector-value'] = label_selector_value
        
        import sys
        print(f"DEBUG CREATE: selection_mode={selection_mode}, label_key={label_selector_key}, label_value={label_selector_value}", file=sys.stderr, flush=True)
        print(f"DEBUG CREATE: annotations={annotations}", file=sys.stderr, flush=True)
        
        # Create ProtectionPlan
        plan_manifest = {
            'apiVersion': f'{Config.NDK_API_GROUP}/{Config.NDK_API_VERSION}',
            'kind': 'ProtectionPlan',
            'metadata': {
                'name': name,
                'namespace': namespace,
                'annotations': annotations
            },
            'spec': {
                'scheduleName': scheduler_name,
                'retentionPolicy': retention_policy,
                'applications': applications
            }
        }
        
        result = k8s_api.create_namespaced_custom_object(
            group=Config.NDK_API_GROUP,
            version=Config.NDK_API_VERSION,
            namespace=namespace,
            plural='protectionplans',
            body=plan_manifest
        )
        
        return {
            'name': name,
            'namespace': namespace,
            'schedule': schedule,
            'retention': retention,
            'applications': applications
        }