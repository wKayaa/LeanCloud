/**
 * HTTPx Cloud v1 Phase 1 - Main Application Logic
 * Handles navigation, WebSocket connections, and global state
 */

// Global application state
window.HTTPxApp = {
    currentPage: 'dashboard',
    activeWebSocket: null,
    currentScan: null,
    lists: [],
    settings: {},
    isLoading: false
};

// Initialize application when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    console.log('HTTPx Cloud v1 Phase 1 - Interface futuriste loaded');
    
    // Initialize navigation
    initializeNavigation();
    
    // Load initial data
    loadInitialData();
    
    // Initialize WebSocket connection for dashboard
    connectWebSocket();
    
    // Add keyboard shortcuts
    initializeKeyboardShortcuts();
    
    // Add visibility change handler
    document.addEventListener('visibilitychange', handleVisibilityChange);
});

/**
 * Initialize navigation tab switching
 */
function initializeNavigation() {
    const navTabs = document.querySelectorAll('.nav-tab');
    const pageSection = document.querySelectorAll('.page-section');
    
    navTabs.forEach(tab => {
        tab.addEventListener('click', function() {
            const targetPage = this.dataset.page;
            
            // Update active tab
            navTabs.forEach(t => t.classList.remove('active'));
            this.classList.add('active');
            
            // Update visible page
            pageSection.forEach(page => page.classList.remove('active'));
            const targetSection = document.getElementById(`${targetPage}-page`);
            if (targetSection) {
                targetSection.classList.add('active');
            }
            
            // Update global state
            HTTPxApp.currentPage = targetPage;
            
            // Load page-specific data
            loadPageData(targetPage);
            
            console.log(`Navigated to page: ${targetPage}`);
        });
    });
}

/**
 * Load page-specific data when navigating
 */
function loadPageData(page) {
    switch (page) {
        case 'dashboard':
            refreshDashboard();
            break;
        case 'scan':
            loadAvailableLists();
            break;
        case 'lists':
            refreshLists();
            break;
        case 'settings':
            loadCurrentSettings();
            break;
        case 'ipgen':
            // IP generator doesn't need initial data
            break;
        case 'hits':
            // Hits will be loaded in Phase 2
            break;
    }
}

/**
 * Load initial application data
 */
async function loadInitialData() {
    try {
        HTTPxApp.isLoading = true;
        
        // Load dashboard data
        await refreshDashboard();
        
        // Load available lists for scan form
        await loadAvailableLists();
        
        HTTPxApp.isLoading = false;
    } catch (error) {
        console.error('Failed to load initial data:', error);
        showNotification('Erreur lors du chargement initial des données', 'error');
        HTTPxApp.isLoading = false;
    }
}

/**
 * Connect to WebSocket for real-time updates
 */
