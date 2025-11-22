import { describe, it, expect } from "vitest"
import { render, screen } from "@testing-library/react"
import ChatPage from "@/app/chat/page"

describe("ChatPage", () => {
  it("renders heading", () => {
    render(<ChatPage />)
    expect(screen.getByText(/AI Chat/i)).toBeDefined()
  })
})