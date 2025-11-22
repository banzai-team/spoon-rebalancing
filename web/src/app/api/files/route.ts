export const runtime = "nodejs"

import { NextResponse } from "next/server"
import { promises as fs } from "fs"
import path from "path"

export async function POST(req: Request) {
  const form = await req.formData()
  const files = form.getAll("files") as File[]
  const uploadsDir = path.join(process.cwd(), "public", "uploads")
  await fs.mkdir(uploadsDir, { recursive: true })

  const urls: string[] = []
  for (const file of files) {
    const arrayBuffer = await file.arrayBuffer()
    const buffer = Buffer.from(arrayBuffer)
    const safeName = `${Date.now()}-${file.name.replace(/[^a-zA-Z0-9.\-_]/g, "_")}`
    const filePath = path.join(uploadsDir, safeName)
    await fs.writeFile(filePath, buffer)
    urls.push(`/uploads/${safeName}`)
  }

  return NextResponse.json({ urls })
}