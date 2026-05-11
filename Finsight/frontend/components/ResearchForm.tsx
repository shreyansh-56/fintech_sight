"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { startResearch } from "@/lib/api";

const TARGET_TYPES = [
  { value: "financial_company", label: "Public Company" },
  { value: "industry", label: "Industry / Sector" },
  { value: "macro", label: "Macro / Economy" },
  { value: "general", label: "General Topic" },
];

export function ResearchForm() {
  const [ticker, setTicker] = useState("");
  const [targetName, setTargetName] = useState("");
  const [targetType, setTargetType] = useState("financial_company");
  const [customTasks, setCustomTasks] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    try {
      const job = await startResearch({
        target_name: targetName,
        stock_code: ticker,
        target_type: targetType,
        language: "en",
        custom_tasks: customTasks,
      });
      router.push(`/research/${job.job_id}`);
    } catch (error) {
      console.error("Failed to start research:", error);
      alert("Failed to start research. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="bg-white/5 backdrop-blur-xl border border-white/10 rounded-2xl p-8 text-left">
      <form onSubmit={handleSubmit} className="space-y-6">
        <div>
          <label className="block text-sm font-medium text-white mb-2">
            Company / Target Name
          </label>
          <input
            type="text"
            value={targetName}
            onChange={(e) => setTargetName(e.target.value)}
            placeholder="e.g., NVIDIA, Apple Inc."
            className="w-full px-4 py-2 bg-white/10 border border-white/20 rounded-lg text-white placeholder-white/50 focus:outline-none focus:ring-2 focus:ring-blue-500"
            required
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-white mb-2">
            Stock Ticker
          </label>
          <input
            type="text"
            value={ticker}
            onChange={(e) => setTicker(e.target.value.toUpperCase())}
            placeholder="e.g., NVDA, AAPL"
            className="w-full px-4 py-2 bg-white/10 border border-white/20 rounded-lg text-white placeholder-white/50 focus:outline-none focus:ring-2 focus:ring-blue-500"
            required
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-white mb-2">
            Target Type
          </label>
          <select
            value={targetType}
            onChange={(e) => setTargetType(e.target.value)}
            className="w-full px-4 py-2 bg-white/10 border border-white/20 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            {TARGET_TYPES.map((type) => (
              <option key={type.value} value={type.value}>
                {type.label}
              </option>
            ))}
          </select>
        </div>

        <button
          type="submit"
          disabled={loading}
          className="w-full py-3 px-6 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-800 text-white font-semibold rounded-lg transition-colors"
        >
          {loading ? "Starting Research..." : "Start FinSight Research"}
        </button>
      </form>
    </div>
  );
}
