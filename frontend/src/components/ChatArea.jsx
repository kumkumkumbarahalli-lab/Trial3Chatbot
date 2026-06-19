import { useEffect, useRef, useState } from 'react'
import './ChatArea.css'
import { FiSend, FiChevronLeft, FiChevronRight } from 'react-icons/fi'

export default function ChatArea({
  messages,
  onSendMessage,
  loading,
  starterPrompts,
  showLeftSidebar,
  showRightSidebar,
  onToggleLeftSidebar,
  onToggleRightSidebar,
}) {
  const [inputValue, setInputValue] = useState('')
  const messagesEndRef = useRef(null)
  const showLandingState =
    messages.length === 1 &&
    messages[0]?.role === 'assistant' &&
    !loading

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const handleSend = () => {
    if (inputValue.trim() && !loading) {
      onSendMessage(inputValue)
      setInputValue('')
    }
  }

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className="chat-area">
      <div className="chat-header">
        <div className="chat-header-left">
          <h1>KANTAR BrandEcho</h1>
        </div>
      </div>

      <button
        className={`edge-toggle right ${showRightSidebar ? 'open' : 'closed'}`}
        type="button"
        onClick={onToggleRightSidebar}
        title={showRightSidebar ? 'Hide right sidebar' : 'Show right sidebar'}
      >
        {showRightSidebar ? <FiChevronRight size={18} /> : <FiChevronLeft size={18} />}
      </button>

      <div className="messages-container">
        {showLandingState ? (
          <div className="landing-state">
            <div className="landing-orb"></div>
            <div className="landing-copy">
              <h2>KANTAR BrandEcho</h2>
              <p>Search brand analytics projects through natural language</p>
            </div>

            <div className="starter-grid">
              {starterPrompts.map((prompt) => (
                <button
                  key={prompt}
                  type="button"
                  className="starter-card"
                  onClick={() => onSendMessage(prompt)}
                >
                  {prompt}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="messages-list">
            {messages.map((msg, idx) => (
              <div key={idx} className={`message-wrapper ${msg.role}`}>
                <div className={`message ${msg.role}`}>
                  <p>{msg.content}</p>
                </div>
              </div>
            ))}
            {loading && (
              <div className="message-wrapper assistant">
                <div className="message assistant">
                  <div className="loading-dots">
                    <span></span>
                    <span></span>
                    <span></span>
                  </div>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      <div className="input-area">
        <div className="input-wrapper">
          <textarea
            className="message-input"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="Ask about project categories, brands, markets and factors."
            rows="1"
            disabled={loading}
          />
          <button
            className="send-btn"
            onClick={handleSend}
            disabled={loading || !inputValue.trim()}
            title="Send message"
          >
            <FiSend size={18} />
          </button>
        </div>
        <p className="input-hint">
          Responses may be inaccurate. Cross-reference the database.
        </p>
      </div>
    </div>
  )
}
