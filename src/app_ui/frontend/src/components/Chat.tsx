import React, { useState, useEffect, useRef, useCallback } from 'react'
import { v4 as uuidv4 } from 'uuid'
import MessageBubble from './MessageBubble'
import SuggestionCards from './SuggestionCards'
import TypingIndicator from './TypingIndicator'

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  sources?: Array<{
    title: string
    source_uri: string
    product: string
    lang: string
  }>
  timings?: {
    retrieval_ms: number
    llm_ms: number
    total_ms: number
  }
  trace_id?: string
}

// NOTE: keep these within the knowledge-base coverage so every card returns a
// grounded answer. KB today: Shield (overview/pricing/features/setup/privacy/
// troubleshooting), Alert (overview/pricing/features), Family/ID/Scan (overview),
// Plans (comparison). Detailed how-to only exists for Shield/Alert.
const SUGGESTION_QUESTIONS = [
  {
    text: 'How much does Sentiva Shield cost?',
    lang: 'en',
  },
  {
    text: 'Sentiva Shield の設定方法を教えて',
    lang: 'ja',
  },
  {
    text: 'Comment Sentiva Alert détecte-t-il les arnaques ?',
    lang: 'fr',
  },
  {
    text: 'Was kann Sentiva Family für Kinder tun?',
    lang: 'de',
  },
  {
    text: 'What does Sentiva ID protect?',
    lang: 'en',
  },
  {
    text: 'Sentiva Scan とは何ですか?',
    lang: 'ja',
  },
  {
    text: 'Quels appareils Sentiva Shield protège-t-il ?',
    lang: 'fr',
  },
  {
    text: 'Sentiva Shield reagiert langsam – was kann ich tun?',
    lang: 'de',
  },
]

const Chat: React.FC = () => {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [sessionId, setSessionId] = useState<string>('')
  const [showSuggestions, setShowSuggestions] = useState(true)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  // Initialize session
  useEffect(() => {
    const stored = localStorage.getItem('sentiva_session_id')
    const id = stored || uuidv4()
    setSessionId(id)
    if (!stored) {
      localStorage.setItem('sentiva_session_id', id)
    }
  }, [])

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [])

  useEffect(() => {
    scrollToBottom()
  }, [messages, scrollToBottom])

  const handleSendMessage = useCallback(
    async (text: string) => {
      if (!text.trim() || loading || !sessionId) return

      const userMessage: Message = {
        id: uuidv4(),
        role: 'user',
        content: text,
      }
      const assistantId = uuidv4()

      // add the user turn + an empty assistant bubble that fills in as tokens stream
      setMessages((prev) => [
        ...prev,
        userMessage,
        { id: assistantId, role: 'assistant', content: '' },
      ])
      setInput('')
      setLoading(true)
      setError(null)
      setShowSuggestions(false)

      const patch = (id: string, fn: (m: Message) => Message) =>
        setMessages((prev) => prev.map((m) => (m.id === id ? fn(m) : m)))

      try {
        const response = await fetch('/api/chat/stream', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ session_id: sessionId, message: text }),
        })

        if (!response.ok || !response.body) {
          const errorData = await response.json().catch(() => ({}))
          throw new Error(
            errorData.detail || `API error: ${response.statusText}`
          )
        }

        const reader = response.body.getReader()
        const decoder = new TextDecoder()
        let buffer = ''
        let streamError: string | null = null

        // parse Server-Sent Events: newline-delimited `data: {json}` lines
        while (true) {
          const { done, value } = await reader.read()
          if (done) break
          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split('\n')
          buffer = lines.pop() ?? ''
          for (const line of lines) {
            const s = line.trim()
            if (!s.startsWith('data:')) continue
            let ev: any
            try {
              ev = JSON.parse(s.slice(5).trim())
            } catch {
              continue
            }
            if (ev.type === 'token') {
              setLoading(false) // first tokens arrived — drop the typing indicator
              patch(assistantId, (m) => ({ ...m, content: m.content + ev.text }))
            } else if (ev.type === 'done') {
              patch(assistantId, (m) => ({
                ...m,
                sources: ev.sources,
                timings: ev.timings,
                trace_id: ev.trace_id,
              }))
            } else if (ev.type === 'error') {
              streamError = ev.error
            }
          }
        }
        if (streamError) throw new Error(streamError)
      } catch (err) {
        const errorMsg =
          err instanceof Error ? err.message : 'Failed to send message'
        setError(errorMsg)
        // drop the empty assistant placeholder if nothing streamed
        setMessages((prev) =>
          prev.filter((m) => !(m.id === assistantId && !m.content))
        )
        console.error('Chat error:', err)
      } finally {
        setLoading(false)
      }
    },
    [loading, sessionId]
  )

  const handleSuggestionClick = (question: string) => {
    handleSendMessage(question)
  }

  // Start a fresh conversation: new session_id (so Lakebase memory starts clean) + clear UI.
  const handleNewConversation = useCallback(() => {
    if (loading) return
    const id = uuidv4()
    setSessionId(id)
    try {
      localStorage.setItem('sentiva_session_id', id)
    } catch {
      /* storage may be unavailable */
    }
    setMessages([])
    setShowSuggestions(true)
    setError(null)
    setInput('')
  }, [loading])

  return (
    <div className="chat-container">
      {messages.length > 0 && (
        <div className="chat-toolbar">
          <button
            className="new-chat-btn"
            onClick={handleNewConversation}
            disabled={loading}
            title="Start a new conversation (clears memory)"
          >
            <span aria-hidden="true">＋</span> New chat
          </button>
        </div>
      )}
      <div className="messages-area">
        {error && <div className="error-toast">{error}</div>}

        {messages.length === 0 && showSuggestions && (
          <div className="empty-state">
            <div className="empty-state-icon">🛡️</div>
            <div className="empty-state-text">
              Welcome to Sentiva Support
            </div>
            <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>
              Ask me anything about Sentiva products
            </p>
          </div>
        )}

        {messages.map((msg) => (
          <MessageBubble key={msg.id} message={msg} />
        ))}

        {loading && (
          <div className="message assistant">
            <TypingIndicator />
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {messages.length === 0 && showSuggestions && (
        <div style={{ padding: '1rem 1.5rem 0' }}>
          <SuggestionCards
            suggestions={SUGGESTION_QUESTIONS}
            onSelect={handleSuggestionClick}
          />
        </div>
      )}

      <div className="input-area">
        <div className="input-wrapper">
          <input
            type="text"
            className="input-field"
            placeholder="Ask about Sentiva products..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                handleSendMessage(input)
              }
            }}
            disabled={loading}
          />
          <button
            className="send-button"
            onClick={() => handleSendMessage(input)}
            disabled={loading || !input.trim()}
          >
            {loading ? '...' : 'Send'}
          </button>
        </div>
      </div>
    </div>
  )
}

export default Chat
