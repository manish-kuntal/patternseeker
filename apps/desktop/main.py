import hashlib
import os
import platform
import socket
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
from dotenv import load_dotenv

from hardware import collect_system_metrics
from screen_intelligence import ScreenIntelligence

load_dotenv()

API = os.getenv("PATTERN_API", "http://127.0.0.1:8000")
KEY = os.getenv("PATTERN_KEY", "change-me")
DEVICE_ID = os.getenv("DEVICE_ID", socket.gethostname())
DEVICE_NAME = os.getenv("DEVICE_NAME", socket.gethostname())

# Lightweight foreground-app sampling. Project/Git scans happen much less often.
POLL_SECONDS = max(10, int(os.getenv("POLL_SECONDS", "30")))
PROJECT_SCAN_SECONDS = max(60, int(os.getenv("PROJECT_SCAN_SECONDS", "300")))
FILE_SCAN_SECONDS = max(60, int(os.getenv("FILE_SCAN_SECONDS", "180")))
GIT_SCAN_SECONDS = max(60, int(os.getenv("GIT_SCAN_SECONDS", "300")))
SYSTEM_POLL_SECONDS = max(10, int(os.getenv("SYSTEM_POLL_SECONDS", "15")))
AUTO_DISCOVER = os.getenv("AUTO_DISCOVER", "true").lower() == "true"
MAX_DEPTH = max(1, int(os.getenv("MAX_DEPTH", "3")))

DEFAULT_ROOTS = [
    Path.home() / "Desktop",
    Path.home() / "Documents",
    Path.home() / "Downloads",
    Path.home() / "source",
    Path.home() / "projects",
]

CODE_EXTENSIONS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".c", ".cpp",
    ".cs", ".go", ".rs", ".php", ".html", ".css", ".scss",
    ".dart", ".sql", ".json", ".md"
}

IGNORE_DIRS = {
    ".git", "node_modules", ".venv", "venv", "__pycache__",
    "dist", "build", ".next", ".idea", ".vscode", ".gradle",
    "target", "coverage", "vendor", "Pods"
}

last_file_event = {}
last_commit = {}
last_discovered_projects = set()
current_app = None
current_app_started = None
last_app_sample = None
projects_cache = []
last_project_scan = 0.0
last_file_scan = 0.0
last_git_scan = 0.0
last_system_poll = 0.0
screen_intelligence = ScreenIntelligence()


def now():
    return datetime.now(timezone.utc).isoformat()


def set_low_priority():
    """Keep the collector below normal Windows priority so it cannot easily starve the UI."""
    if platform.system() != "Windows":
        return
    try:
        import ctypes
        BELOW_NORMAL_PRIORITY_CLASS = 0x00004000
        handle = ctypes.windll.kernel32.GetCurrentProcess()
        ctypes.windll.kernel32.SetPriorityClass(handle, BELOW_NORMAL_PRIORITY_CLASS)
        print("[resource] Windows priority=BELOW_NORMAL")
    except Exception as exc:
        print(f"[resource] priority unchanged: {exc}")


def send(client, event):
    try:
        r = client.post(
            f"{API}/api/events",
            json=event,
            headers={"X-Pattern-Key": KEY},
            timeout=5,
        )
        r.raise_for_status()
        return True
    except Exception as exc:
        print(f"[sync] {exc}")
        return False


def register(client):
    r = client.post(
        f"{API}/api/devices",
        json={
            "device_id": DEVICE_ID,
            "name": DEVICE_NAME,
            "platform": platform.system(),
        },
        timeout=5,
    )
    r.raise_for_status()


def configured_roots():
    """Use explicitly configured roots. Defaults are only used when PROJECT_ROOTS is empty."""
    raw = os.getenv("PROJECT_ROOTS", "").strip()
    if raw:
        roots = [Path(x.strip()) for x in raw.split(";") if x.strip()]
    else:
        roots = DEFAULT_ROOTS

    unique = []
    seen = set()
    for p in roots:
        try:
            p = p.expanduser().resolve()
        except Exception:
            continue
        key = str(p).lower()
        if key not in seen and p.exists():
            seen.add(key)
            unique.append(p)
    return unique


def is_project_dir(path: Path):
    try:
        return (
            (path / ".git").exists()
            or (path / "package.json").exists()
            or (path / "pyproject.toml").exists()
            or (path / "requirements.txt").exists()
            or (path / "pubspec.yaml").exists()
            or (path / "pom.xml").exists()
            or (path / "Cargo.toml").exists()
        )
    except Exception:
        return False


