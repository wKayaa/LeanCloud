# HTTPx Cloud Scanner - Futuristic Multi-Service Intelligence Platform

A production-ready HTTP response scanner with a French-themed futuristic web interface, built with FastAPI and vanilla JavaScript. This tool performs comprehensive scanning with real-time telemetry, provider validation, and domain management capabilities.

## Features

### 🚀 French Futuristic UI
- **Statistiques du Scan**: Live progress tracking with provider tiles (AWS, SendGrid, SparkPost, Twilio, Brevo, MailGun)
- **Résultats des Hits**: Advanced filtering with Validés/Invalides counters and detail drawer
- **Gestion des Domaines**: Domain list management with integrated Grabber worker
- **Contrôle du Cracker**: Dashboard control panel with status monitoring
- **Real-time Metrics**: URLs/sec, HTTPS req/sec, precision, duration, ETA display

### 🔒 Security-First Design
- **Authentication**: Secure login with forced password change on first run
- **Rate Limiting**: Configurable per-minute request limits  
- **RBAC**: Admin and viewer roles with appropriate permissions
- **Safe Defaults**: Conservative settings for production use
- **Audit Logging**: Complete scan and access logging

### 🎯 Advanced Scanning Engine
- **Multi-Pass Scanning**: URL generation and HTTP response analysis
- **Provider Validation**: Safe credential verification for discovered secrets
- **Pattern Library**: Pre-configured v5.sh patterns for major providers
- **HTTPx Integration**: Leverages ProjectDiscovery's httpx CLI tool
- **Live Telemetry**: Real-time WebSocket streaming of scan metrics

### 🤖 Domain Intelligence
- **Grabber Worker**: Automated domain candidate generation
- **Safe Permutations**: Non-intrusive subdomain and TLD variations
- **File Management**: Upload, dedupe, and manage domain lists
- **Batch Processing**: Efficient handling of large domain sets

### ⚡ Performance & Scalability
- **High Concurrency**: Up to 50k async concurrent tasks
- **Adaptive Rate Control**: Dynamic requests per second limiting
- **Memory Efficient**: Streaming results processing
- **WebSocket Streaming**: Sub-250ms telemetry updates

## Quick Start

### 🐳 Docker Deployment (Recommended)

The fastest way to get started is with Docker Compose:

```bash
# 1. Clone the repository
git clone https://github.com/wKayaa/LeanCloud.git
cd LeanCloud

# 2. Run first-time setup (interactive)
./scripts/setup.sh

# 3. Start all services
docker compose up -d

# 4. Access the application
open http://localhost:8000
```

The setup script will configure:
- **Admin credentials** (email and secure password)
- **Database settings** (PostgreSQL or SQLite)
- **Redis configuration** (with graceful degradation)
- **Security keys** (auto-generated)
- **Scanner settings** (concurrency, rate limits)

The Docker setup includes:
- **FastAPI Application** (port 8000)
- **PostgreSQL Database** (persistent storage)
- **Redis Cache** (pub/sub and rate limiting)
- **Automatic health checks** and service dependencies

### 🔧 Manual Installation

### Prerequisites
- **Python 3.8+** - Required for the FastAPI backend
- **httpx CLI tool** - The core scanning engine (required for live scanning)
- **Optional**: Redis (for caching and pub/sub)
- **Optional**: PostgreSQL (for persistent storage)

### Redis Installation (Optional but Recommended)

Redis provides real-time WebSocket updates and rate limiting. The application gracefully degrades when Redis is unavailable.

**Ubuntu/Debian:**
```bash
sudo apt-get update && sudo apt-get install -y redis-server
sudo systemctl enable --now redis-server
redis-cli ping  # Should return PONG
```

**Docker:**
```bash
docker run -d --name redis -p 6379:6379 redis:7-alpine
```

**macOS:**
```bash
brew install redis
brew services start redis
```

### Configuration Options

The application supports flexible configuration via environment variables and YAML:

- **With Redis enabled**: Full real-time features, WebSocket updates, rate limiting
- **Redis disabled**: Polling mode, local rate limiting, degraded real-time features
- **SQLite**: Good for development and small deployments
- **PostgreSQL**: Recommended for production with high concurrency

Set `USE_REDIS=false` in your `.env` file to disable Redis dependency.

### HTTPx CLI Installation
The application requires ProjectDiscovery's httpx CLI tool for live scanning:

```bash
# Install httpx CLI (Go required)
go install -v github.com/projectdiscovery/httpx/cmd/httpx@latest

# Or download pre-compiled binary
wget https://github.com/projectdiscovery/httpx/releases/latest/download/httpx_linux_amd64.zip
unzip httpx_linux_amd64.zip
sudo mv httpx /usr/local/bin/

# Verify installation
httpx --help
```

**Note**: Without httpx CLI, the application will start but scans will fail with a clear error message. The UI will display a warning badge if httpx is not detected.

### Installation

1. **Clone and Setup**
   ```bash
   git clone https://github.com/wKayaa/httpxCloud.git
   cd httpxCloud
   pip install -r requirements.txt
   ```

2. **Install HTTPx CLI**
   ```bash
   # If you have Go installed:
   go install -v github.com/projectdiscovery/httpx/cmd/httpx@latest
   
   # Or download binary from: https://github.com/projectdiscovery/httpx/releases
   ```

3. **Start the Server**
   ```bash
   python run.py
   ```

4. **Access Web Interface**
   - Open: http://localhost:8000
   - Default login: `admin` / `admin123`
   - **Important**: Change password on first login!

### 🛠️ Production Configuration

For production deployments, ensure proper environment configuration:

```bash
# Required production settings
SECRET_KEY=your-strong-secret-key-here
JWT_SECRET_KEY=your-jwt-secret-key-here
ADMIN_PASSWORD=your-secure-admin-password

# Database (use PostgreSQL for production)
DATABASE_URL=postgresql+asyncpg://user:password@host:5432/dbname

# Redis (recommended for production)
REDIS_URL=redis://redis-host:6379/0

# Security settings
CORS_ORIGINS=https://yourdomain.com,https://scanner.yourdomain.com
RATE_LIMIT_PER_MINUTE=30

# Performance tuning
MAX_CONCURRENCY=1000
MAX_SCAN_RETENTION_DAYS=30
```

**Security Considerations:**
- Always change default passwords
- Use strong, unique secret keys
- Configure CORS origins appropriately
- Enable rate limiting for public deployments
- Use HTTPS in production
- Regular security updates

### 🔍 Health Monitoring

The application provides comprehensive health endpoints:

- **Health Check**: `GET /api/v1/healthz`
- **Readiness Check**: `GET /api/v1/readyz` 
- **Metrics**: `GET /api/v1/metrics` (Prometheus format)

Health status shows component-level information:
- **Database**: Connection and query health
- **Redis**: Cache and pub/sub availability
- **Overall Status**: healthy/degraded/unhealthy

## French UI Guide

### Dashboard - Contrôle du Cracker
The main dashboard provides system control with French interface:
- **Statut**: Shows ARRÊTÉ/EN COURS (Stopped/Running)
- **État**: Displays Prêt/Actif (Ready/Active) 
- **Control Buttons**: Démarrer (Start), Arrêter (Stop), Actualiser (Refresh)

### Statistiques du Scan
Real-time scan telemetry page matching the futuristic design:
- **Progress Bar**: Live percentage with URLs traitées count
- **Provider Tiles**: Hit counters for AWS, SendGrid, SparkPost, Twilio, Brevo, MailGun
- **Performance Metrics**: 
  - Vitesse: URLs/sec processing speed
  - Requêtes HTTPS/sec: HTTPS requests per second
  - Précision: Hit accuracy percentage
  - Durée: Scan duration
  - ETA: Estimated time remaining

