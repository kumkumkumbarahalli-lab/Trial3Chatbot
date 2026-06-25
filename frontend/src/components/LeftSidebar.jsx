import './LeftSidebar.css'
import { useMemo, useState } from 'react'
import { FiBarChart2, FiCheck, FiEdit2, FiMenu, FiMessageSquare, FiPlus, FiSearch, FiX } from 'react-icons/fi'

export default function LeftSidebar({
  chats,
  currentChatId,
  onSelectChat,
  onNewChat,
  onOpenDashboard,
  onRenameChat,
  onToggleSidebar,
  isDashboardActive,
  collapsed,
  width,
  onStartResize,
}) {
  const [searchTerm, setSearchTerm] = useState('')
  const [editingChatId, setEditingChatId] = useState(null)
  const [draftName, setDraftName] = useState('')

  const filteredChats = useMemo(() => {
    const query = searchTerm.trim().toLowerCase()
    if (!query) return chats

    return chats.filter((chat) => chat.name.toLowerCase().includes(query))
  }, [chats, searchTerm])

  const startRenaming = (chat) => {
    setEditingChatId(chat.id)
    setDraftName(chat.name)
  }

  const cancelRenaming = () => {
    setEditingChatId(null)
    setDraftName('')
  }

  const saveRename = (chatId) => {
    onRenameChat(chatId, draftName)
    cancelRenaming()
  }

  return (
    <div
      className={`left-sidebar ${collapsed ? 'collapsed' : ''}`}
      style={!collapsed ? { width: `${width}px`, flexBasis: `${width}px` } : undefined}
    >
      <div className="sidebar-topbar">
        {!collapsed && (
          <div className="app-branding">
            <h2 className="app-name">KANTAR BRANDECHO</h2>
          </div>
        )}
        <button
          className="menu-btn"
          type="button"
          aria-label={collapsed ? 'Show left sidebar' : 'Hide left sidebar'}
          onClick={onToggleSidebar}
        >
          <FiMenu size={22} />
        </button>
      </div>

      {!collapsed && (
        <>
          <button
            className={`dashboard-btn ${isDashboardActive ? 'active' : ''}`}
            onClick={onOpenDashboard}
          >
            <FiBarChart2 size={20} />
            <span>Dashboard</span>
          </button>

          <button className="new-chat-btn" onClick={onNewChat}>
            <FiPlus size={28} />
            <span>New Chat</span>
          </button>

          <label className="search-box" aria-label="Search chats">
            <FiSearch size={18} />
            <input
              className="search-input"
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Search chats"
            />
          </label>

          <div className="chats-section">
            <h4 className="section-title">RECENT</h4>
            <div className="chats-list">
              {filteredChats.length > 0 ? (
                filteredChats.map((chat) => {
                  const isEditing = editingChatId === chat.id

                  return (
                    <div
                      key={chat.id}
                      className={`chat-item ${chat.id === currentChatId ? 'active' : ''} ${isEditing ? 'editing' : ''}`}
                    >
                      <button
                        type="button"
                        className="chat-main"
                        onClick={() => !isEditing && onSelectChat(chat.id)}
                      >
                        <FiMessageSquare size={16} />
                        {isEditing ? (
                          <input
                            className="chat-rename-input"
                            type="text"
                            value={draftName}
                            onChange={(e) => setDraftName(e.target.value)}
                            onClick={(e) => e.stopPropagation()}
                            onKeyDown={(e) => {
                              if (e.key === 'Enter') {
                                e.preventDefault()
                                saveRename(chat.id)
                              }
                              if (e.key === 'Escape') {
                                e.preventDefault()
                                cancelRenaming()
                              }
                            }}
                            autoFocus
                          />
                        ) : (
                          <span className="chat-name">{chat.name}</span>
                        )}
                      </button>

                      <div className="chat-actions">
                        {isEditing ? (
                          <>
                            <button
                              type="button"
                              className="chat-action-btn"
                              onClick={() => saveRename(chat.id)}
                              aria-label="Save chat name"
                            >
                              <FiCheck size={14} />
                            </button>
                            <button
                              type="button"
                              className="chat-action-btn"
                              onClick={cancelRenaming}
                              aria-label="Cancel renaming"
                            >
                              <FiX size={14} />
                            </button>
                          </>
                        ) : (
                          <button
                            type="button"
                            className="chat-action-btn"
                            onClick={() => startRenaming(chat)}
                            aria-label="Rename chat"
                          >
                            <FiEdit2 size={14} />
                          </button>
                        )}
                      </div>
                    </div>
                  )
                })
              ) : (
                <p className="chat-empty-state">No chats match your search.</p>
              )}
            </div>
          </div>

          <div className="sidebar-footer">
            <span>Brand Model Structure Analytics · KAP</span>
          </div>
        </>
      )}

      {collapsed && (
        <>
          <div className="collapsed-shortcuts" aria-label="Collapsed sidebar actions">
            <button
              type="button"
              className={`collapsed-shortcut-btn ${isDashboardActive ? 'active' : ''}`}
              onClick={onOpenDashboard}
              aria-label="Open dashboard"
              title="Dashboard"
            >
              <FiBarChart2 size={18} />
            </button>

            <button
              type="button"
              className="collapsed-shortcut-btn"
              onClick={onNewChat}
              aria-label="Start new chat"
              title="New Chat"
            >
              <FiPlus size={20} />
            </button>
          </div>

          <div className="collapsed-rail-spacer" aria-hidden="true"></div>
        </>
      )}

      {!collapsed && (
        <div
          className="sidebar-resize-handle right"
          onMouseDown={onStartResize}
          role="separator"
          aria-label="Resize left sidebar"
          aria-orientation="vertical"
        ></div>
      )}
    </div>
  )
}
