/* Futuristic HTTPx Cloud Scanner - JavaScript */

// Global variables
let authToken = localStorage.getItem('authToken');
let currentUser = null;
let currentScanId = null;
let websocketConnection = null;
let dashboardWebSocket = null;
let isFirstLogin = false;

// API Base URL
const API_BASE = '/api/v1';

// Initialize the application
document.addEventListener('DOMContentLoaded', function() {
    initializeApp();
});

function initializeApp() {
    console.log('🚀 Initializing HTTPx Cloud Scanner...');
    
    // Check authentication status
    if (authToken) {
        verifyTokenAndShowApp();
    } else {
        showLogin();
    }
    
    // Setup event listeners
    setupEventListeners();
    
    // Initialize UI components
    initializeUIComponents();
}

function setupEventListeners() {
    // Login form
    const loginForm = document.getElementById('loginForm');
    if (loginForm) {
        loginForm.addEventListener('submit', handleLogin);
    }
    
    // Password change form
    const passwordForm = document.getElementById('passwordForm');
    if (passwordForm) {
        passwordForm.addEventListener('submit', handlePasswordChange);
    }
    
    // Logout button
    const logoutBtn = document.getElementById('logoutBtn');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', handleLogout);
    }
    
    // Navigation buttons
    const navButtons = document.querySelectorAll('.nav-btn');
    navButtons.forEach(btn => {
        btn.addEventListener('click', (e) => {
            const tab = e.currentTarget.dataset.tab;
            switchTab(tab);
        });
    });
    
    // Scan form
    const scanForm = document.getElementById('scanForm');
    if (scanForm) {
        scanForm.addEventListener('submit', handleScanSubmit);
    }
    
    // File upload buttons
    const uploadTargetsBtn = document.getElementById('uploadTargetsBtn');
    const targetsFile = document.getElementById('targetsFile');
    if (uploadTargetsBtn && targetsFile) {
        uploadTargetsBtn.addEventListener('click', () => targetsFile.click());
        targetsFile.addEventListener('change', handleTargetsUpload);
    }
    
    const uploadPathsBtn = document.getElementById('uploadPathsBtn');
    const pathsFile = document.getElementById('pathsFile');
    if (uploadPathsBtn && pathsFile) {
        uploadPathsBtn.addEventListener('click', () => pathsFile.click());
        pathsFile.addEventListener('change', handlePathsUpload);
    }
    
    // Lists management
    const uploadListBtn = document.getElementById('uploadListBtn');
    const listFile = document.getElementById('listFile');
    if (uploadListBtn && listFile) {
        uploadListBtn.addEventListener('click', () => listFile.click());
        listFile.addEventListener('change', showUploadModal);
    }
    
    // IP Generator form
    const ipGenForm = document.getElementById('ipGenForm');
    if (ipGenForm) {
        ipGenForm.addEventListener('submit', handleIPGeneration);
    }
    
    // Generator type change
    const generatorType = document.getElementById('generatorType');
    if (generatorType) {
        generatorType.addEventListener('change', handleGeneratorTypeChange);
    }
    
    // Concurrency slider
    const concurrencySlider = document.getElementById('concurrencySlider');
    if (concurrencySlider) {
        concurrencySlider.addEventListener('input', updateConcurrencyDisplay);
        updateConcurrencyDisplay(); // Initial update
    }
    
    // Settings forms
    const telegramForm = document.getElementById('telegramForm');
    if (telegramForm) {
        telegramForm.addEventListener('submit', handleTelegramSettings);
    }
    
    const testTelegramBtn = document.getElementById('testTelegramBtn');
    if (testTelegramBtn) {
        testTelegramBtn.addEventListener('click', handleTestTelegram);
    }
    
    // Export functionality
    const exportHitsBtn = document.getElementById('exportHitsBtn');
    if (exportHitsBtn) {
        exportHitsBtn.addEventListener('click', handleExportHits);
    }
    
    // List category filters
    const categoryBtns = document.querySelectorAll('.category-btn');
    categoryBtns.forEach(btn => {
        btn.addEventListener('click', (e) => {
            const category = e.currentTarget.dataset.category;
            filterListsByCategory(category);
        });
    });
    
    // Scan controls
    const pauseResumeBtn = document.getElementById('pauseResumeBtn');
    const stopScanBtn = document.getElementById('stopScanBtn');
    if (pauseResumeBtn) pauseResumeBtn.addEventListener('click', handlePauseResume);
    if (stopScanBtn) stopScanBtn.addEventListener('click', handleStopScan);
}

function initializeUIComponents() {
    // Update concurrency slider display
    updateConcurrencyDisplay();
    
    // Set initial generator config
    handleGeneratorTypeChange();
}

// Authentication functions
async function handleLogin(e) {
    e.preventDefault();
    const formData = new FormData(e.target);
    const credentials = {
        username: formData.get('username'),
        password: formData.get('password')
    };
    
    try {
        showLoading('loginForm');
        const response = await fetch(`${API_BASE}/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(credentials)
        });
        
        const data = await response.json();
        
        if (response.ok) {
            authToken = data.access_token;
            localStorage.setItem('authToken', authToken);
            currentUser = data.user;
            isFirstLogin = data.first_login || false;
            
            if (isFirstLogin) {
                showPasswordChange();
            } else {
                showMainApp();
            }
        } else {
            showError('loginError', data.detail || 'Login failed');
        }
    } catch (error) {
        console.error('Login error:', error);
        showError('loginError', 'Network error. Please try again.');
    } finally {
        hideLoading('loginForm');
    }
}

async function handlePasswordChange(e) {
    e.preventDefault();
    const formData = new FormData(e.target);
    const passwords = {
        old_password: formData.get('oldPassword'),
        new_password: formData.get('newPassword'),
        confirm_password: formData.get('confirmPassword')
    };
    
    if (passwords.new_password !== passwords.confirm_password) {
        showError('passwordError', 'New passwords do not match');
        return;
    }
    
    try {
        showLoading('passwordForm');
        const response = await fetch(`${API_BASE}/auth/change-password`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${authToken}`
            },
            body: JSON.stringify(passwords)
        });
        
        const data = await response.json();
        
        if (response.ok) {
            showMainApp();
        } else {
            showError('passwordError', data.detail || 'Password change failed');
        }
    } catch (error) {
        console.error('Password change error:', error);
        showError('passwordError', 'Network error. Please try again.');
    } finally {
        hideLoading('passwordForm');
    }
}

