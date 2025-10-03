# NDK Dashboard

A comprehensive web-based dashboard for managing Nutanix Database Kubernetes (NDK) resources. This dashboard provides an intuitive interface for deploying, monitoring, and managing database applications, protection plans, and snapshots in your Kubernetes cluster.

![NDK Dashboard](https://img.shields.io/badge/Nutanix-NDK-blue)
![Python](https://img.shields.io/badge/Python-3.8+-green)
![Flask](https://img.shields.io/badge/Flask-3.0+-lightgrey)
![Kubernetes](https://img.shields.io/badge/Kubernetes-1.20+-326CE5)

## Features

### 📊 Dashboard Overview
- Real-time cluster statistics
- Database application monitoring
- Protection plan status
- Snapshot management
- Resource utilization tracking

### 🗄️ Database Management
- **Supported Databases**: MySQL, PostgreSQL, MongoDB, Elasticsearch
- One-click deployment from templates
- Custom configuration support
- Application lifecycle management (start, stop, delete)
- Real-time status monitoring

### 🛡️ Protection Plans
- Create and manage backup schedules
- Human-readable cron schedule display (e.g., "Daily at 2:00 AM")
- Flexible retention policies (count-based or time-based)
- Track last execution times
- Automatic JobScheduler resource management

### 📸 Snapshot Management
- View all application snapshots
- Manual snapshot creation
- Snapshot restoration
- Snapshot deletion
- Creation time tracking

### 🔍 Resource Monitoring
- List all database applications
- View detailed application configurations
- Monitor application health status
- Track resource relationships

## Prerequisites

- **Kubernetes Cluster**: Version 1.20 or higher
- **Nutanix NDK**: Installed and configured in your cluster
- **Python**: Version 3.8 or higher
- **kubectl**: Configured with cluster access
- **Kubernetes Python Client**: For API interactions

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/nutanixed/ndk-dashboard.git
cd ndk-dashboard
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Kubernetes Access

Ensure your `~/.kube/config` is properly configured to access your Kubernetes cluster:

```bash
kubectl cluster-info
```

### 4. Run the Dashboard

```bash
python app.py
```

The dashboard will be available at `http://localhost:5000`

## Configuration

### Environment Variables

- `KUBECONFIG`: Path to your Kubernetes config file (default: `~/.kube/config`)
- `FLASK_ENV`: Set to `development` for debug mode
- `FLASK_PORT`: Port to run the dashboard (default: 5000)

### Kubernetes Requirements

The dashboard requires access to the following Kubernetes resources:

- **API Groups**:
  - `ndb.nutanix.com/v1alpha1` (Database, ApplicationSnapshot, ProtectionPlan)
  - `scheduler.nutanix.com/v1alpha1` (JobScheduler)
  - Core API (Namespaces, Pods, Services)

- **Permissions**: The service account or user running the dashboard needs:
  - `get`, `list`, `create`, `delete` on Database resources
  - `get`, `list`, `create`, `delete` on ApplicationSnapshot resources
  - `get`, `list`, `create`, `delete` on ProtectionPlan resources
  - `get`, `list`, `create`, `delete` on JobScheduler resources

## Usage

### Deploying a Database

1. Navigate to the **Deploy** section
2. Select a database template (MySQL, PostgreSQL, MongoDB, or Elasticsearch)
3. Configure the deployment parameters:
   - Application name
   - Namespace
   - Database version
   - Storage size
   - Resource limits
4. Click **Deploy**

### Creating a Protection Plan

1. Go to the **Protection Plans** section
2. Click **Create Protection Plan**
3. Configure the plan:
   - **Name**: Unique identifier for the plan
   - **Application**: Select the database to protect
   - **Schedule**: Choose from common schedules or enter custom cron expression
   - **Retention**: Set retention count or max age
4. Click **Create**

### Managing Snapshots

1. Navigate to the **Snapshots** section
2. View all existing snapshots with their status and creation time
3. Actions available:
   - **Create**: Take a manual snapshot of any application
   - **Restore**: Restore an application from a snapshot
   - **Delete**: Remove unwanted snapshots

## Architecture

### Backend (Flask)

- **app.py**: Main Flask application with API endpoints
- **Kubernetes Client**: Direct integration with Kubernetes API
- **Custom Resource Definitions**: Handles NDK-specific CRDs

### Frontend (JavaScript)

- **static/app.js**: Dynamic UI rendering and API interactions
- **static/styles.css**: Custom styling and responsive design
- **templates/index.html**: Single-page application template

### Key Components

1. **Dashboard Controller**: Aggregates cluster statistics
2. **Database Manager**: Handles database lifecycle operations
3. **Protection Plan Manager**: Manages backup schedules and JobScheduler resources
4. **Snapshot Manager**: Controls snapshot operations
5. **Cron Formatter**: Converts cron expressions to human-readable format

## API Endpoints

### Dashboard
- `GET /api/dashboard` - Get cluster statistics

### Applications
- `GET /api/applications` - List all database applications
- `POST /api/applications` - Deploy a new database
- `DELETE /api/applications/<name>` - Delete an application

### Protection Plans
- `GET /api/protectionplans` - List all protection plans
- `POST /api/protectionplans` - Create a new protection plan
- `DELETE /api/protectionplans/<name>` - Delete a protection plan

### Snapshots
- `GET /api/snapshots` - List all snapshots
- `POST /api/snapshots` - Create a manual snapshot
- `POST /api/snapshots/<name>/restore` - Restore from snapshot
- `DELETE /api/snapshots/<name>` - Delete a snapshot

## Troubleshooting

### Dashboard Won't Start

**Issue**: `kubernetes.config.config_exception.ConfigException`

**Solution**: Ensure your kubeconfig is properly configured:
```bash
export KUBECONFIG=~/.kube/config
kubectl get nodes
```

### Protection Plans Show "Not Set"

**Issue**: Schedule or retention showing as "Not Set"

**Solution**: This was fixed in the latest version. Ensure you're running the updated code that:
- Fetches JobScheduler resources for schedules
- Reads retentionPolicy object for retention values
- Queries ApplicationSnapshots for last execution time

### Applications Won't Deploy

**Issue**: Deployment fails with API errors

**Solution**: 
1. Verify NDK is installed: `kubectl get crd databases.ndb.nutanix.com`
2. Check namespace exists: `kubectl get namespace <namespace>`
3. Review logs: Check Flask console output for detailed errors

### Snapshots Not Showing

**Issue**: Snapshots exist but don't appear in dashboard

**Solution**: Ensure snapshots have the correct labels:
```bash
kubectl get applicationsnapshots -A --show-labels
```

## Development

### Project Structure

```
ndk-dashboard/
├── app.py                 # Flask backend
├── requirements.txt       # Python dependencies
├── static/
│   ├── app.js            # Frontend JavaScript
│   └── styles.css        # CSS styling
├── templates/
│   └── index.html        # HTML template
└── README.md             # This file
```

### Adding New Database Templates

1. Edit `templates/index.html`
2. Add a new template card in the Deploy section
3. Update `static/app.js` to handle the new template
4. Add deployment logic in `app.py` if needed

### Extending Protection Plans

To add new schedule patterns to the cron formatter:

1. Edit `static/app.js`
2. Update the `formatCronSchedule()` function
3. Add new regex patterns and formatting logic

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Built for Nutanix Database Kubernetes (NDK)
- Uses the Kubernetes Python Client
- Flask web framework
- Bootstrap for UI components

## Support

For issues, questions, or contributions, please open an issue on GitHub.

## Changelog

### Version 1.0.0 (Current)

**Features**:
- ✅ Complete dashboard with cluster statistics
- ✅ Database deployment and management
- ✅ Protection plan creation and management
- ✅ Snapshot operations (create, restore, delete)
- ✅ Human-readable cron schedule display
- ✅ Proper retention policy display
- ✅ Last execution time tracking
- ✅ Automatic JobScheduler resource management
- ✅ Resource cleanup on deletion

**Bug Fixes**:
- Fixed schedule display (now fetches from JobScheduler resources)
- Fixed retention display (now reads from retentionPolicy object)
- Fixed last execution time (now queries ApplicationSnapshots)
- Fixed protection plan creation (now creates JobScheduler resources)
- Fixed protection plan deletion (now cleans up JobScheduler resources)

**UI Improvements**:
- Human-readable schedule format (e.g., "Daily at 2:00 AM")
- Hidden unused database templates (Redis, Cassandra)
- Improved error handling and user feedback
- Responsive design for mobile devices

## Roadmap

- [ ] Multi-cluster support
- [ ] Advanced filtering and search
- [ ] Backup/restore history tracking
- [ ] Email notifications for backup failures
- [ ] Grafana dashboard integration
- [ ] RBAC and authentication
- [ ] Audit logging
- [ ] Backup verification and testing
- [ ] Cost tracking and optimization
- [ ] Custom database configurations