import React, { useRef, useState } from "react"
import { Loader2, CheckCircle2, XCircle, Paperclip, X } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { cn } from "@/lib/utils"

type FormState = "idle" | "loading" | "success" | "error"

interface FormValues {
  name: string
  email: string
  description: string
}

const API_ENDPOINT = "https://api.example.com/submit"

export default function SubmitForm() {
  const [values, setValues] = useState<FormValues>({
    name: "",
    email: "",
    description: "",
  })
  const [file, setFile] = useState<File | null>(null)
  const [formState, setFormState] = useState<FormState>("idle")
  const [errorMessage, setErrorMessage] = useState("")
  const [fieldErrors, setFieldErrors] = useState<Partial<FormValues & { file: string }>>({})
  const fileInputRef = useRef<HTMLInputElement>(null)

  function handleChange(
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>
  ) {
    const { name, value } = e.target
    setValues((prev) => ({ ...prev, [name]: value }))
    if (fieldErrors[name as keyof typeof fieldErrors]) {
      setFieldErrors((prev) => ({ ...prev, [name]: undefined }))
    }
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const selected = e.target.files?.[0] ?? null
    setFile(selected)
    if (fieldErrors.file) {
      setFieldErrors((prev) => ({ ...prev, file: undefined }))
    }
  }

  function clearFile() {
    setFile(null)
    if (fileInputRef.current) fileInputRef.current.value = ""
  }

  function validate(): boolean {
    const errors: Partial<FormValues & { file: string }> = {}
    if (!values.name.trim()) errors.name = "Name is required."
    if (!values.email.trim()) {
      errors.email = "Email is required."
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(values.email)) {
      errors.email = "Enter a valid email address."
    }
    if (!values.description.trim()) errors.description = "Description is required."
    if (!file) errors.file = "Please select a file to upload."
    setFieldErrors(errors)
    return Object.keys(errors).length === 0
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!validate()) return

    setFormState("loading")
    setErrorMessage("")

    const formData = new FormData()
    formData.append("name", values.name.trim())
    formData.append("email", values.email.trim())
    formData.append("description", values.description.trim())
    if (file) formData.append("file", file)

    try {
      const response = await fetch(API_ENDPOINT, {
        method: "POST",
        body: formData,
      })

      if (!response.ok) {
        const text = await response.text().catch(() => "")
        throw new Error(text || `Request failed with status ${response.status}.`)
      }

      setFormState("success")
    } catch (err) {
      const msg = err instanceof Error ? err.message : "An unexpected error occurred."
      setErrorMessage(msg)
      setFormState("error")
    }
  }

  function handleReset() {
    setValues({ name: "", email: "", description: "" })
    clearFile()
    setFormState("idle")
    setErrorMessage("")
    setFieldErrors({})
  }

  if (formState === "success") {
    return (
      <div className="flex flex-col items-center gap-4 py-10 text-center">
        <CheckCircle2 className="h-14 w-14 text-green-500" />
        <h2 className="text-xl font-semibold text-foreground">Submission successful!</h2>
        <p className="text-muted-foreground text-sm max-w-xs">
          Your form has been submitted. We'll be in touch shortly.
        </p>
        <Button variant="outline" onClick={handleReset} className="mt-2">
          Submit another
        </Button>
      </div>
    )
  }

  return (
    <form onSubmit={handleSubmit} noValidate className="space-y-5">
      {/* Name */}
      <div className="space-y-1.5">
        <Label htmlFor="name">
          Name <span className="text-destructive">*</span>
        </Label>
        <Input
          id="name"
          name="name"
          type="text"
          placeholder="Jane Doe"
          value={values.name}
          onChange={handleChange}
          disabled={formState === "loading"}
          className={cn(fieldErrors.name && "border-destructive focus-visible:ring-destructive")}
        />
        {fieldErrors.name && (
          <p className="text-xs text-destructive">{fieldErrors.name}</p>
        )}
      </div>

      {/* Email */}
      <div className="space-y-1.5">
        <Label htmlFor="email">
          Email <span className="text-destructive">*</span>
        </Label>
        <Input
          id="email"
          name="email"
          type="email"
          placeholder="jane@example.com"
          value={values.email}
          onChange={handleChange}
          disabled={formState === "loading"}
          className={cn(fieldErrors.email && "border-destructive focus-visible:ring-destructive")}
        />
        {fieldErrors.email && (
          <p className="text-xs text-destructive">{fieldErrors.email}</p>
        )}
      </div>

      {/* Description */}
      <div className="space-y-1.5">
        <Label htmlFor="description">
          Description <span className="text-destructive">*</span>
        </Label>
        <Textarea
          id="description"
          name="description"
          placeholder="Tell us more about your request…"
          rows={4}
          value={values.description}
          onChange={handleChange}
          disabled={formState === "loading"}
          className={cn(fieldErrors.description && "border-destructive focus-visible:ring-destructive")}
        />
        {fieldErrors.description && (
          <p className="text-xs text-destructive">{fieldErrors.description}</p>
        )}
      </div>

      {/* File Upload */}
      <div className="space-y-1.5">
        <Label>
          File <span className="text-destructive">*</span>
        </Label>
        <div
          className={cn(
            "flex items-center gap-3 rounded-md border border-dashed border-input px-3 py-3 transition-colors",
            fieldErrors.file && "border-destructive"
          )}
        >
          <input
            ref={fileInputRef}
            id="file"
            type="file"
            className="sr-only"
            onChange={handleFileChange}
            disabled={formState === "loading"}
          />
          {file ? (
            <div className="flex flex-1 items-center gap-2 min-w-0">
              <Paperclip className="h-4 w-4 shrink-0 text-muted-foreground" />
              <span className="truncate text-sm text-foreground">{file.name}</span>
              <span className="text-xs text-muted-foreground shrink-0">
                ({(file.size / 1024).toFixed(1)} KB)
              </span>
              <button
                type="button"
                onClick={clearFile}
                disabled={formState === "loading"}
                className="ml-auto shrink-0 rounded-sm text-muted-foreground hover:text-foreground focus-visible:outline-none"
                aria-label="Remove file"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          ) : (
            <label
              htmlFor="file"
              className={cn(
                "flex flex-1 cursor-pointer items-center gap-2 text-sm text-muted-foreground",
                formState === "loading" && "cursor-not-allowed opacity-50"
              )}
            >
              <Paperclip className="h-4 w-4 shrink-0" />
              <span>Choose a file&hellip;</span>
              <span className="ml-auto text-xs">Any file type accepted</span>
            </label>
          )}
        </div>
        {fieldErrors.file && (
          <p className="text-xs text-destructive">{fieldErrors.file}</p>
        )}
      </div>

      {/* Error Banner */}
      {formState === "error" && (
        <div className="flex items-start gap-2 rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2.5 text-sm text-destructive">
          <XCircle className="mt-0.5 h-4 w-4 shrink-0" />
          <span>{errorMessage}</span>
        </div>
      )}

      {/* Submit */}
      <Button
        type="submit"
        className="w-full"
        size="lg"
        disabled={formState === "loading"}
      >
        {formState === "loading" ? (
          <>
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            Submitting…
          </>
        ) : (
          "Submit"
        )}
      </Button>
    </form>
  )
}
