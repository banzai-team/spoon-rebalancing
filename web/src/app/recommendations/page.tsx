import { backend } from "@/lib/backend"
import { Card, CardContent } from "@/components/ui/card"

type RecommendationResponse = { id: string; strategy_id: string; recommendation: string; analysis?: Record<string, any>; created_at: string }

export default async function RecommendationsPage() {
  const recs = await backend<RecommendationResponse[]>("/api/recommendations")
  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold">Recommendations</h1>
      <div className="space-y-4">
        {recs.map(r => (
          <Card key={r.id}><CardContent className="p-4 space-y-2"><p className="font-medium">Strategy {r.strategy_id}</p><p className="text-sm text-stone-600">{new Date(r.created_at).toLocaleString()}</p><pre className="whitespace-pre-wrap text-sm">{r.recommendation}</pre></CardContent></Card>
        ))}
      </div>
    </div>
  )
}