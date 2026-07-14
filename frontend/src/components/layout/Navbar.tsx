import { Bell, User, ChevronDown, BookOpen, Globe } from "lucide-react"

interface NavbarProps {
  onSettingsClick: () => void
  activeTab: "dashboard" | "search"
  onTabChange: (tab: "dashboard" | "search") => void
  libraryOnly: boolean
  onLibraryOnlyToggle: () => void
}

export default function Navbar({ onSettingsClick, activeTab, onTabChange, libraryOnly, onLibraryOnlyToggle }: NavbarProps) {
  return (
    <nav className="h-16 flex items-center justify-between px-6 bg-white border-b border-border shrink-0">
      <div className="flex items-center gap-8 text-sm">
        <div className="font-semibold text-xl text-slate-800 tracking-tight flex items-center gap-2">
          AI RAG Research System
        </div>
        
        <div className="flex items-center gap-8 h-full font-medium ml-4 mt-[18px]">
          <button 
            onClick={() => onTabChange("dashboard")}
            className={`${activeTab === "dashboard" ? "text-blue-600 border-b-2 border-blue-600" : "text-slate-500 hover:text-slate-800"} pb-4 relative top-[1px]`}
          >
            Dashboard
          </button>
          <button 
            onClick={() => onTabChange("search")}
            className={`${activeTab === "search" ? "text-blue-600 border-b-2 border-blue-600" : "text-slate-500 hover:text-slate-800"} pb-4 relative top-[1px]`}
          >
            Document Search
          </button>
          <button
            onClick={onSettingsClick}
            className="text-slate-500 hover:text-slate-800 pb-4 relative top-[1px]"
          >
            Settings
          </button>
        </div>
      </div>

      <div className="flex items-center gap-3 text-slate-500">
        {/* Library-Only Mode Toggle */}
        <button
          onClick={onLibraryOnlyToggle}
          className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-semibold transition-all ${
            libraryOnly
              ? "bg-violet-100 text-violet-700 ring-1 ring-violet-200"
              : "bg-slate-100 text-slate-500 hover:bg-slate-200"
          }`}
          title={libraryOnly ? "Library Only: Research uses only your saved papers" : "Open Research: Uses web search + AI knowledge"}
        >
          {libraryOnly ? (
            <>
              <BookOpen className="w-3.5 h-3.5" />
              Library Only
            </>
          ) : (
            <>
              <Globe className="w-3.5 h-3.5" />
              Open Research
            </>
          )}
        </button>

        <button className="hover:bg-slate-100 p-2 rounded-full transition-colors">
          <Bell className="w-5 h-5 fill-slate-400 text-slate-400 hover:fill-slate-600 hover:text-slate-600" />
        </button>
        <div className="flex items-center gap-1 cursor-pointer hover:bg-slate-50 p-1 pr-2 rounded-full transition-colors">
          <div className="flex items-center justify-center bg-slate-300 text-white rounded-full w-8 h-8 flex-shrink-0">
            <User className="w-5 h-5" />
          </div>
          <ChevronDown className="w-4 h-4 ml-1" />
        </div>
      </div>
    </nav>
  )
}
