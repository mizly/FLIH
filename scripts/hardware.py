#!/usr/bin/env python3
"""Start and stop FLIH's hardware bridges: drive, cameras, LiDAR.

The Python counterpart to scripts/hardware.sh. Same three services, same log
directory, same stop order, so the two can be used interchangeably and neither
loses track of what the other started.

    scripts/hardware.py check                # preflight only, starts nothing
    scripts/hardware.py run                  # foreground, interleaved logs, Ctrl-C stops
    scripts/hardware.py run lidar -- --demo  # one service, extra args passed through
    scripts/hardware.py start                # detached, like hardware.sh start
    scripts/hardware.py status
    scripts/hardware.py logs lidar
    scripts/hardware.py stop

These are three separate processes on purpose: video is bulk traffic, driving is
latency-critical, and a wedged camera must not be able to take the motors down.
The reasoning is at the top of backend/camera_stream.py.

The web app is NOT started here, the same way hardware.sh leaves it alone. Every
bridge needs one to authenticate against; `check` probes whichever one is
configured and says what it found.

ROBOT_WS_BASE picks the server, defaulting to DEFAULT_WS below:

    ROBOT_WS_BASE=ws://127.0.0.1:3000 scripts/hardware.py check   # local npm run dev
    ROBOT_WS_BASE=wss://www.flih.help scripts/hardware.py check   # deployed

A remote server only works if it is running server.mjs, the custom Node server that
owns every /ws/* endpoint. A host that merely builds the Next app serves the pages
and 404s the sockets - `check` names that case specifically.

Stop order is load-bearing. The drive bridge goes down first and gets its own grace
period, because the motor board holds its last speed until something overwrites it:
a bridge that is SIGKILLed mid-drive leaves the wheels turning. Only the relay's
500 ms dead-man would catch that, and only on the serial transport.
"""

import argparse
import errno
import http.client
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
RUN_DIR = ROOT / ".data" / "hardware"

# name -> backend module. The short name is what you type; the module is what runs
# and what a running process is identified by, so hardware.sh sees the same thing.
SERVICES = {
    "robot": "robot_websocket",
    "camera": "camera_stream",
    "lidar": "lidar_stream",
}
# Sensors first, motors last: nothing can be commanded to move before there is a
# scan to see it with.
START_ORDER = ["lidar", "camera", "robot"]
STOP_ORDER = ["robot", "camera", "lidar"]

GRACE_S = 5.0        # How long SIGTERM gets before SIGKILL.
STARTUP_CHECK_S = 3.0  # How long to watch a detached child before calling it started.

DEFAULT_WS = "ws://localhost:3000"


# --------------------------------------------------------------------------- env


def load_env():
    """Read scripts/.env into os.environ without python-dotenv.

    Nothing under backend/ loads it: robot_websocket.py and the two publishers read
    os.environ directly, so ROBOT_API_KEY has to be in the environment before they
    start or they raise on import. The file accepts normal dotenv assignments and
    shell-style ``export NAME=value`` lines. Existing variables win, so a one-off
    export on the command line still overrides the file.
    """
    path = Path(__file__).resolve().with_name(".env")
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        os.environ.setdefault(key, value)


def find_pico_port():
    """The Pico 2's stable by-id path, falling back to the ACM index.

    backend/README.md is emphatic about this: the ttyACM number moves when the Pico
    re-enumerates and the bridge does not survive its port disappearing.
    """
    by_id = sorted(Path("/dev/serial/by-id").glob("usb-MicroPython_Board_in_FS_mode_*-if00")) \
        if Path("/dev/serial/by-id").is_dir() else []
    return str(by_id[0]) if by_id else "/dev/ttyACM0"


