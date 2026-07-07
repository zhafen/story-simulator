const API_BASE = "http://127.0.0.1:8000"

export interface Position {
  alias: string
  x: number
  y: number
}

export interface InputResult {
  response: string | null
  stopped: boolean
  positions: Position[]
}

export async function fetchPositions(): Promise<Position[]> {
  const res = await fetch(`${API_BASE}/positions`)
  if (!res.ok) throw new Error(`GET /positions failed: ${res.status}`)
  const data = await res.json()
  return data.positions
}

export async function sendInput(text: string): Promise<InputResult> {
  const res = await fetch(`${API_BASE}/input`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  })
  if (!res.ok) throw new Error(`POST /input failed: ${res.status}`)
  return res.json()
}
