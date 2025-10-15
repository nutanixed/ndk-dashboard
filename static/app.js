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
let currentProtectionPlanFilter = 'all';

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    initializeTabs();
    initializeRefresh();
    initializeSearch();
    initializeNamespaceFilter();
    initializeProtectionPlanFilter();
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

// Protection Plan Filter Management
function initializeProtectionPlanFilter() {
    const planFilter = document.getElementById('protection-plan-filter');
    if (planFilter) {
        planFilter.addEventListener('change', function() {
            currentProtectionPlanFilter = this.value;
            applyFilters('snapshots');
        });
    }
}

function populateProtectionPlanFilter() {
    const planFilter = document.getElementById('protection-plan-filter');
    if (!planFilter || !allData.snapshots) return;
    
    // Get unique protection plans from snapshots
    const plans = new Set();
    allData.snapshots.forEach(snap => {
        if (snap.protectionPlan) {
            plans.add(snap.protectionPlan);
        }
    });
    
    // Sort plans alphabetically
    const sortedPlans = Array.from(plans).sort();
    
    // Preserve current selection
    const currentValue = planFilter.value;
    
    // Rebuild options
    planFilter.innerHTML = '<option value="all">All Protection Plans</option>';
    planFilter.innerHTML += '<option value="manual">Manual Snapshots Only</option>';
    sortedPlans.forEach(plan => {
        const option = document.createElement('option');
        option.value = plan;
        option.textContent = plan;
        planFilter.appendChild(option);
    });
    
    // Restore selection if it still exists
    if (currentValue && Array.from(planFilter.options).some(opt => opt.value === currentValue)) {
        planFilter.value = currentValue;
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
    
    // Apply protection plan filter for snapshots
    if (tabName === 'snapshots' && currentProtectionPlanFilter !== 'all') {
        if (currentProtectionPlanFilter === 'manual') {
            // Show only manual snapshots (no protection plan)
            data = data.filter(snap => !snap.protectionPlan);
        } else {
            // Show snapshots from specific protection plan
            data = data.filter(snap => snap.protectionPlan === currentProtectionPlanFilter);
        }
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
        // Load all resources in parallel (but NOT stats, to avoid cache conflicts)
        await Promise.all([
            loadApplications(),
            loadSnapshots(),
            loadStorageClusters(),
            loadProtectionPlans()
        ]);
        
        // Update stats from loaded data instead of making a separate API call
        updateStatsFromData();
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

function updateStatsFromData() {
    // Update stat counters from the loaded data
    document.getElementById('stat-applications').textContent = allData.applications?.length || 0;
    document.getElementById('stat-snapshots').textContent = allData.snapshots?.length || 0;
    document.getElementById('stat-clusters').textContent = allData.storageclusters?.length || 0;
    document.getElementById('stat-plans').textContent = allData.protectionplans?.length || 0;
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
        // Don't clear content immediately - keep old data visible during refresh
        
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
        updateStatsFromData();
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
        // Don't clear content immediately - keep old data visible during refresh
        
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
        populateProtectionPlanFilter();
        applyFilters('snapshots');
        updateStatsFromData();
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
        // Don't clear content immediately - keep old data visible during refresh
        
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
        updateStatsFromData();
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
        // Don't clear content immediately - keep old data visible during refresh
        
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
        updateStatsFromData();
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
                        <th style="width: 3%;"><input type="checkbox" id="select-all-apps" onchange="toggleSelectAll(this)"></th>
                        <th style="width: 14%;">Name</th>
                        <th style="width: 9%;">Namespace</th>
                        <th style="width: 7%;">Status</th>
                        <th style="width: 5%;">Replicas</th>
                        <th style="width: 6%;">Volume Groups</th>
                        <th style="width: 10%;">Service DNS</th>
                        <th style="width: 12%;">Labels</th>
                        <th style="width: 9%;">Last Snapshot</th>
                        <th style="width: 9%;">Created</th>
                        <th style="width: 16%;">Actions</th>
                    </tr>
                </thead>
                <tbody>
                    ${data.map(app => {
                        const appName = app.name || 'Unknown';
                        const appNamespace = app.namespace || 'default';
                        const appState = app.state || 'Unknown';
                        const appLastSnapshot = app.lastSnapshot || null;
                        const appCreated = app.created || null;
                        const appLabels = app.labels || {};
                        
                        // Format labels for display
                        const labelsHtml = Object.keys(appLabels).length > 0 
                            ? Object.entries(appLabels)
                                .map(([key, value]) => `<span class="label-badge">${escapeHtml(key)}=${escapeHtml(value)}</span>`)
                                .join(' ')
                            : '<span class="text-muted">No labels</span>';
                        
                        // Generate Service DNS
                        const serviceDnsShort = `${escapeHtml(appName)}.${escapeHtml(appNamespace)}`;
                        const serviceDnsFull = `${escapeHtml(appName)}.${escapeHtml(appNamespace)}.svc.cluster.local`;

                        const appId = `${appName}:${appNamespace}`;
                        const isChecked = selectedApplications.has(appId) ? 'checked' : '';
                        return `
                        <tr>
                            <td><input type="checkbox" class="app-checkbox" data-app-name="${escapeHtml(appName)}" data-app-namespace="${escapeHtml(appNamespace)}" onchange="toggleAppSelection(this)" ${isChecked}></td>
                            <td><strong>${escapeHtml(appName)}</strong></td>
                            <td>${escapeHtml(appNamespace)}</td>
                            <td>${getStatusBadge(appState)}</td>
                            <td>
                                <span class="replica-count" 
                                      data-app-name="${escapeHtml(appName)}" 
                                      data-app-namespace="${escapeHtml(appNamespace)}"
                                      onmouseenter="showReplicaTooltip(this, '${escapeHtml(appName)}', '${escapeHtml(appNamespace)}')"
                                      onmouseleave="scheduleHideReplicaTooltip()"
                                      style="cursor: pointer; position: relative;">
                                    <span class="replica-number">...</span>
                                </span>
                            </td>
                            <td>
                                <span class="volume-group-count" 
                                      data-app-name="${escapeHtml(appName)}" 
                                      data-app-namespace="${escapeHtml(appNamespace)}"
                                      onmouseenter="showVolumeGroupTooltip(this, '${escapeHtml(appName)}', '${escapeHtml(appNamespace)}')"
                                      onmouseleave="scheduleHideVolumeGroupTooltip()"
                                      style="cursor: pointer; position: relative;">
                                    <span class="volume-group-number">...</span>
                                </span>
                            </td>
                            <td>
                                <span class="service-dns-wrapper" 
                                      data-app-name="${escapeHtml(appName)}" 
                                      data-app-namespace="${escapeHtml(appNamespace)}"
                                      onmouseenter="showServiceDnsTooltip(this, '${escapeHtml(serviceDnsFull)}')"
                                      onmouseleave="scheduleHideServiceDnsTooltip()"
                                      style="cursor: pointer; position: relative;">
                                    <span class="service-dns-short">${serviceDnsShort}</span>
                                </span>
                            </td>
                            <td>${labelsHtml}</td>
                            <td>${formatDate(appLastSnapshot)}</td>
                            <td>${formatDate(appCreated)}</td>
                            <td>
                                <div class="action-buttons">
                                    <button class="btn-snapshot" onclick="showSnapshotModal('${escapeHtml(appName)}', '${escapeHtml(appNamespace)}')">
                                        📸 Snapshot
                                    </button>
                                    <button class="btn-snapshot" onclick="showEditLabelsModal('${escapeHtml(appName)}', '${escapeHtml(appNamespace)}')">
                                        ✏️ Labels
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
    
    // Fetch replica counts and volume group info for all applications
    fetchReplicaCounts(data);
    fetchVolumeGroupInfo(data);
}

// Cache for replica data to avoid repeated API calls
const replicaCache = new Map();
let tooltipTimeout = null;
let hideTooltipTimeout = null;

async function fetchReplicaCounts(applications) {
    // Fetch replica counts for all applications in parallel
    const promises = applications.map(async (app) => {
        const appName = app.name;
        const appNamespace = app.namespace;
        const cacheKey = `${appNamespace}/${appName}`;
        
        try {
            const response = await fetch(`/api/applications/${appNamespace}/${appName}/pods`);
            if (response.ok) {
                const data = await response.json();
                replicaCache.set(cacheKey, data);
                
                // Update the UI
                const replicaElements = document.querySelectorAll(
                    `.replica-count[data-app-name="${appName}"][data-app-namespace="${appNamespace}"]`
                );
                replicaElements.forEach(el => {
                    const numberEl = el.querySelector('.replica-number');
                    numberEl.textContent = data.replicas;
                    
                    // Add tooltip with selector info
                    if (data.selector) {
                        el.title = `Selector: ${data.selector}`;
                    }
                    
                    if (data.replicas > 0) {
                        numberEl.style.fontWeight = 'bold';
                        numberEl.style.color = '#2ecc71';
                    } else {
                        numberEl.style.color = '#95a5a6';
                        // If 0 replicas, add a warning indicator
                        if (data.selector) {
                            el.title = `No pods found with selector: ${data.selector}`;
                        }
                    }
                });
            }
        } catch (error) {
            console.error(`Error fetching replica count for ${appName}:`, error);
            const replicaElements = document.querySelectorAll(
                `.replica-count[data-app-name="${appName}"][data-app-namespace="${appNamespace}"] .replica-number`
            );
            replicaElements.forEach(el => {
                el.textContent = '?';
                el.style.color = '#e74c3c';
                el.parentElement.title = 'Error fetching replica count';
            });
        }
    });
    
    await Promise.all(promises);
}

function showReplicaTooltip(element, appName, appNamespace) {
    // Clear any existing hide timeout
    if (hideTooltipTimeout) {
        clearTimeout(hideTooltipTimeout);
        hideTooltipTimeout = null;
    }
    
    // Clear any existing show timeout
    if (tooltipTimeout) {
        clearTimeout(tooltipTimeout);
    }
    
    // Add a small delay before showing tooltip
    tooltipTimeout = setTimeout(() => {
        const cacheKey = `${appNamespace}/${appName}`;
        const data = replicaCache.get(cacheKey);
        
        if (!data || !data.pods || data.pods.length === 0) {
            return;
        }
        
        // Remove any existing tooltip
        const existingTooltip = document.getElementById('replica-tooltip');
        if (existingTooltip) {
            existingTooltip.remove();
        }
        
        // Create tooltip
        const tooltip = document.createElement('div');
        tooltip.id = 'replica-tooltip';
        tooltip.className = 'info-tooltip';
        
        // Add hover handlers to keep tooltip visible
        tooltip.addEventListener('mouseenter', () => {
            if (hideTooltipTimeout) {
                clearTimeout(hideTooltipTimeout);
                hideTooltipTimeout = null;
            }
        });
        tooltip.addEventListener('mouseleave', () => {
            scheduleHideReplicaTooltip();
        });
        
        // Build tooltip content
        let tooltipContent = '<div class="tooltip-header">Pod Distribution</div>';
        tooltipContent += '<div class="tooltip-body">';
        
        // Display all pods in a flat list with single spacing
        data.pods.forEach((pod, podIndex) => {
            const statusColor = pod.phase === 'Running' ? '#2ecc71' : '#f39c12';
            
            // Pod name as first item with status indicator
            tooltipContent += `<div class="tooltip-item">
                <span class="tooltip-status" style="background-color: ${statusColor};"></span>
                <span class="tooltip-item-label">Pod:</span>
                <span class="tooltip-item-value">${escapeHtml(pod.name)}</span>
            </div>`;
            
            tooltipContent += `<div class="tooltip-item">
                <span class="tooltip-status" style="visibility: hidden;"></span>
                <span class="tooltip-item-label">Status:</span>
                <span class="tooltip-item-value">${escapeHtml(pod.phase)} - ${pod.ready} ready</span>
            </div>`;
            
            tooltipContent += `<div class="tooltip-item">
                <span class="tooltip-status" style="visibility: hidden;"></span>
                <span class="tooltip-item-label">IP:</span>
                <span class="tooltip-item-value">${escapeHtml(pod.ip || 'N/A')}</span>
            </div>`;
            
            tooltipContent += `<div class="tooltip-item">
                <span class="tooltip-status" style="visibility: hidden;"></span>
                <span class="tooltip-item-label">Node:</span>
                <span class="tooltip-item-value">${escapeHtml(pod.node)}</span>
            </div>`;
            
            // Add separator line between pods (but not after the last pod)
            if (podIndex < data.pods.length - 1) {
                tooltipContent += `<div style="border-bottom: 1px solid #e9ecef; margin: 8px 0;"></div>`;
            }
        });
        
        tooltipContent += '</div>';
        tooltip.innerHTML = tooltipContent;
        
        // Position tooltip
        document.body.appendChild(tooltip);
        const rect = element.getBoundingClientRect();
        const tooltipRect = tooltip.getBoundingClientRect();
        tooltip.style.position = 'fixed';
        
        // Always show tooltip above the element
        tooltip.style.top = `${rect.top - tooltipRect.height - 5}px`;
        tooltip.style.left = `${rect.left}px`;
        
        // Adjust if tooltip goes off screen horizontally
        if (tooltipRect.right > window.innerWidth) {
            tooltip.style.left = `${window.innerWidth - tooltipRect.width - 10}px`;
        }
    }, 500); // 500ms delay for text selection
}

function scheduleHideReplicaTooltip() {
    // Clear any existing show timeout
    if (tooltipTimeout) {
        clearTimeout(tooltipTimeout);
        tooltipTimeout = null;
    }
    
    // Schedule hiding the tooltip after a short delay
    hideTooltipTimeout = setTimeout(() => {
        const tooltip = document.getElementById('replica-tooltip');
        if (tooltip) {
            tooltip.remove();
        }
    }, 200); // 200ms delay before hiding
}

function hideReplicaTooltip() {
    if (tooltipTimeout) {
        clearTimeout(tooltipTimeout);
        tooltipTimeout = null;
    }
    if (hideTooltipTimeout) {
        clearTimeout(hideTooltipTimeout);
        hideTooltipTimeout = null;
    }
    
    const tooltip = document.getElementById('replica-tooltip');
    if (tooltip) {
        tooltip.remove();
    }
}

// Cache for volume group data to avoid repeated API calls
const volumeGroupCache = new Map();
let volumeGroupTooltipTimeout = null;
let hideVolumeGroupTooltipTimeout = null;

async function fetchVolumeGroupInfo(applications) {
    // Fetch volume group info for all applications in parallel
    const promises = applications.map(async (app) => {
        const appName = app.name;
        const appNamespace = app.namespace;
        const cacheKey = `${appNamespace}/${appName}`;
        
        try {
            const response = await fetch(`/api/applications/${appNamespace}/${appName}/pvcs`);
            if (response.ok) {
                const data = await response.json();
                console.log(`[VG] Got data for ${appName}:`, data);
                volumeGroupCache.set(cacheKey, data);
                
                // Update the UI
                const vgElements = document.querySelectorAll(
                    `.volume-group-count[data-app-name="${appName}"][data-app-namespace="${appNamespace}"]`
                );
                console.log(`[VG] Found ${vgElements.length} elements for ${appName}`);
                vgElements.forEach(el => {
                    const numberEl = el.querySelector('.volume-group-number');
                    console.log(`[VG] Updating element for ${appName}, count=${data.count}`);
                    numberEl.textContent = data.count;
                    
                    if (data.count > 0) {
                        numberEl.style.fontWeight = 'bold';
                        numberEl.style.color = '#2ecc71';
                    } else {
                        numberEl.style.color = '#95a5a6';
                    }
                });
            } else {
                // Handle non-OK response
                const vgElements = document.querySelectorAll(
                    `.volume-group-count[data-app-name="${appName}"][data-app-namespace="${appNamespace}"] .volume-group-number`
                );
                vgElements.forEach(el => {
                    el.textContent = '?';
                    el.style.color = '#e74c3c';
                    el.parentElement.title = `Error: ${response.status} ${response.statusText}`;
                });
            }
        } catch (error) {
            console.error(`Error fetching volume group info for ${appName}:`, error);
            const vgElements = document.querySelectorAll(
                `.volume-group-count[data-app-name="${appName}"][data-app-namespace="${appNamespace}"] .volume-group-number`
            );
            vgElements.forEach(el => {
                el.textContent = '?';
                el.style.color = '#e74c3c';
                el.parentElement.title = 'Error fetching volume group info';
            });
        }
    });
    
    await Promise.all(promises);
}

function showVolumeGroupTooltip(element, appName, appNamespace) {
    // Clear any existing hide timeout
    if (hideVolumeGroupTooltipTimeout) {
        clearTimeout(hideVolumeGroupTooltipTimeout);
        hideVolumeGroupTooltipTimeout = null;
    }
    
    // Clear any existing show timeout
    if (volumeGroupTooltipTimeout) {
        clearTimeout(volumeGroupTooltipTimeout);
    }
    
    // Add delay before showing tooltip to allow text selection
    volumeGroupTooltipTimeout = setTimeout(() => {
        const cacheKey = `${appNamespace}/${appName}`;
        const data = volumeGroupCache.get(cacheKey);
        
        if (!data || !data.pvcs || data.pvcs.length === 0) {
            return;
        }
        
        // Remove any existing tooltip
        const existingTooltip = document.getElementById('volume-group-tooltip');
        if (existingTooltip) {
            existingTooltip.remove();
        }
        
        // Create tooltip
        const tooltip = document.createElement('div');
        tooltip.id = 'volume-group-tooltip';
        tooltip.className = 'info-tooltip';
        
        // Add hover handlers to keep tooltip visible
        tooltip.addEventListener('mouseenter', () => {
            if (hideVolumeGroupTooltipTimeout) {
                clearTimeout(hideVolumeGroupTooltipTimeout);
                hideVolumeGroupTooltipTimeout = null;
            }
        });
        tooltip.addEventListener('mouseleave', () => {
            scheduleHideVolumeGroupTooltip();
        });
        
        // Build tooltip content
        let tooltipContent = '<div class="tooltip-header">Volume Groups</div>';
        tooltipContent += '<div class="tooltip-body">';
        
        data.pvcs.forEach((pvc, pvcIndex) => {
            // Map "Bound" status to "Connected"
            const displayStatus = pvc.status === 'Bound' ? 'Connected' : pvc.status;
            const statusColor = pvc.status === 'Bound' ? '#2ecc71' : '#f39c12';
            
            // PVC name as first item with status indicator
            tooltipContent += `<div class="tooltip-item">
                <span class="tooltip-status" style="background-color: ${statusColor};"></span>
                <span class="tooltip-item-label">PVC:</span>
                <span class="tooltip-item-value">${escapeHtml(pvc.name)}</span>
            </div>`;
            
            tooltipContent += `<div class="tooltip-item">
                <span class="tooltip-status" style="visibility: hidden;"></span>
                <span class="tooltip-item-label">Status:</span>
                <span class="tooltip-item-value">${escapeHtml(displayStatus)}</span>
            </div>`;
            
            tooltipContent += `<div class="tooltip-item">
                <span class="tooltip-status" style="visibility: hidden;"></span>
                <span class="tooltip-item-label">Capacity:</span>
                <span class="tooltip-item-value">${escapeHtml(pvc.capacity)}</span>
            </div>`;
            
            tooltipContent += `<div class="tooltip-item">
                <span class="tooltip-status" style="visibility: hidden;"></span>
                <span class="tooltip-item-label">PV:</span>
                <span class="tooltip-item-value">${escapeHtml(pvc.pvName)}</span>
            </div>`;
            
            // Show Volume Group if available (without gray box)
            if (pvc.volumeGroup) {
                tooltipContent += `<div class="tooltip-item">
                    <span class="tooltip-status" style="visibility: hidden;"></span>
                    <span class="tooltip-item-label">Volume Group:</span>
                    <span class="tooltip-item-value">${escapeHtml(pvc.volumeGroup)}</span>
                </div>`;
            }
            
            tooltipContent += `<div class="tooltip-item">
                <span class="tooltip-status" style="visibility: hidden;"></span>
                <span class="tooltip-item-label">Storage Class:</span>
                <span class="tooltip-item-value">${escapeHtml(pvc.storageClass)}</span>
            </div>`;
            
            // Add separator line between PVCs (but not after the last one)
            if (pvcIndex < data.pvcs.length - 1) {
                tooltipContent += `<div style="border-bottom: 1px solid #e9ecef; margin: 8px 0;"></div>`;
            }
        });
        
        tooltipContent += '</div>';
        tooltip.innerHTML = tooltipContent;
        
        // Position tooltip
        document.body.appendChild(tooltip);
        const rect = element.getBoundingClientRect();
        const tooltipRect = tooltip.getBoundingClientRect();
        tooltip.style.position = 'fixed';
        
        // Always show tooltip above the element
        tooltip.style.top = `${rect.top - tooltipRect.height - 5}px`;
        tooltip.style.left = `${rect.left}px`;
        
        // Adjust if tooltip goes off screen horizontally
        if (tooltipRect.right > window.innerWidth) {
            tooltip.style.left = `${window.innerWidth - tooltipRect.width - 10}px`;
        }
    }, 500); // 500ms delay for text selection
}

function scheduleHideVolumeGroupTooltip() {
    // Clear any existing show timeout
    if (volumeGroupTooltipTimeout) {
        clearTimeout(volumeGroupTooltipTimeout);
        volumeGroupTooltipTimeout = null;
    }
    
    // Schedule hiding the tooltip after a short delay
    hideVolumeGroupTooltipTimeout = setTimeout(() => {
        const tooltip = document.getElementById('volume-group-tooltip');
        if (tooltip) {
            tooltip.remove();
        }
    }, 200); // 200ms delay before hiding
}

function hideVolumeGroupTooltip() {
    if (volumeGroupTooltipTimeout) {
        clearTimeout(volumeGroupTooltipTimeout);
        volumeGroupTooltipTimeout = null;
    }
    if (hideVolumeGroupTooltipTimeout) {
        clearTimeout(hideVolumeGroupTooltipTimeout);
        hideVolumeGroupTooltipTimeout = null;
    }
    
    const tooltip = document.getElementById('volume-group-tooltip');
    if (tooltip) {
        tooltip.remove();
    }
}

// Service DNS tooltip management
let serviceDnsTooltipTimeout = null;
let hideServiceDnsTooltipTimeout = null;

function showServiceDnsTooltip(element, fullDns) {
    // Clear any existing hide timeout
    if (hideServiceDnsTooltipTimeout) {
        clearTimeout(hideServiceDnsTooltipTimeout);
        hideServiceDnsTooltipTimeout = null;
    }
    
    // Clear any existing show timeout
    if (serviceDnsTooltipTimeout) {
        clearTimeout(serviceDnsTooltipTimeout);
    }
    
    // Add a small delay before showing tooltip
    serviceDnsTooltipTimeout = setTimeout(() => {
        // Remove any existing tooltip
        const existingTooltip = document.getElementById('service-dns-tooltip');
        if (existingTooltip) {
            existingTooltip.remove();
        }
        
        // Create tooltip
        const tooltip = document.createElement('div');
        tooltip.id = 'service-dns-tooltip';
        tooltip.className = 'info-tooltip';
        
        // Add hover handlers to keep tooltip visible
        tooltip.addEventListener('mouseenter', () => {
            if (hideServiceDnsTooltipTimeout) {
                clearTimeout(hideServiceDnsTooltipTimeout);
                hideServiceDnsTooltipTimeout = null;
            }
        });
        tooltip.addEventListener('mouseleave', () => {
            scheduleHideServiceDnsTooltip();
        });
        
        // Build tooltip content
        let tooltipContent = '<div class="tooltip-header">Service DNS</div>';
        tooltipContent += '<div class="tooltip-body">';
        tooltipContent += `<div class="tooltip-item">
            <span class="tooltip-item-label">Full DNS:</span>
            <span class="tooltip-item-value">${escapeHtml(fullDns)}</span>
        </div>`;
        tooltipContent += '</div>';
        
        tooltip.innerHTML = tooltipContent;
        
        // Position tooltip
        document.body.appendChild(tooltip);
        const rect = element.getBoundingClientRect();
        const tooltipRect = tooltip.getBoundingClientRect();
        tooltip.style.position = 'fixed';
        
        // Always show tooltip above the element
        tooltip.style.top = `${rect.top - tooltipRect.height - 5}px`;
        tooltip.style.left = `${rect.left}px`;
        
        // Adjust if tooltip goes off screen horizontally
        if (tooltipRect.right > window.innerWidth) {
            tooltip.style.left = `${window.innerWidth - tooltipRect.width - 10}px`;
        }
    }, 500); // 500ms delay for text selection
}

function scheduleHideServiceDnsTooltip() {
    // Clear any existing show timeout
    if (serviceDnsTooltipTimeout) {
        clearTimeout(serviceDnsTooltipTimeout);
        serviceDnsTooltipTimeout = null;
    }
    
    // Schedule hiding the tooltip after a short delay
    hideServiceDnsTooltipTimeout = setTimeout(() => {
        const tooltip = document.getElementById('service-dns-tooltip');
        if (tooltip) {
            tooltip.remove();
        }
    }, 200); // 200ms delay before hiding
}

function hideServiceDnsTooltip() {
    if (serviceDnsTooltipTimeout) {
        clearTimeout(serviceDnsTooltipTimeout);
        serviceDnsTooltipTimeout = null;
    }
    if (hideServiceDnsTooltipTimeout) {
        clearTimeout(hideServiceDnsTooltipTimeout);
        hideServiceDnsTooltipTimeout = null;
    }
    
    const tooltip = document.getElementById('service-dns-tooltip');
    if (tooltip) {
        tooltip.remove();
    }
}

function renderSnapshots(data, container) {
    // Sort snapshots by creation time (newest first)
    const sortedData = [...data].sort((a, b) => {
        const timeA = a.creationTime || a.created || '';
        const timeB = b.creationTime || b.created || '';
        return timeB.localeCompare(timeA);
    });
    
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
                        <th style="width: 3%;"><input type="checkbox" id="select-all-snapshots" onchange="toggleAllSnapshots(this.checked)"></th>
                        <th style="width: 22%;">Name</th>
                        <th style="width: 15%;">Application</th>
                        <th style="width: 12%;">Namespace</th>
                        <th style="width: 15%;">Protection Plan</th>
                        <th style="width: 8%;">Status</th>
                        <th style="width: 10%;">Expires After</th>
                        <th style="width: 12%;">Created</th>
                        <th style="width: 13%;">Actions</th>
                    </tr>
                </thead>
                <tbody>
                    ${sortedData.map(snap => {
                        const snapName = snap.name || 'Unknown';
                        const snapNamespace = snap.namespace || 'default';
                        const snapApplication = snap.application || 'Unknown';
                        const snapState = snap.state || 'Unknown';
                        const snapExpires = snap.expiresAfter || snap.retentionPeriod || 'Not set';
                        const snapCreated = snap.created || null;
                        const protectionPlan = snap.protectionPlan || 'Manual';
                        
                        return `
                        <tr>
                            <td><input type="checkbox" class="snapshot-checkbox" data-name="${escapeHtml(snapName)}" data-namespace="${escapeHtml(snapNamespace)}" onchange="updateSnapshotSelection()"></td>
                            <td><strong>${escapeHtml(snapName)}</strong></td>
                            <td>${escapeHtml(snapApplication)}</td>
                            <td>${escapeHtml(snapNamespace)}</td>
                            <td>${escapeHtml(protectionPlan)}</td>
                            <td>${getStatusBadge(snapState)}</td>
                            <td>${escapeHtml(snapExpires)}</td>
                            <td>${formatDate(snapCreated)}</td>
                            <td>
                                <div class="action-buttons">
                                    <button class="btn-restore" onclick="showRestoreModal('${escapeHtml(snapName)}', '${escapeHtml(snapNamespace)}', '${escapeHtml(snapApplication)}')" title="Restore from snapshot" ${snapState !== 'Ready' ? 'disabled' : ''}>
                                        ↻ Restore
                                    </button>
                                    <button class="btn-delete" onclick="deleteSnapshot('${escapeHtml(snapName)}', '${escapeHtml(snapNamespace)}')" title="Delete snapshot">
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

function renderStorageClusters(data, container) {
    const html = `
        <div class="data-table">
            <table>
                <thead>
                    <tr>
                        <th style="width: 25%;">Name</th>
                        <th style="width: 25%;">Prism Central</th>
                        <th style="width: 30%;">Storage Server UUID</th>
                        <th style="width: 10%;">Status</th>
                        <th style="width: 10%;">Created</th>
                    </tr>
                </thead>
                <tbody>
                    ${data.map(cluster => `
                        <tr>
                            <td><strong>${escapeHtml(cluster.name)}</strong></td>
                            <td>${escapeHtml(cluster.prismCentral)}</td>
                            <td><code style="font-size: 0.8125rem; background: var(--neutral-100); padding: 0.25rem 0.5rem; border-radius: 4px;">${escapeHtml(cluster.storageServerUUID)}</code></td>
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
                        <th style="width: 16%;">Name</th>
                        <th style="width: 10%;">Namespace</th>
                        <th style="width: 14%;">Selection</th>
                        <th style="width: 12%;">Schedule</th>
                        <th style="width: 10%;">Retention</th>
                        <th style="width: 8%;">Status</th>
                        <th style="width: 11%;">Last Execution</th>
                        <th style="width: 19%;">Actions</th>
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
                        const isDeleting = plan.isDeleting || false;
                        const hasFinalizers = plan.hasFinalizers || false;
                        
                        // Format selection mode display
                        const selectionMode = plan.selectionMode || 'by-name';
                        let selectionDisplay = '';
                        if (selectionMode === 'by-label' && plan.labelSelectorKey && plan.labelSelectorValue) {
                            selectionDisplay = `<span title="Label-based selection">🏷️ ${escapeHtml(plan.labelSelectorKey)}=${escapeHtml(plan.labelSelectorValue)}</span>`;
                        } else {
                            selectionDisplay = '<span title="Application name selection">📝 By Name</span>';
                        }
                        
                        // Show status - if deleting, indicate it's in progress
                        const displayStatus = isDeleting ? 
                            '<span class="plan-status inactive">⏳ Deleting...</span>' : 
                            `<span class="plan-status ${statusClass}">${isEnabled ? 'Active' : 'Disabled'}</span>`;
                        
                        // If plan is deleting, disable action buttons but still show them
                        // This gives better UX than immediately jumping to force delete
                        const actionButtons = isDeleting ? `
                            <button class="btn-trigger" disabled title="Plan is being deleted">
                                ⚡ Trigger
                            </button>
                            <button class="btn-history" onclick="showPlanHistory('${escapeHtml(planName)}', '${escapeHtml(planNamespace)}')" title="View History">
                                📊 History
                            </button>
                            <button class="btn-delete" disabled title="Deletion in progress... If stuck, refresh and use Force Delete">
                                ⏳ Deleting...
                            </button>
                            <button class="btn-delete" onclick="forceDeletePlan('${escapeHtml(planName)}', '${escapeHtml(planNamespace)}')" title="Force Delete (if stuck)">
                                ⚠️ Force
                            </button>
                        ` : `
                            <button class="btn-trigger" onclick="triggerPlan('${escapeHtml(planName)}', '${escapeHtml(planNamespace)}')" title="Trigger Now">
                                ⚡ Trigger
                            </button>
                            <button class="btn-history" onclick="showPlanHistory('${escapeHtml(planName)}', '${escapeHtml(planNamespace)}')" title="View History">
                                📊 History
                            </button>
                            <button class="btn-delete" onclick="deletePlan('${escapeHtml(planName)}', '${escapeHtml(planNamespace)}')" title="Delete Plan">
                                🗑️ Delete
                            </button>
                        `;
                        
                        return `
                        <tr ${isDeleting ? 'style="background-color: rgba(156, 163, 175, 0.1); opacity: 0.7;"' : ''}>
                            <td><strong>${escapeHtml(planName)}</strong></td>
                            <td>${escapeHtml(planNamespace)}</td>
                            <td>${selectionDisplay}</td>
                            <td>${escapeHtml(formatCronSchedule(planSchedule))}</td>
                            <td>${escapeHtml(formatRetention(planRetention))}</td>
                            <td>${displayStatus}</td>
                            <td>${formatDate(planLastExecution)}</td>
                            <td>
                                <div class="action-buttons">
                                    ${actionButtons}
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
    
    // Check for "every X hours" pattern FIRST (before daily check)
    // "0 */6 * * *" -> "Every 6 hours"
    if (hour.startsWith('*/') && day === '*' && month === '*' && weekday === '*') {
        const hours = hour.substring(2);
        if (minute === '0') {
            return `Every ${hours} hours`;
        } else {
            return `Every ${hours} hours at :${minute.padStart(2, '0')}`;
        }
    }
    
    // Hourly: "0 * * * *" -> "Every hour"
    if (minute !== '*' && hour === '*' && day === '*' && month === '*' && weekday === '*') {
        if (minute === '0') {
            return 'Every hour';
        } else {
            return `Every hour at :${minute.padStart(2, '0')}`;
        }
    }
    
    // Common patterns
    // Daily at specific time: "0 2 * * *" -> "Daily at 2:00 AM"
    if (day === '*' && month === '*' && weekday === '*' && !hour.includes('*') && !hour.includes('/')) {
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
    if (day !== '*' && month === '*' && weekday === '*' && !hour.includes('*') && !hour.includes('/')) {
        const hourNum = parseInt(hour);
        const minuteNum = parseInt(minute);
        const period = hourNum >= 12 ? 'PM' : 'AM';
        const displayHour = hourNum === 0 ? 12 : hourNum > 12 ? hourNum - 12 : hourNum;
        const displayMinute = minuteNum.toString().padStart(2, '0');
        return `Monthly on day ${day} at ${displayHour}:${displayMinute} ${period}`;
    }
    
    // Every X minutes: "*/15 * * * *" -> "Every 15 minutes"
    if (minute.startsWith('*/') && hour === '*' && day === '*' && month === '*' && weekday === '*') {
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
    } else if (statusLower.includes('deleting') || statusLower.includes('terminating')) {
        className = 'status-pending';  // Use pending style for deleting
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
        
        // Reload snapshots only (don't reload stats to avoid showing "Unknown" for other resources)
        await loadSnapshots();
        
        // Update snapshot count in stats without full reload
        const statElement = document.getElementById('stat-snapshots');
        if (statElement) {
            const currentCount = parseInt(statElement.textContent) || 0;
            statElement.textContent = currentCount + 1;
        }
    } catch (error) {
        console.error('Error creating snapshot:', error);
        showToast('✗ Error creating snapshot', 'error');
    }
}

// Snapshot Deletion
function deleteSnapshot(name, namespace) {
    document.getElementById('delete-snapshot-name').textContent = name;
    document.getElementById('delete-snapshot-namespace-hidden').value = namespace;
    document.getElementById('delete-snapshot-modal').style.display = 'flex';
}

function closeDeleteSnapshotModal() {
    document.getElementById('delete-snapshot-modal').style.display = 'none';
}

async function confirmDeleteSnapshot() {
    const name = document.getElementById('delete-snapshot-name').textContent;
    const namespace = document.getElementById('delete-snapshot-namespace-hidden').value;
    
    closeDeleteSnapshotModal();
    
    try {
        showToast('Deleting snapshot...', 'info');
        
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
        
        // Reload snapshots only (don't reload stats to avoid showing "Unknown" for other resources)
        await loadSnapshots();
        
        // Update snapshot count in stats without full reload
        const statElement = document.getElementById('stat-snapshots');
        if (statElement) {
            const currentCount = parseInt(statElement.textContent) || 0;
            statElement.textContent = Math.max(0, currentCount - 1);
        }
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
    
    // Clear selection and reload snapshots only
    clearSnapshotSelection();
    await loadSnapshots();
    
    // Update snapshot count in stats without full reload
    if (successCount > 0) {
        const statElement = document.getElementById('stat-snapshots');
        if (statElement) {
            const currentCount = parseInt(statElement.textContent) || 0;
            statElement.textContent = Math.max(0, currentCount - successCount);
        }
    }
}

// Snapshot Restore
async function showRestoreModal(snapshotName, namespace, appName) {
    const modal = document.getElementById('restore-modal');
    document.getElementById('restore-snapshot-name').textContent = snapshotName;
    document.getElementById('restore-snapshot-name-hidden').value = snapshotName;
    document.getElementById('restore-namespace-hidden').value = namespace;
    document.getElementById('restore-app-name-hidden').value = appName;
    document.getElementById('restore-name').value = `${appName}-restore-${Date.now()}`;
    
    
    // Load namespaces for the dropdown
    await loadRestoreNamespaces(namespace);
    
    modal.style.display = 'flex';
}

async function loadRestoreNamespaces(defaultNamespace) {
    const namespaceSelect = document.getElementById('restore-target-namespace');
    
    try {
        // Show loading state
        namespaceSelect.innerHTML = '<option value="">Loading namespaces...</option>';
        
        const response = await fetch('/api/namespaces');
        
        if (response.redirected || response.url.includes('/login')) {
            window.location.href = '/login';
            return;
        }
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        const namespaces = data.namespaces || [];
        
        // Populate dropdown
        namespaceSelect.innerHTML = '';
        namespaces.forEach(ns => {
            const option = document.createElement('option');
            option.value = ns;
            option.textContent = ns;
            namespaceSelect.appendChild(option);
        });
        
        // Set default namespace
        if (defaultNamespace && namespaces.includes(defaultNamespace)) {
            namespaceSelect.value = defaultNamespace;
        }
    } catch (error) {
        console.error('Error loading namespaces:', error);
        namespaceSelect.innerHTML = '<option value="">Error loading namespaces</option>';
        showToast('✗ Failed to load namespaces', 'error');
    }
}

function closeRestoreModal() {
    const modal = document.getElementById('restore-modal');
    modal.style.display = 'none';
}

async function restoreSnapshot() {
    console.log('restoreSnapshot function called');
    
    const snapshotName = document.getElementById('restore-snapshot-name-hidden').value;
    const namespace = document.getElementById('restore-namespace-hidden').value;
    const restoreName = document.getElementById('restore-name').value;
    const targetNamespace = document.getElementById('restore-target-namespace').value;
    const appName = document.getElementById('restore-app-name-hidden').value;
    
    console.log('Restore snapshot values:', {
        snapshotName,
        namespace,
        restoreName,
        targetNamespace,
        appName
    });
    
    if (!restoreName) {
        showToast('✗ Restore name is required', 'error');
        return;
    }
    
    if (!targetNamespace) {
        showToast('✗ Target namespace is required', 'error');
        return;
    }
    
    // Validate application name
    if (!appName || appName === 'Unknown') {
        showToast('✗ Cannot restore: Application name is missing or unknown in snapshot', 'error');
        return;
    }
    
    // Validation: Check if application exists - NDK requires it to be deleted first
    try {
            const checkResponse = await fetch(`/api/applications/${targetNamespace}/${appName}`);
            
            if (checkResponse.ok) {
                // Application exists - show error
                showToast('⚠️ Cannot restore: Application still exists. Please delete it first.', 'error');
                return;
            } else if (checkResponse.status === 404) {
                // Application doesn't exist - good to proceed
                console.log('Application does not exist, proceeding with restore');
            } else if (checkResponse.redirected || checkResponse.url.includes('/login')) {
                window.location.href = '/login';
                return;
            }
        } catch (error) {
            console.error('Error checking application existence:', error);
            showToast('✗ Error validating restore operation', 'error');
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
        
        // Extract the restored application name from the response
        const restoredAppName = result?.application?.name || appName;
        const displayName = restoredAppName || result?.message || 'restore operation';
        showToast(`✓ Restore initiated: ${displayName}`, 'success');
        
        // Show progress modal and start tracking with the RESTORED app name
        showRestoreProgressModal(targetNamespace, restoredAppName, snapshotName);
    } catch (error) {
        console.error('Error restoring snapshot:', error);
        const errorMessage = error.message || 'Unknown error';
        showToast(`✗ Error restoring snapshot: ${errorMessage}`, 'error');
    }
}

// Restore Progress Tracking
let restoreProgressInterval = null;

function showRestoreProgressModal(namespace, appName, snapshotName) {
    const modal = document.getElementById('restore-progress-modal');
    document.getElementById('restore-progress-app-name').textContent = appName;
    document.getElementById('restore-progress-snapshot-name').textContent = snapshotName;
    document.getElementById('restore-progress-percentage').textContent = '0%';
    document.getElementById('restore-progress-stage').textContent = 'Initializing...';
    document.getElementById('restore-progress-message').textContent = 'Starting restore operation';
    
    const progressFill = document.querySelector('#restore-progress-modal .progress-fill');
    progressFill.style.width = '0%';
    
    modal.style.display = 'flex';
    
    // Start tracking progress
    startRestoreProgressTracking(namespace, appName);
}

function closeRestoreProgressModal() {
    const modal = document.getElementById('restore-progress-modal');
    modal.style.display = 'none';
    
    // Stop polling
    if (restoreProgressInterval) {
        clearInterval(restoreProgressInterval);
        restoreProgressInterval = null;
    }
}

function startRestoreProgressTracking(namespace, appName) {
    // Clear any existing interval
    if (restoreProgressInterval) {
        clearInterval(restoreProgressInterval);
    }
    
    // Poll every 2 seconds
    restoreProgressInterval = setInterval(() => {
        updateRestoreProgress(namespace, appName);
    }, 2000);
    
    // Initial update
    updateRestoreProgress(namespace, appName);
}

async function updateRestoreProgress(namespace, appName) {
    try {
        const response = await fetch(`/api/applications/${namespace}/${appName}/restore-progress`);
        
        if (!response.ok) {
            console.error('Failed to fetch restore progress');
            return;
        }
        
        const data = await response.json();
        
        // Update UI
        document.getElementById('restore-progress-percentage').textContent = `${data.progress}%`;
        document.getElementById('restore-progress-stage').textContent = data.stage;
        document.getElementById('restore-progress-message').textContent = data.message || '';
        
        const progressFill = document.querySelector('#restore-progress-modal .progress-fill');
        progressFill.style.width = `${data.progress}%`;

        // Check for errors
        if (data.error || data.state === 'Failed') {
            // Stop polling
            if (restoreProgressInterval) {
                clearInterval(restoreProgressInterval);
                restoreProgressInterval = null;
            }
            
            // Change progress bar color to red for errors
            progressFill.style.backgroundColor = '#ef4444';
            
            // Show error toast and keep modal open so user can see the error
            showToast(`✗ Restore failed: ${data.stage}`, 'error');
            
            // Don't auto-close on error - let user close manually
            return;
        }

        // Check if complete
        if (data.progress >= 100 || data.state === 'Ready' || data.completed) {
            // Stop polling
            if (restoreProgressInterval) {
                clearInterval(restoreProgressInterval);
                restoreProgressInterval = null;
            }
            
            // Auto-close after 2 seconds and refresh
            setTimeout(async () => {
                closeRestoreProgressModal();
                await loadApplications();
                showToast('✓ Restore completed successfully', 'success');
            }, 2000);
        }
    } catch (error) {
        console.error('Error updating restore progress:', error);
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
        
        // Reload snapshots only (don't reload stats to avoid showing "Unknown" for other resources)
        await loadSnapshots();
        
        // Update snapshot count in stats without full reload
        if (successCount > 0) {
            const statElement = document.getElementById('stat-snapshots');
            if (statElement) {
                const currentCount = parseInt(statElement.textContent) || 0;
                statElement.textContent = currentCount + successCount;
            }
        }
    } catch (error) {
        console.error('Error creating bulk snapshots:', error);
        showToast('✗ Error creating bulk snapshots', 'error');
    }
}

// ============================================
// Protection Plan Management Functions
// ============================================

async function showCreatePlanModal() {
    document.getElementById('plan-modal-title').textContent = 'Create Protection Plan';
    document.getElementById('plan-save-text').textContent = 'Create Plan';
    
    // Reset form
    document.getElementById('plan-name').value = '';
    document.getElementById('plan-namespace').value = 'default';
    document.getElementById('plan-schedule-type').value = 'preset';
    document.getElementById('plan-schedule-preset').value = '0 2 * * *';
    document.getElementById('plan-schedule-custom').value = '';
    document.getElementById('plan-retention-count').value = '7';
    document.getElementById('plan-enabled').checked = true;
    
    // Reset selection mode to by-name
    document.querySelector('input[name="plan-selection-mode"][value="by-name"]').checked = true;
    
    // Reset label selector dropdowns and custom inputs
    const labelKeySelect = document.getElementById('plan-label-key');
    const labelKeyCustom = document.getElementById('plan-label-key-custom');
    const labelValueSelect = document.getElementById('plan-label-value');
    const labelValueCustom = document.getElementById('plan-label-value-custom');
    
    labelKeySelect.innerHTML = '<option value="">-- Select a label key --</option><option value="__custom__" style="font-style: italic; color: #667eea;">✏️ Enter custom key...</option>';
    labelKeySelect.value = '';
    labelKeyCustom.value = '';
    labelKeyCustom.style.display = 'none';
    
    labelValueSelect.innerHTML = '<option value="">-- Select a label key first --</option>';
    labelValueSelect.value = '';
    labelValueSelect.disabled = true;
    labelValueCustom.value = '';
    labelValueCustom.style.display = 'none';
    
    updateScheduleInput();
    updateSelectionMode();
    
    // Load namespaces for the dropdown
    await loadPlanNamespaces();
    
    // Populate applications list with checkboxes
    populateApplicationsList();
    
    document.getElementById('plan-modal').classList.add('active');
}

function populateApplicationsList() {
    const appsList = document.getElementById('plan-applications-list');
    if (!appsList) return;
    
    // Get the selected namespace from the plan form
    const namespaceSelect = document.getElementById('plan-namespace-select');
    const customNamespaceInput = document.getElementById('plan-namespace');
    let selectedNamespace = '';
    
    if (namespaceSelect && namespaceSelect.value === '__custom__') {
        selectedNamespace = customNamespaceInput.value.trim();
    } else if (namespaceSelect) {
        selectedNamespace = namespaceSelect.value;
    }
    
    // If no namespace selected, show prompt
    if (!selectedNamespace || selectedNamespace === '') {
        appsList.innerHTML = `
            <div style="color: #666; font-style: italic; text-align: center; padding: 20px;">
                👆 Please select a namespace first
            </div>
        `;
        return;
    }
    
    // Check if applications data is available
    if (!allData.applications || allData.applications.length === 0) {
        appsList.innerHTML = '<div style="color: #999; font-style: italic; text-align: center; padding: 20px;">No applications available in the cluster</div>';
        return;
    }
    
    // Filter applications by the selected namespace
    const filteredApps = allData.applications.filter(app => {
        const appNamespace = app.namespace || 'default';
        return appNamespace === selectedNamespace;
    });
    
    if (filteredApps.length === 0) {
        appsList.innerHTML = `
            <div style="color: #ff6b6b; font-style: italic; text-align: center; padding: 20px;">
                <div style="font-size: 2em; margin-bottom: 10px;">📭</div>
                <div>No applications found in namespace <strong>"${selectedNamespace}"</strong></div>
                <div style="margin-top: 8px; font-size: 0.9em; color: #999;">Deploy an application to this namespace first</div>
            </div>
        `;
        return;
    }
    
    // Sort applications by name
    const sortedApps = [...filteredApps].sort((a, b) => {
        return (a.name || '').localeCompare(b.name || '');
    });
    
    // Build the list with modern styling
    let html = `
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 12px 15px; margin: -12px -12px 15px -12px; border-radius: 6px 6px 0 0; color: white; display: flex; justify-content: space-between; align-items: center; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
            <div style="display: flex; align-items: center; gap: 8px;">
                <span style="font-size: 1.2em;">📁</span>
                <span style="font-weight: 600; font-size: 1.05em;">${selectedNamespace}</span>
            </div>
            <div style="background-color: rgba(255,255,255,0.25); padding: 4px 12px; border-radius: 12px; font-size: 0.9em; font-weight: 600;">
                ${sortedApps.length} app${sortedApps.length !== 1 ? 's' : ''}
            </div>
        </div>
        <div style="padding: 5px 0;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; padding: 8px; background-color: #f8f9fa; border-left: 3px solid #667eea; border-radius: 4px;">
                <div style="font-size: 0.9em; color: #555;">
                    <strong>💡 Tip:</strong> Select one or more applications to protect
                </div>
                <div style="display: flex; gap: 8px;">
                    <button type="button" onclick="toggleAllApplications(true)" style="
                        padding: 4px 10px;
                        font-size: 0.85em;
                        background-color: #667eea;
                        color: white;
                        border: none;
                        border-radius: 4px;
                        cursor: pointer;
                        font-weight: 500;
                        transition: background-color 0.2s;
                    " onmouseover="this.style.backgroundColor='#5568d3'" onmouseout="this.style.backgroundColor='#667eea'">
                        Select All
                    </button>
                    <button type="button" onclick="toggleAllApplications(false)" style="
                        padding: 4px 10px;
                        font-size: 0.85em;
                        background-color: #6c757d;
                        color: white;
                        border: none;
                        border-radius: 4px;
                        cursor: pointer;
                        font-weight: 500;
                        transition: background-color 0.2s;
                    " onmouseover="this.style.backgroundColor='#5a6268'" onmouseout="this.style.backgroundColor='#6c757d'">
                        Clear All
                    </button>
                </div>
            </div>
    `;
    
    sortedApps.forEach((app, index) => {
        const appName = app.name || 'Unknown';
        const appNamespace = app.namespace || 'default';
        const checkboxId = `app-checkbox-${index}`;
        
        // Add checkbox for application with modern styling
        html += `
            <label class="app-checkbox-item" style="
                display: flex;
                align-items: center;
                padding: 12px 15px;
                margin: 6px 0;
                background-color: white;
                border: 2px solid #e0e0e0;
                border-radius: 8px;
                cursor: pointer;
                transition: all 0.2s ease;
                box-shadow: 0 1px 3px rgba(0,0,0,0.05);
            " onmouseover="this.style.borderColor='#667eea'; this.style.boxShadow='0 2px 8px rgba(102,126,234,0.2)'; this.style.transform='translateY(-1px)';" 
               onmouseout="this.style.borderColor='#e0e0e0'; this.style.boxShadow='0 1px 3px rgba(0,0,0,0.05)'; this.style.transform='translateY(0)';">
                <input type="checkbox" 
                       id="${checkboxId}"
                       class="app-checkbox" 
                       data-app-name="${appName}" 
                       data-app-namespace="${appNamespace}" 
                       style="
                           width: 20px;
                           height: 20px;
                           margin-right: 12px;
                           cursor: pointer;
                           accent-color: #667eea;
                       ">
                <span style="
                    flex: 1;
                    display: flex;
                    align-items: center;
                    gap: 10px;
                    font-weight: 500;
                    color: #333;
                ">
                    <span style="font-size: 1.3em;">📦</span>
                    <span>${appName}</span>
                </span>
            </label>
        `;
    });
    
    html += '</div>';
    appsList.innerHTML = html;
}

function toggleAllApplications(selectAll) {
    const checkboxes = document.querySelectorAll('.app-checkbox');
    checkboxes.forEach(checkbox => {
        checkbox.checked = selectAll;
    });
}

function closePlanModal() {
    document.getElementById('plan-modal').classList.remove('active');
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
    // No longer needed - retention is always count-based (NDK requirement)
    // The HTML template only has plan-retention-count field
}

function selectPlanModeCard(mode) {
    // Remove selected class from all cards
    document.querySelectorAll('#plan-selection-by-name-card, #plan-selection-by-label-card').forEach(card => {
        card.classList.remove('selected');
    });
    
    // Add selected class to clicked card
    const cardId = mode === 'by-name' ? 'plan-selection-by-name-card' : 'plan-selection-by-label-card';
    document.getElementById(cardId).classList.add('selected');
    
    // Check the radio button
    const radioId = mode === 'by-name' ? 'plan-selection-mode-by-name' : 'plan-selection-mode-by-label';
    document.getElementById(radioId).checked = true;
    
    // Update the display
    updateSelectionMode();
}

function updateSelectionMode() {
    const selectionMode = document.querySelector('input[name="plan-selection-mode"]:checked').value;
    const byNameDiv = document.getElementById('plan-selection-by-name-div');
    const byLabelDiv = document.getElementById('plan-selection-by-label-div');
    
    if (selectionMode === 'by-name') {
        byNameDiv.style.display = 'block';
        byLabelDiv.style.display = 'none';
    } else {
        byNameDiv.style.display = 'none';
        byLabelDiv.style.display = 'block';
        populateLabelKeyOptions();
        updateLabelPreview();
    }
    
    // Update card selection styling
    document.querySelectorAll('#plan-selection-by-name-card, #plan-selection-by-label-card').forEach(card => {
        card.classList.remove('selected');
    });
    const selectedCardId = selectionMode === 'by-name' ? 'plan-selection-by-name-card' : 'plan-selection-by-label-card';
    document.getElementById(selectedCardId).classList.add('selected');
}

function populateLabelKeyOptions() {
    const labelKeySelect = document.getElementById('plan-label-key');
    const namespaceSelect = document.getElementById('plan-namespace-select');
    const customNamespaceInput = document.getElementById('plan-namespace');
    
    // Get selected namespace
    let selectedNamespace = '';
    if (namespaceSelect && namespaceSelect.value === '__custom__') {
        selectedNamespace = customNamespaceInput.value.trim();
    } else if (namespaceSelect) {
        selectedNamespace = namespaceSelect.value;
    }
    
    // Clear existing options except the default and custom option
    labelKeySelect.innerHTML = '<option value="">-- Select a label key --</option>';
    
    if (!selectedNamespace || !allData.applications) {
        labelKeySelect.innerHTML += '<option value="__custom__" style="font-style: italic; color: #667eea;">✏️ Enter custom key...</option>';
        labelKeySelect.disabled = true;
        return;
    }
    
    // Collect all unique label keys from applications in the selected namespace
    const labelKeys = new Set();
    allData.applications.forEach(app => {
        if (app.namespace === selectedNamespace && app.labels) {
            Object.keys(app.labels).forEach(key => labelKeys.add(key));
        }
    });
    
    // Sort and add to dropdown
    const sortedKeys = Array.from(labelKeys).sort();
    sortedKeys.forEach(key => {
        const option = document.createElement('option');
        option.value = key;
        option.textContent = key;
        labelKeySelect.appendChild(option);
    });
    
    // Add custom option at the end
    labelKeySelect.innerHTML += '<option value="__custom__" style="font-style: italic; color: #667eea;">✏️ Enter custom key...</option>';
    labelKeySelect.disabled = false;
}

function updateLabelValueOptions() {
    const labelKeySelect = document.getElementById('plan-label-key');
    const labelKeyCustom = document.getElementById('plan-label-key-custom');
    const labelValueSelect = document.getElementById('plan-label-value');
    const labelValueCustom = document.getElementById('plan-label-value-custom');
    const selectedKey = labelKeySelect.value;
    
    // Handle custom key input
    if (selectedKey === '__custom__') {
        labelKeyCustom.style.display = 'block';
        labelValueSelect.disabled = true;
        labelValueSelect.innerHTML = '<option value="">-- Enter custom key first --</option>';
        labelValueCustom.style.display = 'block';
        labelValueCustom.disabled = false;
        updateLabelPreview();
        return;
    } else {
        labelKeyCustom.style.display = 'none';
        labelValueCustom.style.display = 'none';
    }
    
    if (!selectedKey) {
        labelValueSelect.disabled = true;
        labelValueSelect.innerHTML = '<option value="">-- Select a label key first --</option>';
        updateLabelPreview();
        return;
    }
    
    // Get selected namespace
    const namespaceSelect = document.getElementById('plan-namespace-select');
    const customNamespaceInput = document.getElementById('plan-namespace');
    let selectedNamespace = '';
    if (namespaceSelect && namespaceSelect.value === '__custom__') {
        selectedNamespace = customNamespaceInput.value.trim();
    } else if (namespaceSelect) {
        selectedNamespace = namespaceSelect.value;
    }
    
    // Clear existing options
    labelValueSelect.innerHTML = '<option value="">-- Select a label value --</option>';
    
    if (!selectedNamespace || !allData.applications) {
        labelValueSelect.innerHTML += '<option value="__custom__" style="font-style: italic; color: #667eea;">✏️ Enter custom value...</option>';
        labelValueSelect.disabled = false;
        return;
    }
    
    // Collect all unique values for this key from applications in the selected namespace
    const labelValues = new Set();
    allData.applications.forEach(app => {
        if (app.namespace === selectedNamespace && app.labels && app.labels[selectedKey]) {
            labelValues.add(app.labels[selectedKey]);
        }
    });
    
    // Sort and add to dropdown
    const sortedValues = Array.from(labelValues).sort();
    sortedValues.forEach(value => {
        const option = document.createElement('option');
        option.value = value;
        option.textContent = value;
        labelValueSelect.appendChild(option);
    });
    
    // Add custom option at the end
    labelValueSelect.innerHTML += '<option value="__custom__" style="font-style: italic; color: #667eea;">✏️ Enter custom value...</option>';
    labelValueSelect.disabled = false;
    
    updateLabelPreview();
}

function handleLabelValueChange() {
    const labelValueSelect = document.getElementById('plan-label-value');
    const labelValueCustom = document.getElementById('plan-label-value-custom');
    
    if (labelValueSelect.value === '__custom__') {
        labelValueCustom.style.display = 'block';
        labelValueCustom.focus();
    } else {
        labelValueCustom.style.display = 'none';
    }
    
    updateLabelPreview();
}

function updateLabelPreview() {
    const labelKeySelect = document.getElementById('plan-label-key');
    const labelKeyCustom = document.getElementById('plan-label-key-custom');
    const labelValueSelect = document.getElementById('plan-label-value');
    const labelValueCustom = document.getElementById('plan-label-value-custom');
    const previewText = document.getElementById('plan-label-preview-text');
    const matchCount = document.getElementById('plan-label-match-count');
    
    // Get actual label key and value (from dropdown or custom input)
    let labelKey = '';
    let labelValue = '';
    
    if (labelKeySelect.value === '__custom__') {
        labelKey = labelKeyCustom.value.trim();
        // When custom key is used, always get value from custom input
        labelValue = labelValueCustom.value.trim();
    } else {
        labelKey = labelKeySelect.value.trim();
        // When predefined key is used, check if custom value is selected
        if (labelValueSelect.value === '__custom__') {
            labelValue = labelValueCustom.value.trim();
        } else {
            labelValue = labelValueSelect.value.trim();
        }
    }
    
    if (labelKey && labelValue) {
        previewText.textContent = `${labelKey}=${labelValue}`;
        
        // Count matching applications in the selected namespace
        const namespaceSelect = document.getElementById('plan-namespace-select');
        const customNamespaceInput = document.getElementById('plan-namespace');
        let selectedNamespace = '';
        
        if (namespaceSelect && namespaceSelect.value === '__custom__') {
            selectedNamespace = customNamespaceInput.value.trim();
        } else if (namespaceSelect) {
            selectedNamespace = namespaceSelect.value;
        }
        
        if (selectedNamespace && allData.applications) {
            const matchingApps = allData.applications.filter(app => {
                const appNamespace = app.namespace || 'default';
                const appLabels = app.labels || {};
                return appNamespace === selectedNamespace && appLabels[labelKey] === labelValue;
            });
            
            if (matchingApps.length > 0) {
                matchCount.innerHTML = `<span style="color: #28a745; font-weight: 600;">✓ ${matchingApps.length} application${matchingApps.length !== 1 ? 's' : ''} match this selector</span>`;
                matchCount.innerHTML += `<div style="margin-top: 6px; font-size: 0.9em;">${matchingApps.map(app => `• ${app.name}`).join('<br>')}</div>`;
            } else {
                matchCount.innerHTML = `<span style="color: #ff6b6b; font-weight: 600;">⚠ No applications match this selector</span>`;
            }
        } else {
            matchCount.innerHTML = '';
        }
    } else {
        previewText.textContent = '-';
        matchCount.innerHTML = '';
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
    
    // Get retention (count-based only, as NDK requires)
    const retention = parseInt(document.getElementById('plan-retention-count').value);
    
    if (!retention || retention < 1 || retention > 15) {
        showToast('✗ Retention count must be between 1 and 15', 'error');
        return;
    }
    
    // Get selection mode
    const selectionMode = document.querySelector('input[name="plan-selection-mode"]:checked').value;
    
    const enabled = document.getElementById('plan-enabled').checked;
    
    const planData = {
        name: name,
        namespace: namespace,
        schedule: schedule,
        retention: retention,
        enabled: enabled,
        selectionMode: selectionMode
    };
    
    // Handle different selection modes
    if (selectionMode === 'by-name') {
        // Get selected applications
        const selectedApps = [];
        document.querySelectorAll('.app-checkbox:checked').forEach(checkbox => {
            selectedApps.push({
                name: checkbox.dataset.appName,
                namespace: checkbox.dataset.appNamespace
            });
        });
        
        if (selectedApps.length === 0) {
            showToast('✗ Please select at least one application to protect', 'error');
            return;
        }
        
        planData.applications = selectedApps;
    } else {
        // By label selector - get from dropdown or custom input
        const labelKeySelect = document.getElementById('plan-label-key');
        const labelKeyCustom = document.getElementById('plan-label-key-custom');
        const labelValueSelect = document.getElementById('plan-label-value');
        const labelValueCustom = document.getElementById('plan-label-value-custom');
        
        let labelKey = '';
        let labelValue = '';
        
        if (labelKeySelect.value === '__custom__') {
            labelKey = labelKeyCustom.value.trim();
            // When custom key is used, always get value from custom input
            labelValue = labelValueCustom.value.trim();
        } else {
            labelKey = labelKeySelect.value.trim();
            // When predefined key is used, check if custom value is selected
            if (labelValueSelect.value === '__custom__') {
                labelValue = labelValueCustom.value.trim();
            } else {
                labelValue = labelValueSelect.value.trim();
            }
        }
        
        if (!labelKey || !labelValue) {
            showToast('✗ Label key and value are required', 'error');
            return;
        }
        
        planData.labelSelector = {
            key: labelKey,
            value: labelValue
        };
    }
    
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
        
        // Reload protection plans only (don't reload stats to avoid showing "Unknown" for other resources)
        await loadProtectionPlans();
        
        // Update protection plan count in stats without full reload
        const statElement = document.getElementById('stat-plans');
        if (statElement) {
            const currentCount = parseInt(statElement.textContent) || 0;
            statElement.textContent = currentCount + 1;
        }
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
        
        // Reload protection plans only (don't reload stats to avoid showing "Unknown" for other resources)
        await loadProtectionPlans();
        
        // Update protection plan count in stats without full reload
        const statElement = document.getElementById('stat-plans');
        if (statElement) {
            const currentCount = parseInt(statElement.textContent) || 0;
            statElement.textContent = Math.max(0, currentCount - 1);
        }
    } catch (error) {
        console.error('Error deleting protection plan:', error);
        showToast('✗ Error deleting protection plan', 'error');
    }
}

async function forceDeletePlan(name, namespace) {
    if (!confirm(`⚠️ FORCE DELETE WARNING ⚠️\n\nProtection plan "${name}" is stuck in deletion (likely due to finalizers).\n\nForce delete will:\n• Remove all finalizers\n• Force immediate deletion\n• Bypass normal cleanup procedures\n\nThis should only be used when normal deletion fails.\n\nAre you sure you want to force delete?`)) {
        return;
    }
    
    try {
        showToast('Force deleting protection plan...', 'info');
        
        const response = await fetch(`/api/protectionplans/${namespace}/${name}?force=true`, {
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
            showToast(`✗ Failed to force delete: ${result.error}`, 'error');
            return;
        }
        
        const result = await response.json();
        console.log('Protection plan force deleted:', name);
        showToast('✓ Protection plan force deleted successfully', 'success');
        
        // Reload protection plans
        await loadProtectionPlans();
        
        // Update protection plan count in stats
        const statElement = document.getElementById('stat-plans');
        if (statElement) {
            const currentCount = parseInt(statElement.textContent) || 0;
            statElement.textContent = Math.max(0, currentCount - 1);
        }
    } catch (error) {
        console.error('Error force deleting protection plan:', error);
        showToast('✗ Error force deleting protection plan', 'error');
    }
}



async function triggerPlan(name, namespace) {
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

// Edit Protection Plan


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

async function loadWorkerPools() {
    try {
        const response = await fetch('/api/workerpools');
        if (response.ok) {
            const data = await response.json();
            const select = document.getElementById('deploy-worker-pool');
            
            // Clear existing options
            select.innerHTML = '';
            
            // Add default option
            const defaultOption = document.createElement('option');
            defaultOption.value = '';
            defaultOption.textContent = 'Default (Any available node)';
            select.appendChild(defaultOption);
            
            // Add worker pools
            if (data.workerPools && data.workerPools.length > 0) {
                data.workerPools.forEach(pool => {
                    const option = document.createElement('option');
                    option.value = pool;
                    option.textContent = pool;
                    select.appendChild(option);
                });
            }
        }
    } catch (error) {
        console.error('Failed to load worker pools:', error);
        // Keep the default option even if loading fails
    }
}
async function loadStorageClasses() {
    try {
        const response = await fetch('/api/storageclasses');
        if (response.ok) {
            const data = await response.json();
            const select = document.getElementById('deploy-storage-class');
            
            // Clear existing options
            select.innerHTML = '';
            
            // Add storage classes
            if (data.storageClasses && data.storageClasses.length > 0) {
                data.storageClasses.forEach(sc => {
                    const option = document.createElement('option');
                    option.value = sc.name;
                    
                    // Display name with indicator if it's the default
                    if (sc.isDefault) {
                        option.textContent = `${sc.name} (default)`;
                        option.selected = true; // Select the default storage class
                    } else {
                        option.textContent = sc.name;
                    }
                    
                    select.appendChild(option);
                });
            } else {
                // If no storage classes found, add a placeholder
                const option = document.createElement('option');
                option.value = '';
                option.textContent = 'No storage classes available';
                select.appendChild(option);
            }
        }
    } catch (error) {
        console.error('Failed to load storage classes:', error);
        // Add error option
        const select = document.getElementById('deploy-storage-class');
        select.innerHTML = '';
        const option = document.createElement('option');
        option.value = '';
        option.textContent = 'Failed to load storage classes';
        select.appendChild(option);
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
    
    // Refresh the applications list to show only apps in the selected namespace
    populateApplicationsList();
}

// Add event listener for custom namespace input changes
function handleCustomNamespaceInput() {
    // Refresh applications list when custom namespace is typed
    populateApplicationsList();
}

async function loadPlanNamespaces() {
    try {
        const response = await fetch('/api/namespaces');
        if (response.ok) {
            const data = await response.json();
            const select = document.getElementById('plan-namespace-select');
            
            // Clear existing options
            select.innerHTML = '';
            
            // Add placeholder option
            const placeholderOption = document.createElement('option');
            placeholderOption.value = '';
            placeholderOption.textContent = '-- Select a namespace --';
            placeholderOption.disabled = true;
            placeholderOption.selected = true;
            select.appendChild(placeholderOption);
            
            // Add all namespaces
            data.namespaces.forEach(ns => {
                const option = document.createElement('option');
                option.value = ns;
                option.textContent = `📁 ${ns}`;
                select.appendChild(option);
            });
            
            // Add "Create New" option at the end
            const customOption = document.createElement('option');
            customOption.value = '__custom__';
            customOption.textContent = '➕ Create New Namespace...';
            select.appendChild(customOption);
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
    
    // Reset labels
    document.getElementById('deploy-labels-container').innerHTML = '';
    
    // Reset worker pool
    document.getElementById('deploy-worker-pool').value = '';
    
    // Load namespaces for dropdown
    loadNamespaces();
    
    // Load worker pools for dropdown
    loadWorkerPools();

    // Load storage classes for dropdown
    loadStorageClasses();

    document.getElementById('deploy-modal').classList.add('active');
}

// Label management functions
let deployLabelCounter = 0;

function addDeployLabel(key = '', value = '') {
    const container = document.getElementById('deploy-labels-container');
    const labelId = `deploy-label-${deployLabelCounter++}`;
    
    const labelRow = document.createElement('div');
    labelRow.className = 'label-row';
    labelRow.id = labelId;
    labelRow.innerHTML = `
        <input type="text" class="form-control label-key" placeholder="Label key (e.g., environment)" value="${key}">
        <input type="text" class="form-control label-value" placeholder="Label value (e.g., production)" value="${value}">
        <button type="button" class="btn btn-secondary btn-sm" onclick="removeDeployLabel('${labelId}')">
            ➖ Remove
        </button>
    `;
    
    container.appendChild(labelRow);
}

function removeDeployLabel(labelId) {
    const element = document.getElementById(labelId);
    if (element) {
        element.remove();
    }
}

function suggestDeployLabel(key, value) {
    addDeployLabel(key, value);
}

function collectDeployLabels() {
    const labels = {};
    const container = document.getElementById('deploy-labels-container');
    const labelRows = container.querySelectorAll('.label-row');
    
    labelRows.forEach(row => {
        const key = row.querySelector('.label-key').value.trim();
        const value = row.querySelector('.label-value').value.trim();
        
        if (key) {
            // Validate label key format (Kubernetes naming rules)
            if (!/^[a-z0-9]([-a-z0-9_.]*[a-z0-9])?$/.test(key)) {
                throw new Error(`Invalid label key: "${key}". Must be lowercase alphanumeric, dashes, underscores, or dots.`);
            }
            
            // Validate label value format (can be empty)
            if (value && !/^[a-z0-9]([-a-z0-9_.]*[a-z0-9])?$/.test(value)) {
                throw new Error(`Invalid label value: "${value}". Must be lowercase alphanumeric, dashes, underscores, or dots.`);
            }
            
            labels[key] = value;
        }
    });
    
    return labels;
}

function closeDeployModal() {
    document.getElementById('deploy-modal').classList.remove('active');
}

// === EDIT LABELS FUNCTIONS ===
let editLabelCounter = 0;
let currentEditApp = { name: '', namespace: '' };
let originalLabels = {};

async function showEditLabelsModal(appName, namespace) {
    currentEditApp = { name: appName, namespace: namespace };
    
    // Set app info
    document.getElementById('edit-labels-app-name').textContent = appName;
    document.getElementById('edit-labels-namespace').textContent = namespace;
    
    // Clear existing labels
    const container = document.getElementById('edit-labels-container');
    container.innerHTML = '';
    editLabelCounter = 0;
    originalLabels = {};
    
    // Fetch current labels from the application
    try {
        const response = await fetch(`/api/applications/${namespace}/${appName}`);
        if (response.ok) {
            const app = await response.json();
            const labels = app.labels || {};
            originalLabels = { ...labels };
            
            if (Object.keys(labels).length === 0) {
                container.innerHTML = '<div style="text-align: center; padding: 20px; color: var(--text-secondary); font-style: italic;">No labels yet. Click "Add New Label" to get started.</div>';
            } else {
                Object.entries(labels).forEach(([key, value]) => {
                    addEditLabel(key, value, true);
                });
            }
        } else {
            console.error('Failed to fetch application labels');
            container.innerHTML = '<div style="text-align: center; padding: 20px; color: var(--error);">Failed to load labels</div>';
        }
    } catch (error) {
        console.error('Error fetching application labels:', error);
        container.innerHTML = '<div style="text-align: center; padding: 20px; color: var(--error);">Error loading labels</div>';
    }
    
    // Show modal
    document.getElementById('edit-labels-modal').style.display = 'flex';
}

function closeEditLabelsModal() {
    document.getElementById('edit-labels-modal').style.display = 'none';
}

function isSystemLabel(key) {
    const systemPrefixes = ['app.kubernetes.io/', 'kubernetes.io/', 'k8s.io/', 'helm.sh/'];
    return systemPrefixes.some(prefix => key.startsWith(prefix));
}

function addEditLabel(key = '', value = '', readonly = false) {
    const container = document.getElementById('edit-labels-container');
    
    if (container.querySelector('div[style*="text-align: center"]')) {
        container.innerHTML = '';
    }
    
    const labelId = `edit-label-${editLabelCounter++}`;
    const labelRow = document.createElement('div');
    labelRow.className = 'label-row';
    labelRow.id = labelId;
    
    let badge = '';
    let keyReadonly = '';
    let removeDisabled = '';
    let removeTitle = '';
    let removeStyle = '';
    
    if (readonly && key) {
        const isSystem = isSystemLabel(key);
        if (isSystem) {
            badge = '<span style="display: inline-flex; align-items: center; background-color: #fff3cd; color: #856404; padding: 2px 8px; border-radius: 4px; font-size: 0.7rem; font-weight: 600; white-space: nowrap;">🔒 System</span>';
            keyReadonly = 'readonly';
            removeDisabled = 'disabled';
            removeTitle = 'title="System labels cannot be removed"';
        } else {
            badge = '<span style="display: inline-flex; align-items: center; background-color: #e3f2fd; color: #1976d2; padding: 2px 8px; border-radius: 4px; font-size: 0.7rem; font-weight: 600; white-space: nowrap;">Existing</span>';
            removeStyle = 'style="background-color: #dc3545; color: white;"';
        }
    } else if (!readonly && key === '') {
        badge = '<span style="display: inline-flex; align-items: center; background-color: #d4edda; color: #155724; padding: 2px 8px; border-radius: 4px; font-size: 0.7rem; font-weight: 600; white-space: nowrap;">New</span>';
    }
    
    labelRow.innerHTML = `
        ${badge}
        <input type="text" class="form-control label-key" placeholder="Label key (e.g., environment)" value="${escapeHtml(key)}" ${keyReadonly}>
        <input type="text" class="form-control label-value" placeholder="Label value (e.g., production)" value="${escapeHtml(value)}">
        <button type="button" class="btn btn-secondary btn-sm" onclick="removeEditLabel('${labelId}')" ${removeDisabled} ${removeTitle} ${removeStyle}>
            Remove
        </button>
    `;
    
    container.appendChild(labelRow);
}

function removeEditLabel(labelId) {
    const element = document.getElementById(labelId);
    if (element) {
        element.remove();
    }
}

function suggestEditLabel(key, value) {
    addEditLabel(key, value);
}

function collectEditLabels() {
    const labels = {};
    const labelsToRemove = [];
    const container = document.getElementById('edit-labels-container');
    const labelRows = container.querySelectorAll('.label-row');
    
    const currentLabels = {};
    labelRows.forEach(row => {
        const key = row.querySelector('.label-key').value.trim();
        const value = row.querySelector('.label-value').value.trim();
        
        if (key) {
            const keyPattern = /^([a-z0-9]([-a-z0-9.]*[a-z0-9])?\/)?[a-z0-9]([-a-z0-9_.]*[a-z0-9])?$/i;
            if (!keyPattern.test(key)) {
                throw new Error(`Invalid label key: "${key}". Must follow Kubernetes label naming rules.`);
            }
            
            if (value && !/^[a-z0-9]([-a-z0-9_.]*[a-z0-9])?$/i.test(value)) {
                throw new Error(`Invalid label value: "${value}". Must be alphanumeric with dashes, underscores, or dots.`);
            }
            
            currentLabels[key] = value;
            labels[key] = value;
        }
    });
    
    for (const key in originalLabels) {
        if (!(key in currentLabels) && !isSystemLabel(key)) {
            labelsToRemove.push(key);
        }
    }
    
    return { labels, labelsToRemove };
}

async function saveApplicationLabels() {
    try {
        const result = collectEditLabels();
        const { labels, labelsToRemove } = result;
        
        // Calculate change summary
        let addedCount = 0;
        let updatedCount = 0;
        for (const key in labels) {
            if (key in originalLabels) {
                if (originalLabels[key] !== labels[key]) {
                    updatedCount++;
                }
            } else {
                addedCount++;
            }
        }
        const removedCount = labelsToRemove.length;
        
        // Check if there are any changes
        if (addedCount === 0 && updatedCount === 0 && removedCount === 0) {
            showToast('No changes detected', 'info');
            return;
        }
        
        const response = await fetch(`/api/applications/${currentEditApp.namespace}/${currentEditApp.name}/labels`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ 
                labels: labels,
                labels_to_remove: labelsToRemove
            })
        });
        
        if (response.ok) {
            const changeSummary = [];
            if (addedCount > 0) changeSummary.push(`${addedCount} added`);
            if (updatedCount > 0) changeSummary.push(`${updatedCount} updated`);
            if (removedCount > 0) changeSummary.push(`${removedCount} removed`);
            
            const message = `Labels updated successfully (${changeSummary.join(', ')})`;
            showToast(message, 'success');
            closeEditLabelsModal();
            loadApplications(); // Refresh the applications table
        } else {
            const error = await response.json();
            showToast(`Failed to update labels: ${error.error || 'Unknown error'}`, 'error');
        }
    } catch (error) {
        showToast(`Error: ${error.message}`, 'error');
    }
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
    
    // Collect and validate labels
    let labels = {};
    try {
        labels = collectDeployLabels();
    } catch (error) {
        alert(error.message);
        return;
    }
    
    const template = APP_TEMPLATES[appType];
    
    // Get worker pool selection
    const workerPool = document.getElementById('deploy-worker-pool').value;
    
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
        createNDKApp: createNDKApp,
        labels: labels,  // Add labels to deployment config
        workerPool: workerPool || null  // Add worker pool to deployment config
    };
    
    // Add protection plan config if enabled
    if (createProtectionPlan) {
        const retention = parseInt(document.getElementById('deploy-protection-retention').value);
        
        // Validate retention count (NDK requires 1-15)
        if (isNaN(retention) || retention < 1 || retention > 15) {
            alert('Retention count must be a number between 1 and 15');
            return;
        }
        
        deployConfig.protectionPlan = {
            schedule: document.getElementById('deploy-protection-schedule').value,
            retention: retention
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

function toggleYAMLDropdown(event) {
    event.stopPropagation();
    const dropdown = document.getElementById('yaml-dropdown');
    dropdown.style.display = dropdown.style.display === 'none' ? 'block' : 'none';
}

document.addEventListener('click', function(event) {
    const dropdown = document.getElementById('yaml-dropdown');
    if (dropdown && !event.target.closest('#yaml-dropdown') && !event.target.closest('button[onclick*="toggleYAMLDropdown"]')) {
        dropdown.style.display = 'none';
    }
});

function downloadYAML(appType) {
    document.getElementById('yaml-dropdown').style.display = 'none';
    
    const configs = {
        mysql: {
            name: 'mysql',
            image: 'mysql:8.0',
            port: 3306,
            envVars: `        - name: MYSQL_ROOT_PASSWORD
          valueFrom:
            secretKeyRef:
              name: {{APP_NAME}}-credentials
              key: password
        - name: MYSQL_DATABASE
          valueFrom:
            secretKeyRef:
              name: {{APP_NAME}}-credentials
              key: database`,
            mountPath: '/var/lib/mysql',
            secretData: `  password: "your-secure-password"
  database: "mydb"`
        },
        postgresql: {
            name: 'postgresql',
            image: 'postgres:15',
            port: 5432,
            envVars: `        - name: POSTGRES_PASSWORD
          valueFrom:
            secretKeyRef:
              name: {{APP_NAME}}-credentials
              key: password
        - name: POSTGRES_DB
          valueFrom:
            secretKeyRef:
              name: {{APP_NAME}}-credentials
              key: database`,
            mountPath: '/var/lib/postgresql/data',
            secretData: `  password: "your-secure-password"
  database: "mydb"`
        },
        mongodb: {
            name: 'mongodb',
            image: 'mongo:7.0',
            port: 27017,
            envVars: `        - name: MONGO_INITDB_ROOT_PASSWORD
          valueFrom:
            secretKeyRef:
              name: {{APP_NAME}}-credentials
              key: password`,
            mountPath: '/data/db',
            secretData: `  password: "your-secure-password"`
        },
        elasticsearch: {
            name: 'elasticsearch',
            image: 'docker.elastic.co/elasticsearch/elasticsearch:8.11.0',
            port: 9200,
            envVars: `        - name: ELASTIC_PASSWORD
          valueFrom:
            secretKeyRef:
              name: {{APP_NAME}}-credentials
              key: password
        - name: discovery.type
          value: single-node
        - name: xpack.security.enabled
          value: "true"`,
            mountPath: '/usr/share/elasticsearch/data',
            secretData: `  password: "your-secure-password"`
        }
    };
    
    const config = configs[appType];
    
    const yamlContent = `---
# Namespace
apiVersion: v1
kind: Namespace
metadata:
  name: {{NAMESPACE}}

---
# Secret for credentials
apiVersion: v1
kind: Secret
metadata:
  name: {{APP_NAME}}-credentials
  namespace: {{NAMESPACE}}
  labels:
    app: {{APP_NAME}}
type: Opaque
stringData:
${config.secretData}

---
# Service
apiVersion: v1
kind: Service
metadata:
  name: {{APP_NAME}}
  namespace: {{NAMESPACE}}
  labels:
    app: {{APP_NAME}}
spec:
  ports:
  - port: ${config.port}
    name: ${config.name}
  clusterIP: None
  selector:
    app: {{APP_NAME}}

---
# StatefulSet
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: {{APP_NAME}}
  namespace: {{NAMESPACE}}
  labels:
    app: {{APP_NAME}}
spec:
  serviceName: {{APP_NAME}}
  replicas: {{REPLICAS}}
  selector:
    matchLabels:
      app: {{APP_NAME}}
  template:
    metadata:
      labels:
        app: {{APP_NAME}}
    spec:
      containers:
      - name: ${config.name}
        image: ${config.image}
        ports:
        - containerPort: ${config.port}
          name: ${config.name}
        env:
${config.envVars}
        volumeMounts:
        - name: data
          mountPath: ${config.mountPath}
  volumeClaimTemplates:
  - metadata:
      name: data
      labels:
        app: {{APP_NAME}}
    spec:
      accessModes: ["ReadWriteOnce"]
      storageClassName: {{STORAGE_CLASS}}
      resources:
        requests:
          storage: {{STORAGE_SIZE}}

---
# NDK Application CR (Enable NDK Data Services)
apiVersion: dataservices.nutanix.com/v1alpha1
kind: Application
metadata:
  name: {{APP_NAME}}
  namespace: {{NAMESPACE}}
  labels:
    app.kubernetes.io/managed-by: ndk-dashboard
    {{CUSTOM_LABELS}}
spec:
  applicationSelector:
    resourceLabelSelectors:
    - labelSelector:
        matchLabels:
          app: {{APP_NAME}}
  start: true
  useExistingConfig: false

---
# JobScheduler for Protection Plan
apiVersion: scheduler.nutanix.com/v1alpha1
kind: JobScheduler
metadata:
  name: {{APP_NAME}}-plan-scheduler
  namespace: {{NAMESPACE}}
spec:
  cronSchedule: "{{CRON_SCHEDULE}}"

---
# ProtectionPlan
apiVersion: dataservices.nutanix.com/v1alpha1
kind: ProtectionPlan
metadata:
  name: {{APP_NAME}}-plan
  namespace: {{NAMESPACE}}
  annotations:
    ndk-dashboard/selection-mode: by-name
spec:
  scheduleName: {{APP_NAME}}-plan-scheduler
  retentionPolicy:
    retentionCount: {{RETENTION_COUNT}}
  applications:
  - {{APP_NAME}}

---
# AppProtectionPlan (Links Application to ProtectionPlan)
apiVersion: dataservices.nutanix.com/v1alpha1
kind: AppProtectionPlan
metadata:
  name: {{APP_NAME}}-{{APP_NAME}}-plan
  namespace: {{NAMESPACE}}
spec:
  applicationName: {{APP_NAME}}
  protectionPlanNames:
  - {{APP_NAME}}-plan
`;

    const blob = new Blob([yamlContent], { type: 'text/yaml' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `ndk-${config.name}-deployment.yaml`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    
    showToast(`✓ ${config.name.charAt(0).toUpperCase() + config.name.slice(1)} YAML downloaded`, 'success');
}