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
    
    // Initialize lists cache and populate selectors
    loadLists();
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
    
    // Attach scan form gating
    attachScanFormGating();
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
// Remove old handleScanSubmit - using enhanced version below

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
    
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/dashboard?token=${authToken}`;
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
    
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/scans/${scanId}?token=${authToken}`;
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
        // Try to fallback to polling if WebSocket fails
        if (currentScanId === scanId) {
            setTimeout(() => startScanPolling(scanId), 2000);
        }
    };
    
    websocketConnection.onerror = function(error) {
        console.error('Scan WebSocket error:', error);
        // Fallback to polling
        if (currentScanId === scanId) {
            startScanPolling(scanId);
        }
    };
}

// Polling fallback for when WebSocket fails
let scanPollingInterval = null;

function startScanPolling(scanId) {
    if (scanPollingInterval) {
        clearInterval(scanPollingInterval);
    }
    
    console.log('Starting scan polling fallback for', scanId);
    
    scanPollingInterval = setInterval(async () => {
        try {
            // Get scan progress
            const progressResponse = await fetch(`${API_BASE}/scans/${scanId}/progress`, {
                headers: { 'Authorization': `Bearer ${authToken}` }
            });
            
            if (progressResponse.ok) {
                const progressData = await progressResponse.json();
                
                // Update UI with progress data
                updateLiveScanStats({
                    status: progressData.status,
                    progress_percent: progressData.progress_percent || 0,
                    processed_urls: progressData.processed_urls || 0,
                    total_urls: progressData.total_urls || 0,
                    hits_count: progressData.hits_count || 0,
                    checks_per_sec: progressData.checks_per_sec || 0,
                    urls_per_sec: progressData.urls_per_sec || 0,
                    eta_seconds: progressData.eta_seconds,
                    errors_count: 0,
                    invalid_urls: 0
                });
                
                // Stop polling if scan is complete
                if (progressData.status === 'completed' || 
                    progressData.status === 'failed' || 
                    progressData.status === 'stopped') {
                    clearInterval(scanPollingInterval);
                    scanPollingInterval = null;
                }
            }
        } catch (error) {
            console.error('Polling error:', error);
        }
    }, 2000); // Poll every 2 seconds
}

function stopScanPolling() {
    if (scanPollingInterval) {
        clearInterval(scanPollingInterval);
        scanPollingInterval = null;
    }
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
    // If elementId is provided, use the legacy inline error display
    if (elementId) {
        const element = document.getElementById(elementId);
        if (element) {
            element.textContent = message;
            element.classList.add('show');
            setTimeout(() => element.classList.remove('show'), 5000);
        }
    }
    
    // Also show a toast notification
    showToast(message, 'error');
}

function showSuccess(message) {
    showToast(message, 'success');
}

function showWarning(message) {
    showToast(message, 'warning');
}

function showInfo(message) {
    showToast(message, 'info');
}

function showToast(message, type = 'info', duration = 5000) {
    // Create toast container if it doesn't exist
    let container = document.getElementById('toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toast-container';
        container.className = 'toast-container';
        document.body.appendChild(container);
    }
    
    // Create toast element
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    
    // Get appropriate icon
    const icons = {
        success: '✅',
        error: '❌',
        warning: '⚠️',
        info: 'ℹ️'
    };
    
    toast.innerHTML = `
        <div class="toast-content">
            <span class="toast-icon">${icons[type] || icons.info}</span>
            <span class="toast-message">${message}</span>
        </div>
        <button class="toast-close" onclick="removeToast(this.parentElement)">×</button>
    `;
    
    // Add to container
    container.appendChild(toast);
    
    // Auto-remove after duration
    setTimeout(() => {
        removeToast(toast);
    }, duration);
}

