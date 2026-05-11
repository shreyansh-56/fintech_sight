"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import {
  Plus,
  TrendingUp,
  Clock,
  CheckCircle2,
  XCircle,
  ChevronRight,
  Loader2,
  Search,
  Building2,
} from "lucide-react";
import { startResearch, getJobStatus, getReport } from "@/lib/api";
import { useWebSocket } from "@/lib/websocket";
import { ProgressTracker } from "@/components/ProgressTracker";
import { ReportViewer } from "@/components/ReportViewer";

/* ─── Types ─────────────────────────────────────────────────────── */
type AppState = "selection" | "progress" | "report";

interface HistoryItem {
  jobId: string;
  ticker: string;
  companyName: string;
  date: string;
  status: "completed" | "failed" | "running";
  report?: string;
}

/* ─── localStorage helpers ───────────────────────────────────────── */
const LS_KEY = "finsight_history";

function loadHistory(): HistoryItem[] {
  if (typeof window === "undefined") return [];
  try {
    return JSON.parse(localStorage.getItem(LS_KEY) || "[]");
  } catch {
    return [];
  }
}

function saveHistory(items: HistoryItem[]) {
  localStorage.setItem(LS_KEY, JSON.stringify(items.slice(0, 50)));
}

/* ─── Sidebar ────────────────────────────────────────────────────── */
function Sidebar({
  history,
  activeJobId,
  onNew,
  onSelectHistory,
}: {
  history: HistoryItem[];
  activeJobId: string | null;
  onNew: () => void;
  onSelectHistory: (item: HistoryItem) => void;
}) {
  return (
    <aside className="w-64 shrink-0 h-screen flex flex-col bg-[#0a0f1e] border-r border-white/8 fixed left-0 top-0 z-40">
      {/* Logo */}
      <div className="flex items-center gap-3 px-4 pt-5 pb-4 border-b border-white/8">
        <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500 to-cyan-400 flex items-center justify-center shadow-lg shadow-blue-500/30">
          <TrendingUp className="w-4 h-4 text-white" />
        </div>
        <div>
          <p className="text-white font-bold text-sm leading-none">FinSight</p>
          <p className="text-slate-500 text-xs mt-0.5">AI Research</p>
        </div>
      </div>

      {/* New Analysis button */}
      <div className="px-3 pt-3 pb-2">
        <button
          onClick={onNew}
          className="w-full flex items-center gap-2 px-3 py-2.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium transition-all shadow-lg shadow-blue-600/20 hover:shadow-blue-500/30"
        >
          <Plus className="w-4 h-4" />
          New Analysis
        </button>
      </div>

      {/* History label */}
      <div className="px-4 pt-3 pb-1">
        <p className="text-xs uppercase tracking-widest text-slate-600 font-semibold">History</p>
      </div>

      {/* History list */}
      <div className="flex-1 overflow-y-auto px-2 pb-4 space-y-0.5">
        {history.length === 0 ? (
          <div className="px-3 py-8 text-center">
            <Clock className="w-6 h-6 text-slate-700 mx-auto mb-2" />
            <p className="text-xs text-slate-600">No reports yet</p>
          </div>
        ) : (
          history.map((item) => {
            const isActive = item.jobId === activeJobId;
            return (
              <button
                key={item.jobId}
                onClick={() => onSelectHistory(item)}
                className={`w-full text-left px-3 py-2.5 rounded-lg transition-all group ${
                  isActive
                    ? "bg-blue-600/20 border border-blue-500/30"
                    : "hover:bg-white/5 border border-transparent"
                }`}
              >
                <div className="flex items-start justify-between gap-1.5">
                  <div className="min-w-0">
                    <p className={`text-sm font-medium truncate ${isActive ? "text-blue-300" : "text-slate-300 group-hover:text-white"}`}>
                      {item.ticker || item.companyName}
                    </p>
                    <p className="text-xs text-slate-600 truncate mt-0.5">{item.companyName}</p>
                    <p className="text-xs text-slate-700 mt-0.5">{item.date}</p>
                  </div>
                  <StatusBadge status={item.status} />
                </div>
              </button>
            );
          })
        )}
      </div>

      {/* Footer */}
      <div className="px-4 py-3 border-t border-white/8">
        <p className="text-xs text-slate-700 text-center">
          Powered by Gemini · Groq
        </p>
      </div>
    </aside>
  );
}

function StatusBadge({ status }: { status: HistoryItem["status"] }) {
  if (status === "completed")
    return <CheckCircle2 className="w-3.5 h-3.5 text-green-400 shrink-0 mt-0.5" />;
  if (status === "failed")
    return <XCircle className="w-3.5 h-3.5 text-rose-400 shrink-0 mt-0.5" />;
  return <Loader2 className="w-3.5 h-3.5 text-blue-400 shrink-0 mt-0.5 animate-spin" />;
}

