"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { ProgressTracker } from "@/components/ProgressTracker";
import { ReportViewer } from "@/components/ReportViewer";
import { getJobStatus, getReport } from "@/lib/api";
import { useWebSocket } from "@/lib/websocket";

export default function ResearchPage() {
  const params = useParams();
  const router = useRouter();
  const jobId = params.id as string;

  const [job, setJob] = useState<any>(null);
  const [report, setReport] = useState<string>("");
  const { events, isConnected } = useWebSocket(jobId);

  useEffect(() => {
    fetchJob();
    const interval = setInterval(fetchJob, 2000);
    return () => clearInterval(interval);
  }, [jobId]);

  useEffect(() => {
    if (job?.status === "done") {
      fetchReport();
    }
  }, [job?.status]);

  const fetchJob = async () => {
    try {
      const jobData = await getJobStatus(jobId);
      setJob(jobData);
      if (jobData.status === "done") {
        fetchReport();
      }
    } catch (error) {
      console.error("Failed to fetch job status:", error);
    }
  };

  const fetchReport = async () => {
    try {
      const data = await getReport(jobId);
      setReport(data.markdown);
    } catch (error) {
      console.error("Failed to fetch report:", error);
    }
  };

  if (job?.status === "done" && report) {
    return <ReportViewer report={report} job={job} />;
  }

  return <ProgressTracker job={job} events={events} />;
}
