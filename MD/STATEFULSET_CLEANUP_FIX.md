# StatefulSet Cleanup Fix

## Problem Identified

The NDK Dashboard's delete function was **not properly cleaning up all resources** created during application deployment, leading to orphaned resources in the Kubernetes cluster.

### What Was Created During Deployment
1. ✅ Secret (`{app-name}-secret`)
2. ✅ StatefulSet (`{app-name}`)
3. ✅ Service (`{app-name}` - headless)
4. ✅ PVCs (via volumeClaimTemplates)
5. ✅ NDK Application CR (`{app-name}`)

### What Was Deleted (Before Fix)
1. ✅ Application Snapshots
2. ✅ Protection Plans
3. ✅ PVCs and PVs
4. ✅ Volume Groups
5. ✅ NDK Application CR

### What Was NOT Deleted (Orphaned Resources)
1. ❌ **StatefulSet** - The workload controller
2. ❌ **Service** - The headless service
3. ❌ **Secret** - Credentials and passwords
4. ❌ **Pods** - Running database pods (orphaned without StatefulSet)

## Solution Implemented

### 1. Updated Delete Function (`app.py`)

Added **4 new cleanup steps** to the `manage_application()` DELETE method:

#### **Step 5: Delete StatefulSet**
- Looks for StatefulSet with the same name as the application
- Uses `propagation_policy='Foreground'` to ensure pods are deleted first
- Waits 2 seconds for graceful pod termination

#### **Step 6: Delete Service**
- Removes the headless service created for StatefulSet networking
- Prevents DNS resolution issues

#### **Step 7: Delete Secret**
- Removes the secret containing database credentials
- Follows naming convention: `{app-name}-secret`

#### **Step 8: Delete Orphaned Pods**
- Cleans up any remaining pods with matching labels
- Uses `grace_period_seconds=0` for immediate termination
- Catches stragglers that might have been missed

#### **Step 9: Delete NDK Application CR**
- (Previously Step 5) - Remains unchanged
- Final step to remove the custom resource

### 2. New Cleanup Script

Created `cleanup-statefulset-orphans.sh` to handle **existing orphaned resources** from previous deletions.

#### Features:
- **Interactive scanning** - Choose all namespaces, default, or specific namespace
- **Safe deletion** - Prompts before deleting each resource
- **Comprehensive checks** - Finds orphaned:
  - StatefulSets (with `app.kubernetes.io/managed-by=ndk-dashboard` label)
  - Headless Services (without corresponding StatefulSet)
  - Secrets (with `-secret` suffix, no corresponding app)
  - PVCs (from deleted StatefulSets, with `data-` prefix)
  - Pods (orphaned from deleted StatefulSets)
- **Summary report** - Shows total found vs. deleted

## Deletion Order (Correct Sequence)

The updated delete function now follows this order:

```
1. Snapshots          (NDK resources that depend on the app)
2. Protection Plans   (NDK policies targeting the app)
3. PVCs/PVs          (Storage resources)
4. Volume Groups     (NDK volume groups)
5. StatefulSet       (Workload controller) ← NEW
6. Service           (Networking) ← NEW
7. Secret            (Credentials) ← NEW
8. Orphaned Pods     (Cleanup stragglers) ← NEW
9. Application CR    (The NDK custom resource)
```

This is the **reverse order** of creation, ensuring clean dependency resolution.

## Usage

### For New Deletions
The fix is **automatic**. When you delete an application through the Admin page:
1. All resources will be properly cleaned up
2. No orphaned StatefulSets, Services, or Secrets will remain
3. Cleanup log will show all deleted resources

### For Existing Orphaned Resources
Run the cleanup script to find and remove orphaned resources from previous deletions:

```bash
./cleanup-statefulset-orphans.sh
```

Follow the interactive prompts to:
1. Select namespace(s) to scan
2. Review found orphaned resources
3. Confirm deletion for each resource

## Verification

After running the cleanup script or deleting an application, verify no orphans remain:

```bash
# Check for orphaned StatefulSets
kubectl get statefulsets -A -l app.kubernetes.io/managed-by=ndk-dashboard

# Check for orphaned headless services
kubectl get services -A -o json | jq -r '.items[] | select(.spec.clusterIP=="None") | "\(.metadata.namespace)/\(.metadata.name)"'

# Check for orphaned secrets
kubectl get secrets -A -o name | grep -- '-secret$'

# Check for orphaned PVCs from StatefulSets
kubectl get pvc -A -o name | grep '^persistentvolumeclaim/data-'
```

All commands should return empty results (or only resources with corresponding applications).

## Benefits

1. **No Resource Leaks** - All created resources are properly cleaned up
2. **Cost Savings** - No orphaned PVCs consuming storage
3. **Clean Cluster** - Easier to manage and audit resources
4. **Proper Lifecycle** - Resources follow correct creation/deletion order
5. **Better UX** - Users can trust that delete means complete removal

## Testing Recommendations

1. **Deploy a test application** through the dashboard
2. **Verify all resources are created**:
   ```bash
   kubectl get statefulsets,services,secrets,pvc -n <namespace> -l app=<app-name>
   ```
3. **Delete the application** through the Admin page
4. **Verify all resources are removed**:
   ```bash
   kubectl get statefulsets,services,secrets,pvc -n <namespace> -l app=<app-name>
   ```
   Should return: `No resources found`

5. **Check cleanup log** in the delete response for confirmation

## Notes

- The fix is **backward compatible** - it gracefully handles missing resources (404 errors)
- All delete operations include proper error handling and logging
- Force delete option still works and removes finalizers when needed
- The cleanup script is **safe** - it prompts before each deletion

## Files Modified

1. **`app.py`** - Updated `manage_application()` DELETE method (lines ~497-614)
2. **`cleanup-statefulset-orphans.sh`** - New interactive cleanup script
3. **`STATEFULSET_CLEANUP_FIX.md`** - This documentation

## Related Scripts

- `cleanup-orphaned.sh` - General orphaned resource cleanup (pods, replica sets, services)
- `cleanup-statefulset-orphans.sh` - Specific to StatefulSet-related orphans
- `deploy.sh` - Deployment script (unchanged, but benefits from proper cleanup)