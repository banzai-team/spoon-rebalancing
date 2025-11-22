import { AgentStatus } from "@/components/dashboard/agent-status"
import { QuickLinks } from "@/components/dashboard/quick-links"

export default function Home() {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Dashboard</h1>
      <AgentStatus />
      <QuickLinks />
    </div>
  )
}
