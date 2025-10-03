# NDK Dashboard - Application Deployment Guide

## Overview

The NDK Dashboard now includes a comprehensive application deployment interface that allows you to deploy stateful applications with built-in Nutanix Data Services for Kubernetes (NDK) protection capabilities.

## Features

### 🚀 One-Click Deployment
Deploy popular stateful applications with pre-configured templates:
- **MySQL** - Relational database
- **PostgreSQL** - Advanced relational database
- **MongoDB** - Document database
- **Redis** - In-memory data store
- **Elasticsearch** - Search and analytics engine
- **Cassandra** - Distributed NoSQL database

### 🛡️ Integrated NDK Protection
- Automatic creation of NDK Application Custom Resources
- Optional Protection Plan setup with configurable schedules
- Crash-consistent snapshots across all volumes
- Automated retention policies

### ⚙️ Flexible Configuration
- Custom application names and namespaces
- Configurable replica counts
- Storage class and size selection
- Database-specific settings (passwords, database names)
- Auto-generated secure passwords

## Using the Deployment Interface

### Step 1: Access the Deploy Tab

1. Log in to the NDK Dashboard
2. Click on the **🚀 Deploy** tab in the navigation bar
3. Browse the available application templates

### Step 2: Select an Application Template

Click on any application card to open the deployment configuration modal. Each template includes:
- Pre-configured Docker image
- Default port settings
- Recommended storage configuration
- Application-specific environment variables

### Step 3: Configure Basic Settings

**Application Name**
- Must be unique within the namespace
- Used for StatefulSet, Service, and NDK Application CR names
- Example: `my-postgres`, `prod-mysql`

**Namespace**
- Kubernetes namespace for the deployment
- Will be created automatically if it doesn't exist
- Example: `databases`, `production`

**Replicas**
- Number of StatefulSet replicas
- Default: 1
- Range: 1-10

### Step 4: Configure Storage

**Storage Class**
- Select from available Kubernetes storage classes
- Recommended: `nutanix-volume` for Nutanix HCI
- Each replica gets its own PersistentVolumeClaim

**Storage Size**
- Size per replica (e.g., `10Gi`, `50Gi`, `100Gi`)
- Consider your data growth requirements
- Nutanix provides thin provisioning

### Step 5: Application Configuration

**Password** (Optional)
- Leave empty to auto-generate a secure 16-character password
- Or provide your own password
- Stored securely in a Kubernetes Secret

**Database Name** (For MySQL/PostgreSQL)
- Initial database to create
- Optional for most applications

### Step 6: NDK Protection Settings

**Create NDK Application**
- ✅ Enabled: Creates an NDK Application CR for data protection
- Allows taking snapshots and creating protection plans
- Required for automated protection

**Create Protection Plan** (Requires NDK Application)
- ✅ Enabled: Automatically creates an AppProtectionPlan
- **Schedule**: Cron expression for snapshot frequency
  - `0 2 * * *` - Daily at 2 AM
  - `0 */6 * * *` - Every 6 hours
  - `0 0 * * 0` - Weekly on Sunday
- **Retention**: How long to keep snapshots
  - `7d` - 7 days
  - `30d` - 30 days
  - `90d` - 90 days

### Step 7: Deploy

1. Review all settings
2. Click **Deploy Application**
3. Wait for the deployment to complete
4. Note the generated password (if auto-generated)
5. The dashboard will automatically refresh and switch to the Applications tab

## What Gets Created

When you deploy an application, the following Kubernetes resources are created:

### 1. Namespace
```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: <namespace>
```

### 2. Secret (Credentials)
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: <app-name>-credentials
  namespace: <namespace>
type: Opaque
data:
  password: <base64-encoded-password>
  database: <base64-encoded-database-name>  # If applicable
```

### 3. StatefulSet
```yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: <app-name>
  namespace: <namespace>
  labels:
    app: <app-name>
    app.kubernetes.io/name: <app-type>
    app.kubernetes.io/managed-by: ndk-dashboard
spec:
  serviceName: <app-name>
  replicas: <replicas>
  selector:
    matchLabels:
      app: <app-name>
  template:
    metadata:
      labels:
        app: <app-name>
        app.kubernetes.io/name: <app-type>
    spec:
      containers:
      - name: <app-type>
        image: <docker-image>
        ports:
        - containerPort: <port>
          name: <app-type>
        env:
        - name: <PASSWORD_ENV_VAR>
          valueFrom:
            secretKeyRef:
              name: <app-name>-credentials
              key: password
        volumeMounts:
        - name: data
          mountPath: <data-path>
  volumeClaimTemplates:
  - metadata:
      name: data
    spec:
      accessModes: ["ReadWriteOnce"]
      storageClassName: <storage-class>
      resources:
        requests:
          storage: <storage-size>
