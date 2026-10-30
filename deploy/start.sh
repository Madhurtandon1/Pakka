#!/bin/bash
# Start the FastAPI app on an internal port, then nginx on the public one.
# If either process stops, the container exits so the host restarts it.
set -euo pipefail

PORT="${PORT:-8000}"
sed "s/__PORT__/${PORT}/" /app/deploy/nginx.conf.template > /tmp/nginx.conf

uvicorn app.main:app --host 127.0.0.1 --port 9000 --proxy-headers --forwarded-allow-ips 127.0.0.1 &

# Wait (up to 30 s) for the app before opening the public port.
python - <<'EOF'
import socket, sys, time
for _ in range(60):
    try:
        socket.create_connection(("127.0.0.1", 9000), timeout=1).close()
        sys.exit(0)
    except OSError:
        time.sleep(0.5)
sys.exit("app did not start")
EOF

nginx -c /tmp/nginx.conf -g "daemon off;" &
echo "Pakka: nginx on port ${PORT} -> app on 127.0.0.1:9000"

wait -n
exit $?
