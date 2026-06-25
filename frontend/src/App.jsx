import { useState, useEffect } from 'react'
import './App.css'
import LeftSidebar from './components/LeftSidebar'
import ChatArea from './components/ChatArea'
import DashboardView from './components/DashboardView'
import RightSidebar from './components/RightSidebar'
import { apiCall } from './utils/api'

const LEFT_SIDEBAR_MIN = 220
const LEFT_SIDEBAR_MAX = 420
const RIGHT_SIDEBAR_MIN = 220
const RIGHT_SIDEBAR_MAX = 420

const STARTER_PROMPTS = [
  'Top 5 categories by number of brand models',
  'Have we worked in Dubai before?',
  'List the sub categories in Home Decor',
  'How many markets have we worked with Nescafe?',
  'Which brand models are most diversified across markets?',
  'What clients have we worked with in Egypt?',
  'How many Banking projects have we done?',
  'Which categories are present in both India and Egypt?'
]

const WELCOME_MESSAGE = 'Insight mode on. Explore projects by category, brand model, market, or client.'

const EMPTY_RETRIEVAL_NOTE = 'No retrieval yet. Ask a question to see retrieval output.'

function createChatId() {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
}

function createDefaultMessages() {
  return [
    {
      role: 'assistant',
      content: WELCOME_MESSAGE,
    },
  ]
}

function createChatState(id) {
  return {
    id,
    name: 'New Chat',
    createdAt: new Date(),
    messages: createDefaultMessages(),
    lastRoute: null,
    lastRawRoute: null,
    lastMergedRoute: null,
    routeHistory: [],
    lastProjects: [],
    lastFactors: [],
    lastRetrievalNote: EMPTY_RETRIEVAL_NOTE,
  }
}

