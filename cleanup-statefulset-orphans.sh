#!/bin/bash
# NDK Dashboard - Cleanup Orphaned StatefulSet Resources Script
# This script finds and removes StatefulSets, Services, and Secrets that were
# created by the NDK Dashboard but whose NDK Application CR no longer exists

set -e

echo "=========================================="
echo "NDK Dashboard - StatefulSet Orphan Cleanup"
echo "=========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
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

# Get all namespaces or use default
echo "Select namespace to scan:"
echo "1) All namespaces"
echo "2) default namespace only"
echo "3) Specify namespace"
read -p "Enter choice (1-3): " ns_choice

case $ns_choice in
    1)
        NAMESPACES=$(kubectl get namespaces -o jsonpath='{.items[*].metadata.name}')
        echo -e "${BLUE}Scanning all namespaces...${NC}"
        ;;
    2)
        NAMESPACES="default"
        echo -e "${BLUE}Scanning default namespace...${NC}"
        ;;
    3)
        read -p "Enter namespace name: " custom_ns
        NAMESPACES="$custom_ns"
        echo -e "${BLUE}Scanning namespace: $custom_ns${NC}"
        ;;
    *)
        echo -e "${RED}Invalid choice${NC}"
        exit 1
        ;;
esac

echo ""

# Function to check if NDK Application exists
app_exists() {
    local app_name=$1
    local namespace=$2
    kubectl get application.dataservices.nutanix.com "$app_name" -n "$namespace" &> /dev/null
    return $?
}

# Function to safely delete a resource
delete_resource() {
    local resource_type=$1
    local resource_name=$2
    local namespace=$3
    
    echo -e "${YELLOW}Found orphaned $resource_type: $resource_name (namespace: $namespace)${NC}"
    read -p "Delete this resource? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        kubectl delete $resource_type $resource_name -n $namespace
        echo -e "${GREEN}✓ Deleted $resource_type: $resource_name${NC}"
        return 0
    else
        echo -e "${YELLOW}⊘ Skipped $resource_type: $resource_name${NC}"
        return 1
    fi
}

total_orphans=0
deleted_count=0

