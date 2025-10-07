"""
Deployment routes - API endpoints for deploying applications
"""
from flask import Blueprint, jsonify, request
from kubernetes.client.rest import ApiException
import json
import re
from app.utils import login_required, invalidate_cache
from app.services.deployment import DeploymentService
from app.extensions import k8s_core_api

deployment_bp = Blueprint('deployment', __name__)


@deployment_bp.route('/deploy', methods=['POST'])
@login_required
def deploy_application():
    """Deploy a new application with NDK capabilities"""
    try:
        data = request.get_json()
        
        # Extract deployment configuration
        app_type = data.get('appType')
        app_name = data.get('name')
        namespace = data.get('namespace')
        replicas = int(data.get('replicas', 1))
        storage_class = data.get('storageClass')
        storage_size = data.get('storageSize')
        password = data.get('password')
        database_name = data.get('database')
        docker_image = data.get('image')
        port = int(data.get('port', 3306))
        create_ndk_app = data.get('createNDKApp', False)
        custom_labels = data.get('labels', {})
        worker_pool = data.get('workerPool')
        
        # Handle protection plan
        protection_plan = data.get('protectionPlan', {})
        create_protection_plan = bool(protection_plan)
        schedule = protection_plan.get('schedule', '0 2 * * *') if protection_plan else '0 2 * * *'
        retention = protection_plan.get('retention', 7) if protection_plan else 7
        
        # Deploy the application
        deployment_info = DeploymentService.deploy_application(
            app_type, app_name, namespace, replicas, storage_class,
            storage_size, password, database_name, docker_image, port,
            create_ndk_app, custom_labels, worker_pool,
            create_protection_plan, schedule, retention
        )
        
        # Invalidate cache
        invalidate_cache('applications', 'protectionplans')
        
        return jsonify({
            'success': True,
            'message': f'Application {app_name} deployed successfully',
            'deployment': deployment_info
        }), 201
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except ApiException as e:
        error_msg = f"Failed to deploy application: {e.reason}"
        if e.body:
            try:
                error_body = json.loads(e.body)
                error_msg = error_body.get('message', error_msg)
            except:
                pass
        return jsonify({'error': error_msg}), e.status
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@deployment_bp.route('/namespaces', methods=['GET'])
@login_required
def get_namespaces():
    """Get list of all namespaces"""
    if not k8s_core_api:
        return jsonify({'error': 'Kubernetes API not available'}), 500
    
    try:
        namespaces = k8s_core_api.list_namespace()
        namespace_list = [ns.metadata.name for ns in namespaces.items]
        return jsonify({'namespaces': sorted(namespace_list)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@deployment_bp.route('/workerpools', methods=['GET'])
@login_required
def get_worker_pools():
    """Get list of available worker pools from node labels and names"""
    if not k8s_core_api:
        return jsonify({'error': 'Kubernetes API not available'}), 500
    
    try:
        nodes = k8s_core_api.list_node()
        worker_pools = set()
        
        # Extract worker pool labels from nodes
        # Priority: 1) Node name pattern (NKP), 2) Explicit labels
        for node in nodes.items:
            labels = node.metadata.labels or {}
            node_name = node.metadata.name
            
            # First, try to extract worker pool from node name (for NKP/Karbon clusters)
            # Pattern: nkp-{cluster}-{id}-{POOL_NAME}-worker-{N}
            # Example: nkp-dev01-a8970c-nkp-dev-worker-pool-worker-0 -> nkp-dev-worker-pool
            match = re.search(r'nkp-[^-]+-[^-]+-(.+?)-worker-\d+$', node_name)
            if match:
                pool_name = match.group(1)
                worker_pools.add(pool_name)
            else:
                # If no node name pattern, fall back to label-based detection
                # Check for Nutanix Karbon/NKP label
                if 'karbon.nutanix.com/workerpool' in labels:
                    pool_name = labels['karbon.nutanix.com/workerpool']
                    if pool_name:
                        worker_pools.add(pool_name)
                # Check for nodepool label (common in NKP)
                elif 'nodepool' in labels:
                    pool_name = labels['nodepool']
                    if pool_name:
                        worker_pools.add(pool_name)
                # Check for common worker pool label patterns
                elif 'node-role.kubernetes.io/worker-pool' in labels:
                    pool_name = labels['node-role.kubernetes.io/worker-pool']
                    if pool_name:
                        worker_pools.add(pool_name)
                elif 'worker-pool' in labels:
                    pool_name = labels['worker-pool']
                    if pool_name:
                        worker_pools.add(pool_name)
                elif 'pool' in labels:
                    pool_name = labels['pool']
                    if pool_name:
                        worker_pools.add(pool_name)
        
        return jsonify({'workerPools': sorted(list(worker_pools))})
    except Exception as e:
        return jsonify({'error': str(e)}), 500