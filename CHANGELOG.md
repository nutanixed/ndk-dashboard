# Changelog

All notable changes to the NDK Dashboard project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [3.2.0] - 2025-01-14

### ✨ New Features

#### UI Improvements
- **Snapshot Deletion Modal**: Added styled confirmation modal for snapshot deletion (replaces browser confirm dialog)
  - Red gradient header with trash icon
  - Warning message with snapshot name display
  - Consistent with other modal designs
- **Download YAML Templates**: Added dropdown button in Deploy tab to download YAML manifests
  - Support for MySQL, PostgreSQL, MongoDB, and Elasticsearch
  - Templates include all resources: Namespace, Secret, Service, StatefulSet, Application CR, JobScheduler, ProtectionPlan, AppProtectionPlan
  - Uses customizable variables: `{{APP_NAME}}`, `{{NAMESPACE}}`, `{{REPLICAS}}`, `{{STORAGE_CLASS}}`, `{{STORAGE_SIZE}}`, `{{CRON_SCHEDULE}}`, `{{RETENTION_COUNT}}`, `{{CUSTOM_LABELS}}`
- **SVG Icons**: Replaced emoji icons with professional SVG icons for:
  - Applications (document/list icon)
  - Snapshots (camera/image icon)
  - Storage Clusters (database/cylinder icon)
  - Protection Plans (shield icon)
- **Label Clarity**: Changed "Create NDK Application CR" to "Enable NDK Data Services" for better user understanding

#### Examples Directory
- **Deployment Examples**: Added `/examples` directory with complete YAML manifests:
  - `mysql-deployment.yaml` - 3 replicas, 10Gi storage, daily backups, 7 retention
  - `postgresql-deployment.yaml` - 3 replicas, 20Gi storage, every 6 hours, 14 retention
  - `mongodb-deployment.yaml` - 3 replicas, 50Gi storage, daily backups, 10 retention
  - `elasticsearch-deployment.yaml` - 3 replicas, 100Gi storage, daily backups, 5 retention
  - `README.md` - Complete documentation with usage instructions and customization tips

### 🔄 Changed

- **Removed Confirmation Prompts**: Removed browser confirm dialogs for:
  - Protection plan trigger (now triggers immediately)
  - Snapshot deletion (now uses styled modal)

### 🐛 Fixed

#### Critical Fixes
- **AppProtectionPlan Creation**: Fixed protection plans not creating snapshots at scheduled intervals
  - Now properly creates AppProtectionPlan resources when deploying applications with protection plans
  - Handles both string and dict formats for application data
  - Links applications to protection plans correctly for by-name selection mode
- **Protection Plan Deletion**: Enhanced cleanup to properly remove all associated resources:
  - JobScheduler resources
  - AppProtectionPlan resources
  - ProtectionPlan itself
  - Supports force deletion with finalizer removal

#### Minor Fixes
- **Bulk Snapshot Creation**: Fixed field name mismatch between frontend and backend (`success` vs `successful`)
- **Namespace Label Consistency**: Simplified protection plan namespace field to match deploy modal format
  - Changed from "Select Namespace:" to "Namespace:"
  - Removed gradient background and special styling

### 📚 Documentation

- **YAML Examples**: Comprehensive examples for all supported database types
- **README in Examples**: Detailed guide for using and customizing deployment YAMLs
- **Variable Documentation**: Clear documentation of all template variables

### 🗑️ Removed

- **Edit Protection Plan**: Completely removed edit and suspend/disable functionality for protection plans
  - Removed edit button and toggle button from UI
  - Removed edit modal HTML
  - Removed JavaScript functions: `editProtectionPlan()`, `saveProtectionPlan()`, `closeEditPlanModal()`, `updateEditScheduleInput()`, `togglePlan()`
  - Removed backend routes: PUT `/protectionplans/<namespace>/<name>`, POST `/enable`, POST `/disable`
  - Removed `update_protection_plan()` method from ProtectionPlanService
  - Protection plans now only support: Trigger, History, and Delete actions

### 📦 Files Modified

- `app/services/protection_plans.py` - AppProtectionPlan creation and cleanup logic
- `app/routes/protectionplans.py` - Removed edit/enable/disable routes
- `app/services/snapshots.py` - Fixed field name for bulk operations
- `app/routes/snapshots.py` - Fixed field reference
- `static/app.js` - Added YAML download, snapshot deletion modal, removed edit functions
- `templates/index.html` - Added delete modal, YAML dropdown, updated icons and labels
- `examples/*` - New deployment examples and documentation

---

## [3.0.0] - 2025-01-08

### 🎉 Major Release - Complete Architecture Overhaul

This release represents a complete architectural transformation of the NDK Dashboard, moving from a monolithic structure to a modern, modular Flask application with service-oriented architecture.

### ⚠️ Breaking Changes

