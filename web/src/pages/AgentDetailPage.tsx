import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, MessageSquarePlus, Save } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api'
import { ErrorBanner, inputClass } from '../components/Modal'
import SessionComposer from '../components/SessionComposer'

export default function AgentDetailPage() {
  const { agentId = '' } = useParams()
  const queryClient = useQueryClient()
  const [chat, setChat] = useState(false)
  const [description, setDescription] = useState('')
  const [prompt, setPrompt] = useState('')
  const [config, setConfig] = useState('')
  const agent = useQuery({ queryKey: ['agent', agentId], queryFn: () => api.get(`/api/agents/${agentId}`).then((r) => r.data) })
  const sessions = useQuery({ queryKey: ['sessions', agentId], queryFn: () => api.get('/api/sessions', { params: { agent_id: agentId } }).then((r) => r.data) })
  useEffect(() => { if (agent.data) { setDescription(agent.data.description || ''); setPrompt(agent.data.system_prompt || ''); setConfig(agent.data.config_yaml || '') } }, [agent.data])
  const save = useMutation({ mutationFn: () => api.put(`/api/agents/${agentId}`, { description, system_prompt: prompt, config_yaml: config }), onSuccess: () => queryClient.invalidateQueries({ queryKey: ['agent', agentId] }) })
  if (agent.isLoading) return <div className="p-8 text-gray-500">Loading agent…</div>
  if (!agent.data) return <div className="p-8"><ErrorBanner error={agent.error || new Error('Agent not found')} /></div>
  return <div className="p-8"><Link to="/agents" className="mb-5 inline-flex items-center gap-2 text-sm text-gray-500"><ArrowLeft className="h-4 w-4" />Agents</Link>
    <div className="mb-8 flex items-start justify-between"><div><h2 className="text-3xl font-bold dark:text-white">{agent.data.name}</h2><p className="mt-1 font-mono text-sm text-gray-500">{agent.data.home_path}</p></div><button onClick={() => setChat(true)} className="flex gap-2 rounded-lg bg-primary-600 px-4 py-2 text-white"><MessageSquarePlus className="h-5 w-5" />Start session</button></div>
    <ErrorBanner error={save.error} /><div className="grid gap-6 xl:grid-cols-[minmax(0,2fr)_minmax(280px,1fr)]"><div className="space-y-5 rounded-xl border bg-white p-6 dark:bg-gray-800"><label className="block text-sm font-medium">Description<input value={description} onChange={(e) => setDescription(e.target.value)} className={`${inputClass} mt-1`} /></label><label className="block text-sm font-medium">System prompt<textarea value={prompt} onChange={(e) => setPrompt(e.target.value)} rows={12} className={`${inputClass} mt-1 font-mono text-sm`} /></label><label className="block text-sm font-medium">config.yaml<textarea value={config} onChange={(e) => setConfig(e.target.value)} rows={12} className={`${inputClass} mt-1 font-mono text-sm`} /></label><button onClick={() => save.mutate()} disabled={save.isPending} className="flex gap-2 rounded-lg bg-gray-900 px-4 py-2 text-white"><Save className="h-4 w-4" />Save changes</button></div>
      <aside className="space-y-5"><section className="rounded-xl border bg-white p-5 dark:bg-gray-800"><h3 className="font-semibold dark:text-white">Runtime</h3><dl className="mt-3 space-y-2 text-sm text-gray-500"><div><dt>Provider</dt><dd className="font-mono text-gray-900 dark:text-white">{agent.data.provider || 'Not configured'}</dd></div><div><dt>Model</dt><dd className="font-mono text-gray-900 dark:text-white">{agent.data.model || 'Not configured'}</dd></div><div><dt>Default workspace</dt><dd className="break-all font-mono text-xs">{agent.data.workspace_path || 'Select one when starting a session'}</dd></div></dl></section><section className="rounded-xl border bg-white p-5 dark:bg-gray-800"><h3 className="font-semibold dark:text-white">Recent sessions</h3><div className="mt-3 space-y-2">{sessions.data?.slice(0, 6).map((session: any) => <Link key={session.id} to={`/sessions/${session.id}`} className="block rounded-lg bg-gray-50 p-3 text-sm hover:bg-gray-100 dark:bg-gray-900"><strong className="dark:text-white">{session.title}</strong><span className="block text-xs text-gray-500">{session.workspace_name || 'Default workspace'} · {session.message_count} messages</span></Link>)}{sessions.data?.length === 0 && <p className="text-sm text-gray-500">No sessions yet.</p>}</div></section></aside></div>
    {chat && <SessionComposer initialAgentId={agentId} onClose={() => setChat(false)} />}
  </div>
}