### Résultats des Hits
Advanced results management with French filtering:
- **Counters**: Total/Validés/Invalides hit counts
- **Filters**: 
  - Statut: Tous/Validés/Invalides
  - Service: Filter by provider (AWS, SendGrid, etc.)
  - Trier par: Date (récent/ancien)
- **Details Drawer**: Click any hit to view masked credentials and validation status
- **Actions**: Export results, Supprimer Tout (Delete All - admin only)

## Live Scanning Flow

### Real-time httpx CLI Integration
HTTPx Cloud Scanner provides live execution of the httpx CLI with real-time telemetry:

1. **Scan Configuration**: Fill out the scan form with targets, wordlists, and options
2. **httpx Command Generation**: The system automatically builds httpx commands:
   ```bash
   httpx -l targets.txt -json -silent -no-color -timeout 10 -rl 100 -threads 50
   ```
3. **Live Execution**: httpx runs as subprocess with stdout/stderr parsing
4. **Real-time Updates**: WebSocket streams progress, logs, and results instantly
5. **Scan Control**: Pause/stop functionality sends signals to httpx process

### Example Scan Flow
```bash
# 1. Target list generated from form input
echo "example.com" > /tmp/targets.txt
echo "httpbin.org" >> /tmp/targets.txt

# 2. URLs built from targets + wordlist
https://example.com/.well-known/security.txt
https://example.com/robots.txt
https://httpbin.org/.env
https://httpbin.org/config.json

# 3. httpx command executed
httpx -l /tmp/targets.txt -json -silent -timeout 10 -rl 100

# 4. Live JSON parsing for hits detection
{"url": "https://httpbin.org/json", "status_code": 200, "content_length": 429}
```

### WebSocket Events
The UI receives real-time updates via WebSocket:
- **SCAN_PROGRESS**: URLs processed, throughput, ETA
- **SCAN_LOG**: httpx stdout/stderr messages  
- **SCAN_HIT**: Detected interesting responses
- **SCAN_STATUS**: Started/completed/stopped/failed

### Fallback Mechanisms
- **Polling Fallback**: If WebSocket fails, automatic polling of `/api/v1/scans/{id}/progress`
- **Redis Optional**: Rate limiting and caching work without Redis
- **Graceful Degradation**: Missing httpx shows clear warning, other features continue

### Troubleshooting Common Issues

| Issue | Cause | Solution |
|-------|-------|---------|
| "httpx binary not found" | httpx CLI not installed | Install httpx CLI or configure `httpx_path` in config |
| Scans fail to start | Permission issues | Check httpx binary permissions: `chmod +x /usr/local/bin/httpx` |
| Low performance | ulimit too low | Increase limits: `ulimit -n 65536` |
| WebSocket disconnects | Network/proxy issues | System falls back to polling automatically |

### Gestion des Domaines
Domain list management and Grabber control:
- **File Management**: Import .txt files, view size and entry counts
- **Grabber Worker**: 
  - Démarrer/Arrêter: Start/Stop domain processing
  - Status tracking: Domaines traités, Candidats générés
- **Safe Processing**: Non-intrusive domain variations and normalization

## CLI/API Cookbook

### Complete End-to-End Workflow

#### 1. Authentication & Setup
```bash
# Login and get token
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}' | \
  jq -r '.access_token')

echo "Token: $TOKEN"

# Change password (required on first login)
curl -X POST http://localhost:8000/api/v1/auth/change-password \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"old_password": "admin123", "new_password": "SecurePassword123!"}'
```

#### 2. Upload Target Lists
```bash
# Upload targets file (multipart)
curl -X POST http://localhost:8000/api/v1/upload/targets \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@targets.txt"

# Or create inline targets
echo -e "example.com\ntarget.com\ntest.org" > /tmp/targets.txt
curl -X POST http://localhost:8000/api/v1/upload/targets \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@/tmp/targets.txt"
```