def discover_projects():
    """Bounded discovery. This is intentionally NOT called on every app sample."""
    found = []
    seen = set()

    for root in configured_roots():
        if is_project_dir(root):
            candidates = [root]
        else:
            candidates = []
            try:
                for current, dirs, files in os.walk(root):
                    current_path = Path(current)
                    try:
                        depth = len(current_path.relative_to(root).parts)
                    except ValueError:
                        continue

                    dirs[:] = [
                        d for d in dirs
                        if d not in IGNORE_DIRS and not d.startswith(".")
                    ]

                    if depth >= MAX_DEPTH:
                        dirs[:] = []

                    if is_project_dir(current_path):
                        candidates.append(current_path)
                        # Do not recursively scan inside an identified project.
                        dirs[:] = []
            except (PermissionError, OSError):
                continue

        for p in candidates:
            key = str(p).lower()
            if key not in seen:
                seen.add(key)
                found.append(p)

    return found


def active_app():
    """Return foreground Windows process name only. No title, URL or content."""
    if platform.system() != "Windows":
        return None
    try:
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return None
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if not pid.value:
            return None
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
        if not handle:
            return None
        try:
            size = wintypes.DWORD(1024)
            buffer = ctypes.create_unicode_buffer(size.value)
            if kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
                return Path(buffer.value).name[:255]
        finally:
            kernel32.CloseHandle(handle)
    except Exception:
        return None
    return None


IGNORED_APPS = {
    "python.exe", "pythonw.exe", "cmd.exe", "conhost.exe",
    "powershell.exe", "pwsh.exe",
}


def application_usage_event(app_name, started_at, duration_seconds):
    if not app_name or app_name.lower() in IGNORED_APPS or duration_seconds <= 0:
        return None
    return {
        "device_id": DEVICE_ID,
        "event_type": "application_usage",
        "source": "windows",
        "timestamp": now(),
        "application": app_name,
        "duration_seconds": round(float(duration_seconds), 1),
        "metadata": {
            "session_started_at": started_at,
            "tracking": "foreground_process_only",
        },
    }


def track_active_app(client, app_name):
    global current_app, current_app_started, last_app_sample
    sampled_at = time.time()
    normalized = app_name if app_name and app_name.lower() not in IGNORED_APPS else None

    if current_app is None:
        current_app = normalized
        current_app_started = sampled_at if normalized else None
        last_app_sample = sampled_at
        return

    elapsed = sampled_at - (last_app_sample or sampled_at)
    previous_app = current_app
    previous_started = current_app_started

    if previous_app and elapsed >= 1:
        event = application_usage_event(
            previous_app,
            datetime.fromtimestamp(previous_started, tz=timezone.utc).isoformat(),
            elapsed,
        )
        if event:
            send(client, event)

    if normalized != previous_app:
        current_app = normalized
        current_app_started = sampled_at if normalized else None

    last_app_sample = sampled_at


def project_discovery_event(project: Path):
    key = str(project).lower()
    if key in last_discovered_projects:
        return None
    last_discovered_projects.add(key)
    return {
        "device_id": DEVICE_ID,
        "event_type": "project_discovered",
        "source": "filesystem",
        "timestamp": now(),
        "project": project.name,
        "metadata": {
            "path": str(project),
            "git_repository": (project / ".git").exists(),
        },
    }


