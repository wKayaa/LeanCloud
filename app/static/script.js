// Global state
let authToken = null;
let currentUser = null;
let websocket = null;
let currentScanId = null;

// DOM elements
const loginModal = document.getElementById('loginModal');
const passwordModal = document.getElementById('passwordModal');
const mainApp = document.getElementById('mainApp');
const logsModal = document.getElementById('logsModal');
const findingsModal = document.getElementById('findingsModal');

// Initialize app
document.addEventListener('DOMContentLoaded', function() {
    checkAuthentication();
    setupEventListeners();
});

// Authentication functions
function checkAuthentication() {
    const stored = localStorage.getItem('httpx_auth');
    if (stored) {
        const auth = JSON.parse(stored);
        authToken = auth.token;
        currentUser = auth.user;
        
        // Verify token is still valid
        fetch('/api/v1/health', {
            headers: {
                'Authorization': `Bearer ${authToken}`
            }
        }).then(response => {
            if (response.ok) {
                showMainApp();
            } else {
                showLogin();
            }
        }).catch(() => showLogin());
    } else {
        showLogin();
    }
}

function showLogin() {
    loginModal.style.display = 'block';
    mainApp.style.display = 'none';
    passwordModal.style.display = 'none';
}

function showPasswordChange() {
    loginModal.style.display = 'none';
    passwordModal.style.display = 'block';
    mainApp.style.display = 'none';
}

function showMainApp() {
    loginModal.style.display = 'none';
    passwordModal.style.display = 'none';
    mainApp.style.display = 'block';
    
    document.getElementById('userInfo').textContent = `Welcome, ${currentUser.username}`;
    loadDashboard();
    connectWebSocket();
}

function logout() {
    localStorage.removeItem('httpx_auth');
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
    document.getElementById('loginForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        const formData = new FormData(e.target);
        const username = formData.get('username');
        const password = formData.get('password');
        
        try {
            const response = await fetch('/api/v1/auth/login', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ username, password })
            });
            
            const data = await response.json();
            
            if (response.ok) {
                authToken = data.access_token;
                currentUser = data.user;
                localStorage.setItem('httpx_auth', JSON.stringify({
                    token: authToken,
                    user: currentUser
                }));
                
                if (data.first_run) {
                    showPasswordChange();
                } else {
                    showMainApp();
                }
            } else {
                showError('loginError', data.detail || 'Login failed');
            }
        } catch (error) {
            showError('loginError', 'Network error');
        }
    });
    
    // Password change form
    document.getElementById('passwordForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        const formData = new FormData(e.target);
        const oldPassword = formData.get('oldPassword');
        const newPassword = formData.get('newPassword');
        const confirmPassword = formData.get('confirmPassword');
        
        if (newPassword !== confirmPassword) {
            showError('passwordError', 'Passwords do not match');
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
                    old_password: oldPassword,
                    new_password: newPassword
                })
            });
            
            if (response.ok) {
                showMainApp();
            } else {
                const data = await response.json();
                showError('passwordError', data.detail || 'Password change failed');
            }
        } catch (error) {
            showError('passwordError', 'Network error');
        }
    });
    
    // Logout button
    document.getElementById('logoutBtn').addEventListener('click', logout);
    
    // Navigation
    document.querySelectorAll('.nav-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const tab = e.target.getAttribute('data-tab');
            switchTab(tab);
        });
    });
    
    // Scan form
    document.getElementById('scanForm').addEventListener('submit', handleScanSubmit);
    
    // File uploads
    document.getElementById('uploadTargetsBtn').addEventListener('click', () => {
        document.getElementById('targetsFile').click();
    });
    
    document.getElementById('targetsFile').addEventListener('change', handleTargetsUpload);
    
    document.getElementById('uploadWordlistBtn').addEventListener('click', () => {
        document.getElementById('wordlistFile').click();
    });
    
    document.getElementById('wordlistFile').addEventListener('change', handleWordlistUpload);
    
    // Refresh results
    document.getElementById('refreshResults').addEventListener('click', loadResults);
}

// Tab switching
function switchTab(tabName) {
    // Update nav buttons
    document.querySelectorAll('.nav-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    document.querySelector(`[data-tab="${tabName}"]`).classList.add('active');
    
    // Update tab content
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.remove('active');
    });
    document.getElementById(tabName).classList.add('active');
    
    // Load tab-specific data
    switch(tabName) {
        case 'dashboard':
            loadDashboard();
            break;
        case 'results':
            loadResults();
            break;
        case 'config':
            loadConfig();
            break;
    }
}

// Dashboard functions
async function loadDashboard() {
    try {
        const [statsResponse, scansResponse] = await Promise.all([
            fetch('/api/v1/stats', {
                headers: { 'Authorization': `Bearer ${authToken}` }
            }),
            fetch('/api/v1/scans', {
                headers: { 'Authorization': `Bearer ${authToken}` }
            })
        ]);
        
        if (statsResponse.ok) {
            const stats = await statsResponse.json();
            updateDashboardStats(stats);
        }
        
        if (scansResponse.ok) {
            const scans = await scansResponse.json();
            updateRecentScans(scans);
        }
    } catch (error) {
        console.error('Error loading dashboard:', error);
    }
}

