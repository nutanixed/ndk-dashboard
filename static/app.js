// NDK Dashboard JavaScript

// State
let currentTab = 'applications';
let allData = {
    applications: [],
    snapshots: [],
    storageclusters: [],
    protectionplans: []
};
let selectedApplications = new Set();
let currentNamespaceFilter = 'all';

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    initializeTabs();
    initializeRefresh();
    initializeSearch();
    initializeNamespaceFilter();
    loadAllData();
});

// Tab Management
function initializeTabs() {
    const tabButtons = document.querySelectorAll('.tab-btn');
    
    tabButtons.forEach(button => {
        button.addEventListener('click', function() {
            const tabName = this.getAttribute('data-tab');
            switchTab(tabName);
        });
    });
}

function switchTab(tabName) {
    // Update buttons
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    document.querySelector(`[data-tab="${tabName}"]`).classList.add('active');
    
    // Update content
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.remove('active');
    });
    document.getElementById(`${tabName}-tab`).classList.add('active');
    
    currentTab = tabName;
}

// Refresh Management
function initializeRefresh() {
    const refreshBtn = document.getElementById('refreshBtn');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', function() {
            loadAllData();
        });
    }
}

// Namespace Filter Management
function initializeNamespaceFilter() {
    const namespaceFilter = document.getElementById('namespace-filter');
    if (namespaceFilter) {
        namespaceFilter.addEventListener('change', function() {
            currentNamespaceFilter = this.value;
            applyFilters('applications');
        });
    }
}

function populateNamespaceFilter() {
    const namespaceFilter = document.getElementById('namespace-filter');
    if (!namespaceFilter || !allData.applications) return;
    
    // Get unique namespaces from applications
    const namespaces = new Set();
    allData.applications.forEach(app => {
        if (app.namespace) {
            namespaces.add(app.namespace);
        }
    });
    
    // Sort namespaces alphabetically
    const sortedNamespaces = Array.from(namespaces).sort();
    
    // Preserve current selection
    const currentValue = namespaceFilter.value;
    
    // Rebuild options
    namespaceFilter.innerHTML = '<option value="all">All Namespaces</option>';
    sortedNamespaces.forEach(ns => {
        const option = document.createElement('option');
        option.value = ns;
        option.textContent = ns;
        namespaceFilter.appendChild(option);
    });
    
    // Restore selection if it still exists
    if (currentValue && Array.from(namespaceFilter.options).some(opt => opt.value === currentValue)) {
        namespaceFilter.value = currentValue;
    }
}

// Search Management
function initializeSearch() {
    const searchInputs = document.querySelectorAll('.search-input');
    
    searchInputs.forEach(input => {
        input.addEventListener('input', function() {
            const searchTerm = this.value.toLowerCase();
            const tabName = this.id.replace('search-', '');
            applyFilters(tabName, searchTerm);
        });
    });
}

function applyFilters(tabName, searchTerm = null) {
    // Get search term from input if not provided
    if (searchTerm === null) {
        const searchInput = document.getElementById(`search-${tabName}`);
        searchTerm = searchInput ? searchInput.value.toLowerCase() : '';
    }
    
    let data = allData[tabName];
    
    // Apply namespace filter for applications
    if (tabName === 'applications' && currentNamespaceFilter !== 'all') {
        data = data.filter(app => app.namespace === currentNamespaceFilter);
    }
    
    // Apply search filter
    if (searchTerm) {
        data = data.filter(item => {
            return JSON.stringify(item).toLowerCase().includes(searchTerm);
        });
    }
    
    renderData(tabName, data);
}

// Legacy function for backward compatibility
function filterData(tabName, searchTerm) {
    applyFilters(tabName, searchTerm);
}

// Data Loading
async function loadAllData() {
    const refreshIcon = document.getElementById('refreshIcon');
    if (refreshIcon) {
        refreshIcon.classList.add('spinning');
    }
    
    try {
        await Promise.all([
            loadStats(),
            loadApplications(),
            loadSnapshots(),
            loadStorageClusters(),
            loadProtectionPlans()
        ]);
        
        updateLastUpdated();
    } catch (error) {
        console.error('Error loading data:', error);
        showToast('Error loading data', 'error');
    } finally {
        if (refreshIcon) {
            refreshIcon.classList.remove('spinning');
        }
    }
}

async function loadStats() {
    try {
        const response = await fetch('/api/stats');
        
        if (response.redirected || response.url.includes('/login')) {
            window.location.href = '/login';
            return;
        }
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const stats = await response.json();
        console.log('Stats loaded:', stats);
        
        document.getElementById('stat-applications').textContent = stats.applications || 0;
        document.getElementById('stat-snapshots').textContent = stats.snapshots || 0;
        document.getElementById('stat-clusters').textContent = stats.storageClusters || 0;
        document.getElementById('stat-plans').textContent = stats.protectionPlans || 0;
    } catch (error) {
        console.error('Error loading stats:', error);
    }
}

async function loadApplications() {
    const loadingEl = document.getElementById('applications-loading');
    const contentEl = document.getElementById('applications-content');
    
    try {
        loadingEl.style.display = 'block';
        contentEl.innerHTML = '';
        
        const response = await fetch('/api/applications');
        
        // Check if we got redirected to login
        if (response.redirected || response.url.includes('/login')) {
            window.location.href = '/login';
            return;
        }
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        console.log('Applications loaded:', data.length, 'items');
        
        // Get unique namespaces for logging
        const namespaces = new Set(data.map(app => app.namespace));
        console.log('Namespaces found:', Array.from(namespaces).sort());
        
        allData.applications = data;
        populateNamespaceFilter();
        applyFilters('applications');
    } catch (error) {
        console.error('Error loading applications:', error);
        contentEl.innerHTML = '<div class="empty-state">Error loading applications</div>';
    } finally {
        loadingEl.style.display = 'none';
    }
}

async function loadSnapshots() {
    const loadingEl = document.getElementById('snapshots-loading');
    const contentEl = document.getElementById('snapshots-content');
    
    try {
        loadingEl.style.display = 'block';
        contentEl.innerHTML = '';
        
        const response = await fetch('/api/snapshots');
        
        // Check if we got redirected to login
        if (response.redirected || response.url.includes('/login')) {
            window.location.href = '/login';
            return;
        }
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        console.log('Snapshots loaded:', data.length, 'items');
        
        allData.snapshots = data;
        renderData('snapshots', data);
    } catch (error) {
        console.error('Error loading snapshots:', error);
        contentEl.innerHTML = '<div class="empty-state">Error loading snapshots</div>';
    } finally {
        loadingEl.style.display = 'none';
    }
}

