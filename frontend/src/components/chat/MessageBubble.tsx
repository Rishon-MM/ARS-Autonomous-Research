import { User, Sparkles, AlertCircle } from "lucide-react"

export interface MessageBubbleProps {
  role: "user" | "ai"
  content: string
  isStreaming?: boolean
  isError?: boolean
}

export default function MessageBubble({ role, content, isStreaming, isError }: MessageBubbleProps) {
  const isUser = role === "user"

  return (
    <div className={`flex gap-4 w-full items-start`}>
      <div className={`flex-shrink-0 w-10 h-10 rounded-full flex items-center justify-center mt-1
        ${isUser ? "bg-slate-400 text-white" : isError ? "bg-red-500 text-white" : "bg-blue-600 text-white"}  
      `}>
        {isUser ? <User className="w-6 h-6" /> : isError ? <AlertCircle className="w-5 h-5"/> : <Sparkles className="w-5 h-5" />}
      </div>
      <div className={`flex-1 flex flex-col py-3 px-4 rounded-lg border shadow-sm min-h-[48px]
        ${isUser ? "bg-white border-slate-200" : isError ? "bg-red-50 border-red-200" : "bg-slate-50 border-blue-100"}
      `}>
        {isStreaming && content.length === 0 ? (
          <div className="flex gap-1.5 items-center h-6 pl-1">
             <div className="w-2 h-2 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
             <div className="w-2 h-2 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></div>
             <div className="w-2 h-2 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
          </div>
        ) : (
          <p className={`text-[15px] ${isError ? "text-red-700 font-medium" : "text-slate-800"} whitespace-pre-wrap leading-relaxed`}>
            {content}
            {isStreaming && <span className="inline-block w-1.5 h-4 ml-1 bg-blue-500 animate-pulse align-middle" />}
          </p>
        )}
      </div>
    </div>
  )
}
