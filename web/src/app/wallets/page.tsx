"use client"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Separator } from "@/components/ui/separator"
import { backend } from "@/lib/backend"
import { useState } from "react"

type Wallet = { id: string; address: string; chain: string; label?: string; tokens: string[]; created_at: string; updated_at: string }

export default function WalletsPage() {
  const qc = useQueryClient()
  const { data, isLoading } = useQuery({ queryKey: ["wallets"], queryFn: () => backend<Wallet[]>("/api/wallets") })
  const [form, setForm] = useState({ address: "", chain: "ethereum", label: "", tokens: "BTC,ETH,USDC" })

  const createMut = useMutation({
    mutationFn: async () => backend<Wallet>("/api/wallets", { method: "POST", body: JSON.stringify({
      address: form.address,
      chain: form.chain,
      label: form.label || undefined,
      tokens: form.tokens.split(",").map(t => t.trim()).filter(Boolean),
    }) }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["wallets"] }) },
  })

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold">Wallets</h1>
      <Card>
        <CardContent className="p-4 space-y-2">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-2">
            <Input placeholder="Address" value={form.address} onChange={e => setForm({ ...form, address: e.target.value })} />
            <Input placeholder="Chain" value={form.chain} onChange={e => setForm({ ...form, chain: e.target.value })} />
            <Input placeholder="Label" value={form.label} onChange={e => setForm({ ...form, label: e.target.value })} />
            <Input placeholder="Tokens (comma separated)" value={form.tokens} onChange={e => setForm({ ...form, tokens: e.target.value })} />
          </div>
          <Button onClick={() => createMut.mutate()} disabled={createMut.isPending}>Add Wallet</Button>
        </CardContent>
      </Card>

      <Separator />
      {isLoading ? (
        <p>Loading…</p>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {data?.map(w => (
            <Card key={w.id}>
              <CardContent className="p-4 space-y-2">
                <p className="font-medium">{w.label || w.address}</p>
                <p className="text-sm text-muted-foreground">{w.chain}</p>
                <p className="text-sm">Tokens: {w.tokens.join(", ")}</p>
                <Button asChild variant="outline"><a href={`/wallets/${w.id}`}>Open</a></Button>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}