function removeToast(toast) {
    if (toast && toast.parentElement) {
        toast.classList.add('removing');
        setTimeout(() => {
            if (toast.parentElement) {
                toast.parentElement.removeChild(toast);
            }
        }, 300);
    }
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

// ===== GLOBAL MESSAGING SYSTEM =====
function showUserMessage(message, type = 'info', title = null, dismissible = true, duration = null) {
    const container = document.getElementById('globalMessages');
    if (!container) return;
    
    const messageId = 'msg-' + Date.now();
    const alertDiv = document.createElement('div');
    alertDiv.id = messageId;
    alertDiv.className = `alert alert-${type}${dismissible ? ' alert-dismissible' : ''}`;
    
    const iconMap = {
        success: '✅',
        error: '❌', 
        warning: '⚠️',
        info: 'ℹ️'
    };
    
    alertDiv.innerHTML = `
        <div class="alert-icon">${iconMap[type] || 'ℹ️'}</div>
        <div class="alert-content">
            ${title ? `<div class="alert-title">${title}</div>` : ''}
            <div class="alert-message">${message}</div>
        </div>
        ${dismissible ? '<button class="alert-close" onclick="hideUserMessage(\'' + messageId + '\')">&times;</button>' : ''}
    `;
    
    container.appendChild(alertDiv);
    
    // Auto-dismiss if duration is set
    if (duration) {
        setTimeout(() => hideUserMessage(messageId), duration);
    } else if (type === 'success' || type === 'info') {
        // Auto-dismiss success and info messages after 5 seconds
        setTimeout(() => hideUserMessage(messageId), 5000);
    }
    
    return messageId;
}

function hideUserMessage(messageId) {
    const message = document.getElementById(messageId);
    if (message) {
        message.style.animation = 'slideOutTop 0.3s ease-in';
        setTimeout(() => message.remove(), 300);
    }
}

function showToast(message, type = 'info', duration = 3000) {
    return showUserMessage(message, type, null, true, duration);
}

// ===== SCAN READINESS VALIDATION =====
function validateScanReadiness() {
    const checklist = {
        hasTargets: false,
        hasValidConfig: false,
        hasWordlist: false
    };
    
    // Check if targets are provided (either from list or textarea)
    const targetsListId = document.getElementById('targetsListId')?.value;
    const targetsText = document.getElementById('targets')?.value?.trim();
    checklist.hasTargets = !!(targetsListId || targetsText);
    
    // Check wordlist selection
    const wordlist = document.getElementById('wordlistSelect')?.value;
    checklist.hasWordlist = !!wordlist;
    
    // Check basic config
    const operationName = document.getElementById('crackName')?.value?.trim();
    checklist.hasValidConfig = !!operationName;
    
    return checklist;
}

function updateScanStartGating() {
    const checklist = validateScanReadiness();
    const allReady = Object.values(checklist).every(ready => ready);
    
    // Update submit button state
    const submitBtn = document.querySelector('#scanForm button[type="submit"]');
    if (submitBtn) {
        submitBtn.disabled = !allReady;
        if (!allReady) {
            submitBtn.classList.add('btn--loading');
        } else {
            submitBtn.classList.remove('btn--loading');
        }
    }
    
    // Update readiness indicator
    const indicator = document.getElementById('readinessIndicator');
    const text = document.getElementById('readinessText');
    
    if (indicator && text) {
        if (allReady) {
            indicator.className = 'readiness-indicator ready';
            indicator.innerHTML = '<span>✅</span><span>Ready to launch</span>';
        } else {
            indicator.className = 'readiness-indicator pending';
            const missing = [];
            if (!checklist.hasTargets) missing.push('targets');
            if (!checklist.hasWordlist) missing.push('wordlist');
            if (!checklist.hasValidConfig) missing.push('operation name');
            indicator.innerHTML = `<span>⚠️</span><span>Missing: ${missing.join(', ')}</span>`;
        }
    }
}

function attachScanFormGating() {
    // Attach event listeners to form fields that affect readiness
    const fields = [
        'targetsListId',
        'targets', 
        'wordlistSelect',
        'crackName'
    ];
    
    fields.forEach(fieldId => {
        const field = document.getElementById(fieldId);
        if (field) {
            field.addEventListener('input', updateScanStartGating);
            field.addEventListener('change', updateScanStartGating);
        }
    });
    
    // Initial validation
    updateScanStartGating();
}

// ===== LISTS MANAGEMENT =====
let cachedLists = [];

async function loadLists() {
    try {
        const response = await fetch(`${API_BASE}/lists`, {
            headers: { 'Authorization': `Bearer ${authToken}` }
        });
        
        if (response.ok) {
            const lists = await response.json();
            cachedLists = lists;
            
            // Store in localStorage for offline access
            localStorage.setItem('cachedLists', JSON.stringify(lists));
            
            displayLists(lists);
            populateScanListSelector(lists);
        } else if (response.status === 401) {
            // Authentication error - handled elsewhere
            console.warn('Authentication required for lists');
        } else {
            throw new Error(`Failed to load lists: ${response.status}`);
        }
    } catch (error) {
        console.error('Failed to load lists:', error);
        
        // Try to load from cache
        const cached = localStorage.getItem('cachedLists');
        if (cached) {
            try {
                const lists = JSON.parse(cached);
                cachedLists = lists;
                displayLists(lists);
                populateScanListSelector(lists);
                showUserMessage('Loaded lists from cache (offline mode)', 'warning');
            } catch (e) {
                console.error('Failed to parse cached lists:', e);
            }
        } else {
            showUserMessage('Failed to load target lists', 'error');
        }
    }
}

function populateScanListSelector(lists) {
    const selector = document.getElementById('targetsListId');
    if (!selector) return;
    
    // Clear existing options except default
    selector.innerHTML = '<option value="">Select a saved list (optional)</option>';
    
    // Add target lists only
    const targetLists = lists.filter(list => list.list_type === 'targets' || list.list_type === 'mixed');
    targetLists.forEach(list => {
        const option = document.createElement('option');
        option.value = list.id;
        option.textContent = `${list.name} (${list.size.toLocaleString()} items)`;
        selector.appendChild(option);
    });
    
    // Add event listener for list selection
    selector.removeEventListener('change', handleListSelection); // Remove existing listener
    selector.addEventListener('change', handleListSelection);
}

function handleListSelection(e) {
    const listId = e.target.value;
    const targetsTextarea = document.getElementById('targets');
    
    if (listId && targetsTextarea) {
        // When a list is selected, clear the textarea and update gating
        targetsTextarea.value = '';
        targetsTextarea.placeholder = 'List selected above - targets will be loaded from saved list';
        targetsTextarea.disabled = true;
    } else if (targetsTextarea) {
        // When no list is selected, re-enable textarea
        targetsTextarea.placeholder = 'example.com\nhttps://target.com\napp.example.com';
        targetsTextarea.disabled = false;
    }
    
    updateScanStartGating();
}

function displayLists(lists) {
    const container = document.getElementById('listsGrid');
    if (!container) return;
    
    if (lists.length === 0) {
        container.innerHTML = '<div class="no-lists">No lists uploaded yet</div>';
        return;
    }
    
    container.innerHTML = lists.map(list => `
        <div class="list-card card-hover transition-fast" data-list-id="${list.id}">
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
            <div class="list-actions space-2">
                <button class="btn btn-sm btn-primary" onclick="useList('${list.id}')">Use</button>
                <button class="btn btn-sm btn-danger" onclick="deleteList('${list.id}')">Delete</button>
            </div>
        </div>
    `).join('');
}

function useList(listId) {
    // Switch to scan tab and select this list
    switchTab('scan');
    
    // Set the list selector
    const selector = document.getElementById('targetsListId');
    if (selector) {
        selector.value = listId;
        handleListSelection({ target: selector });
    }
    
    const list = cachedLists.find(l => l.id === listId);
    if (list) {
        showToast(`Selected list: ${list.name}`, 'success');
    }
}

async function deleteList(listId) {
    const list = cachedLists.find(l => l.id === listId);
    if (!list) return;
    
    if (!confirm(`Are you sure you want to delete "${list.name}"? This action cannot be undone.`)) {
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/lists/${listId}`, {
            method: 'DELETE',
            headers: { 'Authorization': `Bearer ${authToken}` }
        });
        
        if (response.ok) {
            showToast('List deleted successfully', 'success');
            // Reload lists to refresh the display
            loadLists();
        } else {
            const error = await response.json();
            showUserMessage(error.detail || 'Failed to delete list', 'error');
        }
    } catch (error) {
        console.error('Failed to delete list:', error);
        showUserMessage('Network error while deleting list', 'error');
    }
}

// ===== ENHANCED SCAN HANDLING =====
async function handleScanSubmit(e) {
    e.preventDefault();
    
    // Validate readiness
    const checklist = validateScanReadiness();
    const allReady = Object.values(checklist).every(ready => ready);
    
    if (!allReady) {
        const missing = [];
        if (!checklist.hasTargets) missing.push('targets or saved list');
        if (!checklist.hasWordlist) missing.push('wordlist');
        if (!checklist.hasValidConfig) missing.push('operation name');
        
        showUserMessage(`Cannot start scan: Missing ${missing.join(', ')}`, 'error', 'Scan Validation Failed');
        return;
    }
    
    const formData = new FormData(e.target);
    
    // Determine targets source
    let targets = [];
    const selectedListId = formData.get('targetsListId');
    
    if (selectedListId) {
        // Use selected list - targets will be loaded server-side
        targets = []; // Empty array indicates list should be used
    } else {
        // Use pasted targets
        const targetText = formData.get('targets');
        targets = targetText.split('\n').filter(t => t.trim()).map(t => t.trim());
    }
    
    // Get selected modules and services
    const modules = Array.from(document.querySelectorAll('input[name="modules"]:checked')).map(cb => cb.value);
    const services = Array.from(document.querySelectorAll('input[name="services"]:checked')).map(cb => cb.value);
    
    const scanRequest = {
        name: formData.get('crackName'),
        targets: targets,
        target_list_id: selectedListId || null,
        wordlist: formData.get('wordlist'),
        concurrency: parseInt(formData.get('concurrency')),
        timeout: parseInt(formData.get('timeout')),
        modules: modules,
        services: services
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
            
            showUserMessage(`Scan started successfully: ${result.scan_id}`, 'success', 'Operation Launched');
            
            // Transition to live monitoring
            showLiveScanMonitor(result.scan_id, scanRequest.name);
            updateStepperState('live');
            
            // Reset form
            e.target.reset();
            updateScanStartGating();
            
        } else {
            const error = await response.json();
            showUserMessage(error.detail || 'Failed to start scan', 'error', 'Scan Start Failed');
        }
    } catch (error) {
        console.error('Scan submission error:', error);
        showUserMessage('Network error while starting scan', 'error', 'Connection Error');
    } finally {
        hideLoading('scanForm');
    }
}

function updateStepperState(activeStep) {
    const steps = document.querySelectorAll('.stepper-step');
    const stepOrder = ['targets', 'config', 'review', 'live'];
    const activeIndex = stepOrder.indexOf(activeStep);
    
    steps.forEach((step, index) => {
        const stepData = step.dataset.step;
        const stepIndex = stepOrder.indexOf(stepData);
        
        step.classList.remove('active', 'completed');
        
        if (stepIndex < activeIndex) {
            step.classList.add('completed');
        } else if (stepIndex === activeIndex) {
            step.classList.add('active');
        }
    });
}

function showLiveScanMonitor(scanId, scanName) {
    // Hide pre-scan config
    const preScanConfig = document.getElementById('preScanConfig');
    if (preScanConfig) {
        preScanConfig.style.display = 'none';
    }
    
    // Show live monitor
    const liveMonitor = document.getElementById('liveScanMonitor');
    if (liveMonitor) {
        liveMonitor.style.display = 'block';
        
        // Update title
        const title = document.getElementById('activeScanTitle');
        if (title) {
            title.textContent = `🎯 Operation: ${scanName}`;
        }
    }
}

// ===== PAUSE/RESUME FUNCTIONALITY =====
async function handlePauseResume() {
    if (!currentScanId) {
        showUserMessage('No active scan to control', 'warning');
        return;
    }
    
    const button = document.getElementById('pauseResumeBtn');
    if (!button) return;
    
    const isPaused = button.textContent.includes('Resume');
    const action = isPaused ? 'resume' : 'pause';
    
    try {
        const response = await fetch(`${API_BASE}/scans/${currentScanId}/control`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${authToken}`
            },
            body: JSON.stringify({ action })
        });
        
        if (response.ok) {
            const result = await response.json();
            
            // Update button text and state
            if (action === 'pause') {
                button.innerHTML = '▶️ Resume';
                button.className = 'btn btn-primary';
                showToast('Scan paused successfully', 'info');
            } else {
                button.innerHTML = '⏸️ Pause'; 
                button.className = 'btn btn-warning';
                showToast('Scan resumed successfully', 'success');
            }
            
            // Update scan status display
            const statusElement = document.getElementById('scanStatus');
            if (statusElement) {
                statusElement.textContent = result.status?.toUpperCase() || (action === 'pause' ? 'PAUSED' : 'RUNNING');
                statusElement.className = `stat-value ${result.status || (action === 'pause' ? 'paused' : 'running')}`;
            }
            
        } else {
            const error = await response.json();
            showUserMessage(error.detail || `Failed to ${action} scan`, 'error');
        }
    } catch (error) {
        console.error(`${action} scan error:`, error);
        showUserMessage('Network error while controlling scan', 'error');
    }
}
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
    // Load generated IP lists for the IP Generator tab
    try {
        const response = await fetch(`${API_BASE}/generator/lists`, {
            headers: { 'Authorization': `Bearer ${authToken}` }
        });
        
        if (response.ok) {
            const lists = await response.json();
            displayGeneratedLists(lists);
        }
    } catch (error) {
        console.error('Failed to load generated lists:', error);
    }
}

