import { useState } from "react"
import Navbar from "./Navbar"
import AgentSidebar from "../agents/AgentSidebar"
import ChatPanel from "../chat/ChatPanel"
import CitationsSidebar from "../citations/CitationsSidebar"
import SettingsModal from "./SettingsModal"
import DocumentSearchPage from "../search/DocumentSearchPage"

export default function MainLayout() {
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [activeTab, setActiveTab] = useState<"dashboard" | "search">("dashboard")
  const [provider, setProvider] = useState(() => {
    return localStorage.getItem("ai_provider") || "gemini"
  })
  const [agentProviders, setAgentProviders] = useState<Record<string, string>>(() => {
    try {
      const stored = localStorage.getItem("ai_agent_providers")
      return stored ? JSON.parse(stored) : {}
    } catch {
      return {}
    }
  })
  const [agentTemperatures, setAgentTemperatures] = useState<Record<string, number>>(() => {
    try {
      const stored = localStorage.getItem("ai_agent_temperatures")
      return stored ? JSON.parse(stored) : {}
    } catch {
      return {}
    }
  })
  const [libraryOnly, setLibraryOnly] = useState(() => {
    return localStorage.getItem("research_mode") === "library_only"
  })

  const handleProviderChange = (p: string) => {
    setProvider(p)
    localStorage.setItem("ai_provider", p)
  }

  const handleAgentProviderChange = (agent: string, p: string) => {
    setAgentProviders(prev => {
      const next = { ...prev }
      if (p === "default") {
        delete next[agent]
      } else {
        next[agent] = p
      }
      localStorage.setItem("ai_agent_providers", JSON.stringify(next))
      return next
    })
  }

  const handleTemperatureChange = (agent: string, temp: number) => {
    setAgentTemperatures(prev => {
      const next = { ...prev, [agent]: temp }
      localStorage.setItem("ai_agent_temperatures", JSON.stringify(next))
      return next
    })
  }

  const handleLibraryOnlyToggle = () => {
    setLibraryOnly(prev => {
      const next = !prev
      localStorage.setItem("research_mode", next ? "library_only" : "open")
      return next
    })
  }

  return (
    <div className="flex flex-col h-screen overflow-hidden bg-slate-50 text-slate-800 font-sans">
      <Navbar
        onSettingsClick={() => setSettingsOpen(true)}
        activeTab={activeTab}
        onTabChange={setActiveTab}
        libraryOnly={libraryOnly}
        onLibraryOnlyToggle={handleLibraryOnlyToggle}
      />
      <div className="flex-1 flex overflow-hidden p-6 gap-6 max-w-[1600px] w-full mx-auto">
        {activeTab === "dashboard" ? (
          <>
            {/* Left Sidebar */}
            <div className="hidden lg:block w-[320px] flex-shrink-0 flex flex-col">
              <AgentSidebar 
                globalProvider={provider} 
                agentProviders={agentProviders} 
                agentTemperatures={agentTemperatures}
                onTemperatureChange={handleTemperatureChange}
                libraryOnly={libraryOnly}
              />
            </div>

            {/* Center Panel */}
            <div className="flex-1 flex flex-col min-w-0 bg-white border border-slate-200 shadow-sm rounded-lg overflow-hidden">
              <ChatPanel 
                provider={provider} 
                agentProviders={agentProviders} 
                agentTemperatures={agentTemperatures}
                libraryOnly={libraryOnly}
              />
            </div>

            {/* Right Sidebar */}
            <div className="hidden xl:block w-[280px] flex-shrink-0 flex flex-col bg-white border border-slate-200 shadow-sm rounded-lg overflow-hidden">
              <CitationsSidebar />
            </div>
          </>
        ) : (
          <div className="flex-1 min-w-0 bg-white border border-slate-200 shadow-sm rounded-lg overflow-hidden flex flex-col">
            <DocumentSearchPage />
          </div>
        )}
      </div>

      <SettingsModal
        isOpen={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        currentProvider={provider}
        onProviderChange={handleProviderChange}
        agentProviders={agentProviders}
        onAgentProviderChange={handleAgentProviderChange}
      />
    </div>
  )
}
