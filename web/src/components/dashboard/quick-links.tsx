import Link from "next/link"
import { Card, CardContent } from "@/components/ui/card"

const links = [
  { href: "/wallets", title: "Manage Wallets", desc: "Add, edit, remove wallets" },
  { href: "/strategies", title: "Strategies", desc: "Create and update rebalancing strategies" },
  { href: "/chat", title: "Chat", desc: "Talk to the agent and view history" },
  { href: "/recommendations", title: "Recommendations", desc: "Browse past rebalancing suggestions" },
]

export function QuickLinks() {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
      {links.map(l => (
        <Link key={l.href} href={l.href} className="focus:outline-none focus:ring-2 focus:ring-offset-2 rounded-md">
          <Card>
            <CardContent className="p-4">
              <p className="font-medium">{l.title}</p>
              <p className="text-sm text-stone-600">{l.desc}</p>
            </CardContent>
          </Card>
        </Link>
      ))}
    </div>
  )
}