function connectWebSocket() {
    if (HTTPxApp.activeWebSocket) {
        HTTPxApp.activeWebSocket.close();
    }
    
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/dashboard`;
    
    HTTPxApp.activeWebSocket = new WebSocket(wsUrl);
    
    HTTPxApp.activeWebSocket.onopen = function() {
        console.log('Dashboard WebSocket connected');
        showNotification('Connexion temps réel établie', 'success');
    };
    
    HTTPxApp.activeWebSocket.onmessage = function(event) {
        try {
            const data = JSON.parse(event.data);
            handleWebSocketMessage(data);
        } catch (error) {
            console.error('Failed to parse WebSocket message:', error);
        }
    };
    
    HTTPxApp.activeWebSocket.onclose = function() {
        console.log('Dashboard WebSocket disconnected');
        showNotification('Connexion temps réel fermée', 'warning');
        
        // Attempt to reconnect after 5 seconds
        setTimeout(() => {
            if (HTTPxApp.currentPage === 'dashboard') {
                connectWebSocket();
            }
        }, 5000);
    };
    
    HTTPxApp.activeWebSocket.onerror = function(error) {
        console.error('Dashboard WebSocket error:', error);
        showNotification('Erreur de connexion temps réel', 'error');
    };
}

/**
 * Handle incoming WebSocket messages
 */
function handleWebSocketMessage(data) {
    console.log('WebSocket message received:', data);
    
    switch (data.type) {
        case 'dashboard.stats':
            updateDashboardStats(data.data);
            break;
        case 'scan.progress':
            updateScanProgress(data.data);
            break;
        case 'scan.hit':
            handleNewHit(data.data);
            break;
        case 'connected':
            console.log('WebSocket connection confirmed');
            break;
        case 'pong':
            // Handle ping response
            break;
        default:
            console.log('Unknown WebSocket message type:', data.type);
    }
}

/**
 * Update dashboard statistics
 */
function updateDashboardStats(stats) {
    // Update stat cards
    const elements = {
        'total-scans': stats.total_scans || 0,
        'active-scans': stats.active_scans || 0,
        'total-hits': stats.total_hits || 0,
        'avg-speed': Math.round(stats.avg_urls_per_sec || 0)
    };
    
    Object.entries(elements).forEach(([id, value]) => {
        const element = document.getElementById(id);
        if (element) {
            // Animate number change
            animateNumber(element, value);
        }
    });
}

/**
 * Animate number changes in stat cards
 */
function animateNumber(element, targetValue) {
    const currentValue = parseInt(element.textContent) || 0;
    const increment = (targetValue - currentValue) / 10;
    let step = 0;
    
    const animation = setInterval(() => {
        step++;
        const newValue = Math.round(currentValue + (increment * step));
        
        if (step >= 10) {
            element.textContent = targetValue.toLocaleString();
            clearInterval(animation);
        } else {
            element.textContent = newValue.toLocaleString();
        }
    }, 50);
}

/**
 * Refresh dashboard data
 */
async function refreshDashboard() {
    try {
        // Get recent scans
        const response = await fetch('/api/v1/scans');
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        
        const data = await response.json();
        displayRecentScans(data.scans || []);
        
        // Send WebSocket request for stats if connected
        if (HTTPxApp.activeWebSocket && HTTPxApp.activeWebSocket.readyState === WebSocket.OPEN) {
            HTTPxApp.activeWebSocket.send(JSON.stringify({
                type: 'get_stats'
            }));
        }
        
    } catch (error) {
        console.error('Failed to refresh dashboard:', error);
        document.getElementById('recent-scans').innerHTML = `
            <div class="alert alert-error">
                <strong>Erreur:</strong> Impossible de charger les données du dashboard
            </div>
        `;
    }
}

/**
 * Display recent scans in dashboard
 */
function displayRecentScans(scans) {
    const container = document.getElementById('recent-scans');
    
    if (!scans || scans.length === 0) {
        container.innerHTML = `
            <div class="text-center text-muted" style="padding: 2rem;">
                <p>Aucun scan récent</p>
                <button class="btn btn-primary" onclick="switchToPage('scan')">
                    <svg class="icon" viewBox="0 0 24 24">
                        <path d="M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z"/>
                    </svg>
                    Créer un scan
                </button>
            </div>
        `;
        return;
    }
    
    const scansHtml = scans.slice(0, 5).map(scan => {
        const statusClass = getStatusClass(scan.status);
        const progressPercent = scan.progress_percent || 0;
        
        return `
            <div class="scan-item glass" style="padding: 1rem; margin-bottom: 1rem; border-radius: 0.5rem;">
                <div style="display: flex; justify-content: between; align-items: center; margin-bottom: 0.5rem;">
                    <div>
                        <strong>${scan.name}</strong>
                        <span style="color: var(--text-muted); margin-left: 1rem;">${scan.crack_id}</span>
                    </div>
                    <span class="status-badge ${statusClass}">${getStatusText(scan.status)}</span>
                </div>
                
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(100px, 1fr)); gap: 1rem; margin-bottom: 0.5rem; font-size: 0.9rem;">
                    <div><span style="color: var(--text-muted);">URLs:</span> ${scan.processed_urls}/${scan.total_urls}</div>
                    <div><span style="color: var(--text-muted);">Hits:</span> <span style="color: var(--neon-pink);">${scan.hits}</span></div>
                    <div><span style="color: var(--text-muted);">Erreurs:</span> <span style="color: var(--neon-red);">${scan.errors}</span></div>
                    ${scan.urls_per_sec ? `<div><span style="color: var(--text-muted);">Vitesse:</span> ${Math.round(scan.urls_per_sec)} URL/s</div>` : ''}
                </div>
                
                ${scan.status === 'running' ? `
                    <div class="progress" style="height: 4px;">
                        <div class="progress-bar" style="width: ${progressPercent}%"></div>
                    </div>
                ` : ''}
            </div>
        `;
    }).join('');
    
    container.innerHTML = scansHtml;
}

/**
 * Get CSS class for scan status
 */
function getStatusClass(status) {
    const statusMap = {
        'running': 'status-running',
        'completed': 'status-completed', 
        'paused': 'status-paused',
        'stopped': 'status-error',
        'error': 'status-error',
        'queued': 'status-warning'
    };
    return statusMap[status] || 'status-warning';
}

/**
 * Get display text for scan status
 */
function getStatusText(status) {
    const statusMap = {
        'running': 'En cours',
        'completed': 'Terminé',
        'paused': 'En pause',
        'stopped': 'Arrêté',
        'error': 'Erreur',
        'queued': 'En attente'
    };
    return statusMap[status] || status;
}

/**
 * Switch to a specific page programmatically
 */
function switchToPage(pageName) {
    const tab = document.querySelector(`[data-page="${pageName}"]`);
    if (tab) {
        tab.click();
    }
}

/**
 * Initialize keyboard shortcuts
 */
function initializeKeyboardShortcuts() {
    document.addEventListener('keydown', function(event) {
        // Only process shortcuts when not typing in form fields
        if (event.target.tagName === 'INPUT' || event.target.tagName === 'TEXTAREA') {
            return;
        }
        
        if (event.ctrlKey || event.metaKey) {
            switch (event.key) {
                case '1':
                    event.preventDefault();
                    switchToPage('dashboard');
                    break;
                case '2':
                    event.preventDefault();
                    switchToPage('scan');
                    break;
                case '3':
                    event.preventDefault();
                    switchToPage('lists');
                    break;
                case '4':
                    event.preventDefault();
                    switchToPage('ipgen');
                    break;
                case '5':
                    event.preventDefault();
                    switchToPage('hits');
                    break;
                case '6':
                    event.preventDefault();
                    switchToPage('settings');
                    break;
                case 'r':
                    event.preventDefault();
                    refreshCurrentPage();
                    break;
            }
        }
        
        // ESC key to close modals or cancel operations
        if (event.key === 'Escape') {
            // Handle ESC key logic here
            console.log('ESC pressed');
        }
    });
}

/**
 * Refresh current page data
 */
function refreshCurrentPage() {
    loadPageData(HTTPxApp.currentPage);
    showNotification('Page actualisée', 'info');
}

/**
 * Handle page visibility changes
 */
function handleVisibilityChange() {
    if (document.hidden) {
        // Page is hidden, maybe pause some operations
        console.log('Page hidden');
    } else {
        // Page is visible, refresh data
        console.log('Page visible');
        refreshCurrentPage();
    }
}

/**
 * Show notification to user
 */
function showNotification(message, type = 'info', duration = 4000) {
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `alert alert-${type}`;
    notification.style.cssText = `
        position: fixed;
        top: 1rem;
        right: 1rem;
        z-index: 1000;
        min-width: 300px;
        max-width: 500px;
        animation: slideInRight 0.3s ease-out;
    `;
    notification.innerHTML = `
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <span>${message}</span>
            <button onclick="this.parentElement.parentElement.remove()" style="background: none; border: none; color: inherit; font-size: 1.2rem; cursor: pointer;">&times;</button>
        </div>
    `;
    
    // Add to page
    document.body.appendChild(notification);
    
    // Auto remove after duration
    setTimeout(() => {
        if (notification.parentElement) {
            notification.style.animation = 'slideOutRight 0.3s ease-in forwards';
            setTimeout(() => notification.remove(), 300);
        }
    }, duration);
}

/**
 * Add CSS animations for notifications
 */
const style = document.createElement('style');
style.textContent = `
    @keyframes slideInRight {
        from { transform: translateX(100%); opacity: 0; }
        to { transform: translateX(0); opacity: 1; }
    }
    
    @keyframes slideOutRight {
        from { transform: translateX(0); opacity: 1; }
        to { transform: translateX(100%); opacity: 0; }
    }
`;
document.head.appendChild(style);

/**
 * Utility function to format file sizes
 */
function formatFileSize(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

/**
 * Utility function to format numbers
 */
function formatNumber(num) {
    if (num >= 1000000) {
        return (num / 1000000).toFixed(1) + 'M';
    } else if (num >= 1000) {
        return (num / 1000).toFixed(1) + 'k';
    }
    return num.toString();
}

/**
 * Utility function to format time duration
 */
function formatDuration(seconds) {
    if (!seconds || seconds < 0) return '--';
    
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);
    
    if (hours > 0) {
        return `${hours}h ${minutes}m`;
    } else if (minutes > 0) {
        return `${minutes}m ${secs}s`;
    } else {
        return `${secs}s`;
    }
}

/**
 * Debounce function for API calls
 */
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Export utility functions to global scope
window.showNotification = showNotification;
window.formatFileSize = formatFileSize;
window.formatNumber = formatNumber;
window.formatDuration = formatDuration;
window.debounce = debounce;
window.refreshDashboard = refreshDashboard;