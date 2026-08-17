import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Bot, MessageSquarePlus, Plus, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import Modal, { ErrorBanner, inputClass } from '../components/Modal'
import SessionComposer from '../components/SessionComposer'

export default function AgentsPage() {
  const queryClient = useQueryClient()
  const [creating, setCreating] = useState(false)
  const [chatAgent, setChatAgent] = useState<string | null>(null)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [source, setSource] = useState('')
  const [sourcePath, setSourcePath] = useState('')
  const agents = useQuery({ queryKey: ['agents'], queryFn: () => api.get('/api/agents').then((r) => r.data) })
  const create = useMutation({ mutationFn: () => api.post('/api/agents', { name, description: description || null, source: source === 'custom' ? sourcePath : source || null }), onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['agents'] }); setCreating(false); setName(''); setDescription(''); setSource(''); setSourcePath('') } })
  const remove = useMutation({ mutationFn: (id: string) => api.delete(`/api/agents/${id}`), onSuccess: () => queryClient.invalidateQueries({ queryKey: ['agents'] }) })
  return <div className="p-8">
    <div className="mb-6 flex items-end justify-between"><div><h2 className="text-2xl font-bold dark:text-white">Agents</h2><p className="text-gray-500">Identity, prompt, memory, skills and default workspace in one Agent Home.</p></div><button onClick={() => setCreating(true)} className="flex gap-2 rounded-lg bg-primary-600 px-4 py-2 text-white"><Plus className="h-5 w-5" />New agent</button></div>
    <ErrorBanner error={agents.error || remove.error} />
    <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">{agents.data?.map((agent: any) => <div key={agent.id} className="rounded-xl border bg-white p-5 shadow-sm dark:bg-gray-800">
      <Link to={`/agents/${agent.id}`} className="block"><div className="mb-4 flex items-start gap-3"><div className="rounded-xl bg-primary-100 p-3"><Bot className="h-6 w-6 text-primary-600" /></div><div className="min-w-0"><h3 className="font-semibold dark:text-white">{agent.name}</h3><p className="line-clamp-2 text-sm text-gray-500">{agent.description || 'No description yet'}</p></div></div><dl className="space-y-1 text-xs text-gray-500"><div><dt className="inline font-medium">Model: </dt><dd className="inline">{agent.provider && `${agent.provider} / `}{agent.model || 'not configured'}</dd></div><div className="truncate"><dt className="inline font-medium">Home: </dt><dd className="inline font-mono">{agent.home_path || 'bundled'}</dd></div></dl></Link>
      <div className="mt-5 flex gap-2"><button onClick={() => setChatAgent(agent.id)} className="flex flex-1 items-center justify-center gap-2 rounded-lg bg-gray-900 px-3 py-2 text-sm text-white dark:bg-primary-600"><MessageSquarePlus className="h-4 w-4" />Start chat</button>{agent.id !== 'quenda-code' && <button onClick={() => window.confirm(`Delete ${agent.name}?`) && remove.mutate(agent.id)} className="rounded-lg border p-2 text-gray-400 hover:text-red-500"><Trash2 className="h-5 w-5" /></button>}</div>
    </div>)}</div>
    {creating && <Modal title="Create an Agent Home" onClose={() => setCreating(false)}><ErrorBanner error={create.error} /><div className="space-y-4"><label className="block text-sm">Name<input autoFocus value={name} onChange={(e) => setName(e.target.value)} placeholder="reviewer" className={`${inputClass} mt-1`} /></label><label className="block text-sm">Description<input value={description} onChange={(e) => setDescription(e.target.value)} className={`${inputClass} mt-1`} /></label><label className="block text-sm">Seed from<select value={source} onChange={(e) => setSource(e.target.value)} className={`${inputClass} mt-1`}><option value="">Blank personal agent</option><option value="quenda-code">Installed Quenda Code</option><option value="custom">Source directory</option></select></label>{source === 'custom' && <label className="block text-sm">Source directory<input value={sourcePath} onChange={(e) => setSourcePath(e.target.value)} placeholder="/path/to/agent-source" className={`${inputClass} mt-1 font-mono`} /></label>}<div className="flex justify-end gap-3"><button onClick={() => setCreating(false)}>Cancel</button><button disabled={!name || (source === 'custom' && !sourcePath) || create.isPending} onClick={() => create.mutate()} className="rounded-lg bg-primary-600 px-4 py-2 text-white disabled:opacity-50">Create</button></div></div></Modal>}
    {chatAgent && <SessionComposer initialAgentId={chatAgent} onClose={() => setChatAgent(null)} />}
  </div>
}
