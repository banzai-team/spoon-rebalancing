import { NextResponse } from "next/server"

export async function POST(req: Request) {
  const body = await req.json()
  const messages: { role: "user" | "assistant" | "system"; content: string }[] = body.messages ?? []
  const strategyId: string | undefined = body.strategyId
  const walletIds: string[] | undefined = body.walletIds

  const lastUser = [...messages].reverse().find(m => m.role === "user")
  const userText = lastUser?.content ?? ""

  const res = await fetch(`${process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000"}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message: userText, strategy_id: strategyId, wallet_ids: walletIds }),
    cache: "no-store",
  })

  if (!res.ok) {
    const errorText = await res.text()
    return NextResponse.json({ error: errorText || "Chat backend error" }, { status: res.status })
  }

  const data = await res.json() as { message_id: string; agent_response: string }
  return NextResponse.json({
    message: { id: data.message_id, role: "assistant", content: data.agent_response },
  })
}