function handleLogout() {
    authToken = null;
    currentUser = null;
    localStorage.removeItem('authToken');
    
    // Close WebSocket connections
    if (websocketConnection) {
        websocketConnection.close();
        websocketConnection = null;
    }
    if (dashboardWebSocket) {
        dashboardWebSocket.close();
        dashboardWebSocket = null;
    }
    
    showLogin();
}

async function verifyTokenAndShowApp() {
    try {
        const response = await fetch(`${API_BASE}/auth/me`, {
            headers: { 'Authorization': `Bearer ${authToken}` }
        });
        
        if (response.ok) {
            const userData = await response.json();
            currentUser = userData;
            showMainApp();
        } else {
            authToken = null;
            localStorage.removeItem('authToken');
            showLogin();
        }
    } catch (error) {
        console.error('Token verification error:', error);
        showLogin();
    }
}

// UI State Management
function showLogin() {
    const loginModal = document.getElementById('loginModal');
    const passwordModal = document.getElementById('passwordModal');
    const mainApp = document.getElementById('mainApp');
    
    if (loginModal) loginModal.style.display = 'flex';
    if (passwordModal) passwordModal.style.display = 'none';
    if (mainApp) mainApp.style.display = 'none';
}

function showPasswordChange() {
    const loginModal = document.getElementById('loginModal');
    const passwordModal = document.getElementById('passwordModal');
    const mainApp = document.getElementById('mainApp');
    
    if (loginModal) loginModal.style.display = 'none';
    if (passwordModal) passwordModal.style.display = 'flex';
    if (mainApp) mainApp.style.display = 'none';
}

function showMainApp() {
    const loginModal = document.getElementById('loginModal');
    const passwordModal = document.getElementById('passwordModal');
    const mainApp = document.getElementById('mainApp');
    
    if (loginModal) loginModal.style.display = 'none';
    if (passwordModal) passwordModal.style.display = 'none';
    if (mainApp) mainApp.style.display = 'flex';
    
    // Update user info
    const userInfo = document.getElementById('userInfo');
    if (userInfo && currentUser) {
        userInfo.textContent = currentUser.username || 'Admin';
    }
    
    // Initialize dashboard
    switchTab('dashboard');
    
    // Connect WebSockets
    connectDashboardWebSocket();
    
    // Load initial data
    loadDashboardData();
}

function switchTab(tabName) {
    // Update navigation
    document.querySelectorAll('.nav-btn').forEach(btn => {
        btn.classList.remove('active');
        if (btn.dataset.tab === tabName) {
            btn.classList.add('active');
        }
    });
    
    // Update content
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.remove('active');
        content.style.display = 'none';
    });
    
    const activeTab = document.getElementById(tabName);
    if (activeTab) {
        activeTab.classList.add('active');
        activeTab.style.display = 'block';
    }
    
    // Load tab-specific data
    switch (tabName) {
        case 'dashboard':
            loadDashboardData();
            break;
        case 'scan':
            loadScanConfig();
            break;
        case 'lists':
            loadLists();
            break;
        case 'ipgen':
            loadGeneratedLists();
            break;
        case 'hits':
            loadHits();
            break;
        case 'settings':
            loadSettings();
            break;
    }
}

// Dashboard functions
async function loadDashboardData() {
    try {
        const response = await fetch(`${API_BASE}/stats/dashboard`, {
            headers: { 'Authorization': `Bearer ${authToken}` }
        });
        
        if (response.ok) {
            const stats = await response.json();
            updateDashboardStats(stats);
        }
    } catch (error) {
        console.error('Failed to load dashboard data:', error);
    }
}

function updateDashboardStats(stats) {
    // Update stat cards
    updateElement('totalActiveScans', stats.active_scans || 0);
    updateElement('totalHits', stats.total_hits || 0);
    updateElement('globalThroughput', `${stats.checks_per_sec || 0}/sec`);
    updateElement('successRate', `${stats.success_rate || 0}%`);
    
    // Update header stats
    updateElement('headerActiveScans', stats.active_scans || 0);
    updateElement('headerTotalHits', stats.total_hits || 0);
    
    // Update resource usage
    if (stats.resources) {
        updateResourceUsage(stats.resources);
    }
    
    // Update active scans
    if (stats.active_scans_list) {
        updateActiveScans(stats.active_scans_list);
    }
}

function updateResourceUsage(resources) {
    const cpuPercent = resources.cpu_percent || 0;
    const ramPercent = resources.ram_percent || 0;
    const networkMbps = resources.network_mbps || 0;
    
    updateElement('cpuUsage', `${cpuPercent.toFixed(1)}%`);
    updateElement('ramUsage', `${(resources.ram_mb || 0).toFixed(0)}MB`);
    updateElement('networkIO', `${networkMbps.toFixed(1)}MB/s`);
    
    // Update progress bars
    const cpuBar = document.getElementById('cpuBar');
    const ramBar = document.getElementById('ramBar');
    const networkBar = document.getElementById('networkBar');
    
    if (cpuBar) cpuBar.style.width = `${Math.min(cpuPercent, 100)}%`;
    if (ramBar) ramBar.style.width = `${Math.min(ramPercent, 100)}%`;
    if (networkBar) networkBar.style.width = `${Math.min(networkMbps / 100 * 100, 100)}%`;
}

function updateActiveScans(scans) {
    const container = document.getElementById('activeScansList');
    if (!container) return;
    
    if (scans.length === 0) {
        container.innerHTML = '<div class="no-scans">No active scans</div>';
        return;
    }
    
    container.innerHTML = scans.map(scan => `
        <div class="active-scan-card" data-scan-id="${scan.id}">
            <div class="scan-header">
                <h4>${scan.crack_id}</h4>
                <span class="scan-status ${scan.status}">${scan.status.toUpperCase()}</span>
            </div>
            <div class="scan-progress">
                <div class="progress-info">
                    <span>${scan.processed_urls}/${scan.total_urls} URLs</span>
                    <span>${scan.progress_percent.toFixed(1)}%</span>
                </div>
                <div class="progress-bar">
                    <div class="progress-fill" style="width: ${scan.progress_percent}%"></div>
                </div>
            </div>
            <div class="scan-stats">
                <div class="stat">
                    <span class="label">Hits:</span>
                    <span class="value">${scan.hits_count}</span>
                </div>
                <div class="stat">
                    <span class="label">Speed:</span>
                    <span class="value">${scan.checks_per_sec}/sec</span>
                </div>
                <div class="stat">
                    <span class="label">ETA:</span>
                    <span class="value">${formatETA(scan.eta_seconds)}</span>
                </div>
            </div>
            <div class="scan-actions">
                <button class="btn btn-sm" onclick="viewScanDetails('${scan.id}')">View</button>
                <button class="btn btn-sm btn-warning" onclick="pauseScan('${scan.id}')">Pause</button>
                <button class="btn btn-sm btn-danger" onclick="stopScan('${scan.id}')">Stop</button>
            </div>
        </div>
    `).join('');
}

