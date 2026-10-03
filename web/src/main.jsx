import React, { useEffect, useMemo, useState } from "react"
import { createRoot } from "react-dom/client"
import "./styles.css"

const API = "http://localhost:8000/api"

function formatDuration(seconds) {
  const total = Math.max(0, Math.round(seconds || 0))
  const hours = Math.floor(total / 3600)
  const minutes = Math.floor((total % 3600) / 60)
  if (hours) return `${hours}h ${minutes}m`
  return `${minutes}m`
}

function Metric({ label, value, hint }) {
  return (
    <div className="metricCard">
      <div className="metricLabel">{label}</div>
      <div className="metricValue">{value}</div>
      {hint && <div className="metricHint">{hint}</div>}
      <div className="metricGlow" />
    </div>
  )
}

function StatusDot({ status }) {
  const live = status === "Live"
  return <span className={`status ${live ? "statusLive" : "statusOff"}`}><i />{status}</span>
}

function App() {
  const [summary, setSummary] = useState({})
  const [patterns, setPatterns] = useState([])
  const [events, setEvents] = useState([])
  const [devices, setDevices] = useState([])
  const [usage, setUsage] = useState({ applications: [], total_minutes: 0 })
  const [intelligence, setIntelligence] = useState({ application_sessions: 0, median_session_minutes: 0, active_days: 0, top_application: null, top_project: null, peak_hour: null, top_transition: null })
  const [projects, setProjects] = useState([])
  const [status, setStatus] = useState("Connecting")
  const [detecting, setDetecting] = useState(false)
  const [activeView, setActiveView] = useState("Overview")
  const [system, setSystem] = useState({ available: false, metrics: null })
  const [health, setHealth] = useState({ available: false })
  const [performance, setPerformance] = useState({ available: false })
  const [telemetry, setTelemetry] = useState({ points: [] })
  const [screenIntel, setScreenIntel] = useState({ enabled: false, observations: [], top_categories: [] })
  const [behaviorGraph, setBehaviorGraph] = useState({nodes: [], edges: []})
  const [focus, setFocus] = useState({available:false})
  const [predictions, setPredictions] = useState({available:false, predictions:[]})
  const [forecast, setForecast] = useState({available:false,next:[],windows:[]})
  const [patternCandidates, setPatternCandidates] = useState({available:false,candidates:[]})
  const [anomalies, setAnomalies] = useState({available:false, anomalies:[]})
  const [brief, setBrief] = useState({})
  const [routines, setRoutines] = useState({routines:[]})
  const [lifecycle, setLifecycle] = useState({projects:[]})
  const [switches, setSwitches] = useState({switches:[], total:0})
  const [quality, setQuality] = useState({score:0})
  const [searchQ, setSearchQ] = useState("")
  const [searchResults, setSearchResults] = useState([])

  async function load() {
    try {
      const [s, p, e, d, u, pr, i, sys, hi, perf, tel, scr, bg, fc, pd, pf, pc, an, db, rt, lc, sw, dq] = await Promise.all([
        fetch(`${API}/analytics/summary`).then(r => r.json()),
        fetch(`${API}/insights`).then(r => r.json()),
        fetch(`${API}/events/recent?limit=40`).then(r => r.json()),
        fetch(`${API}/devices`).then(r => r.json()),
        fetch(`${API}/analytics/app-usage?days=1`).then(r => r.json()),
        fetch(`${API}/projects?days=90`).then(r => r.json()),
        fetch(`${API}/analytics/intelligence?days=30`).then(r => r.json()),
        fetch(`${API}/analytics/system`).then(r => r.json()),
        fetch(`${API}/analytics/health-intelligence`).then(r => r.json()),
        fetch(`${API}/analytics/performance`).then(r => r.json()),
        fetch(`${API}/analytics/telemetry-history?hours=6`).then(r => r.json()),
        fetch(`${API}/analytics/screen-intelligence?limit=30`).then(r => r.json()),
        fetch(`${API}/intelligence/behavior-graph?days=30`).then(r => r.json()),
        fetch(`${API}/intelligence/focus?days=14`).then(r => r.json()),
        fetch(`${API}/intelligence/predictions?days=30`).then(r => r.json()),
        fetch(`${API}/prediction/forecast?hours=24&days=90`).then(r => r.json()),
        fetch(`${API}/prediction/pattern-candidates?days=90`).then(r => r.json()),
        fetch(`${API}/intelligence/anomalies?days=30`).then(r => r.json()),
        fetch(`${API}/advanced/daily-brief?days=1`).then(r => r.json()),
        fetch(`${API}/advanced/routines?days=30`).then(r => r.json()),
        fetch(`${API}/advanced/project-lifecycle?days=180`).then(r => r.json()),
        fetch(`${API}/advanced/context-switches?days=14`).then(r => r.json()),
        fetch(`${API}/advanced/data-quality?days=7`).then(r => r.json())
      ])
      setSummary(s)
      setPatterns(p)
      setEvents(e)
      setDevices(d)
      setUsage(u)
      setProjects(pr.projects || [])
      setIntelligence(i)
      setSystem(sys)
      setHealth(hi)
      setPerformance(perf)
      setTelemetry(tel)
      setScreenIntel(scr)
      setBehaviorGraph(bg)
      setFocus(fc)
      setPredictions(pd)
      setForecast(pf)
      setPatternCandidates(pc)
      setAnomalies(an)
      setBrief(db)
      setRoutines(rt)
      setLifecycle(lc)
      setSwitches(sw)
      setQuality(dq)
      setStatus("Live")
    } catch {
      setStatus("API Offline")
    }
  }

  async function detect() {
    setDetecting(true)
    try {
      await fetch(`${API}/analytics/detect`, { method: "POST" })
      await load()
    } finally {
      setDetecting(false)
    }
  }

  useEffect(() => {
    load()
    const timer = setInterval(load, 10000)
    return () => clearInterval(timer)
  }, [])

  const usageMax = useMemo(() => Math.max(...usage.applications.map(a => a.seconds || 0), 1), [usage])
  const eventBars = useMemo(() => {
    const buckets = Array.from({ length: 12 }, (_, i) => ({ label: `${i * 2}:00`, value: 0 }))
    events.forEach(e => {
      const hour = new Date(e.timestamp).getHours()
      const index = Math.min(11, Math.floor(hour / 2))
      buckets[index].value += 1
    })
    const max = Math.max(...buckets.map(b => b.value), 1)
    return buckets.map(b => ({ ...b, height: Math.max(8, Math.round((b.value / max) * 100)) }))
  }, [events])

  const nav = ["Overview", "Timeline", "Applications", "Projects", "Patterns"]

  return (
    <div className="shell">
      <div className="ambient ambientOne" />
      <div className="ambient ambientTwo" />
      <div className="noise" />
      <aside className="sidebar">
        <div className="brandMark"><span>PS</span></div>
        <div className="brandName">PATTERN<span>SEEKER</span></div>
        <div className="brandSub">PERSONAL INTELLIGENCE</div>

        <nav>
          {nav.map(item => (
            <button key={item} className={`navItem ${activeView === item ? "active" : ""}`} onClick={() => setActiveView(item)}>
              <span className="navIcon">{item === "Overview" ? "⌂" : item === "Timeline" ? "◷" : item === "Applications" ? "▦" : item === "Projects" ? "◇" : "✦"}</span>
              {item}
            </button>
          ))}
        </nav>

        <div className="sidebarDivider" />
        <div className="sectionCaption">INTELLIGENCE LAYERS</div>
        {[
          ["Behavior Graph", "Behavior Graph"], ["Focus Analysis", "Focus Analysis"], ["Predictions", "Predictions"], ["Pattern Forecast", "Pattern Forecast"], ["Anomaly Detection", "Anomaly Detection"],
          ["Daily Brief", "Daily Brief"], ["Routines", "Routines"], ["Project Lifecycle", "Project Lifecycle"], ["Data Quality", "Data Quality"], ["Search", "Search"]
        ].map(([label, view]) => (
          <button className={`lockedItem intelligenceNav ${activeView === view ? "selected" : ""}`} key={label} onClick={() => setActiveView(view)}>
            <span>{label}</span><em>LIVE</em>
          </button>
        ))}

        <div className="sidebarBottom">
          <div className="privacyBadge"><span>●</span> Metadata-only mode</div>
          <div className="version">PatternSeeker <b>v2.3</b></div>
        </div>
      </aside>

      <main className="content">
        <div className="pageProgress" />
        <div className="topbar">
          <div>
            <div className="eyebrow">DIGITAL BEHAVIOR OBSERVATORY / {activeView.toUpperCase()}</div>
            <h1>See the patterns<br /><span>behind your activity.</span></h1>
            <p className="heroCopy">PatternSeeker turns local activity signals into evidence-backed behavioral intelligence.</p>
          </div>
          <div className="topActions">
            <StatusDot status={status} />
            <button className="primaryButton" onClick={detect} disabled={detecting}>
              <span className="spark">✦</span>{detecting ? "Analyzing…" : "Detect patterns"}
            </button>
          </div>
        </div>

        <div className="signalLine"><span className="pulseDot" />LIVE SIGNAL STREAM <b>·</b> {devices.length || 0} DEVICE{devices.length === 1 ? "" : "S"} CONNECTED <b>·</b> AUTO REFRESH 10S</div>

        {activeView === "Daily Brief" && <section className="panel intelligencePanel"><div className="panelHeader"><div><span className="panelEyebrow">INTELLIGENCE / DAILY BRIEF</span><h2>Today at a glance</h2></div><span className="micro">LOCAL EVIDENCE</span></div><div className="intelGrid"><div className="intelMetric"><small>EVENTS</small><strong>{brief.events||0}</strong></div><div className="intelMetric"><small>TRACKED TIME</small><strong>{brief.tracked_minutes||0}m</strong></div><div className="intelMetric"><small>DEEP WORK</small><strong>{brief.deep_work_minutes||0}m</strong></div><div className="intelMetric"><small>SWITCHES</small><strong>{brief.context_switches||0}</strong></div><div className="intelMetric"><small>TOP APP</small><strong>{brief.top_app||"—"}</strong></div><div className="intelMetric"><small>TOP PROJECT</small><strong>{brief.top_project||"—"}</strong></div></div><div className="intelligenceLead">Top activity: <b>{brief.top_activity||"Not enough screen context"}</b>. This is a descriptive summary of recorded signals.</div></section>}
{activeView === "Routines" && <section className="panel intelligencePanel"><div className="panelHeader"><div><span className="panelEyebrow">INTELLIGENCE / ROUTINES</span><h2>Recurring activity windows</h2></div><span className="micro">30 DAYS</span></div>{routines.routines?.length ? routines.routines.map((r,i)=><div className="edgeRow" key={i}><span>{["Mon","Tue","Wed","Thu","Fri","Sat","Sun"][r.weekday]} {String(r.hour).padStart(2,"0")}:00</span><b>→</b><span>{r.label}</span><em>{Math.round(r.dominance*100)}% · {r.observations} obs</em></div>) : <div className="empty">No recurring window has enough evidence yet.</div>}</section>}
{activeView === "Project Lifecycle" && <section className="panel intelligencePanel"><div className="panelHeader"><div><span className="panelEyebrow">INTELLIGENCE / PROJECTS</span><h2>Project lifecycle</h2></div><span className="micro">180 DAYS</span></div>{lifecycle.projects?.length ? lifecycle.projects.map(p=><div className="projectRow" key={p.project}><div className="projectIdentity"><span className="projectOrb active"/><div><strong>{p.project}</strong><small>{p.phase.toUpperCase()} · {p.active_days} active days</small></div></div><div className="projectStats"><span>{p.signals} signals</span><span>{p.commits} commits</span><span>{p.file_events} file events</span></div><div className="projectLast">{new Date(p.last_seen).toLocaleDateString()}</div></div>) : <div className="empty">Project lifecycle data will appear as projects accumulate history.</div>}</section>}
{activeView === "Data Quality" && <section className="panel intelligencePanel"><div className="panelHeader"><div><span className="panelEyebrow">SYSTEM / DATA QUALITY</span><h2>Collection quality</h2></div><span className="micro">LAST 7 DAYS</span></div><div className="focusGrid"><div className="focusScore"><small>COVERAGE</small><strong>{quality.score||0}</strong><span>/ 100</span></div><div className="intelStat"><small>EVENTS</small><strong>{quality.events||0}</strong><span>recorded</span></div><div className="intelStat"><small>ACTIVE DAYS</small><strong>{quality.active_days||0}</strong><span>of {quality.window_days||7}</span></div><div className="intelStat"><small>GAP DAYS</small><strong>{quality.gap_days||0}</strong><span>no signals</span></div></div><div className="intelligenceLead">Coverage measures recorded event presence, not the quality of your behavior.</div></section>}
{activeView === "Search" && <section className="panel intelligencePanel"><div className="panelHeader"><div><span className="panelEyebrow">LOCAL SEARCH / METADATA</span><h2>Search your activity</h2></div><span className="micro">NO RAW OCR</span></div><div style={{display:"flex",gap:10}}><input value={searchQ} onChange={e=>setSearchQ(e.target.value)} placeholder="Search app, project, event type…" style={{flex:1,padding:12,borderRadius:9,border:"1px solid rgba(49,135,255,.18)",background:"#03070d",color:"#dcecff"}}/><button className="primaryButton" onClick={async()=>{if(!searchQ.trim())return;const r=await fetch(`${API}/advanced/search?q=${encodeURIComponent(searchQ)}`).then(x=>x.json());setSearchResults(r.results||[])}}>Search</button></div><div className="events" style={{marginTop:15}}>{searchResults.map(x=><div className="event" key={x.id}><time>{new Date(x.timestamp).toLocaleString()}</time><strong>{x.event_type}</strong><span>{x.project||x.application||x.source}</span></div>)}</div></section>}
{activeView === "Behavior Graph" && <section className="panel intelligencePanel">
          <div className="panelHeader"><div><span className="panelEyebrow">INTELLIGENCE / RELATIONSHIP MODEL</span><h2>Behavior Graph</h2></div><span className="micro">30 DAY WINDOW</span></div>
          <p className="intelligenceLead">Observed relationships between applications, projects and screen activity. Edge weight is the number of observed transitions.</p>
          {behaviorGraph.nodes.length ? <div className="graphGrid">
            <div className="graphNodes">{behaviorGraph.nodes.map(n => <div className="graphNode" key={n.id}><span className={`nodeDot ${n.type}`} /><div><strong>{n.label}</strong><small>{n.type} · {n.weight} signals</small></div></div>)}</div>
            <div className="edgeList">{behaviorGraph.edges.slice(0,18).map(e => <div className="edgeRow" key={`${e.source}-${e.target}`}><span>{e.source.replace(/^(app:|project:|activity:)/,'')}</span><b>→</b><span>{e.target.replace(/^(app:|project:|activity:)/,'')}</span><em>{e.weight}</em></div>)}</div>
          </div> : <div className="empty">Build more application, project and screen history to generate the graph.</div>}
        </section>}

        {activeView === "Focus Analysis" && <section className="panel intelligencePanel">
          <div className="panelHeader"><div><span className="panelEyebrow">INTELLIGENCE / ATTENTION</span><h2>Focus Analysis</h2></div><span className="micro">14 DAY WINDOW</span></div>
          {!focus.available ? <div className="empty">{focus.message}</div> : <div className="focusGrid">
            <div className="focusScore"><small>FOCUS SCORE</small><strong>{focus.score}</strong><span>/ 100</span></div>
            <div className="intelStat"><small>DEEP SESSIONS</small><strong>{focus.deep_sessions}</strong><span>{focus.deep_work_minutes} min</span></div>
            <div className="intelStat"><small>CONTEXT SWITCHES</small><strong>{focus.context_switches}</strong><span>{focus.switches_per_hour}/hour</span></div>
            <div className="intelStat"><small>PEAK HOUR</small><strong>{String(focus.peak_hour).padStart(2,'0')}:00</strong><span>{focus.peak_hour_sessions} sessions</span></div>
          </div>}
        </section>}

        {activeView === "Predictions" && <section className="panel intelligencePanel">
          <div className="panelHeader"><div><span className="panelEyebrow">INTELLIGENCE / RECURRENCE</span><h2>Prediction Engine</h2></div><span className="micro">HISTORICAL ESTIMATES</span></div>
          <p className="intelligenceLead">These are recurring activity estimates derived from your observed weekday/hour history, not guaranteed future events.</p>
          {!forecast.available && !predictions.available ? <div className="empty">{forecast.message || predictions.message}</div> : <>
            <div className="intelGrid">
              <div className="intelMetric"><small>NEXT SIGNAL</small><strong>{forecast.next?.[0]?.expected || "—"}</strong></div>
              <div className="intelMetric"><small>STARTS IN</small><strong>{forecast.next?.[0] ? `${forecast.next[0].starts_in_hours}h` : "—"}</strong></div>
              <div className="intelMetric"><small>CONFIDENCE</small><strong>{forecast.next?.[0] ? `${Math.round(forecast.next[0].confidence*100)}%` : "—"}</strong></div>
              <div className="intelMetric"><small>CANDIDATES</small><strong>{patternCandidates.candidates?.length || 0}</strong></div>
            </div>
            <h3 className="subsectionTitle">Next observed windows</h3>
            <div className="predictionList">{(forecast.next || []).map((p,i) => <div className="predictionRow" key={`next-${i}`}><span className="dayPill">{['Mon','Tue','Wed','Thu','Fri','Sat','Sun'][p.weekday]}</span><strong>{String(p.hour).padStart(2,'0')}:00</strong><span>{String(p.expected).replaceAll('_',' ')}</span><small>{p.support} support · {p.observations} observations · {Math.round(p.confidence*100)}% evidence confidence</small></div>)}</div>
            <h3 className="subsectionTitle">Pattern candidates</h3>
            <div className="predictionList">{(patternCandidates.candidates || []).slice(0,8).map((p,i) => <div className="predictionRow" key={`candidate-${i}`}><span className="dayPill">{['Mon','Tue','Wed','Thu','Fri','Sat','Sun'][p.common_weekday]}</span><strong>{String(p.common_hour).padStart(2,'0')}:00</strong><span>{String(p.label).replaceAll('_',' ')}</span><small>{p.observations} observations · {Math.round(p.confidence*100)}% · {p.status}</small></div>)}</div>
          </>}
        </section>}

        {activeView === "Pattern Forecast" && <section className="panel intelligencePanel">
          <div className="panelHeader"><div><span className="panelEyebrow">INTELLIGENCE / PATTERN FORECAST</span><h2>Pattern Forecast</h2></div><span className="micro">EVIDENCE PIPELINE</span></div>
          <p className="intelligenceLead">Emerging patterns are kept as candidates until repeated evidence is strong enough to promote them into the durable pattern engine.</p>
          {(patternCandidates.candidates || []).length ? <div className="predictionList">{patternCandidates.candidates.map((p,i) => <div className="predictionRow" key={i}><span className="dayPill">{Math.round(p.confidence*100)}%</span><strong>{p.observations} obs</strong><span>{String(p.label).replaceAll('_',' ')}</span><small>{['Mon','Tue','Wed','Thu','Fri','Sat','Sun'][p.common_weekday]} {String(p.common_hour).padStart(2,'0')}:00 · {p.status}</small></div>)}</div> : <div className="empty">No emerging pattern has enough evidence yet.</div>}
        </section>}

        {activeView === "Anomaly Detection" && <section className="panel intelligencePanel">
          <div className="panelHeader"><div><span className="panelEyebrow">INTELLIGENCE / DEVIATION</span><h2>Anomaly Detection</h2></div><span className="micro">30 DAY BASELINE</span></div>
          {!anomalies.available ? <div className="empty">{anomalies.message}</div> : <>
            <div className="baselineLine"><span>Baseline median</span><strong>{anomalies.baseline.median_daily_events} events/day</strong><span>{anomalies.baseline.active_days} active days</span></div>
            {anomalies.anomalies.length ? <div className="anomalyList">{anomalies.anomalies.map((a,i) => <div className="anomalyRow" key={i}><span>{a.date}</span><strong>{a.type.replaceAll('_',' ')}</strong><b>{a.value}</b><small>{a.robust_deviation} MAD from baseline</small></div>)}</div> : <div className="empty">No strong daily activity deviations detected in the current baseline.</div>}
          </>}
        </section>}

        <section className="metricsGrid">
          <Metric label="Tracked events" value={summary.events ?? 0} hint="Local activity signals" />
          <Metric label="Projects detected" value={summary.projects ?? 0} hint="Discovered codebases" />
          <Metric label="Git commits" value={summary.git_commits ?? 0} hint="Development signals" />
          <Metric label="Connected devices" value={summary.devices ?? 0} hint="Active collectors" />
          <Metric label="Patterns found" value={summary.patterns ?? 0} hint="Evidence-backed" />
          <Metric label="Tracked today" value={`${Math.round(usage.total_minutes ?? 0)}m`} hint="Foreground usage" />
        </section>

        <section className="panel hardwarePanel">
          <div className="panelHeader"><div><span className="panelEyebrow">00 / SYSTEM TELEMETRY</span><h2>Machine health</h2></div><span className="micro">LOCAL HARDWARE</span></div>
          {!system.available ? <div className="empty">Hardware telemetry will appear when the desktop collector sends its first system sample.</div> : (() => {
            const m = system.metrics || {}; const cpu = m.cpu || {}; const mem = m.memory || {}; const gpu = m.gpu || {}; const disk = m.disk || {}; const bat = m.battery || {};
            const meter = (value) => value == null ? 0 : Math.max(0, Math.min(100, Number(value)));
            const temp = m.cpu_temperature_c;
            return <div className="hardwareGrid">
              <div className="hardwareCard"><span>CPU LOAD</span><strong>{cpu.usage_percent ?? "—"}%</strong><div className="meter"><i style={{width:`${meter(cpu.usage_percent)}%`}} /></div><small>{cpu.clock_mhz ? `${Math.round(cpu.clock_mhz)} MHz current` : "Clock unavailable"} · {cpu.threads || "—"} threads</small></div>
              <div className="hardwareCard"><span>MEMORY</span><strong>{mem.usage_percent ?? "—"}%</strong><div className="meter"><i style={{width:`${meter(mem.usage_percent)}%`}} /></div><small>{mem.used_gb ?? "—"} / {mem.total_gb ?? "—"} GB used</small></div>
              <div className="hardwareCard"><span>GPU</span><strong>{gpu.utilization_percent ?? "—"}%</strong><div className="meter"><i style={{width:`${meter(gpu.utilization_percent)}%`}} /></div><small>{gpu.temperature_c != null ? `${gpu.temperature_c}°C` : "Temp unavailable"} · {gpu.clock_mhz != null ? `${Math.round(gpu.clock_mhz)} MHz` : "Clock unavailable"}</small><small>{gpu.memory_used_mb != null && gpu.memory_total_mb != null ? `${Math.round(gpu.memory_used_mb)} / ${Math.round(gpu.memory_total_mb)} MB VRAM` : "VRAM unavailable"}</small></div>
              <div className="hardwareCard"><span>THERMALS / FAN</span><strong>{temp != null ? `${temp}°C` : "—"}</strong><div className="hardwarePair"><small>CPU FAN <b>{m.cpu_fan_rpm != null ? `${Math.round(m.cpu_fan_rpm)} RPM` : "N/A"}</b></small><small>GPU FAN <b>{gpu.fan_percent != null ? `${Math.round(gpu.fan_percent)}%` : "N/A"}</b></small></div><small>{gpu.power_w != null ? `GPU power ${gpu.power_w} W` : (gpu.power_status === "invalid_driver_value" ? "GPU power reading rejected as unreliable" : "GPU power unavailable")}</small></div>
              <div className="hardwareCard"><span>STORAGE</span><strong>{disk.usage_percent ?? "—"}%</strong><div className="meter"><i style={{width:`${meter(disk.usage_percent)}%`}} /></div><small>{disk.free_gb ?? "—"} GB free · {disk.total_gb ?? "—"} GB total</small></div>
              <div className="hardwareCard"><span>POWER / UPTIME</span><strong>{bat.percent != null ? `${bat.percent}%` : "AC"}</strong><div className="hardwarePair"><small>POWER <b>{bat.plugged ? "PLUGGED" : bat.percent != null ? "BATTERY" : "N/A"}</b></small><small>UPTIME <b>{m.system?.uptime_hours ?? "—"}h</b></small></div><small>Telemetry stays local and metadata-only.</small></div>
              <div className="hardwareCard"><span>NETWORK</span><strong>{m.network ? `${m.network.sent_mb + m.network.received_mb} MB` : "—"}</strong><div className="hardwarePair"><small>UP <b>{m.network ? `${m.network.sent_mb} MB` : "N/A"}</b></small><small>DOWN <b>{m.network ? `${m.network.received_mb} MB` : "N/A"}</b></small></div><small>Cumulative interface traffic since boot.</small></div>
            </div>
          })()}
        </section>

        <section className="panel healthStrip">
          <div className="panelHeader"><div><span className="panelEyebrow">00 / COLLECTOR HEALTH</span><h2>Runtime health</h2></div><span className={`healthBadge ${health.health === "healthy" ? "healthy" : "attention"}`}>{health.health || "UNKNOWN"}</span></div>
          <div className="healthGrid">
            <div><small>COLLECTOR CPU</small><strong>{health.collector_impact?.cpu_percent ?? "—"}%</strong></div>
            <div><small>COLLECTOR RAM</small><strong>{health.collector_impact?.memory_mb ?? "—"} MB</strong></div>
            <div><small>COLLECTOR THREADS</small><strong>{health.collector_impact?.threads ?? "—"}</strong></div>
            <div><small>GPU POWER</small><strong>{health.gpu_power_reliable ? "VERIFIED" : "SAFE / UNAVAILABLE"}</strong></div>
            <div className="healthWarnings"><small>DIAGNOSTICS</small><strong>{(health.warnings || []).length ? health.warnings.join(" · ") : "No active warnings"}</strong></div>
          </div>
        </section>

        <section className="panel performancePanel">
          <div className="panelHeader"><div><span className="panelEyebrow">00 / RUNTIME INTELLIGENCE</span><h2>Performance radar</h2></div><span className="micro">LOCAL · LOW IMPACT</span></div>
          <div className="performanceGrid">
            <div className="healthScore"><span>DEVICE HEALTH</span><strong>{performance.score ?? "—"}</strong><small>{performance.state || "waiting"}</small></div>
            <div className="perfStat"><small>COLLECTOR CPU</small><strong>{performance.collector?.cpu_percent ?? "—"}%</strong><span>Target &lt; 5%</span></div>
            <div className="perfStat"><small>COLLECTOR RAM</small><strong>{performance.collector?.memory_mb ?? "—"} MB</strong><span>Background footprint</span></div>
            <div className="perfStat"><small>GPU POWER</small><strong>{system.metrics?.gpu?.power_w != null ? `${system.metrics.gpu.power_w} W` : "N/A"}</strong><span>{system.metrics?.gpu?.power_status === "valid" ? "Driver verified" : "Safe fallback"}</span></div>
          </div>
          <div className="telemetryMini">
            <div><span>CPU</span><b>{telemetry.points?.length ? `${telemetry.points.at(-1)?.cpu ?? "—"}%` : "—"}</b></div>
            <div><span>RAM</span><b>{telemetry.points?.length ? `${telemetry.points.at(-1)?.memory ?? "—"}%` : "—"}</b></div>
            <div><span>GPU TEMP</span><b>{telemetry.points?.length ? `${telemetry.points.at(-1)?.gpu_temp ?? "—"}${telemetry.points.at(-1)?.gpu_temp != null ? "°C" : ""}` : "—"}</b></div>
            <div><span>DISK WRITE</span><b>{telemetry.points?.length ? `${telemetry.points.at(-1)?.disk_write_mb_s ?? "—"} MB/s` : "—"}</b></div>
            <div><span>NETWORK DOWN</span><b>{telemetry.points?.length ? `${telemetry.points.at(-1)?.download_mb_s ?? "—"} MB/s` : "—"}</b></div>
          </div>
          <div className="telemetryChart" aria-label="Recent CPU telemetry">
            {(telemetry.points || []).slice(-60).map((pt, idx) => <span key={`${pt.timestamp}-${idx}`} title={`${new Date(pt.timestamp).toLocaleTimeString()} · CPU ${pt.cpu ?? "—"}%`} style={{height:`${Math.max(5, Math.min(100, Number(pt.cpu ?? 0)))}%`}} />)}
          </div>
        </section>

        <section className="panel screenPanel">
          <div className="panelHeader"><div><span className="panelEyebrow">00 / SCREEN INTELLIGENCE</span><h2>Context observer</h2></div><span className="micro">LOCAL · NO SCREENSHOTS STORED</span></div>
          <div className="screenIntelGrid">
            <div className="screenStatus"><span className={`healthBadge ${screenIntel.observations?.length ? "healthy" : "attention"}`}>{screenIntel.observations?.length ? "ACTIVE" : "WAITING"}</span><strong>{screenIntel.observations?.length || 0}</strong><small>recent observations</small></div>
            <div className="screenCategories">{(screenIntel.top_categories || []).slice(0, 6).map(x => <div className="screenCat" key={x.category}><span>{x.category}</span><b>{x.observations}</b></div>)}{!(screenIntel.top_categories || []).length && <div className="empty">Enable screen intelligence in the desktop collector to build context history.</div>}</div>
            <div className="screenObservations">{(screenIntel.observations || []).slice(0, 6).map((x, idx) => <div className="screenObs" key={`${x.timestamp}-${idx}`}><time>{new Date(x.timestamp).toLocaleTimeString([], {hour:"2-digit", minute:"2-digit"})}</time><strong>{x.category}</strong><span>{x.application || "desktop"}</span><em>{Math.round((x.confidence || 0) * 100)}%</em></div>)}</div>
          </div>
          <div className="privacyNote"><span>●</span> Screen frames are processed in memory. No screenshots or raw OCR text are stored or uploaded to the PatternSeeker API.</div>
        </section>

        <section className="panel intelligencePanel">
          <div className="panelHeader"><div><span className="panelEyebrow">00 / INTELLIGENCE SNAPSHOT</span><h2>Behavior signals</h2></div><span className="micro">LAST 30 DAYS</span></div>
          <div className="intelGrid">
            <div className="intelMetric"><small>ACTIVE DAYS</small><strong>{intelligence.active_days}</strong></div>
            <div className="intelMetric"><small>SESSIONS</small><strong>{intelligence.application_sessions}</strong></div>
            <div className="intelMetric"><small>MEDIAN SESSION</small><strong>{intelligence.median_session_minutes}m</strong></div>
            <div className="intelMetric"><small>PEAK HOUR</small><strong>{intelligence.peak_hour ? `${String(intelligence.peak_hour.hour).padStart(2, "0")}:00` : "—"}</strong></div>
            <div className="intelMetric"><small>TOP APP</small><strong>{intelligence.top_application?.name || "—"}</strong></div>
            <div className="intelMetric"><small>TOP PROJECT</small><strong>{intelligence.top_project?.name || "—"}</strong></div>
          </div>
          {intelligence.top_transition && <div className="transitionLine"><span>FREQUENT TRANSITION</span><b>{intelligence.top_transition.from}</b><i>→</i><b>{intelligence.top_transition.to}</b><small>{intelligence.top_transition.occurrences} observed transitions</small></div>}
        </section>

        <section className="panel processPanel">
          <div className="panelHeader"><div><span className="panelEyebrow">00 / RESOURCE PRESSURE</span><h2>Top processes</h2></div><span className="micro">METADATA ONLY</span></div>
          <div className="processGrid">
            {(performance.top_processes || []).map((proc) => <div className="processRow" key={`${proc.pid}-${proc.name}`}><div><strong>{proc.name}</strong><small>PID {proc.pid}</small></div><span>{proc.cpu_percent}% CPU</span><span>{proc.memory_mb} MB</span></div>)}
            {!performance.top_processes?.length && <div className="empty">Process telemetry will appear after the next system sample.</div>}
          </div>
        </section>

        <section className="gridMain">
          <div className="panel usagePanel">
            <div className="panelHeader">
              <div><span className="panelEyebrow">01 / ACTIVITY SIGNAL</span><h2>Application usage</h2></div>
              <span className="micro">FOREGROUND PROCESS ONLY</span>
            </div>
            {usage.applications.length === 0 ? <div className="empty">Usage signals will appear after the collector records foreground applications.</div> : (
              <div className="usageList">
                {usage.applications.slice(0, 8).map(a => (
                  <div className="usageRow" key={a.application}>
                    <div className="usageIdentity"><span className="appOrb" /><div><strong>{a.application}</strong><small>{Math.round(a.share * 100)}% of tracked time</small></div></div>
                    <div className="usageBar"><span style={{ width: `${Math.max(4, (a.seconds / usageMax) * 100)}%` }} /></div>
                    <strong className="usageTime">{formatDuration(a.seconds)}</strong>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="panel activityPanel">
            <div className="panelHeader"><div><span className="panelEyebrow">02 / ACTIVITY RHYTHM</span><h2>Signal timeline</h2></div><span className="micro">TODAY</span></div>
            <div className="barChart">
              {eventBars.map(b => <div className="barCol" key={b.label}><div className="barTrack"><span style={{ height: `${b.height}%` }} /></div><small>{b.label}</small></div>)}
            </div>
            <div className="chartLegend"><span><i className="legendBlue" />Activity density</span><span>{events.length} recent signals</span></div>
          </div>
        </section>

        <section className="panel projectsPanel">
          <div className="panelHeader"><div><span className="panelEyebrow">03 / PROJECT INTELLIGENCE</span><h2>Detected projects</h2></div><span className="micro">{projects.length} CODEBASES</span></div>
          {projects.length === 0 ? <div className="empty">Project signals will appear when the collector discovers codebases.</div> : (
            <div className="projectList">
              {projects.slice(0, 8).map(project => (
                <div className="projectRow" key={project.project}>
                  <div className="projectIdentity"><span className={`projectOrb ${project.status === "active" ? "active" : ""}`} /><div><strong>{project.project}</strong><small>{project.status.toUpperCase()} · {project.active_days} active day{project.active_days === 1 ? "" : "s"}</small></div></div>
                  <div className="projectStats"><span>{project.events} signals</span><span>{project.git_commits} commits</span><span>{project.file_activity} file events</span></div>
                  <div className="projectLast">{project.last_seen ? new Date(project.last_seen).toLocaleDateString() : "—"}</div>
                </div>
              ))}
            </div>
          )}
        </section>

        <section className="panel patternsPanel">
          <div className="panelHeader"><div><span className="panelEyebrow">04 / INTELLIGENCE ENGINE</span><h2>Detected patterns</h2></div><span className="confidenceBadge">EVIDENCE-BACKED</span></div>
          {patterns.length === 0 && <div className="empty patternEmpty"><div className="emptyIcon">✦</div><div><strong>Waiting for enough evidence</strong><p>Run the collector, build activity history, then use Detect patterns to surface recurring behavior.</p></div></div>}
          {patterns.map(p => (
            <article className="pattern" key={p.id}>
              <div className="patternHeader"><div><span className="tag">{p.pattern_type}</span><h3>{p.title}</h3></div><div className="confidence">{Math.round(p.confidence * 100)}%<small>confidence</small></div></div>
              <p>{p.description}</p>
              {p.ai_explanation && <div className="ai"><strong>LOCAL AI EXPLANATION</strong><p>{p.ai_explanation}</p></div>}
              <details><summary>View evidence</summary><pre>{JSON.stringify(p.evidence, null, 2)}</pre></details>
            </article>
          ))}
        </section>

        <section className="futureGrid">
          {[
            ["Behavior Graph", "Map relationships between apps, projects, sessions and recurring actions.", "GRAPH"],
            ["Focus Analysis", "Detect deep-work windows, context switching and fragmented sessions.", "FOCUS"],
            ["Prediction Engine", "Forecast recurring activity windows from historical evidence.", "PREDICT"],
            ["Pattern Forecast", "Surface emerging patterns before promoting them to durable patterns.", "FORECAST"],
            ["Anomaly Detection", "Surface unusual changes in your normal digital behavior.", "ANOMALY"]
          ].map(([title, desc, code]) => (
            <button className="futureCard liveFuture" key={title} onClick={() => setActiveView(title === "Prediction Engine" ? "Predictions" : title)}>
              <div className="futureTop"><span>{code}</span><b>LIVE</b></div>
              <h3>{title}</h3><p>{desc}</p><div className="coming">OPEN INTELLIGENCE <span>→</span></div>
            </button>
          ))}
        </section>

        <section className="twoCol">
          <section className="panel">
            <div className="panelHeader"><div><span className="panelEyebrow">05 / DEVICES</span><h2>Connected devices</h2></div><span className="micro">{devices.length} ONLINE</span></div>
            {devices.map(d => <div className="device" key={d.device_id}><div className="deviceIdentity"><span className="deviceIcon">▣</span><div><strong>{d.name}</strong><small>{d.platform}</small></div></div><small className={d.active ? "deviceActive" : "deviceInactive"}>{d.active ? "ACTIVE" : "INACTIVE"}</small></div>)}
          </section>
          <section className="panel">
            <div className="panelHeader"><div><span className="panelEyebrow">06 / RAW SIGNALS</span><h2>Recent events</h2></div><span className="micro">{events.length} EVENTS</span></div>
            <div className="events">{events.map(e => <div className="event" key={e.id}><time>{new Date(e.timestamp).toLocaleTimeString([], {hour: "2-digit", minute: "2-digit"})}</time><strong>{e.event_type}</strong><span>{e.project || e.application || e.source}</span></div>)}</div>
          </section>
        </section>

        <footer><span>PATTERNSEEKER</span><span>LOCAL-FIRST · PRIVACY-AWARE · EVIDENCE-DRIVEN</span><span>v2.3</span></footer>
      </main>
    </div>
  )
}

createRoot(document.getElementById("root")).render(<App />)