/* ─── Selection screen ───────────────────────────────────────────── */
function SelectionPanel({ onStart }: { onStart: (jobId: string, ticker: string, name: string) => void }) {
  const [ticker, setTicker] = useState("");
  const [name, setName] = useState("");
  const [type, setType] = useState("financial_company");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const TYPES = [
    { value: "financial_company", label: "Public Company", emoji: "🏢" },
    { value: "industry", label: "Industry / Sector", emoji: "🏭" },
    { value: "macro", label: "Macro / Economy", emoji: "🌐" },
  ];

  const SUGGESTIONS = [
    { ticker: "AAPL", name: "Apple Inc." },
    { ticker: "MSFT", name: "Microsoft" },
    { ticker: "NVDA", name: "NVIDIA" },
    { ticker: "GOOGL", name: "Alphabet" },
    { ticker: "AMZN", name: "Amazon" },
    { ticker: "META", name: "Meta" },
  ];

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!ticker || !name) return;
    setLoading(true);
    setError("");
    try {
      const job = await startResearch({
        target_name: name,
        stock_code: ticker,
        target_type: type,
        language: "en",
        custom_tasks: [],
      });
      onStart(job.job_id, ticker, name);
    } catch {
      setError("Failed to start research. Is the backend running?");
    } finally {
      setLoading(false);
    }
  }

  function fillSuggestion(t: string, n: string) {
    setTicker(t);
    setName(n);
  }

  return (
    <div className="flex-1 flex flex-col items-center justify-center px-6 py-12 min-h-screen">
      {/* Hero */}
      <div className="text-center mb-10 max-w-xl">
        <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-gradient-to-br from-blue-500 to-cyan-400 shadow-xl shadow-blue-500/30 mb-5">
          <TrendingUp className="w-7 h-7 text-white" />
        </div>
        <h1 className="text-4xl font-bold text-white mb-3">
          FinSight <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-cyan-400">Research</span>
        </h1>
        <p className="text-slate-400 text-base leading-relaxed">
          Multi-agent AI financial analysis. One ticker. One click. Publication-ready institutional reports.
        </p>
      </div>

      {/* Form card */}
      <div className="w-full max-w-lg">
        <div className="bg-white/[0.04] backdrop-blur-xl border border-white/10 rounded-2xl p-7 shadow-2xl shadow-black/40">
          <form onSubmit={handleSubmit} className="space-y-5">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold text-slate-400 uppercase tracking-widest mb-2">
                  Stock Ticker
                </label>
                <input
                  value={ticker}
                  onChange={(e) => setTicker(e.target.value.toUpperCase())}
                  placeholder="e.g. NVDA"
                  className="w-full px-3.5 py-2.5 bg-white/8 border border-white/12 rounded-xl text-white placeholder-slate-600 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/50 focus:border-blue-500/50 transition-all font-mono tracking-wide"
                  required
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-400 uppercase tracking-widest mb-2">
                  Company Name
                </label>
                <input
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g. NVIDIA Corp."
                  className="w-full px-3.5 py-2.5 bg-white/8 border border-white/12 rounded-xl text-white placeholder-slate-600 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/50 focus:border-blue-500/50 transition-all"
                  required
                />
              </div>
            </div>

            {/* Type selector */}
            <div>
              <label className="block text-xs font-semibold text-slate-400 uppercase tracking-widest mb-2">
                Analysis Type
              </label>
              <div className="grid grid-cols-3 gap-2">
                {TYPES.map((t) => (
                  <button
                    key={t.value}
                    type="button"
                    onClick={() => setType(t.value)}
                    className={`flex flex-col items-center gap-1 px-2 py-2.5 rounded-xl border text-xs font-medium transition-all ${
                      type === t.value
                        ? "bg-blue-600/25 border-blue-500/50 text-blue-300"
                        : "bg-white/4 border-white/10 text-slate-500 hover:text-slate-300 hover:bg-white/8"
                    }`}
                  >
                    <span className="text-base">{t.emoji}</span>
                    {t.label}
                  </button>
                ))}
              </div>
            </div>

            {error && (
              <div className="flex items-center gap-2 px-3 py-2 bg-rose-500/10 border border-rose-500/20 rounded-lg text-rose-400 text-sm">
                <XCircle className="w-4 h-4 shrink-0" />
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading || !ticker || !name}
              className="w-full flex items-center justify-center gap-2 py-3 px-6 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed text-white font-semibold rounded-xl transition-all shadow-lg shadow-blue-600/25 hover:shadow-blue-500/30 text-sm"
            >
              {loading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Starting Pipeline…
                </>
              ) : (
                <>
                  <Search className="w-4 h-4" />
                  Run Deep Research
                  <ChevronRight className="w-4 h-4" />
                </>
              )}
            </button>
          </form>
        </div>

        {/* Suggestions */}
        <div className="mt-5">
          <p className="text-xs text-slate-600 text-center mb-3 uppercase tracking-widest">Quick picks</p>
          <div className="flex flex-wrap justify-center gap-2">
            {SUGGESTIONS.map((s) => (
              <button
                key={s.ticker}
                onClick={() => fillSuggestion(s.ticker, s.name)}
                className="flex items-center gap-1.5 px-3 py-1.5 bg-white/5 hover:bg-white/10 border border-white/10 hover:border-white/20 rounded-full text-xs text-slate-400 hover:text-white transition-all"
              >
                <Building2 className="w-3 h-3" />
                <span className="font-mono font-bold text-slate-300">{s.ticker}</span>
                <span>{s.name}</span>
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

/* ─── Progress panel (wrapper) ───────────────────────────────────── */
function ProgressPanel({
  jobId,
  onComplete,
}: {
  jobId: string;
  onComplete: (report: string, job: any) => void;
}) {
  const [job, setJob] = useState<any>(null);
  const { events } = useWebSocket(jobId);
  const fetchedReport = useRef(false);

  useEffect(() => {
    const interval = setInterval(async () => {
      try {
        const j = await getJobStatus(jobId);
        setJob(j);
        if (j.status === "done" && !fetchedReport.current) {
          fetchedReport.current = true;
          clearInterval(interval);
          const data = await getReport(jobId);
          onComplete(data.markdown, j);
        }
      } catch {
        // swallow polling errors
      }
    }, 2000);
    return () => clearInterval(interval);
  }, [jobId, onComplete]);

  return (
    <div className="flex-1 overflow-y-auto">
      <ProgressTracker job={job} events={events} />
    </div>
  );
}

/* ─── Root App ───────────────────────────────────────────────────── */
export default function App() {
  const [appState, setAppState] = useState<AppState>("selection");
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [activeTicker, setActiveTicker] = useState("");
  const [activeName, setActiveName] = useState("");
  const [report, setReport] = useState("");
  const [activeJob, setActiveJob] = useState<any>(null);
  const [history, setHistory] = useState<HistoryItem[]>([]);

  // Load history on mount
  useEffect(() => {
    setHistory(loadHistory());
  }, []);

  /* Save to history helper */
  const upsertHistory = useCallback(
    (item: Partial<HistoryItem> & { jobId: string }) => {
      setHistory((prev) => {
        const idx = prev.findIndex((h) => h.jobId === item.jobId);
        let next: HistoryItem[];
        if (idx >= 0) {
          next = prev.map((h) => (h.jobId === item.jobId ? { ...h, ...item } as HistoryItem : h));
        } else {
          next = [item as HistoryItem, ...prev];
        }
        saveHistory(next);
        return next;
      });
    },
    []
  );

  /* Start a new analysis */
  function handleStart(jobId: string, ticker: string, name: string) {
    setActiveJobId(jobId);
    setActiveTicker(ticker);
    setActiveName(name);
    setReport("");
    setActiveJob(null);
    setAppState("progress");

    upsertHistory({
      jobId,
      ticker,
      companyName: name,
      date: new Date().toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" }),
      status: "running",
    });
  }

  /* Pipeline completes */
  function handleComplete(md: string, job: any) {
    setReport(md);
    setActiveJob(job);
    setAppState("report");

    upsertHistory({
      jobId: job.job_id,
      ticker: activeTicker,
      companyName: activeName,
      date: new Date().toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" }),
      status: "completed",
      report: md,
    });
  }

  /* New Analysis button */
  function handleNew() {
    setAppState("selection");
    setActiveJobId(null);
    setReport("");
    setActiveJob(null);
  }

  /* Click a history item */
  function handleSelectHistory(item: HistoryItem) {
    setActiveJobId(item.jobId);
    setActiveTicker(item.ticker);
    setActiveName(item.companyName);

    if (item.report) {
      setReport(item.report);
      setActiveJob({ job_id: item.jobId });
      setAppState("report");
    } else if (item.status === "running") {
      setAppState("progress");
    } else {
      setAppState("selection");
    }
  }

  return (
    <div className="flex h-screen bg-[#050a18] overflow-hidden">
      {/* Sidebar */}
      <Sidebar
        history={history}
        activeJobId={activeJobId}
        onNew={handleNew}
        onSelectHistory={handleSelectHistory}
      />

      {/* Main panel — offset by sidebar width */}
      <div className="flex-1 ml-64 h-screen overflow-y-auto">
        {appState === "selection" && (
          <SelectionPanel onStart={handleStart} />
        )}

        {appState === "progress" && activeJobId && (
          <ProgressPanel
            jobId={activeJobId}
            onComplete={handleComplete}
          />
        )}

        {appState === "report" && report && (
          <ReportViewer report={report} job={activeJob} />
        )}
      </div>
    </div>
  );
}
