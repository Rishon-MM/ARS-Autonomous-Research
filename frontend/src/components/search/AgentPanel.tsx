import { useEffect, useRef, useState } from 'react';
import { Bot, AlertCircle, Database, ChevronDown, ChevronUp, Brain } from 'lucide-react';
import StepItem from './StepItem';
import type { AgentStep, IngestionStats } from './useAgentStream';

interface AgentPanelProps {
  steps: AgentStep[];
  status: 'idle' | 'running' | 'done';
  error: string | null;
  paperCount?: number;
  ingestionStats?: IngestionStats | null;
  onTerminate?: () => void;
}

export default function AgentPanel({ steps, status, error, paperCount, ingestionStats, onTerminate }: AgentPanelProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [isCollapsed, setIsCollapsed] = useState(false);

  // Auto-scroll to bottom as new steps arrive
  useEffect(() => {
    if (containerRef.current && !isCollapsed) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [steps, isCollapsed]);

  // Auto-collapse when done so papers get more space
  useEffect(() => {
    if (status === 'done' && !error) {
      setIsCollapsed(true);
    } else if (status === 'running') {
      setIsCollapsed(false);
    }
  }, [status, error]);

  if (status === 'idle' && steps.length === 0) return null;

  // Find the latest screenshot to show prominently
  const latestScreenshot = [...steps].reverse().find(s => s.screenshot)?.screenshot;

  return (
    <div className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden flex flex-col mb-6 mt-4">
      {/* Header */}
      <div 
        className="px-4 py-3 border-b border-slate-100 bg-slate-50 flex items-center justify-between cursor-pointer"
        onClick={() => setIsCollapsed(!isCollapsed)}
      >
        <div className="flex items-center gap-2">
          <Bot className="w-5 h-5 text-indigo-500" />
          <h3 className="font-semibold text-slate-800">Agent Activity</h3>
          <span className="text-xs text-slate-400 ml-1">({steps.length} steps)</span>
        </div>
        <div className="flex items-center gap-2">
          {status === 'running' && (
            <div className="flex items-center gap-2">
              <span className="flex items-center gap-1.5 text-xs font-medium text-blue-600 bg-blue-50 px-2 py-1 rounded-full">
                <span className="relative flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-blue-500"></span>
                </span>
                Agent is working...
              </span>
              {onTerminate && (
                <button 
                  onClick={(e) => {
                    e.stopPropagation();
                    onTerminate();
                  }}
                  className="text-xs font-medium text-red-600 bg-red-50 hover:bg-red-100 px-2.5 py-1 rounded-full transition-colors border border-red-200"
                >
                  Terminate
                </button>
              )}
            </div>
          )}
          {status === 'done' && !error && (
            <span className="text-xs font-medium text-green-600 bg-green-50 px-2 py-1 rounded-full">
              Completed ({paperCount} found)
            </span>
          )}
          {isCollapsed ? <ChevronDown className="w-4 h-4 text-slate-400" /> : <ChevronUp className="w-4 h-4 text-slate-400" />}
        </div>
      </div>

      {!isCollapsed && (
        <>
          {/* Main Content: Split layout - screenshot left, steps right */}
          <div className="flex flex-col lg:flex-row">
            {/* Live Screenshot - Full width or left half */}
            {latestScreenshot && (
              <div className="lg:w-1/2 border-b lg:border-b-0 lg:border-r border-slate-100 bg-slate-900 p-2">
                <div className="text-[10px] uppercase tracking-wider text-slate-400 px-1 pb-1 flex items-center gap-1">
                  <span className="relative flex h-1.5 w-1.5">
                    {status === 'running' && <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>}
                    <span className={`relative inline-flex rounded-full h-1.5 w-1.5 ${status === 'running' ? 'bg-red-500' : 'bg-slate-500'}`}></span>
                  </span>
                  Live Browser View
                </div>
                <img 
                  src={latestScreenshot} 
                  alt="Agent browser view" 
                  className="w-full h-auto rounded border border-slate-700 shadow-lg"
                />
              </div>
            )}

            {/* Step Log */}
            <div 
              ref={containerRef}
              className={`p-3 flex flex-col gap-0.5 overflow-y-auto ${latestScreenshot ? 'lg:w-1/2 max-h-[300px]' : 'max-h-[400px]'}`}
            >
              {steps.map((step, i) => (
                <StepItem key={`${step.step}-${i}`} step={step} hideScreenshot />
              ))}
              
              {error && (
                <div className="mt-2 p-3 bg-red-50 text-red-700 text-sm rounded-lg flex items-start gap-2 border border-red-100">
                  <AlertCircle className="w-5 h-5 shrink-0 mt-0.5 text-red-500" />
                  <span>{error}</span>
                </div>
              )}
            </div>
          </div>

          {/* Footer: Knowledge Base + Memory Stats */}
          <div className="border-t border-slate-100 flex flex-wrap">
            {ingestionStats && ingestionStats.totalChunks > 0 && (
              <div className="px-4 py-2 bg-indigo-50 flex items-center gap-2 text-xs text-indigo-700 flex-1">
                <Database className="w-3.5 h-3.5" />
                <span className="font-medium">Knowledge Base:</span>
                <span>{ingestionStats.totalChunks} chunks from {ingestionStats.successful}/{ingestionStats.totalPapers} papers</span>
              </div>
            )}
            {steps.length > 0 && steps[0].reasoning && steps[0].reasoning !== "No prior lessons." && (
              <div className="px-4 py-2 bg-amber-50 flex items-center gap-2 text-xs text-amber-700 flex-1">
                <Brain className="w-3.5 h-3.5" />
                <span className="font-medium">Self-Learning:</span>
                <span>Using past lessons to improve search</span>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
