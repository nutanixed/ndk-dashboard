"""
Snapshot service - Business logic for NDK Application Snapshots
"""
from datetime import datetime
from kubernetes.client.rest import ApiException
from app.extensions import k8s_api, k8s_core_api, with_auth_retry
from config import Config
import logging
import sys

logger = logging.getLogger(__name__)


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
                # NDK uses the full domain prefix for protection plan labels
                protection_plan = labels.get('dataservices.nutanix.com/protection-plan', None)
                
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
    def restore_snapshot(namespace, name, target_namespace=None, new_app_name=None):
        """Restore an application from a snapshot using ApplicationSnapshotRestore CRD
        
        Args:
            namespace: Namespace where the snapshot exists
            name: Name of the snapshot
            target_namespace: Target namespace for restore (optional, defaults to snapshot namespace)
            new_app_name: New name for the restored application (optional, defaults to original name)
                         This enables "clone from snapshot" functionality
        """
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
        
        # Use custom app name if provided (clone), otherwise use original name
        restored_app_name = new_app_name if new_app_name else original_app_name
        
        # Use target namespace if provided, otherwise use original namespace
        restore_namespace = target_namespace if target_namespace else namespace
        
        # Create target namespace if it doesn't exist
        try:
            k8s_core_api.read_namespace(restore_namespace)
            logger.info(f"✓ Target namespace '{restore_namespace}' exists")
            sys.stdout.flush()
        except ApiException as e:
            if e.status == 404:
                logger.info(f"⚠ Target namespace '{restore_namespace}' not found, creating it...")
                sys.stdout.flush()
                namespace_manifest = {
                    'apiVersion': 'v1',
                    'kind': 'Namespace',
                    'metadata': {'name': restore_namespace}
                }
                k8s_core_api.create_namespace(body=namespace_manifest)
                logger.info(f"✓ Created namespace '{restore_namespace}'")
                sys.stdout.flush()
            else:
                raise
        
        # For cross-namespace restores, create a ReferenceGrant to allow access
        if restore_namespace != namespace:
            logger.info(f"🔐 Cross-namespace restore detected, ensuring ReferenceGrant exists...")
            sys.stdout.flush()
            
            reference_grant_name = f"allow-restore-from-{restore_namespace}"
            
            # Check if ReferenceGrant already exists
            try:
                k8s_api.get_namespaced_custom_object(
                    group='gateway.networking.k8s.io',
                    version='v1beta1',
                    namespace=namespace,  # Grant is created in the SOURCE namespace
                    plural='referencegrants',
                    name=reference_grant_name
                )
                logger.info(f"✓ ReferenceGrant '{reference_grant_name}' already exists")
                sys.stdout.flush()
            except ApiException as e:
                if e.status == 404:
                    # Create the ReferenceGrant
                    logger.info(f"⚠ ReferenceGrant not found, creating it...")
                    sys.stdout.flush()
                    
                    reference_grant_manifest = {
                        'apiVersion': 'gateway.networking.k8s.io/v1beta1',
                        'kind': 'ReferenceGrant',
                        'metadata': {
                            'name': reference_grant_name,
                            'namespace': namespace  # SOURCE namespace where snapshot exists
                        },
                        'spec': {
                            'from': [{
                                'group': 'dataservices.nutanix.com',
                                'kind': 'ApplicationSnapshotRestore',
                                'namespace': restore_namespace  # TARGET namespace
                            }],
                            'to': [{
                                'group': 'dataservices.nutanix.com',
                                'kind': 'ApplicationSnapshot'
                            }]
                        }
                    }
                    
                    k8s_api.create_namespaced_custom_object(
                        group='gateway.networking.k8s.io',
                        version='v1beta1',
                        namespace=namespace,
                        plural='referencegrants',
                        body=reference_grant_manifest
                    )
                    logger.info(f"✓ Created ReferenceGrant '{reference_grant_name}' in namespace '{namespace}'")
                    sys.stdout.flush()
                else:
                    raise
        
        # For cross-namespace restores, copy ConfigMaps and Secrets
        if restore_namespace != namespace:
            logger.info(f"📦 Copying ConfigMaps and Secrets from '{namespace}' to '{restore_namespace}'...")
            sys.stdout.flush()
            
            # Get all ConfigMaps from source namespace
            try:
                configmaps = k8s_core_api.list_namespaced_config_map(namespace)
                copied_cm_count = 0
                for cm in configmaps.items:
                    cm_name = cm.metadata.name
                    # Skip system ConfigMaps
                    if cm_name.startswith('kube-') or cm_name.startswith('istio-'):
                        continue
                    
                    # Check if ConfigMap already exists in target namespace
                    try:
                        k8s_core_api.read_namespaced_config_map(cm_name, restore_namespace)
                        logger.info(f"  ✓ ConfigMap '{cm_name}' already exists in target namespace")
                        sys.stdout.flush()
                    except ApiException as e:
                        if e.status == 404:
                            # Copy the ConfigMap and add application label for proper cleanup
                            labels = cm.metadata.labels.copy() if cm.metadata.labels else {}
                            # Add the application label so it can be found by label selector during deletion
                            # Use original_app_name to match the Application CRD selector (NDK restores with original names)
                            labels['app'] = original_app_name
                            
                            new_cm = {
                                'apiVersion': 'v1',
                                'kind': 'ConfigMap',
                                'metadata': {
                                    'name': cm_name,
                                    'namespace': restore_namespace,
                                    'labels': labels
                                },
                                'data': cm.data or {}
                            }
                            k8s_core_api.create_namespaced_config_map(restore_namespace, new_cm)
                            copied_cm_count += 1
                            logger.info(f"  ✓ Copied ConfigMap '{cm_name}'")
                            sys.stdout.flush()
                        else:
                            raise
                
                if copied_cm_count > 0:
                    logger.info(f"✓ Copied {copied_cm_count} ConfigMap(s)")
                    sys.stdout.flush()
            except ApiException as e:
                logger.warning(f"⚠ Error copying ConfigMaps: {e}")
                sys.stdout.flush()
            
            # Get all Secrets from source namespace
            try:
                secrets = k8s_core_api.list_namespaced_secret(namespace)
                copied_secret_count = 0
                for secret in secrets.items:
                    secret_name = secret.metadata.name
                    # Skip system Secrets (service account tokens, etc.)
                    if (secret_name.startswith('default-token-') or 
                        secret_name.startswith('kube-') or
                        secret.type == 'kubernetes.io/service-account-token'):
                        continue
                    
                    # Check if Secret already exists in target namespace
                    try:
                        k8s_core_api.read_namespaced_secret(secret_name, restore_namespace)
                        logger.info(f"  ✓ Secret '{secret_name}' already exists in target namespace")
                        sys.stdout.flush()
                    except ApiException as e:
                        if e.status == 404:
                            # Copy the Secret and add application label for proper cleanup
                            labels = secret.metadata.labels.copy() if secret.metadata.labels else {}
                            # Add the application label so it can be found by label selector during deletion
                            # Use original_app_name to match the Application CRD selector (NDK restores with original names)
                            labels['app'] = original_app_name
                            
                            new_secret = {
                                'apiVersion': 'v1',
                                'kind': 'Secret',
                                'metadata': {
                                    'name': secret_name,
                                    'namespace': restore_namespace,
                                    'labels': labels
                                },
                                'type': secret.type,
                                'data': secret.data or {}
                            }
                            k8s_core_api.create_namespaced_secret(restore_namespace, new_secret)
                            copied_secret_count += 1
                            logger.info(f"  ✓ Copied Secret '{secret_name}'")
                            sys.stdout.flush()
                        else:
                            raise
                
                if copied_secret_count > 0:
                    logger.info(f"✓ Copied {copied_secret_count} Secret(s)")
                    sys.stdout.flush()
            except ApiException as e:
                logger.warning(f"⚠ Error copying Secrets: {e}")
                sys.stdout.flush()
        
        # Generate a unique name for the restore operation
        timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        restore_name = f"{restored_app_name}-restore-{timestamp}"
        
        # Create ApplicationSnapshotRestore manifest (NDK 1.3.0+)
        # The restore CRD is created in the TARGET namespace where resources will be restored
        restore_manifest = {
            'apiVersion': f'{Config.NDK_API_GROUP}/{Config.NDK_API_VERSION}',
            'kind': 'ApplicationSnapshotRestore',
            'metadata': {
                'name': restore_name,
                'namespace': restore_namespace  # Target namespace for restore
            },
            'spec': {
                'applicationSnapshotName': name,
                'applicationSnapshotNamespace': namespace  # Source snapshot namespace
            }
        }
        
        # Log the restore manifest for debugging
        logger.info(f"📝 Creating restore with manifest:")
        logger.info(f"   Snapshot: {namespace}/{name}")
        logger.info(f"   Target Namespace: {restore_namespace}")
        logger.info(f"   Restore Name: {restore_name}")
        sys.stdout.flush()
        
        # Create the restore operation
        result = k8s_api.create_namespaced_custom_object(
            group=Config.NDK_API_GROUP,
            version=Config.NDK_API_VERSION,
            namespace=restore_namespace,
            plural='applicationsnapshotrestores',
            body=restore_manifest
        )
        
        logger.info(f"✓ Restore operation {restore_name} initiated")
        sys.stdout.flush()
        
        # Wait a moment for NDK to process and check for immediate errors
        import time
        time.sleep(2)
        
        # Check the restore status for immediate errors
        try:
            restore_status = k8s_api.get_namespaced_custom_object(
                group=Config.NDK_API_GROUP,
                version=Config.NDK_API_VERSION,
                namespace=restore_namespace,
                plural='applicationsnapshotrestores',
                name=restore_name
            )
            
            status = restore_status.get('status', {})
            conditions = status.get('conditions', [])
            
            # Check for failed conditions (but ignore in-progress states)
            for condition in conditions:
                if condition.get('status') == 'False':
                    error_msg = condition.get('message', 'Unknown error')
                    error_type = condition.get('type', 'Unknown')
                    error_reason = condition.get('reason', 'Unknown')
                    
                    # Ignore "in-progress" reasons - these are not actual failures
                    in_progress_reasons = ['RunningPrechecks', 'Restoring', 'Pending']
                    
                    # Also ignore messages that indicate waiting/in-progress states
                    in_progress_messages = [
                        'Waiting for PVCs to get Bound',
                        'Waiting for volumes',
                        'Restoring volumes',
                        'Volumes are being restored',
                        'Restoring application'
                    ]
                    
                    is_in_progress = (
                        error_reason in in_progress_reasons or
                        any(msg in error_msg for msg in in_progress_messages)
                    )
                    
                    if is_in_progress:
                        logger.info(f"⏳ Restore in progress - {error_type}: {error_reason}")
                        logger.info(f"   Message: {error_msg}")
                        sys.stdout.flush()
                        continue
                    
                    # This is an actual failure
                    logger.error(f"❌ Restore failed - Type: {error_type}, Reason: {error_reason}")
                    logger.error(f"   Message: {error_msg}")
                    sys.stdout.flush()
                    raise Exception(f"Restore failed: {error_msg}")
            
            logger.info(f"✓ Restore initiated successfully, phase: {status.get('phase', 'Unknown')}")
            sys.stdout.flush()
            
        except ApiException as e:
            if e.status != 404:  # Ignore if status not yet available
                raise
        
        # NDK does NOT automatically create the Application CRD for restores
        # We need to create it manually so the restored app appears in the dashboard
        logger.info(f"📋 Creating NDK Application CRD for restored application...")
        sys.stdout.flush()
        
        # Get the original Application CRD from source namespace to copy its selector
        try:
            source_app = k8s_api.get_namespaced_custom_object(
                group=Config.NDK_API_GROUP,
                version=Config.NDK_API_VERSION,
                namespace=namespace,
                plural='applications',
                name=original_app_name
            )
            
            # Extract the application selector from the source
            source_spec = source_app.get('spec', {})
            app_selector = source_spec.get('applicationSelector', {
                'resourceLabelSelectors': [{
                    'labelSelector': {
                        'matchLabels': {'app': original_app_name}
                    }
                }]
            })
            
            logger.info(f"  ✓ Found source Application CRD with selector: {app_selector}")
            sys.stdout.flush()
            
        except ApiException as e:
            if e.status == 404:
                # Source Application CRD doesn't exist, use default selector
                logger.warning(f"  ⚠ Source Application CRD not found, using default selector")
                app_selector = {
                    'resourceLabelSelectors': [{
                        'labelSelector': {
                            'matchLabels': {'app': original_app_name}
                        }
                    }]
                }
                sys.stdout.flush()
            else:
                raise
        
        # Check if Application CRD already exists in target namespace
        # Use restored_app_name (which could be different if cloning) for the CRD name
        try:
            k8s_api.get_namespaced_custom_object(
                group=Config.NDK_API_GROUP,
                version=Config.NDK_API_VERSION,
                namespace=restore_namespace,
                plural='applications',
                name=restored_app_name
            )
            logger.info(f"  ✓ Application CRD '{restored_app_name}' already exists in target namespace")
            sys.stdout.flush()
        except ApiException as e:
            if e.status == 404:
                # Create the Application CRD in target namespace
                # Use restored_app_name for the CRD name (supports cloning with new name)
                # But keep the selector pointing to original_app_name (NDK restores with original names)
                app_manifest = {
                    'apiVersion': f'{Config.NDK_API_GROUP}/{Config.NDK_API_VERSION}',
                    'kind': 'Application',
                    'metadata': {
                        'name': restored_app_name,
                        'namespace': restore_namespace,
                        'labels': {
                            'app.kubernetes.io/managed-by': 'ndk-dashboard',
                            'restored-from': namespace
                        }
                    },
                    'spec': {
                        'applicationSelector': app_selector
                    }
                }
                
                k8s_api.create_namespaced_custom_object(
                    group=Config.NDK_API_GROUP,
                    version=Config.NDK_API_VERSION,
                    namespace=restore_namespace,
                    plural='applications',
                    body=app_manifest
                )
                logger.info(f"  ✓ Created Application CRD '{restored_app_name}' in namespace '{restore_namespace}'")
                sys.stdout.flush()
            else:
                raise
        
        # Return info about the restored/cloned application
        return {
            'name': restored_app_name,  # The new application name (could be different if cloned)
            'namespace': restore_namespace,
            'snapshot': name,
            'original_application': original_app_name,
            'restore_name': restore_name,  # The restore CRD name
            'is_clone': new_app_name is not None and new_app_name != original_app_name
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
    
    @staticmethod
    def get_restore_status(namespace, restore_name):
        """Get detailed status of a restore operation including error messages"""
        if not k8s_api:
            raise Exception('Kubernetes API not available')
        
        # Get the ApplicationSnapshotRestore CRD
        restore_crd = k8s_api.get_namespaced_custom_object(
            group=Config.NDK_API_GROUP,
            version=Config.NDK_API_VERSION,
            namespace=namespace,
            plural='applicationsnapshotrestores',
            name=restore_name
        )
        
        status = restore_crd.get('status', {})
        conditions = status.get('conditions', [])
        
        # Extract detailed error information
        error_details = []
        for condition in conditions:
            if condition.get('status') == 'False':
                error_details.append({
                    'type': condition.get('type'),
                    'reason': condition.get('reason'),
                    'message': condition.get('message'),
                    'lastTransitionTime': condition.get('lastTransitionTime')
                })
        
        # Log detailed status for debugging
        logger.info(f"📊 Restore Status for {restore_name}:")
        logger.info(f"   Phase: {status.get('phase', 'Unknown')}")
        logger.info(f"   Conditions: {len(conditions)}")
        if error_details:
            logger.error(f"   ❌ Errors found:")
            for error in error_details:
                logger.error(f"      - {error['type']}: {error['message']}")
        sys.stdout.flush()
        
        return {
            'name': restore_name,
            'namespace': namespace,
            'phase': status.get('phase', 'Unknown'),
            'conditions': conditions,
            'errors': error_details,
            'full_status': status
        }