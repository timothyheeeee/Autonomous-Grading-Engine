"use client";

import { useEffect, useMemo, useState } from "react";
import AuditTrail from "@/components/AuditTrail";
import DropZone from "@/components/DropZone";
import ContributionBarChart from "@/components/charts/ContributionBarChart";
import CriterionChart from "@/components/charts/CriterionChart";
import { api, getThreadId, setThreadId, type PipelineState } from "@/lib/api";

const NODE_COPY: Record<string, string> = {
  vision_extractor: "Reading the rubric screenshot…",
  semantic_parser: "Extracting team members from the CSV…",
  calculate: "Converting scores into percentages…",
  save_to_database: "Waiting for approval…",
  halt: "Stopped.",
};

const ERROR_COPY: Record<string, string> = {
  invalid_rubric:
    "The uploaded image does not appear to contain a grading rubric. Please upload a screenshot showing assessment criteria.",
  invalid_csv:
    "The uploaded CSV does not appear to contain student peer-review information. Please check the file and try again.",
  vision_unavailable: "Rubric verification is unavailable because the vision model is not configured.",
};

function pipelineErrorMessage(error: PipelineState["error"]): string {
  const message = error?.message?.trim() ?? "";
  if (message && message !== "unreadable_data" && message !== error?.reason && !message.includes("Traceback")) {
    return message;
  }
  if (error?.reason && ERROR_COPY[error.reason]) return ERROR_COPY[error.reason];
  return "The upload could not be validated. Check the rubric screenshot and peer-review CSV.";
}

export default function HomeClient() {
  const [mounted, setMounted] = useState(false);
  const [csv, setCsv] = useState<File | null>(null);
  const [image, setImage] = useState<File | null>(null);
  const [state, setState] = useState<PipelineState | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    const existing = getThreadId();
    if (!existing) return;
    api<PipelineState>(`/api/pipeline/${existing}`)
      .then((payload) => {
        if (payload.status !== "empty") setState(payload);
        else setThreadId(null);
      })
      .catch(() => setThreadId(null));
  }, []);

  useEffect(() => {
    if (!state || state.status !== "running") return;
    const timer = window.setInterval(async () => {
      const next = await api<PipelineState>(`/api/pipeline/${state.thread_id}`);
      setState(next);
      if (next.status !== "running") window.clearInterval(timer);
    }, 400);
    return () => window.clearInterval(timer);
  }, [state?.thread_id, state?.status]);

  const contribution = useMemo(
    () =>
      (state?.percentages?.students ?? []).map((row) => ({
        student: row.student_name,
        percentage: row.contribution_percentage,
      })),
    [state],
  );

  async function submit() {
    if (!csv || !image) return;
    setBusy(true);
    setError("");
    try {
      const body = new FormData();
      body.append("csv_file", csv);
      body.append("rubric_image", image);
      const started = await api<PipelineState>("/api/pipeline/run", { method: "POST", body });
      setThreadId(started.thread_id);
      setState(started);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setBusy(false);
    }
  }

  async function approve() {
    if (!state) return;
    setBusy(true);
    try {
      const next = await api<PipelineState>(`/api/pipeline/${state.thread_id}/approve`, {
        method: "POST",
        body: JSON.stringify({ approved: true }),
      });
      setState(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Approve failed");
    } finally {
      setBusy(false);
    }
  }

  function reset() {
    setCsv(null);
    setImage(null);
    setState(null);
    setError("");
    setThreadId(null);
  }

  const showUpload = !state || state.status === "empty" || state.status === "error";
  const showDashboard = Boolean(state?.percentages);

  if (!mounted) {
    return (
      <main className="mx-auto min-h-screen max-w-5xl px-6 py-16">
        <p className="text-xs uppercase tracking-[0.22em] text-neutral-400">Capability</p>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight">Group contribution, as percentages.</h1>
        <p className="mt-2 max-w-xl text-sm leading-6 text-neutral-500">
          Drop a peer-review CSV and a rubric screenshot. The model reads. Pandas calculates. Nothing is saved until you approve.
        </p>
      </main>
    );
  }

  return (
    <main className="mx-auto min-h-screen max-w-5xl px-6 py-16">
      <header className="mb-12 flex items-end justify-between gap-6">
        <div>
          <p className="text-xs uppercase tracking-[0.22em] text-neutral-400">Capability</p>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight">Group contribution, as percentages.</h1>
          <p className="mt-2 max-w-xl text-sm leading-6 text-neutral-500">
            Drop a peer-review CSV and a rubric screenshot. The model reads. Pandas calculates. Nothing is saved until you approve.
          </p>
        </div>
        {state ? (
          <button type="button" onClick={reset} className="text-sm text-neutral-500 underline-offset-4 hover:underline">
            Start over
          </button>
        ) : null}
      </header>

      {showUpload ? (
        <section className="space-y-6">
          <div className="grid gap-4 md:grid-cols-2">
            <DropZone label="Peer reviews" hint="Drop a .csv" accept=".csv,text/csv" file={csv} onFile={setCsv} />
            <DropZone
              label="Rubric screenshot"
              hint="Drop a png or jpg"
              accept="image/png,image/jpeg,image/webp"
              file={image}
              onFile={setImage}
            />
          </div>
          <button
            type="button"
            disabled={!csv || !image || busy}
            onClick={submit}
            className="rounded-full bg-neutral-950 px-6 py-2.5 text-sm text-white disabled:opacity-30"
          >
            Submit
          </button>
          {state?.status === "error" ? (
            <p className="text-sm text-red-600">{pipelineErrorMessage(state.error)}</p>
          ) : null}
          {error ? <p className="text-sm text-red-600">{error}</p> : null}
        </section>
      ) : null}

      {state?.status === "running" ? (
        <div className="rounded-2xl border border-neutral-200 bg-white px-6 py-10 text-center">
          <div className="mx-auto mb-4 h-8 w-8 animate-spin rounded-full border-2 border-neutral-200 border-t-neutral-950" />
          <p className="text-sm">{NODE_COPY[state.current_node] || "Working…"}</p>
          <p className="mt-1 text-xs text-neutral-400">You can refresh. Progress is checkpointed.</p>
        </div>
      ) : null}

      {showDashboard && state ? (
        <div className="space-y-10">
          {state.status === "pending_review" ? (
            <div className="flex items-center justify-between rounded-2xl border border-neutral-200 bg-white px-5 py-4">
              <div>
                <p className="text-sm font-medium">Pending review</p>
                <p className="text-sm text-neutral-500">Percentages are calculated. They are not saved yet.</p>
              </div>
              <button
                type="button"
                disabled={busy}
                onClick={approve}
                className="rounded-full bg-neutral-950 px-5 py-2 text-sm text-white"
              >
                Approve calculation
              </button>
            </div>
          ) : null}
          {state.status === "published" ? (
            <p className="text-sm text-neutral-500">Saved. Charts below are the approved percentages.</p>
          ) : null}
          <section className="rounded-2xl border border-neutral-200 bg-white p-6">
            <h2 className="text-sm font-medium text-neutral-500">Contribution share</h2>
            <ContributionBarChart data={contribution} />
          </section>
          <section className="rounded-2xl border border-neutral-200 bg-white p-6">
            <h2 className="text-sm font-medium text-neutral-500">Rubric criteria</h2>
            <CriterionChart students={state.percentages?.students ?? []} />
          </section>
          <AuditTrail steps={state.audit_trail} />
          {error ? <p className="text-sm text-red-600">{error}</p> : null}
        </div>
      ) : null}
    </main>
  );
}