// Scan functions
async function handleScanSubmit(e) {
    e.preventDefault();
    const formData = new FormData(e.target);
    
    // Collect form data
    const targets = formData.get('targets').split('\n').filter(t => t.trim());
    const modules = Array.from(formData.getAll('modules'));
    const services = Array.from(formData.getAll('services'));
    
    const scanRequest = {
        crack_name: formData.get('crackName'),
        targets: targets,
        wordlist: formData.get('wordlist'),
        modules: modules,
        services: services,
        concurrency: parseInt(formData.get('concurrency')),
        timeout: parseInt(formData.get('timeout'))
    };
    
    try {
        showLoading('scanForm');
        const response = await fetch(`${API_BASE}/scans`, {
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
            
            // Switch to live monitoring
            showLiveScanMonitor(result);
            
            // Connect to scan WebSocket
            connectScanWebSocket(result.scan_id);
            
            showSuccess('Scan launched successfully!');
        } else {
            const error = await response.json();
            showError('scanError', error.detail || 'Failed to launch scan');
        }
    } catch (error) {
        console.error('Scan launch error:', error);
        showError('scanError', 'Network error. Please try again.');
    } finally {
        hideLoading('scanForm');
    }
}

function showLiveScanMonitor(scanData) {
    document.getElementById('preScanConfig').style.display = 'none';
    document.getElementById('liveScanMonitor').style.display = 'block';
    
    // Update scan title
    const title = document.getElementById('activeScanTitle');
    if (title) {
        title.textContent = `🎯 Operation: ${scanData.crack_id}`;
    }
    
    // Initialize stats
    updateLiveScanStats({
        status: 'RUNNING',
        progress_percent: 0,
        processed_urls: 0,
        total_urls: scanData.total_urls || 0,
        hits_count: 0,
        checks_per_sec: 0,
        urls_per_sec: 0,
        eta_seconds: null,
        errors_count: 0,
        invalid_urls: 0
    });
}

function updateLiveScanStats(stats) {
    updateElement('scanStatus', stats.status);
    updateElement('scanProgress', `${stats.progress_percent.toFixed(1)}%`);
    updateElement('processedUrls', stats.processed_urls);
    updateElement('totalUrls', stats.total_urls);
    updateElement('hitsFound', stats.hits_count);
    updateElement('checksPerSec', stats.checks_per_sec);
    updateElement('urlsPerSec', stats.urls_per_sec);
    updateElement('scanEta', formatETA(stats.eta_seconds));
    updateElement('scanErrors', stats.errors_count);
    updateElement('invalidUrls', stats.invalid_urls);
    
    // Update progress bar
    const progressFill = document.getElementById('progressFill');
    if (progressFill) {
        progressFill.style.width = `${stats.progress_percent}%`;
    }
}

// File upload functions
async function handleTargetsUpload(e) {
    const file = e.target.files[0];
    if (!file) return;
    
    try {
        const text = await file.text();
        const targets = text.split('\n').filter(t => t.trim());
        document.getElementById('targets').value = targets.join('\n');
        showSuccess(`Loaded ${targets.length} targets`);
    } catch (error) {
        console.error('File upload error:', error);
        showError('uploadError', 'Failed to read file');
    }
}

async function handlePathsUpload(e) {
    const file = e.target.files[0];
    if (!file) return;
    
    const formData = new FormData();
    formData.append('file', file);
    
    try {
        const response = await fetch(`${API_BASE}/upload/wordlist`, {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${authToken}` },
            body: formData
        });
        
        if (response.ok) {
            const result = await response.json();
            // Add to wordlist dropdown
            const select = document.getElementById('wordlistSelect');
            const option = new Option(result.filename, result.filename);
            select.add(option);
            select.value = result.filename;
            showSuccess(`Uploaded wordlist with ${result.paths_count} paths`);
        } else {
            const error = await response.json();
            showError('uploadError', error.detail || 'Upload failed');
        }
    } catch (error) {
        console.error('Upload error:', error);
        showError('uploadError', 'Network error during upload');
    }
}

// Concurrency slider
function updateConcurrencyDisplay() {
    const slider = document.getElementById('concurrencySlider');
    const display = document.getElementById('concurrencyValue');
    const indicator = document.getElementById('performanceIndicator');
    
    if (!slider || !display) return;
    
    const value = parseInt(slider.value);
    display.textContent = value.toLocaleString();
    
    // Update performance indicator
    if (indicator) {
        if (value < 1000) {
            indicator.textContent = '⚡ Standard Performance';
            indicator.className = 'performance-indicator standard';
        } else if (value < 10000) {
            indicator.textContent = '🚀 High Performance';
            indicator.className = 'performance-indicator high';
        } else if (value < 30000) {
            indicator.textContent = '🔥 Extreme Performance';
            indicator.className = 'performance-indicator extreme';
        } else {
            indicator.textContent = '💥 Maximum Performance';
            indicator.className = 'performance-indicator maximum';
        }
    }
}

// IP Generator functions
function handleGeneratorTypeChange() {
    const generatorType = document.getElementById('generatorType');
    if (!generatorType) return;
    
    const type = generatorType.value;
    
    // Hide all config panels
    document.getElementById('randomConfig').style.display = 'none';
    
    // Show relevant config panel
    if (type === 'random') {
        document.getElementById('randomConfig').style.display = 'block';
    }
    // Add more config panels as needed
}

async function handleIPGeneration(e) {
    e.preventDefault();
    const formData = new FormData(e.target);
    
    const request = {
        name: formData.get('listName'),
        generator_type: formData.get('generatorType'),
        config: {
            ip_count: parseInt(formData.get('ipCount')),
            exclude_private: formData.has('excludePrivate')
        }
    };
    
    try {
        showLoading('ipGenForm');
        const response = await fetch(`${API_BASE}/ip-generator/generate`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${authToken}`
            },
            body: JSON.stringify(request)
        });
        
        if (response.ok) {
            const result = await response.json();
            showSuccess(`Generated ${result.ip_count} unique IPs`);
            loadGeneratedLists();
            e.target.reset();
        } else {
            const error = await response.json();
            showError('ipGenError', error.detail || 'Generation failed');
        }
    } catch (error) {
        console.error('IP generation error:', error);
        showError('ipGenError', 'Network error during generation');
    } finally {
        hideLoading('ipGenForm');
    }
}

