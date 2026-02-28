# Changelog

All notable changes to the NDK Dashboard project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [3.5.1] - 2025-11-18

### 🐛 Bug Fixes

#### ProtectionPlan YAML Download Enhancement
- **Retention Duration Annotation**: Added `ndk-dashboard/retention-duration` annotation to downloaded ProtectionPlan YAML templates
  - Ensures time-based retention policies are properly preserved during deployment
  - Complements retention count for comprehensive retention policy support
  - Annotation automatically included in all generated ProtectionPlan manifests

## [3.5.0] - 2025-11-17

### ✨ New Features

#### Kubernetes ConfigMap Integration
- **ConfigMap Persistence**: Database settings now persist in Kubernetes ConfigMap (`ndk-dashboard-settings`)
  - Automatic ConfigMap creation if it doesn't exist
  - Settings survive pod restarts and cluster updates
  - Centralized configuration accessible cluster-wide
  - Fallback to local file storage for offline functionality

#### Multi-Pod Database Configuration
- **Pod-Specific Settings**: Configure different database connection parameters for multiple pods
  - Add Pod/Deployment Name field to specify which pod settings apply to
  - Support for any number of pods with independent configurations
  - Extensible architecture for managing multiple applications
- **Dynamic Host Configuration**: SQL Host/DNS Name is now fully configurable
  - Previously hardcoded to `mysql-0.mysql.nkpdev.svc.cluster.local`
  - Now supports any pod IP, hostname, or custom DNS entry
- **Configurable Database Credentials**
  - Username field (previously hardcoded to `root`)
  - Database Name field (previously hardcoded to `mydb`)
  - Password field (already configurable)

#### Public API Endpoint
- **New Endpoint**: `/api/public/taskapp-db-settings/<pod_name>`
  - Unauthenticated access for cluster-wide configuration retrieval
  - Allows any pod to fetch its database settings by pod name
  - Returns complete connection parameters in JSON format
  - Enables external applications to dynamically configure themselves

### 🔄 Changed

#### Backend Updates
- **Settings Management**: Enhanced settings system in `app/routes/main.py`
  - New `load_settings_from_configmap()` function for ConfigMap reading
  - New `save_settings_to_configmap()` function with automatic ConfigMap creation
  - Updated `load_settings()` and `save_settings()` with ConfigMap support and file fallback
  - All database connection functions now use configurable host and username parameters
- **Configuration Structure**: Extended settings.json with new fields
  - Added `pod` field to identify target pod
  - Added `host` field for database hostname
  - Added `username` field for database user
  - Maintains backward compatibility with existing configurations

#### Frontend Updates
- **Admin UI**: Task App Database section redesign
  - New Pod/Deployment Name input field
  - SQL Host/DNS Name configurable input
  - Username configurable input
  - Reordered fields for logical workflow
  - Updated button styling with inline Save Settings
- **JavaScript**: Enhanced `loadTaskAppDatabaseSettings()` and `saveTaskAppDatabaseSettings()`
  - Load and persist all five configuration parameters
  - Improved validation before saving
  - Better error handling and user feedback

#### Deployment Examples
- **Examples Documentation**: Comprehensive guide for ConfigMap usage in `examples/README.md`
  - Settings structure documentation
  - Deployment instructions
  - Public API usage examples
  - Python code example for applications to fetch settings

### 📦 Files Modified

- `app/routes/main.py` - ConfigMap integration and multi-pod support
- `instance/settings.json` - New pod, host, and username fields
- `templates/admin.html` - UI redesign for multi-pod configuration
- `examples/README.md` - ConfigMap and public API documentation
- `examples/ndk-dashboard-configmap.yaml` - New example ConfigMap manifest

### 🎯 Technical Details

#### ConfigMap Implementation
- Namespace: `nkpdev`, ConfigMap Name: `ndk-dashboard-settings`
- Automatic creation with proper labels and ownership
- Graceful fallback to local file if ConfigMap access fails
- Supports both ConfigMap and file-based persistence