async function loadStorageClusters() {
    const loadingEl = document.getElementById('storageclusters-loading');
    const contentEl = document.getElementById('storageclusters-content');
    
    try {
        loadingEl.style.display = 'block';
        contentEl.innerHTML = '';
        
        const response = await fetch('/api/storageclusters');
        
        if (response.redirected || response.url.includes('/login')) {
            window.location.href = '/login';
            return;
        }
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        console.log('Storage clusters loaded:', data.length, 'items');
        
        allData.storageclusters = data;
        renderData('storageclusters', data);
    } catch (error) {
        console.error('Error loading storage clusters:', error);
        contentEl.innerHTML = '<div class="empty-state">Error loading storage clusters</div>';
    } finally {
        loadingEl.style.display = 'none';
    }
}

async function loadProtectionPlans() {
    const loadingEl = document.getElementById('protectionplans-loading');
    const contentEl = document.getElementById('protectionplans-content');
    
    try {
        loadingEl.style.display = 'block';
        contentEl.innerHTML = '';
        
        const response = await fetch('/api/protectionplans');
        
        if (response.redirected || response.url.includes('/login')) {
            window.location.href = '/login';
            return;
        }
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        console.log('Protection plans loaded:', data.length, 'items');
        
        allData.protectionplans = data;
        renderData('protectionplans', data);
    } catch (error) {
        console.error('Error loading protection plans:', error);
        contentEl.innerHTML = '<div class="empty-state">Error loading protection plans</div>';
    } finally {
        loadingEl.style.display = 'none';
    }
}

