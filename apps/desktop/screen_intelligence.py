import base64
import hashlib
import io
import os
import re
import time
import json
import psutil
from datetime import datetime, timezone
from pathlib import Path

import httpx

try:
    import mss
    from PIL import Image
except Exception:
    mss = None
    Image = None

try:
    import pytesseract
except Exception:
    pytesseract = None


CATEGORY_RULES = {
    "coding": ["visual studio", "vs code", "pycharm", "intellij", "github", "gitlab", "code", "debug", "terminal", "python", "javascript", "typescript", "react", "fastapi", "npm", "pip"],
    "research": ["search", "google", "bing", "documentation", "docs", "stackoverflow", "wikipedia", "arxiv", "research", "reference"],
    "communication": ["discord", "slack", "teams", "whatsapp", "telegram", "chat", "message", "mail", "gmail", "outlook"],
    "learning": ["course", "tutorial", "lecture", "udemy", "coursera", "learn", "lesson", "assignment"],
    "design": ["figma", "photoshop", "illustrator", "canva", "blender", "unity", "design", "prototype"],
    "entertainment": ["youtube", "netflix", "spotify", "twitch", "steam", "movie", "music", "game"],
    "file_management": ["file explorer", "explorer", "downloads", "documents", "onedrive", "folder"],
    "meeting": ["zoom", "meet", "teams meeting", "webex", "meeting", "call"],
}

DEFAULT_SENSITIVE = [
    "1password", "bitwarden", "keepass", "lastpass", "password", "bank", "banking",
    "wallet", "paytm", "phonepe", "googlepay", "gpay", "upi", "otp", "authenticator",
    "incognito", "private browsing", "private window", "login", "signin", "sign in",
]


def _now():
    return datetime.now(timezone.utc).isoformat()


def _windows_title():
    if os.name != "nt":
        return ""
    try:
        import ctypes
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return ""
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return ""
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        return buf.value[:300]
    except Exception:
        return ""


def _active_process():
    if os.name != "nt":
        return ""
    try:
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return ""
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if not pid.value:
            return ""
        handle = kernel32.OpenProcess(0x1000, False, pid.value)
        if not handle:
            return ""
        try:
            size = wintypes.DWORD(1024)
            buf = ctypes.create_unicode_buffer(size.value)
            if kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
                return Path(buf.value).name[:160]
        finally:
            kernel32.CloseHandle(handle)
    except Exception:
        return ""
    return ""


def _sensitive(text, custom):
    hay = (text or "").lower()
    terms = [x.strip().lower() for x in custom.split(",") if x.strip()] or DEFAULT_SENSITIVE
    return any(term in hay for term in terms)


def _classify(text):
    hay = (text or "").lower()
    scores = {category: sum(1 for token in tokens if token in hay) for category, tokens in CATEGORY_RULES.items()}
    category, score = max(scores.items(), key=lambda x: x[1]) if scores else ("unknown", 0)
    if score == 0:
        return "unknown", 0.2, []
    matched = [token for token in CATEGORY_RULES[category] if token in hay][:8]
    confidence = min(0.95, 0.42 + score * 0.10)
    return category, round(confidence, 2), matched


def _ocr(image):
    if not pytesseract or image is None:
        return ""
    try:
        # Downscale to keep OCR cheap. Do not persist the image.
        w, h = image.size
        if w > 1600:
            image = image.resize((1600, int(h * 1600 / w)))
        text = pytesseract.image_to_string(image, config="--psm 6", timeout=8)
        return re.sub(r"\s+", " ", text).strip()[:3000]
    except Exception:
        return ""


def _vision_summary(image_bytes, url, model):
    if not image_bytes or not url or not model:
        return None
    try:
        encoded = base64.b64encode(image_bytes).decode("ascii")
        prompt = (
            "Analyze this desktop screenshot locally. Do not reproduce sensitive text, credentials, "
            "messages, URLs, names, or private data. Return only JSON with keys "
            "activity_category and short_summary. Categories: coding, research, communication, "
            "learning, design, entertainment, file_management, meeting, unknown. "
            "The summary must be generic and under 12 words."
        )
        with httpx.Client(timeout=25) as client:
            r = client.post(f"{url.rstrip('/')}/api/chat", json={
                "model": model,
                "stream": False,
                "format": "json",
                "messages": [{"role": "user", "content": prompt, "images": [encoded]}],
                "options": {"temperature": 0.1},
            })
            r.raise_for_status()
            data = r.json()
            raw = data.get("message", {}).get("content", "")
            obj = json.loads(raw)
            return {
                "category": str(obj.get("activity_category", "unknown"))[:40],
                "summary": str(obj.get("short_summary", ""))[:120],
            }
    except Exception:
        return None


def _resize_for_analysis(image, max_width, max_height):
    """Bound screen inference cost while preserving aspect ratio."""
    if image is None:
        return None
    width, height = image.size
    scale = min(1.0, max_width / max(1, width), max_height / max(1, height))
    if scale >= 0.999:
        return image
    return image.resize((max(1, int(width * scale)), max(1, int(height * scale))), Image.Resampling.LANCZOS)


def _system_allows_vision(max_cpu, max_memory):
    try:
        cpu = psutil.cpu_percent(interval=None)
        memory = psutil.virtual_memory().percent
        return cpu <= max_cpu and memory <= max_memory, cpu, memory
    except Exception:
        return True, None, None


