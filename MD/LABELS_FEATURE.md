# Application Labels Feature

## Overview
Added the ability to view Kubernetes labels on applications in the NDK Dashboard. This is critical for understanding which applications will be selected by Protection Plans, since Protection Plans use label selectors to target applications.

## Problem Solved
Previously, there was **no way to see what labels your applications have** in the dashboard. This made it difficult to:
- Know which labels to use when creating Protection Plans
- Understand why a Protection Plan might not be selecting your applications
- Verify that applications have the correct labels for backup policies

## Changes Made

### 1. Backend Changes (`app.py`)
**Lines 164-180**: Added label extraction to the `/api/applications` endpoint

```python
# Extract labels (excluding system labels)
all_labels = metadata.get('labels', {})
# Filter out common system labels
system_label_prefixes = ['kubectl.kubernetes.io/', 'kubernetes.io/', 'k8s.io/']
user_labels = {k: v for k, v in all_labels.items() 
              if not any(k.startswith(prefix) for prefix in system_label_prefixes)}

applications.append({
    'name': metadata.get('name', 'Unknown'),
    'namespace': namespace,
    'created': metadata.get('creationTimestamp', ''),
    'selector': spec.get('applicationSelector', {}),
    'state': state,
    'message': message,
    'lastSnapshot': status.get('lastSnapshotTime', 'Never'),
    'labels': user_labels  # ← NEW: Include user labels
})
```