// Data Rendering
function renderData(type, data) {
    const contentEl = document.getElementById(`${type}-content`);
    
    if (!data || data.length === 0) {
        contentEl.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">📭</div>
                <p>No ${type} found</p>
            </div>
        `;
        return;
    }
    
    switch(type) {
        case 'applications':
            renderApplications(data, contentEl);
            break;
        case 'snapshots':
            renderSnapshots(data, contentEl);
            break;
        case 'storageclusters':
            renderStorageClusters(data, contentEl);
            break;
        case 'protectionplans':
            renderProtectionPlans(data, contentEl);
            break;
    }
}

function renderApplications(data, container) {
    const bulkActionsHtml = data.length > 0 ? `
        <div class="bulk-actions" id="bulk-actions" style="display: none;">
            <span id="selected-count">0 selected</span>
            <button class="btn-bulk" onclick="bulkCreateSnapshots()">📸 Create Snapshots</button>
            <button class="btn-bulk-cancel" onclick="clearSelection()">✕ Clear</button>
        </div>
    ` : '';
    
    const html = `
        ${bulkActionsHtml}
        <div class="data-table">
            <table>
                <thead>
                    <tr>
                        <th><input type="checkbox" id="select-all-apps" onchange="toggleSelectAll(this)"></th>
                        <th>Name</th>
                        <th>Namespace</th>
                        <th>Status</th>
                        <th>Last Snapshot</th>
                        <th>Created</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
                    ${data.map(app => {
                        const appName = app.name || 'Unknown';
                        const appNamespace = app.namespace || 'default';
                        const appState = app.state || 'Unknown';
                        const appLastSnapshot = app.lastSnapshot || null;
                        const appCreated = app.created || null;
                        
                        const appId = `${appName}:${appNamespace}`;
                        const isChecked = selectedApplications.has(appId) ? 'checked' : '';
                        return `
                        <tr>
                            <td><input type="checkbox" class="app-checkbox" data-app-name="${escapeHtml(appName)}" data-app-namespace="${escapeHtml(appNamespace)}" onchange="toggleAppSelection(this)" ${isChecked}></td>
                            <td><strong>${escapeHtml(appName)}</strong></td>
                            <td>${escapeHtml(appNamespace)}</td>
                            <td>${getStatusBadge(appState)}</td>
                            <td>${formatDate(appLastSnapshot)}</td>
                            <td>${formatDate(appCreated)}</td>
                            <td>
                                <button class="btn-snapshot" onclick="showSnapshotModal('${escapeHtml(appName)}', '${escapeHtml(appNamespace)}')" title="Create Snapshot">
                                    📸 Snapshot
                                </button>
                            </td>
                        </tr>
                    `}).join('')}
                </tbody>
            </table>
        </div>
    `;
    container.innerHTML = html;
}

function renderSnapshots(data, container) {
    const html = `
        <div class="bulk-actions-bar" id="snapshot-bulk-actions" style="display: none;">
            <div class="selection-info">
                <span id="snapshot-selected-count">0 selected</span>
            </div>
            <div class="actions">
                <button class="btn btn-danger btn-sm" onclick="deleteBulkSnapshots()">🗑️ Delete Selected</button>
                <button class="btn btn-secondary btn-sm" onclick="clearSnapshotSelection()">Clear Selection</button>
            </div>
        </div>
        <div class="data-table">
            <table>
                <thead>
                    <tr>
                        <th><input type="checkbox" id="select-all-snapshots" onchange="toggleAllSnapshots(this.checked)"></th>
                        <th>Name</th>
                        <th>Application</th>
                        <th>Namespace</th>
                        <th>Status</th>
                        <th>Expires After</th>
                        <th>Created</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
                    ${data.map(snap => {
                        const snapName = snap.name || 'Unknown';
                        const snapNamespace = snap.namespace || 'default';
                        const snapApplication = snap.application || 'Unknown';
                        const snapState = snap.state || 'Unknown';
                        const snapExpires = snap.expiresAfter || snap.retentionPeriod || 'Not set';
                        const snapCreated = snap.created || null;
                        
                        return `
                        <tr>
                            <td><input type="checkbox" class="snapshot-checkbox" data-name="${escapeHtml(snapName)}" data-namespace="${escapeHtml(snapNamespace)}" onchange="updateSnapshotSelection()"></td>
                            <td><strong>${escapeHtml(snapName)}</strong></td>
                            <td>${escapeHtml(snapApplication)}</td>
                            <td>${escapeHtml(snapNamespace)}</td>
                            <td>${getStatusBadge(snapState)}</td>
                            <td>${escapeHtml(snapExpires)}</td>
                            <td>${formatDate(snapCreated)}</td>
                            <td>
                                <button class="btn-action btn-restore" onclick="showRestoreModal('${escapeHtml(snapName)}', '${escapeHtml(snapNamespace)}', '${escapeHtml(snapApplication)}')" title="Restore from snapshot" ${snapState !== 'Ready' ? 'disabled' : ''}>
                                    ↻ Restore
                                </button>
                                <button class="btn-action btn-delete" onclick="deleteSnapshot('${escapeHtml(snapName)}', '${escapeHtml(snapNamespace)}')" title="Delete snapshot">
                                    🗑️ Delete
                                </button>
                            </td>
                        </tr>
                    `}).join('')}
                </tbody>
            </table>
        </div>
    `;
    container.innerHTML = html;
}

function renderStorageClusters(data, container) {
    const html = `
        <div class="data-table">
            <table>
                <thead>
                    <tr>
                        <th>Name</th>
                        <th>Prism Central</th>
                        <th>PRISM ELEMENT UUID</th>
                        <th>Status</th>
                        <th>Created</th>
                    </tr>
                </thead>
                <tbody>
                    ${data.map(cluster => `
                        <tr>
                            <td><strong>${escapeHtml(cluster.name)}</strong></td>
                            <td>${escapeHtml(cluster.prismCentral)}</td>
                            <td><span class="code">${escapeHtml(cluster.storageServerUUID)}</span></td>
                            <td>${getStatusBadge(cluster.state)}</td>
                            <td>${formatDate(cluster.created)}</td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        </div>
    `;
    container.innerHTML = html;
}

function renderProtectionPlans(data, container) {
    const html = `
        <div class="data-table">
            <table>
                <thead>
                    <tr>
                        <th>Name</th>
                        <th>Namespace</th>
                        <th>Schedule</th>
                        <th>Retention</th>
                        <th>Status</th>
                        <th>Last Execution</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
                    ${data.map(plan => {
                        // NDK uses 'suspend' field: suspend=true means disabled, suspend=false means enabled
                        const isEnabled = plan.suspend !== true;
                        const statusClass = isEnabled ? 'active' : 'inactive';
                        const toggleText = isEnabled ? '⏸ Disable' : '▶ Enable';
                        const toggleClass = isEnabled ? 'enabled' : '';
                        
                        // Safely handle potentially undefined values
                        const planName = plan.name || 'Unknown';
                        const planNamespace = plan.namespace || 'default';
                        const planSchedule = plan.schedule || 'Not set';
                        const planRetention = plan.retention || 'Not set';
                        const planLastExecution = plan.lastExecution || 'Never';
                        
                        return `
                        <tr>
                            <td><strong>${escapeHtml(planName)}</strong></td>
                            <td>${escapeHtml(planNamespace)}</td>
                            <td>${escapeHtml(formatCronSchedule(planSchedule))}</td>
                            <td>${escapeHtml(formatRetention(planRetention))}</td>
                            <td><span class="plan-status ${statusClass}">${isEnabled ? 'Active' : 'Disabled'}</span></td>
                            <td>${formatDate(planLastExecution)}</td>
                            <td>
                                <div class="action-buttons">
                                    <button class="btn-trigger" onclick="triggerPlan('${escapeHtml(planName)}', '${escapeHtml(planNamespace)}')" title="Trigger Now">
                                        ⚡ Trigger
                                    </button>
                                    <button class="btn-toggle ${toggleClass}" onclick="togglePlan('${escapeHtml(planName)}', '${escapeHtml(planNamespace)}', ${!isEnabled})" title="${isEnabled ? 'Disable' : 'Enable'} Plan">
                                        ${toggleText}
                                    </button>
                                    <button class="btn-history" onclick="showPlanHistory('${escapeHtml(planName)}', '${escapeHtml(planNamespace)}')" title="View History">
                                        📊 History
                                    </button>
                                    <button class="btn-delete" onclick="deletePlan('${escapeHtml(planName)}', '${escapeHtml(planNamespace)}')" title="Delete Plan">
                                        🗑️ Delete
                                    </button>
                                </div>
                            </td>
                        </tr>
                    `}).join('')}
                </tbody>
            </table>
        </div>
    `;
    container.innerHTML = html;
}

function formatRetention(retention) {
    if (!retention || retention === 'Not set') return 'Not set';
    
    // If it's a number, assume it's count
    if (typeof retention === 'number') {
        return `Last ${retention} snapshots`;
    }
    
    // If it's a string, check if it's duration or count
    const str = String(retention);
    if (str.includes('h')) {
        const hours = parseInt(str);
        if (hours >= 8760) return `${hours / 8760} year(s)`;
        if (hours >= 720) return `${hours / 720} month(s)`;
        if (hours >= 168) return `${hours / 168} week(s)`;
        if (hours >= 24) return `${hours / 24} day(s)`;
        return `${hours} hour(s)`;
    }
    
    return str;
}

function formatCronSchedule(cronExpression) {
    if (!cronExpression || cronExpression === 'Not set') return 'Not set';
    
    // Parse cron expression: minute hour day month weekday
    const parts = cronExpression.trim().split(/\s+/);
    if (parts.length < 5) return cronExpression; // Invalid cron, return as-is
    
    const [minute, hour, day, month, weekday] = parts;
    
    // Common patterns
    // Daily at specific time: "0 2 * * *" -> "Daily at 2:00 AM"
    if (day === '*' && month === '*' && weekday === '*') {
        const hourNum = parseInt(hour);
        const minuteNum = parseInt(minute);
        const period = hourNum >= 12 ? 'PM' : 'AM';
        const displayHour = hourNum === 0 ? 12 : hourNum > 12 ? hourNum - 12 : hourNum;
        const displayMinute = minuteNum.toString().padStart(2, '0');
        return `Daily at ${displayHour}:${displayMinute} ${period}`;
    }
    
    // Weekly on specific day: "0 2 * * 0" -> "Weekly on Sunday at 2:00 AM"
    if (day === '*' && month === '*' && weekday !== '*') {
        const days = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
        const dayName = days[parseInt(weekday)] || `day ${weekday}`;
        const hourNum = parseInt(hour);
        const minuteNum = parseInt(minute);
        const period = hourNum >= 12 ? 'PM' : 'AM';
        const displayHour = hourNum === 0 ? 12 : hourNum > 12 ? hourNum - 12 : hourNum;
        const displayMinute = minuteNum.toString().padStart(2, '0');
        return `Weekly on ${dayName} at ${displayHour}:${displayMinute} ${period}`;
    }
    
    // Monthly on specific day: "0 2 15 * *" -> "Monthly on day 15 at 2:00 AM"
    if (day !== '*' && month === '*' && weekday === '*') {
        const hourNum = parseInt(hour);
        const minuteNum = parseInt(minute);
        const period = hourNum >= 12 ? 'PM' : 'AM';
        const displayHour = hourNum === 0 ? 12 : hourNum > 12 ? hourNum - 12 : hourNum;
        const displayMinute = minuteNum.toString().padStart(2, '0');
        return `Monthly on day ${day} at ${displayHour}:${displayMinute} ${period}`;
    }
    
    // Hourly: "0 * * * *" -> "Every hour"
    if (minute !== '*' && hour === '*' && day === '*' && month === '*' && weekday === '*') {
        if (minute === '0') {
            return 'Every hour';
        } else {
            return `Every hour at :${minute.padStart(2, '0')}`;
        }
    }
    
    // Every X hours: "0 */6 * * *" -> "Every 6 hours"
    if (hour.startsWith('*/')) {
        const hours = hour.substring(2);
        return `Every ${hours} hours`;
    }
    
    // Every X minutes: "*/15 * * * *" -> "Every 15 minutes"
    if (minute.startsWith('*/')) {
        const minutes = minute.substring(2);
        return `Every ${minutes} minutes`;
    }
    
    // If we can't parse it nicely, return the original
    return cronExpression;
}

// Utility Functions
function getStatusBadge(status) {
    if (!status) return '<span class="status-badge status-unknown">Unknown</span>';
    
    const statusLower = status.toLowerCase();
    let className = 'status-unknown';
    
    if (statusLower.includes('ready') || statusLower.includes('active') || statusLower.includes('completed')) {
        className = 'status-ready';
    } else if (statusLower.includes('pending') || statusLower.includes('creating')) {
        className = 'status-pending';
    } else if (statusLower.includes('failed') || statusLower.includes('error')) {
        className = 'status-failed';
    }
    
    return `<span class="status-badge ${className}">${escapeHtml(status)}</span>`;
}

function formatDate(dateString) {
    if (!dateString || dateString === 'Never' || dateString === 'Not set') {
        return dateString || '-';
    }
    
    try {
        const date = new Date(dateString);
        const now = new Date();
        const diffMs = now - date;
        const diffMins = Math.floor(diffMs / 60000);
        const diffHours = Math.floor(diffMs / 3600000);
        const diffDays = Math.floor(diffMs / 86400000);
        
        if (diffMins < 1) return 'Just now';
        if (diffMins < 60) return `${diffMins}m ago`;
        if (diffHours < 24) return `${diffHours}h ago`;
        if (diffDays < 7) return `${diffDays}d ago`;
        
        return date.toLocaleDateString();
    } catch (error) {
        return dateString;
    }
}

function escapeHtml(text) {
    // Handle null, undefined, and non-string values
    if (text === null || text === undefined) return '';
    if (typeof text !== 'string') return String(text);
    
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return text.replace(/[&<>"']/g, m => map[m]);
}

function updateLastUpdated() {
    const lastUpdatedEl = document.getElementById('last-updated');
    if (lastUpdatedEl) {
        lastUpdatedEl.textContent = new Date().toLocaleTimeString();
    }
}

function showToast(message, type = 'info') {
    // Create toast element
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    
    // Add to body
    document.body.appendChild(toast);
    
    // Show toast
    setTimeout(() => toast.classList.add('show'), 10);
    
    // Remove after 3 seconds
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// Snapshot Creation with Modal
function showSnapshotModal(appName, namespace) {
    const modal = document.getElementById('snapshot-modal');
    document.getElementById('snapshot-app-name').textContent = appName;
    document.getElementById('snapshot-app-name-hidden').value = appName;
    document.getElementById('snapshot-namespace-hidden').value = namespace;
    modal.style.display = 'flex';
}

function closeSnapshotModal() {
    const modal = document.getElementById('snapshot-modal');
    modal.style.display = 'none';
    document.getElementById('snapshot-expiration').value = '720h';
}

async function createSnapshotWithExpiration() {
    const appName = document.getElementById('snapshot-app-name-hidden').value;
    const namespace = document.getElementById('snapshot-namespace-hidden').value;
    const expiresAfter = document.getElementById('snapshot-expiration').value;
    
    closeSnapshotModal();
    
    try {
        const response = await fetch('/api/snapshots', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                applicationName: appName,
                namespace: namespace,
                expiresAfter: expiresAfter
            })
        });
        
        // Check if we got redirected to login
        if (response.redirected || response.url.includes('/login')) {
            console.log('Session expired, redirecting to login');
            window.location.href = '/login';
            return;
        }
        
        if (!response.ok) {
            const result = await response.json();
            showToast(`✗ Failed to create snapshot: ${result.error}`, 'error');
            return;
        }
        
        const result = await response.json();
        console.log('Snapshot created:', result);
        showToast(`✓ Snapshot created: ${result.snapshot.name}`, 'success');
         // Reload data immediately
        await Promise.all([
            loadSnapshots(),
            loadStats()
       
        ]);
    } catch (error) {
        console.error('Error creating snapshot:', error);
        showToast('✗ Error creating snapshot', 'error');
    }
}

// Snapshot Deletion
async function deleteSnapshot(name, namespace) {
    if (!confirm(`Are you sure you want to delete snapshot "${name}"?\n\nThis action cannot be undone.`)) {
        return;
    }
    
    try {
        const response = await fetch(`/api/snapshots/${namespace}/${name}`, {
            method: 'DELETE'
        });
        
        // Check if we got redirected to login
        if (response.redirected || response.url.includes('/login')) {
            console.log('Session expired, redirecting to login');
            window.location.href = '/login';
            return;
        }
        
        if (!response.ok) {
            const result = await response.json();
            showToast(`✗ Failed to delete snapshot: ${result.error}`, 'error');
            return;
        }
        
        const result = await response.json();
        console.log('Snapshot deleted:', name);
        showToast(`✓ Snapshot deleted: ${name}`, 'success');
        
        // Reload data immediately
        await Promise.all([
            loadSnapshots(),
            loadStats()
        ]);
    } catch (error) {
        console.error('Error deleting snapshot:', error);
        showToast('✗ Error deleting snapshot', 'error');
    }
}

// Bulk Snapshot Selection
function toggleAllSnapshots(checked) {
    const checkboxes = document.querySelectorAll('.snapshot-checkbox');
    checkboxes.forEach(cb => cb.checked = checked);
    updateSnapshotSelection();
}

function updateSnapshotSelection() {
    const checkboxes = document.querySelectorAll('.snapshot-checkbox');
    const checked = Array.from(checkboxes).filter(cb => cb.checked);
    const count = checked.length;
    
    const bulkActionsBar = document.getElementById('snapshot-bulk-actions');
    const countSpan = document.getElementById('snapshot-selected-count');
    
    if (count > 0) {
        bulkActionsBar.style.display = 'flex';
        countSpan.textContent = `${count} selected`;
    } else {
        bulkActionsBar.style.display = 'none';
    }
    
    // Update select-all checkbox state
    const selectAllCheckbox = document.getElementById('select-all-snapshots');
    if (selectAllCheckbox) {
        selectAllCheckbox.checked = count === checkboxes.length && count > 0;
        selectAllCheckbox.indeterminate = count > 0 && count < checkboxes.length;
    }
}

function clearSnapshotSelection() {
    const checkboxes = document.querySelectorAll('.snapshot-checkbox');
    checkboxes.forEach(cb => cb.checked = false);
    updateSnapshotSelection();
}

async function deleteBulkSnapshots() {
    const checkboxes = document.querySelectorAll('.snapshot-checkbox:checked');
    const snapshots = Array.from(checkboxes).map(cb => ({
        name: cb.dataset.name,
        namespace: cb.dataset.namespace
    }));
    
    if (snapshots.length === 0) {
        showToast('✗ No snapshots selected', 'error');
        return;
    }
    
    if (!confirm(`Are you sure you want to delete ${snapshots.length} snapshot(s)?\n\nThis action cannot be undone.`)) {
        return;
    }
    
    let successCount = 0;
    let failCount = 0;
    
    showToast(`Deleting ${snapshots.length} snapshot(s)...`, 'info');
    
    for (const snapshot of snapshots) {
        try {
            const response = await fetch(`/api/snapshots/${snapshot.namespace}/${snapshot.name}`, {
                method: 'DELETE'
            });
            
            // Check if we got redirected to login
            if (response.redirected || response.url.includes('/login')) {
                console.log('Session expired, redirecting to login');
                window.location.href = '/login';
                return;
            }
            
            if (response.ok) {
                successCount++;
                console.log('Snapshot deleted:', snapshot.name);
            } else {
                failCount++;
                console.error('Failed to delete snapshot:', snapshot.name);
            }
        } catch (error) {
            failCount++;
            console.error('Error deleting snapshot:', snapshot.name, error);
        }
    }
    
    // Show result
    if (successCount > 0 && failCount === 0) {
        showToast(`✓ Successfully deleted ${successCount} snapshot(s)`, 'success');
    } else if (successCount > 0 && failCount > 0) {
        showToast(`⚠ Deleted ${successCount} snapshot(s), ${failCount} failed`, 'warning');
    } else {
        showToast(`✗ Failed to delete snapshots`, 'error');
    }
    
    // Clear selection and reload data
    clearSnapshotSelection();
    await Promise.all([
        loadSnapshots(),
        loadStats()
    ]);
}

// Snapshot Restore
function showRestoreModal(snapshotName, namespace, appName) {
    const modal = document.getElementById('restore-modal');
    document.getElementById('restore-snapshot-name').textContent = snapshotName;
    document.getElementById('restore-snapshot-name-hidden').value = snapshotName;
    document.getElementById('restore-namespace-hidden').value = namespace;
    document.getElementById('restore-name').value = `${appName}-restore-${Date.now()}`;
    document.getElementById('restore-target-namespace').value = namespace;
    modal.style.display = 'flex';
}

function closeRestoreModal() {
    const modal = document.getElementById('restore-modal');
    modal.style.display = 'none';
}

async function restoreSnapshot() {
    const snapshotName = document.getElementById('restore-snapshot-name-hidden').value;
    const namespace = document.getElementById('restore-namespace-hidden').value;
    const restoreName = document.getElementById('restore-name').value;
    const targetNamespace = document.getElementById('restore-target-namespace').value;
    
    if (!restoreName) {
        showToast('✗ Restore name is required', 'error');
        return;
    }
    
    closeRestoreModal();
    
    try {
        const response = await fetch(`/api/snapshots/${namespace}/${snapshotName}/restore`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                restoreName: restoreName,
                targetNamespace: targetNamespace
            })
        });
        
        // Check if we got redirected to login
        if (response.redirected || response.url.includes('/login')) {
            console.log('Session expired, redirecting to login');
            window.location.href = '/login';
            return;
        }
        
        if (!response.ok) {
            const result = await response.json();
            showToast(`✗ Failed to restore snapshot: ${result.error}`, 'error');
            return;
        }
        
        const result = await response.json();
        console.log('Restore initiated:', result);
        showToast(`✓ Restore initiated: ${result.restore.name}`, 'success');
        
        // Reload data immediately
        await Promise.all([
            loadApplications(),
            loadStats()
        ]);
    } catch (error) {
        console.error('Error restoring snapshot:', error);
        showToast('✗ Error restoring snapshot', 'error');
    }
}

