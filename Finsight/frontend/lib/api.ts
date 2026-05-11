/** API client for FinSight backend */
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface ResearchRequest {
  target_name: string;
  stock_code: string;
  target_type?: string;
  language?: string;
  custom_tasks?: string[];
}

export interface ResearchJob {
  job_id: string;
  status: string;
  stage: string;
  progress: number;
  report_path: string;
  error: string;
}

export async function startResearch(request: ResearchRequest): Promise<ResearchJob> {
  const response = await fetch(`${API_BASE}/api/research/start`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  return response.json();
}

export async function getJobStatus(jobId: string): Promise<ResearchJob> {
  const response = await fetch(`${API_BASE}/api/research/${jobId}`);
  return response.json();
}

export async function getReport(jobId: string): Promise<{ markdown: string; job: ResearchJob }> {
  const response = await fetch(`${API_BASE}/api/research/${jobId}/report`);
  return response.json();
}

export async function getHistory(): Promise<ResearchJob[]> {
  const response = await fetch(`${API_BASE}/api/history`);
  return response.json();
}
