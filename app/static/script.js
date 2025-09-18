/**
 * HTTPx Cloud Scanner - Futuristic Frontend
 * Modern JavaScript with enhanced features
 */

// Global state
let authToken = null;
let currentUser = null;
let websocket = null;
let currentScanId = null;
let dashboardStats = {};
let isLogsPaused = false;

// DOM elements
const loginModal = document.getElementById('loginModal');
const passwordModal = document.getElementById('passwordModal');
const mainApp = document.getElementById('mainApp');
const uploadModal = document.getElementById('uploadModal');
const connectionStatus = document.getElementById('connectionStatus');

// Initialize app
document.addEventListener('DOMContentLoaded', function() {
    console.log('🚀 HTTPx Cloud Scanner initializing...');
    checkAuthentication();
    setupEventListeners();
    setupConcurrencySlider();
});

// Authentication functions
function checkAuthentication() {
    authToken = localStorage.getItem('authToken');
    if (authToken) {
        validateToken();
    } else {
        showLogin();
    }
}

function showLogin() {
    if (loginModal) {
        loginModal.classList.add('show');
    }
    if (mainApp) {
        mainApp.style.display = 'none';
    }
}

function showPasswordChange() {
    if (loginModal) {
        loginModal.classList.remove('show');
    }
    if (passwordModal) {
        passwordModal.classList.add('show');
    }
}

function showMainApp() {
    if (loginModal) {
        loginModal.classList.remove('show');
    }
    if (passwordModal) {
        passwordModal.classList.remove('show');
    }
    if (mainApp) {
        mainApp.style.display = 'block';
    }
    
    // Load initial data
    loadDashboard();
    loadLists();
    setupWebSocket();
    
    // Update user info
    if (currentUser) {
        const userInfo = document.getElementById('userInfo');
        if (userInfo) {
            userInfo.textContent = currentUser.username || 'User';
        }
    }
}

async function validateToken() {
    try {
        const response = await fetch('/api/v1/healthz', {
            headers: { 'Authorization': `Bearer ${authToken}` }
        });
        
        if (response.ok) {
            showMainApp();
        } else {
            localStorage.removeItem('authToken');
            showLogin();
        }
    } catch (error) {
        console.error('Token validation failed:', error);
        showLogin();
    }
}

function logout() {
    localStorage.removeItem('authToken');
    authToken = null;
    currentUser = null;
    if (websocket) {
        websocket.close();
        websocket = null;
    }
    showLogin();
}

// Event listeners
function setupEventListeners() {
    // Login form
    const loginForm = document.getElementById('loginForm');
    if (loginForm) {
        loginForm.addEventListener('submit', handleLogin);
    }

    // Password form
    const passwordForm = document.getElementById('passwordForm');
    if (passwordForm) {
        passwordForm.addEventListener('submit', handlePasswordChange);
    }

    // Logout button
    const logoutBtn = document.getElementById('logoutBtn');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', logout);
    }

    // Tab navigation
    document.querySelectorAll('.nav-tab').forEach(tab => {
        tab.addEventListener('click', (e) => {
            const tabName = e.currentTarget.dataset.tab;
            showTab(tabName);
        });
    });

    // Scan form
    const scanForm = document.getElementById('scanForm');
    if (scanForm) {
        scanForm.addEventListener('submit', handleScanSubmit);
    }

    // Upload list button
    const uploadListBtn = document.getElementById('uploadListBtn');
    if (uploadListBtn) {
        uploadListBtn.addEventListener('click', showUploadModal);
    }

    // Upload form
    const uploadForm = document.getElementById('uploadForm');
    if (uploadForm) {
        uploadForm.addEventListener('submit', handleUploadSubmit);
    }

    // Scan controls
    const pauseBtn = document.getElementById('pauseBtn');
    const resumeBtn = document.getElementById('resumeBtn');
    const stopBtn = document.getElementById('stopBtn');
    
    if (pauseBtn) pauseBtn.addEventListener('click', () => controlScan('pause'));
    if (resumeBtn) resumeBtn.addEventListener('click', () => controlScan('resume'));
    if (stopBtn) stopBtn.addEventListener('click', () => controlScan('stop'));

    // Clear logs
    const clearLogs = document.getElementById('clearLogs');
    if (clearLogs) {
        clearLogs.addEventListener('click', () => {
            const container = document.getElementById('liveLogsContainer');
            if (container) {
                container.innerHTML = '<div class="log-line"><span class="log-time">--:--:--</span><span class="log-level info">INFO</span><span class="log-message">Logs cleared</span></div>';
            }
        });
    }

    // Pause logs
    const pauseLogs = document.getElementById('pauseLogs');
    if (pauseLogs) {
        pauseLogs.addEventListener('click', () => {
            isLogsPaused = !isLogsPaused;
            pauseLogs.textContent = isLogsPaused ? 'Resume' : 'Pause';
        });
    }
}

