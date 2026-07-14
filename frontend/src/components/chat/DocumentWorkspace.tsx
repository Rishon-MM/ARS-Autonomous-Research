import {
  FileText,
  Copy,
  Download,
  ShieldCheck,
  ShieldAlert,
  ChevronDown,
  ChevronUp,
} from "lucide-react"
import React, { useState } from "react"
import type { ReportData } from "./ChatPanel"

export default function DocumentWorkspace({ data }: { data?: ReportData }) {
  if (!data) return null

  const [showCritic, setShowCritic] = useState(false)
  const [exporting, setExporting] = useState<string | null>(null)

  const criticPassed = data.reflection?.outcome_type === "success"
  const confidence = Math.round((data.reflection?.confidence ?? 0) * 100)

  const handleExport = async (format: "docx" | "pdf") => {
    setExporting(format)
    try {
      const res = await fetch("http://localhost:8000/api/export", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ report: data.report, format }),
      })
      if (!res.ok) throw new Error("Export failed")

      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement("a")
      a.href = url
      a.download = `research_report.${format}`
      a.click()
      URL.revokeObjectURL(url)
    } catch (e) {
      console.error("Export error:", e)
    } finally {
      setExporting(null)
    }
  }

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(data.report)
    } catch {
      // fallback
    }
  }

  // Render the markdown report into React elements
  const renderReport = (text: string) => {
    const lines = text.split("\n")
    const elements: React.ReactNode[] = []

    let i = 0
    while (i < lines.length) {
      const line = lines[i]
      const trimmed = line.trim()

      if (trimmed.startsWith("### ")) {
        elements.push(
          <h3 key={i} className="text-sm font-bold text-slate-800 mt-4 mb-2">
            {trimmed.slice(4)}
          </h3>
        )
      } else if (trimmed.startsWith("## ")) {
        elements.push(
          <h2 key={i} className="text-base font-bold text-slate-900 mt-6 mb-2 pb-1 border-b border-slate-100">
            {trimmed.slice(3)}
          </h2>
        )
      } else if (trimmed.startsWith("# ")) {
        elements.push(
          <h1 key={i} className="text-xl font-bold text-slate-900 mt-2 mb-4">
            {trimmed.slice(2)}
          </h1>
        )
      } else if (trimmed.length === 0) {
        // skip blank lines
      } else {
        // Render paragraph — highlight inline citations [1], [2], etc.
        const parts = trimmed.split(/(\[\d+\])/)
        elements.push(
          <p key={i} className="text-sm text-slate-700 leading-relaxed mb-3">
            {parts.map((part, pi) =>
              /^\[\d+\]$/.test(part) ? (
                <span key={pi} className="text-blue-600 font-medium text-xs align-super cursor-pointer hover:underline">
                  {part}
                </span>
              ) : (
                <span key={pi}>{part}</span>
              )
            )}
          </p>
        )
      }
      i++
    }
    return elements
  }

  return (
    <div className="border border-slate-200 rounded-lg shadow-sm bg-white overflow-hidden my-4 mr-4 ml-14">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-slate-100">
        <div className="flex items-center gap-2 text-blue-600 font-medium text-sm">
          <FileText className="w-4 h-4" />
          <span>Research Report</span>
          {data.title && (
            <span className="text-slate-400 font-normal text-xs ml-1 truncate max-w-[200px]">
              — {data.title}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {/* Critic badge */}
          <button
            onClick={() => setShowCritic(!showCritic)}
            className={`flex items-center gap-1 px-2 py-1 rounded text-xs font-medium transition-colors
              ${criticPassed
                ? "bg-green-50 text-green-700 hover:bg-green-100"
                : "bg-red-50 text-red-700 hover:bg-red-100"
              }`}
          >
            {criticPassed
              ? <ShieldCheck className="w-3 h-3" />
              : <ShieldAlert className="w-3 h-3" />
            }
            {confidence}%
            {showCritic ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
          </button>

          {/* Actions */}
          <button
            onClick={handleCopy}
            className="text-slate-400 hover:text-slate-600 transition-colors p-1"
            title="Copy report"
          >
            <Copy className="w-4 h-4" />
          </button>
          <button
            onClick={() => handleExport("docx")}
            disabled={!!exporting}
            className="text-slate-400 hover:text-slate-600 transition-colors p-1 disabled:opacity-50"
            title="Download DOCX"
          >
            <Download className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Critic review expandable */}
      {showCritic && data.reflection && (
        <div className={`px-4 py-3 text-xs border-b ${criticPassed ? "bg-green-50 border-green-100" : "bg-red-50 border-red-100"}`}>
          <p className="font-semibold mb-1">
            Reflection — {data.reflection.outcome_type.toUpperCase()} ({confidence}% confidence)
          </p>
          {data.reflection.failed_strategies?.length > 0 && (
            <div className="mb-2">
              <p className="font-medium text-slate-600 mb-0.5">Failed Strategies / Issues:</p>
              <ul className="list-disc pl-4 text-slate-600 space-y-0.5">
                {data.reflection.failed_strategies.map((issue, i) => (
                  <li key={i}>{issue}</li>
                ))}
              </ul>
            </div>
          )}
          {data.reflection.planning_feedback && (
            <div>
              <p className="font-medium text-slate-600 mb-0.5">Suggestions for Future:</p>
              <p className="pl-2 text-slate-600 space-y-0.5 italic">{data.reflection.planning_feedback}</p>
            </div>
          )}
        </div>
      )}

      {/* Report body */}
      <div className="p-6 max-h-[600px] overflow-y-auto">
        {renderReport(data.report)}
      </div>

      {/* Export footer */}
      <div className="flex items-center gap-2 px-4 py-3 border-t border-slate-100 bg-slate-50">
        <button
          onClick={() => handleExport("docx")}
          disabled={!!exporting}
          className="bg-blue-600 hover:bg-blue-700 text-white px-3 py-1.5 rounded text-xs font-medium transition-colors disabled:opacity-50"
        >
          {exporting === "docx" ? "Exporting..." : "Download DOCX"}
        </button>
        <button
          onClick={() => handleExport("pdf")}
          disabled={!!exporting}
          className="bg-slate-700 hover:bg-slate-800 text-white px-3 py-1.5 rounded text-xs font-medium transition-colors disabled:opacity-50"
        >
          {exporting === "pdf" ? "Exporting..." : "Download PDF"}
        </button>
      </div>
    </div>
  )
}
