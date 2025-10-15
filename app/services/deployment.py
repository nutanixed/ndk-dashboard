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
                'namespace': namespace,
                'labels': {'app': app_name}
            },
            'type': 'Opaque',
            'data': encoded_secret_data
        }
        
        try:
            k8s_core_api.create_namespaced_secret(namespace=namespace, body=secret_manifest)
        except ApiException as e:
            if e.status != 409:  # Ignore if already exists
                raise
        
        # Step 3: Create ConfigMap for MySQL replication if needed
        if app_type == 'mysql' and replicas > 1:
            DeploymentService._create_mysql_replication_configmap(app_name, namespace)
        
        # Step 4: Build environment variables based on app type
        env_vars = DeploymentService._build_env_vars(app_type, secret_name, database_name, app_name)
        
        # Step 5: Build StatefulSet manifest
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
        
        # Step 6: Create Service
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
        
        # Step 7: Create NDK Application CR if requested
        if create_ndk_app:
            DeploymentService._create_ndk_application(app_name, namespace, custom_labels)
        
        # Step 8: Create Protection Plan if requested
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
    def _build_env_vars(app_type, secret_name, database_name, app_name=None):
        """Build environment variables based on application type"""
        env_vars = []
        
        if app_type == 'mysql':
            env_vars = [
                {'name': 'MYSQL_ROOT_PASSWORD', 'valueFrom': {'secretKeyRef': {'name': secret_name, 'key': 'password'}}},
                {'name': 'MYSQL_REPLICATION_USER', 'value': 'repl'},
                {'name': 'MYSQL_REPLICATION_PASSWORD', 'valueFrom': {'secretKeyRef': {'name': secret_name, 'key': 'password'}}},
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
    def _create_mysql_replication_configmap(app_name, namespace):
        """Create ConfigMap with MySQL replication configuration scripts"""
        configmap_name = f"{app_name}-replication-config"
        
        # Init script for master configuration
        master_cnf = """[mysqld]
log-bin=mysql-bin
server-id=1
binlog-format=ROW
"""
        
        # Init script for replica configuration
        replica_cnf = """[mysqld]
server-id=REPLICA_ID
relay-log=relay-bin
read-only=1
"""
        
        # Initialization script to set up replication
        init_script = """#!/bin/bash
set -ex

# Get pod ordinal from hostname
[[ $(hostname) =~ -([0-9]+)$ ]] || exit 1
ordinal=${BASH_REMATCH[1]}

# Copy appropriate config based on ordinal
if [[ $ordinal -eq 0 ]]; then
  # This is the master
  cp /mnt/config-map/master.cnf /etc/mysql/conf.d/server-id.cnf
else
  # This is a replica
  cp /mnt/config-map/replica.cnf /etc/mysql/conf.d/server-id.cnf
  # Set unique server-id for each replica
  sed -i "s/REPLICA_ID/$((100 + $ordinal))/g" /etc/mysql/conf.d/server-id.cnf
fi
"""
        
        # Post-start script to configure replication
        post_start_script = """#!/bin/bash
set -ex

# Get pod ordinal from hostname
[[ $(hostname) =~ -([0-9]+)$ ]] || exit 1
ordinal=${BASH_REMATCH[1]}

# Wait for MySQL to be ready
until mysql -h 127.0.0.1 -uroot -p${MYSQL_ROOT_PASSWORD} -e "SELECT 1"; do
  echo "Waiting for MySQL to be ready..."
  sleep 2
done

if [[ $ordinal -eq 0 ]]; then
  # This is the master - create replication user
  mysql -h 127.0.0.1 -uroot -p${MYSQL_ROOT_PASSWORD} <<EOF
CREATE USER IF NOT EXISTS '${MYSQL_REPLICATION_USER}'@'%' IDENTIFIED BY '${MYSQL_REPLICATION_PASSWORD}';
GRANT REPLICATION SLAVE ON *.* TO '${MYSQL_REPLICATION_USER}'@'%';
FLUSH PRIVILEGES;
EOF
else
  # This is a replica - configure replication from master
  # Wait for master to be ready
  until mysql -h MASTER_HOST -uroot -p${MYSQL_ROOT_PASSWORD} -e "SELECT 1"; do
    echo "Waiting for master to be ready..."
    sleep 2
  done
  
  # Get master status
  MASTER_LOG_FILE=$(mysql -h MASTER_HOST -uroot -p${MYSQL_ROOT_PASSWORD} -e "SHOW MASTER STATUS\\G" | grep File | awk '{print $2}')
  MASTER_LOG_POS=$(mysql -h MASTER_HOST -uroot -p${MYSQL_ROOT_PASSWORD} -e "SHOW MASTER STATUS\\G" | grep Position | awk '{print $2}')
  
  # Configure replication
  mysql -h 127.0.0.1 -uroot -p${MYSQL_ROOT_PASSWORD} <<EOF
STOP SLAVE;
CHANGE MASTER TO
  MASTER_HOST='MASTER_HOST',
  MASTER_USER='${MYSQL_REPLICATION_USER}',
  MASTER_PASSWORD='${MYSQL_REPLICATION_PASSWORD}',
  MASTER_LOG_FILE='${MASTER_LOG_FILE}',
  MASTER_LOG_POS=${MASTER_LOG_POS};
START SLAVE;
EOF
fi
"""
        
        configmap_manifest = {
            'apiVersion': 'v1',
            'kind': 'ConfigMap',
            'metadata': {
                'name': configmap_name,
                'namespace': namespace,
                'labels': {'app': app_name}
            },
            'data': {
                'master.cnf': master_cnf,
                'replica.cnf': replica_cnf,
                'init-mysql.sh': init_script,
                'post-start.sh': post_start_script
            }
        }
        
        try:
            k8s_core_api.create_namespaced_config_map(namespace=namespace, body=configmap_manifest)
        except ApiException as e:
            if e.status != 409:  # Ignore if already exists
                raise
    
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
        
        # Base container configuration
        container_spec = {
            'name': app_type,
            'image': docker_image,
            'ports': [{'containerPort': port, 'name': app_type}],
            'env': env_vars,
            'volumeMounts': [{
                'name': 'data',
                'mountPath': mount_path
            }]
        }
        
        # Pod spec
        pod_spec = {
            'containers': [container_spec]
        }
        
        # Add MySQL replication configuration if replicas > 1
        if app_type == 'mysql' and replicas > 1:
            # Add config volume mount to main container
            container_spec['volumeMounts'].append({
                'name': 'conf',
                'mountPath': '/etc/mysql/conf.d'
            })
            
            # Add scripts volume mount to main container
            container_spec['volumeMounts'].append({
                'name': 'scripts',
                'mountPath': '/docker-entrypoint-initdb.d'
            })
            
            # Add lifecycle hook to configure replication after MySQL starts
            master_service = f"{app_name}-0.{app_name}.{namespace}.svc.cluster.local"
            post_start_script_with_master = f"""#!/bin/bash
set -ex

# Get pod ordinal from HOSTNAME environment variable
[[ $HOSTNAME =~ -([0-9]+)$ ]] || exit 1
ordinal=${{BASH_REMATCH[1]}}

# Wait for MySQL to be ready
until mysql -h 127.0.0.1 -uroot -p${{MYSQL_ROOT_PASSWORD}} -e "SELECT 1" 2>/dev/null; do
  echo "Waiting for MySQL to be ready..."
  sleep 2
done

if [[ $ordinal -eq 0 ]]; then
  # This is the master - create replication user
  mysql -h 127.0.0.1 -uroot -p${{MYSQL_ROOT_PASSWORD}} <<EOF
CREATE USER IF NOT EXISTS '${{MYSQL_REPLICATION_USER}}'@'%' IDENTIFIED BY '${{MYSQL_REPLICATION_PASSWORD}}';
GRANT REPLICATION SLAVE ON *.* TO '${{MYSQL_REPLICATION_USER}}'@'%';
FLUSH PRIVILEGES;
EOF
else
  # This is a replica - configure replication from master
  # Wait for master to be ready
  until mysql -h {master_service} -uroot -p${{MYSQL_ROOT_PASSWORD}} -e "SELECT 1" 2>/dev/null; do
    echo "Waiting for master to be ready..."
    sleep 2
  done
  
  # Get master status
  MASTER_LOG_FILE=$(mysql -h {master_service} -uroot -p${{MYSQL_ROOT_PASSWORD}} -e "SHOW MASTER STATUS\\G" 2>/dev/null | grep File | awk '{{print $2}}')
  MASTER_LOG_POS=$(mysql -h {master_service} -uroot -p${{MYSQL_ROOT_PASSWORD}} -e "SHOW MASTER STATUS\\G" 2>/dev/null | grep Position | awk '{{print $2}}')
  
  # Configure replication
  mysql -h 127.0.0.1 -uroot -p${{MYSQL_ROOT_PASSWORD}} <<EOF
STOP SLAVE;
CHANGE MASTER TO
  MASTER_HOST='{master_service}',
  MASTER_USER='${{MYSQL_REPLICATION_USER}}',
  MASTER_PASSWORD='${{MYSQL_REPLICATION_PASSWORD}}',
  MASTER_LOG_FILE='${{MASTER_LOG_FILE}}',
  MASTER_LOG_POS=${{MASTER_LOG_POS}};
START SLAVE;
EOF
fi
"""
            
            container_spec['lifecycle'] = {
                'postStart': {
                    'exec': {
                        'command': ['/bin/bash', '-c', post_start_script_with_master]
                    }
                }
            }
            
            # Add init container to set up MySQL configuration
            pod_spec['initContainers'] = [{
                'name': 'init-mysql',
                'image': docker_image,
                'command': ['/bin/bash', '-c'],
                'args': ["""
set -ex
# Get pod ordinal from HOSTNAME environment variable
[[ $HOSTNAME =~ -([0-9]+)$ ]] || exit 1
ordinal=${BASH_REMATCH[1]}

# Copy appropriate config based on ordinal
if [[ $ordinal -eq 0 ]]; then
  # This is the master
  cp /mnt/config-map/master.cnf /mnt/conf.d/server-id.cnf
else
  # This is a replica
  cp /mnt/config-map/replica.cnf /mnt/conf.d/server-id.cnf
  # Set unique server-id for each replica
  sed -i "s/REPLICA_ID/$((100 + $ordinal))/g" /mnt/conf.d/server-id.cnf
fi
                """],
                'volumeMounts': [
                    {
                        'name': 'conf',
                        'mountPath': '/mnt/conf.d'
                    },
                    {
                        'name': 'config-map',
                        'mountPath': '/mnt/config-map'
                    }
                ]
            }]
            
            # Add volumes for configuration
            pod_spec['volumes'] = [
                {
                    'name': 'conf',
                    'emptyDir': {}
                },
                {
                    'name': 'scripts',
                    'emptyDir': {}
                },
                {
                    'name': 'config-map',
                    'configMap': {
                        'name': f"{app_name}-replication-config"
                    }
                }
            ]
        
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
                    'spec': pod_spec
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
            'namespace': namespace,
            'labels': {
                'app.kubernetes.io/managed-by': 'ndk-dashboard'
            }
        }
        
        # Add custom labels if provided
        if custom_labels:
            metadata['labels'].update(custom_labels)
        
        ndk_app_manifest = {
            'apiVersion': f'{Config.NDK_API_GROUP}/{Config.NDK_API_VERSION}',
            'kind': 'Application',
            'metadata': metadata,
            'spec': {
                'applicationSelector': {
                    'resourceLabelSelectors': [
                        {
                            'labelSelector': {
                                'matchLabels': {'app': app_name}
                            }
                        }
                    ]
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