import { backend, BACKEND_URL } from "@/lib/backend"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { toast } from "sonner"

type Wallet = { id: string; address: string; chain: string; label?: string; tokens: string[]; created_at: string; updated_at: string }
type Balance = { id: string; wallet_id: string; user_id: string; token_symbol: string; balance: string; balance_usd?: number; chain: string; created_at: string; updated_at: string }

export default async function WalletDetail({ params }: { params: { id: string } }) {
  const wallet = await backend<Wallet>(`/api/wallets/${params.id}`)
  const balances = await backend<Balance[]>(`/api/wallet-token-balances?wallet_id=${params.id}`)
  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold">{wallet.label || wallet.address}</h1>
      <Card>
        <CardContent className="p-4 space-y-2">
              <p className="text-sm text-muted-foreground">{wallet.chain}</p>
          <p className="text-sm">Tokens: {wallet.tokens.join(", ")}</p>
          <BalanceForm walletId={wallet.id} chain={wallet.chain} />
        </CardContent>
      </Card>
      <div className="space-y-2">
        {balances.map(b => (
          <Card key={b.id}><CardContent className="p-4 flex items-center justify-between"><div><p className="font-medium">{b.token_symbol}</p><p className="text-sm text-muted-foreground">{b.balance} ({b.balance_usd ?? 0} USD)</p></div><Button variant="outline" onClick={async () => {
            const res = await fetch(`${BACKEND_URL}/api/wallet-token-balances/${b.id}`, { method: "DELETE" })
            if (!res.ok) return toast.error("Delete failed")
            toast.success("Deleted")
          }}>Delete</Button></CardContent></Card>
        ))}
      </div>
    </div>
  )
}
function BalanceForm({ walletId, chain }: { walletId: string; chain: string }) {
  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const formData = new FormData(e.currentTarget)
    const token_symbol = String(formData.get("token_symbol") || "")
    const balance = String(formData.get("balance") || "")
    const balance_usd = Number(formData.get("balance_usd") || "")
    const res = await fetch(`${BACKEND_URL}/api/wallet-token-balances`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ wallet_id: walletId, token_symbol, balance, balance_usd: isNaN(balance_usd) ? undefined : balance_usd, chain }),
    })
    if (!res.ok) return toast.error("Failed to upsert balance")
    toast.success("Balance saved")
  }
  return (
    <form onSubmit={onSubmit} className="grid grid-cols-1 md:grid-cols-5 gap-2 mt-2">
      <Input name="token_symbol" placeholder="Token" />
      <Input name="balance" placeholder="Balance" />
      <Input name="balance_usd" placeholder="Balance USD" />
      <Input name="chain" placeholder="Chain" defaultValue={chain} />
      <Button type="submit">Add/Update</Button>
    </form>
  )
}