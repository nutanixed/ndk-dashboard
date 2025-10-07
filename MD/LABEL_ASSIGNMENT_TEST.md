# Label Assignment Feature - Testing Guide

## Feature Overview
The label assignment feature allows users to add custom Kubernetes labels to applications during deployment through the dashboard UI. This eliminates the need for manual kubectl commands and enables immediate integration with label-based Protection Plans.

## Implementation Status
✅ **COMPLETE** - All code changes have been implemented and are ready for testing.

## Quick Test Steps

### Test 1: Deploy Application with Labels

1. **Open the Dashboard**
   - Navigate to http://localhost:5000 (or your dashboard URL)
   - Go to the "Applications" tab

2. **Start Deployment**
   - Click "Deploy MySQL" button
   - Fill in basic information:
     - Name: `test-mysql-labeled`
     - Namespace: `default`
     - Storage Class: Select your storage class
     - Storage Size: `10Gi`

3. **Add Labels**
   - Scroll to the "🏷️ Labels (Optional)" section
   - Click the "environment" suggestion badge (should auto-fill `environment` key)
   - Enter value: `production`
   - Click "➕ Add Label" button
   - Enter key: `tier`, value: `database`
   - Click "backup-policy" suggestion
   - Enter value: `daily`

4. **Deploy**
   - Ensure "Create NDK Application CR" is checked
   - Click "Deploy Application"
   - Wait for success message

5. **Verify Labels**
   ```bash
   kubectl get application.dataservices.nutanix.com test-mysql-labeled -n default --show-labels
   ```
   
   **Expected Output:**
   ```
   NAME                  AGE   ACTIVE   LABELS
   test-mysql-labeled    1m    True     backup-policy=daily,environment=production,tier=database
   ```

6. **Verify in Dashboard**
   - Refresh the Applications tab
   - Click on the application name to view details
   - Labels should be visible in the application metadata

### Test 2: Label Validation

1. **Test Invalid Label Key**
   - Click "Deploy MySQL"
   - Add a label with key: `Environment` (uppercase)
   - Try to deploy
   - **Expected:** Error message about invalid label format

2. **Test Invalid Label Value**
   - Add a label with key: `env`, value: `Production` (uppercase)
   - Try to deploy
   - **Expected:** Error message about invalid label format

3. **Test Valid Formats**
   - Valid keys: `environment`, `app-name`, `tier.level`, `backup_policy`
   - Valid values: `production`, `web-server`, `tier-1`, `daily_backup`

### Test 3: Protection Plan Integration

1. **Deploy Application with Labels** (if not already done)
   ```
   Name: test-mysql-labeled
   Labels:
     - environment=production
     - tier=database
   ```

2. **Create Protection Plan**
   - Go to "Protection Plans" tab
   - Click "Create Protection Plan"
   - Fill in:
     - Name: `production-backup`
     - Namespace: `default`
     - Selector Type: **Label Selector**
     - Label Key: `environment`
     - Label Value: `production`
     - Schedule: `0 2 * * *` (2 AM daily)
     - Retention: `7`
   - Click "Create Protection Plan"

3. **Verify Plan Targets Application**
   ```bash
   kubectl get protectionplan.dataservices.nutanix.com production-backup -n default -o yaml
   ```
   
   Look for:
   ```yaml
   spec:
     selector:
       matchLabels:
         environment: production
   ```

4. **Trigger Backup**
   - In Protection Plans tab, click "Trigger Now" on the `production-backup` plan
   - Wait for snapshot to be created
   - Go to "Snapshots" tab
   - Verify snapshot was created for `test-mysql-labeled`

### Test 4: Deploy Without Labels (Backward Compatibility)

1. **Deploy Application**
   - Click "Deploy MySQL"
   - Fill in basic info: `test-mysql-no-labels`
   - **Do NOT add any labels**
   - Deploy

2. **Verify**
   ```bash
   kubectl get application.dataservices.nutanix.com test-mysql-no-labels -n default --show-labels
   ```
   
   **Expected:** `LABELS` column shows `<none>` - this is correct!

### Test 5: UI Functionality

1. **Add/Remove Labels**
   - Click "Deploy MySQL"
   - Click "➕ Add Label" 3 times
   - Fill in different labels
   - Click "➖ Remove" on the middle label
   - Verify only 2 labels remain

2. **Suggestion Badges**
   - Click each suggestion badge: `environment`, `tier`, `app`, `backup-policy`
   - Verify each adds a new label row with the key pre-filled
   - Verify you can modify the pre-filled values

3. **Empty Labels**
   - Add a label with only a key (no value)
   - Deploy
   - **Expected:** Label is created with empty value (this is valid in Kubernetes)

## Validation Rules

### Label Keys
- **Format:** `/^[a-z0-9]([-a-z0-9_.]*[a-z0-9])?$/`
- **Valid:** `environment`, `app-name`, `tier.level`, `backup_policy`
- **Invalid:** `Environment` (uppercase), `app name` (space), `-app` (starts with dash)

### Label Values
- **Format:** `/^[a-z0-9]([-a-z0-9_.]*[a-z0-9])?$/` or empty
- **Valid:** `production`, `web-server`, `tier-1`, `` (empty)
- **Invalid:** `Production` (uppercase), `web server` (space)

## Common Label Patterns

### Environment Labels
```
environment=production
environment=staging
environment=development
```

### Tier Labels
```
tier=frontend
tier=backend
tier=database
tier=cache
```

### Application Labels
```
app=mysql
app=postgresql
app=mongodb
app=redis
```

### Backup Policy Labels
```
backup-policy=daily
backup-policy=hourly
backup-policy=weekly
backup-policy=critical
```

### Team/Owner Labels
```
team=platform
team=data
owner=john.doe
```

## Troubleshooting

### Labels Not Appearing
1. Check if "Create NDK Application CR" was checked during deployment
2. Verify labels in kubectl: `kubectl get application.dataservices.nutanix.com <name> -n <namespace> -o yaml`
3. Check dashboard logs: `kubectl logs -n ndk-system -l app=ndk-dashboard`

### Protection Plan Not Matching
1. Verify label selector matches exactly (case-sensitive)
2. Check namespace matches between app and protection plan
3. Use `kubectl get application.dataservices.nutanix.com -A --show-labels` to see all labels

### Validation Errors
1. Ensure all keys and values are lowercase
2. No spaces allowed in keys or values
3. Keys and values must start and end with alphanumeric characters
4. Only dashes, underscores, and dots allowed in the middle

## Cleanup

After testing, remove test resources:

```bash
# Delete applications
kubectl delete application.dataservices.nutanix.com test-mysql-labeled -n default
kubectl delete application.dataservices.nutanix.com test-mysql-no-labels -n default

# Delete protection plan
kubectl delete protectionplan.dataservices.nutanix.com production-backup -n default

# Delete snapshots (if any)
kubectl delete snapshot.dataservices.nutanix.com -n default -l environment=production
```

## Success Criteria

✅ Labels can be added during deployment
✅ Label validation prevents invalid formats
✅ Labels appear in kubectl output
✅ Labels appear in dashboard
✅ Protection Plans can target applications by labels
✅ Deploying without labels still works (backward compatible)
✅ UI is intuitive and responsive

## Next Steps

After successful testing:
1. Document recommended labeling strategies for users
2. Consider adding label templates for common patterns
3. Add bulk label editing for existing applications
4. Implement label autocomplete based on existing labels
5. Add label analytics to show label usage across applications