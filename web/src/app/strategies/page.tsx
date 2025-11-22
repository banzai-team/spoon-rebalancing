"use client"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { backend } from "@/lib/backend"
import { useState } from "react"

type Strategy = { id: string; name: string; description: string; wallet_ids: string[]; created_at: string; updated_at: string }
type Wallet = { id: string; address: string; chain: string; label?: string }

export default function StrategiesPage() {
  const qc = useQueryClient()
  const { data: wallets } = useQuery({ queryKey: ["wallets"], queryFn: () => backend<Wallet[]>("/api/wallets") })
  const { data: strategies } = useQuery({ queryKey: ["strategies"], queryFn: () => backend<Strategy[]>("/api/strategies") })
  const [form, setForm] = useState({ name: "", description: "40% BTC, 35% ETH, 25% USDC", selectedWallets: [] as string[] })

  const createMut = useMutation({
    mutationFn: async () => backend<Strategy>("/api/strategies", { method: "POST", body: JSON.stringify({
      name: form.name,
      description: form.description,
      wallet_ids: form.selectedWallets,
    }) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["strategies"] }),
  })

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold">Strategies</h1>
      <Card>
        <CardContent className="p-4 space-y-2">
          <Input placeholder="Name" value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} />
          <Input placeholder="Description" value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} />
          <div className="grid grid-cols-2 gap-2">
            {wallets?.map(w => (
              <label key={w.id} className="flex items-center gap-2">
                <input type="checkbox" aria-label={`Select wallet ${w.label || w.address}`} checked={form.selectedWallets.includes(w.id)} onChange={e => {
                  const checked = e.target.checked
                  setForm(prev => ({ ...prev, selectedWallets: checked ? [...prev.selectedWallets, w.id] : prev.selectedWallets.filter(id => id !== w.id) }))
                }} />
                <span>{w.label || w.address} ({w.chain})</span>
              </label>
            ))}
          </div>
          <Button onClick={() => createMut.mutate()} disabled={createMut.isPending}>Create Strategy</Button>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {strategies?.map(s => (
          <Card key={s.id}>
            <CardContent className="p-4 space-y-2">
              <p className="font-medium">{s.name}</p>
              <p className="text-sm text-muted-foreground">{s.description}</p>
              <Button asChild variant="outline"><a href={`/strategies/${s.id}`}>Open</a></Button>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  )
}