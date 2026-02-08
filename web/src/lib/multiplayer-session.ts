export type MultiplayerSession = {
  roomCode: string
  roomId: string
  roundId: string
  templateId: string | null
  role: "host" | "player"
  playerId: string
  playerToken: string
  hostToken?: string
  displayName?: string | null
  createdAt: string
}

const STORAGE_KEY = "storyfill.multiplayerSession"

export function saveMultiplayerSession(session: MultiplayerSession) {
  if (typeof window === "undefined") return
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(session))
}

export function loadMultiplayerSession(): MultiplayerSession | null {
  if (typeof window === "undefined") return null
  const raw = window.localStorage.getItem(STORAGE_KEY)
  if (!raw) return null
  try {
    return JSON.parse(raw) as MultiplayerSession
  } catch {
    return null
  }
}

export function clearMultiplayerSession() {
  if (typeof window === "undefined") return
  window.localStorage.removeItem(STORAGE_KEY)
}