async function loadHits() {
    // Load scan results/hits for current user
    try {
        const response = await fetch(`${API_BASE}/results`, {
            headers: { 'Authorization': `Bearer ${authToken}` }
        });
        
        if (response.ok) {
            const hits = await response.json();
            displayHits(hits);
        }
    } catch (error) {
        console.error('Failed to load hits:', error);
        showUserMessage('Failed to load scan results', 'error');
    }
}

async function loadSettings() {
    // Load current user settings and system configuration
    try {
        const response = await fetch(`${API_BASE}/settings`, {
            headers: { 'Authorization': `Bearer ${authToken}` }
        });
        
        if (response.ok) {
            const settings = await response.json();
            displaySettings(settings);
        }
    } catch (error) {
        console.error('Failed to load settings:', error);
        showUserMessage('Failed to load settings', 'error');
    }
}

// Additional utility functions
function showUploadModal() {
    // Handle file upload for lists
    const fileInput = document.getElementById('listFile');
    if (!fileInput || !fileInput.files[0]) return;
    
    const file = fileInput.files[0];
    const formData = new FormData();
    formData.append('file', file);
    formData.append('list_type', 'targets'); // Default type
    
    uploadList(formData, file.name);
}

async function uploadList(formData, fileName) {
    try {
        const uploadMsgId = showUserMessage('Uploading list...', 'info', null, false);
        
        const response = await fetch(`${API_BASE}/lists`, {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${authToken}` },
            body: formData
        });
        
        hideUserMessage(uploadMsgId);
        
        if (response.ok) {
            const result = await response.json();
            showUserMessage(`List "${fileName}" uploaded successfully (${result.size} items)`, 'success');
            
            // Refresh lists display
            loadLists();
        } else {
            const error = await response.json();
            showUserMessage(error.detail || 'Failed to upload list', 'error');
        }
    } catch (error) {
        console.error('Upload error:', error);
        showUserMessage('Network error during upload', 'error');
    }
}

function useList(listId) {
    console.log('Use list:', listId);
}

function deleteList(listId) {
    console.log('Delete list:', listId);
}

function viewScanDetails(scanId) {
    console.log('View scan details:', scanId);
    // Switch to scan tab and connect to scan WebSocket
    switchTab('scan');
    currentScanId = scanId;
    connectScanWebSocket(scanId);
    
    // Show scan details
    showLiveScanMonitor({scan_id: scanId, crack_id: scanId});
}

async function pauseScan(scanId) {
    try {
        const response = await fetch(`${API_BASE}/scans/${scanId}/control`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${authToken}`
            },
            body: JSON.stringify({action: 'pause'})
        });
        
        if (response.ok) {
            showSuccess('Scan paused successfully');
        } else {
            const error = await response.json();
            showError('scanError', error.detail || 'Failed to pause scan');
        }
    } catch (error) {
        console.error('Pause scan error:', error);
        showError('scanError', 'Network error. Please try again.');
    }
}