#### Public API Design
- RESTful endpoint for configuration retrieval
- Pod name path parameter for target specification
- JSON response format with success flag
- No authentication required (assumes trusted cluster network)

#### Settings Persistence Strategy
- ConfigMap: Primary persistence layer for cluster-wide access
- Local File: Secondary persistence layer for offline access and backward compatibility
- Synchronization: Both storage mechanisms updated on save
- Reconciliation: File serves as fallback when ConfigMap is unavailable

---

## [3.4.0] - 2025-11-16

### ✨ New Features

#### Resources Management Page
- **New Resources Tab**: Added comprehensive resources management interface
  - Display Kubernetes resources with real-time status
  - Filter and search capabilities
  - Detailed resource information
  - Inline resource operations (delete, update)
  - Support for multiple resource types

#### UI Enhancements
- **Improved Navigation**: Enhanced admin panel with resources tab
- **Responsive Design**: Better layout and styling for all screen sizes
- **Visual Improvements**: Updated styles and animations for better UX
- **Application Icons**: Refined iconography across the dashboard

### 🔄 Changed

#### Frontend Updates
- **Admin Panel**: Expanded admin interface with new resources management
- **CSS Styling**: Comprehensive style updates for improved visual hierarchy
  - Enhanced color scheme and gradients
  - Better spacing and alignment
  - Improved responsive breakpoints
  - Updated animation timings
- **JavaScript**: Refactored application logic
  - Better event handling
  - Improved state management
  - Enhanced error handling
  - Better modal interactions
- **Templates**: Updated HTML templates for consistency

#### Backend Updates
- **Route Handlers**: Enhanced main.py with improved endpoint handling
- **Extensions**: Updated Flask extensions configuration
- **Services**: Minor improvements to snapshot service

#### Dependencies
- **requirements.txt**: Updated package versions for better compatibility
- **Configuration**: Added settings.json for application configuration

### 🐛 Fixed

- **UI Consistency**: Fixed styling inconsistencies across pages
- **Modal Interactions**: Improved modal behavior and animations
- **Error Handling**: Enhanced error messages and user feedback

### 📦 Files Modified

- `app/extensions.py` - Updated extensions configuration
- `app/routes/main.py` - Enhanced route handlers and added new endpoints
- `app/services/snapshots.py` - Improved snapshot service logic
- `instance/settings.json` - New configuration file
- `requirements.txt` - Updated dependencies
- `static/app.js` - Refactored JavaScript with new features
- `static/styles.css` - Comprehensive style updates
- `templates/admin.html` - Enhanced admin panel with resources tab
- `templates/index.html` - Updated dashboard template
- `templates/resources.html` - New resources management page

### 🎯 Technical Details

#### New Endpoints
- Enhanced admin panel with resources management capabilities
- Improved API response handling
- Better cache management

#### UI/UX Improvements
- More intuitive navigation
- Better visual feedback for operations
- Improved error messages
- Enhanced responsive design

---

## [3.3.0] - 2025-01-14

### ✨ New Features

#### Restore Job Cleanup Management
- **Restore Cleanup Tab**: Added new admin section for managing Velero restore jobs
  - View all restore jobs across all namespaces with detailed status information
  - Display restore phase (Completed, Failed, PartiallyFailed, InProgress)
  - Show creation timestamp, completion time, and warnings
  - Filter and search capabilities for restore jobs
  - Individual restore job deletion with confirmation modal
  - Bulk cleanup operations:
    - Delete all completed restores
    - Delete all failed restores
    - Delete all restores (with confirmation)
  - Real-time status updates and error handling
  - Professional UI with status badges and action buttons

#### Backend Services
- **Restore Service Layer**: New `app/services/restores.py` module
  - List all Velero restore jobs across namespaces
  - Get detailed restore job information
  - Delete individual restore jobs
  - Bulk cleanup operations with filtering by status
  - Comprehensive error handling and logging
