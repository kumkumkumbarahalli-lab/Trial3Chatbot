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
  'Have we worked in Dubai before?',
  'How many Banking projects have we done?',
  'Have we worked near Coke or Pepsi’s space?',
  'What factors did we use for Beer brands?',
  'Show me all FMCG projects',
  'Which clients are repeat buyers?',
  'Have we worked in Southeast Asia?',
  'What emotional factors have we used for Food brands?',
]

const WELCOME_MESSAGE = 'Hi, I can answer from your Excel data. Ask me about a project, factor flow, brand, market, or dependent variable.'

function App() {
  const [isDarkMode, setIsDarkMode] = useState(false)
  const [showLeftSidebar, setShowLeftSidebar] = useState(true)
  const [showRightSidebar, setShowRightSidebar] = useState(true)
  const [leftSidebarWidth, setLeftSidebarWidth] = useState(272)
  const [rightSidebarWidth, setRightSidebarWidth] = useState(252)
  const [chats, setChats] = useState([])
  const [currentChatId, setCurrentChatId] = useState(null)
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      content: WELCOME_MESSAGE,
    },
  ])
  const [lastRoute, setLastRoute] = useState(null)
  const [lastProjects, setLastProjects] = useState([])
  const [lastFactors, setLastFactors] = useState([])
  const [lastRetrievalNote, setLastRetrievalNote] = useState('No retrieval yet. Ask a question to see retrieval output.')
  const [activeView, setActiveView] = useState('chat')
  const [dashboardData, setDashboardData] = useState(null)
  const [dashboardLoading, setDashboardLoading] = useState(false)
  const [dashboardError, setDashboardError] = useState('')
  const [selectedDashboardCategory, setSelectedDashboardCategory] = useState('')
  const [loading, setLoading] = useState(false)

  // Initialize with one empty chat
  useEffect(() => {
    const initialChatId = Date.now().toString()
    setChats([{ id: initialChatId, name: 'New Chat', createdAt: new Date() }])
    setCurrentChatId(initialChatId)
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
    const chatId = Date.now().toString()
    const newChat = { id: chatId, name: 'New Chat', createdAt: new Date() }
    setChats([newChat, ...chats])
    setCurrentChatId(chatId)
    setMessages([
      {
        role: 'assistant',
        content: WELCOME_MESSAGE,
      },
    ])
    setLastRoute(null)
    setLastProjects([])
    setLastFactors([])
    setLastRetrievalNote('No retrieval yet. Ask a question to see retrieval output.')
    setActiveView('chat')
  }

  // Switch to existing chat
  const switchChat = (chatId) => {
    setCurrentChatId(chatId)
    setActiveView('chat')
    // In a real app, you'd load the chat history from a database
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

    // Add user message
    const updatedMessages = [...messages, { role: 'user', content: question }]
    setMessages(updatedMessages)
    setLoading(true)

    try {
      // Step 1: Route the query
      const routeResp = await apiCall('POST', '/api/route-query', {
        question,
        history: updatedMessages.slice(0, -1),
      })
      const route = routeResp

      setLastRoute(route)

      let answer = ''
      let projects = []
      let factors = []

      if (route.intent === 'clarify') {
        answer = route.clarification_question || 'Can you clarify?'
        setLastRetrievalNote('Routing requested clarification.')
      } else {
        // Step 2: Filter projects
        const filterResp = await apiCall('POST', '/api/filter-projects', route)

        projects = filterResp.projects || []

        if (filterResp.clarification_message) {
          answer = filterResp.clarification_message
          setLastRetrievalNote('Clarification needed due to ambiguous filters.')
        } else if (projects.length === 0) {
          answer = 'I could not find a matching project in the database.'
          setLastRetrievalNote('No project rows matched the current filters.')
        } else {
          const isFactorQuery = route.intent === 'factor_lookup' || !!route.factor_type_hint

          if (
            isFactorQuery &&
            projects.length > 1 &&
            !route.coe_job_number_hint
          ) {
            // Get unique project combinations (like main.py's unique_project_options)
            const seen = new Set()
            const uniqueProjects = []
            projects.slice(0, 12).forEach((p) => {
              const key = JSON.stringify({
                BrandModelled: p.BrandModelled,
                MarketforBrand: p.MarketforBrand,
                CoEJobnumber: p.CoEJobnumber,
                Client: p.Client,
              })
              if (!seen.has(key)) {
                seen.add(key)
                uniqueProjects.push(p)
              }
            })

            const options = uniqueProjects
              .map((p, i) => {
                const bits = []
                if (p.BrandModelled) bits.push(`BrandModelled: ${p.BrandModelled}`)
                if (p.MarketforBrand) bits.push(`MarketforBrand: ${p.MarketforBrand}`)
                if (p.CoEJobnumber) bits.push(`CoEJobnumber: ${p.CoEJobnumber}`)
                if (p.Client) bits.push(`Client: ${p.Client}`)
                return `${i + 1}. ${bits.join(' | ')}`
              })
              .join('\n')

            answer = `I found multiple matching projects for factors. Please provide more detail (CoE job number, brand, market, or client).\n\nMatches:\n${options}`
            setLastRetrievalNote('Multiple projects matched a factor query; awaiting disambiguation.')
          } else {
            // Step 3: Fetch factors if needed
            if (isFactorQuery) {
              const factorsResp = await apiCall('POST', '/api/fetch-factors', {
                projects,
                route,
              })
              factors = factorsResp.factors || []

              answer = formatFactorsResponse(factors)
              setLastRetrievalNote('Factor retrieval completed.')
            } else {
              // Step 4: Get answer from Groq
              const answerResp = await apiCall('POST', '/api/answer', {
                question,
                route,
                project_rows: projects,
                factor_rows: factors,
              })
              answer = answerResp.answer
              setLastRetrievalNote('Project retrieval completed and passed to answer model.')
            }
          }
        }
      }

      setLastProjects(projects)
      setLastFactors(factors)

      // Add assistant response
      const finalMessages = [...updatedMessages, { role: 'assistant', content: answer }]
      setMessages(finalMessages)

      // Update chat name based on first user message
      setChats((prevChats) =>
        prevChats.map((chat) =>
          chat.id === currentChatId
            ? { ...chat, name: question.substring(0, 30) + (question.length > 30 ? '...' : '') }
            : chat
        )
      )
    } catch (error) {
      console.error('Error:', error)
      const errorMessage = `Error: ${error.message}`
      setMessages([...updatedMessages, { role: 'assistant', content: errorMessage }])
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
