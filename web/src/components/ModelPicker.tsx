import { useQuery } from '@tanstack/react-query'
import { ChevronDown, Eye, Search, Wrench } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { api } from '../api'

type Props = {
  provider?: string | null
  model?: string | null
  onChange: (provider: string | null, model: string | null) => void
  allowDefault?: boolean
  className?: string
}

export default function ModelPicker({ provider, model, onChange, allowDefault = true, className = '' }: Props) {
  const [open, setOpen] = useState(false)
  const [search, setSearch] = useState('')
  const root = useRef<HTMLDivElement>(null)
  const trigger = useRef<HTMLButtonElement>(null)
  const models = useQuery({ queryKey: ['models'], queryFn: () => api.get('/api/models').then((response) => response.data), staleTime: 60_000 })
  const filtered = useMemo(() => {
    const query = search.trim().toLowerCase()
    return (models.data || []).filter((item: any) => !query || `${item.provider_name} ${item.provider_id} ${item.model_name} ${item.model_id}`.toLowerCase().includes(query)).slice(0, 100)
  }, [models.data, search])
  const current = (models.data || []).find((item: any) => item.provider_id === provider && item.model_id === model)

  useEffect(() => {
    if (!open) return
    const closeOutside = (event: Event) => {
      if (!root.current?.contains(event.target as Node)) setOpen(false)
    }
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setOpen(false)
        trigger.current?.focus()
      }
    }
    document.addEventListener('pointerdown', closeOutside, true)
    document.addEventListener('mousedown', closeOutside, true)
    document.addEventListener('click', closeOutside, true)
    document.addEventListener('keydown', closeOnEscape)
    return () => {
      document.removeEventListener('pointerdown', closeOutside, true)
      document.removeEventListener('mousedown', closeOutside, true)
      document.removeEventListener('click', closeOutside, true)
      document.removeEventListener('keydown', closeOnEscape)
    }
  }, [open])

  return <div ref={root} className={`relative ${className}`}>
    <button ref={trigger} type="button" aria-haspopup="listbox" aria-expanded={open} onClick={() => setOpen((value) => !value)} className="flex h-7 min-w-0 max-w-44 items-center gap-1.5 rounded-md border border-gray-200 bg-white px-2 text-left text-[11px] shadow-sm transition hover:border-primary-300 dark:border-gray-700 dark:bg-gray-900 dark:text-white sm:max-w-56">
      <span className="min-w-0 flex-1 truncate font-medium">{current?.model_name || model || 'Default model'}</span>{provider && <span className="hidden max-w-20 truncate text-[9px] text-gray-400 sm:block">{current?.provider_name || provider}</span>}<ChevronDown className={`h-3 w-3 shrink-0 text-gray-400 transition ${open ? 'rotate-180' : ''}`} />
    </button>
    {open && <div role="listbox" className="absolute right-0 z-[100] mt-1.5 w-[min(25rem,calc(100vw-1.5rem))] rounded-xl border border-gray-200 bg-white p-2.5 shadow-2xl ring-1 ring-black/5 dark:border-gray-700 dark:bg-gray-800">
      <div className="flex items-center gap-2 rounded-lg border px-2.5"><Search className="h-3.5 w-3.5 text-gray-400" /><input autoFocus value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search model or provider" className="w-full bg-transparent py-1.5 text-xs outline-none dark:text-white" /></div>
      <div className="mt-2 max-h-80 space-y-1 overflow-auto">
        {allowDefault && <button type="button" role="option" onClick={() => { onChange(null, null); setOpen(false) }} className="w-full rounded-lg px-2.5 py-1.5 text-left hover:bg-gray-100 dark:hover:bg-gray-700"><strong className="block text-xs dark:text-white">Agent default model</strong><span className="text-[11px] text-gray-500">Follow config.yaml</span></button>}
        {filtered.map((item: any) => <button type="button" role="option" aria-selected={item.provider_id === provider && item.model_id === model} key={`${item.provider_id}/${item.model_id}`} onClick={() => { onChange(item.provider_id, item.model_id); setOpen(false) }} className={`flex w-full items-center gap-3 rounded-lg px-2.5 py-1.5 text-left hover:bg-gray-100 dark:hover:bg-gray-700 ${item.provider_id === provider && item.model_id === model ? 'bg-primary-50 ring-1 ring-primary-200 dark:bg-primary-950/40' : ''}`}><span className="min-w-0 flex-1"><strong className="block truncate text-xs dark:text-white">{item.model_name}</strong><span className="block truncate text-[11px] text-gray-500">{item.provider_name} · {item.provider_id}/{item.model_id}</span></span><span className="flex gap-1 text-gray-400">{item.vision && <span title="Vision"><Eye className="h-3.5 w-3.5" /></span>}{item.tool_calling && <span title="Tool calling"><Wrench className="h-3.5 w-3.5" /></span>}</span></button>)}
        {filtered.length === 0 && <p className="p-4 text-center text-sm text-gray-500">No matching models.</p>}
      </div>
      {(models.data?.length || 0) > 100 && !search && <p className="mt-2 text-center text-[11px] text-gray-400">Type to search all {models.data.length} models</p>}
    </div>}
  </div>
}
