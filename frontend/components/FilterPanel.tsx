'use client'

import React, { useCallback, useState } from 'react'

export type AudienceOption = 'b2b' | 'b2c' | 'all' | ''

export interface Filters {
  tenant: string
  audience: AudienceOption
  plan: string
}

interface FilterPanelProps {
  filters: Filters
  onChange: (filters: Filters) => void
}

const AUDIENCE_OPTIONS: { label: string; value: AudienceOption }[] = [
  { label: '— Sem filtro —', value: '' },
  { label: 'B2B', value: 'b2b' },
  { label: 'B2C', value: 'b2c' },
  { label: 'All', value: 'all' },
]

const EMPTY_FILTERS: Filters = { tenant: '', audience: '', plan: '' }

export function countActiveFilters(filters: Filters): number {
  return [filters.tenant, filters.audience, filters.plan].filter(Boolean).length
}

export default function FilterPanel({ filters, onChange }: FilterPanelProps) {
  const [open, setOpen] = useState(false)

  const activeCount = countActiveFilters(filters)

  const handleClear = useCallback(() => {
    onChange(EMPTY_FILTERS)
  }, [onChange])

  const handleTenantChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      // rerender-functional-setstate: derive next state from previous via onChange callback
      onChange({ ...filters, tenant: e.target.value })
    },
    [filters, onChange],
  )

  const handleAudienceChange = useCallback(
    (e: React.ChangeEvent<HTMLSelectElement>) => {
      onChange({ ...filters, audience: e.target.value as AudienceOption })
    },
    [filters, onChange],
  )

  const handlePlanChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      onChange({ ...filters, plan: e.target.value })
    },
    [filters, onChange],
  )

  return (
    <div className="border-b border-zinc-800 bg-zinc-900">
      {/* Header row */}
      <button
        onClick={() => setOpen((prev) => !prev)}
        className="flex w-full items-center gap-2 px-4 py-3 text-sm text-zinc-400 hover:text-zinc-200 transition-colors"
        aria-expanded={open}
      >
        <svg
          className={`h-3.5 w-3.5 transition-transform ${open ? 'rotate-90' : ''}`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2.5}
          aria-hidden="true"
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
        </svg>
        <span className="font-medium">Filtros</span>
        {activeCount > 0 ? (
          <span className="ml-1 flex h-4 w-4 items-center justify-center rounded-full bg-white text-[10px] font-bold text-black">
            {activeCount}
          </span>
        ) : null}
        <span className="ml-auto text-xs text-zinc-600">opcionais</span>
      </button>

      {/* Collapsible body */}
      {open ? (
        <div className="px-4 pb-4 pt-1 grid grid-cols-1 gap-3 sm:grid-cols-3">
          {/* Tenant */}
          <div className="flex flex-col gap-1">
            <label htmlFor="filter-tenant" className="text-xs font-medium text-zinc-500 uppercase tracking-wide">
              Tenant
            </label>
            <input
              id="filter-tenant"
              type="text"
              value={filters.tenant}
              onChange={handleTenantChange}
              placeholder="ex: teletech"
              className="rounded border border-zinc-700 bg-zinc-800 px-3 py-1.5 text-sm text-zinc-100 placeholder-zinc-600 outline-none focus:border-zinc-500 transition-colors"
            />
          </div>

          {/* Audience */}
          <div className="flex flex-col gap-1">
            <label htmlFor="filter-audience" className="text-xs font-medium text-zinc-500 uppercase tracking-wide">
              Audience
            </label>
            <select
              id="filter-audience"
              value={filters.audience}
              onChange={handleAudienceChange}
              className="rounded border border-zinc-700 bg-zinc-800 px-3 py-1.5 text-sm text-zinc-100 outline-none focus:border-zinc-500 transition-colors cursor-pointer"
            >
              {AUDIENCE_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          {/* Plan */}
          <div className="flex flex-col gap-1">
            <label htmlFor="filter-plan" className="text-xs font-medium text-zinc-500 uppercase tracking-wide">
              Plan
            </label>
            <input
              id="filter-plan"
              type="text"
              value={filters.plan}
              onChange={handlePlanChange}
              placeholder="ex: enterprise"
              className="rounded border border-zinc-700 bg-zinc-800 px-3 py-1.5 text-sm text-zinc-100 placeholder-zinc-600 outline-none focus:border-zinc-500 transition-colors"
            />
          </div>

          {/* Clear button */}
          {activeCount > 0 ? (
            <div className="sm:col-span-3 flex justify-end">
              <button
                onClick={handleClear}
                className="text-xs text-zinc-500 hover:text-zinc-300 underline underline-offset-2 transition-colors"
              >
                Limpar filtros
              </button>
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}