async function stopScan(scanId) {
    if (!confirm('Are you sure you want to stop this scan?')) {
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/scans/${scanId}/control`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${authToken}`
            },
            body: JSON.stringify({action: 'stop'})
        });
        
        if (response.ok) {
            showSuccess('Scan stopped successfully');
        } else {
            const error = await response.json();
            showError('scanError', error.detail || 'Failed to stop scan');
        }
    } catch (error) {
        console.error('Stop scan error:', error);
        showError('scanError', 'Network error. Please try again.');
    }
}

async function handleStopScan() {
    if (currentScanId) {
        await stopScan(currentScanId);
    }
}

// ===== FRENCH UI FUNCTIONS =====

// Statistiques page functions
async function loadStatistiques() {
    try {
        console.log('Loading statistiques...');
        
        // Get provider stats
        const response = await fetch(`${API_BASE}/results/providers`, {
            headers: { 'Authorization': `Bearer ${authToken}` }
        });
        
        if (response.ok) {
            const providerStats = await response.json();
            updateProviderTiles(providerStats);
        }
        
        // Get result counters
        const countersResponse = await fetch(`${API_BASE}/results/counters`, {
            headers: { 'Authorization': `Bearer ${authToken}` }
        });
        
        if (countersResponse.ok) {
            const counters = await countersResponse.json();
            updateResultCounters(counters);
        }
        
    } catch (error) {
        console.error('Failed to load statistiques:', error);
    }
}

