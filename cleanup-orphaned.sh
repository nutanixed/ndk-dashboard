#!/bin/bash
# NDK Dashboard - Cleanup Orphaned Resources Script

set -e

echo "=========================================="
echo "NDK Dashboard - Cleanup Orphaned Resources"
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

# Function to safely delete a resource
delete_resource() {
    local resource_type=$1
    local resource_name=$2
    local namespace=${3:-default}
    
    if kubectl get $resource_type $resource_name -n $namespace &> /dev/null; then
        echo -e "${YELLOW}Found orphaned $resource_type: $resource_name${NC}"
        read -p "Delete this resource? (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            kubectl delete $resource_type $resource_name -n $namespace
            echo -e "${GREEN}✓ Deleted $resource_type: $resource_name${NC}"
        else
            echo -e "${YELLOW}⊘ Skipped $resource_type: $resource_name${NC}"
        fi
    fi
}

echo "Checking for orphaned resources..."
echo ""

# Check for old duplicate services
echo "1. Checking for duplicate services..."
delete_resource "service" "ndk-dashboard-service" "default"
delete_resource "service" "ndk-dashboard-loadbalancer" "default"
echo ""

# Check for failed pods
echo "2. Checking for failed pods..."
FAILED_PODS=$(kubectl get pods -n default -l app=ndk-dashboard --field-selector=status.phase=Failed -o jsonpath='{.items[*].metadata.name}' 2>/dev/null || echo "")
if [ ! -z "$FAILED_PODS" ]; then
    echo -e "${YELLOW}Found failed pods: $FAILED_PODS${NC}"
    read -p "Delete all failed pods? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        kubectl delete pods -n default -l app=ndk-dashboard --field-selector=status.phase=Failed
        echo -e "${GREEN}✓ Deleted failed pods${NC}"
    else
        echo -e "${YELLOW}⊘ Skipped failed pods${NC}"
    fi
else
    echo -e "${GREEN}✓ No failed pods found${NC}"
fi
echo ""

# Check for evicted pods
echo "3. Checking for evicted pods..."
EVICTED_PODS=$(kubectl get pods -n default -l app=ndk-dashboard --field-selector=status.phase=Failed -o json 2>/dev/null | grep -i "evicted" | wc -l || echo "0")
if [ "$EVICTED_PODS" -gt 0 ]; then
    echo -e "${YELLOW}Found $EVICTED_PODS evicted pods${NC}"
    read -p "Delete all evicted pods? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        kubectl get pods -n default -l app=ndk-dashboard --field-selector=status.phase=Failed -o json | \
            jq -r '.items[] | select(.status.reason=="Evicted") | .metadata.name' | \
            xargs -r kubectl delete pod -n default
        echo -e "${GREEN}✓ Deleted evicted pods${NC}"
    else
        echo -e "${YELLOW}⊘ Skipped evicted pods${NC}"
    fi
else
    echo -e "${GREEN}✓ No evicted pods found${NC}"
fi
echo ""

# Check for old replica sets
echo "4. Checking for old replica sets..."
OLD_RS=$(kubectl get rs -n default -l app=ndk-dashboard -o json | jq -r '.items[] | select(.spec.replicas==0) | .metadata.name' 2>/dev/null || echo "")
if [ ! -z "$OLD_RS" ]; then
    echo -e "${YELLOW}Found old replica sets with 0 replicas:${NC}"
    echo "$OLD_RS"
    read -p "Delete old replica sets? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "$OLD_RS" | xargs -r kubectl delete rs -n default
        echo -e "${GREEN}✓ Deleted old replica sets${NC}"
    else
        echo -e "${YELLOW}⊘ Skipped old replica sets${NC}"
    fi
else
    echo -e "${GREEN}✓ No old replica sets found${NC}"
fi
echo ""

# Check for orphaned config maps (not referenced by current deployment)
echo "5. Checking for orphaned config maps..."
# This is informational only - we won't auto-delete config maps
CONFIGMAPS=$(kubectl get configmap -n default -l app=ndk-dashboard -o jsonpath='{.items[*].metadata.name}' 2>/dev/null || echo "")
if [ ! -z "$CONFIGMAPS" ]; then
    echo -e "${GREEN}Found config maps: $CONFIGMAPS${NC}"
    echo "These are being used by the deployment."
else
    echo -e "${GREEN}✓ No config maps found${NC}"
fi
echo ""

# Check for orphaned secrets (not referenced by current deployment)
echo "6. Checking for orphaned secrets..."
# This is informational only - we won't auto-delete secrets
SECRETS=$(kubectl get secret -n default -l app=ndk-dashboard -o jsonpath='{.items[*].metadata.name}' 2>/dev/null || echo "")
if [ ! -z "$SECRETS" ]; then
    echo -e "${GREEN}Found secrets: $SECRETS${NC}"
    echo "These are being used by the deployment."
else
    echo -e "${GREEN}✓ No secrets found${NC}"
fi
echo ""

echo "=========================================="
echo "Cleanup Summary"
echo "=========================================="
echo ""
echo "Current resources:"
echo ""
echo "Deployments:"
kubectl get deployments -n default -l app=ndk-dashboard 2>/dev/null || echo "None"
echo ""
echo "Pods:"
kubectl get pods -n default -l app=ndk-dashboard 2>/dev/null || echo "None"
echo ""
echo "Services:"
kubectl get svc -n default -l app=ndk-dashboard 2>/dev/null || echo "None"
echo ""
echo "ReplicaSets:"
kubectl get rs -n default -l app=ndk-dashboard 2>/dev/null || echo "None"
echo ""

echo -e "${GREEN}Cleanup complete!${NC}"
echo ""
echo "To redeploy with cleaned up configuration, run:"
echo "  ./deploy.sh"