// Bulk Operations
function toggleSelectAll(checkbox) {
    const checkboxes = document.querySelectorAll('.app-checkbox');
    checkboxes.forEach(cb => {
        cb.checked = checkbox.checked;
        const appName = cb.dataset.appName;
        const appNamespace = cb.dataset.appNamespace;
        const appId = `${appName}:${appNamespace}`;
        
        if (checkbox.checked) {
            selectedApplications.add(appId);
        } else {
            selectedApplications.delete(appId);
        }
    });
    updateBulkActionsVisibility();
}

function toggleAppSelection(checkbox) {
    const appName = checkbox.dataset.appName;
    const appNamespace = checkbox.dataset.appNamespace;
    const appId = `${appName}:${appNamespace}`;
    
    if (checkbox.checked) {
        selectedApplications.add(appId);
    } else {
        selectedApplications.delete(appId);
    }
    
    updateBulkActionsVisibility();
}

function updateBulkActionsVisibility() {
    const bulkActions = document.getElementById('bulk-actions');
    const selectedCount = document.getElementById('selected-count');
    const selectAllCheckbox = document.getElementById('select-all-apps');
    
    if (bulkActions && selectedCount) {
        if (selectedApplications.size > 0) {
            bulkActions.style.display = 'flex';
            selectedCount.textContent = `${selectedApplications.size} selected`;
        } else {
            bulkActions.style.display = 'none';
        }
    }
    
    // Update select-all checkbox state
    if (selectAllCheckbox) {
        const checkboxes = document.querySelectorAll('.app-checkbox');
        const allChecked = checkboxes.length > 0 && Array.from(checkboxes).every(cb => cb.checked);
        selectAllCheckbox.checked = allChecked;
    }
}

