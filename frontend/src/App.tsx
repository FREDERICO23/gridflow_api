import SubmitForm from "@/components/SubmitForm"

function App() {
  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center px-4 py-12">
      <div className="w-full max-w-md">
        {/* Header */}
        <div className="mb-8 text-center">
          <h1 className="text-2xl font-bold tracking-tight text-foreground">
            Submit a Request
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Fill in the details below and attach any relevant file.
          </p>
        </div>

        {/* Card */}
        <div className="rounded-xl border border-border bg-white px-6 py-8 shadow-sm">
          <SubmitForm />
        </div>

        <p className="mt-6 text-center text-xs text-muted-foreground">
          Fields marked with <span className="text-destructive font-medium">*</span> are required.
        </p>
      </div>
    </div>
  )
}

export default App
