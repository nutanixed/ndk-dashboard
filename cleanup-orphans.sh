#!/bin/bash

# Cleanup script for orphaned Kubernetes resources created by NDK Dashboard
# This script identifies and removes orphaned StatefulSets, Services, Secrets, and PVCs

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}NDK Dashboard Orphaned Resource Cleanup${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Namespace to check
NAMESPACE="mysql-namespace"

echo -e "${YELLOW}Scanning namespace: ${NAMESPACE}${NC}"
echo ""

# Get all StatefulSets managed by ndk-dashboard
echo -e "${BLUE}Active StatefulSets:${NC}"
ACTIVE_STATEFULSETS=$(kubectl get statefulsets -n ${NAMESPACE} -l app.kubernetes.io/managed-by=ndk-dashboard -o jsonpath='{.items[*].metadata.name}')
if [ -z "$ACTIVE_STATEFULSETS" ]; then
    echo "  None found"
    ACTIVE_STATEFULSETS=""
else
    for sts in $ACTIVE_STATEFULSETS; do
        echo -e "  ${GREEN}✓${NC} $sts"
    done
fi
echo ""

# Get all Services
echo -e "${BLUE}Checking Services:${NC}"
ALL_SERVICES=$(kubectl get services -n ${NAMESPACE} -o jsonpath='{.items[*].metadata.name}')
ORPHANED_SERVICES=""
for svc in $ALL_SERVICES; do
    # Check if there's a matching StatefulSet
    if echo "$ACTIVE_STATEFULSETS" | grep -qw "$svc"; then
        echo -e "  ${GREEN}✓${NC} $svc (active)"
    else
        echo -e "  ${RED}✗${NC} $svc (ORPHANED)"
        ORPHANED_SERVICES="$ORPHANED_SERVICES $svc"
    fi
done
echo ""

# Get all Secrets (excluding default tokens and helm releases)
echo -e "${BLUE}Checking Secrets:${NC}"
ALL_SECRETS=$(kubectl get secrets -n ${NAMESPACE} -o jsonpath='{.items[?(@.type!="kubernetes.io/service-account-token")].metadata.name}' | tr ' ' '\n' | grep -v "^sh\.helm\.release" | tr '\n' ' ')
ORPHANED_SECRETS=""
for secret in $ALL_SECRETS; do
    # Extract app name from secret (remove -credentials suffix)
    app_name=$(echo "$secret" | sed 's/-credentials$//')
    
    # Check if there's a matching StatefulSet
    if echo "$ACTIVE_STATEFULSETS" | grep -qw "$app_name"; then
        echo -e "  ${GREEN}✓${NC} $secret (active)"
    else
        echo -e "  ${RED}✗${NC} $secret (ORPHANED)"
        ORPHANED_SECRETS="$ORPHANED_SECRETS $secret"
    fi
done
echo ""

# Get all PVCs
echo -e "${BLUE}Checking PVCs:${NC}"
ALL_PVCS=$(kubectl get pvc -n ${NAMESPACE} -o jsonpath='{.items[*].metadata.name}')
ORPHANED_PVCS=""
for pvc in $ALL_PVCS; do
    # Extract StatefulSet name from PVC (format: data-{statefulset}-{ordinal})
    sts_name=$(echo "$pvc" | sed -E 's/^data-(.+)-[0-9]+$/\1/')
    
    # Check if the StatefulSet exists
    if echo "$ACTIVE_STATEFULSETS" | grep -qw "$sts_name"; then
        # Check if the ordinal is within the replica count
        ordinal=$(echo "$pvc" | sed -E 's/^data-.+-([0-9]+)$/\1/')
        replicas=$(kubectl get statefulset "$sts_name" -n ${NAMESPACE} -o jsonpath='{.spec.replicas}')
        
        if [ "$ordinal" -lt "$replicas" ]; then
            echo -e "  ${GREEN}✓${NC} $pvc (active)"
        else
            echo -e "  ${RED}✗${NC} $pvc (ORPHANED - ordinal $ordinal >= replicas $replicas)"
            ORPHANED_PVCS="$ORPHANED_PVCS $pvc"
        fi
    else
        echo -e "  ${RED}✗${NC} $pvc (ORPHANED - no StatefulSet)"
        ORPHANED_PVCS="$ORPHANED_PVCS $pvc"
    fi
done
echo ""

# Summary
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Summary:${NC}"
echo -e "${BLUE}========================================${NC}"
ORPHANED_SERVICES_COUNT=$(echo $ORPHANED_SERVICES | wc -w)
ORPHANED_SECRETS_COUNT=$(echo $ORPHANED_SECRETS | wc -w)
ORPHANED_PVCS_COUNT=$(echo $ORPHANED_PVCS | wc -w)

echo -e "Orphaned Services: ${RED}$ORPHANED_SERVICES_COUNT${NC}"
echo -e "Orphaned Secrets:  ${RED}$ORPHANED_SECRETS_COUNT${NC}"
echo -e "Orphaned PVCs:     ${RED}$ORPHANED_PVCS_COUNT${NC}"
echo ""

TOTAL_ORPHANED=$((ORPHANED_SERVICES_COUNT + ORPHANED_SECRETS_COUNT + ORPHANED_PVCS_COUNT))

if [ $TOTAL_ORPHANED -eq 0 ]; then
    echo -e "${GREEN}No orphaned resources found!${NC}"
    exit 0
fi

# Confirmation prompt
echo -e "${YELLOW}WARNING: This will delete the orphaned resources listed above.${NC}"
echo -e "${YELLOW}This action cannot be undone!${NC}"
echo ""
read -p "Do you want to proceed with cleanup? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo -e "${YELLOW}Cleanup cancelled.${NC}"
    exit 0
fi

echo ""
echo -e "${BLUE}Starting cleanup...${NC}"
echo ""

# Delete orphaned Services
if [ -n "$ORPHANED_SERVICES" ]; then
    echo -e "${BLUE}Deleting orphaned Services...${NC}"
    for svc in $ORPHANED_SERVICES; do
        echo -n "  Deleting service: $svc... "
        if kubectl delete service "$svc" -n ${NAMESPACE} --ignore-not-found=true; then
            echo -e "${GREEN}✓${NC}"
        else
            echo -e "${RED}✗ Failed${NC}"
        fi
    done
    echo ""
fi

# Delete orphaned Secrets
if [ -n "$ORPHANED_SECRETS" ]; then
    echo -e "${BLUE}Deleting orphaned Secrets...${NC}"
    for secret in $ORPHANED_SECRETS; do
        echo -n "  Deleting secret: $secret... "
        if kubectl delete secret "$secret" -n ${NAMESPACE} --ignore-not-found=true; then
            echo -e "${GREEN}✓${NC}"
        else
            echo -e "${RED}✗ Failed${NC}"
        fi
    done
    echo ""
fi

# Delete orphaned PVCs
if [ -n "$ORPHANED_PVCS" ]; then
    echo -e "${BLUE}Deleting orphaned PVCs...${NC}"
    for pvc in $ORPHANED_PVCS; do
        echo -n "  Deleting PVC: $pvc... "
        if kubectl delete pvc "$pvc" -n ${NAMESPACE} --ignore-not-found=true; then
            echo -e "${GREEN}✓${NC}"
        else
            echo -e "${RED}✗ Failed${NC}"
        fi
    done
    echo ""
fi

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Cleanup completed!${NC}"
echo -e "${GREEN}========================================${NC}"