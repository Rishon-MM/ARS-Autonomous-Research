import { useState, useEffect } from "react"
import { Compass, Search, ListTree, PenLine, FileEdit, ShieldCheck } from "lucide-react"
import AgentCard from "./AgentCard"

export interface AgentState {
  state: "idle" | "working" | "complete" | "failed"
  statusText: string
  subText: string
}

const AGENT_KEYS = ["Planner", "Researcher", "Outliner", "Section Writer", "Editor", "Critic"] as const

const initialStates: Record<string, AgentState> = {
  Planner: { state: "idle", statusText: "Waiting for topic...", subText: "" },
  Researcher: { state: "idle", statusText: "Waiting for plan...", subText: "" },
  Outliner: { state: "idle", statusText: "Waiting for sources...", subText: "" },
  "Section Writer": { state: "idle", statusText: "Waiting for outline...", subText: "" },
  Editor: { state: "idle", statusText: "Waiting for sections...", subText: "" },
  Critic: { state: "idle", statusText: "Waiting for report...", subText: "" },
}

const AGENT_ICONS: Record<string, any> = {
  Planner: Compass,
  Researcher: Search,
  Outliner: ListTree,
  "Section Writer": PenLine,
  Editor: FileEdit,
  Critic: ShieldCheck,
}

interface AgentSidebarProps {
  globalProvider: string
  agentProviders: Record<string, string>
  agentTemperatures: Record<string, number>
  onTemperatureChange: (agent: string, temp: number) => void
  libraryOnly: boolean
}

export default function AgentSidebar({ globalProvider, agentProviders, agentTemperatures, onTemperatureChange, libraryOnly }: AgentSidebarProps) {
  const [agents, setAgents] = useState<Record<string, AgentState>>(initialStates)

  useEffect(() => {
    const handleUpdate = (e: Event) => {
      const data = (e as CustomEvent).detail
      
      if (data.type === "error") {
        setAgents(prev => {
          const next = { ...prev }
          for (const key in next) {
            if (next[key].state === "working") {
              next[key] = {
                ...next[key],
                state: "failed",
                statusText: data.message || "Pipeline stopped",
                subText: ""
              }
            }
          }
          return next
        })
        return
      }

      if (!data.agent) return

      setAgents(prev => ({
        ...prev,
        [data.agent]: {
          state: data.state || prev[data.agent]?.state || "idle",
          statusText: data.statusText || prev[data.agent]?.statusText || "",
          subText: data.subText ?? prev[data.agent]?.subText ?? ""
        }
      }))
    }

    const handleStart = () => setAgents(initialStates)

    window.addEventListener("agentUpdate", handleUpdate)
    window.addEventListener("agentStart", handleStart)
    return () => {
      window.removeEventListener("agentUpdate", handleUpdate)
      window.removeEventListener("agentStart", handleStart)
    }
  }, [])

  const getProviderForAgent = (agentName: string): string => {
    return agentProviders[agentName] || globalProvider || "gemini"
  }

  const isCustom = Object.keys(agentProviders).length > 0

  return (
    <div className="flex flex-col h-full">
      <div className="mb-5 px-1 flex items-center justify-between">
        <h2 className="text-base font-bold text-slate-800">Agent Pipeline</h2>
        <div className="flex items-center gap-1.5">
          {libraryOnly && (
            <span className="text-[11px] font-semibold px-2 py-0.5 rounded-md bg-violet-100 text-violet-700">
              📚 Library
            </span>
          )}
          {isCustom && (
            <span className="text-[11px] font-semibold px-2 py-0.5 rounded-md bg-amber-100 text-amber-700">
              Custom
            </span>
          )}
        </div>
      </div>
      <div className="overflow-y-auto flex-1 pr-2 pb-4 space-y-0">
        {AGENT_KEYS.map((name) => (
          <div key={name} className="relative">
            <AgentCard
              name={name}
              Icon={AGENT_ICONS[name]}
              state={agents[name].state}
              statusText={agents[name].statusText}
              subText={agents[name].subText}
              provider={getProviderForAgent(name)}
              temperature={agentTemperatures[name] ?? 0.5}
              onTemperatureChange={(temp) => onTemperatureChange(name, temp)}
            />
          </div>
        ))}
      </div>
    </div>
  )
}