- **Restore API Routes**: New `app/routes/restores.py` blueprint
  - `GET /api/restores` - List all restore jobs
  - `DELETE /api/restores/<namespace>/<name>` - Delete specific restore job
  - `POST /api/restores/cleanup` - Bulk cleanup with status filtering
  - Proper error responses and status codes

### 🔄 Changed

#### UI Improvements
- **Admin Panel**: Enhanced admin interface with new Restore Cleanup tab
- **Modal Styling**: Consistent confirmation modals for all restore operations
  - Individual restore deletion now uses the same polished modal UI as "Cleanup All"
  - Red gradient header with trash icon
  - Warning message with restore job details (name and namespace)
  - Progress modal with status updates and auto-refresh
  - Replaced simple confirm/alert dialogs with professional modal workflow
- **Status Display**: Color-coded status badges for restore phases:
  - Green for Completed
  - Red for Failed
  - Orange for PartiallyFailed
  - Blue for InProgress

#### Code Organization
- **Blueprint Registration**: Added restores blueprint to application factory
- **Route Exports**: Updated `app/routes/__init__.py` to export restores blueprint

### 🐛 Fixed

#### Critical Fixes
- **Restore API Routes**: Fixed URL prefix conflict in restores blueprint
  - Removed duplicate `/api` prefix that caused 404 errors
  - Routes now correctly registered at `/api/restores` instead of `/api/api/restores`
  - Updated route decorators to include full paths
  - Fixed "Unexpected token '<'" error in frontend caused by HTML 404 responses
- **Snapshot Restore Application CRD Creation**: Fixed missing Application CRD after snapshot restore
  - Fixed bug where Application CRD was only created for cross-namespace restores
  - Now creates Application CRD for ALL restore operations (same-namespace and cross-namespace)
  - Ensures restored applications are immediately visible in the NDK Dashboard
  - Properly copies selector from source Application CRD or uses default selector
  - Updated comments to clarify that NDK does not automatically create Application CRDs for any restore type

#### Improvements to Existing Features
- **Snapshot Management**: Enhanced error handling and status reporting
- **Protection Plans**: Improved trigger and cleanup operations
- **Deployment Service**: Better validation and error messages

### 🔒 Security

- **Configuration Protection**: Added `config.cfg` to `.gitignore`
  - Prevents accidental commits of sensitive Kubernetes cluster credentials
  - Protects server URLs, certificates, and authentication tokens
  - Follows security best practices for credential management

### 📦 Files Added

- `app/services/restores.py` - Service layer for restore job management
- `app/routes/restores.py` - API routes for restore operations

### 📦 Files Modified

- `.gitignore` - Added config.cfg to prevent credential leaks
- `app/__init__.py` - Registered restores blueprint
- `app/routes/__init__.py` - Exported restores blueprint
- `templates/admin.html` - Added Restore Cleanup tab with full UI and individual restore deletion modal
- `app/routes/protectionplans.py` - Enhanced error handling
- `app/routes/snapshots.py` - Improved status reporting
- `app/services/deployment.py` - Better validation
- `app/services/protection_plans.py` - Improved cleanup operations
- `app/services/snapshots.py` - Fixed Application CRD creation logic for all restore types
- `static/app.js` - Added restore cleanup functionality
- `static/styles.css` - Added restore UI styling
- `templates/index.html` - Minor UI improvements

### 🎯 Technical Details

#### Blueprint URL Prefix Pattern
- Blueprints are defined without URL prefix in their definition
- URL prefix is applied during registration in `app/__init__.py`
- Route decorators include the full path relative to the prefix
- This pattern ensures consistency across all blueprints

#### Restore Job Management
- Uses Velero CRD (`restore.velero.io/v1`)
- Supports filtering by restore phase (Completed, Failed, PartiallyFailed)
- Handles finalizers for proper resource cleanup
- Provides detailed status information including warnings and errors

---

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