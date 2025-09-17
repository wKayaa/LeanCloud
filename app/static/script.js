// Global state
let authToken = null;
let currentUser = null;
let websocket = null;
let currentScanId = null;
let resourceMonitorInterval = null;

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
    setupEnhancedControls();
    startResourceMonitoring();
});

// Enhanced setup for new controls
function setupEnhancedControls() {
    // Concurrency slider
    const concurrencySlider = document.getElementById('concurrency');
    const concurrencyValue = document.getElementById('concurrencyValue');
    
    if (concurrencySlider && concurrencyValue) {
        concurrencySlider.addEventListener('input', function() {
            const value = parseInt(this.value);
            concurrencyValue.textContent = formatConcurrency(value);
            updateConcurrencyColor(value);
        });
    }

    // Preset buttons
    document.querySelectorAll('.preset-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            const value = parseInt(this.dataset.value);
            if (concurrencySlider) {
                concurrencySlider.value = value;
                concurrencyValue.textContent = formatConcurrency(value);
                updateConcurrencyColor(value);
            }
        });
    });

    // Enhanced regex toggle
    const enableRegex = document.getElementById('enableRegex');
    const regexSection = document.getElementById('regexSection');
    
    if (enableRegex && regexSection) {
        enableRegex.addEventListener('change', function() {
            regexSection.style.display = this.checked ? 'block' : 'none';
        });
    }

    // Validation buttons
    const validateTargetsBtn = document.getElementById('validateTargetsBtn');
    const validateRegexBtn = document.getElementById('validateRegexBtn');
    
    if (validateTargetsBtn) {
        validateTargetsBtn.addEventListener('click', validateTargets);
    }
    
    if (validateRegexBtn) {
        validateRegexBtn.addEventListener('click', validateRegex);
    }

    // Template selection
    const scanTemplate = document.getElementById('scanTemplate');
    if (scanTemplate) {
        scanTemplate.addEventListener('change', applyScanTemplate);
    }

    // Preview button
    const previewScanBtn = document.getElementById('previewScanBtn');
    if (previewScanBtn) {
        previewScanBtn.addEventListener('click', showScanPreview);
    }
}

// Format concurrency display
function formatConcurrency(value) {
    if (value >= 1000) {
        return (value / 1000).toFixed(1) + 'K';
    }
    return value.toString();
}

// Update concurrency color based on value
function updateConcurrencyColor(value) {
    const concurrencyValue = document.getElementById('concurrencyValue');
    if (!concurrencyValue) return;

    if (value <= 100) {
        concurrencyValue.style.color = 'var(--neon-green)';
    } else if (value <= 1000) {
        concurrencyValue.style.color = 'var(--neon-cyan)';
    } else if (value <= 10000) {
        concurrencyValue.style.color = '#f59e0b';
    } else {
        concurrencyValue.style.color = '#ef4444';
    }
}

// Validate targets
function validateTargets() {
    const targetsInput = document.getElementById('targets');
    const validationDiv = document.getElementById('targetValidation');
    
    if (!targetsInput || !validationDiv) return;
    
    const targets = targetsInput.value.split('\n').filter(t => t.trim());
    let validCount = 0;
    let invalidTargets = [];
    
    targets.forEach(target => {
        target = target.trim();
        if (isValidTarget(target)) {
            validCount++;
        } else {
            invalidTargets.push(target);
        }
    });
    
    validationDiv.style.display = 'block';
    
    if (invalidTargets.length === 0) {
        validationDiv.className = 'validation-result success';
        validationDiv.innerHTML = `✅ All ${validCount} targets are valid`;
    } else {
        validationDiv.className = 'validation-result warning';
        validationDiv.innerHTML = `⚠️ ${validCount} valid targets, ${invalidTargets.length} invalid:<br>
            <small>${invalidTargets.slice(0, 3).join(', ')}${invalidTargets.length > 3 ? '...' : ''}</small>`;
    }
}

// Simple target validation
function isValidTarget(target) {
    // URL pattern
    const urlPattern = /^https?:\/\/.+/;
    // Domain pattern
    const domainPattern = /^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*$/;
    // IP pattern (simple)
    const ipPattern = /^(\d{1,3}\.){3}\d{1,3}(\/\d{1,2})?$/;
    
    return urlPattern.test(target) || domainPattern.test(target) || ipPattern.test(target);
}