def prepare_env():
    """The environment all three bridges share."""
    load_env()
    base = os.environ.get("ROBOT_WS_BASE", DEFAULT_WS).rstrip("/")
    # Each publisher derives its own endpoint from ROBOT_WS_URL when its specific
    # variable is unset, but setting all three keeps `check` honest about what the
    # children will actually dial.
    os.environ.setdefault("ROBOT_WS_URL", base + "/ws/robot")
    os.environ.setdefault("ROBOT_CAMERA_WS_URL", base + "/ws/camera")
    os.environ.setdefault("ROBOT_LIDAR_WS_URL", base + "/ws/lidar")
    os.environ.setdefault("ROBOT_TRANSPORT", "serial")
    os.environ.setdefault("ROBOT_SERIAL_PORT", find_pico_port())


# ----------------------------------------------------------------------- process


def running_pid(name):
    """PID of a running bridge, or None.

    Reads /proc rather than shelling out to pgrep so a process started by
    hardware.sh, by hand, or by an earlier run of this script is all found the same
    way - the identity is the command line, not a pidfile we happen to own.

    Matching is per argument, and the interpreter has to look like Python. A plain
    substring search over the whole command line - which is also what `pgrep -f`
    does - matches any shell whose `-c` text happens to mention the path, so
    `bash -c '... backend/lidar_stream.py ...'` reads as the bridge itself. Stopping
    that "bridge" kills the shell and leaves the real process running.
    """
    script = "backend/%s.py" % SERVICES[name]
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit() or int(entry.name) == os.getpid():
            continue
        try:
            raw = (entry / "cmdline").read_bytes()
        except OSError:
            continue  # Exited between listing and reading; not our process.
        args = [a for a in raw.decode("utf-8", "replace").split("\0") if a]
        if not args or "python" not in Path(args[0]).name:
            continue
        if any(a == script or a.endswith("/" + script) for a in args[1:]):
            return int(entry.name)
    return None


def alive(pid):
    """True while the process is still running.

    A zombie is not alive. `run` mode's children are ours, so between their exit and
    being reaped they keep a PID that os.kill(pid, 0) happily accepts - which reads
    as "ignored SIGTERM" and earns a pointless SIGKILL and a scary message about the
    motors. Read the state out of /proc/<pid>/stat instead.
    """
    try:
        os.kill(pid, 0)
    except OSError as error:
        return error.errno == errno.EPERM
    try:
        stat = (Path("/proc") / str(pid) / "stat").read_text()
        # The comm field is parenthesised and may itself contain spaces, so the
        # state is the first field after the closing parenthesis, not stat[2].
        return stat[stat.rindex(")") + 2] != "Z"
    except (OSError, ValueError, IndexError):
        return False


def log_path(name):
    return RUN_DIR / ("%s.log" % SERVICES[name])


def tail(path, lines=12):
    try:
        return path.read_text(errors="replace").splitlines()[-lines:]
    except OSError:
        return []


def stop_one(name, grace=GRACE_S):
    """SIGTERM, wait out the grace period, SIGKILL only as a last resort."""
    pid = running_pid(name)
    if pid is None:
        print("  %-9s not running" % name)
        return True

    os.kill(pid, signal.SIGTERM)
    deadline = time.monotonic() + grace
    while time.monotonic() < deadline:
        if not alive(pid):
            print("  %-9s stopped (pid %d)" % (name, pid))
            return True
        time.sleep(0.1)

    os.kill(pid, signal.SIGKILL)
    print("  %-9s did not exit on SIGTERM, killed (pid %d)" % (name, pid))
    if name == "robot":
        print("           ! a killed drive bridge may leave the motors asserted;"
              " check the wheels")
    return False


def stop_all(names=None):
    for name in [n for n in STOP_ORDER if n in (names or SERVICES)]:
        stop_one(name)
        # The drive bridge releases the motors on its way out. Give that a clear
        # moment of its own rather than racing it against two camera teardowns.
        if name == "robot":
            time.sleep(0.5)


# ---------------------------------------------------------------------- preflight


def ws_endpoint(url):
    """(secure, host, port, path) for a ws:// or wss:// URL."""
    parts = urlsplit(url)
    secure = parts.scheme == "wss"
    return secure, parts.hostname, parts.port or (443 if secure else 80), parts.path or "/"


