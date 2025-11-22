"use client"
import { useEffect, useMemo, useRef, useState } from "react"
import { Card, CardContent } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Separator } from "@/components/ui/separator"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Paperclip, Send, Loader2, Smile } from "lucide-react"
import { toast } from "sonner"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import { DropdownMenu, DropdownMenuTrigger, DropdownMenuContent } from "@/components/ui/dropdown-menu"
const EMOJI = [
  "😀","😅","😂","😉","😊","😍","🤔","🤨","😐","😴",
  "👍","👎","🙏","🚀","🔥","🎯","💡","✅","❌","📈"
]

type ChatMessage = { id: string; role: "user" | "assistant" | "system"; content: string }

export function ChatPane() {
  const [strategyId, setStrategyId] = useState<string | undefined>(undefined)
  const [walletIds, setWalletIds] = useState<string[] | undefined>(undefined)
  const [files, setFiles] = useState<File[]>([])
  const fileInputRef = useRef<HTMLInputElement | null>(null)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState("")
  const [typing, setTyping] = useState(false)

  const onPickFiles = () => fileInputRef.current?.click()

  const onFilesChanged = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const picked = Array.from(e.target.files ?? [])
    if (picked.length === 0) return
    setFiles(picked)
    const form = new FormData()
    picked.forEach((f: File) => form.append("files", f))
    const res = await fetch("/api/files", { method: "POST", body: form })
    if (!res.ok) return toast.error("Upload failed")
    const { urls } = await res.json() as { urls: string[] }
    if (urls.length) {
      const joined = urls.map(u => `Attachment: ${u}`).join("\n")
      setInput((prev: string) => prev ? `${prev}\n\n${joined}` : joined)
      toast.success("Files attached")
    }
  }

  const sendMessage = async (e: React.FormEvent) => {
    e.preventDefault()
    const text = input.trim()
    if (!text) return
    const userMsg: ChatMessage = { id: crypto.randomUUID(), role: "user", content: text }
    setMessages(prev => [...prev, userMsg])
    setInput("")
    setTyping(true)
    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages, strategyId, walletIds, message: text }),
      })
      if (!res.ok) throw new Error(`Chat ${res.status}`)
      const data = await res.json() as { message: ChatMessage }
      setMessages(prev => [...prev, data.message])
    } catch (err) {
      toast.error("Chat error")
    } finally {
      setTyping(false)
      setFiles([])
    }
  }

  return (
    <Card>
      <CardContent className="p-0">
        <div className="grid grid-rows-[1fr_auto] h-[70vh]">
          <ScrollArea className="p-4">
            <div className="space-y-4">
              {messages.map((m: ChatMessage) => (
                <div key={m.id} className="flex items-start gap-3" role="listitem">
                  <Avatar>
                    <AvatarFallback>{m.role === "user" ? "U" : "A"}</AvatarFallback>
                  </Avatar>
                  <div className="max-w-prose text-sm">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{m.content}</ReactMarkdown>
                  </div>
                </div>
              ))}
              {typing && (
                <div className="flex items-center gap-2 text-stone-600" role="status" aria-live="polite">
                  <Loader2 className="size-4 animate-spin" />
                  <span>Agent is typing…</span>
                </div>
              )}
            </div>
          </ScrollArea>
          <Separator />
          <form onSubmit={sendMessage} className="p-3 flex items-center gap-2" aria-label="Send message">
            <Input
              value={input}
              onChange={e => setInput(e.target.value)}
              placeholder="Type your message"
              aria-label="Message input"
            />
            <input ref={fileInputRef} type="file" className="hidden" multiple onChange={onFilesChanged} />
            <Button type="button" variant="outline" onClick={onPickFiles} aria-label="Attach files">
              <Paperclip className="size-4" />
            </Button>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button type="button" variant="outline" aria-label="Insert emoji"><Smile className="size-4" /></Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent className="p-2" align="end">
                <div className="grid grid-cols-10 gap-1">
                  {EMOJI.map(e => (
                    <button key={e} type="button" className="text-xl" aria-label={`Insert ${e}`} onClick={() => setInput(prev => (prev || "") + e)}>{e}</button>
                  ))}
                </div>
              </DropdownMenuContent>
            </DropdownMenu>
            <Button type="submit" disabled={typing} aria-label="Send">
              {typing ? <Loader2 className="size-4 animate-spin" /> : <Send className="size-4" />}
            </Button>
          </form>
        </div>
      </CardContent>
    </Card>
  )
}