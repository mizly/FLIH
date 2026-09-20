#!/usr/bin/env bash
# Start and stop the FLIH hardware bridges (drive, cameras, LiDAR).
#
# These are three separate processes on purpose: video is bulk traffic, driving is
# latency-critical, and a wedged camera must not be able to take the motors down.
# The web server (npm run dev / npm start) is separate and is not touched here.
#
#   scripts/hardware.sh start|stop|restart|status|logs [name]

set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN="$ROOT/.data/hardware"
SERVICES="robot_websocket camera_stream lidar_stream"

cd "$ROOT"
mkdir -p "$RUN"

if [ -f .env ]; then set -a; . ./.env; set +a; fi

: "${ROBOT_WS_URL:=ws://127.0.0.1:3000/ws/robot}"
: "${ROBOT_CAMERA_WS_URL:=ws://127.0.0.1:3000/ws/camera}"
: "${ROBOT_LIDAR_WS_URL:=ws://127.0.0.1:3000/ws/lidar}"
: "${ROBOT_TRANSPORT:=serial}"
export ROBOT_WS_URL ROBOT_CAMERA_WS_URL ROBOT_LIDAR_WS_URL ROBOT_TRANSPORT

# Prefer the stable by-id path: the ttyACM index moves when the Pico re-enumerates
# and the bridge does not survive its port disappearing.
if [ -z "${ROBOT_SERIAL_PORT:-}" ]; then
  for p in /dev/serial/by-id/usb-MicroPython_Board_in_FS_mode_*-if00; do
    [ -e "$p" ] && ROBOT_SERIAL_PORT="$p" && break
  done
fi
export ROBOT_SERIAL_PORT="${ROBOT_SERIAL_PORT:-/dev/ttyACM0}"

pid_of() { pgrep -f "backend/$1.py" | head -1; }

start_one() {
  local name="$1" pid
  pid="$(pid_of "$name")"
  if [ -n "$pid" ]; then printf '  %-17s already running (pid %s)\n' "$name" "$pid"; return; fi
  nohup /usr/bin/python3 -u "backend/$name.py" >"$RUN/$name.log" 2>&1 &
  printf '  %-17s started (pid %s) -> .data/hardware/%s.log\n' "$name" "$!" "$name"
}

# Stop the drive bridge first so the motors are released before anything else goes.
stop_one() {
  local name="$1" pid
  pid="$(pid_of "$name")"
  if [ -z "$pid" ]; then printf '  %-17s not running\n' "$name"; return; fi
  kill -TERM "$pid" 2>/dev/null
  # Real grace period: a SIGKILLed drive bridge may leave the motors asserted.
  for _ in $(seq 1 50); do kill -0 "$pid" 2>/dev/null || break; sleep 0.1; done
  if kill -0 "$pid" 2>/dev/null; then
    kill -KILL "$pid" 2>/dev/null
    printf '  %-17s did not exit on SIGTERM, killed (pid %s)\n' "$name" "$pid"
  else
    printf '  %-17s stopped (pid %s)\n' "$name" "$pid"
  fi
}

case "${1:-status}" in
  start)
    if ! ss -tln 2>/dev/null | grep -q '127.0.0.1:3000'; then
      echo "warning: nothing is listening on 127.0.0.1:3000 - start the web app first (npm run dev)" >&2
    fi
    echo "Serial port: $ROBOT_SERIAL_PORT"
    [ -e "$ROBOT_SERIAL_PORT" ] || echo "warning: $ROBOT_SERIAL_PORT is missing - is the Pico 2 plugged in?" >&2
    [ -n "${ROBOT_API_KEY:-}" ] || echo "warning: ROBOT_API_KEY is empty - the bridges will fail to authenticate" >&2
    for s in $SERVICES; do start_one "$s"; done
    ;;
  stop)
    for s in robot_websocket camera_stream lidar_stream; do stop_one "$s"; done
    ;;
  restart)
    "$0" stop; "$0" start
    ;;
  status)
    for s in $SERVICES; do
      pid="$(pid_of "$s")"
      if [ -n "$pid" ]; then
        printf '  %-17s up   (pid %s, %s)\n' "$s" "$pid" "$(ps -p "$pid" -o etime= | tr -d ' ')"
      else
        printf '  %-17s down\n' "$s"
      fi
    done
    ;;
  logs)
    name="${2:-}"
    if [ -n "$name" ]; then tail -n 40 -f "$RUN/$name.log"; else tail -n 15 "$RUN"/*.log; fi
    ;;
  *)
    echo "usage: scripts/hardware.sh start|stop|restart|status|logs [name]" >&2
    exit 2
    ;;
esac