function updateProviderTiles(stats) {
    document.getElementById('awsCount').textContent = stats.aws || 0;
    document.getElementById('sendgridCount').textContent = stats.sendgrid || 0;
    document.getElementById('sparkpostCount').textContent = stats.sparkpost || 0;
    document.getElementById('twilioCount').textContent = stats.twilio || 0;
    document.getElementById('brevoCount').textContent = stats.brevo || 0;
    document.getElementById('mailgunCount').textContent = stats.mailgun || 0;
}

function updateStatisticsMetrics(data) {
    // Update progress
    const progressPercent = data.progress_percent || 0;
    document.getElementById('progressPercentage').textContent = `${progressPercent.toFixed(1)}%`;
    document.getElementById('progressBarFill').style.width = `${progressPercent}%`;
    
    // Update URL counts
    document.getElementById('processedUrlsCount').textContent = data.processed_urls || 0;
    document.getElementById('totalUrlsCount').textContent = data.total_urls || 0;
    
    // Update performance metrics
    document.getElementById('urlsPerSecSpeed').textContent = `${data.urls_per_sec || 0} URLs/sec`;
    document.getElementById('httpsReqsPerSec').textContent = data.https_reqs_per_sec || 0;
    document.getElementById('precisionPercent').textContent = `${(data.precision_percent || 0).toFixed(2)}%`;
    document.getElementById('scanDuration').textContent = formatDuration(data.duration_seconds || 0);
    document.getElementById('scanETA').textContent = data.eta_seconds ? formatDuration(data.eta_seconds) : 'En cours...';
    document.getElementById('totalHitsCount').textContent = data.hits_count || 0;
}

