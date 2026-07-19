import { useState, useEffect } from "react"
import { ExternalLink, BookOpen, Globe, FileText } from "lucide-react"

interface Source {
  title: string
  url: string
  source_type: string
  key_points: string[]
  citation: string
}

const TYPE_ICONS: Record<string, any> = {
  paper:   BookOpen,
  article: FileText,
  website: Globe,
}

const TYPE_COLORS: Record<string, string> = {
  paper:   "bg-purple-100 text-purple-700",
  article: "bg-blue-100 text-blue-700",
  website: "bg-amber-100 text-amber-700",
}

export default function CitationsSidebar() {
  const [sources, setSources] = useState<Source[]>([])

  useEffect(() => {
    const handleSourcesUpdate = (e: Event) => {
      const data = (e as CustomEvent).detail
      if (Array.isArray(data)) {
        setSources(data)
      }
    }

    const handleStart = () => setSources([])

    window.addEventListener("sourcesUpdate", handleSourcesUpdate)
    window.addEventListener("agentStart", handleStart)
    return () => {
      window.removeEventListener("sourcesUpdate", handleSourcesUpdate)
      window.removeEventListener("agentStart", handleStart)
    }
  }, [])

  return (
    <div className="flex flex-col h-full bg-white">
      <div className="px-5 py-5 bg-gradient-to-r from-slate-50 to-white border-b border-slate-200/80 flex-shrink-0 relative overflow-hidden">
        <h2 className="text-base font-bold text-slate-800 tracking-tight flex items-center gap-2 relative z-10">
          <BookOpen className="w-4 h-4 text-blue-500" />
          Sources
        </h2>
        {sources.length > 0 && (
          <p className="text-xs font-medium text-slate-500 mt-1 relative z-10">{sources.length} sources found</p>
        )}
        <div className="absolute top-0 right-0 -mt-4 -mr-4 w-24 h-24 bg-blue-50 rounded-full blur-2xl opacity-60"></div>
      </div>

      <div className="flex-1 overflow-y-auto p-4">
        {sources.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-slate-300 gap-2">
            <BookOpen className="w-8 h-8" />
            <p className="text-xs text-center">Sources will appear here after the Researcher agent completes</p>
          </div>
        ) : (
          <div className="space-y-3">
            {sources.map((src, idx) => {
              const TypeIcon = TYPE_ICONS[src.source_type] || Globe
              const typeColor = TYPE_COLORS[src.source_type] || TYPE_COLORS.website

              return (
                <div
                  key={idx}
                  className="relative overflow-hidden bg-white border border-slate-200/60 rounded-xl p-4 shadow-[0_2px_10px_-3px_rgba(6,81,237,0.05)] hover:shadow-[0_8px_30px_-4px_rgba(6,81,237,0.12)] hover:-translate-y-1 transition-all duration-300 group"
                >
                  <div className="absolute top-0 left-0 w-1 h-full bg-gradient-to-b from-blue-500 to-purple-500 opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
                  
                  <div className="flex items-start justify-between gap-3 mb-2.5">
                    <div className="flex items-start gap-2.5 min-w-0">
                      <span className="flex items-center justify-center w-5 h-5 rounded bg-blue-50 text-blue-600 font-bold text-[10px] flex-shrink-0 mt-0.5">
                        {idx + 1}
                      </span>
                      <h3 className="text-sm font-semibold text-slate-800 leading-snug group-hover:text-blue-600 transition-colors duration-200">
                        {src.title}
                      </h3>
                    </div>
                    {src.url && (
                      <a
                        href={src.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-slate-400 hover:text-blue-500 flex-shrink-0 mt-0.5"
                      >
                        <ExternalLink className="w-3 h-3" />
                      </a>
                    )}
                  </div>

                  <div className="flex items-center gap-1.5 mb-2">
                    <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium ${typeColor}`}>
                      <TypeIcon className="w-2.5 h-2.5" />
                      {src.source_type}
                    </span>
                  </div>

                  {src.key_points && src.key_points.length > 0 && (
                    <ul className="space-y-0.5 text-[11px] text-slate-500 pl-4">
                      {src.key_points.slice(0, 3).map((kp, ki) => (
                        <li key={ki} className="list-disc leading-snug">{kp}</li>
                      ))}
                      {src.key_points.length > 3 && (
                        <li className="text-slate-400 italic">
                          +{src.key_points.length - 3} more...
                        </li>
                      )}
                    </ul>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