```

### 4. Service (Headless)
```yaml
apiVersion: v1
kind: Service
metadata:
  name: <app-name>
  namespace: <namespace>
spec:
  ports:
  - port: <port>
    name: <app-type>
  clusterIP: None
  selector:
    app: <app-name>
```

### 5. NDK Application CR (If enabled)
```yaml
apiVersion: ndk.nutanix.com/v1alpha1
kind: Application
metadata:
  name: <app-name>
  namespace: <namespace>
spec:
  selector:
    matchLabels:
      app: <app-name>
```

### 6. AppProtectionPlan (If enabled)
```yaml
apiVersion: ndk.nutanix.com/v1alpha1
kind: AppProtectionPlan
metadata:
  name: <app-name>-protection
  namespace: <namespace>
spec:
  target:
    applicationRef:
      name: <app-name>
  schedule:
    cron: <schedule>
  retention:
    expiresAfter: <retention>
```

## Application-Specific Details

### MySQL
- **Image**: `mysql:8.0`
- **Port**: 3306
- **Data Path**: `/var/lib/mysql`
- **Environment Variables**:
  - `MYSQL_ROOT_PASSWORD`: Root password from secret
  - `MYSQL_DATABASE`: Initial database name (optional)

### PostgreSQL
- **Image**: `postgres:15`
- **Port**: 5432
- **Data Path**: `/var/lib/postgresql/data`
- **Environment Variables**:
  - `POSTGRES_PASSWORD`: Password from secret
  - `POSTGRES_DB`: Initial database name (optional)

### MongoDB
- **Image**: `mongo:7`
- **Port**: 27017
- **Data Path**: `/data/db`
- **Environment Variables**:
  - `MONGO_INITDB_ROOT_USERNAME`: `admin`
  - `MONGO_INITDB_ROOT_PASSWORD`: Password from secret

### Redis
- **Image**: `redis:7`
- **Port**: 6379
- **Data Path**: `/data`
- **Environment Variables**:
  - `REDIS_PASSWORD`: Password from secret

### Elasticsearch
- **Image**: `elasticsearch:8.11.0`
- **Port**: 9200
- **Data Path**: `/usr/share/elasticsearch/data`
- **Environment Variables**:
  - `ELASTIC_PASSWORD`: Password from secret
  - `discovery.type`: `single-node`
  - `xpack.security.enabled`: `true`

### Cassandra
- **Image**: `cassandra:4`
- **Port**: 9042
- **Data Path**: `/var/lib/cassandra`
- **Environment Variables**:
  - `CASSANDRA_PASSWORD`: Password from secret

## Connecting to Deployed Applications

### From Within the Cluster

Applications are accessible via their service name:

```bash
# MySQL
mysql -h <app-name>.<namespace>.svc.cluster.local -u root -p

# PostgreSQL
psql -h <app-name>.<namespace>.svc.cluster.local -U postgres

# MongoDB
mongosh mongodb://admin:<password>@<app-name>.<namespace>.svc.cluster.local:27017

# Redis
redis-cli -h <app-name>.<namespace>.svc.cluster.local -a <password>
```

### From Outside the Cluster

Use `kubectl port-forward`:

```bash
# Forward local port to the application
kubectl port-forward -n <namespace> svc/<app-name> <local-port>:<app-port>

# Example for PostgreSQL
kubectl port-forward -n test-db svc/my-postgres 5432:5432

