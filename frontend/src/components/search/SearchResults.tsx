import React from "react"
import { ExternalLink, BookOpen, User, Calendar, MapPin, Plus } from "lucide-react"
import type { Paper } from "./types"
import { getPaperLink } from "./types"

interface Props {
  papers: Paper[]
  onAddToLibrary: (paper: Paper) => void
  savedPaperIds: Set<string>
  isLoading: boolean
}

export default function SearchResults({ papers, onAddToLibrary, savedPaperIds, isLoading }: Props) {
  if (isLoading) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
          <p className="text-sm text-slate-500">Searching research databases...</p>
        </div>
      </div>
    )
  }

  if (papers.length === 0) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center text-slate-500">
        <BookOpen className="w-12 h-12 text-slate-300 mb-4" />
        <p className="text-lg font-medium">No results found</p>
        <p className="text-sm">Try adjusting your search terms or paste a paper URL</p>
      </div>
    )
  }

  return (
    <div className="flex-1 overflow-y-auto p-6 space-y-4">
      {papers.map(paper => {
        const isSaved = savedPaperIds.has(paper.id)
        const link = getPaperLink(paper)
        
        return (
          <div key={paper.id} className="border border-slate-200 rounded-xl p-5 bg-white hover:shadow-md transition-shadow">
            <div className="flex items-start justify-between gap-4">
              {link ? (
                <a 
                  href={link} 
                  target="_blank" 
                  rel="noreferrer"
                  className="font-semibold text-lg text-slate-900 leading-snug hover:text-blue-600 hover:underline transition-colors"
                >
                  {paper.title}
                </a>
              ) : (
                <h3 className="font-semibold text-lg text-slate-900 leading-snug">
                  {paper.title}
                </h3>
              )}
              <span className={`shrink-0 text-xs font-medium px-2 py-1 rounded ${
                paper.source === "Semantic Scholar" 
                  ? "bg-blue-50 text-blue-600" 
                  : paper.source === "arXiv" 
                    ? "bg-orange-50 text-orange-600" 
                    : "bg-violet-50 text-violet-600"
              }`}>
                {paper.source}
              </span>
            </div>
            
            <div className="flex flex-wrap text-sm text-slate-500 mt-2 gap-x-4 gap-y-1">
              <div className="flex items-center gap-1.5">
                <User className="w-3.5 h-3.5" />
                <span className="truncate max-w-[300px]">
                  {paper.authors.length > 0 ? paper.authors.join(", ") : "Unknown authors"}
                </span>
              </div>
              <div className="flex items-center gap-1.5">
                <Calendar className="w-3.5 h-3.5" />
                <span>{paper.year || "Unknown Year"}</span>
              </div>
              <div className="flex items-center gap-1.5">
                <MapPin className="w-3.5 h-3.5" />
                <span>{paper.venue || "Unknown Venue"}</span>
              </div>
            </div>
            
            <p className="mt-3 text-sm text-slate-600 line-clamp-3 leading-relaxed">
              {paper.abstract}
            </p>
            
            <div className="mt-4 flex items-center justify-end gap-3">
              {link && (
                <a 
                  href={link} 
                  target="_blank" 
                  rel="noreferrer"
                  className="flex items-center gap-1.5 text-blue-600 hover:text-blue-700 text-sm font-medium px-3 py-1.5 rounded-md hover:bg-blue-50 transition-colors"
                >
                  <ExternalLink className="w-4 h-4" />
                  {paper.pdfUrl ? "View PDF" : "View Source"}
                </a>
              )}
              <button
                onClick={() => onAddToLibrary(paper)}
                disabled={isSaved}
                className={`flex items-center gap-1.5 text-sm font-medium px-4 py-1.5 rounded-md transition-colors ${
                  isSaved 
                    ? "bg-green-50 text-green-600 cursor-not-allowed" 
                    : "bg-blue-600 hover:bg-blue-700 text-white shadow-sm"
                }`}
              >
                {!isSaved && <Plus className="w-4 h-4" />}
                {isSaved ? "✓ In Library" : "Add to Library"}
              </button>
            </div>
          </div>
        )
      })}
    </div>
  )
}
