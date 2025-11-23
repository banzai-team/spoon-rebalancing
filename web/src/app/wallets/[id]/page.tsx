import { backend } from "@/lib/backend"
import { Card, CardContent } from "@/components/ui/card"
import BalanceForm from "./balance-form"
import BalanceItem from "./balance-item"

type Wallet = { id: string; address: string; chain: string; label?: string; tokens: string[]; created_at: string; updated_at: string }
type Balance = { id: string; wallet_id: string; user_id: string; token_symbol: string; balance: string; balance_usd?: number; chain: string; created_at: string; updated_at: string }

export default async function WalletDetail({ params }: { params: Promise<{ id: string }> | { id: string } }) {
  const resolvedParams = await Promise.resolve(params)
  const walletId = resolvedParams.id
  
  if (!walletId) {
    throw new Error("Wallet ID is required")
  }
  
  const wallet = await backend<Wallet>(`/api/wallets/${walletId}`)
  const balances = await backend<Balance[]>(`/api/wallet-token-balances?wallet_id=${walletId}`)
  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold">{wallet.label + " " + wallet.address}</h1>
      <Card>
        <CardContent className="p-4 space-y-2">
          <p className="text-sm text-muted-foreground">{wallet.chain}</p>
          <p className="text-sm">Tokens: {wallet.tokens.join(", ")}</p>
          <BalanceForm walletId={wallet.id} chain={wallet.chain} />
        </CardContent>
      </Card>
      <div className="space-y-2">
        {balances.map(b => (
          <BalanceItem key={b.id} balance={b} />
        ))}
      </div>
    </div>
  )
}