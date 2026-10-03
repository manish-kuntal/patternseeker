import hashlib
import json
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from ..models import Event, Pattern

WINDOW_DAYS = 90
MIN_SESSIONS = 5


def confidence(value):
    return round(max(0.0, min(0.99, value)), 2)


def make_fp(pattern_type, title):
    return hashlib.sha256(f"{pattern_type}:{title}".encode()).hexdigest()


def add_pattern(db, pattern_type, title, description, score, evidence):
    fp = make_fp(pattern_type, title)
    p = db.query(Pattern).filter(Pattern.fingerprint == fp).first()
    if p:
        p.description = description
        p.confidence = confidence(score)
        p.evidence_json = json.dumps(evidence, ensure_ascii=False)
        return p, False
    p = Pattern(
        fingerprint=fp,
        pattern_type=pattern_type,
        title=title,
        description=description,
        confidence=confidence(score),
        evidence_json=json.dumps(evidence, ensure_ascii=False),
    )
    db.add(p)
    return p, True


def _aware(ts):
    return ts.replace(tzinfo=timezone.utc) if ts.tzinfo is None else ts


def _event_ts(e):
    return _aware(e.timestamp)


def _app_sessions(app_events):
    """Build lightweight foreground sessions from privacy-safe application samples."""
    sessions = []
    current = None
    start = None
    last = None

    for e in app_events:
        ts = _event_ts(e)
        app = e.application
        if not app:
            continue
        if current != app or (last and ts - last > timedelta(minutes=10)):
            if current and start and last:
                duration = (last - start).total_seconds()
                if 10 <= duration <= 8 * 3600:
                    sessions.append({"application": current, "start": start, "end": last, "seconds": duration})
            current = app
            start = ts
        last = ts

    if current and start and last:
        duration = (last - start).total_seconds()
        if 10 <= duration <= 8 * 3600:
            sessions.append({"application": current, "start": start, "end": last, "seconds": duration})
    return sessions