// Résultats page functions
async function loadResultats() {
    try {
        console.log('Loading résultats...');
        
        const service = document.getElementById('serviceFilterRes')?.value || '';
        const validated = document.getElementById('validationFilter')?.value || '';
        const sort = document.getElementById('sortFilter')?.value || 'date_desc';
        
        const params = new URLSearchParams();
        if (service) params.append('service', service);
        if (validated !== '') params.append('validated', validated);
        params.append('sort', sort);
        params.append('limit', '50');
        
        const response = await fetch(`${API_BASE}/results?${params}`, {
            headers: { 'Authorization': `Bearer ${authToken}` }
        });
        
        if (response.ok) {
            const data = await response.json();
            updateResultsList(data.hits);
            updateResultCounters(data.counters);
        }
        
    } catch (error) {
        console.error('Failed to load résultats:', error);
    }
}

function updateResultsList(hits) {
    const container = document.getElementById('resultsList');
    if (!container) return;
    
    if (hits.length === 0) {
        container.innerHTML = '<div class="no-results">Aucun résultat trouvé</div>';
        return;
    }
    
    container.innerHTML = hits.map(hit => `
        <div class="result-item" onclick="showResultDetails('${hit.id}')">
            <div class="result-header">
                <div class="result-service ${hit.service}">${hit.service.toUpperCase()}</div>
                <div class="result-status ${hit.validated ? 'valid' : 'invalid'}">
                    ${hit.validated ? 'Validé' : 'Invalide'}
                </div>
            </div>
            <div class="result-url">${hit.url}</div>
            <div class="result-time">${formatDate(hit.discovered_at)}</div>
        </div>
    `).join('');
}

function updateResultCounters(counters) {
    if (document.getElementById('totalCounter')) {
        document.getElementById('totalCounter').textContent = counters.total || 0;
    }
    if (document.getElementById('validCounter')) {
        document.getElementById('validCounter').textContent = counters.valides || 0;
    }
    if (document.getElementById('invalidCounter')) {
        document.getElementById('invalidCounter').textContent = counters.invalides || 0;
    }
}

async function showResultDetails(hitId) {
    try {
        const response = await fetch(`${API_BASE}/results/${hitId}`, {
            headers: { 'Authorization': `Bearer ${authToken}` }
        });
        
        if (response.ok) {
            const hit = await response.json();
            
            const drawer = document.getElementById('detailsDrawer');
            const content = document.getElementById('drawerContent');
            
            content.innerHTML = `
                <div class="detail-section">
                    <h4>Informations Générales</h4>
                    <div class="detail-row">
                        <span class="detail-label">URL:</span>
                        <span class="detail-value">${hit.url}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Service:</span>
                        <span class="detail-value service-chip ${hit.service}">${hit.service.toUpperCase()}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Statut:</span>
                        <span class="detail-value status-chip ${hit.validated ? 'valid' : 'invalid'}">
                            ${hit.validated ? 'Validé' : 'Invalide'}
                        </span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Découvert:</span>
                        <span class="detail-value">${formatDateTime(hit.discovered_at)}</span>
                    </div>
                </div>
                
                ${hit.provider_payload ? `
                <div class="detail-section">
                    <h4>Informations Fournisseur</h4>
                    <div class="detail-row">
                        <span class="detail-label">Clé API (masquée):</span>
                        <span class="detail-value masked">${hit.provider_payload.api_key_masked}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Statut:</span>
                        <span class="detail-value">${hit.provider_payload.status}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Raison:</span>
                        <span class="detail-value">${hit.provider_payload.reason || 'N/A'}</span>
                    </div>
                    ${hit.provider_payload.quota ? `
                    <div class="detail-row">
                        <span class="detail-label">Quota:</span>
                        <span class="detail-value">${JSON.stringify(hit.provider_payload.quota)}</span>
                    </div>
                    ` : ''}
                </div>
                ` : ''}
            `;
            
            drawer.style.display = 'block';
        }
        
    } catch (error) {
        console.error('Failed to load result details:', error);
    }
}

