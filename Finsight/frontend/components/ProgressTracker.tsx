"use client";

import { Database, BarChart3, FileText, CheckCircle, Clock, TrendingUp, Cpu } from "lucide-react";
import { ProgressEvent } from "@/lib/websocket";

const STAGES = [
  {
    id: "data_collection",
    label: "Data Collection",
    icon: Database,
    description: "Gathering financial data, news, SEC filings & macro indicators",
    color: "blue",
  },
  {
    id: "parallel_perspectives",
    label: "Parallel Analysis",
    icon: Cpu,
    description: "Running 6 parallel analytical perspectives simultaneously",
    color: "purple",
  },
  {
    id: "chart_generation",
    label: "Chart Generation",
    icon: TrendingUp,
    description: "Generating 6 professional financial charts",
    color: "yellow",
  },
  {
    id: "report_generation",
    label: "Report Writing",
    icon: FileText,
    description: "Composing comprehensive 5,000+ word investment report",
    color: "green",
  },
];

interface ProgressTrackerProps {
  job: any;
  events: ProgressEvent[];
}

export function ProgressTracker({ job, events }: ProgressTrackerProps) {
  const currentStage = job?.stage || "";

  // Derive progress from WS events (stage_done / progress carry progress %)
  const wsProgress = events
    .filter((e) => typeof e.progress === "number")
    .at(-1)?.progress;
  const progress = wsProgress ?? job?.progress ?? 0;

  // Build a Set of stage ids that have been explicitly marked done
  const completedStages = new Set(
    events
      .filter((e) => e.type === "stage_done" && e.stage)
      .map((e) => e.stage as string)
  );

  // Latest log message
  const latestMessage = events
    .filter((e) => e.message)
    .at(-1)?.message;

  return (
    <div className="max-w-4xl mx-auto px-6 py-12">
      <div className="mb-8">
        <h2 className="text-3xl font-bold text-white mb-2">FinSight Pipeline</h2>
        <p className="text-slate-400">
          {latestMessage || "Processing your research request..."}
        </p>
      </div>

      <div className="mb-8">
        <div className="flex justify-between text-sm text-slate-400 mb-2">
          <span>Overall Progress</span>
          <span>{progress}%</span>
        </div>
        <div className="w-full bg-white/10 rounded-full h-2">
          <div
            className="bg-blue-600 h-2 rounded-full transition-all duration-700"
            style={{ width: `${Math.max(progress, 2)}%` }}
          />
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {STAGES.map((stage) => {
          const Icon = stage.icon;
          const isComplete = completedStages.has(stage.id);
          const isActive = !isComplete && currentStage === stage.id;

          return (
            <div
              key={stage.id}
              className={`relative p-5 rounded-xl border transition-all ${
                isActive
                  ? `bg-${stage.color}-500/20 border-${stage.color}-500`
                  : isComplete
                  ? "bg-green-500/10 border-green-500/50"
                  : "bg-white/5 border-white/10"
              }`}
            >
              <div className="flex items-center justify-between mb-3">
                <Icon
                  className={`w-7 h-7 ${
                    isActive
                      ? `text-${stage.color}-400`
                      : isComplete
                      ? "text-green-400"
                      : "text-slate-500"
                  }`}
                />
                {isComplete ? (
                  <CheckCircle className="w-5 h-5 text-green-400" />
                ) : isActive ? (
                  <Clock className="w-5 h-5 text-blue-400 animate-spin" />
                ) : null}
              </div>
              <h3 className="text-base font-semibold text-white mb-1">
                {stage.label}
              </h3>
              <p className="text-xs text-slate-400">{stage.description}</p>
            </div>
          );
        })}
      </div>

      {events.length > 0 && (
        <div className="mt-8 bg-white/5 border border-white/10 rounded-xl p-6">
          <h3 className="text-lg font-semibold text-white mb-4">Activity Log</h3>
          <div className="space-y-2 max-h-64 overflow-y-auto">
            {events.slice(-15).map((event, index) => (
              <div
                key={index}
                className="text-sm text-slate-300 font-mono border-l-2 border-white/20 pl-3"
              >
                <span className="text-slate-500">[{event.type}]</span>{" "}
                {event.message || event.stage || ""}
                {typeof event.progress === "number" && (
                  <span className="ml-2 text-blue-400">{event.progress}%</span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
