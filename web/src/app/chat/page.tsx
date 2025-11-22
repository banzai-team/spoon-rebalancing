import { ChatPane } from "@/components/chat/chat-pane"

export default function ChatPage() {
  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">AI Chat</h1>
      <ChatPane />
    </div>
  )
}