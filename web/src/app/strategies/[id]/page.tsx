import { backend } from "@/lib/backend"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import StrategyActions from "./strategy-actions"

type Strategy = { id: string; name: string; description: string; wallet_ids: string[]; created_at: string; updated_at: string }
type RecommendationResponse = { id: string; strategy_id: string; recommendation: string; analysis?: Record<string, any>; created_at: string }

export default async function StrategyDetail({ params }: { params: Promise<{ id: string }> | { id: string } }) {
  const resolvedParams = await Promise.resolve(params)
  const strategyId = resolvedParams.id
  
  if (!strategyId) {
    throw new Error("Strategy ID is required")
  }
  
  const s = await backend<Strategy>(`/api/strategies/${strategyId}`)
  const recs = await backend<RecommendationResponse[]>(`/api/recommendations?strategy_id=${strategyId}`)
  
  if (!s?.id) {
    throw new Error("Strategy not found")
  }
  
  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold">{s.name}</h1>
      <Card>
        <CardContent className="p-4 space-y-2">
          <p>{s.description}</p>
          <StrategyActions strategyId={strategyId} />
        </CardContent>
      </Card>
      <div className="space-y-4">
        {recs.map(r => (
          <Card key={r.id}><CardContent className="p-4 space-y-2"><p className="font-medium">{new Date(r.created_at).toLocaleString()}</p><pre className="whitespace-pre-wrap text-sm">{r.recommendation}</pre></CardContent></Card>
        ))}
      </div>
    </div>
  )
}