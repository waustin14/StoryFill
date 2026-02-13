import { Suspense } from "react"
import TemplateSelectClient from "./template-select-client"

export default function TemplateSelectPage() {
  return (
    <Suspense>
      <TemplateSelectClient />
    </Suspense>
  )
}