# Scan each namespace
for namespace in $NAMESPACES; do
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}Scanning namespace: $namespace${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    
    # Check for orphaned StatefulSets
    echo ""
    echo "1. Checking for orphaned StatefulSets..."
    STATEFULSETS=$(kubectl get statefulsets -n "$namespace" -l app.kubernetes.io/managed-by=ndk-dashboard -o jsonpath='{.items[*].metadata.name}' 2>/dev/null || echo "")
    
    if [ ! -z "$STATEFULSETS" ]; then
        for sts in $STATEFULSETS; do
            if ! app_exists "$sts" "$namespace"; then
                ((total_orphans++))
                if delete_resource "statefulset" "$sts" "$namespace"; then
                    ((deleted_count++))
                fi
            else
                echo -e "${GREEN}✓ StatefulSet $sts has corresponding NDK Application${NC}"
            fi
        done
    else
        echo -e "${GREEN}✓ No StatefulSets with ndk-dashboard label found${NC}"
    fi
    
    # Check for orphaned Services (headless services created by dashboard)
    echo ""
    echo "2. Checking for orphaned Services..."
    SERVICES=$(kubectl get services -n "$namespace" -o json 2>/dev/null | \
               jq -r '.items[] | select(.spec.clusterIP=="None") | .metadata.name' || echo "")
    
    if [ ! -z "$SERVICES" ]; then
        for svc in $SERVICES; do
            # Check if there's a corresponding StatefulSet or NDK Application
            if ! kubectl get statefulset "$svc" -n "$namespace" &> /dev/null && \
               ! app_exists "$svc" "$namespace"; then
                ((total_orphans++))
                if delete_resource "service" "$svc" "$namespace"; then
                    ((deleted_count++))
                fi
            else
                echo -e "${GREEN}✓ Service $svc has corresponding resources${NC}"
            fi
        done
    else
        echo -e "${GREEN}✓ No headless services found${NC}"
    fi
    
    # Check for orphaned Secrets (created by dashboard with -secret suffix)
    echo ""
    echo "3. Checking for orphaned Secrets..."
    SECRETS=$(kubectl get secrets -n "$namespace" -o jsonpath='{.items[*].metadata.name}' 2>/dev/null | \
              tr ' ' '\n' | grep -E '\-secret$' || echo "")
    
    if [ ! -z "$SECRETS" ]; then
        for secret in $SECRETS; do
            # Extract app name by removing -secret suffix
            app_name="${secret%-secret}"
            
            # Check if corresponding StatefulSet or NDK Application exists
            if ! kubectl get statefulset "$app_name" -n "$namespace" &> /dev/null && \
               ! app_exists "$app_name" "$namespace"; then
                ((total_orphans++))
                if delete_resource "secret" "$secret" "$namespace"; then
                    ((deleted_count++))
                fi
            else
                echo -e "${GREEN}✓ Secret $secret has corresponding resources${NC}"
            fi
        done
    else
        echo -e "${GREEN}✓ No secrets with -secret suffix found${NC}"
    fi
    
    # Check for orphaned PVCs from StatefulSets
    echo ""
    echo "4. Checking for orphaned PVCs from deleted StatefulSets..."
    PVCS=$(kubectl get pvc -n "$namespace" -o json 2>/dev/null | \
           jq -r '.items[] | select(.metadata.name | startswith("data-")) | .metadata.name' || echo "")
    
    if [ ! -z "$PVCS" ]; then
        for pvc in $PVCS; do
            # Extract StatefulSet name from PVC name (format: data-{statefulset-name}-{ordinal})
            sts_name=$(echo "$pvc" | sed -E 's/^data-(.+)-[0-9]+$/\1/')
            
            # Check if corresponding StatefulSet exists
            if ! kubectl get statefulset "$sts_name" -n "$namespace" &> /dev/null; then
                ((total_orphans++))
                echo -e "${YELLOW}Found orphaned PVC: $pvc (from deleted StatefulSet: $sts_name)${NC}"
                echo -e "${RED}⚠ WARNING: This will delete data permanently!${NC}"
                read -p "Delete this PVC and its data? (y/n) " -n 1 -r
                echo
                if [[ $REPLY =~ ^[Yy]$ ]]; then
                    kubectl delete pvc "$pvc" -n "$namespace"
                    echo -e "${GREEN}✓ Deleted PVC: $pvc${NC}"
                    ((deleted_count++))
                else
                    echo -e "${YELLOW}⊘ Skipped PVC: $pvc${NC}"
                fi
            else
                echo -e "${GREEN}✓ PVC $pvc has corresponding StatefulSet${NC}"
            fi
        done
    else
        echo -e "${GREEN}✓ No StatefulSet PVCs found${NC}"
    fi
    
    # Check for orphaned Pods
    echo ""
    echo "5. Checking for orphaned Pods..."
    PODS=$(kubectl get pods -n "$namespace" -l app.kubernetes.io/managed-by=ndk-dashboard -o jsonpath='{.items[*].metadata.name}' 2>/dev/null || echo "")
    
    if [ ! -z "$PODS" ]; then
        for pod in $PODS; do
            # Extract app name from pod (format: {app-name}-{ordinal})
            app_name=$(echo "$pod" | sed -E 's/-[0-9]+$//')
            
            # Check if corresponding StatefulSet exists
            if ! kubectl get statefulset "$app_name" -n "$namespace" &> /dev/null; then
                ((total_orphans++))
                if delete_resource "pod" "$pod" "$namespace"; then
                    ((deleted_count++))
                fi
            else
                echo -e "${GREEN}✓ Pod $pod has corresponding StatefulSet${NC}"
            fi
        done
    else
        echo -e "${GREEN}✓ No orphaned pods found${NC}"
    fi
done

echo ""
echo "=========================================="
echo "Cleanup Summary"
echo "=========================================="
echo ""
echo -e "Total orphaned resources found: ${YELLOW}$total_orphans${NC}"
echo -e "Resources deleted: ${GREEN}$deleted_count${NC}"
echo -e "Resources skipped: ${YELLOW}$((total_orphans - deleted_count))${NC}"
echo ""

if [ $total_orphans -eq 0 ]; then
    echo -e "${GREEN}✓ No orphaned resources found! Your cluster is clean.${NC}"
elif [ $deleted_count -eq $total_orphans ]; then
    echo -e "${GREEN}✓ All orphaned resources have been cleaned up!${NC}"
else
    echo -e "${YELLOW}⚠ Some orphaned resources were not deleted.${NC}"
    echo "Run this script again to clean them up."
fi

echo ""
echo -e "${BLUE}Note: The delete function in the NDK Dashboard has been updated${NC}"
echo -e "${BLUE}to prevent orphaned resources in future deletions.${NC}"