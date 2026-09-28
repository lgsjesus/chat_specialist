import { Suspense } from 'react'
import ChatInterface from '@/components/ChatInterface'

function LoadingFallback() {
  return (
    <div className="flex h-full items-center justify-center">
      <div className="flex gap-1">
        <span className="h-2 w-2 animate-bounce rounded-full bg-zinc-500 [animation-delay:-0.3s]" />
        <span className="h-2 w-2 animate-bounce rounded-full bg-zinc-500 [animation-delay:-0.15s]" />
        <span className="h-2 w-2 animate-bounce rounded-full bg-zinc-500" />
      </div>
    </div>
  )
}

export default function Page() {
  return (
    <main className="h-full">
      <Suspense fallback={<LoadingFallback />}>
        <ChatInterface />
      </Suspense>
    </main>
  )
}