- **Removed monolithic `app.py`**: Application now uses Flask application factory pattern
- **Removed deployment files**: Legacy deployment manifests removed (will be recreated for v3.0.0)
  - `deployment/configmap.yaml`
  - `deployment/deployment.yaml`
  - `deployment/rbac.yaml`
  - `deployment/secret.yaml`
  - `deployment/service.yaml`
  - `deploy.sh`
- **Removed `verify_schema.py`**: Schema verification moved to service layer
- **Configuration changes**: Now uses centralized `config.py` with environment variables
- **Import paths changed**: All imports now use `app.` prefix for modular structure

### ✨ New Features

#### Architecture
- **Flask Application Factory**: Implemented `create_app()` pattern for better testing and flexibility
- **Blueprint Architecture**: Modular route organization with separate blueprints:
  - `main_bp`: Dashboard pages and health checks
  - `auth_bp`: Authentication routes
  - `applications_bp`: Application management
  - `snapshots_bp`: Snapshot operations
  - `storage_bp`: Storage cluster management
  - `protectionplans_bp`: Protection plan management
  - `deployment_bp`: Application deployment templates
- **Service Layer**: Separated business logic from routes:
  - `ApplicationService`: Application management logic
  - `SnapshotService`: Snapshot operations
  - `ProtectionPlanService`: Protection plan management
  - `StorageService`: Storage cluster operations
  - `DeploymentService`: Template-based deployments
- **Extensions Module**: Centralized Flask extensions and Kubernetes client initialization

#### Features
- **Namespace Cleanup Utility**: New `cleanup_namespace.py` script for comprehensive namespace cleanup
  - Supports dry-run mode
  - Handles NDK custom resources and standard Kubernetes resources
  - Interactive confirmation with resource counts
  - Detailed cleanup logging
- **Enhanced Snapshot Management**: Improved snapshot creation and restoration
- **Label Management**: Add and remove labels from applications via API
- **Deployment Templates**: Pre-configured MySQL and PostgreSQL deployment templates
- **Admin Panel**: Dedicated admin interface for advanced operations
- **Custom Error Pages**: 404 and 500 error pages with consistent styling
- **Favicon and Branding**: Added Nutanix branding assets (favicon.svg, sk8s.jpg)

#### UI/UX Improvements
- **Replica Pod Information**: Display pod IP addresses in replica tooltips
- **Standardized Styling**: Consistent DNS and service name styling
- **Centered Logo**: Updated header to match NKP dashboard style
- **Button Consistency**: Standardized button sizes across the interface
- **Real-time Updates**: Improved refresh functionality
- **Loading States**: Better visual feedback during operations

### 🔄 Changed

#### Code Organization
- **Modular Structure**: Complete reorganization into logical modules
  ```
  app/
  ├── __init__.py          # Application factory
  ├── extensions.py        # Flask extensions
  ├── routes/              # Route blueprints
  ├── services/            # Business logic
  └── utils/               # Utility functions
  ```
- **Configuration Management**: Centralized in `config.py` with environment variable support
- **Entry Point**: New `run.py` as the application entry point

#### Scripts
- **Updated `start-local.sh`**: Enhanced startup script with better error handling
- **Updated `restart.sh`**: Improved restart logic for modular architecture
- **New `backup.sh`**: Automated backup script with timestamped backups

#### Dependencies
- **Flask**: 3.0.0 (latest stable)
- **Kubernetes**: 28.1.0 (updated)
- **python-dotenv**: 1.0.0 (added for environment management)
- **Werkzeug**: 3.0.1 (updated)

#### API Changes
- **Consistent Response Format**: All API endpoints now return standardized JSON responses
- **Better Error Handling**: Comprehensive error messages with proper HTTP status codes
- **Cache Invalidation**: Improved cache management across related resources

### 🔒 Security

- **Environment-based Configuration**: Sensitive data moved to environment variables
- **Session Management**: Enhanced session timeout configuration
- **Secret Key Management**: Proper secret key handling with environment variables
- **RBAC Considerations**: Improved Kubernetes RBAC integration

### 🐛 Fixed

- **Label Deletion**: Fixed label deletion functionality (v2.0.0 fix carried forward)
- **Refresh Button**: Fixed button size consistency
- **Service DNS Display**: Corrected styling for service DNS names
- **Pod IP Display**: Added missing pod IP information in tooltips
- **Cache Consistency**: Fixed cache invalidation issues across related resources
- **Error Handling**: Improved error handling in snapshot operations

### 📚 Documentation

- **Comprehensive README**: Complete documentation with:
  - Installation instructions
  - Configuration guide
  - API endpoint documentation
  - Architecture overview
  - Development guidelines
  - Deployment instructions
  - Troubleshooting guide
- **Code Documentation**: Added docstrings to all modules, classes, and functions
- **Inline Comments**: Improved code comments for better maintainability

