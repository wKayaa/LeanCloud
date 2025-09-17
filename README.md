# HTTPx Scanner Web Panel

A production-ready HTTP response scanner with a clean web interface, built with FastAPI and vanilla JavaScript. This tool performs two-pass scanning: first building URLs from wordlists, then scanning responses for secrets using regex patterns.

## Features

### 🔒 Security-First Design
- **Authentication**: Secure login with forced password change on first run
- **Rate Limiting**: Configurable per-minute request limits  
- **RBAC**: Admin and viewer roles with appropriate permissions
- **Safe Defaults**: Conservative settings for production use
- **Audit Logging**: Complete scan and access logging

### 🎯 Two-Pass Scanning
- **Pass 1**: URL generation from targets and wordlist paths
- **Pass 2**: HTTP response analysis with regex pattern matching
- **Pattern Library**: Pre-configured patterns for AWS, SendGrid, Stripe, etc.
- **HTTPx Integration**: Leverages ProjectDiscovery's httpx CLI tool

### 🖥️ Web Interface
- **Clean UI**: Minimal, responsive design inspired by modern dashboards
- **Live Updates**: Real-time scan progress via WebSocket
- **Results Management**: Export findings as JSON/CSV
- **File Uploads**: Drag-and-drop targets and custom wordlists
- **Configuration**: Runtime config changes via web UI

### ⚡ Performance & Scalability
- **Concurrent Scanning**: Configurable thread pools
- **Rate Control**: Requests per second limiting
- **Memory Efficient**: Streaming results processing
- **Background Processing**: Non-blocking scan execution

## Quick Start

### Prerequisites
- Python 3.8+
- httpx CLI tool installed (`go install -v github.com/projectdiscovery/httpx/cmd/httpx@latest`)

### Installation

1. **Clone and Setup**
   ```bash
   git clone https://github.com/wKayaa/httpx_scanner.git
   cd httpx_scanner
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

## Usage

### Starting a Scan

1. **Navigate to "New Scan" tab**
2. **Add targets**: Enter domains/URLs or upload a file
3. **Select wordlist**: Use default or upload custom paths
4. **Configure settings**:
   - Concurrency: Number of parallel requests
   - Rate Limit: Requests per second  
   - Timeout: Request timeout in seconds
   - Follow Redirects: Enable/disable redirect following
5. **Click "Start Scan"**

### Monitoring Progress

- **Dashboard**: View scan statistics and recent activity
- **Live Logs**: Real-time scan progress (WebSocket)
- **Results Tab**: All scan results with filtering

### Managing Results

- **View Findings**: Browse discovered secrets/patterns
- **Export Data**: Download as JSON or CSV
- **Evidence Access**: Full evidence for admin users (masked for viewers)

## Configuration

### Regex Patterns

The scanner includes pre-configured patterns for:
- AWS Access Keys (`AKIA[A-Z0-9]{16}`)
- SendGrid API Keys (`SG\.[0-9A-Za-z\-_]{22}\.[0-9A-Za-z\-_]{43}`)
- Stripe Live Keys (`sk_live_[0-9A-Za-z]{24,99}`)
- Mailgun API Keys (`key-[0-9a-zA-Z]{32}`)
- Twilio Account SIDs (`AC[a-f0-9]{32}`)
- And more...

### Custom Wordlists

Upload custom wordlists via the web interface:
- **Format**: One path per line
- **Examples**: `/admin`, `config.json`, `.env`
- **File Types**: `.txt` files only

### Environment Variables

```bash
# Optional: Custom httpx binary path
export HTTPX_PATH="/path/to/httpx"

# Optional: Custom config file
export CONFIG_PATH="data/custom-config.yml"
```

## API Reference

### Authentication
```bash
# Login
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "your-password"}'

# Change Password  
curl -X POST http://localhost:8000/api/v1/auth/change-password \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"old_password": "old", "new_password": "new"}'
```

### Scans
```bash
# Start Scan
curl -X POST http://localhost:8000/api/v1/scans \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "targets": ["example.com", "target.com"],
    "wordlist": "paths.txt",
    "concurrency": 50,
    "timeout": 10,
    "follow_redirects": true
  }'

# Get Scan Status
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8000/api/v1/scans/SCAN_ID

# Get Findings
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8000/api/v1/scans/SCAN_ID/findings
```

### Results Export
```bash
# Export as JSON
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8000/api/v1/scans/SCAN_ID/export/json > results.json

# Export as CSV  
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8000/api/v1/scans/SCAN_ID/export/csv > results.csv
```

## Architecture

### Components
- **FastAPI Backend**: REST API and WebSocket server
- **Scanner Engine**: HTTPx CLI integration with pattern matching
- **Web UI**: Vanilla JavaScript frontend (no frameworks)
- **Auth System**: JWT-based authentication with bcrypt passwords
- **Config Management**: YAML-based persistent configuration

### File Structure
```
httpx_scanner/
├── app/
│   ├── main.py           # FastAPI application
│   ├── api/              # REST endpoints and WebSocket
│   ├── core/             # Business logic (scanner, auth, config)
│   └── static/           # Web UI files
├── data/
│   ├── config.yml        # Runtime configuration
│   ├── paths.txt         # Default wordlist
│   └── results/          # Scan result storage
└── requirements.txt      # Python dependencies
```

## Security Considerations

### Production Deployment
- Change default secret key in `data/config.yml`
- Configure proper CORS origins
- Use HTTPS with reverse proxy
- Set up proper firewall rules
- Enable audit logging

### Safe Mode Features
- **Rate limiting** prevents abuse
- **Authentication required** by default
- **Password complexity** requirements
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

2. **Permission errors**
   ```bash
   # Ensure write permissions
   chmod -R 755 data/
   ```

3. **Port already in use**
   ```bash
   # Change port in run.py or kill existing process
   lsof -ti:8000 | xargs kill -9
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
- Regex patterns based on common secret detection rules