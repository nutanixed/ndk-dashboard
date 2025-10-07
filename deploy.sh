#!/bin/bash
# NDK Dashboard Deployment Script

set -e

echo "=========================================="
echo "NDK Dashboard Deployment"
echo "=========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if kubectl is available
if ! command -v kubectl &> /dev/null; then
    echo -e "${RED}✗ kubectl not found. Please install kubectl first.${NC}"
    exit 1
fi

echo -e "${GREEN}✓ kubectl found${NC}"

# Check cluster connectivity
if ! kubectl cluster-info &> /dev/null; then
    echo -e "${RED}✗ Cannot connect to Kubernetes cluster${NC}"
    echo "Please configure kubectl to connect to your cluster"
    exit 1
fi

echo -e "${GREEN}✓ Connected to Kubernetes cluster${NC}"
echo ""

# Check if NDK CRDs exist
echo "Checking for NDK CRDs..."
if kubectl get crd applications.dataservices.nutanix.com &> /dev/null; then
    echo -e "${GREEN}✓ NDK CRDs found${NC}"
else
    echo -e "${YELLOW}⚠ NDK CRDs not found. Make sure NDK is installed.${NC}"
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi
echo ""

# Deploy RBAC
echo "Deploying RBAC (ServiceAccount, ClusterRole, ClusterRoleBinding)..."
kubectl apply -f deployment/rbac.yaml
echo -e "${GREEN}✓ RBAC deployed${NC}"
echo ""

# Deploy Secret
echo "Deploying Secret..."
echo -e "${YELLOW}⚠ WARNING: Using default credentials. Change them in deployment/secret.yaml for production!${NC}"
kubectl apply -f deployment/secret.yaml
echo -e "${GREEN}✓ Secret deployed${NC}"
echo ""

# Deploy ConfigMap
echo "Deploying ConfigMap..."
kubectl apply -f deployment/configmap.yaml
echo -e "${GREEN}✓ ConfigMap deployed${NC}"
echo ""

# Deploy Application
echo "Deploying NDK Dashboard application..."
kubectl apply -f deployment/deployment.yaml
echo -e "${GREEN}✓ Deployment created${NC}"
echo ""

# Deploy Service
echo "Deploying Services..."
kubectl apply -f deployment/service.yaml
echo -e "${GREEN}✓ Services created${NC}"
echo ""

# Wait for pods to be ready
echo "Waiting for pods to be ready (this may take a few minutes)..."
if kubectl wait --for=condition=ready pod -l app=ndk-dashboard --timeout=300s 2>/dev/null; then
    echo -e "${GREEN}✓ Pods are ready${NC}"
else
    echo -e "${YELLOW}⚠ Pods are not ready yet. Check status with: kubectl get pods -l app=ndk-dashboard${NC}"
fi
echo ""

# Get service information
echo "=========================================="
echo "Deployment Summary"
echo "=========================================="
echo ""

echo "Pods:"
kubectl get pods -l app=ndk-dashboard
echo ""

echo "Services:"
kubectl get svc -l app=ndk-dashboard
echo ""

# Get LoadBalancer IP
EXTERNAL_IP=$(kubectl get svc ndk-dashboard -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || echo "")

if [ -z "$EXTERNAL_IP" ]; then
    echo -e "${YELLOW}⚠ LoadBalancer IP not assigned yet${NC}"
    echo "Run this command to check when it's ready:"
    echo "  kubectl get svc ndk-dashboard"
    echo ""
    echo "If your cluster doesn't support LoadBalancer, use NodePort:"
    echo "  kubectl patch svc ndk-dashboard -p '{\"spec\":{\"type\":\"NodePort\"}}'"
else
    echo -e "${GREEN}✓ Dashboard is accessible at: http://${EXTERNAL_IP}${NC}"
fi

echo ""
echo "=========================================="
echo "Next Steps"
echo "=========================================="
echo ""
echo "1. Access the dashboard:"
echo "   - Get the external IP: kubectl get svc ndk-dashboard"
echo "   - Open in browser: http://<EXTERNAL-IP>"
echo ""
echo "2. Login with credentials:"
echo "   - Username: admin (default)"
echo "   - Password: admin (default)"
echo "   - Change these in deployment/secret.yaml!"
echo ""
echo "3. Monitor the deployment:"
echo "   - Pods: kubectl get pods -l app=ndk-dashboard"
echo "   - Logs: kubectl logs -l app=ndk-dashboard -f"
echo "   - Events: kubectl get events --sort-by='.lastTimestamp'"
echo ""
echo "4. Troubleshooting:"
echo "   - Check pod status: kubectl describe pod -l app=ndk-dashboard"
echo "   - Check logs: kubectl logs -l app=ndk-dashboard"
echo "   - Check RBAC: kubectl auth can-i list applications.dataservices.nutanix.com --as=system:serviceaccount:default:ndk-dashboard"
echo ""
echo -e "${GREEN}Deployment complete!${NC}"