def probe_endpoint(url, timeout=6.0):
    """Ask the server about a WebSocket path. Returns (ok, description).

    Sends the upgrade headers but deliberately **no** Authorization header. A
    successful upgrade would register this probe as the robot or as a publisher and
    bump the real bridge off its socket, so the healthy answer we want back is a
    refusal: 401 means the endpoint is there and enforcing the key.

    The statuses that matter, all of which this has actually returned:

      401  endpoint present, auth enforced - this is success
      404  nothing serving that path. The /ws/* endpoints live in server.mjs, the
           custom Node server; a platform that only builds the Next app (Vercel and
           other serverless hosts) cannot run it and cannot hold a socket open.
      3xx  a redirect. websocket-client follows it, gets an https:// Location and
           dies with "scheme https is invalid", because it will not turn that back
           into wss://. An apex domain redirecting to www does exactly this.
    """
    secure, host, port, path = ws_endpoint(url)
    if not host:
        return False, "unparseable URL %r" % url

    headers = {"Connection": "Upgrade", "Upgrade": "websocket",
               "Sec-WebSocket-Version": "13",
               "Sec-WebSocket-Key": "dGhlIHNhbXBsZSBub25jZQ=="}
    try:
        if secure:
            connection = http.client.HTTPSConnection(host, port, timeout=timeout)
        else:
            connection = http.client.HTTPConnection(host, port, timeout=timeout)
        connection.request("GET", path, headers=headers)
        response = connection.getresponse()
        status, location = response.status, response.getheader("Location")
        connection.close()
    except (OSError, http.client.HTTPException) as error:
        return False, "cannot reach %s:%d (%s)" % (host, port, type(error).__name__)

    if status in (101, 401, 403):
        return True, "reachable (HTTP %d)" % status
    if status in (301, 302, 303, 307, 308):
        canonical = location or "?"
        hint = ""
        if location:
            redirected = urlsplit(location)
            if redirected.scheme in ("http", "https"):
                hint = ("; point ROBOT_WS_BASE at %s://%s instead"
                        % ("wss" if redirected.scheme == "https" else "ws",
                           redirected.netloc))
        return False, ("HTTP %d redirect to %s - websocket-client cannot follow a "
                       "redirect into an https:// URL%s" % (status, canonical, hint))
    if status == 404:
        return False, ("HTTP 404 - no WebSocket endpoint there. /ws/* is served by "
                       "server.mjs, which a serverless host does not run")
    return False, "HTTP %d" % status


def find_scanner():
    """Whatever backend/lidar.py's autodetect would land on, for reporting only."""
    if Path("/dev/ydlidar").exists():
        return "/dev/ydlidar"
    ports = sorted(Path("/dev").glob("ttyUSB*"))
    return str(ports[0]) if ports else None


