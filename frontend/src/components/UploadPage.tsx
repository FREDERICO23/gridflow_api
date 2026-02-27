import React, { useRef, useState } from "react"
import { Loader2, Paperclip, X, XCircle } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { cn } from "@/lib/utils"
import { uploadFile, ApiError } from "@/lib/api"

interface Props {
  apiKey: string
  onJobCreated: (jobId: string, fileName: string, forecastYear: number) => void
}

const ACCEPTED = ".csv,.xlsx,.xls"
const DEFAULT_YEAR = new Date().getFullYear() + 1

export default function UploadPage({ apiKey, onJobCreated }: Props) {
  const [file, setFile] = useState<File | null>(null)
  const [forecastYear, setForecastYear] = useState<number>(DEFAULT_YEAR)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [fieldErrors, setFieldErrors] = useState<{ file?: string; year?: string; key?: string }>({})
  const fileInputRef = useRef<HTMLInputElement>(null)

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0] ?? null
    setFile(f)
    if (f) setFieldErrors((prev) => ({ ...prev, file: undefined }))
  }

  function clearFile() {
    setFile(null)
    if (fileInputRef.current) fileInputRef.current.value = ""
  }

  function validate(): boolean {
    const errs: typeof fieldErrors = {}
    if (!apiKey.trim()) errs.key = "API key is required — enter it in the header above."
    if (!file) errs.file = "Please select a CSV or Excel file."
    if (!forecastYear || forecastYear < 2000 || forecastYear > 2100)
      errs.year = "Enter a valid forecast year (2000–2100)."
    setFieldErrors(errs)
    return Object.keys(errs).length === 0
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!validate()) return
    setLoading(true)
    setError(null)
    try {
      const resp = await uploadFile(apiKey, file!, forecastYear)
      onJobCreated(resp.job_id, file!.name, forecastYear)
    } catch (err) {
      const msg =
        err instanceof ApiError
          ? err.detail
          : err instanceof Error
          ? err.message
          : "Unexpected error. Is the API running?"
      setError(msg)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-slate-50 flex items-start justify-center px-4 py-12">
      <div className="w-full max-w-lg">
        <div className="mb-8">
          <h2 className="text-xl font-semibold text-foreground">Upload Load Profile</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Upload a CSV or Excel file containing hourly (or sub-hourly) energy consumption
            data. The pipeline will parse, normalize, and forecast the full year.
          </p>
        </div>

        <div className="rounded-xl border border-border bg-white px-6 py-7 shadow-sm">
          <form onSubmit={handleSubmit} noValidate className="space-y-6">

            {/* File upload */}
            <div className="space-y-1.5">
              <Label>
                Load profile file <span className="text-destructive">*</span>
              </Label>
              <div
                className={cn(
                  "flex items-center gap-3 rounded-md border border-dashed border-input px-3 py-3 transition-colors",
                  fieldErrors.file && "border-destructive",
                )}
              >
                <input
                  ref={fileInputRef}
                  id="file-upload"
                  type="file"
                  accept={ACCEPTED}
                  className="sr-only"
                  onChange={handleFileChange}
                  disabled={loading}
                />
                {file ? (
                  <div className="flex flex-1 items-center gap-2 min-w-0">
                    <Paperclip className="h-4 w-4 shrink-0 text-muted-foreground" />
                    <span className="truncate text-sm font-medium text-foreground">
                      {file.name}
                    </span>
                    <span className="text-xs text-muted-foreground shrink-0">
                      ({(file.size / 1024).toFixed(1)} KB)
                    </span>
                    <button
                      type="button"
                      onClick={clearFile}
                      disabled={loading}
                      className="ml-auto shrink-0 rounded-sm text-muted-foreground hover:text-foreground"
                      aria-label="Remove file"
                    >
                      <X className="h-4 w-4" />
                    </button>
                  </div>
                ) : (
                  <label
                    htmlFor="file-upload"
                    className={cn(
                      "flex flex-1 cursor-pointer items-center gap-2 text-sm text-muted-foreground",
                      loading && "cursor-not-allowed opacity-50",
                    )}
                  >
                    <Paperclip className="h-4 w-4 shrink-0" />
                    <span>Choose a file…</span>
                    <span className="ml-auto text-xs">CSV, XLSX, XLS</span>
                  </label>
                )}
              </div>
              {fieldErrors.file && (
                <p className="text-xs text-destructive">{fieldErrors.file}</p>
              )}
            </div>

            {/* Forecast year */}
            <div className="space-y-1.5">
              <Label htmlFor="forecast-year">
                Forecast year <span className="text-destructive">*</span>
              </Label>
              <Input
                id="forecast-year"
                type="number"
                min={2000}
                max={2100}
                value={forecastYear}
                onChange={(e) => {
                  setForecastYear(Number(e.target.value))
                  setFieldErrors((p) => ({ ...p, year: undefined }))
                }}
                disabled={loading}
                className={cn(
                  "w-36",
                  fieldErrors.year && "border-destructive focus-visible:ring-destructive",
                )}
              />
              <p className="text-xs text-muted-foreground">
                The calendar year for which the 8,760-hour forecast will be generated.
              </p>
              {fieldErrors.year && (
                <p className="text-xs text-destructive">{fieldErrors.year}</p>
              )}
            </div>

            {/* API key hint */}
            {fieldErrors.key && (
              <p className="text-xs text-destructive">{fieldErrors.key}</p>
            )}

            {/* Error banner */}
            {error && (
              <div className="flex items-start gap-2 rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2.5 text-sm text-destructive">
                <XCircle className="mt-0.5 h-4 w-4 shrink-0" />
                <span>{error}</span>
              </div>
            )}

            <Button
              type="submit"
              size="lg"
              className="w-full"
              disabled={loading}
            >
              {loading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Uploading…
                </>
              ) : (
                "Start Forecast Pipeline"
              )}
            </Button>
          </form>
        </div>

        <p className="mt-4 text-center text-xs text-muted-foreground">
          Supported formats: <strong>CSV</strong> (comma or semicolon separated, German locale ok),{" "}
          <strong>XLSX / XLS</strong>. Timestamps and kW/kWh columns are auto-detected.
        </p>
      </div>
    </div>
  )
}