// Lists management
async function loadLists() {
    try {
        const response = await fetch(`${API_BASE}/lists`, {
            headers: { 'Authorization': `Bearer ${authToken}` }
        });
        
        if (response.ok) {
            const lists = await response.json();
            displayLists(lists);
        }
    } catch (error) {
        console.error('Failed to load lists:', error);
    }
}

function displayLists(lists) {
    const container = document.getElementById('listsGrid');
    if (!container) return;
    
    if (lists.length === 0) {
        container.innerHTML = '<div class="no-lists">No lists uploaded yet</div>';
        return;
    }
    
    container.innerHTML = lists.map(list => `
        <div class="list-card" data-list-id="${list.id}">
            <div class="list-header">
                <h4>${list.name}</h4>
                <span class="list-type ${list.list_type}">${list.list_type}</span>
            </div>
            <div class="list-stats">
                <div class="stat">
                    <span class="label">Items:</span>
                    <span class="value">${list.size.toLocaleString()}</span>
                </div>
                <div class="stat">
                    <span class="label">Size:</span>
                    <span class="value">${formatFileSize(list.file_size)}</span>
                </div>
                <div class="stat">
                    <span class="label">Created:</span>
                    <span class="value">${formatDate(list.created_at)}</span>
                </div>
            </div>
            <div class="list-actions">
                <button class="btn btn-sm" onclick="useList('${list.id}')">Use</button>
                <button class="btn btn-sm btn-danger" onclick="deleteList('${list.id}')">Delete</button>
            </div>
        </div>
    `).join('');
}

function filterListsByCategory(category) {
    // Update active category button
    document.querySelectorAll('.category-btn').forEach(btn => {
        btn.classList.remove('active');
        if (btn.dataset.category === category) {
            btn.classList.add('active');
        }
    });
    
    // Filter lists
    const listCards = document.querySelectorAll('.list-card');
    listCards.forEach(card => {
        const listType = card.querySelector('.list-type').textContent;
        if (category === 'all' || listType === category) {
            card.style.display = 'block';
        } else {
            card.style.display = 'none';
        }
    });
}

// Settings functions
async function handleTelegramSettings(e) {
    e.preventDefault();
    const formData = new FormData(e.target);
    
    const settings = {
        bot_token: formData.get('botToken'),
        chat_id: formData.get('chatId')
    };
    
    try {
        const response = await fetch(`${API_BASE}/settings/telegram`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${authToken}`
            },
            body: JSON.stringify(settings)
        });
        
        if (response.ok) {
            showSuccess('Telegram settings saved successfully');
        } else {
            const error = await response.json();
            showError('telegramError', error.detail || 'Failed to save settings');
        }
    } catch (error) {
        console.error('Settings error:', error);
        showError('telegramError', 'Network error during save');
    }
}

async function handleTestTelegram() {
    try {
        const response = await fetch(`${API_BASE}/notifications/test/telegram`, {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${authToken}` }
        });
        
        if (response.ok) {
            showSuccess('Test notification sent successfully');
        } else {
            const error = await response.json();
            showError('telegramError', error.detail || 'Test failed');
        }
    } catch (error) {
        console.error('Test notification error:', error);
        showError('telegramError', 'Network error during test');
    }
}

// WebSocket functions
function connectDashboardWebSocket() {
    if (dashboardWebSocket) {
        dashboardWebSocket.close();
    }
    
    const wsUrl = `ws://localhost:8000/ws/dashboard?token=${authToken}`;
    dashboardWebSocket = new WebSocket(wsUrl);
    
    dashboardWebSocket.onopen = function() {
        console.log('Dashboard WebSocket connected');
    };
    
    dashboardWebSocket.onmessage = function(event) {
        const data = JSON.parse(event.data);
        handleDashboardWebSocketMessage(data);
    };
    
    dashboardWebSocket.onclose = function() {
        console.log('Dashboard WebSocket disconnected');
        // Attempt to reconnect after 5 seconds
        setTimeout(connectDashboardWebSocket, 5000);
    };
    
    dashboardWebSocket.onerror = function(error) {
        console.error('Dashboard WebSocket error:', error);
    };
}

function connectScanWebSocket(scanId) {
    if (websocketConnection) {
        websocketConnection.close();
    }
    
    const wsUrl = `ws://localhost:8000/ws/scans/${scanId}?token=${authToken}`;
    websocketConnection = new WebSocket(wsUrl);
    
    websocketConnection.onopen = function() {
        console.log('Scan WebSocket connected');
    };
    
    websocketConnection.onmessage = function(event) {
        const data = JSON.parse(event.data);
        handleScanWebSocketMessage(data);
    };
    
    websocketConnection.onclose = function() {
        console.log('Scan WebSocket disconnected');
    };
    
    websocketConnection.onerror = function(error) {
        console.error('Scan WebSocket error:', error);
    };
}

function handleDashboardWebSocketMessage(data) {
    switch (data.type) {
        case 'dashboard_stats':
            updateDashboardStats(data.data);
            break;
        case 'scan_status':
            updateActiveScanStatus(data.data);
            break;
    }
}

function handleScanWebSocketMessage(data) {
    switch (data.type) {
        case 'scan_progress':
            updateLiveScanStats(data.data);
            break;
        case 'scan_log':
            addLiveLog(data.data);
            break;
        case 'scan_hit':
            handleNewHit(data.data);
            break;
        case 'scan_status':
            updateScanStatus(data.data);
            break;
    }
}

function addLiveLog(logData) {
    const container = document.getElementById('liveLogs');
    if (!container) return;
    
    const logEntry = document.createElement('div');
    logEntry.className = `log-entry ${logData.level}`;
    logEntry.innerHTML = `
        <span class="log-time">${formatTime(logData.timestamp)}</span>
        <span class="log-level">[${logData.level.toUpperCase()}]</span>
        <span class="log-message">${logData.message}</span>
    `;
    
    container.appendChild(logEntry);
    container.scrollTop = container.scrollHeight;
    
    // Keep only last 100 log entries
    while (container.children.length > 100) {
        container.removeChild(container.firstChild);
    }
}