function App() {
  const [isDarkMode, setIsDarkMode] = useState(false)
  const [showLeftSidebar, setShowLeftSidebar] = useState(true)
  const [showRightSidebar, setShowRightSidebar] = useState(true)
  const [leftSidebarWidth, setLeftSidebarWidth] = useState(245)
  const [rightSidebarWidth, setRightSidebarWidth] = useState(252)
  const [chats, setChats] = useState([])
  const [currentChatId, setCurrentChatId] = useState(null)
  const [messages, setMessages] = useState(createDefaultMessages)
  const [lastRoute, setLastRoute] = useState(null)
  const [lastRawRoute, setLastRawRoute] = useState(null)
  const [lastMergedRoute, setLastMergedRoute] = useState(null)
  const [routeHistory, setRouteHistory] = useState([])
  const [lastProjects, setLastProjects] = useState([])
  const [lastFactors, setLastFactors] = useState([])
  const [lastRetrievalNote, setLastRetrievalNote] = useState(EMPTY_RETRIEVAL_NOTE)
  const [activeView, setActiveView] = useState('chat')
  const [dashboardData, setDashboardData] = useState(null)
  const [dashboardLoading, setDashboardLoading] = useState(false)
  const [dashboardError, setDashboardError] = useState('')
  const [selectedDashboardCategory, setSelectedDashboardCategory] = useState('')
  const [loading, setLoading] = useState(false)

  // Initialize with one empty chat
  useEffect(() => {
    const initialChatId = createChatId()
    const initialChat = createChatState(initialChatId)
    setChats([initialChat])
    setCurrentChatId(initialChatId)
    setMessages(initialChat.messages)
    setLastRoute(initialChat.lastRoute)
    setLastRawRoute(initialChat.lastRawRoute)
    setLastMergedRoute(initialChat.lastMergedRoute)
    setRouteHistory(initialChat.routeHistory)
    setLastProjects(initialChat.lastProjects)
    setLastFactors(initialChat.lastFactors)
    setLastRetrievalNote(initialChat.lastRetrievalNote)
  }, [])

  // Toggle theme
  const toggleTheme = () => {
    setIsDarkMode(!isDarkMode)
  }

  const toggleLeftSidebar = () => {
    setShowLeftSidebar((prev) => !prev)
  }

  const toggleRightSidebar = () => {
    setShowRightSidebar((prev) => !prev)
  }

  const loadDashboardData = async (categoryValue = selectedDashboardCategory) => {
    setDashboardLoading(true)
    setDashboardError('')

    try {
      const query = categoryValue
        ? `/api/dashboard-summary?selected_category=${encodeURIComponent(categoryValue)}`
        : '/api/dashboard-summary'
      const response = await apiCall('GET', query)
      setDashboardData(response)

      const serverSelected = response?.slicers?.selected_category || ''
      if (serverSelected && serverSelected !== selectedDashboardCategory) {
        setSelectedDashboardCategory(serverSelected)
      }
    } catch (error) {
      setDashboardError(`Unable to load dashboard data. ${error.message}`)
    } finally {
      setDashboardLoading(false)
    }
  }

  const openDashboard = async () => {
    setActiveView('dashboard')
    setShowRightSidebar(false)

    if (dashboardLoading) {
      return
    }

    await loadDashboardData(selectedDashboardCategory)
  }

  const handleDashboardCategoryChange = async (nextCategory) => {
    setSelectedDashboardCategory(nextCategory)
    await loadDashboardData(nextCategory)
  }

  const startSidebarResize = (side, event) => {
    event.preventDefault()

    const startX = event.clientX
    const startWidth = side === 'left' ? leftSidebarWidth : rightSidebarWidth

    document.body.style.userSelect = 'none'
    document.body.style.cursor = 'col-resize'

    const handleMouseMove = (moveEvent) => {
      const deltaX = moveEvent.clientX - startX

      if (side === 'left') {
        const nextWidth = clamp(
          startWidth + deltaX,
          LEFT_SIDEBAR_MIN,
          LEFT_SIDEBAR_MAX
        )
        setLeftSidebarWidth(nextWidth)
        return
      }

      const nextWidth = clamp(
        startWidth - deltaX,
        RIGHT_SIDEBAR_MIN,
        RIGHT_SIDEBAR_MAX
      )
      setRightSidebarWidth(nextWidth)
    }

    const stopResizing = () => {
      document.removeEventListener('mousemove', handleMouseMove)
      document.removeEventListener('mouseup', stopResizing)
      document.body.style.userSelect = ''
      document.body.style.cursor = ''
    }

    document.addEventListener('mousemove', handleMouseMove)
    document.addEventListener('mouseup', stopResizing)
  }

  // Create new chat
  const createNewChat = () => {
    const chatId = createChatId()
    const newChat = createChatState(chatId)

    setChats((prevChats) => [newChat, ...prevChats])
    setCurrentChatId(chatId)
    setMessages(newChat.messages)
    setLastRoute(newChat.lastRoute)
    setLastRawRoute(newChat.lastRawRoute)
    setLastMergedRoute(newChat.lastMergedRoute)
    setRouteHistory(newChat.routeHistory)
    setLastProjects(newChat.lastProjects)
    setLastFactors(newChat.lastFactors)
    setLastRetrievalNote(newChat.lastRetrievalNote)
    setActiveView('chat')
  }

  // Switch to existing chat
  const switchChat = (chatId) => {
    const selectedChat = chats.find((chat) => chat.id === chatId)
    if (!selectedChat) return

    setCurrentChatId(chatId)
    setActiveView('chat')
    setMessages(selectedChat.messages || createDefaultMessages())
    setLastRoute(selectedChat.lastRoute || null)
    setLastRawRoute(selectedChat.lastRawRoute || null)
    setLastMergedRoute(selectedChat.lastMergedRoute || null)
    setRouteHistory(selectedChat.routeHistory || [])
    setLastProjects(selectedChat.lastProjects || [])
    setLastFactors(selectedChat.lastFactors || [])
    setLastRetrievalNote(selectedChat.lastRetrievalNote || EMPTY_RETRIEVAL_NOTE)
  }

  const renameChat = (chatId, nextName) => {
    const trimmedName = nextName.trim()
    if (!trimmedName) return

    setChats((prevChats) =>
      prevChats.map((chat) =>
        chat.id === chatId ? { ...chat, name: trimmedName } : chat
      )
    )
  }

  // Handle sending message
  const handleSendMessage = async (question) => {
    if (!question.trim()) return
    if (!currentChatId) return

    // Add user message
    const updatedMessages = [...messages, { role: 'user', content: question }]
    setMessages(updatedMessages)
    setLoading(true)

    try {
      // Step 1: Route the query
      const routeResp = await apiCall('POST', '/api/route-query', {
        question,
        history: updatedMessages.slice(0, -1),
        route_history: routeHistory,
      })
      const route = routeResp.merged_route || routeResp
      const rawRoute = routeResp.raw_route || route
      const mergedRoute = routeResp.merged_route || route

      setLastRoute(route)
      setLastRawRoute(rawRoute)
      setLastMergedRoute(mergedRoute)
      setRouteHistory((prev) => [...prev, mergedRoute])

      let answer = ''
      let projects = []
      let factors = []
      let retrievalNote = EMPTY_RETRIEVAL_NOTE

      const hasPriorContext = lastProjects.length > 0 || lastFactors.length > 0

      if (route.intent === 'follow_up' && !hasPriorContext) {
        answer = "That's a follow-up, but I don't have context from a previous question. Start fresh-what brand model, market, or category interests you?"
        retrievalNote = 'Follow-up attempted without prior context - clarification requested.'
      } else if (route.intent === 'analytics') {
        const analyticsResp = await apiCall('POST', '/api/analytics-answer', {
          question,
          route,
        })
        answer = analyticsResp.answer || 'No data found for that query.'
        projects = analyticsResp.projects || []
        retrievalNote =
          analyticsResp.analytics_type
            ? `Analytics query: ${analyticsResp.analytics_type} (limit ${analyticsResp.analytics_limit || 10}) - pre-computed stats passed to answer model.`
            : 'Analytics query but no type specified.'
      } else if (route.intent === 'clarify') {
        answer = route.clarification_question || 'Can you clarify?'
        retrievalNote = 'Routing requested clarification.'
      } else {
        const isFactorQuery = route.intent === 'factor_lookup' || !!route.factor_type_hint

        if (isFactorQuery) {
          // Step 2a: Filter directly from factors-db
          const factorsFilterResp = await apiCall('POST', '/api/filter-factors', route)
          factors = factorsFilterResp.factors || []
          projects = factorsFilterResp.projects || []

          if (factorsFilterResp.clarification_message) {
            answer = factorsFilterResp.clarification_message
            retrievalNote = 'Multiple projects in factors-db; awaiting disambiguation.'
          } else if (factors.length === 0) {
            answer = 'I could not find any factors matching your criteria in the factors database.'
            retrievalNote = 'No factors matched the filters in factors-db.'
          } else {
            answer = formatFactorsResponse(factors)
            retrievalNote = 'Factor retrieval from factors-db completed.'
          }
        } else {
          // Step 2b: Filter projects from complete-db for non-factor queries
          const filterResp = await apiCall('POST', '/api/filter-projects', route)
          projects = filterResp.projects || []

          if (filterResp.clarification_message) {
            answer = filterResp.clarification_message
            retrievalNote = 'Clarification needed due to ambiguous filters.'
          } else if (projects.length === 0) {
            if (route.intent === 'follow_up') {
              const contextSummary = getContextSummary(lastProjects)
              answer = `That did not narrow it down. We were just discussing ${contextSummary}. Can you be more specific?`
              retrievalNote = 'Follow-up returned no matches - provided context reminder.'
            } else {
              answer = 'I could not find a matching project in the database.'
              retrievalNote = 'No project rows matched the current filters.'
            }
          } else {
            // Step 3: Get answer from Groq
            const answerResp = await apiCall('POST', '/api/answer', {
              question,
              route,
              project_rows: projects,
              factor_rows: factors,
            })
            answer = answerResp.answer
            retrievalNote = 'Project retrieval completed and passed to answer model.'
          }
        }
      }

      setLastProjects(projects)
      setLastFactors(factors)
      setLastRetrievalNote(retrievalNote)

      // Add assistant response
      const finalMessages = [...updatedMessages, { role: 'assistant', content: answer }]
      setMessages(finalMessages)
      const latestRouteHistory = [...routeHistory, mergedRoute]

      setChats((prevChats) =>
        prevChats.map((chat) =>
          chat.id === currentChatId
            ? {
                ...chat,
                name: question.substring(0, 30) + (question.length > 30 ? '...' : ''),
                messages: finalMessages,
                lastRoute: route,
                lastRawRoute: rawRoute,
                lastMergedRoute: mergedRoute,
                routeHistory: latestRouteHistory,
                lastProjects: projects,
                lastFactors: factors,
                lastRetrievalNote: retrievalNote,
              }
            : chat
        )
      )

    } catch (error) {
      console.error('Error:', error)
      const errorMessage = `Error: ${error.message}`
      const erroredMessages = [...updatedMessages, { role: 'assistant', content: errorMessage }]
      setMessages(erroredMessages)
      setChats((prevChats) =>
        prevChats.map((chat) =>
          chat.id === currentChatId
            ? {
                ...chat,
                messages: erroredMessages,
              }
            : chat
        )
      )
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className={`app ${isDarkMode ? 'dark' : 'light'}`}>
      <LeftSidebar
        chats={chats}
        currentChatId={currentChatId}
        onSelectChat={switchChat}
        onNewChat={createNewChat}
        onOpenDashboard={openDashboard}
        onRenameChat={renameChat}
        onToggleSidebar={toggleLeftSidebar}
        isDashboardActive={activeView === 'dashboard'}
        collapsed={!showLeftSidebar}
        width={leftSidebarWidth}
        onStartResize={(event) => startSidebarResize('left', event)}
      />

      {activeView === 'dashboard' ? (
        <DashboardView
          data={dashboardData}
          loading={dashboardLoading}
          error={dashboardError}
          onCategoryChange={handleDashboardCategoryChange}
        />
      ) : (
        <ChatArea
          messages={messages}
          onSendMessage={handleSendMessage}
          loading={loading}
          starterPrompts={STARTER_PROMPTS}
          isDarkMode={isDarkMode}
          onToggleTheme={toggleTheme}
          showLeftSidebar={showLeftSidebar}
          showRightSidebar={showRightSidebar}
          onToggleLeftSidebar={toggleLeftSidebar}
          onToggleRightSidebar={toggleRightSidebar}
        />
      )}

      {showRightSidebar && activeView !== 'dashboard' && (
        <RightSidebar
          lastRoute={lastRoute}
          lastRawRoute={lastRawRoute}
          lastMergedRoute={lastMergedRoute}
          lastProjects={lastProjects}
          lastFactors={lastFactors}
          lastRetrievalNote={lastRetrievalNote}
          width={rightSidebarWidth}
          onStartResize={(event) => startSidebarResize('right', event)}
        />
      )}
    </div>
  )
}

function getContextSummary(projects) {
  if (!projects || projects.length === 0) {
    return 'no previous context'
  }

  const brands = [...new Set(projects.map((p) => p.BrandModelled).filter(Boolean))]
  const markets = [...new Set(projects.map((p) => p.MarketforBrand).filter(Boolean))]
  const parts = []

  if (brands.length > 0) {
    parts.push(`Brand models: ${brands.join(', ')}`)
  }
  if (markets.length > 0) {
    parts.push(`Markets: ${markets.join(', ')}`)
  }

  return parts.join(' | ') || 'no previous context'
}

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value))
}

