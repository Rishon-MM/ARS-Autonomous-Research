import { useState, useRef, useEffect } from "react"
import MessageBubble from "./MessageBubble"
import type { MessageBubbleProps } from "./MessageBubble"
import DocumentWorkspace from "./DocumentWorkspace"
import { Square } from "lucide-react"

export interface ReportData {
  report: string
  title: string
  sources: {
    title: string
    url: string
    source_type: string
    key_points: string[]
    citation: string
  }[]
  reflection?: {
    outcome_type: string
    confidence: number
    failed_strategies: string[]
    planning_feedback: string
  }
}

export interface Message extends MessageBubbleProps {
  id: string
  reportData?: ReportData
}

export default function ChatPanel({ provider, agentProviders, agentTemperatures, libraryOnly }: { provider: string, agentProviders: Record<string, string>, agentTemperatures: Record<string, number>, libraryOnly: boolean }) {
  const [inputMessage, setInputMessage] = useState("")
  const [messages, setMessages] = useState<Message[]>([])
  const [isLoading, setIsLoading] = useState(false)

  const abortControllerRef = useRef<AbortController | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const handleStop = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
      setIsLoading(false)
      setMessages(prev => {
        const newMsg = [...prev]
        if (newMsg.length > 0 && newMsg[newMsg.length - 1].role === "ai") {
          newMsg[newMsg.length - 1].isStreaming = false
          newMsg[newMsg.length - 1].content = newMsg[newMsg.length - 1].content + "\n\n*[Generation stopped by user]*"
        }
        return newMsg
      })
      window.dispatchEvent(new CustomEvent("agentUpdate", { detail: { type: "error", message: "Generation stopped" } }))
    }
  }

  const handleSend = async () => {
    if (!inputMessage.trim() || isLoading) return

    const userMsg: Message = { id: Date.now().toString(), role: "user", content: inputMessage }
    setMessages(prev => [...prev, userMsg])
    setInputMessage("")
    setIsLoading(true)

    const aiMessageId = (Date.now() + 1).toString()
    setMessages(prev => [...prev, { id: aiMessageId, role: "ai", content: "", isStreaming: true }])

    abortControllerRef.current = new AbortController()
    window.dispatchEvent(new CustomEvent("agentStart"))

    try {
      // Build request body
      const requestBody: any = {
        message: userMsg.content,
        provider,
        agent_providers: agentProviders,
        agent_temperatures: agentTemperatures,
        library_only: libraryOnly,
      }

      // If library-only mode, attach saved papers
      if (libraryOnly) {
        try {
          const stored = localStorage.getItem("research-library")
          requestBody.library_papers = stored ? JSON.parse(stored) : []
        } catch {
          requestBody.library_papers = []
        }

        if (!requestBody.library_papers.length) {
          setMessages(prev =>
            prev.map(m =>
              m.id === aiMessageId
                ? { ...m, content: "Library is empty. Please add papers to your Library first via the Document Search tab.", isError: true, isStreaming: false }
                : m
            )
          )
          setIsLoading(false)
          return
        }
      }

      const response = await fetch("http://localhost:8000/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(requestBody),
        signal: abortControllerRef.current.signal,
      })

      if (!response.ok) throw new Error(`API Error: ${response.statusText}`)
      if (!response.body) throw new Error("No readable response body")

      const reader = response.body.getReader()
      const decoder = new TextDecoder("utf-8")
      let aiContent = ""
      let buffer = ""

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })

        let endOfEvent
        while ((endOfEvent = buffer.indexOf("\n\n")) !== -1) {
          const event = buffer.substring(0, endOfEvent)
          buffer = buffer.substring(endOfEvent + 2)

          if (event.startsWith("data: ") && event !== "data: [DONE]") {
            try {
              const data = JSON.parse(event.substring(6))

              if (data.type === "error" || data.error) {
                const errMsg = data.error || data.message || "Unknown error"
                aiContent = `[Error: ${errMsg}]`
                setMessages(prev =>
                  prev.map(m =>
                    m.id === aiMessageId ? { ...m, content: aiContent, isError: true } : m
                  )
                )
                window.dispatchEvent(new CustomEvent("agentUpdate", { detail: { type: "error" } }))
                continue
              }

              if (data.type === "agent_status") {
                window.dispatchEvent(new CustomEvent("agentUpdate", { detail: data }))
                aiContent = data.statusText
                setMessages(prev =>
                  prev.map(m => (m.id === aiMessageId ? { ...m, content: aiContent } : m))
                )
              } else if (data.type === "sources_update") {
                // Dispatch sources to the citations sidebar
                window.dispatchEvent(new CustomEvent("sourcesUpdate", { detail: data.sources }))
              } else if (data.type === "agent_completion") {
                aiContent = "Research report generated successfully."
                setMessages(prev =>
                  prev.map(m =>
                    m.id === aiMessageId
                      ? {
                          ...m,
                          content: aiContent,
                          reportData: {
                            report: data.report,
                            title: data.title,
                            sources: data.sources || [],
                            reflection: data.reflection || undefined,
                          },
                        }
                      : m
                  )
                )
              }
            } catch (e) {
              console.error("Failed to parse SSE event", e)
            }
          }
        }
      }
    } catch (error: any) {
      if (error.name !== "AbortError") {
        setMessages(prev =>
          prev.map(m =>
            m.id === aiMessageId
              ? {
                  ...m,
                  content: `Connection Error: ${error.message}. Is your backend running?`,
                  isError: true,
                }
              : m
          )
        )
      }
    } finally {
      setIsLoading(false)
      abortControllerRef.current = null
      setMessages(prev =>
        prev.map(m => (m.id === aiMessageId ? { ...m, isStreaming: false } : m))
      )
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className="flex flex-col h-full bg-slate-50 relative">
      <div className="px-6 py-4 border-b border-slate-200 flex-shrink-0 bg-white shadow-sm z-10">
        <h2 className="text-sm font-semibold text-slate-800">Research Chat</h2>
      </div>

      <div className="flex-1 overflow-y-auto px-6 py-6 space-y-5 bg-white">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-slate-400 gap-3">
            <div className="text-4xl">🔬</div>
            <p className="text-sm font-medium">Enter a research topic to generate a report</p>
            <p className="text-xs text-slate-300">The 6-agent pipeline will plan, research, write, and review your report</p>
          </div>
        )}
        {messages.map((msg) => (
          <div key={msg.id}>
            <MessageBubble
              role={msg.role}
              content={msg.content}
              isStreaming={msg.isStreaming}
              isError={msg.isError}
            />
            {msg.reportData && <DocumentWorkspace data={msg.reportData} />}
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>

      <div className="p-4 border-t border-slate-200 flex-shrink-0 bg-white">
        {isLoading && (
          <div className="flex justify-center -mt-12 absolute left-0 right-0 top-auto">
            <button
              onClick={handleStop}
              className="bg-slate-800 text-white rounded-full px-4 py-1.5 text-xs font-semibold flex items-center gap-2 hover:bg-slate-700 shadow-md transition-colors z-20"
            >
              <Square className="w-3 h-3 fill-current" />
              Stop Generating
            </button>
          </div>
        )}
        <div className="flex gap-3">
          <input
            type="text"
            placeholder="Enter a research topic (e.g. 'Impact of AI on healthcare')..."
            value={inputMessage}
            onChange={(e) => setInputMessage(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isLoading}
            className="flex-1 border border-slate-300 rounded-md px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent text-slate-800 disabled:opacity-50 disabled:bg-slate-50"
          />
          <button
            onClick={handleSend}
            disabled={isLoading || !inputMessage.trim()}
            className="bg-blue-600 hover:bg-blue-700 text-white px-8 py-2.5 rounded-md font-medium text-sm transition-colors flex items-center justify-center disabled:opacity-50 disabled:hover:bg-blue-600"
          >
            Research
          </button>
        </div>
      </div>
    </div>
  )
}
