"use client"
import { BACKEND_URL } from "@/lib/backend"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { toast } from "sonner"

export default function BalanceForm({ walletId, chain }: { walletId: string; chain: string }) {
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
    // Reset form
    e.currentTarget.reset()
    // Reload page to show new balance
    window.location.reload()
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

