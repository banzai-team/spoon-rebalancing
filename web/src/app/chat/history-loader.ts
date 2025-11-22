import { backend } from "@/lib/backend"

export type ChatResponse = { message_id: string; user_message: string; agent_response: string; timestamp: string }
export type ChatHistoryResponse = { messages: ChatResponse[]; total: number }

export async function loadChatHistory(strategyId?: string, limit = 50) {
  const params = new URLSearchParams()
  if (strategyId) params.set("strategy_id", strategyId)
  params.set("limit", String(limit))
  return backend<ChatHistoryResponse>(`/api/chat/history?${params.toString()}`)
}