// Utility functions
function updateElement(id, value) {
    const element = document.getElementById(id);
    if (element) {
        element.textContent = value;
    }
}

function showError(elementId, message) {
    const element = document.getElementById(elementId);
    if (element) {
        element.textContent = message;
        element.classList.add('show');
        setTimeout(() => element.classList.remove('show'), 5000);
    }
}

function showSuccess(message) {
    // Create a temporary success message
    const successDiv = document.createElement('div');
    successDiv.className = 'success-message';
    successDiv.textContent = message;
    document.body.appendChild(successDiv);
    
    setTimeout(() => {
        document.body.removeChild(successDiv);
    }, 3000);
}

function showLoading(formId) {
    const form = document.getElementById(formId);
    if (form) {
        form.classList.add('loading');
        const submitBtn = form.querySelector('button[type="submit"]');
        if (submitBtn) {
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<span class="spinner"></span> Loading...';
        }
    }
}

function hideLoading(formId) {
    const form = document.getElementById(formId);
    if (form) {
        form.classList.remove('loading');
        const submitBtn = form.querySelector('button[type="submit"]');
        if (submitBtn) {
            submitBtn.disabled = false;
            // Restore original button text based on form
            const originalTexts = {
                'loginForm': 'Launch Panel',
                'passwordForm': 'Update Security',
                'scanForm': '🚀 Launch Intelligence Operation',
                'ipGenForm': '🎯 Generate IP List'
            };
            submitBtn.innerHTML = originalTexts[formId] || 'Submit';
        }
    }
}

function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
}

function formatTime(dateString) {
    const date = new Date(dateString);
    return date.toLocaleTimeString();
}

function formatETA(seconds) {
    if (!seconds || seconds <= 0) return 'Calculating...';
    
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);
    
    if (hours > 0) {
        return `${hours}h ${minutes}m ${secs}s`;
    } else if (minutes > 0) {
        return `${minutes}m ${secs}s`;
    } else {
        return `${secs}s`;
    }
}

// Export functions
async function handleExportHits() {
    // Implementation for hit export
    console.log('Export hits functionality to be implemented');
}

// Scan control functions
async function handlePauseResume() {
    // Implementation for pause/resume
    console.log('Pause/Resume functionality to be implemented');
}

async function handleStopScan() {
    // Implementation for stop scan
    console.log('Stop scan functionality to be implemented');
}

// Placeholder functions for missing implementations
async function loadScanConfig() {
    // Load available wordlists for dropdown
    try {
        const response = await fetch(`${API_BASE}/wordlists`, {
            headers: { 'Authorization': `Bearer ${authToken}` }
        });
        
        if (response.ok) {
            const wordlists = await response.json();
            const select = document.getElementById('wordlistSelect');
            if (select) {
                // Clear existing options except default
                const defaultOption = select.querySelector('option[value="paths.txt"]');
                select.innerHTML = '';
                if (defaultOption) select.appendChild(defaultOption);
                
                // Add wordlists
                wordlists.forEach(wordlist => {
                    const option = new Option(wordlist.name, wordlist.filename);
                    select.appendChild(option);
                });
            }
        }
    } catch (error) {
        console.error('Failed to load wordlists:', error);
    }
}

async function loadGeneratedLists() {
    // Load generated IP lists
    console.log('Loading generated lists...');
}

async function loadHits() {
    // Load hits data
    console.log('Loading hits...');
}

async function loadSettings() {
    // Load current settings
    console.log('Loading settings...');
}

// Additional utility functions
function showUploadModal() {
    console.log('Show upload modal');
}

function useList(listId) {
    console.log('Use list:', listId);
}

function deleteList(listId) {
    console.log('Delete list:', listId);
}

function viewScanDetails(scanId) {
    console.log('View scan details:', scanId);
}

function pauseScan(scanId) {
    console.log('Pause scan:', scanId);
}

function stopScan(scanId) {
    console.log('Stop scan:', scanId);
}

// ==========================================
// FRENCH PANEL FUNCTIONALITY
// ==========================================

// Statistiques du Scan functionality
let currentScanTelemetry = null;
let telemetryWebSocket = null;

function initStatistiquesTab() {
    // Initialize Statistiques tab event listeners
    document.getElementById('startScanBtn')?.addEventListener('click', handleStartScan);
    document.getElementById('pauseScanBtn')?.addEventListener('click', handlePauseScan);
    document.getElementById('stopScanBtn')?.addEventListener('click', handleStopScan);
    document.getElementById('refreshStatsBtn')?.addEventListener('click', refreshScanStats);
    
    // Initialize WebSocket for telemetry
    initTelemetryWebSocket();
}

async function handleStartScan() {
    try {
        // For demo, start a mock scan
        const response = await fetch(`${API_BASE}/scans`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${authToken}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                targets: ['example.com', 'test.com'],
                concurrency: 100,
                rate_limit: 50
            })
        });
        
        if (response.ok) {
            const result = await response.json();
            currentScanTelemetry = result.scan_id;
            updateScanStatus('running', 'SCAN EN COURS', 'Analyse en cours...');
            showScanControls('running');
        }
    } catch (error) {
        console.error('Failed to start scan:', error);
    }
}

async function handlePauseScan() {
    if (!currentScanTelemetry) return;
    
    try {
        const response = await fetch(`${API_BASE}/scans/${currentScanTelemetry}/pause`, {
            method: 'POST',
            headers: {'Authorization': `Bearer ${authToken}`}
        });
        
        if (response.ok) {
            updateScanStatus('paused', 'EN PAUSE', 'Scan mis en pause');
            showScanControls('paused');
        }
    } catch (error) {
        console.error('Failed to pause scan:', error);
    }
}

async function handleStopScan() {
    if (!currentScanTelemetry) return;
    
    try {
        const response = await fetch(`${API_BASE}/scans/${currentScanTelemetry}/stop`, {
            method: 'POST',
            headers: {'Authorization': `Bearer ${authToken}`}
        });
        
        if (response.ok) {
            updateScanStatus('stopped', 'ARRÊTÉ', 'Prêt pour le scan');
            showScanControls('stopped');
            currentScanTelemetry = null;
        }
    } catch (error) {
        console.error('Failed to stop scan:', error);
    }
}

