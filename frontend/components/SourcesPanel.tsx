'use client'

import React, { memo, useState } from 'react'

export interface Source {
  content: string
  metadata?: Record<string, string | number | boolean>
}

interface SourcesPanelProps {
  sources: Source[]
}

// Extracted outside parent — rerender-no-inline-components
function SourceItem({ source, index }: { source: Source; index: number }) {
  const title =
    (source.metadata?.title as string | undefined) ??
    (source.metadata?.document_type as string | undefined) ??
    `Fonte ${index + 1}`

  return (
    <li className="border border-zinc-800 rounded px-3 py-2 space-y-1">
      <p className="text-xs font-medium text-zinc-300 truncate">{title}</p>
      {source.metadata && (
        <div className="flex flex-wrap gap-x-3 gap-y-0.5">
          {Object.entries(source.metadata)
            .filter(([k]) => k !== 'title')
            .slice(0, 4)
            .map(([key, val]) => (
              <span key={key} className="text-[10px] text-zinc-500">
                <span className="text-zinc-600">{key}:</span> {String(val)}
              </span>
            ))}
        </div>
      )}
      <p className="text-xs text-zinc-400 line-clamp-3 leading-relaxed mt-1">
        {source.content}
      </p>
    </li>
  )
}

// rerender-memo: wrapped with React.memo
const SourcesPanel = memo(function SourcesPanel({ sources }: SourcesPanelProps) {
  const [open, setOpen] = useState(false)

  if (sources.length === 0) {
    return null
  }

  return (
    <div className="mt-2 w-full max-w-2xl">
      <button
        onClick={() => setOpen((prev) => !prev)}
        className="flex items-center gap-1.5 text-xs text-zinc-500 hover:text-zinc-300 transition-colors"
        aria-expanded={open}
      >
        <svg
          className={`h-3 w-3 transition-transform ${open ? 'rotate-90' : ''}`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2.5}
          aria-hidden="true"
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
        </svg>
        Ver fontes ({sources.length})
      </button>

      {open ? (
        <ul className="mt-2 space-y-2">
          {sources.map((source, i) => (
            <SourceItem key={i} source={source} index={i} />
          ))}
        </ul>
      ) : null}
    </div>
  )
})

export default SourcesPanel
