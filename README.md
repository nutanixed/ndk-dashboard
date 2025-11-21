# NDK Dashboard

A comprehensive web-based dashboard for managing Nutanix Data Services for Kubernetes (NDK) resources. Built with Flask and the Kubernetes Python client, this dashboard provides an intuitive interface for managing applications, snapshots, protection plans, and storage clusters.

![Version](https://img.shields.io/badge/version-3.5.1-blue.svg)
![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.12-blue.svg)
![Flask](https://img.shields.io/badge/flask-3.0.0-green.svg)
![Kubernetes](https://img.shields.io/badge/kubernetes-28.1.0-blue.svg)

## 🌟 Features

### Core Functionality
- **Application Management**: View, create, and delete NDK Applications with detailed status information
- **Snapshot Management**: Create, restore, and delete application snapshots
- **Protection Plans**: Manage automated backup schedules and retention policies
- **Storage Clusters**: Monitor and manage Nutanix storage cluster connections
- **Resources Management**: Browse and manage Kubernetes resources with filtering and search
- **Deployment Tools**: Deploy sample applications (MySQL, PostgreSQL) with pre-configured templates
- **Multi-Pod Database Configuration**: Configure different database connection parameters for multiple pods
- **ConfigMap-Based Settings**: Persistent configuration storage in Kubernetes ConfigMap with automatic creation

### Dashboard Features
- **Real-time Statistics**: Live counts of applications, snapshots, storage clusters, and protection plans
- **Interactive UI**: Modern, responsive interface with real-time updates
- **Authentication**: Secure login system with session management
- **Admin Panel**: Dedicated admin interface for advanced operations
- **Health Monitoring**: Built-in health check endpoints for monitoring

### Technical Features
- **Modular Architecture**: Flask application factory pattern with blueprints
- **Service Layer**: Separated business logic from route handlers
- **Caching**: Intelligent caching system to reduce Kubernetes API calls
- **Error Handling**: Comprehensive error handling with custom error pages
- **In-Cluster Support**: Runs both locally and inside Kubernetes clusters
- **ConfigMap Integration**: Persistent settings storage with Kubernetes ConfigMap and file fallback
- **Public API Endpoints**: Unauthenticated endpoints for cross-pod configuration retrieval
- **Dynamic Configuration**: Fully configurable database connection parameters (host, username, database name, password)

## 📋 Quick Links

- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [API Endpoints](#api-endpoints)
- [Architecture](#architecture)
- [Deployment](#deployment)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)

## 🔧 Prerequisites

### Required
- **Python**: 3.12 or higher
- **Kubernetes Cluster**: Access to a cluster with NDK installed
- **kubectl**: Configured with cluster access
- **NDK**: Nutanix Data Services for Kubernetes v2.x or higher

### Optional
- **Git**: For cloning the repository
- **Virtual Environment**: Recommended for local development

## 📦 Installation

### Local Development Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/nutanixed/ndk-dashboard.git
   cd ndk-dashboard
   ```

2. **Create a virtual environment**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**
   ```bash
   cp .env.example .env  # If available
   # Edit .env with your settings
   ```

5. **Verify kubectl access**
   ```bash
   kubectl cluster-info
   kubectl get storageclusters
   ```

### Quick Start

Use the provided startup script:

```bash
chmod +x start-local.sh
./start-local.sh
```

The dashboard will be available at: http://localhost:5000

## ⚙️ Configuration

### Environment Variables

Create a `.env` file in the project root or set environment variables:

```bash
# Flask Configuration
SECRET_KEY=your-secret-key-here
FLASK_ENV=development  # or 'production'

# Authentication
DASHBOARD_USERNAME=nutanix
DASHBOARD_PASSWORD=Nutanix/4u!

# Session Configuration
SESSION_TIMEOUT_HOURS=24

# Kubernetes Configuration
IN_CLUSTER=false  # Set to 'true' when running in Kubernetes

# Cache Configuration
CACHE_TTL=30  # Cache time-to-live in seconds
```



### Security Considerations

⚠️ **Important**: Change default credentials in production!

```bash
# Generate a secure secret key
python3 -c "import secrets; print(secrets.token_hex(32))"

# Set strong credentials
export DASHBOARD_USERNAME=your_username
export DASHBOARD_PASSWORD=your_strong_password
```

### ConfigMap Integration

The dashboard stores task app database settings in a Kubernetes ConfigMap for cluster-wide access. The ConfigMap is automatically created when you save settings through the admin panel.

**ConfigMap Details:**
- **Name**: `ndk-dashboard-settings`
- **Namespace**: `ndk-dev`
- **Storage**: Primary persistence layer for settings
- **Fallback**: Local `instance/settings.json` file if ConfigMap is unavailable

**Example ConfigMap:**
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: ndk-dashboard-settings
  namespace: ndk-dev
data:
  settings.json: |
    {
      "taskapp_db": {
        "pod": "task-web-app",
        "host": "mysql-0.mysql.ndk-dev.svc.cluster.local",
        "username": "root",
        "database_name": "mydb",
        "password": "your-db-password"
      }
    }
```

**Accessing Settings from Other Pods:**

Any pod in the cluster can fetch database settings via the public API:

```python
import requests

response = requests.get(
    'http://ndk-dashboard:5000/api/public/taskapp-db-settings/task-web-app'
)

if response.status_code == 200:
    settings = response.json()['settings']
    db_host = settings['host']
    db_user = settings['username']
    db_name = settings['database_name']
    db_pass = settings['password']
```

See `examples/README.md` for complete configuration examples and deployment instructions.

## 🚀 Usage

### Starting the Dashboard

**Development Mode:**
```bash
./start-local.sh
# Or manually:
python3 run.py
```

**Production Mode:**
```bash
export FLASK_ENV=production
gunicorn -w 4 -b 0.0.0.0:5000 run:app
```

### Accessing the Dashboard

1. Open your browser to: http://localhost:5000
2. Login with your credentials (default: nutanix / Nutanix/4u!)
3. Navigate through the dashboard:
   - **Home**: View statistics and manage resources
   - **Admin**: Advanced operations and deployment tools



## 📡 API Endpoints

### Authentication

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/login` | Login page |
| POST | `/login` | Authenticate user |
| GET | `/logout` | Logout and clear session |

### Dashboard

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Main dashboard page |
| GET | `/admin` | Admin panel |
| GET | `/health` | Health check endpoint |
| GET | `/api/stats` | Dashboard statistics |

### Applications

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/applications` | List all applications |
| GET | `/api/applications/<namespace>/<name>` | Get application details |
| DELETE | `/api/applications/<namespace>/<name>` | Delete application |
| POST | `/api/applications/<namespace>/<name>/labels` | Add label to application |
| DELETE | `/api/applications/<namespace>/<name>/labels/<key>` | Remove label from application |

### Snapshots

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/snapshots` | List all snapshots |
| GET | `/api/snapshots/<namespace>/<name>` | Get snapshot details |
| POST | `/api/snapshots` | Create new snapshot |
| DELETE | `/api/snapshots/<namespace>/<name>` | Delete snapshot |
| POST | `/api/snapshots/<namespace>/<name>/restore` | Restore snapshot |

### Protection Plans

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/protectionplans` | List all protection plans |
| GET | `/api/protectionplans/<namespace>/<name>` | Get protection plan details |
| POST | `/api/protectionplans` | Create protection plan |
| DELETE | `/api/protectionplans/<namespace>/<name>` | Delete protection plan |

### Storage Clusters

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/storageclusters` | List all storage clusters |
| GET | `/api/storageclusters/<name>` | Get storage cluster details |

### Deployment

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/deploy/mysql` | Deploy MySQL application |
| POST | `/api/deploy/postgresql` | Deploy PostgreSQL application |

### Task App Database Configuration

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/taskapp-db/settings` | Get task app database settings (authenticated) |
| POST | `/api/taskapp-db/settings` | Save task app database settings (authenticated) |
| GET | `/api/taskapp-db/status` | Get database connection status |
| POST | `/api/taskapp-db/init` | Initialize database |
| POST | `/api/taskapp-db/clear` | Clear database |
| GET | `/api/public/taskapp-db-settings/<pod_name>` | Get database settings for a specific pod (public, unauthenticated) |

### Quick API Examples

All authenticated endpoints require a session cookie. Examples:

```bash
# List applications
curl -X GET http://localhost:5000/api/applications \
  -H "Cookie: session=your-session-cookie"

# Create snapshot
curl -X POST http://localhost:5000/api/snapshots \
  -H "Content-Type: application/json" \
  -H "Cookie: session=your-session-cookie" \
  -d '{"appNamespace": "default", "appName": "mysql-app", "snapshotName": "backup-001"}'

# Delete application
curl -X DELETE "http://localhost:5000/api/applications/default/mysql-app?force=true" \
  -H "Cookie: session=your-session-cookie"
```

## 🏗️ Architecture

### Project Structure

```
ndk-dashboard/
├── app/
│   ├── __init__.py              # Application factory
│   ├── extensions.py            # Flask extensions and K8s client
│   ├── routes/                  # Route blueprints
│   │   ├── __init__.py
│   │   ├── main.py             # Dashboard and health routes
│   │   ├── auth.py             # Authentication routes
│   │   ├── applications.py     # Application management
│   │   ├── snapshots.py        # Snapshot management
│   │   ├── protectionplans.py  # Protection plan management
│   │   ├── storage.py          # Storage cluster routes
│   │   └── deployment.py       # Deployment templates
│   ├── services/                # Business logic layer
│   │   ├── __init__.py
│   │   ├── applications.py     # Application service
│   │   ├── snapshots.py        # Snapshot service
│   │   ├── protection_plans.py # Protection plan service
│   │   ├── storage.py          # Storage service
│   │   └── deployment.py       # Deployment service
│   └── utils/                   # Utility functions
│       ├── __init__.py
│       ├── decorators.py       # Login required decorator
│       └── cache.py            # Caching utilities
├── templates/                   # Jinja2 templates
│   ├── index.html              # Main dashboard
│   ├── admin.html              # Admin panel
│   ├── login.html              # Login page
│   ├── 404.html                # Not found page
│   └── 500.html                # Error page
├── static/                      # Static assets
│   ├── styles.css              # Dashboard styles
│   ├── app.js                  # Frontend JavaScript
│   ├── favicon.svg             # Favicon
│   └── sk8s.jpg                # Background image
├── config.py                    # Configuration management
├── run.py                       # Application entry point
├── requirements.txt             # Python dependencies
├── cleanup_namespace.py         # Namespace cleanup utility
├── start-local.sh              # Local startup script
├── restart.sh                  # Restart script
├── backup.sh                   # Backup script
├── LICENSE                     # MIT License
└── README.md                   # This file
```

### Design Patterns

The application follows these architectural patterns:

- **Application Factory Pattern**: Modular Flask app initialization with configuration management
- **Blueprint Architecture**: Separated concerns for routes (auth, applications, snapshots, etc.)
- **Service Layer**: Business logic separated from route handlers for reusability and testing
- **Intelligent Caching**: Reduces Kubernetes API calls with configurable TTL

## 💻 Development

### Setting Up Development Environment

1. **Fork and clone the repository**
   ```bash
   git clone https://github.com/your-username/ndk-dashboard.git
   cd ndk-dashboard
   ```

2. **Create virtual environment**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run in development mode**
   ```bash
   export FLASK_ENV=development
   python3 run.py
   ```

### Code Style

- Follow PEP 8 guidelines
- Use type hints where appropriate
- Document functions with docstrings
- Keep functions focused and small

### Adding New Features

**Adding a New Route:**

1. Create route in appropriate blueprint:
   ```python
   # app/routes/your_feature.py
   from flask import Blueprint, jsonify
   from app.utils import login_required
   
   your_feature_bp = Blueprint('your_feature', __name__)
   
   @your_feature_bp.route('/api/your-endpoint')
   @login_required
   def your_endpoint():
       return jsonify({'status': 'success'})
   ```

2. Register blueprint in `app/__init__.py`:
   ```python
   from app.routes import your_feature_bp
   app.register_blueprint(your_feature_bp, url_prefix='/api')
   ```

**Adding a New Service:**

1. Create service file:
   ```python
   # app/services/your_service.py
   from app.extensions import k8s_api
   from config import Config
   
   class YourService:
       @staticmethod
       def your_method():
           # Business logic here
           pass
   ```

2. Import in routes:
   ```python
   from app.services import YourService
   ```

### Testing

Test the dashboard with:

```bash
# Health check
curl http://localhost:5000/health

# Test API
curl -X GET http://localhost:5000/api/applications

# Verify NDK resources
kubectl get applications
kubectl get applicationsnapshots
```

## 🚢 Deployment

### Nutanix NKP (Kubernetes Platform) Deployment

#### Quick Start (Copy-Paste Instructions)

**Prerequisites:**
- Nutanix NKP cluster with NDK installed
- kubectl configured with cluster access
- Terminal/shell access

**One-Command Deployment:**

1. **Create a deployment file**:
   ```bash
   cat > ndk-dashboard-nkp.yaml << 'EOF'
   apiVersion: v1
   kind: Namespace
   metadata:
     name: ndk-dashboard
     labels:
       app.kubernetes.io/managed-by: ndk-dashboard
   ---
   apiVersion: v1
   kind: ConfigMap
   metadata:
     name: ndk-dashboard-config
     namespace: ndk-dashboard
   data:
     FLASK_ENV: "production"
     IN_CLUSTER: "true"
     CACHE_TTL: "30"
     SESSION_TIMEOUT_HOURS: "24"
   ---
   apiVersion: v1
   kind: Secret
   metadata:
     name: ndk-dashboard-secret
     namespace: ndk-dashboard
   type: Opaque
   stringData:
     SECRET_KEY: "change-this-to-random-key-in-production"
     DASHBOARD_USERNAME: "nutanix"
     DASHBOARD_PASSWORD: "Nutanix/4u!"
   ---
   apiVersion: v1
   kind: ServiceAccount
   metadata:
     name: ndk-dashboard
     namespace: ndk-dashboard
   ---
   apiVersion: rbac.authorization.k8s.io/v1
   kind: ClusterRole
   metadata:
     name: ndk-dashboard
   rules:
   - apiGroups: ["dataservices.nutanix.com"]
     resources: ["*"]
     verbs: ["get", "list", "watch", "create", "update", "patch", "delete"]
   - apiGroups: [""]
     resources: ["namespaces", "pods", "services", "persistentvolumeclaims", "configmaps"]
     verbs: ["get", "list", "watch", "create", "update", "patch", "delete"]
   - apiGroups: ["apps"]
     resources: ["statefulsets", "deployments"]
     verbs: ["get", "list", "watch", "delete"]
   ---
   apiVersion: rbac.authorization.k8s.io/v1
   kind: ClusterRoleBinding
   metadata:
     name: ndk-dashboard
   roleRef:
     apiGroup: rbac.authorization.k8s.io
     kind: ClusterRole
     name: ndk-dashboard
   subjects:
   - kind: ServiceAccount
     name: ndk-dashboard
     namespace: ndk-dashboard
   ---
   apiVersion: apps/v1
   kind: Deployment
   metadata:
     name: ndk-dashboard
     namespace: ndk-dashboard
   spec:
     replicas: 2
     selector:
       matchLabels:
         app: ndk-dashboard
     template:
       metadata:
         labels:
           app: ndk-dashboard
       spec:
         affinity:
           podAntiAffinity:
             preferredDuringSchedulingIgnoredDuringExecution:
             - weight: 100
               podAffinityTerm:
                 labelSelector:
                   matchExpressions:
                   - key: app
                     operator: In
                     values:
                     - ndk-dashboard
                 topologyKey: kubernetes.io/hostname
         serviceAccountName: ndk-dashboard
         containers:
         - name: ndk-dashboard
           image: python:3.12-slim
           imagePullPolicy: IfNotPresent
           ports:
           - containerPort: 5000
             name: http
           envFrom:
           - configMapRef:
               name: ndk-dashboard-config
           - secretRef:
               name: ndk-dashboard-secret
           command: ["/bin/bash", "-c"]
           args:
           - |
             git clone https://github.com/nutanixed/ndk-dashboard.git /app
             cd /app
             pip install --no-cache-dir -r requirements.txt
             python3 run.py
           resources:
             requests:
               memory: "256Mi"
               cpu: "250m"
             limits:
               memory: "512Mi"
               cpu: "500m"
           livenessProbe:
             httpGet:
               path: /health
               port: 5000
             initialDelaySeconds: 30
             periodSeconds: 10
           readinessProbe:
             httpGet:
               path: /health
               port: 5000
             initialDelaySeconds: 10
             periodSeconds: 5
   ---
   apiVersion: v1
   kind: Service
   metadata:
     name: ndk-dashboard
     namespace: ndk-dashboard
     labels:
       app: ndk-dashboard
   spec:
     type: LoadBalancer
     selector:
       app: ndk-dashboard
     ports:
     - protocol: TCP
       port: 80
       targetPort: 5000
       name: http
     sessionAffinity: ClientIP
   EOF
   ```

2. **Deploy to your NKP cluster**:
   ```bash
   kubectl apply -f ndk-dashboard-nkp.yaml
   ```

3. **Wait for the deployment to be ready** (2-3 minutes):
   ```bash
   kubectl rollout status deployment/ndk-dashboard -n ndk-dashboard
   ```

4. **Get the dashboard URL**:
   ```bash
   kubectl get svc ndk-dashboard -n ndk-dashboard
   ```
   Copy the `EXTERNAL-IP` value and open `http://<EXTERNAL-IP>` in your browser

5. **Login with default credentials**:
   - **Username**: `nutanix`
   - **Password**: `Nutanix/4u!`

**Verification Commands:**

```bash
# Check pod status
kubectl get pods -n ndk-dashboard

# View logs
kubectl logs -f deployment/ndk-dashboard -n ndk-dashboard

# Check service
kubectl get svc -n ndk-dashboard

# Verify health
curl http://<EXTERNAL-IP>/health
```



**NKP-Specific Considerations:**
- **Storage**: NKP provides native Nutanix storage integration; no additional configuration needed
- **Replicas**: Deploy 2+ replicas for HA within NKP cluster
- **Pod Anti-Affinity**: Spreads dashboard pods across nodes for resilience
- **Session Affinity**: ClientIP sticky sessions for stateful dashboard access
- **GitHub Bootstrap**: Deployment automatically clones and bootstraps from GitHub on pod startup
- **Resource Quotas**: Set appropriate quotas in the ndk-dashboard namespace
- **Monitoring**: Integrate with NKP's built-in monitoring and alerting

### General Kubernetes Deployment

**Prerequisites:**
- Kubernetes cluster (1.20+) with NDK installed
- kubectl configured with cluster access
- Appropriate RBAC permissions
- Python 3.12 or container runtime

**Deployment Steps:**

1. **Create namespace**:
   ```bash
   kubectl create namespace ndk-dashboard
   ```

2. **Create ConfigMap**:
   ```yaml
   apiVersion: v1
   kind: ConfigMap
   metadata:
     name: ndk-dashboard-config
     namespace: ndk-dashboard
   data:
     FLASK_ENV: "production"
     IN_CLUSTER: "true"
     CACHE_TTL: "30"
     SESSION_TIMEOUT_HOURS: "24"
   ```

3. **Create Secret**:
   ```bash
   kubectl create secret generic ndk-dashboard-secret \
     --from-literal=SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))") \
     --from-literal=DASHBOARD_USERNAME=nutanix \
     --from-literal=DASHBOARD_PASSWORD='Nutanix/4u!' \
     -n ndk-dashboard
   ```

4. **Create RBAC**:
   ```yaml
   apiVersion: v1
   kind: ServiceAccount
   metadata:
     name: ndk-dashboard
     namespace: ndk-dashboard
   ---
   apiVersion: rbac.authorization.k8s.io/v1
   kind: ClusterRole
   metadata:
     name: ndk-dashboard
   rules:
   - apiGroups: ["dataservices.nutanix.com"]
     resources: ["*"]
     verbs: ["get", "list", "watch", "create", "update", "patch", "delete"]
   - apiGroups: [""]
     resources: ["namespaces", "pods", "services", "persistentvolumeclaims", "configmaps"]
     verbs: ["get", "list", "watch", "create", "update", "patch", "delete"]
   - apiGroups: ["apps"]
     resources: ["statefulsets", "deployments"]
     verbs: ["get", "list", "watch", "delete"]
   ---
   apiVersion: rbac.authorization.k8s.io/v1
   kind: ClusterRoleBinding
   metadata:
     name: ndk-dashboard
   roleRef:
     apiGroup: rbac.authorization.k8s.io
     kind: ClusterRole
     name: ndk-dashboard
   subjects:
   - kind: ServiceAccount
     name: ndk-dashboard
     namespace: ndk-dashboard
   ```

5. **Create Deployment**:
   ```yaml
   apiVersion: apps/v1
   kind: Deployment
   metadata:
     name: ndk-dashboard
     namespace: ndk-dashboard
   spec:
     replicas: 1
     selector:
       matchLabels:
         app: ndk-dashboard
     template:
       metadata:
         labels:
           app: ndk-dashboard
       spec:
         serviceAccountName: ndk-dashboard
         containers:
         - name: ndk-dashboard
           image: python:3.12-slim
           ports:
           - containerPort: 5000
           envFrom:
           - configMapRef:
               name: ndk-dashboard-config
           - secretRef:
               name: ndk-dashboard-secret
           command: ["/bin/bash", "-c"]
           args:
           - |
             git clone https://github.com/nutanixed/ndk-dashboard.git /app
             cd /app
             git checkout v3.0.0
             pip install --no-cache-dir -r requirements.txt
             python3 run.py
           resources:
             requests:
               memory: "256Mi"
               cpu: "250m"
             limits:
               memory: "512Mi"
               cpu: "500m"
           livenessProbe:
             httpGet:
               path: /health
               port: 5000
             initialDelaySeconds: 30
             periodSeconds: 10
           readinessProbe:
             httpGet:
               path: /health
               port: 5000
             initialDelaySeconds: 10
             periodSeconds: 5
   ```

6. **Create Service**:
   ```yaml
   apiVersion: v1
   kind: Service
   metadata:
     name: ndk-dashboard
     namespace: ndk-dashboard
   spec:
     type: LoadBalancer
     selector:
       app: ndk-dashboard
     ports:
     - protocol: TCP
       port: 80
       targetPort: 5000
   ```

7. **Deploy**:
   ```bash
   kubectl apply -f ndk-dashboard-deployment.yaml
   ```

8. **Get LoadBalancer IP**:
   ```bash
   kubectl get svc ndk-dashboard -n ndk-dashboard
   ```

### Production Considerations

**Security:**
- Change default credentials
- Use strong SECRET_KEY
- Enable HTTPS/TLS
- Implement network policies
- Regular security updates

**Performance:**
- Adjust CACHE_TTL based on needs
- Scale replicas for high availability
- Monitor resource usage
- Optimize Kubernetes API calls

**Monitoring:**
- Set up health check monitoring
- Configure logging aggregation
- Monitor pod restarts
- Track API response times

## 🔍 Troubleshooting

### Common Issues

**Issue: Cannot connect to Kubernetes cluster**
```bash
# Check kubectl configuration
kubectl cluster-info
kubectl get nodes

# Verify RBAC permissions
kubectl auth can-i list applications
kubectl auth can-i create applicationsnapshots
```

**Issue: Authentication fails**
```bash
# Check credentials in config
echo $DASHBOARD_USERNAME
echo $DASHBOARD_PASSWORD

# Verify session configuration
# Check SECRET_KEY is set
```

**Issue: Applications not showing**
```bash
# Verify NDK is installed
kubectl get crd | grep dataservices

# Check applications exist
kubectl get applications --all-namespaces

# Check dashboard logs
kubectl logs -l app=ndk-dashboard -n ndk-dashboard
```

**Issue: Snapshot creation fails**
```bash
# Check storage cluster status
kubectl get storageclusters

# Verify application is ready
kubectl get application <name> -n <namespace> -o yaml

# Check NDK operator logs
kubectl logs -n ntnx-system -l app=ndk-operator
```

### Debug Mode

Enable debug logging:
```bash
export FLASK_ENV=development
python3 run.py
```

Check application logs:
```bash
tail -f flask.log
```

## 🤝 Contributing

Contributions are welcome! Please follow these guidelines:

1. **Fork the repository**
2. **Create a feature branch**: `git checkout -b feature/your-feature`
3. **Make your changes**
4. **Test thoroughly**
5. **Commit with clear messages**: `git commit -m "Add feature: description"`
6. **Push to your fork**: `git push origin feature/your-feature`
7. **Create a Pull Request**

### Contribution Guidelines

- Follow existing code style
- Add tests for new features
- Update documentation
- Keep commits focused and atomic
- Write clear commit messages

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **Nutanix**: For NDK and Kubernetes integration
- **Flask**: For the excellent web framework
- **Kubernetes Python Client**: For Kubernetes API access
- **Community**: For feedback and contributions

---

**Version**: 3.0.0  
**Last Updated**: 2025-01-08  
**Maintained by**: Nutanix Community