#### 3. Start Enhanced Scan
```bash
# Start scan with high concurrency and custom settings
SCAN_RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/scans \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "targets": ["example.com", "target.com"],
    "wordlist": "paths.txt",
    "concurrency": 1000,
    "rate_limit": 500,
    "timeout": 10,
    "follow_redirects": true,
    "modules": ["aws", "sendgrid", "mailgun", "twilio"],
    "notes": "Production scan - high priority"
  }')

SCAN_ID=$(echo $SCAN_RESPONSE | jq -r '.scan_id')
CRACK_ID=$(echo $SCAN_RESPONSE | jq -r '.crack_id')
echo "Started scan: $SCAN_ID (Crack ID: $CRACK_ID)"
```

#### 4. Monitor Scan Progress
```bash
# Get real-time scan status
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/scans/$SCAN_ID" | jq

# WebSocket connection for live updates (using websocat or similar)
# websocat "ws://localhost:8000/ws/scans/$SCAN_ID?token=$TOKEN"

# Poll until completion
while true; do
  STATUS=$(curl -s -H "Authorization: Bearer $TOKEN" \
    "http://localhost:8000/api/v1/scans/$SCAN_ID" | jq -r '.status')
  PROGRESS=$(curl -s -H "Authorization: Bearer $TOKEN" \
    "http://localhost:8000/api/v1/scans/$SCAN_ID" | jq -r '.progress_percent')
  
  echo "Status: $STATUS, Progress: $PROGRESS%"
  
  if [[ "$STATUS" == "completed" || "$STATUS" == "failed" ]]; then
    break
  fi
  
  sleep 5
done
```

#### 5. Retrieve Results with French Filters
```bash
# Get all results
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/results" | jq

# Filter by validated results (Validés)
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/results?validated=true" | jq

# Filter by service provider
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/results?service=aws" | jq

# Sort by date (recent first - default)
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/results?sort=date_desc" | jq

# Combined filters with pagination
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/results?service=sendgrid&validated=true&sort=date_desc&limit=20" | jq

# Get result counters (for French UI)
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/results/counters" | jq
```

#### 6. Get Detailed Hit Information
```bash
# Get specific hit details with provider payload
HIT_ID=$(curl -s -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/results?limit=1" | jq -r '.hits[0].id')

curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/results/$HIT_ID" | jq

# Example response includes masked credentials and validation status
```

#### 7. Export Results
```bash
# Export as JSON
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/scans/$SCAN_ID/export/json" > results.json

# Export as CSV
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/scans/$SCAN_ID/export/csv" > results.csv

# Export with filters
curl -H "Authorization: Bearer $TOKEN" \
  -X POST "http://localhost:8000/api/v1/export" \
  -H "Content-Type: application/json" \
  -d '{
    "format": "jsonl",
    "service_filter": "aws",
    "works_filter": true,
    "reveal": false
  }' > aws-working-creds.jsonl
```

#### 8. Domain Management & Grabber
```bash
# List available domain lists
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/lists" | jq

# Start domain grabber
curl -X POST -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/grabber/start" | jq

# Monitor grabber status
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/grabber/status" | jq

# Stop grabber
curl -X POST -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/grabber/stop" | jq
```

#### 9. Telegram Notifications
```bash
# Configure Telegram settings
curl -X POST -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  "http://localhost:8000/api/v1/settings/telegram" \
  -d '{
    "bot_token": "YOUR_BOT_TOKEN",
    "chat_id": "YOUR_CHAT_ID",
    "enabled": true
  }'

# Test notification
curl -X POST -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/notifications/test/telegram"
```

### v5.sh Pattern Integration

The scanner maps v5.sh regex patterns to provider tiles:

```bash
# AWS Keys: AKIA[A-Z0-9]{16}
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/results?service=aws"

# SendGrid: SG\.[0-9A-Za-z-_]{22}\.[0-9A-Za-z-_]{43}
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/results?service=sendgrid"

# MailGun: key-[0-9a-zA-Z]{32}
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/results?service=mailgun"

# Stripe: sk_live_[0-9A-Za-z]{24,99}
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/results?service=stripe"

# Brevo: xkeysib-[a-f0-9]{64}-[a-zA-Z0-9]{16}
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/results?service=brevo"

# Twilio: AC[a-f0-9]{32}
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/results?service=twilio"
```

