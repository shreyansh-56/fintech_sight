"use client";

import { useEffect, useRef, useState } from "react";
import {
  Download,
  Copy,
  FileText,
  TrendingUp,
  Building2,
  BarChart2,
  Activity,
  PieChart,
  Swords,
  ShieldAlert,
  Globe2,
  Telescope,
  Star,
  BookOpen,
  Check,
  ChevronRight,
  ExternalLink,
} from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

/* ─── Types ─────────────────────────────────────────────────────────────── */
interface ReportViewerProps {
  report: string;
  job: any;
}

/* ─── Section metadata ───────────────────────────────────────────────────── */
const SECTIONS = [
  { key: "executive",    label: "Executive Summary",       icon: Star,        color: "blue",   num: 1 },
  { key: "company",      label: "Company Overview",         icon: Building2,   color: "indigo", num: 2 },
  { key: "financial",    label: "Financial Analysis",       icon: BarChart2,   color: "cyan",   num: 3 },
  { key: "stock",        label: "Stock Performance",        icon: Activity,    color: "emerald",num: 4 },
  { key: "segment",      label: "Business Segments",        icon: PieChart,    color: "violet", num: 5 },
  { key: "competitive",  label: "Competitive Analysis",     icon: Swords,      color: "fuchsia",num: 6 },
  { key: "risk",         label: "Risk Factors",             icon: ShieldAlert, color: "rose",   num: 7 },
  { key: "macro",        label: "Macro Environment",        icon: Globe2,      color: "amber",  num: 8 },
  { key: "outlook",      label: "Outlook & Catalysts",      icon: Telescope,   color: "teal",   num: 9 },
  { key: "recommendation", label: "Investment Recommendation", icon: TrendingUp, color: "green", num: 10 },
  { key: "references",   label: "References",               icon: BookOpen,    color: "slate",  num: 11 },
];

const COLOR_MAP: Record<string, { bg: string; border: string; text: string; badge: string; glow: string }> = {
  blue:    { bg: "bg-blue-500/10",    border: "border-blue-500/30",    text: "text-blue-400",    badge: "bg-blue-500/20 text-blue-300",    glow: "shadow-blue-500/10" },
  indigo:  { bg: "bg-indigo-500/10",  border: "border-indigo-500/30",  text: "text-indigo-400",  badge: "bg-indigo-500/20 text-indigo-300",  glow: "shadow-indigo-500/10" },
  cyan:    { bg: "bg-cyan-500/10",    border: "border-cyan-500/30",    text: "text-cyan-400",    badge: "bg-cyan-500/20 text-cyan-300",    glow: "shadow-cyan-500/10" },
  emerald: { bg: "bg-emerald-500/10", border: "border-emerald-500/30", text: "text-emerald-400", badge: "bg-emerald-500/20 text-emerald-300", glow: "shadow-emerald-500/10" },
  violet:  { bg: "bg-violet-500/10",  border: "border-violet-500/30",  text: "text-violet-400",  badge: "bg-violet-500/20 text-violet-300",  glow: "shadow-violet-500/10" },
  fuchsia: { bg: "bg-fuchsia-500/10", border: "border-fuchsia-500/30", text: "text-fuchsia-400", badge: "bg-fuchsia-500/20 text-fuchsia-300", glow: "shadow-fuchsia-500/10" },
  rose:    { bg: "bg-rose-500/10",    border: "border-rose-500/30",    text: "text-rose-400",    badge: "bg-rose-500/20 text-rose-300",    glow: "shadow-rose-500/10" },
  amber:   { bg: "bg-amber-500/10",   border: "border-amber-500/30",   text: "text-amber-400",   badge: "bg-amber-500/20 text-amber-300",   glow: "shadow-amber-500/10" },
  teal:    { bg: "bg-teal-500/10",    border: "border-teal-500/30",    text: "text-teal-400",    badge: "bg-teal-500/20 text-teal-300",    glow: "shadow-teal-500/10" },
  green:   { bg: "bg-green-500/10",   border: "border-green-500/30",   text: "text-green-400",   badge: "bg-green-500/20 text-green-300",   glow: "shadow-green-500/10" },
  slate:   { bg: "bg-slate-500/10",   border: "border-slate-500/30",   text: "text-slate-400",   badge: "bg-slate-500/20 text-slate-300",   glow: "shadow-slate-500/10" },
};