function updateDashboardStats(stats) {
    document.getElementById('totalScans').textContent = stats.total_scans;
    document.getElementById('runningScans').textContent = stats.running_scans;
    document.getElementById('totalFindings').textContent = stats.total_findings;
    
    const successRate = stats.total_scans > 0 
        ? Math.round((stats.completed_scans / stats.total_scans) * 100)
        : 0;
    document.getElementById('successRate').textContent = `${successRate}%`;
}

function updateRecentScans(scans) {
    const container = document.getElementById('recentScansList');
    const recentScans = scans.slice(0, 5); // Show only recent 5
    
    container.innerHTML = recentScans.map(scan => `
        <div class="scan-item">
            <div class="scan-info">
                <h4>Scan ${scan.id.substring(0, 8)}</h4>
                <p>${scan.targets.length} targets • ${scan.findings_count} findings</p>
            </div>
            <div class="scan-status status-${scan.status}">
                ${scan.status}
            </div>
            <div class="scan-actions">
                ${scan.status === 'running' ? 
                    `<button class="btn btn-warning" onclick="viewLogs('${scan.id}')">Logs</button>` :
                    `<button class="btn btn-secondary" onclick="viewFindings('${scan.id}')">View</button>`
                }
            </div>
        </div>
    `).join('');
}

// Scan functions
async function handleScanSubmit(e) {
    e.preventDefault();
    
    const formData = new FormData(e.target);
    const targets = formData.get('targets').split('\n').filter(t => t.trim());
    
    const scanRequest = {
        targets: targets,
        wordlist: formData.get('wordlist'),
        concurrency: parseInt(formData.get('concurrency')),
        rate_limit: parseInt(formData.get('rateLimit')),
        timeout: parseInt(formData.get('timeout')),
        follow_redirects: formData.has('followRedirects')
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
            alert(`Scan started with ID: ${result.scan_id}`);
            e.target.reset();
            switchTab('results');
        } else {
            const error = await response.json();
            alert(`Error: ${error.detail}`);
        }
    } catch (error) {
        alert('Network error');
    }
}

async function handleTargetsUpload(e) {
    const file = e.target.files[0];
    if (!file) return;
    
    const formData = new FormData();
    formData.append('file', file);
    
    try {
        const response = await fetch('/api/v1/upload/targets', {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${authToken}`
            },
            body: formData
        });
        
        if (response.ok) {
            const result = await response.json();
            document.getElementById('targets').value = result.targets.join('\n');
            alert(`Loaded ${result.count} targets`);
        }
    } catch (error) {
        alert('Upload failed');
    }
}

async function handleWordlistUpload(e) {
    const file = e.target.files[0];
    if (!file) return;
    
    const formData = new FormData();
    formData.append('file', file);
    
    try {
        const response = await fetch('/api/v1/upload/wordlist', {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${authToken}`
            },
            body: formData
        });
        
        if (response.ok) {
            const result = await response.json();
            // Add to wordlist dropdown
            const select = document.getElementById('wordlist');
            const option = new Option(result.filename, result.filename);
            select.add(option);
            select.value = result.filename;
            alert(`Uploaded wordlist with ${result.paths_count} paths`);
        }
    } catch (error) {
        alert('Upload failed');
    }
}

// Results functions
async function loadResults() {
    try {
        const response = await fetch('/api/v1/scans', {
            headers: { 'Authorization': `Bearer ${authToken}` }
        });
        
        if (response.ok) {
            const scans = await response.json();
            displayScans(scans);
        }
    } catch (error) {
        console.error('Error loading results:', error);
    }
}

function displayScans(scans) {
    const container = document.getElementById('scansList');
    
    container.innerHTML = scans.map(scan => `
        <div class="scan-item">
            <div class="scan-info">
                <h4>Scan ${scan.id.substring(0, 8)}</h4>
                <p>${scan.targets.join(', ')}</p>
                <p>${scan.processed_urls}/${scan.total_urls} URLs • ${scan.findings_count} findings</p>
                <p>Created: ${new Date(scan.created_at).toLocaleString()}</p>
                ${scan.status === 'running' ? `
                    <div class="progress-bar">
                        <div class="progress-fill" style="width: ${scan.total_urls > 0 ? (scan.processed_urls/scan.total_urls)*100 : 0}%"></div>
                    </div>
                ` : ''}
            </div>
            <div class="scan-status status-${scan.status}">
                ${scan.status}
            </div>
            <div class="scan-actions">
                ${scan.status === 'running' ? `
                    <button class="btn btn-warning" onclick="viewLogs('${scan.id}')">Logs</button>
                    <button class="btn btn-danger" onclick="stopScan('${scan.id}')">Stop</button>
                ` : `
                    <button class="btn btn-secondary" onclick="viewFindings('${scan.id}')">Findings</button>
                `}
            </div>
        </div>
    `).join('');
}