### Advanced Workflows

#### Automated Scanning Pipeline
```bash
#!/bin/bash
# complete-scan-pipeline.sh

TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "your-password"}' | \
  jq -r '.access_token')

# Upload targets
curl -X POST http://localhost:8000/api/v1/upload/targets \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@$1"

# Start high-concurrency scan
SCAN_ID=$(curl -s -X POST http://localhost:8000/api/v1/scans \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "targets": [],
    "concurrency": 5000,
    "rate_limit": 1000,
    "timeout": 15,
    "modules": ["aws", "sendgrid", "mailgun", "twilio", "brevo"]
  }' | jq -r '.scan_id')

# Wait for completion and export
while [[ $(curl -s -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/scans/$SCAN_ID" | jq -r '.status') != "completed" ]]; do
  sleep 10
done

# Export validated results only
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/results?validated=true" > validated-hits.json

echo "Scan completed. Results saved to validated-hits.json"
```

## Configuration

### Production Configuration

#### Secret Key Security
**IMPORTANT**: Change the secret key in `data/config.yml` before production use:
```yaml
secret_key: "your-secure-random-key-here"  # NOT the default value!
```
The default `"change-me-in-production"` value is only for development.

#### Redis Optional Mode
Redis is **optional** but recommended for enhanced features:

**Without Redis (Degraded Mode)**:
- ✅ All core functionality works
- ✅ Rate limiting falls back to in-memory
- ✅ No error spam (thanks to intelligent backoff)
- ❌ Limited real-time WebSocket features
- ❌ Rate limiting not distributed across instances

**With Redis**:
- ✅ Distributed rate limiting
- ✅ Enhanced WebSocket capabilities
- ✅ Better multi-instance support

To enable Redis, install and configure:
```bash
# Install Redis
sudo apt-get install redis-server  # Ubuntu/Debian
brew install redis                 # macOS

# Configure in data/config.yml
redis_url: "redis://localhost:6379/0"
```

#### Grabber Domain Seed Files
The grabber requires domain seed files to operate:

1. **Create the directory**: `data/lists/` (created automatically)
2. **Add domain files**: Place `.txt` or `.list` files with base domains:
   ```bash
   echo -e "example.com\ntarget.org\ntest.net" > data/lists/domains.txt
   ```
3. **Start via API or UI**: The grabber will process these files to generate domain candidates

**Without seed files**: Grabber returns HTTP 400 with clear error message (by design).

### Provider Pattern Mapping (v5.sh Integration)
The scanner automatically maps detected patterns to provider tiles:

- **AWS**: `AKIA[A-Z0-9]{16}` → AWS tile counter
- **SendGrid**: `SG\.[0-9A-Za-z-_]{22}\.[0-9A-Za-z-_]{43}` → SendGrid tile
- **MailGun**: `key-[0-9a-zA-Z]{32}` → MailGun tile
- **Stripe**: `sk_live_[0-9A-Za-z]{24,99}` → Payments tile
- **Brevo**: `xkeysib-[a-f0-9]{64}-[a-zA-Z0-9]{16}` → Brevo tile
- **Twilio**: `AC[a-f0-9]{32}` → Twilio tile

### Custom Wordlists
Upload custom wordlists via the web interface or API:
- **Format**: One path per line
- **Examples**: `/admin`, `config.json`, `.env`
- **File Types**: `.txt` files only

### Environment Variables
```bash
# Optional: Custom httpx binary path
export HTTPX_PATH="/path/to/httpx"

# Optional: Custom config file
export CONFIG_PATH="data/custom-config.yml"

# Optional: Enable debug logging
export DEBUG=true
```

## Architecture