### 🗑️ Removed

- **Legacy Files**:
  - `app.py` (monolithic application file)
  - `verify_schema.py` (functionality moved to services)
  - `deploy.sh` (will be recreated for v3.0.0)
  - `deployment/*.yaml` (will be recreated for v3.0.0)

### 📦 Migration Guide from v2.x to v3.0.0

#### For Developers

1. **Update imports**:
   ```python
   # Old (v2.x)
   from app import app
   
   # New (v3.0.0)
   from app import create_app
   app = create_app()
   ```

2. **Configuration changes**:
   ```bash
   # Create .env file with your settings
   cp .env.example .env
   
   # Or set environment variables
   export SECRET_KEY=your-secret-key
   export DASHBOARD_USERNAME=your-username
   export DASHBOARD_PASSWORD=your-password
   ```

3. **Update startup**:
   ```bash
   # Old (v2.x)
   python3 app.py
   
   # New (v3.0.0)
   python3 run.py
   # Or use the startup script
   ./start-local.sh
   ```

#### For Kubernetes Deployments

1. **Update deployment manifest**:
   - Change startup command from `python3 app.py` to `python3 run.py`
   - Update environment variables to use new configuration format
   - Update git checkout to `v3.0.0` tag

2. **Update ConfigMap**:
   ```yaml
   apiVersion: v1
   kind: ConfigMap
   metadata:
     name: ndk-dashboard-config
   data:
     FLASK_ENV: "production"
     IN_CLUSTER: "true"
     CACHE_TTL: "30"
     SESSION_TIMEOUT_HOURS: "24"
   ```

3. **Update Secret**:
   ```yaml
   apiVersion: v1
   kind: Secret
   metadata:
     name: ndk-dashboard-secret
   type: Opaque
   stringData:
     SECRET_KEY: "your-secret-key"
     DASHBOARD_USERNAME: "nutanix"
     DASHBOARD_PASSWORD: "Nutanix/4u!"
   ```

#### Breaking Changes Checklist

- [ ] Update application imports
- [ ] Create `.env` file or set environment variables
- [ ] Update startup commands
- [ ] Update Kubernetes manifests (if deployed)
- [ ] Test authentication with new configuration
- [ ] Verify all API endpoints work correctly
- [ ] Update any automation scripts

### 🎯 Upgrade Steps

1. **Backup current deployment**:
   ```bash
   ./backup.sh
   ```

2. **Pull latest changes**:
   ```bash
   git pull origin main
   git checkout v3.0.0
   ```

3. **Update dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment**:
   ```bash
   cp .env.example .env
   # Edit .env with your settings
   ```

5. **Test locally**:
   ```bash
   ./start-local.sh
   ```

6. **Deploy to Kubernetes** (if applicable):
   ```bash
   kubectl apply -f deployment/
   ```

---

## [2.1.0] - 2024-XX-XX

### Added
- Pod IP address display in replica tooltips
- Enhanced replica information display

### Changed
- Standardized Service DNS styling to match table text
- Updated header to match NKP dashboard style with centered Nutanix logo
- Fixed refresh button size to match Admin and Logout buttons

---

## [2.0.0] - 2024-XX-XX

### Added
- Major refactoring with modular architecture
- Protection Plans management
- Snapshots management
- Database management features
- Application deployment capabilities

### Fixed
- Label deletion functionality

### Changed
- Complete code restructure for better maintainability
- Improved UI/UX across all pages

---

## [1.0.0] - 2024-XX-XX

### Added
- Initial release
- Basic NDK Dashboard functionality
- Application listing and management
- Kubernetes integration
- Basic authentication

---

## Version History Summary

| Version | Release Date | Type | Description |
|---------|-------------|------|-------------|
| 3.2.0 | 2025-01-14 | Minor | UI improvements, YAML templates, AppProtectionPlan fixes |
| 3.0.0 | 2025-01-08 | Major | Complete architecture overhaul with modular design |
| 2.1.0 | 2024-XX-XX | Minor | UI improvements and pod information |
| 2.0.0 | 2024-XX-XX | Major | Major refactoring with new features |
| 1.0.0 | 2024-XX-XX | Major | Initial release |

---

## Semantic Versioning

This project follows [Semantic Versioning](https://semver.org/):

- **MAJOR** version (X.0.0): Incompatible API changes or breaking changes
- **MINOR** version (0.X.0): New functionality in a backward-compatible manner
- **PATCH** version (0.0.X): Backward-compatible bug fixes

---

## Links

- [GitHub Repository](https://github.com/nutanixed/ndk-dashboard)
- [Issue Tracker](https://github.com/nutanixed/ndk-dashboard/issues)
- [Documentation](https://github.com/nutanixed/ndk-dashboard/blob/main/README.md)

---

**Note**: Dates marked as "2024-XX-XX" are approximate and should be updated with actual release dates.