function updateScanStatus(status, label, message) {
    const indicator = document.getElementById('scanStatusIndicator');
    const labelEl = document.getElementById('scanStatusLabel');
    const messageEl = document.getElementById('scanStatusMessage');
    
    if (indicator) {
        const statusIcons = {
            'stopped': '🔴',
            'running': '🟢',
            'paused': '🟡'
        };
        indicator.textContent = statusIcons[status] || '⚪';
    }
    
    if (labelEl) labelEl.textContent = label;
    if (messageEl) messageEl.textContent = message;
}

function showScanControls(status) {
    const startBtn = document.getElementById('startScanBtn');
    const pauseBtn = document.getElementById('pauseScanBtn');
    const stopBtn = document.getElementById('stopScanBtn');
    
    if (status === 'running') {
        if (startBtn) startBtn.style.display = 'none';
        if (pauseBtn) pauseBtn.style.display = 'inline-block';
        if (stopBtn) stopBtn.style.display = 'inline-block';
    } else {
        if (startBtn) startBtn.style.display = 'inline-block';
        if (pauseBtn) pauseBtn.style.display = 'none';
        if (stopBtn) stopBtn.style.display = 'none';
    }
}

function initTelemetryWebSocket() {
    if (!authToken) return;
    
    const wsUrl = `ws://${window.location.host}/ws/dashboard?token=${authToken}`;
    telemetryWebSocket = new WebSocket(wsUrl);
    
    telemetryWebSocket.onmessage = (event) => {
        const data = JSON.parse(event.data);
        
        if (data.type === 'scan.progress') {
            updateScanTelemetry(data.data);
        } else if (data.type === 'dashboard.stats') {
            updateDashboardTelemetry(data.data);
        }
    };
    
    telemetryWebSocket.onerror = (error) => {
        console.error('Telemetry WebSocket error:', error);
    };
}

function updateScanTelemetry(telemetryData) {
    // Update progress
    const progressPercent = document.getElementById('scanProgressPercent');
    const progressBar = document.getElementById('scanProgressBar');
    
    if (progressPercent && telemetryData.progress_percent !== undefined) {
        progressPercent.textContent = `${telemetryData.progress_percent.toFixed(1)}%`;
    }
    
    if (progressBar && telemetryData.progress_percent !== undefined) {
        progressBar.style.width = `${telemetryData.progress_percent}%`;
    }
    
    // Update stats
    updateElementText('urlsProcessed', telemetryData.processed_urls || 0);
    updateElementText('urlsPerSec', `${telemetryData.urls_per_sec || 0} URLs/sec`);
    updateElementText('httpsReqsPerSec', telemetryData.https_reqs_per_sec || 0);
    updateElementText('scanPrecision', `${(telemetryData.precision_percent || 0).toFixed(2)}%`);
    updateElementText('scanDuration', formatDuration(telemetryData.duration_seconds || 0));
    updateElementText('scanETA', formatDuration(telemetryData.eta_seconds || 0));
    
    // Update provider counts
    if (telemetryData.provider_counts) {
        updateElementText('awsCount', telemetryData.provider_counts.aws || 0);
        updateElementText('sendgridCount', telemetryData.provider_counts.sendgrid || 0);
        updateElementText('sparkpostCount', telemetryData.provider_counts.sparkpost || 0);
        updateElementText('twilioCount', telemetryData.provider_counts.twilio || 0);
        updateElementText('brevoCount', telemetryData.provider_counts.brevo || 0);
        updateElementText('mailgunCount', telemetryData.provider_counts.mailgun || 0);
        
        const totalHits = Object.values(telemetryData.provider_counts).reduce((sum, count) => sum + count, 0);
        updateElementText('totalHitsCount', totalHits);
    }
}

function updateDashboardTelemetry(dashboardData) {
    // Update system info
    updateElementText('systemCpuUsage', `${(dashboardData.cpu_percent || 0).toFixed(1)}%`);
    updateElementText('systemRamUsage', `${(dashboardData.ram_mb || 0).toFixed(0)} MB`);
    updateElementText('systemNetUsage', `${(dashboardData.net_mbps_out || 0).toFixed(1)} MB/s`);
}

async function refreshScanStats() {
    try {
        // Mock refresh for demo
        console.log('Refreshing scan stats...');
        
        // Update with demo data
        updateScanTelemetry({
            progress_percent: Math.random() * 100,
            processed_urls: Math.floor(Math.random() * 105369),
            urls_per_sec: Math.floor(Math.random() * 100),
            https_reqs_per_sec: Math.floor(Math.random() * 8000),
            precision_percent: Math.random() * 0.1,
            duration_seconds: Math.floor(Math.random() * 3600),
            eta_seconds: Math.floor(Math.random() * 1800),
            provider_counts: {
                aws: Math.floor(Math.random() * 10),
                sendgrid: Math.floor(Math.random() * 10),
                sparkpost: Math.floor(Math.random() * 5),
                twilio: Math.floor(Math.random() * 5),
                brevo: Math.floor(Math.random() * 5),
                mailgun: Math.floor(Math.random() * 5)
            }
        });
        
        updateDashboardTelemetry({
            cpu_percent: Math.random() * 100,
            ram_mb: Math.random() * 2048,
            net_mbps_out: Math.random() * 50
        });
        
    } catch (error) {
        console.error('Failed to refresh stats:', error);
    }
}

// Résultats functionality
function initResultatsTab() {
    document.getElementById('applyFiltersBtn')?.addEventListener('click', applyResultsFilters);
    document.getElementById('resetFiltersBtn')?.addEventListener('click', resetResultsFilters);
    document.getElementById('purgeResultsBtn')?.addEventListener('click', purgeAllResults);
    
    loadResults();
}

async function loadResults() {
    try {
        const serviceFilter = document.getElementById('serviceFilter')?.value || 'all';
        const validationFilter = document.getElementById('validationFilter')?.value || 'all';
        const sortFilter = document.getElementById('sortFilter')?.value || 'date_desc';
        
        const params = new URLSearchParams();
        if (serviceFilter !== 'all') params.append('service', serviceFilter);
        if (validationFilter !== 'all') params.append('validated', validationFilter);
        params.append('sort', sortFilter);
        
        const response = await fetch(`${API_BASE}/results?${params}`, {
            headers: {'Authorization': `Bearer ${authToken}`}
        });
        
        if (response.ok) {
            const data = await response.json();
            displayResults(data.hits);
            updateResultsCounters(data.counters);
        } else {
            // Show demo data if API not ready
            showDemoResults();
        }
    } catch (error) {
        console.error('Failed to load results:', error);
        showDemoResults();
    }
}