def check(verbose=True):
    """Everything that has actually gone wrong here at least once. Returns (ok, fatal)."""
    import importlib.util

    problems, warnings = [], []

    if not os.environ.get("ROBOT_API_KEY", "").strip():
        problems.append("ROBOT_API_KEY is empty - every bridge will fail to authenticate")

    # Probe whatever the bridges will actually dial, not a hardcoded localhost.
    # Each service has its own endpoint and they can fail independently, so ask
    # about all three rather than inferring two of them from one.
    endpoints = {}
    for name, variable in (("lidar", "ROBOT_LIDAR_WS_URL"),
                           ("camera", "ROBOT_CAMERA_WS_URL"),
                           ("robot", "ROBOT_WS_URL")):
        url = os.environ[variable]
        ok, detail = probe_endpoint(url)
        endpoints[name] = (url, ok, detail)
        if not ok:
            problems.append("%s endpoint %s: %s" % (name, url, detail))

    # Declared in backend/requirements.txt, but a missing one is an import-time
    # crash in a detached child, which otherwise just looks like "it didn't start".
    # httpx in particular is pulled in unconditionally by lidar_stream ->
    # omni_fusion -> classification, even though OMNI itself is optional.
    for module, why in (("serial", "pyserial, the motor board and the scanner"),
                        ("websocket", "websocket-client, all three bridges"),
                        ("httpx", "lidar_stream imports it via omni_fusion"),
                        ("cv2", "camera_stream encodes frames with it")):
        if importlib.util.find_spec(module) is None:
            problems.append("python module %r is missing (%s) - "
                            "pip3 install --user -r backend/requirements.txt" % (module, why))

    port = os.environ["ROBOT_SERIAL_PORT"]
    if not Path(port).exists():
        problems.append("%s is missing - is the Pico 2 plugged in?" % port)
    elif not port.startswith("/dev/serial/by-id/"):
        warnings.append("%s is an index that moves across re-enumeration; the by-id "
                        "path is steadier" % port)

    scanner = find_scanner()
    if scanner is None:
        problems.append("no LiDAR port found - no /dev/ydlidar and no /dev/ttyUSB*")
    elif scanner != "/dev/ydlidar":
        warnings.append("scanner autodetects to %s; without the vendor udev rules "
                        "that name moves between reboots (see hardware/Jetson NANO/"
                        "lidar/README.md)" % scanner)

    videos = sorted(Path("/dev").glob("video*"))
    if not videos:
        problems.append("no /dev/video* devices - is a camera overlay enabled?")
    elif len(videos) < 2:
        warnings.append("only %d /dev/video* device; camera_stream expects two CSI "
                        "sensors" % len(videos))

    if verbose:
        for name in ("robot", "camera", "lidar"):
            url, ok, detail = endpoints[name]
            print("%-9s %-34s %s" % (name, url, "OK - " + detail if ok else detail))
        print("Drive port    %s" % port)
        print("Scanner       %s" % (scanner or "not found"))
        print("Cameras       %s" % (", ".join(v.name for v in videos) or "none"))
        print("Transport     %s" % os.environ["ROBOT_TRANSPORT"])
        for warning in warnings:
            print("warning: %s" % warning)
        for problem in problems:
            print("PROBLEM: %s" % problem)
        if not problems:
            print("\nPreflight clean.")

    return not problems


# ------------------------------------------------------------------------ actions


def do_start(names, extra):
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    check(verbose=False) or print("(preflight found problems; run `check` for detail)")

    started = []
    for name in [n for n in START_ORDER if n in names]:
        pid = running_pid(name)
        if pid is not None:
            print("  %-9s already running (pid %d)" % (name, pid))
            continue
        path = log_path(name)
        with open(path, "wb") as handle:
            process = subprocess.Popen(
                [sys.executable, "-u", "backend/%s.py" % SERVICES[name], *extra],
                cwd=ROOT, stdout=handle, stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL, start_new_session=True,
            )
        print("  %-9s started (pid %d) -> %s"
              % (name, process.pid, path.relative_to(ROOT)))
        started.append((name, process))

    # A bridge that dies on an import error or a missing key exits within a second,
    # and a detached child's failure is otherwise invisible until someone reads a log.
    if started:
        time.sleep(STARTUP_CHECK_S)
        for name, process in started:
            if process.poll() is not None:
                print("\n  %s EXITED with code %d:" % (name, process.returncode))
                for line in tail(log_path(name)):
                    print("      %s" % line)


