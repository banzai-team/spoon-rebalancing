"use client"
import { BACKEND_URL } from "@/lib/backend"
import { Button } from "@/components/ui/button"
import { toast } from "sonner"

export default function StrategyActions({ strategyId }: { strategyId: string }) {
  const onGetRecommendation = async () => {
    const res = await fetch(`${BACKEND_URL}/api/recommendations`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ strategy_id: strategyId }),
    })
    if (!res.ok) return toast.error("Failed to get recommendation")
    toast.success("Recommendation requested")
  }
  return <Button onClick={onGetRecommendation}>Get Recommendation</Button>
}