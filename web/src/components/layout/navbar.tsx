"use client"
import Link from "next/link"
import { usePathname } from "next/navigation"
import { Separator } from "@/components/ui/separator"
import { Wallet, MessageSquare, Settings, BookOpen, LayoutDashboard, ChevronRight } from "lucide-react"

const items = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/wallets", label: "Wallets", icon: Wallet },
  { href: "/strategies", label: "Strategies", icon: BookOpen },
  { href: "/recommendations", label: "Reports", icon: BookOpen },
  { href: "/chat", label: "AI Chat", icon: MessageSquare },
  { href: "/settings", label: "Settings", icon: Settings },
]

export function Sidebar() {
  const pathname = usePathname()
  return (
    <aside className="bg-sidebar text-sidebar-foreground border-r border-sidebar-border flex flex-col min-h-dvh">
      <div className="h-14 px-4 flex items-center justify-between">
        <Link href="/" className="font-semibold tracking-wide">Spoon Rebalancer</Link>
      </div>
      <Separator />
      <nav className="px-2 py-2 space-y-1" aria-label="Primary">
        {items.map(({ href, label, icon: Icon }) => {
          const active = pathname === href
          return (
            <Link key={href} href={href} aria-current={active ? "page" : undefined}
              className={`group flex items-center gap-3 px-3 py-2 rounded-md text-sm ${active ? "bg-input/30 text-primary" : "hover:bg-input/30"}`}>
              <span className={`inline-flex items-center justify-center size-6 rounded-sm ${active ? "bg-primary text-primary-foreground" : "bg-input/40"}`}>
                <Icon className="size-4" aria-hidden />
              </span>
              <span className="flex-1">{label}</span>
              <ChevronRight className={`size-4 transition-colors ${active ? "text-primary" : "text-muted-foreground"}`} />
            </Link>
          )
        })}
      </nav>
      <div className="mt-auto px-3 py-4 text-xs text-muted-foreground">v0.1.0</div>
    </aside>
  )
}