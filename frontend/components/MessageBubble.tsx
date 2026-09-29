'use client'

import React, { memo } from 'react'
import SourcesPanel, { type Source } from './SourcesPanel'

interface MessageBubbleProps {
  role: 'user' | 'assistant'
  content: string
  isStreaming?: boolean
  latency?: number
  sources?: Source[]
}

// Typing cursor rendered as a sibling span — rerender-no-inline-components
function StreamingCursor() {
  return (
    <span
      className="ml-0.5 inline-block h-[1em] w-0.5 align-middle bg-zinc-400 animate-pulse"
      aria-hidden="true"
    />
  )
}

// Three-dot loading indicator for empty assistant bubble
function LoadingDots() {
  return (
    <span className="flex items-center gap-1 py-0.5" aria-label="Carregando...">
      <span className="h-1.5 w-1.5 rounded-full bg-zinc-500 animate-bounce [animation-delay:-0.3s]" />
      <span className="h-1.5 w-1.5 rounded-full bg-zinc-500 animate-bounce [animation-delay:-0.15s]" />
      <span className="h-1.5 w-1.5 rounded-full bg-zinc-500 animate-bounce" />
    </span>
  )
}

// rerender-memo: memoized to avoid re-renders from parent state changes
const MessageBubble = memo(function MessageBubble({
  role,
  content,
  isStreaming = false,
  latency,
  sources = [],
}: MessageBubbleProps) {
  const isUser = role === 'user'

  return (
    <div className={`flex w-full ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div className={`flex flex-col ${isUser ? 'items-end' : 'items-start'} max-w-[85%] lg:max-w-[70%]`}>
        {/* Bubble */}
        <div
          className={
            isUser
              ? 'rounded-2xl rounded-tr-sm bg-zinc-800 px-4 py-2.5 text-sm text-zinc-100'
              : 'px-1 py-0.5 text-sm text-zinc-100 leading-relaxed'
          }
        >
          {content.length === 0 && !isUser ? (
            <LoadingDots />
          ) : (
            <>
              <span className="whitespace-pre-wrap">{content}</span>
              {isStreaming ? <StreamingCursor /> : null}
            </>
          )}
        </div>

        {/* Footer: latency badge (normal mode only) */}
        {!isUser && latency !== undefined ? (
          <p className="mt-1 px-1 text-[10px] text-zinc-600">
            {latency.toFixed(0)} ms
          </p>
        ) : null}

        {/* Sources accordion (assistant only, normal mode) */}
        {!isUser && sources.length > 0 ? (
          <div className="px-1">
            <SourcesPanel sources={sources} />
          </div>
        ) : null}
      </div>
    </div>
  )
})

export default MessageBubble
