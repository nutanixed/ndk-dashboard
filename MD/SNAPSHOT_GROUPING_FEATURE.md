# Snapshot Grouping and Protection Plan Visibility Feature

## Overview
This document describes the comprehensive enhancements made to the NDK Dashboard to improve snapshot visibility and organization, particularly for snapshots created by protection plans.

## Problem Statement
When a protection plan is triggered, it creates snapshots for multiple application replicas. Previously, it was difficult to:
1. Identify which snapshots were created by which protection plan
2. Understand which snapshots were taken together as part of the same execution
3. Filter snapshots by protection plan
4. Distinguish between manual and automated snapshots

Additionally, there was a bug where protection plans would protect ALL applications with a matching name across ALL namespaces, instead of just the application in the same namespace as the protection plan.

## Features Implemented

### 1. Protection Plan Column
- **Added "Protection Plan" column** to the snapshots table
- Shows the name of the protection plan that created each snapshot
- Displays "Manual" for snapshots created manually (not by a protection plan)

### 2. Visual Grouping by Protection Plan
- **Color-coded rows**: Snapshots from the same protection plan have matching background colors
- **Batch indicators**: When multiple snapshots are created together (within 5 seconds), they show a badge with the count (e.g., "📦 3")
- **Visual hierarchy**: Subsequent snapshots in a batch show an indented arrow (↳) to indicate they're part of the same group

### 3. Smart Sorting
- Snapshots are automatically sorted by:
  1. Protection plan name (alphabetically)
  2. Creation time (newest first within each plan)
- Manual snapshots appear at the end
- This keeps related snapshots together for easy identification

### 4. Protection Plan Filter Dropdown
- **New filter dropdown** in the snapshots tab header
- Options include:
  - "All Protection Plans" - shows all snapshots
  - "Manual Snapshots Only" - shows only manually created snapshots
  - Individual protection plan names - shows snapshots from that specific plan
- Filter persists during refresh operations
- Automatically populated with available protection plans

### 5. Batch Detection
- Snapshots created within 5 seconds of each other by the same protection plan are grouped as a "batch"
- First snapshot in batch shows a badge indicating total count
- Helps identify which snapshots were created together during a single protection plan execution

### 6. Bug Fix: Namespace-Scoped Protection Plans
- **Fixed critical bug**: Protection plans now only protect applications in the SAME namespace
- Previously, a protection plan in "default" namespace would protect ALL applications with matching names across ALL namespaces
- Now correctly scoped to namespace boundaries

## Technical Implementation

### Backend Changes (`app.py`)

#### 1. Enhanced Snapshot Data Model
```python
# Added to snapshot response:
'protectionPlan': protection_plan,  # From metadata labels
'creationTime': creation_time       # For batch grouping
```

**Location**: Lines 280-310 in `/api/snapshots` endpoint

#### 2. Fixed Protection Plan Scope
```python
# Changed from list_cluster_custom_object to list_namespaced_custom_object
apps_result = k8s_api.list_namespaced_custom_object(
    group=Config.NDK_API_GROUP,
    version=Config.NDK_API_VERSION,
    namespace=namespace,  # Now scoped to protection plan's namespace
    plural='applications'
)
```

**Location**: Lines 989-995 in `/api/protectionplans/<namespace>/<name>/trigger` endpoint

### Frontend Changes

#### 1. HTML Structure (`templates/index.html`)
- Added protection plan filter dropdown to snapshots tab header
- Positioned alongside existing search input

**Location**: Lines 140-152

#### 2. JavaScript State Management (`static/app.js`)
- Added `currentProtectionPlanFilter` state variable
- Initialized protection plan filter event handlers

**Location**: Lines 13, 21, 107-150

#### 3. Filter Logic
```javascript
// Apply protection plan filter for snapshots
if (tabName === 'snapshots' && currentProtectionPlanFilter !== 'all') {
    if (currentProtectionPlanFilter === 'manual') {
        data = data.filter(snap => !snap.protectionPlan);
    } else {
        data = data.filter(snap => snap.protectionPlan === currentProtectionPlanFilter);
    }
}
```

