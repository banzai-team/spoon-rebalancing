"use client"
import { useQuery } from "@tanstack/react-query"
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { Badge } from "@/components/ui/badge"

async function fetchAgentStatus() {
  const url = `${process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000"}/api/agent/status`
  const res = await fetch(url, { cache: "no-store" })
  if (!res.ok) throw new Error(`Status ${res.status}`)
  return res.json() as Promise<{
    success: boolean
    status: { mode: string; min_profit_threshold_usd: number; target_allocation: Record<string, number> | null; max_steps: number }
    statistics: { wallets_count: number; strategies_count: number; recommendations_count: number; chat_messages_count: number }
  }>
}

export function AgentStatus() {
  const { data, isLoading, error } = useQuery({ queryKey: ["agent-status"], queryFn: fetchAgentStatus })

  if (isLoading) return <Skeleton className="h-32 w-full" />
  if (error) return <div role="alert" className="text-red-600">Failed to load agent status</div>

  return (
    <Card aria-label="Agent status">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          Agent Mode
          <Badge variant="secondary">{data?.status.mode}</Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div><p className="text-sm text-muted-foreground">Wallets</p><p className="text-lg font-medium">{data?.statistics.wallets_count}</p></div>
        <div><p className="text-sm text-muted-foreground">Strategies</p><p className="text-lg font-medium">{data?.statistics.strategies_count}</p></div>
        <div><p className="text-sm text-muted-foreground">Recommendations</p><p className="text-lg font-medium">{data?.statistics.recommendations_count}</p></div>
        <div><p className="text-sm text-muted-foreground">Chat Messages</p><p className="text-lg font-medium">{data?.statistics.chat_messages_count}</p></div>
      </CardContent>
    </Card>
  )
}