import { NextRequest } from "next/server"

const apiBaseUrl =
  process.env.API_INTERNAL_BASE_URL ??
  process.env.NEXT_PUBLIC_API_BASE_URL ??
  "http://localhost:8000"

export async function GET(_req: NextRequest, { params }: { params: { jobId: string } }) {
  const response = await fetch(`${apiBaseUrl}/v1/tts/jobs/${params.jobId}/audio`)
  if (!response.ok) {
    return new Response("Audio not available.", { status: response.status })
  }

  const headers = new Headers(response.headers)
  return new Response(response.body, {
    status: response.status,
    headers,
  })
}