# Then connect locally
psql -h localhost -U postgres
```

## Verifying Deployments

### Check StatefulSet Status
```bash
kubectl get statefulsets -n <namespace>
kubectl describe statefulset <app-name> -n <namespace>
```

### Check Pod Status
```bash
kubectl get pods -n <namespace>
kubectl logs <app-name>-0 -n <namespace>
```

### Check PersistentVolumeClaims
```bash
kubectl get pvc -n <namespace>
```

### Check NDK Application
```bash
kubectl get applications.ndk.nutanix.com -n <namespace>
kubectl describe application <app-name> -n <namespace>
```

### Check Protection Plan
```bash
kubectl get appprotectionplans.ndk.nutanix.com -n <namespace>
kubectl describe appprotectionplan <app-name>-protection -n <namespace>
```

### Check Snapshots (After Protection Plan Runs)
```bash
kubectl get applicationsnapshots.ndk.nutanix.com -n <namespace>
```

## API Reference

### Endpoint
```
POST /api/deploy
```

### Request Body
```json
{
  "appType": "postgresql",
  "appName": "my-postgres",
  "namespace": "databases",
  "replicas": 1,
  "storageClass": "nutanix-volume",
  "storageSize": "10Gi",
  "password": null,
  "databaseName": "myapp",
  "dockerImage": "postgres:15",
  "port": 5432,
  "createNdkApp": true,
  "createProtectionPlan": true,
  "schedule": "0 2 * * *",
  "retention": "7d"
}
```

### Response (Success)
```json
{
  "success": true,
  "message": "Application my-postgres deployed successfully",
  "deployment": {
    "name": "my-postgres",
    "namespace": "databases",
    "type": "postgresql",
    "replicas": 1,
    "password": "aB3dE5fG7hI9jK1l",
    "ndkEnabled": true,
    "protectionEnabled": true
  }
}
```

### Response (Error)
```json
{
  "error": "Failed to deploy application: <error message>"
}
```

## Best Practices

### 1. Namespace Organization
- Use separate namespaces for different environments (dev, staging, prod)
- Group related applications in the same namespace
- Example: `prod-databases`, `dev-apps`

### 2. Storage Planning
- Start with conservative storage sizes
- Monitor usage and resize if needed
- Use Nutanix storage classes for best performance

### 3. Protection Strategy
- Enable NDK protection for all production databases
- Use frequent snapshots for critical data (every 6 hours)
- Adjust retention based on compliance requirements
- Test restore procedures regularly

### 4. Security
- Use strong passwords for production deployments
- Store generated passwords securely (password manager)
- Rotate passwords periodically
- Use Kubernetes RBAC to control access

### 5. Monitoring
- Check application logs regularly
- Monitor PVC usage
- Verify protection plan execution
- Review snapshot status

## Troubleshooting

### Deployment Fails with "Storage Class Not Found"
- Verify storage class exists: `kubectl get storageclass`
- Use the correct storage class name (case-sensitive)
- Ensure Nutanix CSI driver is installed

### Pod Stuck in Pending State
- Check PVC status: `kubectl get pvc -n <namespace>`
- Verify storage class can provision volumes
- Check node resources: `kubectl describe node`

### Application Not Starting
- Check pod logs: `kubectl logs <app-name>-0 -n <namespace>`
- Verify secret was created: `kubectl get secret -n <namespace>`
- Check environment variables: `kubectl describe pod <app-name>-0 -n <namespace>`

### NDK Application Not Created
- Verify NDK is installed: `kubectl get crd | grep ndk`
- Check API group and version in config
- Review dashboard logs for errors

### Protection Plan Not Running
- Check plan status: `kubectl describe appprotectionplan <name> -n <namespace>`
- Verify schedule syntax (cron format)
- Ensure storage cluster is configured
- Check NDK operator logs

## Extending the Deployment System

### Adding New Application Templates

Edit `/home/nutanix/dev/ndk-dashboard/static/app.js` and add to `APP_TEMPLATES`:

```javascript
'newapp': {
    name: 'New Application',
    image: 'newapp:latest',
    port: 8080,
    icon: '🆕',
    description: 'Description of the application',
    requiresDatabase: false
}
```

Update the backend in `/home/nutanix/dev/ndk-dashboard/app.py` to handle the new app type's environment variables and volume mounts.

## Support

For issues or questions:
1. Check the dashboard logs
2. Review Kubernetes events: `kubectl get events -n <namespace>`
3. Verify NDK operator status
4. Consult Nutanix NDK documentation

## Summary

The NDK Dashboard deployment interface provides a streamlined way to deploy stateful applications with enterprise-grade data protection. By combining Kubernetes StatefulSets with Nutanix NDK, you get:

- ✅ Automated deployment of popular databases
- ✅ Crash-consistent snapshots
- ✅ Scheduled protection plans
- ✅ Easy restore capabilities
- ✅ Integration with Nutanix storage
- ✅ Production-ready configurations

Start deploying protected applications today! 🚀