**Location**: Lines 179-188

#### 4. Enhanced Snapshot Rendering
The `renderSnapshots()` function now includes:
- Sorting by protection plan and creation time
- Batch detection (5-second window)
- Color assignment per protection plan
- Visual indicators (badges, arrows)
- Row background colors

**Location**: Lines 434-565

## User Experience Improvements

### Before
- Snapshots listed in random order
- No indication of which protection plan created which snapshot
- Difficult to identify related snapshots
- Protection plans could accidentally protect wrong applications

### After
- Snapshots clearly organized by protection plan
- Color-coded visual grouping
- Batch indicators show related snapshots
- Easy filtering by protection plan
- Protection plans correctly scoped to namespace

## Visual Design

### Color Palette
Six distinct pastel colors rotate for different protection plans:
- Blue: `#e3f2fd`
- Purple: `#f3e5f5`
- Green: `#e8f5e9`
- Orange: `#fff3e0`
- Pink: `#fce4ec`
- Teal: `#e0f2f1`

### Batch Indicator Badge
- Background: `#1976d2` (Material Blue)
- Text: White
- Icon: 📦 (package emoji)
- Format: "📦 3" (shows count)

### Visual Hierarchy
```
Protection Plan A (Blue background)
  ├─ snapshot-1 (with badge "📦 3")
  ├─ ↳ snapshot-2
  └─ ↳ snapshot-3

Protection Plan B (Purple background)
  └─ snapshot-4 (single snapshot, no badge)

Manual (No background)
  └─ manual-snapshot-1
```

## Testing Recommendations

1. **Create Protection Plan**: Create a protection plan for an application
2. **Trigger Plan**: Manually trigger the protection plan
3. **Verify Grouping**: Check that all snapshots appear together with same color
4. **Check Batch Indicator**: Verify badge shows correct count
5. **Test Filter**: Use dropdown to filter by protection plan
6. **Test Manual Filter**: Create manual snapshot and filter to "Manual Snapshots Only"
7. **Test Namespace Scope**: Create apps with same name in different namespaces, verify protection plan only protects correct namespace

## Files Modified

1. `/home/nutanix/dev/ndk-dashboard/app.py`
   - Lines 280-310: Added protectionPlan and creationTime to snapshot data
   - Lines 989-995: Fixed namespace scoping for protection plan triggers

2. `/home/nutanix/dev/ndk-dashboard/templates/index.html`
   - Lines 140-152: Added protection plan filter dropdown

3. `/home/nutanix/dev/ndk-dashboard/static/app.js`
   - Line 13: Added currentProtectionPlanFilter state
   - Line 21: Added filter initialization
   - Lines 107-150: Added protection plan filter functions
   - Lines 179-188: Added filter logic
   - Lines 330-332: Added filter population on snapshot load
   - Lines 434-565: Completely rewrote renderSnapshots() with grouping logic

## Future Enhancements

Potential improvements for future iterations:

1. **Collapsible Groups**: Make protection plan groups collapsible/expandable
2. **Batch Actions**: Allow selecting entire batch at once
3. **Timeline View**: Show snapshots on a timeline grouped by execution
4. **Protection Plan Details**: Click protection plan name to see plan details
5. **Batch Restore**: Restore all snapshots from a batch together
6. **Export/Report**: Generate reports showing snapshot coverage by protection plan

## Compatibility

- **Kubernetes**: Compatible with NDK API v1alpha1
- **Browsers**: Modern browsers with ES6 support
- **NDK Version**: Tested with current NDK API version

## Performance Considerations

- **Sorting**: O(n log n) for snapshot sorting
- **Grouping**: O(n) single pass through sorted data
- **Rendering**: Efficient template string generation
- **Filtering**: O(n) filter operations on client-side data

## Conclusion

These enhancements significantly improve the user experience when working with snapshots, especially those created by protection plans. The visual grouping, filtering, and proper namespace scoping make it much easier to understand and manage snapshot lifecycle in the NDK Dashboard.