function clearSelection() {
    selectedApplications.clear();
    const checkboxes = document.querySelectorAll('.app-checkbox');
    checkboxes.forEach(cb => cb.checked = false);
    const selectAllCheckbox = document.getElementById('select-all-apps');
    if (selectAllCheckbox) selectAllCheckbox.checked = false;
    updateBulkActionsVisibility();
}

function showBulkSnapshotModal() {
    const modal = document.getElementById('bulk-snapshot-modal');
    document.getElementById('bulk-selected-count').textContent = selectedApplications.size;
    modal.style.display = 'flex';
}

function closeBulkSnapshotModal() {
    const modal = document.getElementById('bulk-snapshot-modal');
    modal.style.display = 'none';
    document.getElementById('bulk-snapshot-expiration').value = '720h';
}

async function bulkCreateSnapshots() {
    if (selectedApplications.size === 0) {
        showToast('✗ No applications selected', 'error');
        return;
    }
    
    showBulkSnapshotModal();
}

async function createBulkSnapshotsWithExpiration() {
    const expiresAfter = document.getElementById('bulk-snapshot-expiration').value;
    
    closeBulkSnapshotModal();
    
    const applications = Array.from(selectedApplications).map(appId => {
        const [name, namespace] = appId.split(':');
        return { name, namespace };
    });
    
    try {
        showToast(`Creating ${applications.length} snapshots...`, 'info');
        
        const response = await fetch('/api/snapshots/bulk', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                applications: applications,
                expiresAfter: expiresAfter
            })
        });
        // Check if we got redirected to login
        if (response.redirected || response.url.includes('/login')) {
            console.log('Session expired, redirecting to login');
            window.location.href = '/login';
            return;
        }
        
        if (!response.ok) {
            const result = await response.json();
            showToast(`✗ Failed to create snapshots: ${result.error}`, 'error');
            return;
        }
        
        const result = await response.json();
        console.log('Bulk snapshots created:', result);
        
        
        const successCount = result.results.success.length;
        const failedCount = result.results.failed.length;
        
        if (failedCount === 0) {
            showToast(`✓ Created ${successCount} snapshots successfully`, 'success');
        } else {
            showToast(`⚠ Created ${successCount} snapshots, ${failedCount} failed`, 'error');
        }
        
        clearSelection();
        
        // Reload data immediately
        await Promise.all([
            loadSnapshots(),
            loadStats()
        ]);
    } catch (error) {
        console.error('Error creating bulk snapshots:', error);
        showToast('✗ Error creating bulk snapshots', 'error');
    }
}