// Validate regex patterns
function validateRegex() {
    const regexInput = document.getElementById('customRegex');
    const validationDiv = document.getElementById('regexValidation');
    
    if (!regexInput || !validationDiv) return;
    
    const patterns = regexInput.value.split('\n').filter(p => p.trim());
    let validCount = 0;
    let invalidPatterns = [];
    
    patterns.forEach(pattern => {
        pattern = pattern.trim();
        try {
            new RegExp(pattern);
            validCount++;
        } catch (e) {
            invalidPatterns.push(pattern);
        }
    });
    
    validationDiv.style.display = 'block';
    
    if (invalidPatterns.length === 0) {
        validationDiv.className = 'validation-result success';
        validationDiv.innerHTML = `✅ All ${validCount} regex patterns are valid`;
    } else {
        validationDiv.className = 'validation-result error';
        validationDiv.innerHTML = `❌ ${validCount} valid patterns, ${invalidPatterns.length} invalid`;
    }
}

// Apply scan template
function applyScanTemplate() {
    const template = document.getElementById('scanTemplate').value;
    const form = document.getElementById('scanForm');
    
    if (!form) return;
    
    // Template configurations
    const templates = {
        quick: {
            concurrency: 100,
            timeout: 5,
            rateLimit: 500,
            retries: 1,
            delay: 0
        },
        comprehensive: {
            concurrency: 200,
            timeout: 15,
            rateLimit: 100,
            retries: 3,
            delay: 100
        },
        stealth: {
            concurrency: 10,
            timeout: 30,
            rateLimit: 10,
            retries: 2,
            delay: 1000
        },
        aggressive: {
            concurrency: 5000,
            timeout: 5,
            rateLimit: 2000,
            retries: 1,
            delay: 0
        }
    };
    
    if (templates[template]) {
        const config = templates[template];
        
        // Apply configuration
        Object.keys(config).forEach(key => {
            const element = document.getElementById(key);
            if (element) {
                element.value = config[key];
                
                // Update concurrency display if it's the concurrency slider
                if (key === 'concurrency') {
                    const concurrencyValue = document.getElementById('concurrencyValue');
                    if (concurrencyValue) {
                        concurrencyValue.textContent = formatConcurrency(config[key]);
                        updateConcurrencyColor(config[key]);
                    }
                }
            }
        });
        
        // Visual feedback
        form.classList.add('template-applied');
        setTimeout(() => form.classList.remove('template-applied'), 500);
    }
}

// Show scan preview
function showScanPreview() {
    const form = document.getElementById('scanForm');
    if (!form) return;
    
    const formData = new FormData(form);
    const config = {};
    
    // Collect form data
    for (let [key, value] of formData.entries()) {
        config[key] = value;
    }
    
    // Add additional data
    config.targets = formData.get('targets').split('\n').filter(t => t.trim()).length;
    config.estimatedTime = estimateScanTime(config);
    config.resourceUsage = estimateResourceUsage(config);
    
    // Create preview modal (simplified)
    alert(`Scan Configuration Preview:
    
Targets: ${config.targets}
Concurrency: ${config.concurrency}
Timeout: ${config.timeout}s
Rate Limit: ${config.rateLimit}/s
Estimated Time: ${config.estimatedTime}
Resource Usage: ${config.resourceUsage}
    `);
}

// Estimate scan time (simplified)
function estimateScanTime(config) {
    const targets = parseInt(config.targets) || 1;
    const concurrency = parseInt(config.concurrency) || 50;
    const estimatedPaths = 1000; // Default wordlist size
    
    const totalRequests = targets * estimatedPaths;
    const requestsPerSecond = Math.min(concurrency, parseInt(config.rateLimit) || 100);
    const estimatedSeconds = totalRequests / requestsPerSecond;
    
    if (estimatedSeconds < 60) {
        return `${Math.ceil(estimatedSeconds)}s`;
    } else if (estimatedSeconds < 3600) {
        return `${Math.ceil(estimatedSeconds / 60)}m`;
    } else {
        return `${Math.ceil(estimatedSeconds / 3600)}h`;
    }
}

