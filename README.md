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

### Prerequisites
- Python 3.8+
- httpx CLI tool installed (`go install -v github.com/projectdiscovery/httpx/cmd/httpx@latest`)

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