def latest_git_commit(project: Path):
    try:
        r = subprocess.run(
            ["git", "-C", str(project), "log", "-1", "--format=%H|%cI|%s"],
            capture_output=True,
            text=True,
            timeout=3,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if r.returncode != 0 or not r.stdout.strip():
            return None
        sha, timestamp, subject = r.stdout.strip().split("|", 2)
        return {"sha": sha, "timestamp": timestamp, "subject": subject}
    except Exception:
        return None


def newest_code_file(project: Path):
    """Expensive operation, intentionally run only on FILE_SCAN_SECONDS cadence."""
    newest = None
    try:
        for current, dirs, files in os.walk(project):
            dirs[:] = [
                d for d in dirs
                if d not in IGNORE_DIRS and not d.startswith(".")
            ]
            for name in files:
                path = Path(current) / name
                if path.suffix.lower() not in CODE_EXTENSIONS:
                    continue
                try:
                    stat = path.stat()
                except OSError:
                    continue
                if newest is None or stat.st_mtime > newest[0]:
                    newest = (stat.st_mtime, path)
    except (PermissionError, OSError):
        return None
    return newest


def file_event(project: Path):
    newest = newest_code_file(project)
    if not newest:
        return None
    mtime, path = newest
    age = time.time() - mtime
    if age > max(FILE_SCAN_SECONDS * 1.5, 180):
        return None
    signature = f"{project}|{path}|{mtime}"
    fp = hashlib.sha1(signature.encode()).hexdigest()
    if last_file_event.get(str(project)) == fp:
        return None
    last_file_event[str(project)] = fp
    try:
        relative = str(path.relative_to(project))
    except ValueError:
        relative = path.name
    return {
        "device_id": DEVICE_ID,
        "event_type": "project_activity",
        "source": "filesystem",
        "timestamp": datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat(),
        "project": project.name,
        "metadata": {
            "file_extension": path.suffix.lower(),
            "relative_file": relative[:200],
        },
    }


def git_event(project: Path):
    commit = latest_git_commit(project)
    if not commit:
        return None
    key = f"{project}:{commit['sha']}"
    if last_commit.get(str(project)) == key:
        return None
    last_commit[str(project)] = key
    return {
        "device_id": DEVICE_ID,
        "event_type": "git_commit",
        "source": "git",
        "timestamp": commit["timestamp"],
        "project": project.name,
        "application": "git",
        "metadata": {
            "commit": commit["sha"][:12],
            "message_length": len(commit["subject"]),
        },
    }


def refresh_projects(client, force=False):
    global projects_cache, last_project_scan
    now_ts = time.time()
    if not force and now_ts - last_project_scan < PROJECT_SCAN_SECONDS:
        return projects_cache

    started = time.perf_counter()
    discovered = discover_projects() if AUTO_DISCOVER else configured_roots()
    projects_cache = discovered
    last_project_scan = now_ts

    for project in projects_cache:
        event = project_discovery_event(project)
        if event:
            send(client, event)

    elapsed = time.perf_counter() - started
    print(f"[projects] discovered={len(projects_cache)} scan_time={elapsed:.1f}s next={PROJECT_SCAN_SECONDS}s")
    return projects_cache


def refresh_file_activity(client, projects):
    global last_file_scan
    now_ts = time.time()
    if now_ts - last_file_scan < FILE_SCAN_SECONDS:
        return
    started = time.perf_counter()
    for project in projects:
        event = file_event(project)
        if event:
            send(client, event)
        # Yield briefly so Windows UI stays responsive on large repositories.
        time.sleep(0.02)
    last_file_scan = now_ts
    print(f"[files] checked={len(projects)} elapsed={time.perf_counter() - started:.1f}s next={FILE_SCAN_SECONDS}s")


def refresh_git(client, projects):
    global last_git_scan
    now_ts = time.time()
    if now_ts - last_git_scan < GIT_SCAN_SECONDS:
        return
    started = time.perf_counter()
    for project in projects:
        event = git_event(project)
        if event:
            send(client, event)
        time.sleep(0.02)
    last_git_scan = now_ts
    print(f"[git] checked={len(projects)} elapsed={time.perf_counter() - started:.1f}s next={GIT_SCAN_SECONDS}s")



def system_metrics_event():
    metrics = collect_system_metrics()
    return {
        "device_id": DEVICE_ID,
        "event_type": "system_metrics",
        "source": "windows",
        "timestamp": metrics.get("timestamp", now()),
        "metadata": metrics,
    }


def refresh_system_metrics(client):
    global last_system_poll
    now_ts = time.time()
    if now_ts - last_system_poll < SYSTEM_POLL_SECONDS:
        return
    try:
        event = system_metrics_event()
        if send(client, event):
            last_system_poll = now_ts
            m = event["metadata"]
            cpu = m.get("cpu", {})
            gpu = m.get("gpu", {})
            print(f"[system] CPU={cpu.get('usage_percent')}% {cpu.get('clock_mhz')}MHz | RAM={m.get('memory', {}).get('usage_percent')}% | GPU={gpu.get('utilization_percent', 'n/a')}% {gpu.get('temperature_c', 'n/a')}C")
    except Exception as exc:
        print(f"[system] {exc}")



def refresh_screen_intelligence(client):
    try:
        context = screen_intelligence.capture()
        if not context:
            return
        event = {
            "device_id": DEVICE_ID,
            "event_type": "screen_context",
            "source": "screen_local",
            "timestamp": context.get("timestamp", now()),
            "application": context.get("process") or None,
            "metadata": context,
        }
        if send(client, event):
            category = context.get("category", "unknown")
            confidence = context.get("confidence", 0)
            print(f"[screen] category={category} confidence={confidence} app={context.get('process') or 'unknown'}")
    except Exception as exc:
        print(f"[screen] {exc}")

def main():
    set_low_priority()
    print("===================================")
    print(" PatternSeeker Windows Collector v2.0")
    print("===================================")
    print(f"API: {API}")
    print(f"Device: {DEVICE_ID}")
    print("Privacy mode: metadata only")
    print(f"App poll: {POLL_SECONDS}s | Projects: {PROJECT_SCAN_SECONDS}s | Files: {FILE_SCAN_SECONDS}s | Git: {GIT_SCAN_SECONDS}s | System: {SYSTEM_POLL_SECONDS}s | Screen: {screen_intelligence.interval}s")
    print("Resource mode: low priority / adaptive telemetry")
    print()

    with httpx.Client() as client:
        while True:
            try:
                register(client)

                app = active_app()
                track_active_app(client, app)

                refresh_system_metrics(client)
                refresh_screen_intelligence(client)
                projects = refresh_projects(client)
                refresh_file_activity(client, projects)
                refresh_git(client, projects)

                print(f"[loop] projects={len(projects)} app={app or 'unknown'}")
                time.sleep(POLL_SECONDS)

            except KeyboardInterrupt:
                print("\nPatternSeeker collector stopped.")
                return
            except Exception as exc:
                print(f"[collector] {exc}")
                time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
