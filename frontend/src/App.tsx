import { useState, useRef, useEffect, useCallback, useId } from 'react'

// ── Types ──────────────────────────────────────────────────────────────────
interface UIElement {
  type: string
  label: string
  bbox: [number, number, number, number] // x1,y1,x2,y2 as 0‒1 ratios
  issues: string[]
  confidence: number
}
interface Analysis {
  elements: UIElement[]
  issues: string[]
  insights: string
  score: number
}
interface Msg {
  id: number
  kind: 'system' | 'info' | 'success' | 'warn' | 'error' | 'scan'
  text: string
  ts: string
}

// ── Demo script ────────────────────────────────────────────────────────────
const DEMO: Array<{ delay: number; analysis: Analysis; msgs: Array<Omit<Msg, 'id' | 'ts'>> }> = [
  {
    delay: 800,
    analysis: { elements: [], issues: [], insights: 'Neural vision pipeline ready.', score: 0 },
    msgs: [
      { kind: 'system', text: '⬡  OmniSight v1.0 — vision agent online' },
      { kind: 'info',   text: '📡 Streaming frames → analysis pipeline' },
    ],
  },
  {
    delay: 3000,
    analysis: {
      elements: [
        { type: 'nav',  label: 'Navigation',  bbox: [0.02, 0.01, 0.98, 0.09], issues: [],               confidence: 0.96 },
        { type: 'text', label: 'Hero Heading', bbox: [0.08, 0.13, 0.92, 0.27], issues: [],               confidence: 0.97 },
        { type: 'text', label: 'Subheading',   bbox: [0.15, 0.28, 0.85, 0.35], issues: [],               confidence: 0.91 },
      ],
      issues: [],
      insights: 'Header layout looks clean. Continuing scan…',
      score: 68,
    },
    msgs: [
      { kind: 'success', text: '✓  nav bar detected (conf 96%)' },
      { kind: 'success', text: '✓  hero + subheading present' },
      { kind: 'info',    text: '📊 Initial score: 68 / 100' },
    ],
  },
  {
    delay: 6500,
    analysis: {
      elements: [
        { type: 'nav',    label: 'Navigation',    bbox: [0.02, 0.01, 0.98, 0.09], issues: [],                          confidence: 0.96 },
        { type: 'text',   label: 'Hero Heading',  bbox: [0.08, 0.13, 0.92, 0.27], issues: [],                          confidence: 0.97 },
        { type: 'text',   label: 'Subheading',    bbox: [0.15, 0.28, 0.85, 0.35], issues: [],                          confidence: 0.91 },
        { type: 'button', label: 'CTA Button',    bbox: [0.34, 0.40, 0.66, 0.50], issues: ['contrast:2.1:1'],          confidence: 0.93 },
        { type: 'input',  label: 'Email Field',   bbox: [0.24, 0.53, 0.76, 0.61], issues: ['no-aria-label'],           confidence: 0.89 },
      ],
      issues: [
        'Button contrast ratio 2.1:1 — fails WCAG AA (min 4.5:1)',
        'Email input missing accessible label (aria-label / <label>)',
      ],
      insights: '2 accessibility violations detected. Sending to coding agent.',
      score: 51,
    },
    msgs: [
      { kind: 'warn',  text: '⚠  Button contrast 2.1:1 → WCAG AA fail' },
      { kind: 'warn',  text: '⚠  Email input has no aria-label' },
      { kind: 'error', text: '✗  Score: 68 → 51  (-17 pts, 2 violations)' },
      { kind: 'scan',  text: '🤖 Sending visual report to coding agent…' },
    ],
  },
  {
    delay: 10500,
    analysis: {
      elements: [
        { type: 'nav',    label: 'Navigation',    bbox: [0.02, 0.01, 0.98, 0.09], issues: [],  confidence: 0.96 },
        { type: 'text',   label: 'Hero Heading',  bbox: [0.08, 0.13, 0.92, 0.27], issues: [],  confidence: 0.97 },
        { type: 'text',   label: 'Subheading',    bbox: [0.15, 0.28, 0.85, 0.35], issues: [],  confidence: 0.91 },
        { type: 'button', label: 'CTA Button',    bbox: [0.34, 0.40, 0.66, 0.50], issues: [],  confidence: 0.98 },
        { type: 'input',  label: 'Email Field',   bbox: [0.24, 0.53, 0.76, 0.61], issues: [],  confidence: 0.96 },
        { type: 'card',   label: 'Feature A',     bbox: [0.02, 0.66, 0.32, 0.84], issues: [],  confidence: 0.87 },
        { type: 'card',   label: 'Feature B',     bbox: [0.35, 0.66, 0.65, 0.84], issues: [],  confidence: 0.87 },
        { type: 'card',   label: 'Feature C',     bbox: [0.68, 0.66, 0.98, 0.84], issues: [],  confidence: 0.87 },
      ],
      issues: [],
      insights: 'All violations resolved. 3-column feature grid detected. UI ready.',
      score: 91,
    },
    msgs: [
      { kind: 'success', text: '✓  Agent fix applied: contrast → 6.2:1  ✓ WCAG AAA' },
      { kind: 'success', text: '✓  Agent fix applied: aria-label added  ✓' },
      { kind: 'success', text: '✓  3-col feature grid: 3 cards in view' },
      { kind: 'info',    text: '📊 Score: 51 → 91  (+40 pts)  🎉 Vision loop closed!' },
    ],
  },
]