// Login handling
async function handleLogin(e) {
    e.preventDefault();
    const formData = new FormData(e.target);
    const loginError = document.getElementById('loginError');
    
    try {
        const response = await fetch('/api/v1/auth/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                username: formData.get('username'),
                password: formData.get('password')
            })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            authToken = data.access_token;
            currentUser = data.user;
            localStorage.setItem('authToken', authToken);
            
            if (data.requires_password_change) {
                showPasswordChange();
            } else {
                showMainApp();
            }
        } else {
            if (loginError) {
                loginError.textContent = data.detail || 'Login failed';
            }
        }
    } catch (error) {
        console.error('Login error:', error);
        if (loginError) {
            loginError.textContent = 'Network error. Please try again.';
        }
    }
}

// Password change handling
async function handlePasswordChange(e) {
    e.preventDefault();
    const formData = new FormData(e.target);
    const passwordError = document.getElementById('passwordError');
    
    const newPassword = formData.get('newPassword');
    const confirmPassword = formData.get('confirmPassword');
    
    if (newPassword !== confirmPassword) {
        if (passwordError) {
            passwordError.textContent = 'Passwords do not match';
        }
        return;
    }
    
    try {
        const response = await fetch('/api/v1/auth/change-password', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${authToken}`
            },
            body: JSON.stringify({
                old_password: formData.get('oldPassword'),
                new_password: newPassword
            })
        });
        
        if (response.ok) {
            showMainApp();
        } else {
            const data = await response.json();
            if (passwordError) {
                passwordError.textContent = data.detail || 'Password change failed';
            }
        }
    } catch (error) {
        console.error('Password change error:', error);
        if (passwordError) {
            passwordError.textContent = 'Network error. Please try again.';
        }
    }
}

// Tab switching
function showTab(tabName) {
    // Update nav tabs
    document.querySelectorAll('.nav-tab').forEach(tab => {
        tab.classList.remove('active');
    });
    const activeTab = document.querySelector(`[data-tab="${tabName}"]`);
    if (activeTab) {
        activeTab.classList.add('active');
    }
    
    // Update tab content
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.remove('active');
    });
    const activeContent = document.getElementById(tabName);
    if (activeContent) {
        activeContent.classList.add('active');
    }
    
    // Load tab-specific data
    switch (tabName) {
        case 'dashboard':
            loadDashboard();
            break;
        case 'lists':
            loadLists();
            break;
        case 'hits':
            loadHits();
            break;
        case 'settings':
            loadSettings();
            break;
    }
}

// Concurrency slider
function setupConcurrencySlider() {
    const slider = document.getElementById('concurrency');
    const valueDisplay = document.getElementById('concurrencyValue');
    
    if (slider && valueDisplay) {
        slider.addEventListener('input', (e) => {
            const value = parseInt(e.target.value);
            valueDisplay.textContent = formatNumber(value);
        });
    }
}

// Dashboard functions
async function loadDashboard() {
    try {
        const response = await fetch('/api/v1/stats/dashboard', {
            headers: { 'Authorization': `Bearer ${authToken}` }
        });
        
        if (response.ok) {
            const stats = await response.json();
            updateDashboardStats(stats);
        }
    } catch (error) {
        console.error('Error loading dashboard:', error);
    }
}

function updateDashboardStats(stats) {
    // Update stat cards
    updateElement('activeScansCount', stats.active_scans || 0);
    updateElement('totalHitsCount', stats.total_hits || 0);
    updateElement('verifiedHitsCount', stats.verified_hits || 0);
    
    // Update service breakdown
    updateServiceBreakdown(stats.service_breakdown || {});
}

function updateServiceBreakdown(services) {
    const container = document.getElementById('serviceBreakdown');
    if (!container) return;
    
    container.innerHTML = '';
    
    Object.entries(services).forEach(([service, count]) => {
        const item = document.createElement('div');
        item.className = 'service-item';
        item.innerHTML = `
            <span class="service-name">${service}</span>
            <span class="service-count">${count}</span>
        `;
        container.appendChild(item);
    });
}

// Scan functions
async function handleScanSubmit(e) {
    e.preventDefault();
    const formData = new FormData(e.target);
    
    // Get selected modules
    const modules = Array.from(document.querySelectorAll('input[name="modules"]:checked'))
        .map(cb => cb.value);
    
    // Get targets
    let targets = formData.get('targets').split('\n').filter(t => t.trim());
    
    // If no targets but list selected, we'll use the list
    const listId = formData.get('listSelect');
    if (!targets.length && !listId) {
        showError('Please provide targets or select a list');
        return;
    }
    
    const scanRequest = {
        targets: targets,
        list_id: listId || null,
        modules: modules,
        concurrency: parseInt(formData.get('concurrency')),
        timeout: parseInt(formData.get('timeout')),
        notes: formData.get('scanName')
    };
    
    try {
        const response = await fetch('/api/v1/scans', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${authToken}`
            },
            body: JSON.stringify(scanRequest)
        });
        
        if (response.ok) {
            const result = await response.json();
            currentScanId = result.scan_id;
            
            // Show scan monitor
            const scanConfig = document.getElementById('scanConfig');
            const scanMonitor = document.getElementById('scanMonitor');
            const activeScanName = document.getElementById('activeScanName');
            
            if (scanConfig) scanConfig.style.display = 'none';
            if (scanMonitor) scanMonitor.style.display = 'block';
            if (activeScanName) activeScanName.textContent = formData.get('scanName') || 'Unnamed Scan';
            
            // Subscribe to scan updates
            subscribeToScan(currentScanId);
        } else {
            const error = await response.json();
            showError(error.detail || 'Failed to start scan');
        }
    } catch (error) {
        console.error('Scan submission error:', error);
        showError('Network error. Please try again.');
    }
}

