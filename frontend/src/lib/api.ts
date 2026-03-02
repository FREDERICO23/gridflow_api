/**
 * GridFlow API client — all endpoint calls, typed responses, and error handling.
 * In dev: Vite proxies /api → http://localhost:8000.
 * In prod: set VITE_API_BASE_URL to your backend origin (e.g. https://api.example.com)
 *          or leave unset to use relative paths (frontend served by nginx that proxies /api/).
 */

const BASE = `${import.meta.env.VITE_API_BASE_URL ?? ""}/api/v1`

// ── Error class ───────────────────────────────────────────────────────────────

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly detail: string,
  ) {
    super(detail)
    this.name = "ApiError"
  }
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (res.ok) return res.json() as Promise<T>
  let detail = `HTTP ${res.status}`
  try {
    const body = await res.json()
    detail = body?.detail ?? detail
  } catch {
    // ignore parse error
  }
  throw new ApiError(res.status, detail)
}

function authHeaders(apiKey: string): HeadersInit {
  return { "X-API-Key": apiKey }
}

// ── Response types ────────────────────────────────────────────────────────────

export type JobStatusValue =
  | "queued"
  | "parsing"
  | "normalizing"
  | "enriching"
  | "quality_check"
  | "forecasting"
  | "complete"
  | "failed"

export interface UploadResponse {
  job_id: string
  status: JobStatusValue
  message: string
}

export interface JobStatusResp {
  job_id: string
  status: JobStatusValue
  file_name: string
  forecast_year: number
  created_at: string | null
  completed_at: string | null
  error_message: string | null
}

export interface QualityStats {
  mean_kw: number | null
  min_kw: number | null
  max_kw: number | null
  std_kw: number | null
  p5_kw: number | null
  p95_kw: number | null
}

export interface QualityReport {
  job_id: string
  total_records: number
  date_range: { start: string; end: string }
  coverage_percent: number
  missing_hours: number
  statistics: QualityStats
  outliers: { count: number; method: string; threshold_factor: number }
  flat_periods: { count: number; total_hours: number; min_consecutive_hours: number }
  passed: boolean
}

export interface ForecastHour {
  hour_ts: string
  yhat: number
  yhat_lower: number
  yhat_upper: number
}

export interface ForecastResponse {
  job_id: string
  forecast_year: number
  generated_at: string | null
  hours: number
  confidence_interval: number
  data: ForecastHour[]
}

// ── API functions ─────────────────────────────────────────────────────────────

/** Upload a load-profile file and start a processing job. */
export async function uploadFile(
  apiKey: string,
  file: File,
  forecastYear: number,
): Promise<UploadResponse> {
  const form = new FormData()
  form.append("file", file)
  form.append("forecast_year", String(forecastYear))

  const res = await fetch(`${BASE}/upload`, {
    method: "POST",
    headers: authHeaders(apiKey),
    body: form,
  })
  return handleResponse<UploadResponse>(res)
}

/** Poll job processing status. */
export async function getJobStatus(
  apiKey: string,
  jobId: string,
): Promise<JobStatusResp> {
  const res = await fetch(`${BASE}/upload/${jobId}/status`, {
    headers: authHeaders(apiKey),
  })
  return handleResponse<JobStatusResp>(res)
}

/** Fetch the quality report for a completed job. */
export async function getQualityReport(
  apiKey: string,
  jobId: string,
): Promise<QualityReport> {
  const res = await fetch(`${BASE}/jobs/${jobId}/quality-report`, {
    headers: authHeaders(apiKey),
  })
  return handleResponse<QualityReport>(res)
}

/** Fetch the 8,760-hour forecast vector (JSON). */
export async function getForecast(
  apiKey: string,
  jobId: string,
): Promise<ForecastResponse> {
  const res = await fetch(`${BASE}/jobs/${jobId}/forecast`, {
    headers: authHeaders(apiKey),
  })
  return handleResponse<ForecastResponse>(res)
}

/**
 * Download the forecast CSV. Fetches with API key header, then triggers a
 * browser file download via a temporary object URL.
 */
export async function downloadForecastCsv(
  apiKey: string,
  jobId: string,
): Promise<void> {
  const res = await fetch(`${BASE}/jobs/${jobId}/forecast/download`, {
    headers: authHeaders(apiKey),
  })
  if (!res.ok) {
    throw new ApiError(res.status, `Download failed (${res.status})`)
  }
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement("a")
  a.href = url
  a.download = `forecast_${jobId}.csv`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}