async function purgeAllResults() {
    if (!confirm('Êtes-vous sûr de vouloir supprimer tous les résultats ? Cette action est irréversible.')) {
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/results/purge`, {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${authToken}` }
        });
        
        if (response.ok) {
            showUserMessage('Tous les résultats ont été supprimés avec succès.', 'success');
            loadResultats(); // Reload the results
        } else {
            showUserMessage('Erreur lors de la suppression des résultats.', 'error');
        }
        
    } catch (error) {
        console.error('Failed to purge results:', error);
        showUserMessage('Erreur lors de la suppression des résultats.', 'error');
    }
}

// Domaines page functions
async function loadDomaines() {
    try {
        console.log('Loading domaines...');
        
        const response = await fetch(`${API_BASE}/lists`, {
            headers: { 'Authorization': `Bearer ${authToken}` }
        });
        
        if (response.ok) {
            const lists = await response.json();
            updateDomainsList(lists);
        }
        
        // Load grabber status
        const grabberResponse = await fetch(`${API_BASE}/grabber/status`, {
            headers: { 'Authorization': `Bearer ${authToken}` }
        });
        
        if (grabberResponse.ok) {
            const status = await grabberResponse.json();
            updateGrabberStatus(status);
        }
        
    } catch (error) {
        console.error('Failed to load domaines:', error);
    }
}

function updateDomainsList(lists) {
    const container = document.getElementById('domainsList');
    if (!container) return;
    
    if (lists.length === 0) {
        container.innerHTML = '<div class="no-files">Aucun fichier de domaine trouvé</div>';
        return;
    }
    
    container.innerHTML = lists.map(list => `
        <div class="domain-file">
            <div class="file-info">
                <div class="file-name">📄 ${list.filename}</div>
                <div class="file-details">
                    ${list.size} entrées • ${formatFileSize(list.file_size)} • ${formatDate(list.created_at)}
                </div>
            </div>
            <div class="file-actions">
                <button class="btn btn-sm btn-danger" onclick="deleteDomainList('${list.id}')">🗑️</button>
            </div>
        </div>
    `).join('');
}

function updateGrabberStatus(status) {
    document.getElementById('grabberState').textContent = status.active ? 'En cours' : 'Arrêté';
    document.getElementById('processedDomains').textContent = status.processed_domains || 0;
    document.getElementById('generatedCandidates').textContent = status.generated_candidates || 0;
    
    const startBtn = document.getElementById('startGrabberBtn');
    const stopBtn = document.getElementById('stopGrabberBtn');
    
    if (status.active) {
        startBtn.disabled = true;
        stopBtn.disabled = false;
    } else {
        startBtn.disabled = false;
        stopBtn.disabled = true;
    }
}

async function startGrabber() {
    try {
        const response = await fetch(`${API_BASE}/grabber/start`, {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${authToken}` }
        });
        
        if (response.ok) {
            const result = await response.json();
            showUserMessage(result.message, 'success');
            loadDomaines(); // Refresh status
        } else {
            const error = await response.json();
            showUserMessage(`Erreur: ${error.detail}`, 'error');
        }
        
    } catch (error) {
        console.error('Failed to start grabber:', error);
        showUserMessage('Erreur lors du démarrage du grabber.', 'error');
    }
}

async function stopGrabber() {
    try {
        const response = await fetch(`${API_BASE}/grabber/stop`, {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${authToken}` }
        });
        
        if (response.ok) {
            const result = await response.json();
            showUserMessage(result.message, 'success');
            loadDomaines(); // Refresh status
        } else {
            const error = await response.json();
            showUserMessage(`Erreur: ${error.detail}`, 'error');
        }
        
    } catch (error) {
        console.error('Failed to stop grabber:', error);
        showUserMessage('Erreur lors de l\'arrêt du grabber.', 'error');
    }
}