def do_run(names, extra):
    """Foreground: interleave the children's output, stop them all on Ctrl-C."""
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    for name in names:
        pid = running_pid(name)
        if pid is not None:
            print("%s is already running (pid %d). Stop it first." % (name, pid))
            return 1

    if not check(verbose=True):
        print("\nRefusing to start with the problems above. Use `start` to override.")
        return 1

    processes = {}
    for name in [n for n in START_ORDER if n in names]:
        processes[name] = subprocess.Popen(
            [sys.executable, "-u", "backend/%s.py" % SERVICES[name], *extra],
            cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL, text=True, bufsize=1,
        )
        print("  %-9s pid %d" % (name, processes[name].pid))

    def pump(name, process):
        # Mirror to the same log file the detached path writes, so `logs` works
        # afterwards either way.
        with open(log_path(name), "w") as handle:
            for line in process.stdout:
                sys.stdout.write("[%-6s] %s" % (name, line))
                handle.write(line)
                handle.flush()

    threads = [threading.Thread(target=pump, args=(name, process), daemon=True)
               for name, process in processes.items()]
    for thread in threads:
        thread.start()

    print("\nRunning. Ctrl-C to stop.\n")
    try:
        while any(process.poll() is None for process in processes.values()):
            for name, process in processes.items():
                if process.poll() is not None and process.returncode != 0:
                    print("\n[%s] exited with code %d" % (name, process.returncode))
                    processes[name].returncode = 0  # Report it once, then keep going.
            time.sleep(0.3)
        print("\nAll services exited.")
    except KeyboardInterrupt:
        print("\nStopping (drive bridge first)...")
    finally:
        stop_all(set(processes))
        # Reap them, so nothing is left as a zombie holding a PID.
        for process in processes.values():
            try:
                process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                pass
    return 0


def do_status():
    for name in START_ORDER:
        pid = running_pid(name)
        if pid is None:
            print("  %-9s down" % name)
            continue
        try:
            elapsed = subprocess.run(["ps", "-p", str(pid), "-o", "etime="],
                                     capture_output=True, text=True).stdout.strip()
        except OSError:
            elapsed = "?"
        print("  %-9s up   (pid %d, %s)" % (name, pid, elapsed))
    url = os.environ["ROBOT_WS_URL"]
    ok, detail = probe_endpoint(url)
    print("\n  %-9s %s  %s" % ("web app", url, "up - " + detail if ok else detail))


def do_logs(names, follow):
    paths = [log_path(n) for n in names if log_path(n).exists()]
    if not paths:
        print("No logs yet in %s" % RUN_DIR)
        return
    if follow:
        subprocess.run(["tail", "-n", "40", "-f", *[str(p) for p in paths]])
        return
    for path in paths:
        print("==> %s <==" % path.relative_to(ROOT))
        for line in tail(path, 15):
            print(line)
        print()


# --------------------------------------------------------------------------- cli


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("action",
                        choices=["run", "start", "stop", "restart", "status", "logs", "check"],
                        nargs="?", default="status")
    parser.add_argument("services", nargs="*", default=None,
                        help="robot, camera, lidar (default: all three)")
    parser.add_argument("-f", "--follow", action="store_true", help="logs: follow")
    parser.epilog = ("anything after `--` is passed to the named service, e.g.\n"
                     "  scripts/hardware.py run lidar -- --demo")

    # Split on `--` by hand. argparse.REMAINDER cannot do this next to a nargs="*"
    # positional: the service list swallows `--` and everything after it.
    argv = list(sys.argv[1:] if argv is None else argv)
    extra = []
    if "--" in argv:
        split = argv.index("--")
        argv, extra = argv[:split], argv[split + 1:]
    args = parser.parse_args(argv)

    unknown = [s for s in args.services if s not in SERVICES]
    if unknown:
        parser.error("unknown service(s): %s (choose from %s)"
                     % (", ".join(unknown), ", ".join(SERVICES)))
    names = set(args.services) if args.services else set(SERVICES)

    if extra and len(names) != 1:
        parser.error("extra arguments need exactly one service, got %d" % len(names))

    prepare_env()

    if args.action == "check":
        return 0 if check() else 1
    if args.action == "run":
        return do_run(names, extra)
    if args.action == "start":
        do_start(names, extra)
    elif args.action == "stop":
        stop_all(names)
    elif args.action == "restart":
        stop_all(names)
        do_start(names, extra)
    elif args.action == "status":
        do_status()
    elif args.action == "logs":
        do_logs([n for n in START_ORDER if n in names], args.follow)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
