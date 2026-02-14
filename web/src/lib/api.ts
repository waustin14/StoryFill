export const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"

export function wsBaseUrl() {
  const base = new URL(API_BASE_URL)
  base.protocol = base.protocol === "https:" ? "wss:" : "ws:"
  base.pathname = "/v1/ws"
  base.search = ""
  return base.toString()
}
