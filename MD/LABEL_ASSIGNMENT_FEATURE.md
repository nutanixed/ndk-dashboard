# Label Assignment Feature

## Overview
Add the ability to assign custom labels to applications during deployment. This enables users to immediately organize applications for label-based Protection Plans without needing to manually apply labels via kubectl.

## Use Cases
1. **During Deployment**: Assign labels like `environment=production`, `tier=database`, `backup-policy=daily` when deploying a new application
2. **Protection Plan Integration**: Labels assigned during deployment can immediately be used to create Protection Plans with label selectors
3. **Organization**: Helps users organize applications from the start using a consistent labeling strategy

## Implementation

### 1. Frontend Changes (index.html)
- Add a new "🏷️ Labels" section to the deployment modal
- Include a dynamic label editor with key-value pairs
- Allow users to add/remove multiple labels
- Provide common label suggestions (environment, tier, app, backup-policy)

### 2. Frontend JavaScript (app.js)
- Collect labels from the form as key-value pairs
- Validate label keys and values (Kubernetes naming rules)
- Send labels in the deployment API request
- Display labels in the applications table

### 3. Backend Changes (app.py)
- Accept labels in the `/api/deploy` endpoint
- Apply labels to the Application CR metadata
- Validate label format (RFC 1123 DNS subdomain names)

## Label Validation Rules
Following Kubernetes label requirements:
- **Keys**: Must be 63 characters or less, alphanumeric, dashes, underscores, dots
- **Values**: Must be 63 characters or less, alphanumeric, dashes, underscores, dots, can be empty
- **Format**: `key=value` or just `key` (empty value)

## UI Design

### Label Editor Component
```
🏷️ Labels (Optional)
┌─────────────────────────────────────────────────┐
│ Label Key          Label Value                  │
│ ┌──────────────┐  ┌──────────────┐  [➖ Remove]│
│ │ environment  │  │ production   │              │
│ └──────────────┘  └──────────────┘              │
│                                                  │
│ ┌──────────────┐  ┌──────────────┐  [➖ Remove]│
│ │ tier         │  │ database     │              │
│ └──────────────┘  └──────────────┘              │
│                                                  │
│ [➕ Add Label]                                   │
└─────────────────────────────────────────────────┘

Common labels: [environment] [tier] [app] [backup-policy]
```

## Example Workflow
1. User clicks "Deploy MySQL"
2. Fills in basic configuration (name, namespace, etc.)
3. In the Labels section, adds:
   - `environment=production`
   - `tier=database`
   - `backup-policy=daily`
4. Deploys the application
5. Application is created with these labels
6. User can immediately create a Protection Plan with selector `environment=production` to backup all production apps

## Benefits
- ✅ No need to use kubectl to add labels after deployment
- ✅ Consistent labeling from the start
- ✅ Immediate integration with Protection Plans
- ✅ Better organization and governance
- ✅ Reduces manual post-deployment steps

## Future Enhancements
- Label templates/presets (e.g., "Production Database", "Dev Environment")
- Label validation against organization policies
- Bulk label editing for existing applications
- Label inheritance from namespaces