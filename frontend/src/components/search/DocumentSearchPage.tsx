import React, { useState, useEffect } from "react"
import { Search, Link2 } from "lucide-react"
import type { Paper } from "./types"
import SearchResults from "./SearchResults"
import LibraryPanel from "./LibraryPanel"
import AgentPanel from "./AgentPanel"
import { useAgentStream } from "./useAgentStream"

function isUrl(str: string): boolean {
  return str.startsWith("http://") || str.startsWith("https://")
}

export default function DocumentSearchPage() {
  const [query, setQuery] = useState("")
  const [library, setLibrary] = useState<Paper[]>([])
  const [searchMode, setSearchMode] = useState<"search" | "url">("search")
  
  const { steps, status, papers, error, ingestionStats, startSearch, abortSearch, reset } = useAgentStream()
  const isLoading = status === 'running'

  // Load library from localStorage on mount
  useEffect(() => {
    try {
      const stored = localStorage.getItem("research-library")
      if (stored) {
        setLibrary(JSON.parse(stored))
      }
    } catch (e) {
      console.error("Failed to load library:", e)
    }
  }, [])

  // Detect URL vs keyword as user types
  useEffect(() => {
    setSearchMode(isUrl(query.trim()) ? "url" : "search")
  }, [query])

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!query.trim()) return

    if (isUrl(query.trim())) {
      // URL import mode (unchanged, we keep it simple for now)
      try {
        reset()
        const res = await fetch("http://localhost:8000/api/papers/analyze", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ url: query.trim() })
        })
        if (res.ok) {
          // This doesn't stream yet, so we just set papers directly
        }
      } catch (err) {
        console.error("Analyze error:", err)
      }
    } else {
      // Agent streaming search
      startSearch(query.trim())
    }
  }

  const handleAddToLibrary = (paper: Paper) => {
    if (library.some(p => p.id === paper.id)) return
    
    const newLibrary = [...library, paper]
    setLibrary(newLibrary)
    localStorage.setItem("research-library", JSON.stringify(newLibrary))
  }

  const handleRemoveFromLibrary = (id: string) => {
    const newLibrary = library.filter(p => p.id !== id)
    setLibrary(newLibrary)
    localStorage.setItem("research-library", JSON.stringify(newLibrary))
  }

  const savedPaperIds = new Set(library.map(p => p.id))

  return (
    <div className="flex flex-1 overflow-hidden h-full">
      {/* Main Search Area */}
      <div className="flex-1 flex flex-col min-w-0">
        
        {/* Search Header */}
        <div className="p-6 border-b border-slate-200 shrink-0">
          <h1 className="text-2xl font-bold text-slate-800 tracking-tight mb-2">Document Search</h1>
          <p className="text-sm text-slate-500 mb-6">Search verified academic papers or paste a URL to import.</p>
          
          <form onSubmit={handleSearch} className="flex gap-3 max-w-3xl">
            <div className="relative flex-1">
              {searchMode === "url" ? (
                <Link2 className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-violet-500" />
              ) : (
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400" />
              )}
              <input 
                type="text" 
                value={query}
                onChange={e => setQuery(e.target.value)}
                placeholder="Search papers by keyword, title, or paste a URL..."
                className={`w-full pl-10 pr-4 py-3 bg-slate-50 border rounded-lg focus:outline-none focus:ring-2 focus:border-transparent transition-all shadow-inner font-medium text-slate-700 ${
                  searchMode === "url" 
                    ? "border-violet-300 focus:ring-violet-500" 
                    : "border-slate-200 focus:ring-blue-500"
                }`}
              />
            </div>
            <button 
              type="submit" 
              disabled={isLoading || !query.trim()}
              className={`px-6 py-3 rounded-lg font-medium shadow-sm transition-colors disabled:opacity-50 disabled:cursor-not-allowed whitespace-nowrap ${
                searchMode === "url"
                  ? "bg-violet-600 hover:bg-violet-700 text-white"
                  : "bg-blue-600 hover:bg-blue-700 text-white"
              }`}
            >
              {isLoading 
                ? (searchMode === "url" ? "Analyzing..." : "Searching...")
                : (searchMode === "url" ? "Import Paper" : "Search")
              }
            </button>
          </form>

          {searchMode === "url" && (
            <p className="text-xs text-violet-600 mt-2 flex items-center gap-1">
              <Link2 className="w-3 h-3" />
              URL detected — AI will extract paper details from this link
            </p>
          )}

          <AgentPanel 
            steps={steps} 
            status={status} 
            error={error} 
            paperCount={papers.length}
            ingestionStats={ingestionStats}
            onTerminate={abortSearch}
          />
        </div>

        {/* Search Results Area */}
        <SearchResults 
          papers={papers} 
          onAddToLibrary={handleAddToLibrary} 
          savedPaperIds={savedPaperIds}
          isLoading={isLoading}
        />
        
      </div>

      {/* Library Sidebar Area */}
      <LibraryPanel library={library} onRemove={handleRemoveFromLibrary} />
    </div>
  )
}