async function controlScan(action) {
    if (!currentScanId) return;
    
    try {
        const response = await fetch(`/api/v1/scans/${currentScanId}/control?action=${action}`, {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${authToken}` }
        });
        
        if (response.ok) {
            const result = await response.json();
            console.log(`Scan ${action}:`, result);
            
            // Update UI based on action
            const pauseBtn = document.getElementById('pauseBtn');
            const resumeBtn = document.getElementById('resumeBtn');
            const scanConfig = document.getElementById('scanConfig');
            const scanMonitor = document.getElementById('scanMonitor');
            
            if (action === 'pause') {
                if (pauseBtn) pauseBtn.style.display = 'none';
                if (resumeBtn) resumeBtn.style.display = 'inline-flex';
            } else if (action === 'resume') {
                if (pauseBtn) pauseBtn.style.display = 'inline-flex';
                if (resumeBtn) resumeBtn.style.display = 'none';
            } else if (action === 'stop') {
                // Reset to scan config
                if (scanConfig) scanConfig.style.display = 'block';
                if (scanMonitor) scanMonitor.style.display = 'none';
                currentScanId = null;
            }
        }
    } catch (error) {
        console.error(`Error ${action} scan:`, error);
    }
}

// Lists functions
async function loadLists() {
    try {
        const response = await fetch('/api/v1/lists', {
            headers: { 'Authorization': `Bearer ${authToken}` }
        });
        
        if (response.ok) {
            const data = await response.json();
            updateListsGrid(data.lists);
            updateListSelect(data.lists);
        }
    } catch (error) {
        console.error('Error loading lists:', error);
    }
}

function updateListsGrid(lists) {
    const grid = document.getElementById('listsGrid');
    if (!grid) return;
    
    if (lists.length === 0) {
        grid.innerHTML = `
            <div class="empty-state">
                <div class="empty-icon">📁</div>
                <h4>No lists uploaded yet</h4>
                <p>Upload wordlists, target lists, or IP ranges to get started</p>
            </div>
        `;
        return;
    }
    
    grid.innerHTML = lists.map(list => `
        <div class="list-card">
            <div class="list-header">
                <h4>${list.name}</h4>
                <span class="list-type">${list.list_type}</span>
            </div>
            <div class="list-info">
                <div class="list-stat">
                    <span class="stat-label">Items:</span>
                    <span class="stat-value">${formatNumber(list.items_count)}</span>
                </div>
                <div class="list-stat">
                    <span class="stat-label">Size:</span>
                    <span class="stat-value">${formatBytes(list.file_size)}</span>
                </div>
            </div>
            <div class="list-actions">
                <button class="btn btn-small btn-secondary" onclick="downloadList('${list.id}')">Download</button>
                <button class="btn btn-small btn-danger" onclick="deleteList('${list.id}')">Delete</button>
            </div>
        </div>
    `).join('');
}

function updateListSelect(lists) {
    const select = document.getElementById('listSelect');
    if (!select) return;
    
    // Keep the default option
    const defaultOption = select.querySelector('option[value=""]');
    select.innerHTML = '';
    if (defaultOption) {
        select.appendChild(defaultOption);
    }
    
    lists.forEach(list => {
        const option = document.createElement('option');
        option.value = list.id;
        option.textContent = `${list.name} (${list.list_type}, ${formatNumber(list.items_count)} items)`;
        select.appendChild(option);
    });
}

function showUploadModal() {
    if (uploadModal) {
        uploadModal.classList.add('show');
    }
}

function closeUploadModal() {
    if (uploadModal) {
        uploadModal.classList.remove('show');
    }
}

async function handleUploadSubmit(e) {
    e.preventDefault();
    const formData = new FormData();
    
    const name = document.getElementById('uploadName').value;
    const type = document.getElementById('uploadType').value;
    const description = document.getElementById('uploadDescription').value;
    const file = document.getElementById('uploadFile').files[0];
    
    if (!file) {
        showError('Please select a file');
        return;
    }
    
    formData.append('file', file);
    
    try {
        const response = await fetch(`/api/v1/lists/upload?name=${encodeURIComponent(name)}&list_type=${type}&description=${encodeURIComponent(description)}`, {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${authToken}` },
            body: formData
        });
        
        if (response.ok) {
            closeUploadModal();
            loadLists(); // Reload lists
            showSuccess('List uploaded successfully');
        } else {
            const error = await response.json();
            showError(error.detail || 'Upload failed');
        }
    } catch (error) {
        console.error('Upload error:', error);
        showError('Network error. Please try again.');
    }
}

