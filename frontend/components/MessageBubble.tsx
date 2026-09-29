'use client'

import React, { memo } from 'react'
import SourcesPanel, { type Source } from './SourcesPanel'

export interface QueryPlanData {
  intent?: string
  clarified_query?: string
  entities?: string[]
  keywords?: string[]
}

interface MessageBubbleProps {
  role: 'user' | 'assistant'
  content: string
  isStreaming?: boolean
  latency?: number
  sources?: Source[]
  queryPlan?: QueryPlanData
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

// Module-level helper for formatting bold (**text**) and code (`code`) — rerender-no-inline-components
function FormattedText({ content }: { content: string }) {
  if (!content) return null

  // Divide o texto identificando trechos em negrito (**...**) e código inline (`...`)
  const parts = content.split(/(\*\*[\s\S]*?\*\*|`[\s\S]*?`)/g)


  return (
    <>
      {parts.map((part, index) => {
        if (part.startsWith('**') && part.endsWith('**') && part.length >= 4) {
          return (
            <strong key={index} className="font-bold text-white">
              {part.slice(2, -2)}
            </strong>
          )
        }
        if (part.startsWith('`') && part.endsWith('`') && part.length >= 2) {
          return (
            <code
              key={index}
              className="rounded bg-zinc-800/80 px-1 py-0.5 font-mono text-xs text-zinc-200"
            >
              {part.slice(1, -1)}
            </code>
          )
        }
        return <React.Fragment key={index}>{part}</React.Fragment>
      })}
    </>
  )
}

// rerender-memo: memoized to avoid re-renders from parent state changes
const MessageBubble = memo(function MessageBubble({
  role,
  content,
  isStreaming = false,
  latency,
  sources = [],
  queryPlan,
}: MessageBubbleProps) {
  const isUser = role === 'user'

  return (
    <div className={`flex w-full ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div className={`flex flex-col ${isUser ? 'items-end' : 'items-start'} max-w-[85%] lg:max-w-[70%]`}>
        {/* Intent & Clarified Query Badge */}
        {!isUser && queryPlan?.intent ? (
          <div className="mb-1.5 flex flex-wrap items-center gap-1.5 px-1 text-xs">
            <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/10 px-2.5 py-0.5 text-[11px] font-medium text-emerald-400 border border-emerald-500/20">
              <span className="text-[10px]">🎯</span>
              <span>{queryPlan.intent}</span>
            </span>
            {queryPlan.clarified_query && queryPlan.clarified_query !== content ? (
              <span
                className="inline-flex items-center gap-1 rounded-full bg-zinc-800/80 px-2 py-0.5 text-[11px] text-zinc-400 border border-zinc-700/50"
                title={`Busca otimizada: ${queryPlan.clarified_query}`}
              >
                <span className="text-[10px]">🔍</span>
                <span className="max-w-[260px] truncate">{queryPlan.clarified_query}</span>
              </span>
            ) : null}
          </div>
        ) : null}

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
              <span className="whitespace-pre-wrap">
                <FormattedText content={content} />
              </span>
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
