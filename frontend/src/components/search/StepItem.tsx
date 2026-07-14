import { Loader2, CheckCircle2, XCircle } from 'lucide-react';
import type { AgentStep } from './useAgentStream';

interface StepItemProps {
  step: AgentStep;
  hideScreenshot?: boolean;
}

export default function StepItem({ step, hideScreenshot = false }: StepItemProps) {
  return (
    <div className="flex items-start gap-2.5 py-1.5">
      <div className="mt-0.5 shrink-0">
        {step.status === 'running' && <Loader2 className="w-4 h-4 text-blue-500 animate-spin" />}
        {step.status === 'success' && <CheckCircle2 className="w-4 h-4 text-green-500" />}
        {step.status === 'error' && <XCircle className="w-4 h-4 text-red-500" />}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider">Step {step.step}</span>
        </div>
        <p className="text-sm text-slate-800 mt-0.5 leading-snug">{step.message}</p>
        {step.reasoning && (
          <div className="mt-1 p-1.5 bg-slate-50 rounded text-xs text-slate-500 italic border border-slate-100 leading-relaxed">
            {step.reasoning}
          </div>
        )}
        {!hideScreenshot && step.screenshot && (
          <div className="mt-2 border border-slate-200 rounded overflow-hidden shadow-sm">
            <img src={step.screenshot} alt={`Step ${step.step}`} className="w-full h-auto" />
          </div>
        )}
      </div>
    </div>
  );
}
