import { useState, useEffect } from "react"
import { X, Check, Loader2, Sparkles, Zap, Monitor, Settings2 } from "lucide-react"

interface ProviderInfo {
  available: boolean
  models?: { fast: string; strong: string }
  base_url?: string
}

interface SettingsData {
  providers: {
    gemini: ProviderInfo
    openai: ProviderInfo
    local_llama: ProviderInfo
  }
}

interface SettingsModalProps {
  isOpen: boolean
  onClose: () => void
  currentProvider: string
  onProviderChange: (provider: string) => void
  agentProviders: Record<string, string>
  onAgentProviderChange: (agent: string, provider: string) => void
}

const AGENTS = ["Planner", "Researcher", "Outliner", "Section Writer", "Editor", "Critic"]

export default function SettingsModal({ isOpen, onClose, currentProvider, onProviderChange, agentProviders, onAgentProviderChange }: SettingsModalProps) {
  const [settings, setSettings] = useState<SettingsData | null>(null)
  const [loading, setLoading] = useState(false)
  const [llamaChecking, setLlamaChecking] = useState(false)

  useEffect(() => {
    if (isOpen) {
      // 1. Fetch cloud providers instantly
      setLoading(true)
      fetch("http://localhost:8000/api/settings")
        .then(res => res.json())
        .then(data => {
          setSettings(data)
          setLoading(false)

          // 2. Probe local LLaMA in the background (non-blocking)
          setLlamaChecking(true)
          fetch("http://localhost:8000/api/health/local_llama")
            .then(r => r.json())
            .then(health => {
              setSettings(prev => {
                if (!prev) return prev
                return {
                  ...prev,
                  providers: {
                    ...prev.providers,
                    local_llama: {
                      ...prev.providers.local_llama,
                      available: health.available,
                      base_url: health.base_url ?? prev.providers.local_llama.base_url,
                    }
                  }
                }
              })
            })
            .catch(() => { })
            .finally(() => setLlamaChecking(false))
        })
        .catch(() => {
          setSettings(null)
          setLoading(false)
        })
    }
  }, [isOpen])

  if (!isOpen) return null

  const handleSelectProvider = (key: string) => {
    onProviderChange(key)

    // When selecting a non-custom provider, set ALL agents to that provider
    if (key !== "custom") {
      AGENTS.forEach(agent => {
        onAgentProviderChange(agent, key)
      })
    }
  }

  const providers = [
    {
      key: "gemini",
      name: "Google Gemini",
      icon: Sparkles,
      color: "blue",
      description: "Google's Gemini 2.5 Flash model. Free tier available.",
    },
    {
      key: "openai",
      name: "OpenAI",
      icon: Zap,
      color: "green",
      description: "GPT-4o-mini (fast) and GPT-4o (strong) models.",
    },
    {
      key: "local_llama",
      name: "Local LLaMA",
      icon: Monitor,
      color: "purple",
      description: "Self-hosted model via llama.cpp server (OpenAI-compatible API).",
    },
    {
      key: "custom",
      name: "Custom (Per-Agent)",
      icon: Settings2,
      color: "slate",
      description: "Configure individual providers for each agent in the pipeline.",
    },
  ]

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={onClose} />

      {/* Modal */}
      <div className="relative bg-white rounded-xl shadow-2xl w-full max-w-md mx-4 overflow-hidden flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="flex-shrink-0 flex items-center justify-between px-6 py-4 border-b border-slate-100">
          <h2 className="text-lg font-semibold text-slate-800">Settings</h2>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600 transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Body */}
        <div className="p-6 overflow-y-auto flex-1">
          <h3 className="text-sm font-semibold text-slate-700 mb-1">AI Provider</h3>
          <p className="text-xs text-slate-400 mb-4">Select which AI provider to use for the research pipeline</p>

          {loading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="w-6 h-6 text-blue-500 animate-spin" />
            </div>
          ) : (
            <div className="space-y-3">
              {providers.map(p => {
                const info = p.key !== "custom" ? settings?.providers?.[p.key as keyof typeof settings.providers] : undefined
                const isAvailable = p.key === "custom" ? true : (info?.available ?? false)
                const isSelected = currentProvider === p.key
                const Icon = p.icon

                return (
                  <button
                    key={p.key}
                    onClick={() => {
                      if (isAvailable) {
                        handleSelectProvider(p.key)
                      }
                    }}
                    disabled={!isAvailable}
                    className={`w-full text-left p-4 rounded-lg border-2 transition-all ${isSelected
                        ? "border-blue-500 bg-blue-50 shadow-sm"
                        : isAvailable
                          ? "border-slate-200 hover:border-slate-300 bg-white"
                          : "border-slate-100 bg-slate-50 opacity-60 cursor-not-allowed"
                      }`}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <div className={`p-2 rounded-lg ${isSelected ? "bg-blue-600 text-white" : "bg-slate-100 text-slate-500"
                          }`}>
                          <Icon className="w-4 h-4" />
                        </div>
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="font-semibold text-sm text-slate-800">{p.name}</span>
                            {p.key === "local_llama" && llamaChecking ? (
                              <span className="text-[10px] bg-slate-100 text-slate-500 px-1.5 py-0.5 rounded font-medium flex items-center gap-1">
                                <Loader2 className="w-2.5 h-2.5 animate-spin" />
                                Checking…
                              </span>
                            ) : isAvailable && p.key === "local_llama" ? (
                              <span className="text-[10px] bg-green-100 text-green-700 px-1.5 py-0.5 rounded font-medium">
                                Server Online
                              </span>
                            ) : !isAvailable && (
                              <span className="text-[10px] bg-amber-100 text-amber-700 px-1.5 py-0.5 rounded font-medium">
                                {p.key === "local_llama" ? "Server Offline" : "No API Key"}
                              </span>
                            )}
                          </div>
                          <p className="text-xs text-slate-500 mt-0.5">{p.description}</p>
                          {info && isAvailable && p.key !== "custom" && (
                            <p className="text-[10px] text-slate-400 mt-1">
                              {p.key === "local_llama"
                                ? `Model: ${info.models?.fast || "local"} · ${info.base_url ?? ""}`
                                : `Fast: ${info.models?.fast || "auto"} · Strong: ${info.models?.strong || "auto"}`}
                            </p>
                          )}
                        </div>
                      </div>
                      {isSelected && (
                        <div className="bg-blue-600 text-white rounded-full p-0.5">
                          <Check className="w-3 h-3" />
                        </div>
                      )}
                    </div>
                  </button>
                )
              })}
            </div>
          )}

          {/* Agent Configuration section - only for custom mode */}
          {!loading && currentProvider === "custom" && (
            <div className="mt-8 border-t border-slate-100 pt-6">
              <h3 className="text-sm font-semibold text-slate-700 mb-1">Agent Configuration</h3>
              <p className="text-xs text-slate-400 mb-4">Override the provider for specific agents.</p>
              
              <div className="space-y-3">
                {AGENTS.map(agent => {
                  const currentValue = agentProviders[agent] || "gemini"
                  
                  return (
                    <div key={agent} className="flex items-center justify-between py-2 border-b border-slate-50 last:border-0">
                      <span className="text-sm font-medium text-slate-700">{agent}</span>
                      <select 
                        value={currentValue}
                        onChange={(e) => onAgentProviderChange(agent, e.target.value)}
                        className="text-sm border border-slate-200 rounded-md py-1.5 px-3 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 text-slate-600"
                      >
                        {providers.filter(p => p.key !== "custom").map(p => {
                          const info = settings?.providers?.[p.key as keyof typeof settings.providers]
                          const isAvailable = info?.available ?? false
                          return (
                            <option key={p.key} value={p.key} disabled={!isAvailable}>
                              {p.name} {!isAvailable ? "(Unavailable)" : ""}
                            </option>
                          )
                        })}
                      </select>
                    </div>
                  )
                })}
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex-shrink-0 px-6 py-4 border-t border-slate-100 bg-slate-50">
          <p className="text-[11px] text-slate-400">
            Provider selection is stored locally and sent with each request. Add API keys to your .env file to enable cloud providers.
            For Local LLaMA, start your llama-server and set <code className="bg-slate-200 px-1 rounded text-[10px]">LOCAL_LLAMA_URL</code> in your backend .env (default: http://localhost:8080/v1).
          </p>
        </div>
      </div>
    </div>
  )
}