async function deleteDomainList(listId) {
    if (!confirm('Êtes-vous sûr de vouloir supprimer ce fichier ?')) {
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/lists/${listId}`, {
            method: 'DELETE',
            headers: { 'Authorization': `Bearer ${authToken}` }
        });
        
        if (response.ok) {
            loadDomaines(); // Refresh list
        } else {
            showUserMessage('Erreur lors de la suppression du fichier.', 'error');
        }
        
    } catch (error) {
        console.error('Failed to delete domain list:', error);
        showUserMessage('Erreur lors de la suppression du fichier.', 'error');
    }
}

// Cracker control functions
function updateCrackerStatus(isRunning) {
    const statusEl = document.getElementById('crackerStatus');
    const stateEl = document.getElementById('crackerState');
    const messageEl = document.getElementById('crackerMessage');
    const startBtn = document.getElementById('startCrackerBtn');
    const stopBtn = document.getElementById('stopCrackerBtn');
    
    if (isRunning) {
        statusEl.textContent = 'EN COURS';
        statusEl.className = 'status-value running';
        stateEl.textContent = 'Actif';
        messageEl.textContent = 'Scan en cours d\'exécution';
        startBtn.disabled = true;
        stopBtn.disabled = false;
    } else {
        statusEl.textContent = 'ARRÊTÉ';
        statusEl.className = 'status-value stopped';
        stateEl.textContent = 'Prêt';
        messageEl.textContent = 'Prêt pour le scan';
        startBtn.disabled = false;
        stopBtn.disabled = true;
    }
}

// Utility functions
function formatDuration(seconds) {
    if (seconds < 60) return `${Math.round(seconds)}s`;
    if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
    return `${Math.round(seconds / 3600)}h`;
}

function formatDate(dateString) {
    return new Date(dateString).toLocaleDateString('fr-FR');
}

function formatDateTime(dateString) {
    return new Date(dateString).toLocaleString('fr-FR');
}

function formatFileSize(bytes) {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1048576) return `${Math.round(bytes / 1024)} KB`;
    return `${Math.round(bytes / 1048576)} MB`;
}

// Event listeners for French UI
document.addEventListener('DOMContentLoaded', function() {
    // Close drawer
    const closeDrawer = document.getElementById('closeDrawer');
    if (closeDrawer) {
        closeDrawer.addEventListener('click', () => {
            document.getElementById('detailsDrawer').style.display = 'none';
        });
    }
    
    // Filter change handlers
    const validationFilter = document.getElementById('validationFilter');
    const serviceFilterRes = document.getElementById('serviceFilterRes');
    const sortFilter = document.getElementById('sortFilter');
    
    if (validationFilter) validationFilter.addEventListener('change', loadResultats);
    if (serviceFilterRes) serviceFilterRes.addEventListener('change', loadResultats);
    if (sortFilter) sortFilter.addEventListener('change', loadResultats);
    
    // Button handlers
    const purgeBtn = document.getElementById('purgeResultsBtn');
    if (purgeBtn) purgeBtn.addEventListener('click', purgeAllResults);
    
    const startGrabberBtn = document.getElementById('startGrabberBtn');
    const stopGrabberBtn = document.getElementById('stopGrabberBtn');
    if (startGrabberBtn) startGrabberBtn.addEventListener('click', startGrabber);
    if (stopGrabberBtn) stopGrabberBtn.addEventListener('click', stopGrabber);
    
    const refreshDomainsBtn = document.getElementById('refreshDomainsBtn');
    if (refreshDomainsBtn) refreshDomainsBtn.addEventListener('click', loadDomaines);
    
    const refreshStatsBtn = document.getElementById('refreshStatsBtn');
    if (refreshStatsBtn) refreshStatsBtn.addEventListener('click', loadStatistiques);
    
    const refreshCrackerBtn = document.getElementById('refreshCrackerBtn');
    if (refreshCrackerBtn) refreshCrackerBtn.addEventListener('click', () => {
        // Refresh cracker status - this would check actual scan status
        updateCrackerStatus(false); // Default to stopped
    });
});

// Update the switchTab function to handle new tabs
const originalSwitchTab = window.switchTab;
window.switchTab = function(tabName) {
    originalSwitchTab(tabName);
    
    // Load data for specific tabs
    switch(tabName) {
        case 'statistiques':
            loadStatistiques();
            break;
        case 'resultats':
            loadResultats();
            break;
        case 'domaines':
            loadDomaines();
            break;
    }
};