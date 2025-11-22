"use client"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { backend, BACKEND_URL } from "@/lib/backend"
import { useState } from "react"

type Status = { success: boolean; status: { mode: string; min_profit_threshold_usd: number } }

export default function SettingsPage() {
  const qc = useQueryClient()
  const { data } = useQuery({ queryKey: ["agent-status"], queryFn: () => backend<Status>("/api/agent/status") })
  const [mode, setMode] = useState<string>(data?.status.mode ?? "consultation")
  const mut = useMutation({
    mutationFn: async () => fetch(`${BACKEND_URL}/api/agent/configure`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ mode }) }).then(r => r.json()),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["agent-status"] }),
  })
  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold">Agent Settings</h1>
      <Card><CardContent className="p-4 space-y-2">
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2"><input type="radio" name="mode" checked={mode === "consultation"} onChange={() => setMode("consultation")} /> Consultation</label>
          <label className="flex items-center gap-2"><input type="radio" name="mode" checked={mode === "autonomous"} onChange={() => setMode("autonomous")} /> Autonomous</label>
        </div>
        <Button onClick={() => mut.mutate()} disabled={mut.isPending}>Save</Button>
      </CardContent></Card>
    </div>
  )
}