// Hits functions
async function loadHits() {
    try {
        const response = await fetch('/api/v1/scans', {
            headers: { 'Authorization': `Bearer ${authToken}` }
        });
        
        if (response.ok) {
            const data = await response.json();
            // For now, just show empty state
            // TODO: Implement hits table with virtualization
        }
    } catch (error) {
        console.error('Error loading hits:', error);
    }
}

// Settings functions
async function loadSettings() {
    try {
        const response = await fetch('/api/v1/settings', {
            headers: { 'Authorization': `Bearer ${authToken}` }
        });
        
        if (response.ok) {
            const settings = await response.json();
            // TODO: Update settings UI
        }
    } catch (error) {
        console.error('Error loading settings:', error);
    }
}

// WebSocket functions
function setupWebSocket() {
    if (websocket) {
        websocket.close();
    }
    
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/dashboard?token=${authToken}`;
    
    websocket = new WebSocket(wsUrl);
    
    websocket.onopen = () => {
        console.log('🔗 WebSocket connected');
        updateConnectionStatus(true);
    };
    
    websocket.onmessage = (event) => {
        const message = JSON.parse(event.data);
        handleWebSocketMessage(message);
    };
    
    websocket.onclose = () => {
        console.log('❌ WebSocket disconnected');
        updateConnectionStatus(false);
        
        // Reconnect after 5 seconds
        setTimeout(setupWebSocket, 5000);
    };
    
    websocket.onerror = (error) => {
        console.error('WebSocket error:', error);
        updateConnectionStatus(false);
    };
}

function subscribeToScan(scanId) {
    if (websocket && websocket.readyState === WebSocket.OPEN) {
        websocket.send(JSON.stringify({
            type: 'subscribe',
            channel: `scan:${scanId}`
        }));
    }
}

function handleWebSocketMessage(message) {
    switch (message.type) {
        case 'dashboard_stats':
            updateDashboardStats(message.data);
            break;
        case 'scan_progress':
            updateScanProgress(message.data);
            break;
        case 'scan_log':
            if (!isLogsPaused) {
                addLogLine(message.data);
            }
            break;
        case 'scan_hit':
            showNotification('New hit found!', 'success');
            break;
    }
}

function updateConnectionStatus(connected) {
    if (!connectionStatus) return;
    
    const statusDot = connectionStatus.querySelector('.status-dot');
    const statusText = connectionStatus.querySelector('span');
    
    if (connected) {
        if (statusDot) {
            statusDot.classList.remove('disconnected');
            statusDot.classList.add('connected');
        }
        if (statusText) {
            statusText.textContent = 'Connected';
        }
    } else {
        if (statusDot) {
            statusDot.classList.remove('connected');
            statusDot.classList.add('disconnected');
        }
        if (statusText) {
            statusText.textContent = 'Connecting...';
        }
    }
}

function updateScanProgress(data) {
    // Update progress bar
    const progressPercent = document.getElementById('progressPercent');
    const progressFill = document.getElementById('progressFill');
    const processedUrls = document.getElementById('processedUrls');
    const totalUrls = document.getElementById('totalUrls');
    
    if (progressPercent) progressPercent.textContent = `${data.progress_percent}%`;
    if (progressFill) progressFill.style.width = `${data.progress_percent}%`;
    if (processedUrls) processedUrls.textContent = formatNumber(data.processed_urls);
    if (totalUrls) totalUrls.textContent = formatNumber(data.total_urls);
    
    // Update stats
    updateElement('hitsFound', data.hits_count || 0);
    updateElement('urlsPerSec', Math.round(data.urls_per_sec || 0));
    updateElement('errorsCount', data.errors_count || 0);
    
    // Update ETA
    if (data.eta_seconds) {
        updateElement('eta', formatDuration(data.eta_seconds));
    }
}

function addLogLine(logData) {
    const container = document.getElementById('liveLogsContainer');
    if (!container) return;
    
    const logLine = document.createElement('div');
    logLine.className = 'log-line';
    
    const now = new Date();
    const time = now.toTimeString().split(' ')[0];
    
    logLine.innerHTML = `
        <span class="log-time">${time}</span>
        <span class="log-level ${logData.level || 'info'}">${(logData.level || 'info').toUpperCase()}</span>
        <span class="log-message">${logData.message}</span>
    `;
    
    container.appendChild(logLine);
    
    // Keep only last 100 log lines
    const lines = container.querySelectorAll('.log-line');
    if (lines.length > 100) {
        lines[0].remove();
    }
    
    // Auto scroll to bottom
    container.scrollTop = container.scrollHeight;
}

// Utility functions
function updateElement(id, value) {
    const element = document.getElementById(id);
    if (element) {
        element.textContent = value;
    }
}

function formatNumber(num) {
    if (num >= 1000000) {
        return (num / 1000000).toFixed(1) + 'M';
    } else if (num >= 1000) {
        return (num / 1000).toFixed(1) + 'k';
    }
    return num.toString();
}

function formatBytes(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

function formatDuration(seconds) {
    if (seconds < 60) {
        return `${seconds}s`;
    } else if (seconds < 3600) {
        return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
    } else {
        const hours = Math.floor(seconds / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        return `${hours}h ${minutes}m`;
    }
}

function showError(message) {
    showNotification(message, 'error');
}

function showSuccess(message) {
    showNotification(message, 'success');
}

function showNotification(message, type = 'info') {
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.textContent = message;
    
    // Add styles
    Object.assign(notification.style, {
        position: 'fixed',
        top: '20px',
        right: '20px',
        padding: '12px 24px',
        borderRadius: '8px',
        color: 'white',
        fontWeight: '500',
        zIndex: '10000',
        opacity: '0',
        transform: 'translateY(-20px)',
        transition: 'all 0.3s ease',
        maxWidth: '400px'
    });
    
    // Set type-specific styles
    switch (type) {
        case 'success':
            notification.style.background = '#10B981';
            break;
        case 'error':
            notification.style.background = '#EF4444';
            break;
        default:
            notification.style.background = '#6B7280';
    }
    
    // Add to page
    document.body.appendChild(notification);
    
    // Animate in
    setTimeout(() => {
        notification.style.opacity = '1';
        notification.style.transform = 'translateY(0)';
    }, 10);
    
    // Remove after 5 seconds
    setTimeout(() => {
        notification.style.opacity = '0';
        notification.style.transform = 'translateY(-20px)';
        setTimeout(() => {
            if (notification.parentNode) {
                notification.parentNode.removeChild(notification);
            }
        }, 300);
    }, 5000);
}

// Global functions for HTML onclick handlers
window.showTab = showTab;
window.closeUploadModal = closeUploadModal;

window.downloadList = async function(listId) {
    try {
        const response = await fetch(`/api/v1/lists/${listId}/download`, {
            headers: { 'Authorization': `Bearer ${authToken}` }
        });
        
        if (response.ok) {
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `list_${listId}.txt`;
            a.click();
            window.URL.revokeObjectURL(url);
        }
    } catch (error) {
        console.error('Download error:', error);
        showError('Failed to download list');
    }
};

window.deleteList = async function(listId) {
    if (!confirm('Are you sure you want to delete this list?')) return;
    
    try {
        const response = await fetch(`/api/v1/lists/${listId}`, {
            method: 'DELETE',
            headers: { 'Authorization': `Bearer ${authToken}` }
        });
        
        if (response.ok) {
            loadLists(); // Reload lists
            showSuccess('List deleted successfully');
        } else {
            showError('Failed to delete list');
        }
    } catch (error) {
        console.error('Delete error:', error);
        showError('Failed to delete list');
    }
};

console.log('✨ HTTPx Cloud Scanner loaded');