### Enhanced Components
- **FastAPI Backend**: REST API and WebSocket server with French UI support
- **Scanner Engine**: HTTPx CLI integration with provider validation
- **French UI**: Futuristic interface with real-time telemetry
- **Grabber Worker**: Domain candidate generation system
- **Auth System**: JWT-based authentication with RBAC
- **Telemetry System**: Real-time WebSocket streaming

### File Structure
```
httpxCloud/
├── app/
│   ├── main.py              # FastAPI application
│   ├── api/                 # REST endpoints and WebSocket
│   │   ├── endpoints_enhanced.py
│   │   ├── results.py       # French results API
│   │   ├── grabber.py       # Domain grabber API
│   │   ├── settings.py      # Telegram settings API
│   │   └── websocket_enhanced.py
│   ├── core/                # Business logic
│   │   ├── models.py        # Enhanced models with French UI support
│   │   ├── scanner_enhanced.py
│   │   └── ...
│   └── static/              # French UI files
│       ├── index.html       # Enhanced with French tabs
│       └── script.js        # French UI functions
├── data/
│   ├── config.yml           # Runtime configuration
│   ├── settings.json        # Telegram settings
│   ├── lists/              # Domain lists for Grabber
│   └── results/            # Scan result storage
├── v5.sh                   # Pattern reference script
└── requirements.txt        # Python dependencies
```

## API Reference

### New French UI Endpoints

#### Results Management
```bash
# List results with French filters
GET /api/v1/results?service=aws&validated=true&sort=date_desc

# Get result details with provider payload
GET /api/v1/results/{hit_id}

# Purge all results (admin only)
POST /api/v1/results/purge

# Get counters for French UI
GET /api/v1/results/counters

# Get provider statistics for tiles
GET /api/v1/results/providers
```

#### Domain Grabber
```bash
# Start domain grabber
POST /api/v1/grabber/start

# Get grabber status
GET /api/v1/grabber/status

# Stop grabber
POST /api/v1/grabber/stop

# List domain files
GET /api/v1/lists

# Delete domain list
DELETE /api/v1/lists/{list_id}
```

#### Settings & Notifications
```bash
# Save Telegram settings
POST /api/v1/settings/telegram

# Get Telegram settings (masked)
GET /api/v1/settings/telegram

# Test Telegram notification
POST /api/v1/notifications/test/telegram

# Save scan defaults
POST /api/v1/settings/scan_defaults

# Save data retention settings
POST /api/v1/settings/data_retention
```

### WebSocket Endpoints
```bash
# Dashboard stats (French UI compatible)
ws://localhost:8000/ws/dashboard?token=YOUR_TOKEN

# Per-scan telemetry
ws://localhost:8000/ws/scans/{scan_id}?token=YOUR_TOKEN
```

## Security Considerations

### Production Deployment
- Change default secret key in `data/config.yml`
- Configure proper CORS origins
- Use HTTPS with reverse proxy
- Set up proper firewall rules
- Enable audit logging
- Secure Telegram bot tokens

### Safe Mode Features
- **Rate limiting** prevents abuse
- **Authentication required** by default
- **Provider validation** uses safe, time-bounded checks
- **Secret masking** by default (admin flag to reveal)
- **Session management** with JWT expiration
- **Input validation** on all endpoints

## Troubleshooting

### Common Issues

1. **HTTPx not found**
   ```bash
   # Install httpx CLI
   go install -v github.com/projectdiscovery/httpx/cmd/httpx@latest
   # Or set custom path in config
   ```

2. **Redis connection errors**
   ```bash
   # Optional: Install Redis for enhanced WebSocket features
   # The system works without Redis but with limited real-time features
   sudo apt-get install redis-server
   ```

3. **French UI not loading**
   ```bash
   # Clear browser cache and reload
   # Check browser console for JavaScript errors
   ```

4. **Permission errors**
   ```bash
   # Ensure write permissions
   chmod -R 755 data/
   ```

## Troubleshooting