def detect_patterns(db: Session):
    start = datetime.now(timezone.utc) - timedelta(days=WINDOW_DAYS)
    events = db.query(Event).filter(Event.timestamp >= start).order_by(Event.timestamp.asc()).all()
    if not events:
        return []

    created = []

    # ------------------------------------------------------------------
    # 1. Project lifecycle
    # ------------------------------------------------------------------
    project_days = defaultdict(set)
    first_days = []
    project_activity = defaultdict(int)
    for e in events:
        if e.project and e.event_type in {"project_activity", "git_commit", "file_activity", "project_discovered"}:
            day = _event_ts(e).date()
            project_days[e.project].add(day)
            project_activity[e.project] += 1

    spans = []
    for project, days in project_days.items():
        ordered = sorted(days)
        if ordered:
            first_days.append(ordered[0])
            spans.append((ordered[-1] - ordered[0]).days + 1)

    if len(spans) >= 2:
        median = statistics.median(spans)
        evidence = {
            "projects_analyzed": len(spans),
            "median_activity_span_days": median,
            "min_days": min(spans),
            "max_days": max(spans),
            "window_days": WINDOW_DAYS,
        }
        p, new = add_pattern(
            db, "project_lifecycle", "Typical Project Activity Span",
            f"Across {len(spans)} observed projects, the median activity span is {median:.1f} days.",
            0.52 + min(0.40, len(spans) / 25), evidence,
        )
        if new:
            created.append(p)

    # ------------------------------------------------------------------
    # 2. Weekend project starts
    # ------------------------------------------------------------------
    if len(first_days) >= 3:
        weekend = sum(d.weekday() >= 5 for d in first_days)
        rate = weekend / len(first_days)
        if rate >= 0.55:
            evidence = {"projects_analyzed": len(first_days), "weekend_starts": weekend, "weekend_rate": round(rate, 3)}
            p, new = add_pattern(
                db, "timing", "Weekend Project Burst",
                f"{weekend} of {len(first_days)} observed project starts occurred on weekends.",
                0.55 + min(0.30, abs(rate - 0.5)), evidence,
            )
            if new:
                created.append(p)

    # ------------------------------------------------------------------
    # 3. Development peak hour
    # ------------------------------------------------------------------
    dev = [e for e in events if e.event_type in {"git_commit", "project_activity", "file_activity", "application_usage"}]
    hours = Counter(_event_ts(e).hour for e in dev)
    if len(dev) >= 10:
        hour, count = hours.most_common(1)[0]
        share = count / len(dev)
        evidence = {"peak_hour": hour, "events_in_peak_hour": count, "development_events": len(dev), "share": round(share, 3)}
        p, new = add_pattern(
            db, "time_of_day", "Peak Activity Window",
            f"Activity is most concentrated around {hour:02d}:00 in the current evidence window.",
            0.50 + min(0.44, share), evidence,
        )
        if new:
            created.append(p)

    # ------------------------------------------------------------------
    # 4. Application usage + primary application
    # ------------------------------------------------------------------
    app_events = [e for e in events if e.event_type == "application_usage" and e.application]
    usage = Counter()
    for e in app_events:
        usage[e.application] += float(e.duration_seconds or 0)
    total = sum(usage.values())

    if total >= 120 and usage:
        app, seconds = usage.most_common(1)[0]
        share = seconds / total if total else 0
        if share >= 0.30:
            evidence = {
                "applications_tracked": len(usage),
                "top_application": app,
                "top_application_minutes": round(seconds / 60, 1),
                "total_tracked_minutes": round(total / 60, 1),
                "share": round(share, 3),
            }
            p, new = add_pattern(
                db, "application_usage", "Primary Application Pattern",
                f"{app} accounts for {share:.0%} of tracked foreground application time.",
                0.52 + min(0.43, share), evidence,
            )
            if new:
                created.append(p)

    # ------------------------------------------------------------------
    # 5. Application switching
    # ------------------------------------------------------------------
    switches = []
    for prev, cur in zip(app_events, app_events[1:]):
        if prev.application != cur.application:
            gap = _event_ts(cur) - _event_ts(prev)
            if gap <= timedelta(minutes=15):
                switches.append((prev.application, cur.application))
    pairs = Counter(switches)
    if len(switches) >= 6:
        (a, b), count = pairs.most_common(1)[0]
        if count >= 3:
            evidence = {"switches_analyzed": len(switches), "transition": f"{a} → {b}", "occurrences": count}
            p, new = add_pattern(
                db, "app_switching", "Frequent Application Switch",
                f"The most frequent observed app transition is {a} → {b}, occurring {count} times.",
                0.54 + min(0.40, count / 20), evidence,
            )
            if new:
                created.append(p)

    # ------------------------------------------------------------------
    # 6. Session duration
    # ------------------------------------------------------------------
    sessions = _app_sessions(app_events)
    if len(sessions) >= MIN_SESSIONS:
        durations = [s["seconds"] for s in sessions]
        median = statistics.median(durations)
        evidence = {
            "sessions_analyzed": len(sessions),
            "median_session_minutes": round(median / 60, 1),
            "min_minutes": round(min(durations) / 60, 1),
            "max_minutes": round(max(durations) / 60, 1),
        }
        p, new = add_pattern(
            db, "sessions", "Typical Activity Session",
            f"The median observed foreground activity session is {median / 60:.1f} minutes.",
            0.55 + min(0.38, len(sessions) / 40), evidence,
        )
        if new:
            created.append(p)

    # ------------------------------------------------------------------
    # 7. Project focus pattern
    # ------------------------------------------------------------------
    if project_activity:
        project, count = max(project_activity.items(), key=lambda x: x[1])
        total_project_events = sum(project_activity.values())
        share = count / total_project_events
        if total_project_events >= 10 and share >= 0.40:
            evidence = {
                "projects_analyzed": len(project_activity),
                "top_project": project,
                "signals": count,
                "total_project_signals": total_project_events,
                "share": round(share, 3),
            }
            p, new = add_pattern(
                db, "project_focus", "Project Focus Pattern",
                f"{project} contains {share:.0%} of observed project activity in the current evidence window.",
                0.52 + min(0.42, share), evidence,
            )
            if new:
                created.append(p)

    # ------------------------------------------------------------------
    # 8. Screen-context workflow
    # ------------------------------------------------------------------
    screen_events = [e for e in events if e.event_type == "screen_context"]
    categories = Counter()
    transitions = Counter()
    previous = None
    for e in screen_events:
        try:
            meta = json.loads(e.metadata_json or "{}")
        except Exception:
            meta = {}
        category = meta.get("category")
        if category and category not in {"unknown", "unchanged", "protected"}:
            categories[category] += 1
            if previous and previous != category:
                transitions[(previous, category)] += 1
            previous = category
    if len(screen_events) >= 8 and categories:
        top_category, top_count = categories.most_common(1)[0]
        total = sum(categories.values())
        share = top_count / total if total else 0
        evidence = {"screen_observations": len(screen_events), "categories": dict(categories), "dominant_category": top_category, "share": round(share, 3)}
        p, new = add_pattern(db, "screen_context", "Dominant Screen Activity", f"Screen context observations most often correspond to {top_category} activity ({share:.0%} of classified observations).", 0.50 + min(0.40, share), evidence)
        if new:
            created.append(p)
    if sum(transitions.values()) >= 6:
        (a, b), count = transitions.most_common(1)[0]
        evidence = {"screen_transitions": sum(transitions.values()), "transition": f"{a} → {b}", "occurrences": count}
        p, new = add_pattern(db, "screen_workflow", "Recurring Screen Workflow", f"Screen context repeatedly transitions from {a} to {b}.", 0.50 + min(0.38, count / 20), evidence)
        if new:
            created.append(p)

    # ------------------------------------------------------------------
    # 9. Cross-source activity
    # ------------------------------------------------------------------
    sources = Counter(e.source for e in events)
    if len(sources) >= 2:
        evidence = {"sources": dict(sources), "source_count": len(sources)}
        p, new = add_pattern(
            db, "cross_source", "Multi-Source Activity",
            "PatternSeeker is receiving activity signals from multiple connected sources.",
            0.60 + min(0.30, len(sources) / 10), evidence,
        )
        if new:
            created.append(p)

    db.commit()
    return created
