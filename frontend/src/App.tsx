import { useState } from "react"
import { KeyRound } from "lucide-react"
import { Input } from "@/components/ui/input"
import UploadPage from "@/components/UploadPage"
import JobStatusPage from "@/components/JobStatusPage"
import ResultsPage from "@/components/ResultsPage"

// ── View discriminated union ───────────────────────────────────────────────────

type View =
  | { name: "upload" }
  | { name: "status"; jobId: string; fileName: string; forecastYear: number }
  | { name: "results"; jobId: string; fileName: string; forecastYear: number }

// ── App ───────────────────────────────────────────────────────────────────────

const STORAGE_KEY = "gridflow_api_key"

function loadApiKey(): string {
  try {
    return localStorage.getItem(STORAGE_KEY) ?? ""
  } catch {
    return ""
  }
}

function saveApiKey(key: string) {
  try {
    localStorage.setItem(STORAGE_KEY, key)
  } catch {
    // ignore
  }
}

export default function App() {
  const [apiKey, setApiKey] = useState<string>(loadApiKey)
  const [view, setView] = useState<View>({ name: "upload" })

  function handleApiKeyChange(value: string) {
    setApiKey(value)
    saveApiKey(value)
  }

  function handleJobCreated(jobId: string, fileName: string, forecastYear: number) {
    setView({ name: "status", jobId, fileName, forecastYear })
  }

  function handleStatusComplete(jobId: string, fileName: string, forecastYear: number) {
    setView({ name: "results", jobId, fileName, forecastYear })
  }

  function goToUpload() {
    setView({ name: "upload" })
  }

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Persistent header */}
      <header className="sticky top-0 z-10 border-b border-border bg-white/90 backdrop-blur-sm">
        <div className="mx-auto flex max-w-2xl items-center gap-4 px-4 py-3">
          {/* Brand */}
          <div className="flex items-center gap-2 shrink-0">
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth={2}
              className="h-5 w-5 text-primary"
            >
              <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
            </svg>
            <span className="font-semibold text-foreground text-sm">GridFlow</span>
          </div>

          {/* Spacer */}
          <div className="flex-1" />

          {/* API key input */}
          <div className="flex items-center gap-2 min-w-0">
            <KeyRound className="h-4 w-4 text-muted-foreground shrink-0" />
            <Input
              type="password"
              placeholder="API key"
              value={apiKey}
              onChange={(e) => handleApiKeyChange(e.target.value)}
              className="h-8 w-48 text-xs font-mono"
              aria-label="API key"
            />
          </div>
        </div>
      </header>

      {/* Page views */}
      {view.name === "upload" && (
        <UploadPage
          apiKey={apiKey}
          onJobCreated={handleJobCreated}
        />
      )}

      {view.name === "status" && (
        <JobStatusPage
          apiKey={apiKey}
          jobId={view.jobId}
          fileName={view.fileName}
          forecastYear={view.forecastYear}
          onComplete={() =>
            handleStatusComplete(view.jobId, view.fileName, view.forecastYear)
          }
          onBack={goToUpload}
        />
      )}

      {view.name === "results" && (
        <ResultsPage
          apiKey={apiKey}
          jobId={view.jobId}
          fileName={view.fileName}
          forecastYear={view.forecastYear}
          onBack={() =>
            setView({ name: "status", jobId: view.jobId, fileName: view.fileName, forecastYear: view.forecastYear })
          }
          onNewUpload={goToUpload}
        />
      )}
    </div>
  )
}
