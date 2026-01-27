#!/bin/bash

# Configuration
TOR_INSTANCE_COUNT=${TOR_INSTANCE_COUNT:-3}
TOR_START_PORT=${TOR_INSTANCE_START_PORT:-9050}
TOR_CONTROL_START_PORT=${TOR_CONTROL_START_PORT:-9051}
TOR_DATA_DIR="/var/lib/tor"

echo "Starting ${TOR_INSTANCE_COUNT} Tor instance(s)..."

# Create data directories for each Tor instance
for i in $(seq 0 $((TOR_INSTANCE_COUNT - 1))); do
    SOCKS_PORT=$((TOR_START_PORT + i))
    CONTROL_PORT=$((TOR_CONTROL_START_PORT + i))
    DATA_DIR="${TOR_DATA_DIR}_${i}"
    
    mkdir -p "$DATA_DIR"
    
    # Generate torrc configuration for this instance
    cat > "/tmp/torrc_${i}" <<EOF
SocksPort ${SOCKS_PORT}
ControlPort ${CONTROL_PORT}
DataDirectory ${DATA_DIR}
CookieAuthentication 1
EOF
    
    # Start Tor instance
    echo "Starting Tor instance ${i} on SOCKS port ${SOCKS_PORT}, Control port ${CONTROL_PORT}..."
    tor -f "/tmp/torrc_${i}" &
done

# Wait for Tor instances to initialize
echo "Waiting for Tor instances to initialize..."
sleep 15

# Verify Tor instances are running
for i in $(seq 0 $((TOR_INSTANCE_COUNT - 1))); do
    SOCKS_PORT=$((TOR_START_PORT + i))
    echo "Verifying Tor instance on port ${SOCKS_PORT}..."
    # Simple check - try to connect
    timeout 5 bash -c "echo > /dev/tcp/127.0.0.1/${SOCKS_PORT}" 2>/dev/null && echo "Port ${SOCKS_PORT} is ready" || echo "Warning: Port ${SOCKS_PORT} may not be ready"
done

echo "Starting Robin: AI-Powered Dark Web OSINT Tool..."
exec python main.py "$@"