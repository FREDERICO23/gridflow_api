import { useEffect, useState } from "react"
import {
  AlertTriangle,
  CheckCircle2,
  Download,
  Loader2,
  XCircle,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import {
  getQualityReport,
  getForecast,
  downloadForecastCsv,
  QualityReport,
  ForecastResponse,
  ApiError,
} from "@/lib/api"

interface Props {
  apiKey: string
  jobId: string
  fileName: string
  forecastYear: number
  onBack: () => void
  onNewUpload: () => void
}

function fmt(n: number | null, digits = 1): string {
  if (n === null || n === undefined) return "—"
  return n.toLocaleString("en-US", { maximumFractionDigits: digits })
}

function StatCell({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-border bg-slate-50 px-4 py-3">
      <p className="text-xs text-muted-foreground mb-0.5">{label}</p>
      <p className="text-sm font-semibold text-foreground">{value} kW</p>
    </div>
  )
}

export default function ResultsPage({
  apiKey,
  jobId,
  fileName,
  forecastYear,
  onBack,
  onNewUpload,
}: Props) {
  const [quality, setQuality] = useState<QualityReport | null>(null)
  const [forecast, setForecast] = useState<ForecastResponse | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [downloading, setDownloading] = useState(false)
  const [downloadError, setDownloadError] = useState<string | null>(null)

  useEffect(() => {
    async function load() {
      try {
        const [q, f] = await Promise.all([
          getQualityReport(apiKey, jobId),
          getForecast(apiKey, jobId),
        ])
        setQuality(q)
        setForecast(f)
      } catch (err) {
        const msg =
          err instanceof ApiError
            ? err.detail
            : err instanceof Error
            ? err.message
            : "Failed to load results."
        setLoadError(msg)
      }
    }
    load()
  }, [apiKey, jobId])

  async function handleDownload() {
    setDownloading(true)
    setDownloadError(null)
    try {
      await downloadForecastCsv(apiKey, jobId)
    } catch (err) {
      const msg =
        err instanceof ApiError
          ? err.detail
          : err instanceof Error
          ? err.message
          : "Download failed."
      setDownloadError(msg)
    } finally {
      setDownloading(false)
    }
  }

  return (
    <div className="min-h-screen bg-slate-50 flex items-start justify-center px-4 py-12">
      <div className="w-full max-w-2xl">
        {/* Header */}
        <div className="mb-8">
          <button
            onClick={onBack}
            className="text-sm text-muted-foreground hover:text-foreground transition-colors mb-4 flex items-center gap-1"
          >
            ← Back to Status
          </button>
          <h2 className="text-xl font-semibold text-foreground">Forecast Results</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            <span className="font-medium text-foreground">{fileName}</span>
            {" · "}Forecast year:{" "}
            <span className="font-medium text-foreground">{forecastYear}</span>
          </p>
        </div>

        {/* Loading state */}
        {!quality && !forecast && !loadError && (
          <div className="rounded-xl border border-border bg-white px-6 py-12 shadow-sm flex flex-col items-center gap-3">
            <Loader2 className="h-6 w-6 animate-spin text-primary" />
            <p className="text-sm text-muted-foreground">Loading results…</p>
          </div>
        )}

        {/* Load error */}
        {loadError && (
          <div className="rounded-xl border border-destructive/40 bg-destructive/10 px-5 py-4 mb-4 flex items-start gap-2">
            <XCircle className="h-5 w-5 text-destructive shrink-0 mt-0.5" />
            <div>
              <p className="text-sm font-medium text-destructive mb-1">Could not load results</p>
              <p className="text-sm text-destructive/90">{loadError}</p>
            </div>
          </div>
        )}

        {/* Quality Report */}
        {quality && (
          <div className="rounded-xl border border-border bg-white px-6 py-6 shadow-sm mb-4">
            <div className="flex items-center justify-between mb-5">
              <h3 className="text-sm font-medium text-foreground">Quality Report</h3>
              <span
                className={cn(
                  "inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium",
                  quality.passed
                    ? "bg-green-50 text-green-700 border border-green-200"
                    : "bg-red-50 text-red-700 border border-red-200",
                )}
              >
                {quality.passed ? (
                  <CheckCircle2 className="h-3.5 w-3.5" />
                ) : (
                  <AlertTriangle className="h-3.5 w-3.5" />
                )}
                {quality.passed ? "Passed" : "Failed"}
              </span>
            </div>

            {/* Coverage */}
            <div className="mb-5">
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-xs text-muted-foreground">Coverage</span>
                <span className="text-xs font-medium text-foreground">
                  {fmt(quality.coverage_percent, 1)}% ({quality.missing_hours} missing hours)
                </span>
              </div>
              <div className="h-2 rounded-full bg-slate-100 overflow-hidden">
                <div
                  className={cn(
                    "h-full rounded-full transition-all",
                    quality.coverage_percent >= 95
                      ? "bg-green-500"
                      : quality.coverage_percent >= 80
                      ? "bg-amber-400"
                      : "bg-red-500",
                  )}
                  style={{ width: `${Math.min(100, quality.coverage_percent)}%` }}
                />
              </div>
            </div>

            {/* Stats grid */}
            <div className="grid grid-cols-3 gap-2 mb-5">
              <StatCell label="Mean" value={fmt(quality.statistics.mean_kw)} />
              <StatCell label="Min" value={fmt(quality.statistics.min_kw)} />
              <StatCell label="Max" value={fmt(quality.statistics.max_kw)} />
              <StatCell label="Std Dev" value={fmt(quality.statistics.std_kw)} />
              <StatCell label="P5" value={fmt(quality.statistics.p5_kw)} />
              <StatCell label="P95" value={fmt(quality.statistics.p95_kw)} />
            </div>

            {/* Outliers + flat periods */}
            <div className="grid grid-cols-2 gap-3 text-xs border-t border-border pt-4">
              <div>
                <p className="text-muted-foreground mb-0.5">Outliers</p>
                <p className="font-medium text-foreground">
                  {quality.outliers.count} detected ({quality.outliers.method}, ×{quality.outliers.threshold_factor})
                </p>
              </div>
              <div>
                <p className="text-muted-foreground mb-0.5">Flat Periods</p>
                <p className="font-medium text-foreground">
                  {quality.flat_periods.count} periods · {quality.flat_periods.total_hours}h total
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Forecast preview */}
        {forecast && (
          <div className="rounded-xl border border-border bg-white px-6 py-6 shadow-sm mb-4">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-sm font-medium text-foreground">Forecast Preview</h3>
                <p className="text-xs text-muted-foreground mt-0.5">
                  First 24 hours of {forecast.hours.toLocaleString()}-hour vector
                  · {forecast.confidence_interval * 100}% CI
                </p>
              </div>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-border">
                    <th className="text-left py-2 pr-4 font-medium text-muted-foreground">Hour</th>
                    <th className="text-right py-2 px-2 font-medium text-muted-foreground">Lower (kW)</th>
                    <th className="text-right py-2 px-2 font-medium text-foreground">Forecast (kW)</th>
                    <th className="text-right py-2 pl-2 font-medium text-muted-foreground">Upper (kW)</th>
                  </tr>
                </thead>
                <tbody>
                  {forecast.data.slice(0, 24).map((row) => (
                    <tr key={row.hour_ts} className="border-b border-border/50 hover:bg-slate-50">
                      <td className="py-1.5 pr-4 font-mono text-muted-foreground">
                        {new Date(row.hour_ts).toLocaleString("en-GB", {
                          month: "short",
                          day: "numeric",
                          hour: "2-digit",
                          minute: "2-digit",
                        })}
                      </td>
                      <td className="py-1.5 px-2 text-right text-muted-foreground">
                        {fmt(row.yhat_lower)}
                      </td>
                      <td className="py-1.5 px-2 text-right font-medium text-foreground">
                        {fmt(row.yhat)}
                      </td>
                      <td className="py-1.5 pl-2 text-right text-muted-foreground">
                        {fmt(row.yhat_upper)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {forecast.data.length > 24 && (
              <p className="mt-3 text-xs text-muted-foreground text-center">
                … and {(forecast.data.length - 24).toLocaleString()} more hours
              </p>
            )}
          </div>
        )}

        {/* Download error */}
        {downloadError && (
          <div className="rounded-lg border border-destructive/40 bg-destructive/10 px-4 py-2.5 text-sm text-destructive mb-4 flex items-center gap-2">
            <XCircle className="h-4 w-4 shrink-0" />
            {downloadError}
          </div>
        )}

        {/* Actions */}
        {(quality || forecast) && (
          <div className="flex gap-3">
            <Button
              onClick={handleDownload}
              disabled={downloading}
              size="lg"
              className="flex-1"
            >
              {downloading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Downloading…
                </>
              ) : (
                <>
                  <Download className="mr-2 h-4 w-4" />
                  Download CSV
                </>
              )}
            </Button>
            <Button variant="outline" onClick={onNewUpload} size="lg">
              New Upload
            </Button>
          </div>
        )}
      </div>
    </div>
  )
}
