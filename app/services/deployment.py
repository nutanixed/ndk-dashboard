"""
Deployment service - Business logic for deploying applications
"""
import secrets
import string
import base64
import re
from kubernetes import client
from kubernetes.client.rest import ApiException
from app.extensions import k8s_api, k8s_core_api, k8s_apps_api
from config import Config


class DeploymentService:
    """Service class for deploying applications with NDK capabilities"""
    
    @staticmethod
    def deploy_application(app_type, app_name, namespace, replicas, storage_class,
                          storage_size, password, database_name, docker_image, port,
                          create_ndk_app, custom_labels, worker_pool, 
                          create_protection_plan, schedule, retention):
        """Deploy a new application with optional NDK and protection plan"""
        if not k8s_api or not k8s_core_api:
            raise Exception('Kubernetes API not available')
        
        # Validate required fields
        if not all([app_type, app_name, namespace, storage_size, docker_image]):
            raise ValueError('Missing required fields')
        
        # Validate retention count if protection plan is enabled
        if create_protection_plan:
            try:
                retention_int = int(retention)
                if retention_int < 1 or retention_int > 15:
                    raise ValueError('Retention count must be between 1 and 15')
            except (ValueError, TypeError):
                raise ValueError('Retention count must be a valid number between 1 and 15')
        
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
        secret_data = {'password': password}
        if database_name:
            secret_data['database'] = database_name
        
        # Encode secret data to base64
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
        
        # Step 3: Build environment variables based on app type
        env_vars = DeploymentService._build_env_vars(app_type, secret_name, database_name)
        
        # Step 4: Build StatefulSet manifest
        statefulset_manifest = DeploymentService._build_statefulset_manifest(
            app_name, namespace, app_type, replicas, docker_image, port,
            env_vars, storage_class, storage_size
        )
        
        # Add nodeSelector if worker pool is specified
        if worker_pool:
            node_selector = DeploymentService._get_worker_pool_selector(worker_pool)
            if node_selector:
                statefulset_manifest['spec']['template']['spec']['nodeSelector'] = node_selector
        
        # Create StatefulSet
        k8s_apps_api.create_namespaced_stateful_set(namespace=namespace, body=statefulset_manifest)
        
        # Step 5: Create Service
        service_manifest = {
            'apiVersion': 'v1',
            'kind': 'Service',
            'metadata': {
                'name': app_name,
                'namespace': namespace,
                'labels': {'app': app_name}
            },
            'spec': {
                'ports': [{'port': port, 'name': app_type}],
                'clusterIP': 'None',
                'selector': {'app': app_name}
            }
        }
        
        k8s_core_api.create_namespaced_service(namespace=namespace, body=service_manifest)
        
        # Step 6: Create NDK Application CR if requested
        if create_ndk_app:
            DeploymentService._create_ndk_application(app_name, namespace, custom_labels)
        
        # Step 7: Create Protection Plan if requested
        if create_protection_plan and create_ndk_app:
            DeploymentService._create_protection_plan(
                app_name, namespace, schedule, retention
            )
        
        return {
            'name': app_name,
            'namespace': namespace,
            'type': app_type,
            'replicas': replicas,
            'password': password,
            'ndkEnabled': create_ndk_app,
            'protectionEnabled': create_protection_plan
        }
    
    @staticmethod
    def _build_env_vars(app_type, secret_name, database_name):
        """Build environment variables based on application type"""
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
        
        return env_vars
    
    @staticmethod
    def _build_statefulset_manifest(app_name, namespace, app_type, replicas,
                                    docker_image, port, env_vars, storage_class, storage_size):
        """Build StatefulSet manifest"""
        # Determine mount path based on app type
        mount_paths = {
            'mysql': '/var/lib/mysql',
            'postgresql': '/var/lib/postgresql/data',
            'mongodb': '/data/db',
            'redis': '/data',
            'elasticsearch': '/usr/share/elasticsearch/data',
            'cassandra': '/var/lib/cassandra'
        }
        mount_path = mount_paths.get(app_type, '/data')
        
        return {
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
                    'matchLabels': {'app': app_name}
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
                                'mountPath': mount_path
                            }]
                        }]
                    }
                },
                'volumeClaimTemplates': [{
                    'metadata': {'name': 'data'},
                    'spec': {
                        'accessModes': ['ReadWriteOnce'],
                        'storageClassName': storage_class,
                        'resources': {
                            'requests': {'storage': storage_size}
                        }
                    }
                }]
            }
        }
    
    @staticmethod
    def _get_worker_pool_selector(worker_pool):
        """Get node selector for worker pool"""
        if not k8s_core_api:
            return None
        
        pool_label_key = None
        pool_label_value = None
        
        # Check which label pattern is used in the cluster
        nodes = k8s_core_api.list_node()
        for node in nodes.items:
            labels = node.metadata.labels or {}
            node_name = node.metadata.name
            
            # Check if this node matches the selected worker pool
            node_matches = False
            
            # Check label-based matching (direct label value match)
            label_patterns = [
                'karbon.nutanix.com/workerpool',
                'nodepool',
                'node-role.kubernetes.io/worker-pool',
                'worker-pool',
                'pool'
            ]
            
            for label_key in label_patterns:
                if label_key in labels and labels[label_key] == worker_pool:
                    pool_label_key = label_key
                    pool_label_value = worker_pool
                    node_matches = True
                    break
            
            # Check node name-based matching (for NKP/Karbon clusters)
            if not node_matches:
                match = re.search(r'nkp-[^-]+-[^-]+-(.+?)-worker-\d+$', node_name)
                if match and match.group(1) == worker_pool:
                    # Found a node with this pool name - use its nodepool label if available
                    if 'nodepool' in labels:
                        pool_label_key = 'nodepool'
                        pool_label_value = labels['nodepool']
                        node_matches = True
                    elif 'karbon.nutanix.com/workerpool' in labels:
                        pool_label_key = 'karbon.nutanix.com/workerpool'
                        pool_label_value = labels['karbon.nutanix.com/workerpool']
                        node_matches = True
            
            if node_matches:
                break
        
        if pool_label_key and pool_label_value:
            return {pool_label_key: pool_label_value}
        
        return None
    
    @staticmethod
    def _create_ndk_application(app_name, namespace, custom_labels):
        """Create NDK Application CR"""
        metadata = {
            'name': app_name,
            'namespace': namespace
        }
        
        # Add custom labels if provided
        if custom_labels:
            metadata['labels'] = custom_labels
        
        ndk_app_manifest = {
            'apiVersion': f'{Config.NDK_API_GROUP}/{Config.NDK_API_VERSION}',
            'kind': 'Application',
            'metadata': metadata,
            'spec': {
                'selector': {
                    'matchLabels': {'app': app_name}
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
    
    @staticmethod
    def _create_protection_plan(app_name, namespace, schedule, retention):
        """Create protection plan for the application"""
        schedule_name = f"{app_name}-schedule"
        protection_plan_name = f"{app_name}-plan"
        app_protection_plan_name = f"{app_name}-protection"
        
        # Parse retention to get count
        if isinstance(retention, str):
            retention_count = int(retention.rstrip('dDwWmMyY'))
        else:
            retention_count = int(retention)
        
        # Step 1: Create JobScheduler
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
        
        try:
            k8s_api.create_namespaced_custom_object(
                group='scheduler.nutanix.com',
                version='v1alpha1',
                namespace=namespace,
                plural='jobschedulers',
                body=schedule_manifest
            )
        except ApiException as e:
            if e.status != 409:  # Ignore if already exists
                raise
        
        # Step 2: Create ProtectionPlan
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
        
        try:
            k8s_api.create_namespaced_custom_object(
                group=Config.NDK_API_GROUP,
                version=Config.NDK_API_VERSION,
                namespace=namespace,
                plural='protectionplans',
                body=protection_plan_manifest
            )
        except ApiException as e:
            if e.status != 409:  # Ignore if already exists
                raise
        
        # Step 3: Create AppProtectionPlan
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
        
        try:
            k8s_api.create_namespaced_custom_object(
                group=Config.NDK_API_GROUP,
                version=Config.NDK_API_VERSION,
                namespace=namespace,
                plural='appprotectionplans',
                body=app_protection_plan_manifest
            )
        except ApiException as e:
            if e.status != 409:  # Ignore if already exists
                raise