import React, { useState } from 'react'

interface Source {
  title: string
  source_uri: string
  product: string
  lang: string
}

interface Timings {
  retrieval_ms: number
  llm_ms: number
  total_ms: number
}

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  sources?: Source[]
  timings?: Timings
  trace_id?: string
}

interface MessageBubbleProps {
  message: Message
}

const MessageBubble: React.FC<MessageBubbleProps> = ({ message }) => {
  const [sourcesExpanded, setSourcesExpanded] = useState(true)

  return (
    <div className={`message ${message.role}`}>
      <div className="message-bubble">
        {message.content}

        {message.role === 'assistant' && (
          <>
            {message.sources && message.sources.length > 0 && (
              <div className="sources-section">
                <div
                  className={`sources-toggle ${!sourcesExpanded ? 'collapsed' : ''}`}
                  onClick={() => setSourcesExpanded(!sourcesExpanded)}
                >
                  <span className="toggle-arrow">▼</span>
                  <span>Sources ({message.sources.length})</span>
                </div>
                {sourcesExpanded && (
                  <div className="sources-list">
                    {message.sources.map((source, idx) => (
                      <div key={idx} className="source-item">
                        <div className="source-title">{source.title}</div>
                        <div className="source-meta">
                          <span className="source-badge product">
                            {source.product}
                          </span>
                          <span className="source-badge lang">
                            {source.lang.toUpperCase()}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {message.timings && (
              <div>
                <div className="timings">
                  <span>Retrieval: {message.timings.retrieval_ms}ms</span>
                  <span>LLM: {message.timings.llm_ms}ms</span>
                  <span>Total: {message.timings.total_ms}ms</span>
                </div>
                {message.trace_id && (
                  <div className="trace-id">Trace: {message.trace_id}</div>
                )}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}

export default MessageBubble
