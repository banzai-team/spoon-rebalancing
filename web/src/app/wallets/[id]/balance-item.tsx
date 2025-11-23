"use client"
import { BACKEND_URL } from "@/lib/backend"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { toast } from "sonner"

type Balance = { id: string; wallet_id: string; user_id: string; token_symbol: string; balance: string; balance_usd?: number; chain: string; created_at: string; updated_at: string }

export default function BalanceItem({ balance }: { balance: Balance }) {
  const handleDelete = async () => {
    const res = await fetch(`${BACKEND_URL}/api/wallet-token-balances/${balance.id}`, { method: "DELETE" })
    if (!res.ok) return toast.error("Delete failed")
    toast.success("Deleted")
    // Reload page to update list
    window.location.reload()
  }
  
  return (
    <Card>
      <CardContent className="p-4 flex items-center justify-between">
        <div>
          <p className="font-medium">{balance.token_symbol}</p>
          <p className="text-sm text-muted-foreground">{balance.balance} ({balance.balance_usd ?? 0} USD)</p>
        </div>
        <Button variant="outline" onClick={handleDelete}>Delete</Button>
      </CardContent>
    </Card>
  )
}

