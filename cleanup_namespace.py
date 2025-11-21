#!/usr/bin/env python3
"""
NDK Namespace Cleanup Script

This script cleans up all resources in a specified namespace, including:
- NDK Custom Resources (Applications, Snapshots, ProtectionPlans, etc.)
- Standard Kubernetes resources (StatefulSets, Deployments, Services, PVCs, etc.)
- Secrets and ConfigMaps

Usage:
    python cleanup_namespace.py <namespace>
    python cleanup_namespace.py nkp-dev
    python cleanup_namespace.py nkp-dev --dry-run
    python cleanup_namespace.py nkp-dev --skip-confirm
"""

import subprocess
import sys
import argparse
from typing import List, Tuple


class NamespaceCleanup:
    """Handles cleanup of all resources in a Kubernetes namespace"""
    
    # NDK Custom Resource types
    NDK_RESOURCES = [
        'application',
        'applicationsnapshot',
        'applicationsnapshotrestore',
        'protectionplan',
        'jobscheduler',
    ]
    
    # Standard Kubernetes resources (order matters - delete workloads before storage)
    K8S_RESOURCES = [
        'deployment',
        'statefulset',
        'daemonset',
        'replicaset',
        'job',
        'cronjob',
        'pod',
        'service',
        'ingress',
        'pvc',
        'secret',
        'configmap',
    ]
    
    def __init__(self, namespace: str, dry_run: bool = False, skip_confirm: bool = False):
        self.namespace = namespace
        self.dry_run = dry_run
        self.skip_confirm = skip_confirm
        self.deleted_resources = []
        
    def run_kubectl(self, args: List[str]) -> Tuple[int, str, str]:
        """Run kubectl command and return exit code, stdout, stderr"""
        cmd = ['kubectl'] + args
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return 1, "", "Command timed out"
        except Exception as e:
            return 1, "", str(e)
    
    def check_namespace_exists(self) -> bool:
        """Check if the namespace exists"""
        returncode, stdout, stderr = self.run_kubectl(['get', 'namespace', self.namespace])
        return returncode == 0
    
    def get_resources(self, resource_type: str) -> List[str]:
        """Get list of resources of a specific type in the namespace"""
        returncode, stdout, stderr = self.run_kubectl([
            'get', resource_type,
            '-n', self.namespace,
            '-o', 'name',
            '--ignore-not-found'
        ])
        
        if returncode != 0:
            return []
        
        resources = [line.strip() for line in stdout.strip().split('\n') if line.strip()]
        return resources
    
    def delete_resources(self, resource_type: str) -> bool:
        """Delete all resources of a specific type"""
        resources = self.get_resources(resource_type)
        
        if not resources:
            return True
        
        print(f"\n📦 Found {len(resources)} {resource_type}(s):")
        for resource in resources:
            print(f"   - {resource}")
        
        if self.dry_run:
            print(f"   [DRY RUN] Would delete {len(resources)} {resource_type}(s)")
            return True
        
        print(f"   Deleting {len(resources)} {resource_type}(s)...", end=' ')
        returncode, stdout, stderr = self.run_kubectl([
            'delete', resource_type,
            '--all',
            '-n', self.namespace,
            '--timeout=60s'
        ])
        
        if returncode == 0:
            print("✓")
            self.deleted_resources.append(f"{len(resources)} {resource_type}(s)")
            return True
        else:
            print("✗")
            print(f"   Error: {stderr}")
            return False
    
    def cleanup(self) -> bool:
        """Perform the cleanup"""
        print(f"\n{'='*60}")
        print(f"NDK Namespace Cleanup")
        print(f"{'='*60}")
        print(f"Namespace: {self.namespace}")
        print(f"Dry Run: {self.dry_run}")
        print(f"{'='*60}\n")
        
        # Check if namespace exists
        if not self.check_namespace_exists():
            print(f"❌ Namespace '{self.namespace}' does not exist!")
            return False
        
        # Confirm deletion
        if not self.skip_confirm and not self.dry_run:
            print(f"⚠️  WARNING: This will delete ALL resources in namespace '{self.namespace}'")
            response = input("Are you sure you want to continue? (yes/no): ")
            if response.lower() not in ['yes', 'y']:
                print("❌ Cleanup cancelled")
                return False
        
        success = True
        
        # Delete NDK Custom Resources first
        print("\n🔧 Cleaning up NDK Custom Resources...")
        for resource_type in self.NDK_RESOURCES:
            if not self.delete_resources(resource_type):
                success = False
        
        # Delete standard Kubernetes resources
        print("\n🔧 Cleaning up Kubernetes Resources...")
        for resource_type in self.K8S_RESOURCES:
            if not self.delete_resources(resource_type):
                success = False
        
        # Summary
        print(f"\n{'='*60}")
        if self.dry_run:
            print("✓ Dry run completed - no resources were deleted")
        elif success:
            print("✓ Cleanup completed successfully!")
            if self.deleted_resources:
                print("\nDeleted resources:")
                for resource in self.deleted_resources:
                    print(f"   - {resource}")
        else:
            print("⚠️  Cleanup completed with some errors")
        print(f"{'='*60}\n")
        
        return success


def main():
    parser = argparse.ArgumentParser(
        description='Clean up all resources in a Kubernetes namespace',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s nkp-dev                    # Clean up nkp-dev namespace
  %(prog)s nkp-dev --dry-run          # Show what would be deleted
  %(prog)s nkp-dev --skip-confirm     # Skip confirmation prompt
        """
    )
    
    parser.add_argument(
        'namespace',
        help='Namespace to clean up'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be deleted without actually deleting'
    )
    
    parser.add_argument(
        '--skip-confirm',
        action='store_true',
        help='Skip confirmation prompt (use with caution!)'
    )
    
    args = parser.parse_args()
    
    # Validate namespace name
    if not args.namespace or args.namespace.strip() == '':
        print("❌ Error: Namespace cannot be empty")
        sys.exit(1)
    
    # Prevent accidental deletion of system namespaces
    protected_namespaces = ['kube-system', 'kube-public', 'kube-node-lease', 'default']
    if args.namespace in protected_namespaces:
        print(f"❌ Error: Cannot clean up protected namespace '{args.namespace}'")
        sys.exit(1)
    
    # Run cleanup
    cleanup = NamespaceCleanup(
        namespace=args.namespace,
        dry_run=args.dry_run,
        skip_confirm=args.skip_confirm
    )
    
    success = cleanup.cleanup()
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()