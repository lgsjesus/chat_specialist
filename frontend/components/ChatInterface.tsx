'use client'

import React, {
  useCallback,
  useDeferredValue,
  useEffect,
  useRef,
  useState,
} from 'react'
import dynamic from 'next/dynamic'
import MessageBubble, { type QueryPlanData } from './MessageBubble'
import type { Source } from './SourcesPanel'
import type { Filters } from './FilterPanel'

// bundle-dynamic-imports: FilterPanel is non-critical UI; load it lazily
const FilterPanel = dynamic(() => import('./FilterPanel'), {
  ssr: false,
  loading: () => (
    <div className="border-b border-zinc-800 bg-zinc-900 px-4 py-3 text-xs text-zinc-600">
      Carregando filtros…
    </div>
  ),
})

// ─── Types ─────────────────────────────────────────────────────────────────

interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  isStreaming?: boolean
  latency?: number
  sources?: Source[]
  queryPlan?: QueryPlanData
}

type ModeToggle = 'normal' | 'stream'

// ─── Helpers (module-level, rerender-no-inline-components) ─────────────────

function buildRequestBody(question: string, filters: Filters, historyMessages: ChatMessage[] = []) {
  const activeFilters: Record<string, string> = {}
  if (filters.tenant) activeFilters.tenant = filters.tenant
  if (filters.audience) activeFilters.audience = filters.audience
  if (filters.plan) activeFilters.plan = filters.plan

  const history = historyMessages
    .filter((m) => m.content.trim().length > 0)
    .slice(-6)
    .map((m) => ({
      role: m.role,
      content: m.content,
    }))

  return {
    question,
    ...(history.length > 0 ? { history } : {}),
    ...(Object.keys(activeFilters).length > 0 ? { filters: activeFilters } : {}),
  }
}

function generateId(): string {
  return Math.random().toString(36).slice(2, 10)
}


// ─── Empty state illustration ──────────────────────────────────────────────

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center h-full gap-3 text-center select-none">
      <div className="flex h-12 w-12 items-center justify-center rounded-2xl border border-zinc-800 bg-zinc-900">
        <svg
          className="h-6 w-6 text-zinc-600"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={1.5}
          aria-hidden="true"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M8.625 12a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H8.25m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H12m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0h-.375M21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 01-2.555-.337A5.972 5.972 0 015.41 20.97a5.969 5.969 0 01-.474-.065 4.48 4.48 0 00.978-2.025c.09-.457-.133-.901-.467-1.226C3.93 16.178 3 14.189 3 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25z"
          />
        </svg>
      </div>
      <p className="text-sm text-zinc-500">
        Faça uma pergunta para começar
      </p>
    </div>
  )
}

// ─── Send button ───────────────────────────────────────────────────────────

function SendButton({ disabled }: { disabled: boolean }) {
  return (
    <button
      type="submit"
      disabled={disabled}
      className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-white text-black transition-opacity disabled:opacity-30 hover:opacity-80"
      aria-label="Enviar"
    >
      <svg
        className="h-4 w-4"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
        strokeWidth={2.5}
        aria-hidden="true"
      >
        <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 10.5L12 3m0 0l7.5 7.5M12 3v18" />
      </svg>
    </button>
  )
}

// ─── Main component ────────────────────────────────────────────────────────