### Common Issues

#### UUID Database Errors
**Error**: `'str' object has no attribute 'hex'`
**Solution**: This was fixed in the latest version. Update your installation and restart the application.

#### Redis Connection Issues
**Error**: Redis connection failed or WebSocket not working
**Solutions**:
1. **Check Redis status**: `redis-cli ping` should return `PONG`
2. **Restart Redis**: `sudo systemctl restart redis-server`
3. **Disable Redis**: Set `USE_REDIS=false` in `.env` to run in degraded mode
4. **Check Docker**: `docker ps` to ensure Redis container is running

#### Docker Health Check Failures
**Error**: API container health check failing
**Solutions**:
1. **Check logs**: `docker compose logs api`
2. **Verify endpoint**: `curl http://localhost:8000/healthz`
3. **Database connection**: Ensure PostgreSQL is running and accessible
4. **Port conflicts**: Check if port 8000 is already in use

#### Performance Issues
**Symptoms**: Slow scanning, high memory usage, timeouts
**Solutions**:
1. **Reduce concurrency**: Lower `MAX_CONCURRENCY` in `.env`
2. **Increase timeouts**: Adjust `timeout` in scan configuration
3. **Check resources**: Monitor CPU and memory usage
4. **Database tuning**: For PostgreSQL, consider connection pooling

#### Scanner Not Working
**Error**: Scans fail or don't start
**Solutions**:
1. **Check httpx CLI**: `httpx --help` should work
2. **Path issues**: Ensure httpx is in PATH or set `HTTPX_PATH` in `.env`
3. **Permissions**: Check file permissions on wordlist files
4. **Database**: Verify database connection and tables exist

### Environment Variables Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `USE_REDIS` | `true` | Enable Redis for pub/sub and caching |
| `DATABASE_URL` | SQLite | Database connection string |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection string |
| `MAX_CONCURRENCY` | `1000` | Maximum concurrent HTTP requests |
| `RATE_LIMIT_PER_MINUTE` | `60` | Rate limit for API requests |
| `SECRET_KEY` | auto-generated | Application secret key |
| `JWT_SECRET_KEY` | auto-generated | JWT signing key |
| `ADMIN_EMAIL` | `admin@example.com` | Admin user email |
| `ADMIN_PASSWORD` | `admin123` | Admin user password |
| `CORS_ORIGINS` | `http://localhost:8000` | Allowed CORS origins |
| `DEBUG` | `false` | Enable debug logging |

### Health Check Endpoints

- **Health Check**: `GET /healthz` - Basic application health
- **Readiness Check**: `GET /api/v1/readyz` - Component-level health
- **Metrics**: `GET /api/v1/metrics` - Prometheus metrics

Component health includes:
- **Database**: Connection and query health
- **Redis**: Cache and pub/sub availability  
- **Overall Status**: healthy/degraded/unhealthy

### Log Analysis

**View application logs**:
```bash
# Docker Compose
docker compose logs api

# Find specific errors
docker compose logs api | grep ERROR

# Follow logs in real-time
docker compose logs -f api
```

**Common log messages**:
- `Redis initialization failed` - Redis unavailable, running in degraded mode
- `Database initialization failed` - Database connection issues
- `modules_LeanCloud not found` - Optional modules not installed (normal)
- `Configuration issues detected` - Review settings validation warnings

### First-Run Setup Issues

If the setup script fails or you need to reconfigure:

```bash
# Re-run setup
./scripts/setup.sh

# Manual configuration
cp .env.example .env
nano .env  # Edit settings manually

# Reset to defaults
rm .env data/config.yml
./scripts/setup.sh
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Built on [FastAPI](https://fastapi.tiangolo.com/) framework
- Uses [HTTPx](https://github.com/projectdiscovery/httpx) CLI tool
- Inspired by SpaceCracker's unified panel approach
- French UI design inspired by futuristic cybersecurity interfaces
- Regex patterns based on v5.sh and common secret detection rules