// ── Helpers ────────────────────────────────────────────────────────────────
const ELEMENT_COLORS: Record<string, string> = {
  button: '#ff6b35',
  input:  '#f59e0b',
  nav:    '#00d4ff',
  card:   '#a78bfa',
  text:   '#00ff88',
  image:  '#ec4899',
  form:   '#f59e0b',
}
const elColor = (type: string, hasIssues: boolean) =>
  hasIssues ? '#ff3366' : (ELEMENT_COLORS[type] ?? '#00d4ff')

const kindIcon: Record<Msg['kind'], string> = {
  system:  '◈',
  info:    '○',
  success: '●',
  warn:    '▲',
  error:   '■',
  scan:    '◉',
}
const kindColor: Record<Msg['kind'], string> = {
  system:  '#64748b',
  info:    '#00d4ff',
  success: '#00ff88',
  warn:    '#ff6b35',
  error:   '#ff3366',
  scan:    '#a78bfa',
}

// ── Component ──────────────────────────────────────────────────────────────
let _msgId = 1
const nextId = () => _msgId++

export default function App() {
  const videoRef   = useRef<HTMLVideoElement>(null)
  const captureRef = useRef<HTMLCanvasElement>(null) // hidden
  const overlayRef = useRef<HTMLCanvasElement>(null) // visible overlay
  const wsRef      = useRef<WebSocket | null>(null)
  const streamRef  = useRef<MediaStream | null>(null)
  const trackRef   = useRef<MediaStreamTrack | null>(null)
  const onEndedRef = useRef<(() => void) | null>(null)
  const sendIntervalRef = useRef<ReturnType<typeof setInterval>>()
  const demoTimers      = useRef<ReturnType<typeof setTimeout>[]>([])
  const frameCountRef   = useRef(0)
  const lastFpsTs       = useRef(Date.now())

  const [capturing,  setCapturing]  = useState(false)
  const [connected,  setConnected]  = useState(false)
  const [demoMode,   setDemoMode]   = useState(false)
  const [analysis,   setAnalysis]   = useState<Analysis>({ elements: [], issues: [], insights: '', score: 0 })
  const [messages,   setMessages]   = useState<Msg[]>([])
  const [fps,        setFps]        = useState(0)
  const [scanning,   setScanning]   = useState(false)
  const feedRef = useRef<HTMLDivElement>(null)

  const addMsg = useCallback((kind: Msg['kind'], text: string) => {
    const ts = new Date().toLocaleTimeString('en', { hour12: false })
    setMessages(prev => [...prev.slice(-60), { id: nextId(), kind, text, ts }])
  }, [])

  // Auto-scroll feed
  useEffect(() => {
    if (feedRef.current) feedRef.current.scrollTop = feedRef.current.scrollHeight
  }, [messages])

  useEffect(() => {
    return () => {
      demoTimers.current.forEach(clearTimeout)
      clearInterval(sendIntervalRef.current)
      wsRef.current?.close()
      streamRef.current?.getTracks().forEach(t => t.stop())
      if (trackRef.current && onEndedRef.current) {
        trackRef.current.removeEventListener('ended', onEndedRef.current)
      }
      trackRef.current = null
      onEndedRef.current = null
    }
  }, [])

  // Draw overlay boxes on canvas
  useEffect(() => {
    const canvas = overlayRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) {
      console.warn('Could not get 2D context for overlay canvas')
      return
    }
    ctx.clearRect(0, 0, canvas.width, canvas.height)
    const W = canvas.width, H = canvas.height
    for (const el of analysis.elements) {
      const [x1, y1, x2, y2] = el.bbox
      const x = x1 * W, y = y1 * H, bw = (x2 - x1) * W, bh = (y2 - y1) * H
      const col = elColor(el.type, el.issues.length > 0)
      ctx.shadowColor = col; ctx.shadowBlur = 12
      ctx.strokeStyle = col; ctx.lineWidth = 1.5
      ctx.strokeRect(x, y, bw, bh)
      // Corner marks
      const cm = 8; ctx.lineWidth = 2.5; ctx.shadowBlur = 6
      const corners: Array<[number, number, number, number, number, number]> = [
        [x+cm,y, x,y, x,y+cm], [x+bw-cm,y, x+bw,y, x+bw,y+cm],
        [x+cm,y+bh, x,y+bh, x,y+bh-cm], [x+bw-cm,y+bh, x+bw,y+bh, x+bw,y+bh-cm],
      ]
      for (const [ax,ay,bx,by,cx,cy] of corners) {
        ctx.beginPath(); ctx.moveTo(ax,ay); ctx.lineTo(bx,by); ctx.lineTo(cx,cy); ctx.stroke()
      }
      ctx.shadowBlur = 0
      // Label
      const lbl = `${el.type.toUpperCase()} ${Math.round(el.confidence*100)}%`
      ctx.font = 'bold 10px JetBrains Mono, monospace'
      const tw = ctx.measureText(lbl).width
      ctx.fillStyle = col; ctx.fillRect(x, y - 18, tw + 8, 16)
      ctx.fillStyle = '#000'; ctx.fillText(lbl, x + 4, y - 5)
    }
  }, [analysis])

  // Demo mode sequence
  const runDemo = useCallback(() => {
    if (capturing) return
    setDemoMode(true)
    setScanning(true)
    demoTimers.current.forEach(clearTimeout)
    demoTimers.current = []
    DEMO.forEach(frame => {
      const t = setTimeout(() => {
        setAnalysis(frame.analysis)
        frame.msgs.forEach(m => addMsg(m.kind, m.text))
      }, frame.delay)
      demoTimers.current.push(t)
    })
    const endT = setTimeout(() => { setScanning(false); setDemoMode(false) }, 14000)
    demoTimers.current.push(endT)
  }, [addMsg, capturing])

  // Screen capture
  const startCapture = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getDisplayMedia({ video: { frameRate: 5 }, audio: false })
      streamRef.current = stream
      if (videoRef.current) { videoRef.current.srcObject = stream; await videoRef.current.play() }
      setCapturing(true)
      addMsg('system', '📺 Screen capture started')
      const track = stream.getVideoTracks()[0]
      if (track) {
        if (trackRef.current && onEndedRef.current) {
          trackRef.current.removeEventListener('ended', onEndedRef.current)
        }
        trackRef.current = track
        const onEnded = () => stopCapture()
        onEndedRef.current = onEnded
        track.addEventListener('ended', onEnded)
      }
    } catch { addMsg('error', '✗ Screen capture denied — running demo mode') ; runDemo() }
  }, [addMsg, runDemo])

  const stopCapture = useCallback(() => {
    if (trackRef.current && onEndedRef.current) {
      trackRef.current.removeEventListener('ended', onEndedRef.current)
    }
    trackRef.current = null
    onEndedRef.current = null
    streamRef.current?.getTracks().forEach(t => t.stop())
    streamRef.current = null
    if (videoRef.current) { videoRef.current.srcObject = null }
    clearInterval(sendIntervalRef.current)
    setCapturing(false)
    setScanning(false)
    addMsg('system', '■ Capture stopped')
  }, [addMsg])

  // WebSocket + frame sending
  const connectWS = useCallback(() => {
    wsRef.current?.close()
    clearInterval(sendIntervalRef.current)

    const wsUrl = new URL('/ws/vision', window.location.href)
    wsUrl.protocol = wsUrl.protocol === 'https:' ? 'wss:' : 'ws:'
    const apiKey = (import.meta as any).env?.VITE_OMNI_AGENT_API_KEY as string | undefined
    if (apiKey) wsUrl.searchParams.set('api_key', apiKey)

    const ws = new WebSocket(wsUrl.toString())
    wsRef.current = ws
    ws.onopen = () => { setConnected(true); addMsg('system', '🔗 Connected to OmniSight backend') }
    ws.onclose = () => {
      setConnected(false)
      setScanning(false)
      clearInterval(sendIntervalRef.current)
      addMsg('warn', '⚠  WS disconnected')
    }
    ws.onerror = () => { addMsg('error', '✗ Backend unavailable — demo mode active') }
    ws.onmessage = e => {
      try {
        const data = JSON.parse(e.data)
        if (data.type === 'analysis') {
          setAnalysis(data.result)
          const r: Analysis = data.result
          if (r.issues.length > 0) r.issues.forEach(i => addMsg('warn', `⚠  ${i}`))
          else if (r.elements.length > 0) addMsg('success', `✓  ${r.elements.length} elements — score ${r.score}`)
          addMsg('info', `💬 ${r.insights}`)
        }
      } catch (err) {
        console.error('WS message parse failed', err)
      }
    }
  }, [addMsg])

  useEffect(() => {
    if (!capturing || !connected) return
    const ws = wsRef.current
    if (!ws || ws.readyState !== WebSocket.OPEN) return

    setScanning(true)
    clearInterval(sendIntervalRef.current)

    sendIntervalRef.current = setInterval(() => {
      const video = videoRef.current; const canvas = captureRef.current
      if (!video || !canvas || video.readyState < 2 || ws.readyState !== WebSocket.OPEN) return
      canvas.width = video.videoWidth || 1280; canvas.height = video.videoHeight || 720
      const ctx = canvas.getContext('2d')
      if (!ctx) return
      ctx.drawImage(video, 0, 0)
      const frame = canvas.toDataURL('image/jpeg', 0.6).split(',')[1]
      ws.send(JSON.stringify({ type: 'frame', data: frame, w: canvas.width, h: canvas.height }))
      frameCountRef.current++
      const now = Date.now()
      if (now - lastFpsTs.current >= 1000) {
        setFps(frameCountRef.current)
        frameCountRef.current = 0; lastFpsTs.current = now
      }
    }, 500)

    return () => {
      clearInterval(sendIntervalRef.current)
    }
  }, [capturing, connected])

  // Score color
  const scoreColor = analysis.score >= 80 ? '#00ff88' : analysis.score >= 60 ? '#ff6b35' : '#ff3366'
  const scoreLabel = analysis.score >= 80 ? 'GOOD' : analysis.score >= 60 ? 'NEEDS WORK' : analysis.score > 0 ? 'ISSUES FOUND' : '—'

  return (
    <div className="app-root">
      {/* Header */}
      <header className="header">
        <div className="header-left">
          <span className="logo">⬡ OMNISIGHT</span>
          <span className="logo-sub">Visual Dev Agent</span>
          <span className="badge badge-hackathon">WeMakeDevs VisionPossible</span>
        </div>
        <div className="header-right">
          {scanning && <span className="pulse-dot" />}
          <span className={`status-chip ${connected ? 'status-green' : demoMode ? 'status-purple' : 'status-dim'}`}>
            {connected ? '● LIVE' : demoMode ? '◉ DEMO' : '○ IDLE'}
          </span>
          <span className="stat-chip">FPS {fps}</span>
          <span className="stat-chip">{analysis.elements.length} elem</span>
          {analysis.score > 0 && (
            <span className="stat-chip" style={{ color: scoreColor }}>
              ▮ {analysis.score}/100
            </span>
          )}
        </div>
      </header>

      {/* Main */}
      <main className="main">
        {/* Video area */}
        <section className="video-section">
          <div className="video-wrapper">
            <video ref={videoRef} className="video-el" muted playsInline />
            {/* Placeholder when not capturing */}
            {!capturing && (
              <div className="video-placeholder">
                <div className="placeholder-content">
                  <div className="placeholder-icon">⬡</div>
                  <p className="placeholder-title">Vision Agent Ready</p>
                  <p className="placeholder-sub">Capture your screen or run demo</p>
                  <div className="placeholder-grid">
                    {['YOLO', 'Moondream', 'Gemini Vision', 'Claude Vision'].map(m => (
                      <span key={m} className="model-tag">{m}</span>
                    ))}
                  </div>
                </div>
                {/* Animated corner brackets */}
                <div className="corner tl" /><div className="corner tr" />
                <div className="corner bl" /><div className="corner br" />
              </div>
            )}
            {/* Scan line */}
            {scanning && <div className="scan-line" />}
            {/* Analysis overlay canvas */}
            <canvas
              ref={overlayRef}
              className="overlay-canvas"
              width={1280}
              height={720}
            />
            {/* Score badge in corner */}
            {analysis.score > 0 && (
              <div className="score-badge" style={{ borderColor: scoreColor, color: scoreColor }}>
                <div className="score-num">{analysis.score}</div>
                <div className="score-lbl">{scoreLabel}</div>
              </div>
            )}
          </div>

          {/* Insights bar */}
          {analysis.insights && (
            <div className="insights-bar">
              <span className="insights-icon">◉</span>
              <span className="insights-text">{analysis.insights}</span>
            </div>
          )}

          {/* Issues pills */}
          {analysis.issues.length > 0 && (
            <div className="issues-row">
              {analysis.issues.map((iss, i) => (
                <div key={i} className="issue-pill">⚠ {iss}</div>
              ))}
            </div>
          )}

          {/* Element legend */}
          {analysis.elements.length > 0 && (
            <div className="legend-row">
              {[...new Set(analysis.elements.map(e => e.type))].map(t => (
                <span key={t} className="legend-chip" style={{ borderColor: ELEMENT_COLORS[t] ?? '#00d4ff', color: ELEMENT_COLORS[t] ?? '#00d4ff' }}>
                  ● {t}
                </span>
              ))}
            </div>
          )}
        </section>

        {/* Agent feed */}
        <aside className="agent-sidebar">
          <div className="sidebar-header">
            <span className="sidebar-title">◈ AGENT FEED</span>
            <button className="clear-btn" onClick={() => setMessages([])}>clear</button>
          </div>
          <div ref={feedRef} className="feed">
            {messages.length === 0 && (
              <div className="feed-empty">Start capture or demo to see agent analysis…</div>
            )}
            {messages.map(m => (
              <div key={m.id} className="feed-msg" style={{ '--kind-color': kindColor[m.kind] } as React.CSSProperties}>
                <span className="feed-icon" style={{ color: kindColor[m.kind] }}>{kindIcon[m.kind]}</span>
                <span className="feed-text">{m.text}</span>
                <span className="feed-ts">{m.ts}</span>
              </div>
            ))}
          </div>
          {/* Score gauge */}
          <div className="score-panel">
            <div className="score-label-row">
              <span className="score-panel-title">UI QUALITY SCORE</span>
              <span className="score-panel-val" style={{ color: scoreColor }}>{analysis.score > 0 ? analysis.score : '—'}</span>
            </div>
            <div className="score-track">
              <div
                className="score-fill"
                style={{ width: `${analysis.score}%`, background: scoreColor, boxShadow: `0 0 10px ${scoreColor}` }}
              />
            </div>
          </div>
        </aside>
      </main>

      {/* Controls */}
      <footer className="controls">
        <div className="controls-left">
          {!capturing ? (
            <button className="btn btn-primary" onClick={startCapture}>▶ Capture Screen</button>
          ) : (
            <button className="btn btn-danger" onClick={stopCapture}>■ Stop</button>
          )}
          <button className="btn btn-accent" onClick={runDemo} disabled={demoMode || capturing}>◉ Run Demo</button>
        </div>
        <div className="controls-right">
          {!connected ? (
            <button className="btn btn-outline" onClick={connectWS}>⬡ Connect Backend</button>
          ) : (
            <button className="btn btn-outline btn-active" onClick={() => { wsRef.current?.close(); setConnected(false) }}>
              ⬡ Disconnect
            </button>
          )}
          <a
            className="btn btn-ghost"
            href="https://github.com/wildhash/omni-agent"
            target="_blank" rel="noreferrer"
          >
            ↗ GitHub
          </a>
        </div>
      </footer>

      {/* Hidden capture canvas */}
      <canvas ref={captureRef} style={{ display: 'none' }} />
    </div>
  )
}
