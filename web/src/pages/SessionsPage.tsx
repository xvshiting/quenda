import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { MessageSquare, Plus, Search, Trash2 } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import { ErrorBanner, inputClass } from '../components/Modal'
import SessionComposer from '../components/SessionComposer'

export default function SessionsPage() {
  const queryClient = useQueryClient()
  const [creating, setCreating] = useState(false)
  const [query, setQuery] = useState('')
  const [agentFilter, setAgentFilter] = useState('')
  const [workspaceFilter, setWorkspaceFilter] = useState('')
  const sessions = useQuery({ queryKey: ['sessions'], queryFn: () => api.get('/api/sessions').then((r) => r.data) })
  const agents = useQuery({ queryKey: ['agents'], queryFn: () => api.get('/api/agents').then((r) => r.data) })
  const workspaces = useQuery({ queryKey: ['workspaces'], queryFn: () => api.get('/api/workspaces').then((r) => r.data) })
  const remove = useMutation({ mutationFn: (id: string) => api.delete(`/api/sessions/${id}`), onSuccess: () => queryClient.invalidateQueries({ queryKey: ['sessions'] }) })
  const visible = useMemo(() => (sessions.data || []).filter((session: any) => (!agentFilter || session.agent_id === agentFilter) && (!workspaceFilter || session.workspace_id === workspaceFilter) && (!query || `${session.title} ${session.agent_name} ${session.workspace_name}`.toLowerCase().includes(query.toLowerCase()))), [sessions.data, query, agentFilter, workspaceFilter])
  return <div className="p-8"><div className="mb-6 flex items-end justify-between"><div><h2 className="text-2xl font-bold dark:text-white">Sessions</h2><p className="text-gray-500">Resume conversations and understand where each agent is working.</p></div><button onClick={() => setCreating(true)} className="flex gap-2 rounded-lg bg-primary-600 px-4 py-2 text-white"><Plus className="h-5 w-5" />New session</button></div>
    <ErrorBanner error={sessions.error || remove.error} /><div className="mb-6 grid gap-3 rounded-xl border bg-white p-4 md:grid-cols-[1fr_220px_260px] dark:bg-gray-800"><label className="relative"><Search className="absolute left-3 top-2.5 h-5 w-5 text-gray-400" /><input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search sessions" className={`${inputClass} pl-10`} /></label><select value={agentFilter} onChange={(e) => setAgentFilter(e.target.value)} className={inputClass}><option value="">All agents</option>{agents.data?.map((agent: any) => <option key={agent.id} value={agent.id}>{agent.name}</option>)}</select><select value={workspaceFilter} onChange={(e) => setWorkspaceFilter(e.target.value)} className={inputClass}><option value="">All workspaces</option>{workspaces.data?.map((workspace: any) => <option key={workspace.id} value={workspace.id}>{workspace.name}</option>)}</select></div>
    <div className="space-y-3">{visible.map((session: any) => <Link key={session.id} to={`/sessions/${session.id}`} className="flex items-center justify-between rounded-xl border bg-white p-5 shadow-sm hover:border-primary-300 dark:bg-gray-800"><div className="flex min-w-0 gap-4"><div className="rounded-xl bg-primary-100 p-3"><MessageSquare className="h-5 w-5 text-primary-600" /></div><div className="min-w-0"><h3 className="font-semibold dark:text-white">{session.title}</h3><p className="truncate text-sm text-gray-500">{session.agent_name} · {session.workspace_name || 'Default workspace'} · {session.workspace_path}</p><p className="mt-1 text-xs text-gray-400">{session.message_count} messages · {new Date(session.updated_at).toLocaleString()}</p></div></div><button onClick={(event) => { event.preventDefault(); if (window.confirm('Delete this session and its Web history?')) remove.mutate(session.id) }} className="rounded-lg p-2 text-gray-400 hover:bg-red-50 hover:text-red-500"><Trash2 className="h-5 w-5" /></button></Link>)}{!sessions.isLoading && visible.length === 0 && <div className="rounded-xl border border-dashed p-12 text-center text-gray-500">No matching sessions. Start one from here or from an Agent page.</div>}</div>
    {creating && <SessionComposer onClose={() => setCreating(false)} />}
  </div>
}