function displayResults(hits) {
    const tbody = document.getElementById('resultsTableBody');
    const noResults = document.getElementById('noResultsMessage');
    
    if (!tbody) return;
    
    if (hits.length === 0) {
        tbody.innerHTML = '';
        if (noResults) noResults.style.display = 'block';
        return;
    }
    
    if (noResults) noResults.style.display = 'none';
    
    tbody.innerHTML = hits.map(hit => `
        <tr>
            <td><span class="service-badge service-${hit.service}">${hit.service.toUpperCase()}</span></td>
            <td>${hit.host}</td>
            <td><span class="status-badge ${hit.validated ? 'status-valid' : 'status-invalid'}">${hit.validated ? 'Validé' : 'Invalide'}</span></td>
            <td>${new Date(hit.discovered_at).toLocaleString('fr-FR')}</td>
            <td>
                <button class="btn btn-sm btn-primary" onclick="viewResultDetail('${hit.id}')">👁️ Voir</button>
                <button class="btn btn-sm btn-danger" onclick="deleteResult('${hit.id}')">🗑️ Suppr</button>
            </td>
        </tr>
    `).join('');
}

function updateResultsCounters(counters) {
    updateElementText('validatedCount', counters.valides || 0);
    updateElementText('invalidatedCount', counters.invalides || 0);
    updateElementText('totalResultsCount', counters.total || 0);
}

function showDemoResults() {
    // Show demo data for presentation
    const demoHits = [
        {
            id: '1',
            service: 'sendgrid',
            host: 'api.example.com',
            validated: true,
            discovered_at: new Date()
        },
        {
            id: '2',
            service: 'aws',
            host: 'app.test.com',
            validated: false,
            discovered_at: new Date()
        }
    ];
    
    displayResults(demoHits);
    updateResultsCounters({ valides: 1, invalides: 1, total: 2 });
}

async function applyResultsFilters() {
    await loadResults();
}

function resetResultsFilters() {
    document.getElementById('serviceFilter').value = 'all';
    document.getElementById('validationFilter').value = 'all';
    document.getElementById('sortFilter').value = 'date_desc';
    loadResults();
}

async function purgeAllResults() {
    if (!confirm('Êtes-vous sûr de vouloir supprimer tous les résultats ?')) return;
    
    try {
        const response = await fetch(`${API_BASE}/results/purge`, {
            method: 'POST',
            headers: {'Authorization': `Bearer ${authToken}`}
        });
        
        if (response.ok) {
            loadResults(); // Refresh the list
            alert('Tous les résultats ont été supprimés.');
        }
    } catch (error) {
        console.error('Failed to purge results:', error);
    }
}

function viewResultDetail(hitId) {
    console.log('View result detail:', hitId);
    // Implementation for viewing detailed result
}

function deleteResult(hitId) {
    if (!confirm('Supprimer ce résultat ?')) return;
    console.log('Delete result:', hitId);
    // Implementation for deleting single result
}

// Domaines functionality
function initDomainesTab() {
    document.getElementById('uploadDomainsBtn')?.addEventListener('click', showDomainUpload);
    document.getElementById('refreshDomainsBtn')?.addEventListener('click', refreshDomainsList);
    document.getElementById('domainUploadForm')?.addEventListener('submit', handleDomainUpload);
    
    loadDomainsList();
}

function showDomainUpload() {
    document.querySelector('.upload-section').scrollIntoView({ behavior: 'smooth' });
}

async function loadDomainsList() {
    try {
        const response = await fetch(`${API_BASE}/lists`, {
            headers: {'Authorization': `Bearer ${authToken}`}
        });
        
        if (response.ok) {
            const lists = await response.json();
            displayDomainsList(lists);
        } else {
            showDemoDomainsList();
        }
    } catch (error) {
        console.error('Failed to load domains list:', error);
        showDemoDomainsList();
    }
}

function displayDomainsList(lists) {
    const container = document.getElementById('domainFilesList');
    if (!container) return;
    
    if (lists.length === 0) {
        container.innerHTML = '<div class="no-results">Aucun fichier de domaines disponible</div>';
        return;
    }
    
    container.innerHTML = lists.map(list => `
        <div class="file-item">
            <div class="file-header">
                <div class="file-name">📄 ${list.filename}</div>
                <div class="file-actions">
                    <button class="btn btn-sm btn-primary" onclick="useDomainsFile('${list.id}')">📋 Utiliser</button>
                    <button class="btn btn-sm btn-danger" onclick="deleteDomainsList('${list.id}')">🗑️</button>
                </div>
            </div>
            <div class="file-info">
                <span>${list.domain_count} domaines</span>
                <span>${formatFileSize(list.size)}</span>
                <span>${new Date(list.created_at).toLocaleDateString('fr-FR')}</span>
            </div>
        </div>
    `).join('');
}

function showDemoDomainsList() {
    const demoLists = [
        {
            id: '1',
            filename: 'common_domains.txt',
            domain_count: 1500,
            size: 25000,
            created_at: new Date()
        },
        {
            id: '2',
            filename: 'tech_companies.txt',
            domain_count: 850,
            size: 15200,
            created_at: new Date()
        }
    ];
    
    displayDomainsList(demoLists);
}

async function handleDomainUpload(event) {
    event.preventDefault();
    
    const fileInput = document.getElementById('domainFile');
    const file = fileInput.files[0];
    
    if (!file) return;
    
    const formData = new FormData();
    formData.append('file', file);
    
    try {
        const response = await fetch(`${API_BASE}/upload/targets`, {
            method: 'POST',
            headers: {'Authorization': `Bearer ${authToken}`},
            body: formData
        });
        
        if (response.ok) {
            alert('Fichier téléchargé avec succès !');
            loadDomainsList();
            fileInput.value = '';
        }
    } catch (error) {
        console.error('Failed to upload domains file:', error);
        alert('Erreur lors du téléchargement du fichier.');
    }
}

function useDomainsFile(listId) {
    console.log('Use domains file:', listId);
    // Implementation for using domains file in scan
}

async function deleteDomainsList(listId) {
    if (!confirm('Supprimer ce fichier de domaines ?')) return;
    
    try {
        const response = await fetch(`${API_BASE}/lists/${listId}`, {
            method: 'DELETE',
            headers: {'Authorization': `Bearer ${authToken}`}
        });
        
        if (response.ok) {
            loadDomainsList();
        }
    } catch (error) {
        console.error('Failed to delete domains list:', error);
    }
}

