import { useState, useRef, useEffect } from "react"
import { createPortal } from "react-dom"
import { MoreHorizontal, Loader2, CheckCircle, Circle, XCircle, Sparkles, Zap, Monitor, Thermometer } from "lucide-react"
import type { LucideIcon } from "lucide-react"

export interface AgentCardProps {
  name: string
  Icon: LucideIcon
  statusText: string
  subText: string
  state: "idle" | "working" | "complete" | "failed"
  provider: string
  temperature: number
  onTemperatureChange: (temp: number) => void
}

const STATE_STYLES = {
  idle:     { border: "border-slate-200",  iconBg: "bg-slate-400",  StatusIcon: Circle,      iconColor: "text-slate-300" },
  working:  { border: "border-blue-300",   iconBg: "bg-blue-600",   StatusIcon: Loader2,     iconColor: "text-blue-500"  },
  complete: { border: "border-green-200",  iconBg: "bg-green-600",  StatusIcon: CheckCircle, iconColor: "text-green-500" },
  failed:   { border: "border-red-200",    iconBg: "bg-red-600",    StatusIcon: XCircle,     iconColor: "text-red-500"   },
}

const PROVIDER_LABELS: Record<string, { label: string; Icon: LucideIcon; color: string }> = {
  gemini:      { label: "Gemini",  Icon: Sparkles, color: "text-blue-500" },
  openai:      { label: "OpenAI",  Icon: Zap,      color: "text-green-500" },
  local_llama: { label: "LLaMA",   Icon: Monitor,  color: "text-purple-500" },
}

function getTempColor(t: number): string {
  if (t <= 0.3) return "text-blue-500"
  if (t <= 0.7) return "text-amber-500"
  return "text-red-500"
}

function getTempLabel(t: number): string {
  if (t <= 0.2) return "Precise"
  if (t <= 0.5) return "Balanced"
  if (t <= 0.8) return "Creative"
  return "Wild"
}

function TempPopover({ temperature, onTemperatureChange, anchorRef, onClose }: {
  temperature: number
  onTemperatureChange: (t: number) => void
  anchorRef: React.RefObject<HTMLButtonElement>
  onClose: () => void
}) {
  const popoverRef = useRef<HTMLDivElement>(null)
  const [pos, setPos] = useState({ top: 0, left: 0 })

  useEffect(() => {
    if (anchorRef.current) {
      const rect = anchorRef.current.getBoundingClientRect()
      setPos({
        top: rect.bottom + 6,
        left: Math.max(8, rect.right - 256),
      })
    }
  }, [anchorRef])

  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (popoverRef.current && !popoverRef.current.contains(e.target as Node) &&
          anchorRef.current && !anchorRef.current.contains(e.target as Node)) {
        onClose()
      }
    }
    document.addEventListener("mousedown", handleClick)
    return () => document.removeEventListener("mousedown", handleClick)
  }, [onClose, anchorRef])

  return createPortal(
    <div
      ref={popoverRef}
      className="fixed z-[9999] w-60 bg-white border border-slate-200 rounded-xl shadow-xl p-4"
      style={{ top: pos.top, left: pos.left }}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs font-bold text-slate-700 flex items-center gap-1.5">
          <Thermometer className="w-3.5 h-3.5" />
          Temperature
        </span>
        <span className={`text-xs font-bold tabular-nums ${getTempColor(temperature)}`}>
          {temperature.toFixed(2)}
        </span>
      </div>

      {/* Slider */}
      <div className="mb-2">
        <input
          type="range"
          min="0"
          max="1"
          step="0.05"
          value={temperature}
          onChange={(e) => onTemperatureChange(parseFloat(e.target.value))}
          className="temp-slider"
        />
      </div>

      {/* Scale labels */}
      <div className="flex justify-between mb-3 text-[10px] font-medium text-slate-400">
        <span>Precise</span>
        <span>Creative</span>
      </div>

      {/* Current mode label */}
      <div className={`text-[11px] font-bold text-center py-1.5 rounded-lg ${
        temperature <= 0.3 ? "bg-blue-50 text-blue-600" 
        : temperature <= 0.7 ? "bg-amber-50 text-amber-600" 
        : "bg-red-50 text-red-600"
      }`}>
        {getTempLabel(temperature)}
      </div>
    </div>,
    document.body
  )
}

export default function AgentCard({ name, Icon, statusText, subText, state, provider, temperature, onTemperatureChange }: AgentCardProps) {
  const { border, iconBg, StatusIcon, iconColor } = STATE_STYLES[state]
  const isWorking = state === "working"
  const providerInfo = PROVIDER_LABELS[provider] || PROVIDER_LABELS.gemini
  const [menuOpen, setMenuOpen] = useState(false)
  const btnRef = useRef<HTMLButtonElement>(null)

  return (
    <div className={`bg-white border ${border} rounded-lg shadow-sm p-4 mb-2.5 transition-all duration-300
      ${isWorking ? "ring-1 ring-blue-200 shadow-blue-50" : ""}
    `}>
      {/* Top row */}
      <div className="flex justify-between items-center">
        <div className="flex items-center gap-2.5">
          <div className={`${iconBg} text-white p-1.5 rounded-md flex items-center justify-center transition-colors duration-300`}>
            <Icon className="w-4 h-4" />
          </div>
          <h3 className="font-bold text-slate-800 text-[13px]">{name}</h3>
        </div>
        <div className="flex items-center gap-1.5">
          <div className={`flex items-center gap-0.5 ${providerInfo.color}`} title={`Using ${providerInfo.label}`}>
            <providerInfo.Icon className="w-3 h-3" />
            <span className="text-[10px] font-semibold">{providerInfo.label}</span>
          </div>
          <div className={`flex items-center gap-0.5 ${getTempColor(temperature)}`} title={`Temp: ${temperature}`}>
            <Thermometer className="w-3 h-3" />
            <span className="text-[10px] font-semibold">{temperature.toFixed(1)}</span>
          </div>
          <button
            ref={btnRef}
            onClick={() => setMenuOpen(!menuOpen)}
            className="text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded p-0.5 transition-colors"
          >
            <MoreHorizontal className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Status */}
      <div className="flex items-center gap-1.5 mt-2.5">
        <StatusIcon className={`w-3.5 h-3.5 ${iconColor} ${isWorking ? "animate-spin" : ""}`} />
        <p className="text-[12px] font-medium text-slate-700 truncate">{statusText}</p>
      </div>

      {/* Sub-text */}
      {subText && (
        <div className="pl-5 mt-1">
          <p className="text-[11px] text-slate-500 truncate">
            {isWorking ? <span className="text-blue-600 font-semibold">{subText}</span> : subText}
          </p>
        </div>
      )}

      {/* Portal-rendered popover */}
      {menuOpen && (
        <TempPopover
          temperature={temperature}
          onTemperatureChange={onTemperatureChange}
          anchorRef={btnRef as React.RefObject<HTMLButtonElement>}
          onClose={() => setMenuOpen(false)}
        />
      )}
    </div>
  )
}