// ============================================
// Protection Plan Management Functions
// ============================================

async function showCreatePlanModal() {
    document.getElementById('plan-modal-title').textContent = '🛡️ Create Protection Plan';
    document.getElementById('plan-save-text').textContent = 'Create Plan';
    
    // Reset form
    document.getElementById('plan-name').value = '';
    document.getElementById('plan-namespace').value = 'default';
    document.getElementById('plan-schedule-type').value = 'preset';
    document.getElementById('plan-schedule-preset').value = '0 2 * * *';
    document.getElementById('plan-schedule-custom').value = '';
    document.getElementById('plan-retention-type').value = 'count';
    document.getElementById('plan-retention-count').value = '7';
    document.getElementById('plan-retention-duration').value = '168h';
    document.getElementById('plan-selector-type').value = 'label';
    document.getElementById('plan-selector-label-key').value = '';
    document.getElementById('plan-selector-label-value').value = '';
    document.getElementById('plan-selector-name').value = '';
    document.getElementById('plan-enabled').checked = true;
    
    updateScheduleInput();
    updateRetentionInput();
    updateSelectorInput();
    
    // Load namespaces for the dropdown
    await loadPlanNamespaces();
    
    document.getElementById('plan-modal').style.display = 'flex';
}

function closePlanModal() {
    document.getElementById('plan-modal').style.display = 'none';
}

function updateScheduleInput() {
    const scheduleType = document.getElementById('plan-schedule-type').value;
    const presetGroup = document.getElementById('plan-schedule-preset-group');
    const customGroup = document.getElementById('plan-schedule-custom-group');
    
    if (scheduleType === 'preset') {
        presetGroup.style.display = 'block';
        customGroup.style.display = 'none';
    } else {
        presetGroup.style.display = 'none';
        customGroup.style.display = 'block';
    }
}

function updateRetentionInput() {
    const retentionType = document.getElementById('plan-retention-type').value;
    const countGroup = document.getElementById('plan-retention-count-group');
    const durationGroup = document.getElementById('plan-retention-duration-group');
    
    if (retentionType === 'count') {
        countGroup.style.display = 'block';
        durationGroup.style.display = 'none';
    } else {
        countGroup.style.display = 'none';
        durationGroup.style.display = 'block';
    }
}

function updateSelectorInput() {
    const selectorType = document.getElementById('plan-selector-type').value;
    const labelGroup = document.getElementById('plan-selector-label-group');
    const nameGroup = document.getElementById('plan-selector-name-group');
    
    if (selectorType === 'label') {
        labelGroup.style.display = 'block';
        nameGroup.style.display = 'none';
    } else {
        labelGroup.style.display = 'none';
        nameGroup.style.display = 'block';
    }
}

async function savePlan() {
    const name = document.getElementById('plan-name').value.trim();
    const namespace = document.getElementById('plan-namespace').value.trim();
    
    if (!name || !namespace) {
        showToast('✗ Plan name and namespace are required', 'error');
        return;
    }
    
    // Get schedule
    const scheduleType = document.getElementById('plan-schedule-type').value;
    const schedule = scheduleType === 'preset' 
        ? document.getElementById('plan-schedule-preset').value
        : document.getElementById('plan-schedule-custom').value.trim();
    
    if (!schedule) {
        showToast('✗ Schedule is required', 'error');
        return;
    }
    
    // Get retention
    const retentionType = document.getElementById('plan-retention-type').value;
    const retention = retentionType === 'count'
        ? parseInt(document.getElementById('plan-retention-count').value)
        : document.getElementById('plan-retention-duration').value;
    
    // Get selector
    const selectorType = document.getElementById('plan-selector-type').value;
    let selector = {};
    
    if (selectorType === 'label') {
        const key = document.getElementById('plan-selector-label-key').value.trim();
        const value = document.getElementById('plan-selector-label-value').value.trim();
        
        if (!key || !value) {
            showToast('✗ Label key and value are required', 'error');
            return;
        }
        
        selector = {
            matchLabels: {
                [key]: value
            }
        };
    } else {
        const appName = document.getElementById('plan-selector-name').value.trim();
        
        if (!appName) {
            showToast('✗ Application name is required', 'error');
            return;
        }
        
        selector = {
            matchLabels: {
                'app.kubernetes.io/name': appName
            }
        };
    }
    
    const enabled = document.getElementById('plan-enabled').checked;
    
    const planData = {
        name: name,
        namespace: namespace,
        schedule: schedule,
        retention: retention,
        selector: selector,
        enabled: enabled
    };
    
    try {
        showToast('Creating protection plan...', 'info');
        
        const response = await fetch('/api/protectionplans', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(planData)
        });
        // Check if we got redirected to login
        if (response.redirected || response.url.includes('/login')) {
            console.log('Session expired, redirecting to login');
            window.location.href = '/login';
            return;
        }
        
        if (!response.ok) {
            const result = await response.json();
            showToast(`✗ Failed: ${result.error}`, 'error');
            return;
        }
        
        const result = await response.json();
        console.log('Protection plan created:', result);
        showToast('✓ Protection plan created successfully', 'success');
        closePlanModal();
        
        // Reload data immediately
        await Promise.all([
            loadProtectionPlans(),
            loadStats()
        ]);
    } catch (error) {
        console.error('Error saving protection plan:', error);
        showToast('✗ Error creating protection plan', 'error');
    }
}

