"use client"
import { useEffect } from "react"
import { Button } from "@/components/ui/button"

export default function Error({ error, reset }: { error: Error & { digest?: string }, reset: () => void }) {
  useEffect(() => {
    console.error(error)
  }, [error])
  return (
    <div className="container py-12 space-y-4" role="alert">
      <h1 className="text-xl font-semibold">Something went wrong</h1>
      <p className="text-sm text-stone-600">An unexpected error occurred. You can retry.</p>
      <Button onClick={() => reset()}>Try again</Button>
    </div>
  )
}