import { useEffect, useRef, useState } from "react"
import {
  CheckCircle2,
  ChevronRight,
  Circle,
  Loader2,
  XCircle,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { getJobStatus, JobStatusResp, JobStatusValue, ApiError } from "@/lib/api"

interface Props {
  apiKey: string
  jobId: string
  fileName: string
  forecastYear: number
  onComplete: () => void
  onBack: () => void
}

// Pipeline stages in order
const STAGES: JobStatusValue[] = [
  "queued",
  "parsing",
  "normalizing",
  "enriching",
  "quality_check",
  "forecasting",
  "complete",
]

const STAGE_LABELS: Record<JobStatusValue, string> = {
  queued: "Queued",
  parsing: "Parsing",
  normalizing: "Normalizing",
  enriching: "Enriching",
  quality_check: "Quality Check",
  forecasting: "Forecasting",
  complete: "Complete",
  failed: "Failed",
}

const STAGE_DESCRIPTIONS: Partial<Record<JobStatusValue, string>> = {
  queued: "Waiting for a worker to pick up the job…",
  parsing: "Reading file, detecting columns, converting units…",
  normalizing: "Resampling to hourly intervals (Europe/Berlin)…",
  enriching: "Fetching weather data and public holidays…",
  quality_check: "Analysing coverage, outliers, and flat periods…",
  forecasting: "Running Prophet model — this may take a minute…",
  complete: "All done!",
}

const POLL_INTERVAL_MS = 3000

function stageIndex(s: JobStatusValue): number {
  return STAGES.indexOf(s)
}

export default function JobStatusPage({
  apiKey,
  jobId,
  fileName,
  forecastYear,
  onComplete,
  onBack,
}: Props) {
  const [status, setStatus] = useState<JobStatusResp | null>(null)
  const [fetchError, setFetchError] = useState<string | null>(null)
  const cancelledRef = useRef(false)

  useEffect(() => {
    cancelledRef.current = false

    async function poll() {
      if (cancelledRef.current) return
      try {
        const s = await getJobStatus(apiKey, jobId)
        if (cancelledRef.current) return
        setStatus(s)
        setFetchError(null)
        if (s.status !== "complete" && s.status !== "failed") {
          setTimeout(poll, POLL_INTERVAL_MS)
        }
      } catch (err) {
        if (cancelledRef.current) return
        const msg =
          err instanceof ApiError
            ? err.detail
            : err instanceof Error
            ? err.message
            : "Could not reach the API."
        setFetchError(msg)
        // Retry polling even on transient errors
        setTimeout(poll, POLL_INTERVAL_MS)
      }
    }

    poll()

    return () => {
      cancelledRef.current = true
    }
  }, [apiKey, jobId])

  const currentStage = status?.status ?? "queued"
  const isFailed = currentStage === "failed"
  const isComplete = currentStage === "complete"
  const currentIdx = isFailed ? -1 : stageIndex(currentStage)

  return (
    <div className="min-h-screen bg-slate-50 flex items-start justify-center px-4 py-12">
      <div className="w-full max-w-2xl">
        {/* Header */}
        <div className="mb-8">
          <button
            onClick={onBack}
            className="text-sm text-muted-foreground hover:text-foreground transition-colors mb-4 flex items-center gap-1"
          >
            ← New Upload
          </button>
          <h2 className="text-xl font-semibold text-foreground">Processing Job</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            <span className="font-medium text-foreground">{fileName}</span>
            {" · "}Forecast year: <span className="font-medium text-foreground">{forecastYear}</span>
          </p>
        </div>

        {/* Job ID card */}
        <div className="rounded-xl border border-border bg-white px-6 py-5 shadow-sm mb-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs text-muted-foreground uppercase tracking-wide font-medium mb-0.5">
                Job ID
              </p>
              <p className="text-sm font-mono text-foreground">{jobId}</p>
            </div>
            {!isComplete && !isFailed && (
              <div className="flex items-center gap-2 text-sm text-primary">
                <Loader2 className="h-4 w-4 animate-spin" />
                <span>Polling every 3s…</span>
              </div>
            )}
            {isComplete && (
              <CheckCircle2 className="h-6 w-6 text-green-500" />
            )}
            {isFailed && (
              <XCircle className="h-6 w-6 text-destructive" />
            )}
          </div>
        </div>

        {/* Pipeline stepper */}
        <div className="rounded-xl border border-border bg-white px-6 py-6 shadow-sm mb-4">
          <h3 className="text-sm font-medium text-foreground mb-5">Pipeline Progress</h3>

          <div className="flex items-start gap-0">
            {STAGES.map((stage, idx) => {
              const isDone = !isFailed && currentIdx > idx
              const isCurrent = !isFailed && currentIdx === idx
              const isPending = isFailed ? true : currentIdx < idx

              return (
                <div key={stage} className="flex items-start flex-1 min-w-0">
                  {/* Step */}
                  <div className="flex flex-col items-center min-w-0 flex-1">
                    {/* Circle */}
                    <div
                      className={cn(
                        "h-8 w-8 rounded-full flex items-center justify-center border-2 shrink-0 transition-all",
                        isDone && "border-green-500 bg-green-500",
                        isCurrent && "border-primary bg-primary",
                        isPending && "border-slate-300 bg-white",
                        isFailed && "border-destructive bg-destructive",
                      )}
                    >
                      {isDone && <CheckCircle2 className="h-4 w-4 text-white" />}
                      {isCurrent && <Loader2 className="h-4 w-4 text-white animate-spin" />}
                      {isPending && !isFailed && (
                        <Circle className="h-3 w-3 text-slate-300" />
                      )}
                      {isFailed && idx === STAGES.length - 1 && (
                        <XCircle className="h-4 w-4 text-white" />
                      )}
                    </div>

                    {/* Label */}
                    <p
                      className={cn(
                        "mt-2 text-xs text-center leading-tight px-0.5",
                        isDone && "text-green-600 font-medium",
                        isCurrent && "text-primary font-medium",
                        isPending && "text-muted-foreground",
                      )}
                    >
                      {STAGE_LABELS[stage]}
                    </p>
                  </div>

                  {/* Connector line */}
                  {idx < STAGES.length - 1 && (
                    <div className="flex items-center mt-4 shrink-0">
                      <ChevronRight
                        className={cn(
                          "h-4 w-4",
                          isDone ? "text-green-400" : "text-slate-200",
                        )}
                      />
                    </div>
                  )}
                </div>
              )
            })}
          </div>

          {/* Current stage description */}
          {!isFailed && STAGE_DESCRIPTIONS[currentStage] && (
            <p className="mt-5 text-sm text-muted-foreground border-t border-border pt-4">
              {STAGE_DESCRIPTIONS[currentStage]}
            </p>
          )}
        </div>

        {/* Error detail when failed */}
        {isFailed && status?.error_message && (
          <div className="rounded-xl border border-destructive/40 bg-destructive/10 px-5 py-4 mb-4">
            <div className="flex items-start gap-2">
              <XCircle className="h-5 w-5 text-destructive shrink-0 mt-0.5" />
              <div>
                <p className="text-sm font-medium text-destructive mb-1">Job Failed</p>
                <p className="text-sm text-destructive/90 font-mono break-all">
                  {status.error_message}
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Transient fetch error */}
        {fetchError && !isFailed && !isComplete && (
          <div className="rounded-lg border border-amber-300 bg-amber-50 px-4 py-2.5 text-sm text-amber-800 mb-4">
            ⚠ {fetchError} — retrying…
          </div>
        )}

        {/* Timestamps */}
        {status && (
          <div className="flex gap-6 text-xs text-muted-foreground px-1 mb-6">
            {status.created_at && (
              <span>
                Started:{" "}
                <span className="text-foreground font-medium">
                  {new Date(status.created_at).toLocaleString()}
                </span>
              </span>
            )}
            {status.completed_at && (
              <span>
                Finished:{" "}
                <span className="text-foreground font-medium">
                  {new Date(status.completed_at).toLocaleString()}
                </span>
              </span>
            )}
          </div>
        )}

        {/* Actions */}
        <div className="flex gap-3">
          {isComplete && (
            <Button onClick={onComplete} className="flex-1" size="lg">
              View Results
            </Button>
          )}
          <Button
            variant={isComplete ? "outline" : "default"}
            onClick={onBack}
            size="lg"
            className={isComplete ? "" : "flex-1"}
          >
            New Upload
          </Button>
        </div>
      </div>
    </div>
  )
}
