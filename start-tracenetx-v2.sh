#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$HOME/Tracenetx"
BACKEND_DIR="$PROJECT_DIR/backend"
FRONTEND_DIR="$PROJECT_DIR/frontend/tracenetx-ui"
NEO4J_CONTAINER="neo4j"
BOLT_PORT=7687
HTTP_PORT=7474
BACKEND_PORT=8001
FRONTEND_PORT=3002

BACKEND_PID=""
FRONTEND_PID=""

cleanup() {
    echo ""
    echo "[*] Shutting down..."
    [[ -n "$BACKEND_PID" ]] && kill "$BACKEND_PID" 2>/dev/null || true
    [[ -n "$FRONTEND_PID" ]] && kill "$FRONTEND_PID" 2>/dev/null || true
    exit 0
}
trap cleanup SIGINT SIGTERM

echo "[1/4] Ensuring Neo4j container is up..."
if [ "$(docker inspect -f '{{.State.Running}}' "$NEO4J_CONTAINER" 2>/dev/null)" != "true" ]; then
    if docker ps -a --format '{{.Names}}' | grep -q "^${NEO4J_CONTAINER}$"; then
        docker start "$NEO4J_CONTAINER" >/dev/null
    else
        echo "[!] No existing '$NEO4J_CONTAINER' container found. Creating one..."
        docker run -d --name "$NEO4J_CONTAINER" \
            -p ${HTTP_PORT}:7474 -p ${BOLT_PORT}:7687 \
            -e NEO4J_AUTH=neo4j/password123 \
            neo4j:latest >/dev/null
    fi
else
    echo "    Neo4j container already running."
fi

echo "[2/4] Waiting for Neo4j bolt (${BOLT_PORT}) to accept connections..."
for i in $(seq 1 60); do
    if (echo > /dev/tcp/127.0.0.1/${BOLT_PORT}) >/dev/null 2>&1; then
        echo "    Bolt port is open (attempt ${i})."
        break
    fi
    if [ "$i" -eq 60 ]; then
        echo "[X] Neo4j bolt port never came up after 60s. Aborting."
        exit 1
    fi
    sleep 1
done

echo "    Waiting for Neo4j HTTP (${HTTP_PORT}) to respond..."
for i in $(seq 1 60); do
    if curl -sf "http://localhost:${HTTP_PORT}" >/dev/null 2>&1; then
        echo "    Neo4j HTTP is ready (attempt ${i})."
        break
    fi
    if [ "$i" -eq 60 ]; then
        echo "[X] Neo4j HTTP never responded after 60s. Aborting."
        exit 1
    fi
    sleep 1
done

echo "[3/4] Starting FastAPI backend on port ${BACKEND_PORT}..."
cd "$BACKEND_DIR"
source venv/bin/activate
uvicorn main:app --reload --port ${BACKEND_PORT} > /tmp/tracenetx-backend.log 2>&1 &
BACKEND_PID=$!
deactivate

echo "    Waiting for backend /docs to respond..."
for i in $(seq 1 60); do
    if curl -sf "http://localhost:${BACKEND_PORT}/docs" >/dev/null 2>&1; then
        echo "    Backend is ready (attempt ${i})."
        break
    fi
    if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
        echo "[X] Backend process died. Check /tmp/tracenetx-backend.log"
        exit 1
    fi
    if [ "$i" -eq 60 ]; then
        echo "[X] Backend /docs never responded after 60s. Check /tmp/tracenetx-backend.log"
        exit 1
    fi
    sleep 1
done

echo "[4/4] Starting React frontend on port ${FRONTEND_PORT}..."
cd "$FRONTEND_DIR"
PORT=${FRONTEND_PORT} BROWSER=none npm start > /tmp/tracenetx-frontend.log 2>&1 &
FRONTEND_PID=$!

echo "    Waiting for frontend to respond..."
for i in $(seq 1 60); do
    if curl -sf "http://localhost:${FRONTEND_PORT}" >/dev/null 2>&1; then
        echo "    Frontend is ready (attempt ${i})."
        break
    fi
    if ! kill -0 "$FRONTEND_PID" 2>/dev/null; then
        echo "[X] Frontend process died. Check /tmp/tracenetx-frontend.log"
        exit 1
    fi
    if [ "$i" -eq 60 ]; then
        echo "[!] Frontend didn't respond after 60s, opening anyway..."
        break
    fi
    sleep 1
done

echo "    Opening browser tabs..."
xdg-open "http://localhost:${FRONTEND_PORT}" >/dev/null 2>&1 &
xdg-open "http://localhost:${BACKEND_PORT}/docs" >/dev/null 2>&1 &

echo ""
echo "============================================"
echo " TraceNetX v2.0 is up"
echo "   Neo4j Browser : http://localhost:${HTTP_PORT}"
echo "   Backend /docs : http://localhost:${BACKEND_PORT}/docs"
echo "   Frontend      : http://localhost:${FRONTEND_PORT}"
echo " Logs: /tmp/tracenetx-backend.log, /tmp/tracenetx-frontend.log"
echo " Press Ctrl+C to stop backend + frontend (Neo4j container stays up)"
echo "============================================"
echo ""

wait "$BACKEND_PID" "$FRONTEND_PID"