/* ─── Parse heading sections from markdown ───────────────────────────────── */
function parseSectionHeadings(md: string): { id: string; title: string; level: number }[] {
  const headings: { id: string; title: string; level: number }[] = [];
  const lines = md.split("\n");
  for (const line of lines) {
    const m = line.match(/^(#{1,3})\s+(.+)/);
    if (m) {
      const title = m[2].replace(/\*\*/g, "").trim();
      const id = title.toLowerCase().replace(/[^a-z0-9]+/g, "-");
      headings.push({ id, title, level: m[1].length });
    }
  }
  return headings;
}

/* ─── Extract key metrics from report markdown ───────────────────────────── */
function extractMetrics(md: string, job: any) {
  const get = (pattern: RegExp) => { const m = md.match(pattern); return m ? m[1] : null; };
  return {
    ticker:     job?.ticker || get(/\(([A-Z]{2,5})\)/) || "—",
    price:      get(/Current Price[:\*]+\s*\$?([\d,\.]+)/) || "—",
    marketCap:  get(/Market Cap[:\*]+\s*([\$\d\.]+[BKMB]*)/) || "—",
    consensus:  get(/Analyst Consensus[:\*]+\s*([A-Z_]+)/) || "—",
    target:     get(/Price Target[:\*]+\s*\$?([\d,\.]+)/) || "—",
  };
}

/* ─── Match section # from heading ──────────────────────────────────────── */
function getSectionForHeading(title: string) {
  const t = title.toLowerCase();
  if (t.includes("executive")) return SECTIONS[0];
  if (t.includes("company") || t.includes("overview")) return SECTIONS[1];
  if (t.includes("financial") || t.includes("income") || t.includes("balance") || t.includes("cash flow")) return SECTIONS[2];
  if (t.includes("stock") || t.includes("performance") || t.includes("price")) return SECTIONS[3];
  if (t.includes("segment") || t.includes("business segment")) return SECTIONS[4];
  if (t.includes("competitive") || t.includes("peer")) return SECTIONS[5];
  if (t.includes("risk")) return SECTIONS[6];
  if (t.includes("macro") || t.includes("environment")) return SECTIONS[7];
  if (t.includes("outlook") || t.includes("catalyst")) return SECTIONS[8];
  if (t.includes("recommendation") || t.includes("investment rec")) return SECTIONS[9];
  if (t.includes("reference") || t.includes("data source")) return SECTIONS[10];
  return null;
}

/* ─── Custom Markdown Renderers ──────────────────────────────────────────── */
function makeComponents(activeSection: string | null) {
  return {
    /* Images → styled chart cards */
    img: ({ src, alt }: { src?: string; alt?: string }) => (
      <div className="my-8 group">
        <div className="relative overflow-hidden rounded-2xl border border-white/10 bg-white/5 shadow-xl shadow-black/30 transition-all duration-300 group-hover:border-white/20 group-hover:shadow-black/50">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={src}
            alt={alt || "Chart"}
            className="w-full object-contain max-h-[420px]"
            loading="lazy"
          />
          {alt && (
            <div className="flex items-center gap-2 px-4 py-3 border-t border-white/10 bg-black/20">
              <BarChart2 className="w-3.5 h-3.5 text-blue-400 shrink-0" />
              <p className="text-sm text-slate-300 font-medium">{alt}</p>
            </div>
          )}
        </div>
      </div>
    ),

    /* Tables → styled glass tables */
    table: ({ children }: { children?: React.ReactNode }) => (
      <div className="my-6 overflow-x-auto rounded-xl border border-white/10">
        <table className="w-full text-sm">{children}</table>
      </div>
    ),
    thead: ({ children }: { children?: React.ReactNode }) => (
      <thead className="bg-white/10 text-slate-200 uppercase tracking-wide text-xs">{children}</thead>
    ),
    tbody: ({ children }: { children?: React.ReactNode }) => (
      <tbody className="divide-y divide-white/5">{children}</tbody>
    ),
    tr: ({ children }: { children?: React.ReactNode }) => (
      <tr className="hover:bg-white/5 transition-colors">{children}</tr>
    ),
    th: ({ children }: { children?: React.ReactNode }) => (
      <th className="px-4 py-3 text-left text-slate-300 font-semibold">{children}</th>
    ),
    td: ({ children }: { children?: React.ReactNode }) => (
      <td className="px-4 py-3 text-slate-300">{children}</td>
    ),

    /* H1/H2 → styled section headers */
    h1: ({ children }: { children?: React.ReactNode }) => {
      const title = String(children ?? "");
      const id = title.toLowerCase().replace(/[^a-z0-9]+/g, "-");
      const sec = getSectionForHeading(title);
      const c = sec ? COLOR_MAP[sec.color] : COLOR_MAP.slate;
      const Icon = sec?.icon ?? FileText;
      return (
        <div id={id} className={`flex items-center gap-3 mt-10 mb-5 pt-6 pb-4 px-5 rounded-xl border ${c.border} ${c.bg} scroll-mt-24`}>
          <div className={`flex items-center justify-center w-9 h-9 rounded-lg ${c.badge}`}>
            <Icon className="w-5 h-5" />
          </div>
          <h1 className={`text-xl font-bold ${c.text}`}>{children}</h1>
        </div>
      );
    },
    h2: ({ children }: { children?: React.ReactNode }) => {
      const title = String(children ?? "");
      const id = title.toLowerCase().replace(/[^a-z0-9]+/g, "-");
      const sec = getSectionForHeading(title);
      const c = sec ? COLOR_MAP[sec.color] : COLOR_MAP.slate;
      const Icon = sec?.icon ?? FileText;
      return (
        <div id={id} className={`flex items-center gap-3 mt-10 mb-5 pt-5 pb-4 px-5 rounded-xl border ${c.border} ${c.bg} scroll-mt-24`}>
          <div className={`flex items-center justify-center w-8 h-8 rounded-lg ${c.badge}`}>
            <Icon className="w-4 h-4" />
          </div>
          <h2 className={`text-lg font-bold ${c.text}`}>{children}</h2>
        </div>
      );
    },
    h3: ({ children }: { children?: React.ReactNode }) => {
      const title = String(children ?? "");
      const id = title.toLowerCase().replace(/[^a-z0-9]+/g, "-");
      return (
        <h3 id={id} className="text-white font-semibold text-base mt-6 mb-3 flex items-center gap-2 scroll-mt-24">
          <ChevronRight className="w-4 h-4 text-blue-400" />
          {children}
        </h3>
      );
    },

    /* Paragraphs */
    p: ({ children }: { children?: React.ReactNode }) => (
      <p className="text-slate-300 leading-7 mb-4">{children}</p>
    ),

    /* Lists */
    ul: ({ children }: { children?: React.ReactNode }) => (
      <ul className="space-y-1.5 mb-4 ml-1">{children}</ul>
    ),
    ol: ({ children }: { children?: React.ReactNode }) => (
      <ol className="space-y-1.5 mb-4 ml-1 list-decimal list-inside">{children}</ol>
    ),
    li: ({ children }: { children?: React.ReactNode }) => (
      <li className="flex items-start gap-2 text-slate-300 leading-6">
        <span className="mt-1.5 w-1.5 h-1.5 rounded-full bg-blue-400 shrink-0" />
        <span>{children}</span>
      </li>
    ),

    /* Strong */
    strong: ({ children }: { children?: React.ReactNode }) => (
      <strong className="text-white font-semibold">{children}</strong>
    ),

    /* Code */
    code: ({ children }: { children?: React.ReactNode }) => (
      <code className="px-1.5 py-0.5 rounded bg-white/10 text-blue-300 text-sm font-mono">{children}</code>
    ),

    /* HR */
    hr: () => (
      <hr className="my-8 border-white/10" />
    ),

    /* Blockquote */
    blockquote: ({ children }: { children?: React.ReactNode }) => (
      <blockquote className="border-l-4 border-blue-500 pl-4 my-4 bg-blue-500/5 rounded-r-lg py-3 pr-4 italic text-slate-300">
        {children}
      </blockquote>
    ),
  };
}

/* ─── Main Component ────────────────────────────────────────────────────── */
export function ReportViewer({ report, job }: ReportViewerProps) {
  const [copied, setCopied] = useState(false);
  const [activeSection, setActiveSection] = useState<string | null>(null);
  const metrics = extractMetrics(report, job);
  const wordCount = report ? report.split(/\s+/).filter(Boolean).length : 0;

  const handleCopy = () => {
    navigator.clipboard.writeText(report);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownload = () => {
    // Build a clean HTML document and print it — browser saves as PDF
    const printWindow = window.open("", "_blank");
    if (!printWindow) return;

    // Convert markdown image URLs to absolute if needed
    const htmlContent = report
      .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
      .replace(/\*(.*?)\*/g, "<em>$1</em>")
      .replace(/^# (.*$)/gim, "<h1>$1</h1>")
      .replace(/^## (.*$)/gim, "<h2>$1</h2>")
      .replace(/^### (.*$)/gim, "<h3>$1</h3>")
      .replace(/^---$/gim, "<hr>")
      .replace(/!\[([^\]]+)\]\(([^)]+)\)/g,
        '<figure><img src="$2" alt="$1" style="max-width:100%;border-radius:8px;margin:16px 0;"><figcaption style="text-align:center;color:#555;font-size:12px;">$1</figcaption></figure>')
      .replace(/\|(.+)\|/g, (line) => {
        const cells = line.split("|").filter(Boolean).map(c => `<td>${c.trim()}</td>`).join("");
        return `<tr>${cells}</tr>`;
      })
      .replace(/^- (.+)$/gim, "<li>$1</li>")
      .replace(/(<li>.*<\/li>\n?)+/g, (m) => `<ul>${m}</ul>`)
      .replace(/\n\n/g, "</p><p>")
      .replace(/^(?!<[hHuUtT])(.+)$/gim, "<p>$1</p>");

    printWindow.document.write(`
      <!DOCTYPE html>
      <html>
      <head>
        <meta charset="UTF-8">
        <title>FinSight — ${metrics.ticker} Research Report</title>
        <style>
          * { box-sizing: border-box; margin: 0; padding: 0; }
          body { font-family: 'Georgia', serif; color: #1a1a2e; background: #fff;
                 font-size: 11pt; line-height: 1.7; padding: 40px 60px; max-width: 900px; margin: 0 auto; }
          h1 { font-size: 20pt; color: #1a1a2e; margin: 24px 0 12px;
               border-bottom: 2px solid #3b82f6; padding-bottom: 8px; }
          h2 { font-size: 16pt; color: #1e3a5f; margin: 20px 0 10px;
               border-left: 4px solid #3b82f6; padding-left: 12px; }
          h3 { font-size: 13pt; color: #374151; margin: 16px 0 8px; }
          p  { margin-bottom: 10px; }
          strong { color: #111; }
          table { width: 100%; border-collapse: collapse; margin: 16px 0; font-size: 10pt; }
          th { background: #1e3a5f; color: white; padding: 8px 12px; text-align: left; }
          td { padding: 7px 12px; border-bottom: 1px solid #e5e7eb; }
          tr:nth-child(even) td { background: #f9fafb; }
          ul { margin: 8px 0 12px 20px; }
          li { margin-bottom: 4px; }
          hr { border: none; border-top: 1px solid #e5e7eb; margin: 24px 0; }
          figure { text-align: center; margin: 20px 0; page-break-inside: avoid; }
          img { max-width: 100%; height: auto; border: 1px solid #e5e7eb; border-radius: 8px; }
          figcaption { color: #6b7280; font-size: 9pt; margin-top: 6px; font-style: italic; }
          .cover { text-align: center; padding: 60px 0 40px; border-bottom: 2px solid #3b82f6; margin-bottom: 32px; }
          .cover h1 { border: none; font-size: 28pt; }
          .cover .meta { color: #6b7280; margin-top: 12px; font-size: 11pt; }
          .cover .badge { display: inline-block; background: #dbeafe; color: #1e40af;
                          padding: 4px 14px; border-radius: 20px; font-weight: bold; margin-top: 8px; }
          @media print {
            body { padding: 20px 40px; }
            h2 { page-break-before: auto; }
            figure { page-break-inside: avoid; }
          }
        </style>
      </head>
      <body>
        <div class="cover">
          <h1>${metrics.ticker} Investment Research Report</h1>
          <p class="meta">FinSight AI Research &nbsp;·&nbsp; Generated ${new Date().toLocaleDateString("en-US", { year: "numeric", month: "long", day: "numeric" })}</p>
          <p class="meta">Current Price: <strong>$${metrics.price}</strong> &nbsp;|&nbsp; Market Cap: <strong>${metrics.marketCap}</strong> &nbsp;|&nbsp; Target: <strong>$${metrics.target}</strong></p>
          <div class="badge">${metrics.consensus.replace("_", " ")}</div>
        </div>
        ${htmlContent}
      </body>
      </html>
    `);
    printWindow.document.close();
    // Wait for images to load before printing
    setTimeout(() => {
      printWindow.focus();
      printWindow.print();
    }, 1200);
  };

  const scrollTo = (id: string) => {
    const el = document.getElementById(id);
    if (el) { el.scrollIntoView({ behavior: "smooth", block: "start" }); return; }
  };

  // Fuzzy scroll: finds the first h1/h2/h3 whose text includes the label
  const scrollToSection = (label: string) => {
    const allElements = document.querySelectorAll("h1, h2, h3");
    const lower = label.toLowerCase();

    for (const el of Array.from(allElements)) {
      const text = (el.textContent ?? "").toLowerCase();
      if (text.includes(lower)) {
        // Find the nearest scrollable ancestor (the overflow-y-auto panel div)
        let scrollParent: Element | null = el.parentElement;
        while (scrollParent) {
          const style = window.getComputedStyle(scrollParent);
          if (style.overflowY === "auto" || style.overflowY === "scroll") break;
          scrollParent = scrollParent.parentElement;
        }

        if (scrollParent) {
          // Scroll within the overflow container
          const containerTop = scrollParent.getBoundingClientRect().top;
          const elTop = el.getBoundingClientRect().top;
          const offset = elTop - containerTop + scrollParent.scrollTop - 72;
          scrollParent.scrollTo({ top: offset, behavior: "smooth" });
        } else {
          // Fallback: use window scroll
          el.scrollIntoView({ behavior: "smooth", block: "start" });
        }
        return;
      }
    }
  };

  const consensusColor =
    metrics.consensus.includes("BUY") ? "text-green-400" :
    metrics.consensus.includes("SELL") ? "text-rose-400" : "text-amber-400";

  return (
    <div className="min-h-screen bg-[#050a18]">
      {/* ── Top action bar (compact, no back button — sidebar owns nav) ── */}
      <div className="sticky top-0 z-50 border-b border-white/10 bg-[#050a18]/95 backdrop-blur-xl">
        <div className="max-w-screen-2xl mx-auto px-6 h-14 flex items-center justify-between gap-6">
          {/* Left: ticker badge */}
          <div className="flex items-center gap-3">
            <span className="px-3 py-1 rounded-full bg-blue-500/20 border border-blue-500/30 text-blue-300 font-mono font-bold text-sm">
              {metrics.ticker}
            </span>
            <span className="text-slate-500 text-sm hidden sm:inline">{wordCount.toLocaleString()} words</span>
          </div>
          {/* Right: actions */}
          <div className="flex items-center gap-2">
            <button
              onClick={handleCopy}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-white/8 hover:bg-white/15 border border-white/10 text-slate-300 text-sm rounded-lg transition-all"
            >
              {copied ? <Check className="w-3.5 h-3.5 text-green-400" /> : <Copy className="w-3.5 h-3.5" />}
              {copied ? "Copied!" : "Copy"}
            </button>
            <button
              onClick={handleDownload}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-white text-sm rounded-lg transition-all"
            >
              <Download className="w-3.5 h-3.5" />
              Download PDF
            </button>
          </div>
        </div>
      </div>

      {/* ── Metric cards header ───────────────────────────────────────── */}
      <div className="border-b border-white/8 bg-gradient-to-r from-blue-950/40 via-transparent to-cyan-950/20">
        <div className="max-w-screen-2xl mx-auto px-6 py-6">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {[
              { label: "Current Price", value: `$${metrics.price}`, sub: "Live market price", accent: "text-white", icon: "💰" },
              { label: "Market Cap", value: metrics.marketCap, sub: "Total market value", accent: "text-white", icon: "🏦" },
              { label: "Analyst Target", value: `$${metrics.target}`, sub: "Mean analyst estimate", accent: "text-green-400", icon: "🎯" },
              { label: "Consensus", value: metrics.consensus.replace("_", " "), sub: "Wall Street rating", accent: consensusColor, icon: "📊" },
            ].map((m) => (
              <div key={m.label} className="group relative overflow-hidden rounded-xl border border-white/10 bg-white/5 px-5 py-4 hover:border-white/20 transition-all">
                <div className="absolute inset-0 bg-gradient-to-br from-white/3 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
                <div className="flex items-start justify-between">
                  <div>
                    <p className="text-xs text-slate-500 uppercase tracking-widest mb-1">{m.label}</p>
                    <p className={`text-xl font-bold ${m.accent} tabular-nums`}>{m.value}</p>
                    <p className="text-xs text-slate-500 mt-0.5">{m.sub}</p>
                  </div>
                  <span className="text-2xl">{m.icon}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* ── Body: sidebar + content ───────────────────────────────────── */}
      <div className="max-w-screen-2xl mx-auto px-4 py-8 flex gap-8">
        {/* Sticky sidebar TOC */}
        <aside className="hidden xl:block w-64 shrink-0">
          <div className="sticky top-24 space-y-1">
            <p className="text-xs uppercase tracking-widest text-slate-600 font-semibold mb-3 px-2">Contents</p>
            {SECTIONS.map((sec) => {
              const c = COLOR_MAP[sec.color];
              const Icon = sec.icon;
              return (
                <button
                  key={sec.key}
                  onClick={() => scrollToSection(sec.label)}
                  className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-left text-sm transition-all group
                    hover:bg-white/8 border border-transparent hover:border-white/10
                    ${activeSection === sec.key ? "bg-white/8 border-white/10" : ""}`}
                >
                  <Icon className={`w-3.5 h-3.5 shrink-0 ${activeSection === sec.key ? c.text : "text-slate-600 group-hover:text-slate-400"}`} />
                  <span className={`truncate ${activeSection === sec.key ? c.text : "text-slate-500 group-hover:text-slate-200"}`}>
                    {sec.num}. {sec.label}
                  </span>
                </button>
              );
            })}
          </div>
        </aside>

        {/* Main report content */}
        <main className="flex-1 min-w-0">
          {/* Section pills (mobile) */}
          <div className="xl:hidden flex flex-wrap gap-2 mb-6">
            {SECTIONS.map((sec) => {
              const c = COLOR_MAP[sec.color];
              return (
                <button
                  key={sec.key}
                  onClick={() => scrollToSection(sec.label)}
                  className={`px-3 py-1 text-xs rounded-full border ${c.badge} ${c.border} transition-all hover:opacity-80`}
                >
                  {sec.num}. {sec.label}
                </button>
              );
            })}
          </div>

          {/* Report body */}
          <div className="rounded-2xl border border-white/10 bg-white/[0.03] backdrop-blur-sm overflow-hidden">
            <div className="p-8 md:p-10">
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={makeComponents(activeSection) as any}
              >
                {report}
              </ReactMarkdown>
            </div>

            {/* Footer */}
            <div className="border-t border-white/10 px-8 py-5 bg-white/[0.02] flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
              <div className="flex items-center gap-3">
                <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-blue-500 to-cyan-500 flex items-center justify-center">
                  <TrendingUp className="w-4 h-4 text-white" />
                </div>
                <div>
                  <p className="text-sm font-semibold text-white">FinSight AI Research</p>
                  <p className="text-xs text-slate-500">Generated {new Date().toLocaleDateString("en-US", { year: "numeric", month: "long", day: "numeric" })} · {wordCount.toLocaleString()} words</p>
                </div>
              </div>
              <div className="flex gap-2">
                <button
                  onClick={handleCopy}
                  className="flex items-center gap-1.5 px-4 py-2 text-sm bg-white/8 hover:bg-white/15 border border-white/10 text-slate-300 rounded-lg transition-all"
                >
                  {copied ? <Check className="w-4 h-4 text-green-400" /> : <Copy className="w-4 h-4" />}
                  {copied ? "Copied!" : "Copy Markdown"}
                </button>
                <button
                  onClick={handleDownload}
                  className="flex items-center gap-1.5 px-4 py-2 text-sm bg-blue-600 hover:bg-blue-500 text-white rounded-lg transition-all"
                >
                  <Download className="w-4 h-4" />
                  Download PDF
                </button>
              </div>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
