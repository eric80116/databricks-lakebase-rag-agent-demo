import { useEffect, useState } from 'react'

/** Developer panel: how to call the agent API + one-click copy of a runnable
 *  single-line curl command (token embedded) or just the token. */
export default function DevPanel() {
  const [open, setOpen] = useState(false)
  const [agentUrl, setAgentUrl] = useState<string>('')
  const [status, setStatus] = useState<string>('')

  useEffect(() => {
    if (open && !agentUrl) {
      fetch('/api/info').then((r) => r.json()).then((d) => setAgentUrl(d.agent_api_url || '')).catch(() => {})
    }
  }, [open, agentUrl])

  const base = agentUrl || '<AGENT_API_URL>'
  // SINGLE-LINE command (no backslash line-continuations — pastes/runs reliably).
  const cmd = (tok: string) =>
    `curl -X POST "${base}/api/chat" -H "Authorization: Bearer ${tok}" ` +
    `-H "Content-Type: application/json" ` +
    `-d '{"session_id":"demo","message":"How much does Sentiva Shield cost?"}'`

  const display = cmd('$TOKEN')

  function flash(msg: string, ms = 4000) {
    setStatus(msg)
    setTimeout(() => setStatus(''), ms)
  }
  async function write(text: string, label: string) {
    try { await navigator.clipboard.writeText(text); flash(`✓ ${label} copied`) }
    catch { flash('Copy failed — select the text manually') }
  }
  async function getToken(): Promise<{ token?: string; kind?: string; note?: string; detail?: string }> {
    const r = await fetch('/api/token'); return r.json()
  }
  async function copyRunnable() {
    flash('Generating token…', 8000)
    try {
      const d = await getToken()
      if (d.token) await write(cmd(d.token), `runnable command (${d.kind})`)
      else flash(`No token: ${d.detail || 'unavailable'}`)
    } catch { flash('Token request failed') }
  }
  async function copyToken() {
    flash('Generating token…', 8000)
    try {
      const d = await getToken()
      if (d.token) await write(d.token, `token (${d.kind}, ${d.note || '~1h'})`)
      else flash(`No token: ${d.detail || 'unavailable'}`)
    } catch { flash('Token request failed') }
  }

  const box: React.CSSProperties = {
    background: '#0d1117', color: '#e6edf3', padding: '12px 14px', borderRadius: 8,
    fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace', fontSize: 12.5,
    whiteSpace: 'pre-wrap', wordBreak: 'break-all', lineHeight: 1.5, margin: '8px 0',
  }
  const btn: React.CSSProperties = {
    border: '1px solid #6366f1', background: '#6366f1', color: '#fff',
    borderRadius: 6, padding: '6px 12px', fontSize: 13, cursor: 'pointer', marginRight: 8, marginBottom: 6,
  }
  const ghost: React.CSSProperties = { ...btn, background: 'transparent', color: '#6366f1' }

  return (
    <div style={{ maxWidth: 820, margin: '0 auto', padding: '0 16px' }}>
      <button style={{ ...ghost, marginTop: 8 }} onClick={() => setOpen(!open)}>
        {open ? '▾ Developer / API access' : '▸ Developer / API access'}
      </button>
      {open && (
        <div style={{ border: '1px solid #e5e7eb', borderRadius: 10, padding: 16, marginTop: 8 }}>
          <div style={{ fontSize: 13, opacity: 0.8, marginBottom: 6 }}>
            Call the Sentiva agent from your product / terminal. Single-line command; the token
            is a short-lived workspace bearer token (demo convenience).
          </div>
          <div style={box}>{display}</div>
          <div>
            <button style={btn} onClick={copyRunnable}>Copy runnable command (token embedded)</button>
            <button style={ghost} onClick={copyToken}>Copy token</button>
            {agentUrl && <button style={ghost} onClick={() => write(agentUrl, 'API URL')}>Copy API URL</button>}
          </div>
          <div style={{ fontSize: 12.5, minHeight: 18, marginTop: 8, color: '#059669' }}>{status}</div>
          <div style={{ fontSize: 11.5, opacity: 0.6, marginTop: 4 }}>
            "Copy runnable command" pastes a ready-to-run one-liner. Or use "Copy token", then
            <code> export TOKEN=&lt;paste&gt;</code> and run the command shown above.
          </div>
        </div>
      )}
    </div>
  )
}
