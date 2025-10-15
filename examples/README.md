# NDK Dashboard Deployment Examples

This directory contains example YAML manifests for deploying stateful applications with NDK data protection.

## Available Examples

### MySQL (`mysql-deployment.yaml`)
- **Image**: `mysql:8.0`
- **Replicas**: 3
- **Storage**: 10Gi
- **Backup Schedule**: Daily at 2 AM
- **Retention**: 7 snapshots
- **Custom Labels**: `environment: dev`

### PostgreSQL (`postgresql-deployment.yaml`)
- **Image**: `postgres:15`
- **Replicas**: 3
- **Storage**: 20Gi
- **Backup Schedule**: Every 6 hours
- **Retention**: 14 snapshots
- **Custom Labels**: `environment: production`

### MongoDB (`mongodb-deployment.yaml`)
- **Image**: `mongo:7.0`
- **Replicas**: 3
- **Storage**: 50Gi
- **Backup Schedule**: Daily at 3 AM
- **Retention**: 10 snapshots
- **Custom Labels**: `tier: database`

### Elasticsearch (`elasticsearch-deployment.yaml`)
- **Image**: `docker.elastic.co/elasticsearch/elasticsearch:8.11.0`
- **Replicas**: 3
- **Storage**: 100Gi
- **Backup Schedule**: Daily at 1 AM
- **Retention**: 5 snapshots
- **Custom Labels**: `component: search`

## What Each Deployment Includes

Each example creates the following Kubernetes resources:

1. **Namespace** - Isolated environment for the application
2. **Secret** - Stores credentials securely
3. **Service** - Headless service for StatefulSet
4. **StatefulSet** - Manages the stateful application pods
5. **Application CR** - NDK custom resource that enables data services
6. **JobScheduler** - Defines the backup schedule (cron)
7. **ProtectionPlan** - Defines retention policy and backup settings
8. **AppProtectionPlan** - Links the application to the protection plan

## How to Use

1. **Download** the YAML file for your desired application
2. **Customize** the values:
   - Change `namespace` from `ndk-dev` to your preferred namespace
   - Update `password` in the Secret
   - Adjust `replicas`, `storage`, and `storageClassName` as needed
   - Modify `cronSchedule` for backup timing
   - Change `retentionCount` for how many snapshots to keep
3. **Deploy** using kubectl:
   ```bash
   kubectl apply -f mysql-deployment.yaml
   ```

## Customization Tips

### Storage Class
Replace `nutanix-volume` with your cluster's storage class:
```bash
kubectl get storageclass
```

### Backup Schedules (Cron Format)
- `"0 2 * * *"` - Daily at 2 AM
- `"0 */6 * * *"` - Every 6 hours
- `"0 0 * * 0"` - Weekly on Sunday at midnight
- `"0 0 1 * *"` - Monthly on the 1st at midnight

### Retention Policy
You can use either:
- `retentionCount: 7` - Keep last 7 snapshots
- `maxAge: "30d"` - Keep snapshots for 30 days

## Verification

After deployment, verify resources:

```bash
# Check all resources
kubectl get all -n ndk-dev

# Check NDK Application
kubectl get applications -n ndk-dev

# Check Protection Plan
kubectl get protectionplans -n ndk-dev

# Check App Protection Plan
kubectl get appprotectionplans -n ndk-dev

# Check snapshots (after first backup runs)
kubectl get applicationsnapshots -n ndk-dev
```

## Notes

- All examples use `by-name` selection mode for protection plans
- The NDK operator must be installed in your cluster
- Storage class must support dynamic provisioning
- Adjust resource requests/limits based on your workload requirements