function formatFactorsResponse(factors) {
  if (!factors || factors.length === 0) {
    return 'No linked factor rows found for this selection.'
  }

  // Sort by sequence if available, like main.py does
  let sorted = [...factors]
  if (factors.some(f => f.sequence !== undefined)) {
    sorted.sort((a, b) => (a.sequence || 999) - (b.sequence || 999))
  }

  // Group by FactorType and track first seen index
  const grouped = {}
  const firstSeen = {}
  sorted.forEach((factor, idx) => {
    const type = factor.FactorType || 'Unknown'
    if (!grouped[type]) {
      grouped[type] = []
      firstSeen[type] = idx
    }
    if (!grouped[type].includes(factor.FactorName)) {
      grouped[type].push(factor.FactorName)
    }
  })

  const rankFactorType = (type) => {
    const t = type.toLowerCase()
    if (t === 'dv' || t === 'dependent variable' || t === 'dependentvar') return 0
    if (t === 'kpi' || t === 'kpis') return 1
    return 2
  }

  // Sort types by rank, then by first-seen index (like main.py)
  const types = Object.keys(grouped).sort((a, b) => {
    const rankDiff = rankFactorType(a) - rankFactorType(b)
    if (rankDiff !== 0) return rankDiff
    return (firstSeen[a] || 99999) - (firstSeen[b] || 99999)
  })

  const lines = []
  types.forEach((type) => {
    lines.push(type)
    grouped[type].forEach((name) => {
      lines.push(`- ${name}`)
    })
    lines.push('')
  })

  return lines.join('\n').trim() || 'No linked factor rows found for this selection.'
}

export default App