function refreshDomainsList() {
    loadDomainsList();
}

// Grabber functionality
function initGrabberTab() {
    document.getElementById('startGrabberBtn')?.addEventListener('click', startGrabber);
    document.getElementById('stopGrabberBtn')?.addEventListener('click', stopGrabber);
    
    loadGrabberStatus();
}

async function startGrabber() {
    const seedsText = document.getElementById('grabberSeeds')?.value || '';
    const maxDomains = parseInt(document.getElementById('maxDomains')?.value || '1000');
    
    const seeds = seedsText.split('\n').filter(s => s.trim()).map(s => s.trim());
    
    try {
        const response = await fetch(`${API_BASE}/grabber/start`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${authToken}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ seeds, max_domains: maxDomains })
        });
        
        if (response.ok) {
            showGrabberControls('running');
            startGrabberStatusPolling();
        }
    } catch (error) {
        console.error('Failed to start grabber:', error);
    }
}

async function stopGrabber() {
    try {
        const response = await fetch(`${API_BASE}/grabber/stop`, {
            method: 'POST',
            headers: {'Authorization': `Bearer ${authToken}`}
        });
        
        if (response.ok) {
            showGrabberControls('stopped');
            stopGrabberStatusPolling();
        }
    } catch (error) {
        console.error('Failed to stop grabber:', error);
    }
}

function showGrabberControls(status) {
    const startBtn = document.getElementById('startGrabberBtn');
    const stopBtn = document.getElementById('stopGrabberBtn');
    
    if (status === 'running') {
        if (startBtn) startBtn.style.display = 'none';
        if (stopBtn) stopBtn.style.display = 'inline-block';
    } else {
        if (startBtn) startBtn.style.display = 'inline-block';
        if (stopBtn) stopBtn.style.display = 'none';
    }
}

let grabberStatusInterval = null;

function startGrabberStatusPolling() {
    if (grabberStatusInterval) clearInterval(grabberStatusInterval);
    
    grabberStatusInterval = setInterval(async () => {
        await loadGrabberStatus();
    }, 2000);
}

function stopGrabberStatusPolling() {
    if (grabberStatusInterval) {
        clearInterval(grabberStatusInterval);
        grabberStatusInterval = null;
    }
}

async function loadGrabberStatus() {
    try {
        const response = await fetch(`${API_BASE}/grabber/status`, {
            headers: {'Authorization': `Bearer ${authToken}`}
        });
        
        if (response.ok) {
            const status = await response.json();
            updateGrabberStatus(status);
        } else {
            // Show demo status
            updateGrabberStatus({
                status: 'stopped',
                progress: 0,
                domains_generated: 0,
                eta_seconds: null
            });
        }
    } catch (error) {
        console.error('Failed to load grabber status:', error);
    }
}

function updateGrabberStatus(status) {
    updateElementText('grabberStatus', translateGrabberStatus(status.status));
    updateElementText('grabberProgress', `${status.progress}%`);
    updateElementText('domainsGenerated', status.domains_generated);
    updateElementText('grabberETA', status.eta_seconds ? formatDuration(status.eta_seconds) : '--:--:--');
    
    const progressBar = document.getElementById('grabberProgressBar');
    if (progressBar) {
        progressBar.style.width = `${status.progress}%`;
    }
    
    if (status.status === 'running') {
        showGrabberControls('running');
    } else {
        showGrabberControls('stopped');
    }
}

function translateGrabberStatus(status) {
    const translations = {
        'stopped': 'Arrêté',
        'running': 'En cours',
        'completed': 'Terminé',
        'error': 'Erreur'
    };
    return translations[status] || status;
}

// Configuration functionality (extended from settings)
function initConfigurationTab() {
    document.getElementById('telegramForm')?.addEventListener('submit', handleTelegramSettings);
    document.getElementById('testTelegramBtn')?.addEventListener('click', testTelegram);
    
    loadTelegramSettings();
}

async function handleTelegramSettings(event) {
    event.preventDefault();
    
    const formData = new FormData(event.target);
    const settings = {
        bot_token: formData.get('botToken'),
        chat_id: formData.get('chatId'),
        enabled: true
    };
    
    try {
        const response = await fetch(`${API_BASE}/settings/telegram`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${authToken}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(settings)
        });
        
        if (response.ok) {
            alert('Paramètres Telegram sauvegardés !');
        }
    } catch (error) {
        console.error('Failed to save Telegram settings:', error);
    }
}

async function testTelegram() {
    try {
        const response = await fetch(`${API_BASE}/notifications/test/telegram`, {
            method: 'POST',
            headers: {'Authorization': `Bearer ${authToken}`}
        });
        
        if (response.ok) {
            alert('Notification test envoyée !');
        } else {
            alert('Erreur lors de l\'envoi de la notification test.');
        }
    } catch (error) {
        console.error('Failed to test Telegram:', error);
        alert('Erreur lors du test Telegram.');
    }
}

async function loadTelegramSettings() {
    try {
        const response = await fetch(`${API_BASE}/settings/telegram`, {
            headers: {'Authorization': `Bearer ${authToken}`}
        });
        
        if (response.ok) {
            const settings = await response.json();
            
            if (settings.chat_id) {
                document.getElementById('telegramChatId').value = settings.chat_id;
            }
        }
    } catch (error) {
        console.error('Failed to load Telegram settings:', error);
    }
}

// Utility functions
function updateElementText(elementId, text) {
    const element = document.getElementById(elementId);
    if (element) {
        element.textContent = text;
    }
}

function formatDuration(seconds) {
    if (!seconds || seconds < 0) return '00:00:00';
    
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);
    
    return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
}

function formatFileSize(bytes) {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

// Initialize French panel functionality when switching tabs
const originalSwitchTab = switchTab;
switchTab = function(tabName) {
    originalSwitchTab(tabName);
    
    // Initialize tab-specific functionality
    switch (tabName) {
        case 'statistiques':
            setTimeout(initStatistiquesTab, 100);
            break;
        case 'resultats':
            setTimeout(initResultatsTab, 100);
            break;
        case 'domaines':
            setTimeout(initDomainesTab, 100);
            break;
        case 'grabber':
            setTimeout(initGrabberTab, 100);
            break;
        case 'configuration':
            setTimeout(initConfigurationTab, 100);
            break;
    }
};