**Key Features:**
- Extracts all labels from application metadata
- Filters out system labels (kubernetes.io/*, k8s.io/*, kubectl.kubernetes.io/*)
- Returns only user-defined labels that are relevant for Protection Plans

### 2. Frontend Changes (`app.js`)

#### Table Header (Lines 450-461)
Added a new "Labels" column to the Applications table:

```javascript
<th style="width: 18%;">Labels</th>
```

**Updated Column Widths:**
- Checkbox: 3%
- Name: 20% (was 25%)
- Namespace: 12% (was 15%)
- Status: 10% (was 12%)
- **Labels: 18% (NEW)**
- Last Snapshot: 12% (was 15%)
- Created: 12% (was 15%)
- Actions: 13% (was 15%)

#### Table Body (Lines 463-498)
Added label rendering logic:

```javascript
const appLabels = app.labels || {};

// Format labels for display
const labelsHtml = Object.keys(appLabels).length > 0 
    ? Object.entries(appLabels)
        .map(([key, value]) => `<span class="label-badge" title="${escapeHtml(key)}=${escapeHtml(value)}">${escapeHtml(key)}=${escapeHtml(value)}</span>`)
        .join(' ')
    : '<span class="text-muted">No labels</span>';
```

**Features:**
- Displays each label as a styled badge (e.g., `app=mysql`, `environment=production`)
- Shows "No labels" if the application has no user-defined labels
- Each badge has a tooltip showing the full label key=value
- Multiple labels are displayed side-by-side with spacing

### 3. CSS Styling (`styles.css`)

#### Label Badge Styles (Lines 517-536)
Added professional styling for label badges:

```css
.label-badge {
    display: inline-block;
    padding: 0.25rem 0.625rem;
    margin: 0.125rem;
    background: var(--neutral-100);
    color: var(--text-secondary);
    border: 1px solid var(--border-light);
    border-radius: 4px;
    font-size: 0.75rem;
    font-weight: 500;
    font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
    white-space: nowrap;
    cursor: help;
}

.label-badge:hover {
    background: var(--neutral-200);
    border-color: var(--border-medium);
}
```

**Design Features:**
- Monospace font for technical key=value pairs
- Light gray background with subtle border
- Hover effect for better interactivity
- Help cursor to indicate tooltip availability
- Compact sizing to fit multiple labels

## Example: ek-mysql Application

### Current State
Based on the Kubernetes inspection, `ek-mysql` currently has:
- **No user-defined labels** (only system metadata)
- This means it **cannot be selected by label-based Protection Plans**

### What You'll See in the Dashboard
```
Name      | Namespace       | Status | Labels     | Last Snapshot | Created
----------|-----------------|--------|------------|---------------|----------
ek-mysql  | mysql-namespace | Active | No labels  | Never         | 31h ago
```

### How to Add Labels
To make `ek-mysql` selectable by Protection Plans, you need to add labels:

```bash
# Add labels to the application
kubectl label application.dataservices.nutanix.com ek-mysql \
  -n mysql-namespace \
  app=mysql \
  environment=production \
  tier=database
```

After adding labels, the dashboard will show:
```
Labels: app=mysql environment=production tier=database
```

Then you can create a Protection Plan with:
- **Label Selector**: `app` = `mysql` (will backup all MySQL apps)
- **Label Selector**: `environment` = `production` (will backup all production apps)
- **Application Name**: `ek-mysql` (will backup only this specific app)

## Benefits

### 1. **Visibility**
- See at a glance which applications have labels
- Identify applications that need labels for backup policies

### 2. **Protection Plan Configuration**
- Know exactly which label keys and values to use
- Understand which applications will be selected by a given selector

### 3. **Troubleshooting**
- Quickly identify why a Protection Plan isn't selecting an application
- Verify that labels match your backup strategy

### 4. **Best Practices**
- Encourages proper labeling of applications
- Makes label-based organization visible and actionable

## Testing

### Test Case 1: Application with No Labels
**Expected:** Shows "No labels" in gray text

### Test Case 2: Application with One Label
**Expected:** Shows single badge like `app=mysql`

### Test Case 3: Application with Multiple Labels
**Expected:** Shows multiple badges side-by-side:
```
app=mysql environment=production tier=database
```

### Test Case 4: Long Label Values
**Expected:** Badges wrap to next line if needed, maintaining readability

### Test Case 5: Hover Interaction
**Expected:** Badge background darkens on hover, cursor shows help icon

## Files Modified

1. **`/home/nutanix/dev/ndk-dashboard/app.py`**
   - Added label extraction and filtering logic
   - Returns `labels` field in application data

2. **`/home/nutanix/dev/ndk-dashboard/static/app.js`**
   - Added "Labels" column to table header
   - Added label rendering logic to table body
   - Adjusted column widths for better layout

3. **`/home/nutanix/dev/ndk-dashboard/static/styles.css`**
   - Added `.label-badge` styling
   - Added hover effects for labels

## Next Steps

### For Users
1. **Review your applications** - Check which ones have labels
2. **Add labels strategically** - Use consistent naming (e.g., `app`, `environment`, `tier`)
3. **Create Protection Plans** - Use label selectors to group applications for backup

### Recommended Label Schema
```yaml
app: <application-type>           # e.g., mysql, postgresql, mongodb
environment: <env-name>            # e.g., production, staging, dev
tier: <tier-name>                  # e.g., database, frontend, backend
owner: <team-name>                 # e.g., platform-team, data-team
backup-policy: <policy-name>      # e.g., daily, weekly, critical
```

### Example Label Strategy
```bash
# Production databases - daily backups
kubectl label app ek-mysql -n mysql-namespace \
  app=mysql environment=production tier=database backup-policy=daily

# Development databases - weekly backups
kubectl label app dev-postgres -n dev-namespace \
  app=postgresql environment=dev tier=database backup-policy=weekly
```

Then create Protection Plans:
- **Daily Production Backup**: Label selector `backup-policy=daily`
- **Weekly Dev Backup**: Label selector `backup-policy=weekly`
- **All MySQL Backup**: Label selector `app=mysql`

## Compatibility
- ✅ Works with existing applications (shows "No labels" if none exist)
- ✅ No breaking changes to API or data structures
- ✅ Backward compatible with existing Protection Plans
- ✅ System labels are filtered out automatically

## Performance
- Minimal impact: Labels are already fetched from Kubernetes API
- No additional API calls required
- Efficient filtering of system labels
- Lightweight rendering in the UI