export default function ChatInterface() {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [mode, setMode] = useState<ModeToggle>('normal')
  const [filters, setFilters] = useState<Filters>({ tenant: '', audience: '', plan: '' })

  const bottomRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const abortRef = useRef<AbortController | null>(null)

  // rerender-use-deferred-value: keep the message list deferred so typing stays snappy
  const deferredMessages = useDeferredValue(messages)

  // Auto-scroll whenever messages change
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // ── Normal (non-streaming) send ──────────────────────────────────────────
  const sendNormal = useCallback(
    async (question: string, history: ChatMessage[]) => {
      const assistantId = generateId()

      // rerender-functional-setstate
      setMessages((prev) => [
        ...prev,
        { id: assistantId, role: 'assistant', content: '' },
      ])

      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(buildRequestBody(question, filters, history)),
        signal: abortRef.current?.signal,
      })

      if (!res.ok) {
        const err = await res.json().catch(() => ({ error: res.statusText }))
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId
              ? { ...m, content: `Erro: ${err.error ?? res.statusText}` }
              : m,
          ),
        )
        return
      }

      const data = await res.json()

      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId
            ? {
                ...m,
                content: data.answer ?? '',
                latency: data.latency_ms,
                sources: data.sources ?? [],
                queryPlan: data.query_plan ?? undefined,
              }
            : m,
        ),
      )
    },
    [filters],
  )

  // ── Streaming send ───────────────────────────────────────────────────────
  const sendStream = useCallback(
    async (question: string, history: ChatMessage[]) => {
      const assistantId = generateId()

      setMessages((prev) => [
        ...prev,
        { id: assistantId, role: 'assistant', content: '', isStreaming: true },
      ])

      const res = await fetch('/api/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(buildRequestBody(question, filters, history)),
        signal: abortRef.current?.signal,
      })

      if (!res.ok || !res.body) {
        const err = await res.json().catch(() => ({ error: res.statusText }))
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId
              ? { ...m, content: `Erro: ${err.error ?? res.statusText}`, isStreaming: false }
              : m,
          ),
        )
        return
      }

      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      try {
        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          buffer += decoder.decode(value, { stream: true })

          // Parse SSE lines from buffer
          const lines = buffer.split('\n')
          buffer = lines.pop() ?? ''

          for (const line of lines) {
            const trimmed = line.trim()
            if (!trimmed.startsWith('data:')) continue

            const payload = trimmed.slice(5).trim()
            if (payload === '[DONE]') {
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantId ? { ...m, isStreaming: false } : m,
                ),
              )
              return
            }

            try {
              const parsed: { token?: string; plan?: QueryPlanData } = JSON.parse(payload)
              if (parsed.plan) {
                setMessages((prev) =>
                  prev.map((m) =>
                    m.id === assistantId ? { ...m, queryPlan: parsed.plan } : m,
                  ),
                )
              }
              if (parsed.token) {
                setMessages((prev) =>
                  prev.map((m) =>
                    m.id === assistantId
                      ? { ...m, content: m.content + parsed.token }
                      : m,
                  ),
                )
              }
            } catch {
              // Ignore malformed SSE frames
            }
          }
        }
      } finally {
        // Ensure streaming indicator is cleared even on early exit
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId ? { ...m, isStreaming: false } : m,
          ),
        )
      }
    },
    [filters],
  )

  // ── Handle submit ────────────────────────────────────────────────────────
  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault()
      const question = input.trim()
      if (!question || isLoading) return

      // Cancel any ongoing request
      abortRef.current?.abort()
      abortRef.current = new AbortController()

      const currentHistory = [...messages]
      const userMsgId = generateId()
      // rerender-functional-setstate
      setMessages((prev) => [...prev, { id: userMsgId, role: 'user', content: question }])
      setInput('')
      setIsLoading(true)

      try {
        if (mode === 'stream') {
          await sendStream(question, currentHistory)
        } else {
          await sendNormal(question, currentHistory)
        }
      } catch (err) {
        if ((err as Error).name !== 'AbortError') {
          console.error('Chat error:', err)
        }
      } finally {
        setIsLoading(false)
        // Restore focus
        inputRef.current?.focus()
      }
    },
    [input, isLoading, messages, mode, sendNormal, sendStream],
  )


  // Allow Shift+Enter for newlines, Enter to submit
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault()
        handleSubmit(e as unknown as React.FormEvent)
      }
    },
    [handleSubmit],
  )

  const handleInputChange = useCallback((e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value)
  }, [])

  const handleModeToggle = useCallback((newMode: ModeToggle) => {
    setMode(newMode)
  }, [])

  return (
    <div className="flex h-full flex-col">
      {/* ── Filter panel (dynamic import) ─────────────────────────────── */}
      <FilterPanel filters={filters} onChange={setFilters} />

      {/* ── Header ────────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between border-b border-zinc-800 px-4 py-3">
        <h1 className="text-sm font-semibold text-zinc-100">TeleTech Chat</h1>

        {/* Mode toggle */}
        <div className="flex items-center gap-1 rounded-lg border border-zinc-800 bg-zinc-900 p-0.5 text-xs">
          <button
            onClick={() => handleModeToggle('normal')}
            className={`rounded-md px-3 py-1 transition-colors ${
              mode === 'normal'
                ? 'bg-white text-black font-medium'
                : 'text-zinc-400 hover:text-zinc-200'
            }`}
          >
            Normal
          </button>
          <button
            onClick={() => handleModeToggle('stream')}
            className={`rounded-md px-3 py-1 transition-colors ${
              mode === 'stream'
                ? 'bg-white text-black font-medium'
                : 'text-zinc-400 hover:text-zinc-200'
            }`}
          >
            Stream
          </button>
        </div>
      </div>

      {/* ── Messages area ─────────────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto px-4 py-6">
        <div className="mx-auto flex max-w-2xl flex-col gap-5">
          {deferredMessages.length === 0 ? (
            <EmptyState />
          ) : (
            deferredMessages.map((msg) => (
              <MessageBubble
                key={msg.id}
                role={msg.role}
                content={msg.content}
                isStreaming={msg.isStreaming}
                latency={msg.latency}
                sources={msg.sources}
                queryPlan={msg.queryPlan}
              />

            ))
          )}
          <div ref={bottomRef} />
        </div>
      </div>

      {/* ── Input area ────────────────────────────────────────────────── */}
      <div className="border-t border-zinc-800 bg-zinc-950 px-4 py-4">
        <form
          onSubmit={handleSubmit}
          className="mx-auto flex max-w-2xl items-end gap-2"
        >
          <textarea
            ref={inputRef}
            value={input}
            onChange={handleInputChange}
            onKeyDown={handleKeyDown}
            placeholder="Faça uma pergunta… (Enter para enviar)"
            rows={1}
            disabled={isLoading}
            className="flex-1 resize-none overflow-hidden rounded-xl border border-zinc-700 bg-zinc-900 px-4 py-2.5 text-sm text-zinc-100 placeholder-zinc-600 outline-none focus:border-zinc-500 transition-colors disabled:opacity-50 leading-relaxed"
            style={{ maxHeight: '160px', minHeight: '40px' }}
            onInput={(e) => {
              const el = e.currentTarget
              el.style.height = 'auto'
              el.style.height = `${Math.min(el.scrollHeight, 160)}px`
            }}
          />
          <SendButton disabled={isLoading || input.trim().length === 0} />
        </form>
        <p className="mx-auto mt-2 max-w-2xl text-center text-[10px] text-zinc-700">
          {mode === 'stream' ? 'Modo streaming ativo — tokens em tempo real' : 'Modo normal — aguarda resposta completa'}
        </p>
      </div>
    </div>
  )
}