class ScreenIntelligence:
    """Privacy-first screen context collector.

    Screenshots are processed in memory and never written to disk. Only structured
    activity metadata is emitted. Optional local Ollama vision is opt-in.
    """
    def __init__(self):
        self.enabled = os.getenv("SCREEN_INTELLIGENCE_ENABLED", "true").lower() == "true"
        self.interval = max(30, int(os.getenv("SCREEN_INTELLIGENCE_INTERVAL", "60")))
        self.ocr_enabled = os.getenv("SCREEN_OCR_ENABLED", "true").lower() == "true"
        self.ai_enabled = os.getenv("SCREEN_AI_ENABLED", "false").lower() == "true"
        self.ollama_url = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
        self.vision_model = os.getenv("SCREEN_AI_MODEL", "qwen2.5vl:7b")
        self.sensitive = os.getenv("SCREEN_SENSITIVE_TERMS", "")
        self.max_width = max(640, int(os.getenv("SCREEN_MAX_WIDTH", "1280")))
        self.max_height = max(360, int(os.getenv("SCREEN_MAX_HEIGHT", "720")))
        self.process_timeout = max(5, int(os.getenv("SCREEN_PROCESS_TIMEOUT", "10")))
        self.ai_cooldown = max(60, int(os.getenv("SCREEN_AI_COOLDOWN", "120")))
        self.ai_max_cpu = max(30.0, min(95.0, float(os.getenv("SCREEN_AI_MAX_SYSTEM_CPU", "70"))))
        self.ai_max_memory = max(50.0, min(98.0, float(os.getenv("SCREEN_AI_MAX_SYSTEM_MEMORY", "88"))))
        self.ai_on_context_change = os.getenv("SCREEN_AI_ON_CONTEXT_CHANGE", "true").lower() == "true"
        self.last_capture = 0.0
        self.last_signature = None
        self.last_ai_at = 0.0
        self.last_ai_context = None
        self.sct = None

    def capture(self):
        if not self.enabled or os.name != "nt" or mss is None or Image is None:
            return None
        now = time.time()
        if now - self.last_capture < self.interval:
            return None
        self.last_capture = now
        process = _active_process()
        title = _windows_title()
        context = f"{process} {title}"
        if _sensitive(context, self.sensitive):
            return {
                "device_context": "sensitive_window",
                "process": process,
                "category": "protected",
                "confidence": 0.99,
                "signals": ["screen_analysis_paused_sensitive_window"],
                "timestamp": _now(),
            }
        try:
            if self.sct is None:
                self.sct = mss.mss()
            monitor = self.sct.monitors[1]
            shot = self.sct.grab(monitor)
            image = Image.frombytes("RGB", shot.size, shot.rgb)
            image = _resize_for_analysis(image, self.max_width, self.max_height)
            # Small JPEG in memory; never written to disk.
            buf = io.BytesIO()
            image.save(buf, format="JPEG", quality=45, optimize=True)
            image_bytes = buf.getvalue()
            signature = hashlib.sha256(image_bytes[: min(len(image_bytes), 120000)]).hexdigest()[:16]
            if signature == self.last_signature:
                return None
            self.last_signature = signature

            ocr_text = _ocr(image) if self.ocr_enabled else ""
            combined = f"{process} {title} {ocr_text}"
            category, confidence, signals = _classify(combined)

            vision = None
            vision_status = "disabled"
            context_key = f"{process}|{category}"
            if self.ai_enabled:
                vision_status = "cooldown"
                now_ts = time.time()
                context_changed = context_key != self.last_ai_context
                cooldown_ok = now_ts - self.last_ai_at >= self.ai_cooldown
                resource_ok, cpu_now, memory_now = _system_allows_vision(self.ai_max_cpu, self.ai_max_memory)
                should_run = cooldown_ok and (context_changed or not self.ai_on_context_change) and resource_ok
                if should_run:
                    vision_status = "running"
                    vision = _vision_summary(image_bytes, self.ollama_url, self.vision_model)
                    self.last_ai_at = now_ts
                    self.last_ai_context = context_key
                    if vision is not None:
                        vision_status = "used"
                    else:
                        vision_status = "failed"
                elif not resource_ok:
                    vision_status = "deferred_resource_pressure"
                elif self.ai_on_context_change and not context_changed:
                    vision_status = "deferred_same_context"
                else:
                    vision_status = "deferred_cooldown"

            if vision and vision.get("category"):
                category = vision["category"]
                confidence = max(confidence, 0.62)
            if vision and vision.get("summary"):
                signals.append("local_vision")

            return {
                "device_context": "screen_context",
                "process": process,
                "category": category,
                "confidence": confidence,
                "signals": signals[:10],
                "window_app_hint": process[:100],
                "vision_summary": vision.get("summary") if vision else None,
                "vision_status": vision_status,
                "timestamp": _now(),
                "privacy": {
                    "screenshot_stored": False,
                    "raw_ocr_stored": False,
                    "cloud_upload": False,
                },
            }
        except Exception as exc:
            return {"device_context": "error", "category": "unknown", "confidence": 0.0, "signals": [f"capture_error:{type(exc).__name__}"], "timestamp": _now()}
