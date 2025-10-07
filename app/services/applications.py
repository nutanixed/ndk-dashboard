"""
Application service - Business logic for NDK Applications
"""
import time
import re
from kubernetes.client.rest import ApiException
from config import Config
from app.extensions import k8s_api, k8s_core_api, k8s_apps_api
from app.utils.labels import filter_system_label_prefixes, filter_system_labels, preserve_system_labels

# System namespaces to exclude
SYSTEM_NAMESPACES = {
    'kube-system', 'kube-public', 'kube-node-lease', 'ntnx-system'
}


class ApplicationService:
    """Service for managing NDK Applications"""
    
    @staticmethod
    def list_applications():
        """Get all NDK Applications from non-system namespaces"""
        if not k8s_api:
            return []
        
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
                state, message = ApplicationService._extract_state(status)
                
                # Extract labels (excluding system labels)
                all_labels = metadata.get('labels', {})
                user_labels = filter_system_label_prefixes(all_labels)
                
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
    
    @staticmethod
    def get_application(namespace, name):
        """Get a single NDK Application"""
        if not k8s_api:
            raise Exception('Kubernetes API not available')
        
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
            filtered_labels = filter_system_labels(labels)
            
            return {
                'name': metadata.get('name'),
                'namespace': metadata.get('namespace'),
                'labels': filtered_labels
            }
        except ApiException as e:
            raise Exception(f'Application not found: {e}')
    
    @staticmethod
    def delete_application(namespace, name, force=False, app_only=False):
        """
        Delete an NDK Application and optionally its resources
        
        Args:
            namespace: Application namespace
            name: Application name
            force: Force delete by removing finalizers
            app_only: Only delete the Application CRD, preserve snapshots and data
            
        Returns:
            tuple: (success_message, cleanup_log)
        """
        if not k8s_api:
            raise Exception('Kubernetes API not available')
        
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
            
            return 'Application deleted (snapshots & data preserved)', cleanup_log
        
        # Full deletion with cleanup
        # Step 1: Delete all snapshots
        deleted_snapshots = ApplicationService._delete_application_snapshots(
            namespace, name, force, cleanup_log
        )
        
        # Step 2: Delete AppProtectionPlans
        deleted_app_plans = ApplicationService._delete_app_protection_plans(
            namespace, name, force, cleanup_log
        )
        
        # Step 3: Wait for snapshots to be deleted
        if deleted_snapshots > 0:
            ApplicationService._wait_for_snapshot_deletion(
                namespace, name, cleanup_log
            )
        
        # Step 4: Delete the Application CRD
        try:
            if force:
                # Remove finalizers first
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
            
            k8s_api.delete_namespaced_custom_object(
                group=Config.NDK_API_GROUP,
                version=Config.NDK_API_VERSION,
                namespace=namespace,
                plural='applications',
                name=name
            )
            cleanup_log.append(f"✓ Deleted Application: {name}")
            print(f"✓ Deleted Application: {namespace}/{name}")
        except ApiException as e:
            if e.status == 404:
                print(f"✓ Application {name} was already deleted")
                cleanup_log.append(f"Application {name} was already deleted")
            else:
                raise
        
        return f'Application {name} and all associated resources deleted successfully', cleanup_log
    
    @staticmethod
    def update_labels(namespace, name, new_labels):
        """Update labels on an NDK Application"""
        if not k8s_api:
            raise Exception('Kubernetes API not available')
        
        # Get current application
        app = k8s_api.get_namespaced_custom_object(
            group=Config.NDK_API_GROUP,
            version=Config.NDK_API_VERSION,
            namespace=namespace,
            plural='applications',
            name=name
        )
        
        # Preserve system labels
        current_labels = app.get('metadata', {}).get('labels', {})
        merged_labels = preserve_system_labels(current_labels, new_labels)
        
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
        
        return new_labels
    
    @staticmethod
    def get_debug_info(namespace, name):
        """Get debug information for an application"""
        if not k8s_api:
            raise Exception('Kubernetes API not available')
        
        app = k8s_api.get_namespaced_custom_object(
            group=Config.NDK_API_GROUP,
            version=Config.NDK_API_VERSION,
            namespace=namespace,
            plural='applications',
            name=name
        )
        
        return {
            'metadata': app.get('metadata', {}),
            'spec': app.get('spec', {}),
            'status': app.get('status', {})
        }
    
    @staticmethod
    def get_pods(namespace, name):
        """Get pod information for an NDK Application"""
        if not k8s_api or not k8s_core_api:
            raise Exception('Kubernetes API not available')
        
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
        
        # Build label selector
        label_selector = ApplicationService._build_label_selector(app_selector, name)
        
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
        
        return {
            'replicas': len(pod_info),
            'pods': pod_info,
            'selector': label_selector
        }
    
    @staticmethod
    def get_pvcs(namespace, name):
        """Get PVC and Volume Group information for an NDK Application"""
        if not k8s_api or not k8s_core_api:
            raise Exception('Kubernetes API not available')
        
        # Get the application
        app = k8s_api.get_namespaced_custom_object(
            group=Config.NDK_API_GROUP,
            version=Config.NDK_API_VERSION,
            namespace=namespace,
            plural='applications',
            name=name
        )
        
        # Get application selector
        spec = app.get('spec', {})
        app_selector = spec.get('applicationSelector', {})
        label_selector = ApplicationService._build_label_selector(app_selector, name)
        
        # Get PVCs matching the selector
        pvcs = k8s_core_api.list_namespaced_persistent_volume_claim(
            namespace=namespace,
            label_selector=label_selector
        )
        
        pvc_info = []
        volume_groups = set()
        
        for pvc in pvcs.items:
            pvc_name = pvc.metadata.name
            pv_name = pvc.spec.volume_name if pvc.spec.volume_name else 'Pending'
            storage_class = pvc.spec.storage_class_name or 'default'
            capacity = pvc.status.capacity.get('storage', 'Unknown') if pvc.status.capacity else 'Pending'
            status = pvc.status.phase
            
            # Get volume group UUID from PV's CSI volume handle
            volume_group = 'N/A'
            if pv_name != 'Pending':
                try:
                    pv = k8s_core_api.read_persistent_volume(name=pv_name)
                    
                    # Get Nutanix CSI specific details
                    if pv.spec.csi and pv.spec.csi.driver == 'csi.nutanix.com':
                        volume_handle = pv.spec.csi.volume_handle
                        
                        # Extract VG UUID from volume handle (e.g., "NutanixVolumes-8682863c-...")
                        if volume_handle and volume_handle.startswith('NutanixVolumes-'):
                            vg_uuid = volume_handle.replace('NutanixVolumes-', '')
                            volume_group = vg_uuid
                            volume_groups.add(vg_uuid)
                except ApiException as e:
                    print(f"Could not read PV {pv_name}: {e}")
            
            pvc_info.append({
                'name': pvc_name,
                'pvName': pv_name,
                'storageClass': storage_class,
                'capacity': capacity,
                'status': status,
                'volumeGroup': volume_group
            })
        
        return {
            'count': len(pvc_info),
            'pvcs': pvc_info,
            'volumeGroups': list(volume_groups),
            'selector': label_selector
        }
    
    # Helper methods
    
    @staticmethod
    def _extract_state(status):
        """Extract state and message from status conditions"""
        state = 'Unknown'
        message = ''
        conditions = status.get('conditions', [])
        if conditions:
            condition = conditions[0]
            if condition.get('status') == 'True':
                state = condition.get('type', 'Unknown')
            else:
                state = f"Not {condition.get('type', 'Unknown')}"
            message = condition.get('message', '')
        return state, message
    
    @staticmethod
    def _build_label_selector(app_selector, app_name):
        """Build label selector string from application selector"""
        label_selector = None
        
        # Check for resourceLabelSelectors (newer format)
        resource_label_selectors = app_selector.get('resourceLabelSelectors', [])
        if resource_label_selectors:
            # Use the first resourceLabelSelector
            first_selector = resource_label_selectors[0]
            label_selector_obj = first_selector.get('labelSelector', {})
            match_labels = label_selector_obj.get('matchLabels', {})
            match_expressions = label_selector_obj.get('matchExpressions', [])
        else:
            # Fall back to direct matchLabels/matchExpressions (older format)
            match_labels = app_selector.get('matchLabels', {})
            match_expressions = app_selector.get('matchExpressions', [])
        
        if match_labels:
            label_selector = ','.join([f"{k}={v}" for k, v in match_labels.items()])
        elif match_expressions:
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
        
        # If no selector found, try to find resources by app name
        if not label_selector:
            label_selector = f"app={app_name}"
            print(f"No explicit selector found, trying app={app_name}")
        
        return label_selector
    
    @staticmethod
    def _delete_application_snapshots(namespace, name, force, cleanup_log):
        """Delete all snapshots associated with an application"""
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
                cleanup_log.append(f"✓ Deleted {deleted_snapshots} snapshots")
            
            return deleted_snapshots
        except ApiException as e:
            print(f"Warning: Error listing snapshots: {e}")
            cleanup_log.append(f"Warning: Could not list snapshots: {e.reason}")
            return 0
    
    @staticmethod
    def _delete_app_protection_plans(namespace, name, force, cleanup_log):
        """Delete AppProtectionPlans associated with an application"""
        try:
            app_plans = k8s_api.list_namespaced_custom_object(
                group=Config.NDK_API_GROUP,
                version=Config.NDK_API_VERSION,
                namespace=namespace,
                plural='appprotectionplans'
            )
            
            deleted_plans = 0
            for plan in app_plans.get('items', []):
                plan_metadata = plan.get('metadata', {})
                plan_spec = plan.get('spec', {})
                plan_name = plan_metadata.get('name')
                
                # Check if this plan belongs to the application
                if plan_spec.get('applicationName') == name:
                    try:
                        if force and plan_metadata.get('finalizers'):
                            k8s_api.patch_namespaced_custom_object(
                                group=Config.NDK_API_GROUP,
                                version=Config.NDK_API_VERSION,
                                namespace=namespace,
                                plural='appprotectionplans',
                                name=plan_name,
                                body={'metadata': {'finalizers': []}}
                            )
                        
                        k8s_api.delete_namespaced_custom_object(
                            group=Config.NDK_API_GROUP,
                            version=Config.NDK_API_VERSION,
                            namespace=namespace,
                            plural='appprotectionplans',
                            name=plan_name
                        )
                        deleted_plans += 1
                        cleanup_log.append(f"Deleted AppProtectionPlan: {plan_name}")
                    except ApiException as e:
                        if e.status != 404:
                            cleanup_log.append(f"Warning: Failed to delete AppProtectionPlan {plan_name}: {e.reason}")
            
            if deleted_plans > 0:
                print(f"✓ Deleted {deleted_plans} AppProtectionPlans for application {name}")
                cleanup_log.append(f"✓ Deleted {deleted_plans} AppProtectionPlans")
            
            return deleted_plans
        except ApiException as e:
            print(f"Warning: Error listing AppProtectionPlans: {e}")
            cleanup_log.append(f"Warning: Could not list AppProtectionPlans: {e.reason}")
            return 0
    
    @staticmethod
    def _wait_for_snapshot_deletion(namespace, name, cleanup_log, max_wait=30):
        """Wait for snapshots to be deleted"""
        print(f"⏳ Waiting for snapshots to be deleted (max {max_wait}s)...")
        cleanup_log.append(f"Waiting for snapshots to be deleted...")
        
        for i in range(max_wait):
            try:
                snapshots = k8s_api.list_namespaced_custom_object(
                    group=Config.NDK_API_GROUP,
                    version=Config.NDK_API_VERSION,
                    namespace=namespace,
                    plural='applicationsnapshots'
                )
                
                remaining = sum(
                    1 for s in snapshots.get('items', [])
                    if s.get('spec', {}).get('source', {}).get('applicationRef', {}).get('name') == name
                )
                
                if remaining == 0:
                    print(f"✓ All snapshots deleted")
                    cleanup_log.append("✓ All snapshots deleted")
                    break
                
                if i % 5 == 0:
                    print(f"  Still waiting... {remaining} snapshots remaining")
                
                time.sleep(1)
            except ApiException:
                break
        else:
            print(f"⚠ Timeout waiting for snapshots to be deleted")
            cleanup_log.append("Warning: Timeout waiting for snapshots")