// Estimate resource usage
function estimateResourceUsage(config) {
    const concurrency = parseInt(config.concurrency) || 50;
    
    if (concurrency <= 100) return 'Low';
    if (concurrency <= 1000) return 'Medium';
    if (concurrency <= 10000) return 'High';
    return 'Extreme';
}

// Resource monitoring
function startResourceMonitoring() {
    if (resourceMonitorInterval) {
        clearInterval(resourceMonitorInterval);
    }
    
    resourceMonitorInterval = setInterval(updateResourceMonitor, 2000);
    updateResourceMonitor(); // Initial update
}

function updateResourceMonitor() {
    // Simulate resource data (in real implementation, this would come from the server)
    const cpuUsage = Math.random() * 100;
    const memoryUsage = 8 + Math.random() * 20; // GB
    const networkUsage = Math.random() * 10; // Gb/s
    const activeScans = Math.floor(Math.random() * 5);
    
    // Update CPU
    const cpuElement = document.getElementById('cpuUsage');
    const cpuBar = document.getElementById('cpuBar');
    if (cpuElement && cpuBar) {
        cpuElement.textContent = `${Math.round(cpuUsage)}%`;
        cpuBar.style.width = `${cpuUsage}%`;
        cpuBar.className = `resource-fill ${getResourceLevel(cpuUsage)}`;
    }
    
    // Update Memory
    const memoryElement = document.getElementById('memoryUsage');
    const memoryBar = document.getElementById('memoryBar');
    if (memoryElement && memoryBar) {
        memoryElement.textContent = `${memoryUsage.toFixed(1)}GB`;
        const memoryPercent = (memoryUsage / 256) * 100; // Assuming 256GB total
        memoryBar.style.width = `${memoryPercent}%`;
        memoryBar.className = `resource-fill ${getResourceLevel(memoryPercent)}`;
    }
    
    // Update Network
    const networkElement = document.getElementById('networkUsage');
    const networkBar = document.getElementById('networkBar');
    if (networkElement && networkBar) {
        networkElement.textContent = `${networkUsage.toFixed(1)} Gb/s`;
        const networkPercent = (networkUsage / 10) * 100; // Assuming 10Gb/s total
        networkBar.style.width = `${networkPercent}%`;
        networkBar.className = `resource-fill ${getResourceLevel(networkPercent)}`;
    }
    
    // Update Active Scans
    const scansElement = document.getElementById('activeScans');
    const scansBar = document.getElementById('scansBar');
    if (scansElement && scansBar) {
        scansElement.textContent = activeScans.toString();
        const scansPercent = (activeScans / 10) * 100; // Assuming max 10 concurrent scans
        scansBar.style.width = `${scansPercent}%`;
        scansBar.className = `resource-fill ${getResourceLevel(scansPercent)}`;
    }
}

function getResourceLevel(percentage) {
    if (percentage < 30) return 'low';
    if (percentage < 70) return 'medium';
    return 'high';
}

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

// Enhanced Scan functions
async function handleScanSubmit(e) {
    e.preventDefault();
    
    const formData = new FormData(e.target);
    const targets = formData.get('targets').split('\n').filter(t => t.trim());
    
    // Validate minimum requirements
    if (targets.length === 0) {
        showNotification('❌ Please provide at least one target', 'error');
        return;
    }
    
    const concurrency = parseInt(formData.get('concurrency'));
    if (concurrency > 50000) {
        showNotification('❌ Concurrency cannot exceed 50,000 threads', 'error');
        return;
    }
    
    // Build enhanced scan request
    const scanRequest = {
        targets: targets,
        wordlist: formData.get('wordlist'),
        concurrency: concurrency,
        rate_limit: parseInt(formData.get('rateLimit')),
        timeout: parseInt(formData.get('timeout')),
        retries: parseInt(formData.get('retries')) || 3,
        delay: parseInt(formData.get('delay')) || 0,
        follow_redirects: formData.has('followRedirects'),
        verify_ssl: formData.has('verifySSL'),
        save_responses: formData.has('saveResponses'),
        custom_regex: formData.has('enableRegex') ? formData.get('customRegex') : null
    };
    
    // Show loading state
    const submitButton = e.target.querySelector('button[type="submit"]');
    const originalText = submitButton.textContent;
    submitButton.textContent = '🚀 Starting Scan...';
    submitButton.disabled = true;
    
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
            
            // Show success notification
            showNotification(`✅ Scan started successfully!<br>
                <strong>Scan ID:</strong> ${result.scan_id}<br>
                <strong>Targets:</strong> ${targets.length}<br>
                <strong>Concurrency:</strong> ${formatConcurrency(concurrency)}`, 'success');
            
            e.target.reset();
            
            // Reset concurrency display
            const concurrencyValue = document.getElementById('concurrencyValue');
            if (concurrencyValue) {
                concurrencyValue.textContent = '50';
                updateConcurrencyColor(50);
            }
            
            // Switch to results tab
            switchTab('results');
            
            // Start monitoring this scan
            monitorScan(result.scan_id);
            
        } else {
            const error = await response.json();
            showNotification(`❌ ${error.detail || 'Failed to start scan'}`, 'error');
        }
    } catch (error) {
        console.error('Error starting scan:', error);
        showNotification('❌ Network error occurred while starting scan', 'error');
    } finally {
        // Reset button
        submitButton.textContent = originalText;
        submitButton.disabled = false;
    }
}

