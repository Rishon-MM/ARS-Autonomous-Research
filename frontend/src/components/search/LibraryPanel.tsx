import React from "react"
import { Trash2, ExternalLink, Library } from "lucide-react"
import type { Paper } from "./types"
import { getPaperLink } from "./types"

interface Props {
  library: Paper[]
  onRemove: (id: string) => void
}

export default function LibraryPanel({ library, onRemove }: Props) {
  return (
    <div className="w-[350px] border-l border-slate-200 bg-slate-50 flex flex-col h-full overflow-hidden shrink-0">
      <div className="p-4 border-b border-slate-200 bg-white">
        <h2 className="font-semibold text-slate-800 flex items-center gap-2">
          <Library className="w-5 h-5 text-blue-600" />
          My Library
          <span className="ml-auto text-xs font-medium bg-slate-100 text-slate-600 px-2 py-0.5 rounded-full">
            {library.length} {library.length === 1 ? 'Paper' : 'Papers'}
          </span>
        </h2>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {library.length === 0 ? (
          <div className="text-center text-slate-500 mt-10">
            <p className="text-sm">No saved papers yet.</p>
            <p className="text-xs mt-1 text-slate-400">Search and add papers to your library.</p>
          </div>
        ) : (
          library.map(paper => {
            const link = getPaperLink(paper)
            return (
              <div key={paper.id} className="bg-white border border-slate-200 rounded-lg p-3 shadow-sm group">
                {link ? (
                  <a 
                    href={link} 
                    target="_blank" 
                    rel="noreferrer"
                    className="font-medium text-sm text-slate-900 leading-tight mb-1 line-clamp-2 hover:text-blue-600 hover:underline transition-colors block"
                  >
                    {paper.title}
                  </a>
                ) : (
                  <h4 className="font-medium text-sm text-slate-900 leading-tight mb-1 line-clamp-2">
                    {paper.title}
                  </h4>
                )}
                <p className="text-xs text-slate-500 truncate mb-1">
                  {paper.authors.length > 0 ? paper.authors[0] + (paper.authors.length > 1 ? " et al." : "") : "Unknown"} · {paper.year || "N/A"}
                </p>
                <span className={`inline-block text-[10px] font-medium px-1.5 py-0.5 rounded ${
                  paper.source === "Semantic Scholar" 
                    ? "bg-blue-50 text-blue-600" 
                    : paper.source === "arXiv" 
                      ? "bg-orange-50 text-orange-600" 
                      : "bg-violet-50 text-violet-600"
                }`}>
                  {paper.source}
                </span>
                
                <div className="flex items-center justify-between mt-3 pt-2 border-t border-slate-100">
                  {link ? (
                    <a 
                      href={link} 
                      target="_blank" 
                      rel="noreferrer"
                      className="text-xs flex items-center gap-1 text-blue-600 hover:text-blue-700 font-medium"
                    >
                      Open <ExternalLink className="w-3 h-3" />
                    </a>
                  ) : (
                    <span className="text-xs text-slate-400">No link</span>
                  )}
                  
                  <button 
                    onClick={() => onRemove(paper.id)}
                    className="text-slate-400 hover:text-red-600 transition-colors p-1 opacity-0 group-hover:opacity-100"
                    title="Remove from library"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            )
          })
        )}
      </div>
    </div>
  )
}