async function deletePlan(name, namespace) {
    if (!confirm(`Are you sure you want to delete protection plan "${name}"?\n\nThis will not delete existing snapshots created by this plan.`)) {
        return;
    }
    
    try {
        showToast('Deleting protection plan...', 'info');
        
        const response = await fetch(`/api/protectionplans/${namespace}/${name}`, {
            method: 'DELETE'
        });
        
        // Check if we got redirected to login
        if (response.redirected || response.url.includes('/login')) {
            console.log('Session expired, redirecting to login');
            window.location.href = '/login';
            return;
        }
        
        if (!response.ok) {
            const result = await response.json();
            showToast(`✗ Failed to delete: ${result.error}`, 'error');
            return;
        }
        
        const result = await response.json();
        console.log('Protection plan deleted:', name);
        showToast('✓ Protection plan deleted successfully', 'success');
        
        // Reload data immediately
        await Promise.all([
            loadProtectionPlans(),
            loadStats()
        ]);
    } catch (error) {
        console.error('Error deleting protection plan:', error);
        showToast('✗ Error deleting protection plan', 'error');
    }
}

async function togglePlan(name, namespace, enable) {
    const action = enable ? 'enable' : 'disable';
    
    try {
        showToast(`${enable ? 'Enabling' : 'Disabling'} protection plan...`, 'info');
        
        const response = await fetch(`/api/protectionplans/${namespace}/${name}/${action}`, {
            method: 'POST'
        });
        
        // Check if we got redirected to login
        if (response.redirected || response.url.includes('/login')) {
            console.log('Session expired, redirecting to login');
            window.location.href = '/login';
            return;
        }
        
        if (!response.ok) {
            const result = await response.json();
            showToast(`✗ Failed to ${action}: ${result.error}`, 'error');
            return;
        }
        
        const result = await response.json();
        console.log(`Protection plan ${action}d:`, name);
        showToast(`✓ Protection plan ${enable ? 'enabled' : 'disabled'} successfully`, 'success');
        
        // Reload data immediately
        await loadProtectionPlans();
    } catch (error) {
        console.error(`Error ${action}ing protection plan:`, error);
        showToast(`✗ Error ${action}ing protection plan`, 'error');
    }
}

async function triggerPlan(name, namespace) {
    if (!confirm(`Trigger protection plan "${name}" now?\n\nThis will create a snapshot immediately, outside the regular schedule.`)) {
        return;
    }
    
    try {
        showToast('Triggering protection plan...', 'info');
        
        const response = await fetch(`/api/protectionplans/${namespace}/${name}/trigger`, {
            method: 'POST'
        });
        
        // Check if we got redirected to login
        if (response.redirected || response.url.includes('/login')) {
            console.log('Session expired, redirecting to login');
            window.location.href = '/login';
            return;
        }
        
        if (!response.ok) {
            const result = await response.json();
            showToast(`✗ Failed to trigger: ${result.error}`, 'error');
            return;
        }
        
        const result = await response.json();
        console.log('Protection plan triggered:', result);
        showToast('✓ Protection plan triggered successfully', 'success');
        
        // Wait a bit for snapshot to be created, then reload
        setTimeout(async () => {
            await Promise.all([
                loadSnapshots(),
                loadProtectionPlans()
            ]);
        }, 2000);
        
    } catch (error) {
        console.error('Error triggering protection plan:', error);
        showToast('✗ Error triggering protection plan', 'error');
    }
}