// Monitor running scan
function monitorScan(scanId) {
    // Create and show scan indicator
    const indicator = createScanIndicator(scanId);
    document.body.appendChild(indicator);
    
    // Remove after some time or when scan completes
    setTimeout(() => {
        if (indicator.parentNode) {
            indicator.remove();
        }
    }, 30000); // Remove after 30 seconds
}

// Create scan running indicator
function createScanIndicator(scanId) {
    const indicator = document.createElement('div');
    indicator.className = 'scan-running-indicator';
    indicator.innerHTML = `
        <h6>🔄 Scan Running</h6>
        <div class="scan-progress">
            <span class="progress-text">Scan ID: ${scanId.substring(0, 8)}...</span>
            <span class="progress-percentage">0%</span>
        </div>
        <div class="progress-bar">
            <div class="progress-fill" style="width: 0%"></div>
        </div>
        <div style="margin-top: var(--spacing-sm); display: flex; gap: var(--spacing-sm);">
            <button class="btn btn-secondary" onclick="viewLogs('${scanId}')" style="font-size: 0.75rem; padding: var(--spacing-xs) var(--spacing-sm);">
                📋 Logs
            </button>
            <button class="btn btn-danger" onclick="stopScan('${scanId}')" style="font-size: 0.75rem; padding: var(--spacing-xs) var(--spacing-sm);">
                ⏹️ Stop
            </button>
        </div>
    `;
    
    return indicator;
}

// Enhanced notification system
function showNotification(message, type = 'info', duration = 5000) {
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.innerHTML = message;
    
    // Add styles for notification
    Object.assign(notification.style, {
        position: 'fixed',
        top: '20px',
        right: '20px',
        background: type === 'success' ? 'rgba(0, 255, 0, 0.1)' : 
                   type === 'error' ? 'rgba(239, 68, 68, 0.1)' : 
                   'rgba(0, 255, 255, 0.1)',
        border: type === 'success' ? '1px solid rgba(0, 255, 0, 0.2)' : 
                type === 'error' ? '1px solid rgba(239, 68, 68, 0.2)' : 
                '1px solid rgba(0, 255, 255, 0.2)',
        color: type === 'success' ? 'var(--neon-green)' : 
               type === 'error' ? '#ef4444' : 
               'var(--neon-cyan)',
        padding: 'var(--spacing-lg)',
        borderRadius: 'var(--radius-lg)',
        backdropFilter: 'blur(15px)',
        WebkitBackdropFilter: 'blur(15px)',
        boxShadow: '0 8px 32px rgba(0, 0, 0, 0.3)',
        zIndex: '10000',
        maxWidth: '400px',
        fontSize: '0.875rem',
        fontFamily: 'var(--font-secondary)',
        animation: 'slideInRight 0.3s ease-out'
    });
    
    document.body.appendChild(notification);
    
    // Auto remove
    setTimeout(() => {
        notification.style.animation = 'slideOutRight 0.3s ease-out';
        setTimeout(() => {
            if (notification.parentNode) {
                notification.remove();
            }
        }, 300);
    }, duration);
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