// Modal functions
function viewLogs(scanId) {
    currentScanId = scanId;
    logsModal.style.display = 'block';
    
    const container = document.getElementById('logsContainer');
    container.innerHTML = 'Loading logs...\n';
    
    // Subscribe to logs via WebSocket
    if (websocket && websocket.readyState === WebSocket.OPEN) {
        websocket.send(JSON.stringify({
            type: 'subscribe_scan',
            scan_id: scanId
        }));
    }
}

function closeLogs() {
    logsModal.style.display = 'none';
    currentScanId = null;
}

async function viewFindings(scanId) {
    currentScanId = scanId;
    findingsModal.style.display = 'block';
    
    try {
        const response = await fetch(`/api/v1/scans/${scanId}/findings`, {
            headers: { 'Authorization': `Bearer ${authToken}` }
        });
        
        if (response.ok) {
            const findings = await response.json();
            displayFindings(findings);
        }
    } catch (error) {
        console.error('Error loading findings:', error);
    }
}

function displayFindings(findings) {
    const container = document.getElementById('findingsContainer');
    
    if (findings.length === 0) {
        container.innerHTML = '<p>No findings for this scan.</p>';
        return;
    }
    
    container.innerHTML = findings.map(finding => `
        <div class="finding-item">
            <div class="finding-info">
                <h5>${finding.provider}</h5>
                <div class="finding-url">${finding.url}</div>
                <div class="finding-evidence">${finding.evidence_masked}</div>
                <div class="finding-meta">
                    First seen: ${new Date(finding.first_seen).toLocaleString()}
                </div>
            </div>
            ${currentUser.role === 'admin' ? `
                <button class="btn btn-secondary" onclick="viewFullEvidence('${finding.id}')">
                    Full Evidence
                </button>
            ` : ''}
        </div>
    `).join('');
}

function closeFindings() {
    findingsModal.style.display = 'none';
    currentScanId = null;
}

async function stopScan(scanId) {
    if (!confirm('Are you sure you want to stop this scan?')) return;
    
    try {
        const response = await fetch(`/api/v1/scans/${scanId}/stop`, {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${authToken}` }
        });
        
        if (response.ok) {
            loadResults();
        }
    } catch (error) {
        alert('Error stopping scan');
    }
}

// WebSocket functions
function connectWebSocket() {
    const wsUrl = `ws://${window.location.host}/ws?token=${authToken}`;
    websocket = new WebSocket(wsUrl);
    
    websocket.onopen = () => {
        console.log('WebSocket connected');
    };
    
    websocket.onmessage = (event) => {
        const message = JSON.parse(event.data);
        handleWebSocketMessage(message);
    };
    
    websocket.onclose = () => {
        console.log('WebSocket disconnected');
        // Reconnect after 5 seconds
        setTimeout(connectWebSocket, 5000);
    };
}

function handleWebSocketMessage(message) {
    switch (message.type) {
        case 'scan_log':
            if (currentScanId === message.scan_id) {
                const container = document.getElementById('logsContainer');
                container.innerHTML += `[${new Date(message.timestamp).toLocaleTimeString()}] ${message.message}\n`;
                container.scrollTop = container.scrollHeight;
            }
            break;
            
        case 'scan_progress':
            // Update progress bars if visible
            updateProgress(message.scan_id, message.processed_urls, message.total_urls);
            break;
            
        case 'new_finding':
            // Could show notification or update counts
            break;
    }
}

function updateProgress(scanId, processed, total) {
    const progressBars = document.querySelectorAll('.progress-fill');
    progressBars.forEach(bar => {
        const scanItem = bar.closest('.scan-item');
        if (scanItem && scanItem.innerHTML.includes(scanId.substring(0, 8))) {
            const percent = total > 0 ? (processed / total) * 100 : 0;
            bar.style.width = `${percent}%`;
        }
    });
}

// Utility functions
function showError(elementId, message) {
    const element = document.getElementById(elementId);
    element.textContent = message;
    element.classList.add('show');
    setTimeout(() => {
        element.classList.remove('show');
    }, 5000);
}

// Export functions
document.getElementById('exportJson').addEventListener('click', () => {
    if (currentScanId) {
        window.open(`/api/v1/scans/${currentScanId}/export/json`, '_blank');
    }
});

document.getElementById('exportCsv').addEventListener('click', () => {
    if (currentScanId) {
        window.open(`/api/v1/scans/${currentScanId}/export/csv`, '_blank');
    }
});

// Config functions (placeholder)
function loadConfig() {
    document.getElementById('configForm').innerHTML = `
        <p>Configuration management coming soon...</p>
        <p>Current features:</p>
        <ul>
            <li>Authentication enabled</li>
            <li>Rate limiting active</li>
            <li>Default patterns loaded</li>
        </ul>
    `;
}