async function showPlanHistory(name, namespace) {
    document.getElementById('history-plan-name').textContent = name;
    document.getElementById('plan-history-modal').style.display = 'flex';
    document.getElementById('plan-history-loading').style.display = 'block';
    document.getElementById('plan-history-content').innerHTML = '';
    
    try {
        const response = await fetch(`/api/protectionplans/${namespace}/${name}/history`);
        
        // Check if we got redirected to login
        if (response.redirected || response.url.includes('/login')) {
            console.log('Session expired, redirecting to login');
            window.location.href = '/login';
            return;
        }
        
        document.getElementById('plan-history-loading').style.display = 'none';
        
        if (!response.ok) {
            document.getElementById('plan-history-content').innerHTML = 
                '<div class="empty-history">Failed to load history</div>';
            return;
        }
        
        const snapshots = await response.json();
        console.log('Plan history loaded:', snapshots.length, 'snapshots');
        
        if (snapshots.length === 0) {
            document.getElementById('plan-history-content').innerHTML = 
                '<div class="empty-history">No snapshots created by this plan yet</div>';
            return;
        }
        
        const html = `
            <div class="history-table">
                <table>
                    <thead>
                        <tr>
                            <th>Snapshot Name</th>
                            <th>Status</th>
                            <th>Created</th>
                            <th>Expires After</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${snapshots.map(snap => `
                            <tr>
                                <td><strong>${escapeHtml(snap.name)}</strong></td>
                                <td>${getStatusBadge(snap.state)}</td>
                                <td>${formatDate(snap.created)}</td>
                                <td>${escapeHtml(snap.expiresAfter || 'Not set')}</td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        `;
        
        document.getElementById('plan-history-content').innerHTML = html;
    } catch (error) {
        console.error('Error loading plan history:', error);
        document.getElementById('plan-history-loading').style.display = 'none';
        document.getElementById('plan-history-content').innerHTML = 
            '<div class="empty-history">Error loading history</div>';
    }
}

function closePlanHistoryModal() {
    document.getElementById('plan-history-modal').style.display = 'none';
}

// ===================================
// DEPLOY APPLICATION FUNCTIONS
// ===================================

const APP_TEMPLATES = {
    mysql: {
        title: '🐬 Deploy MySQL',
        image: 'mysql:8.0',
        port: 3306,
        passwordLabel: 'MySQL Root Password',
        hasDatabase: true
    },
    postgresql: {
        title: '🐘 Deploy PostgreSQL',
        image: 'postgres:15',
        port: 5432,
        passwordLabel: 'PostgreSQL Password',
        hasDatabase: true
    },
    mongodb: {
        title: '🍃 Deploy MongoDB',
        image: 'mongo:7.0',
        port: 27017,
        passwordLabel: 'MongoDB Root Password',
        hasDatabase: false
    },
    redis: {
        title: '🔴 Deploy Redis',
        image: 'redis:7.2',
        port: 6379,
        passwordLabel: 'Redis Password',
        hasDatabase: false
    },
    elasticsearch: {
        title: '🔍 Deploy Elasticsearch',
        image: 'elasticsearch:8.11.0',
        port: 9200,
        passwordLabel: 'Elastic Password',
        hasDatabase: false
    },
    cassandra: {
        title: '💎 Deploy Cassandra',
        image: 'cassandra:4.1',
        port: 9042,
        passwordLabel: 'Cassandra Password',
        hasDatabase: false
    }
};

async function loadNamespaces() {
    try {
        const response = await fetch('/api/namespaces');
        if (response.ok) {
            const data = await response.json();
            const select = document.getElementById('deploy-namespace-select');
            // Clear existing options except the custom one
            select.innerHTML = '';
            
            // Add all namespaces
            data.namespaces.forEach(ns => {
                const option = document.createElement('option');
                option.value = ns;
                option.textContent = ns;
                select.appendChild(option);
            });
            
            // Add "Create New" option at the end
            const customOption = document.createElement('option');
            customOption.value = '__custom__';
            customOption.textContent = '➕ Create New Namespace...';
            select.appendChild(customOption);
            
            // Set default as selected
            select.value = 'default';
        }
    } catch (error) {
        console.error('Failed to load namespaces:', error);
    }
}

function handleNamespaceChange() {
    const select = document.getElementById('deploy-namespace-select');
    const input = document.getElementById('deploy-namespace');
    
    if (select.value === '__custom__') {
        input.style.display = 'block';
        input.required = true;
        input.value = '';
        input.focus();
    } else {
        input.style.display = 'none';
        input.required = false;
        input.value = select.value;
    }
}

function handlePlanNamespaceChange() {
    const select = document.getElementById('plan-namespace-select');
    const input = document.getElementById('plan-namespace');
    
    if (select.value === '__custom__') {
        input.style.display = 'block';
        input.required = true;
        input.value = '';
        input.focus();
    } else {
        input.style.display = 'none';
        input.required = false;
        input.value = select.value;
    }
}

async function loadPlanNamespaces() {
    try {
        const response = await fetch('/api/namespaces');
        if (response.ok) {
            const data = await response.json();
            const select = document.getElementById('plan-namespace-select');
            
            // Clear existing options
            select.innerHTML = '';
            
            // Add all namespaces
            data.namespaces.forEach(ns => {
                const option = document.createElement('option');
                option.value = ns;
                option.textContent = ns;
                select.appendChild(option);
            });
            
            // Add "Create New" option at the end
            const customOption = document.createElement('option');
            customOption.value = '__custom__';
            customOption.textContent = '➕ Create New Namespace...';
            select.appendChild(customOption);
            
            // Set default as selected
            select.value = 'default';
        }
    } catch (error) {
        console.error('Failed to load namespaces for protection plan:', error);
    }
}

function showDeployModal(appType) {
    const template = APP_TEMPLATES[appType];
    if (!template) {
        alert('Unknown application type');
        return;
    }
    
    // Set modal title
    document.getElementById('deploy-modal-title').textContent = template.title;
    document.getElementById('deploy-app-type').value = appType;
    
    // Update password label
    document.querySelector('#deploy-password-group label').textContent = template.passwordLabel + ':';
    
    // Show/hide database field
    document.getElementById('deploy-database-group').style.display = 
        template.hasDatabase ? 'block' : 'none';
    
    // Reset form
    document.getElementById('deploy-name').value = '';
    document.getElementById('deploy-namespace-select').value = 'default';
    document.getElementById('deploy-namespace').value = 'default';
    document.getElementById('deploy-namespace').style.display = 'none';
    document.getElementById('deploy-replicas').value = '1';
    document.getElementById('deploy-storage-size').value = '10Gi';
    document.getElementById('deploy-password').value = '';
    document.getElementById('deploy-database').value = '';
    document.getElementById('deploy-create-ndk-app').checked = true;
    document.getElementById('deploy-create-protection-plan').checked = false;
    document.getElementById('deploy-protection-config').style.display = 'none';
    
    // Load namespaces for dropdown
    loadNamespaces();
    
    // Show modal
    document.getElementById('deploy-modal').style.display = 'flex';
}

function closeDeployModal() {
    document.getElementById('deploy-modal').style.display = 'none';
}

// Toggle protection plan configuration
document.addEventListener('DOMContentLoaded', function() {
    const protectionCheckbox = document.getElementById('deploy-create-protection-plan');
    if (protectionCheckbox) {
        protectionCheckbox.addEventListener('change', function() {
            document.getElementById('deploy-protection-config').style.display = 
                this.checked ? 'block' : 'none';
        });
    }
});

async function deployApplication() {
    const appType = document.getElementById('deploy-app-type').value;
    const name = document.getElementById('deploy-name').value.trim();
    const namespace = document.getElementById('deploy-namespace').value.trim();
    const replicas = parseInt(document.getElementById('deploy-replicas').value);
    const storageClass = document.getElementById('deploy-storage-class').value;
    const storageSize = document.getElementById('deploy-storage-size').value.trim();
    const password = document.getElementById('deploy-password').value;
    const database = document.getElementById('deploy-database').value.trim();
    const createNDKApp = document.getElementById('deploy-create-ndk-app').checked;
    const createProtectionPlan = document.getElementById('deploy-create-protection-plan').checked;
    
    // Validation
    if (!name) {
        alert('Please enter an application name');
        return;
    }
    
    if (!namespace) {
        alert('Please enter a namespace');
        return;
    }
    
    if (!/^[a-z0-9]([-a-z0-9]*[a-z0-9])?$/.test(name)) {
        alert('Application name must be lowercase alphanumeric characters or \'-\'');
        return;
    }
    
    const template = APP_TEMPLATES[appType];
    
    // Build deployment configuration
    const deployConfig = {
        appType: appType,
        name: name,
        namespace: namespace,
        replicas: replicas,
        storageClass: storageClass === 'default' ? null : storageClass,
        storageSize: storageSize,
        image: template.image,
        port: template.port,
        password: password || null,  // null means auto-generate
        database: database || null,
        createNDKApp: createNDKApp
    };
    
    // Add protection plan config if enabled
    if (createProtectionPlan) {
        deployConfig.protectionPlan = {
            schedule: document.getElementById('deploy-protection-schedule').value,
            retention: parseInt(document.getElementById('deploy-protection-retention').value)
        };
    }
    
    // Disable button and show loading
    const btnText = document.getElementById('deploy-btn-text');
    const originalText = btnText.textContent;
    btnText.textContent = '⏳ Deploying...';
    document.querySelector('#deploy-modal .btn-primary').disabled = true;
    
    try {
        const response = await fetch('/api/deploy', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(deployConfig)
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || 'Deployment failed');
        }
        
        const result = await response.json();
        
        alert(`✅ Application deployed successfully!\n\nApplication: ${name}\nNamespace: ${namespace}\n\n${result.message || 'Deployment is in progress.'}`);
        
        closeDeployModal();
        
        // Refresh applications tab
        await loadApplications();
        
        // Switch to applications tab
        switchTab('applications');
        
    } catch (error) {
        console.error('Deployment error:', error);
        alert(`❌ Deployment failed: ${error.message}`);
    } finally {
        btnText.textContent = originalText;
        document.querySelector('#deploy-modal .btn-primary').disabled = false;
    }
}