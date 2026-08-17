import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Check, FolderOpen, Plus, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { api } from '../api'
import Modal, { ErrorBanner, inputClass } from '../components/Modal'

export default function WorkspacesPage() {
  const queryClient = useQueryClient()
  const [creating, setCreating] = useState(false)
  const [name, setName] = useState('')
  const [path, setPath] = useState('')
  const [description, setDescription] = useState('')
  const workspaces = useQuery({ queryKey: ['workspaces'], queryFn: () => api.get('/api/workspaces').then((r) => r.data) })
  const refresh = () => queryClient.invalidateQueries({ queryKey: ['workspaces'] })
  const create = useMutation({ mutationFn: () => api.post('/api/workspaces', { name, path: path || null, description: description || null }), onSuccess: () => { refresh(); setCreating(false); setName(''); setPath(''); setDescription('') } })
  const activate = useMutation({ mutationFn: (id: string) => api.post(`/api/workspaces/${id}/activate`), onSuccess: refresh })
  const remove = useMutation({ mutationFn: (id: string) => api.delete(`/api/workspaces/${id}`), onSuccess: refresh })
  return <div className="p-8"><div className="mb-6 flex items-end justify-between"><div><h2 className="text-2xl font-bold dark:text-white">Workspaces</h2><p className="text-gray-500">Register projects once, then choose them by name when starting a session.</p></div><button onClick={() => setCreating(true)} className="flex gap-2 rounded-lg bg-primary-600 px-4 py-2 text-white"><Plus className="h-5 w-5" />Add workspace</button></div>
    <ErrorBanner error={workspaces.error || activate.error || remove.error} /><div className="grid gap-4">{workspaces.data?.map((workspace: any) => <div key={workspace.id} className="flex items-center justify-between rounded-xl border bg-white p-5 dark:bg-gray-800"><button onClick={() => activate.mutate(workspace.id)} className="flex min-w-0 flex-1 items-start gap-4 text-left"><div className="rounded-xl bg-amber-100 p-3"><FolderOpen className="h-6 w-6 text-amber-600" /></div><span className="min-w-0"><strong className="dark:text-white">{workspace.name}</strong><span className="block truncate font-mono text-sm text-gray-500">{workspace.path}</span><span className="block text-sm text-gray-400">{workspace.description || 'No description'}</span></span></button><div className="flex items-center gap-3">{workspace.is_active && <span className="flex items-center gap-1 rounded-full bg-green-50 px-3 py-1 text-sm text-green-700"><Check className="h-4 w-4" />Active</span>}<button onClick={() => window.confirm('Remove this registration? Files stay untouched.') && remove.mutate(workspace.id)} className="rounded-lg p-2 text-gray-400 hover:text-red-500"><Trash2 className="h-5 w-5" /></button></div></div>)}</div>
    {creating && <Modal title="Register a workspace" onClose={() => setCreating(false)}><ErrorBanner error={create.error} /><div className="space-y-4"><label className="block text-sm">Name<input value={name} onChange={(e) => setName(e.target.value)} className={`${inputClass} mt-1`} /></label><label className="block text-sm">Directory path<input value={path} onChange={(e) => setPath(e.target.value)} placeholder="/path/to/project" className={`${inputClass} mt-1 font-mono`} /></label><label className="block text-sm">Description<textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={3} className={`${inputClass} mt-1`} /></label><p className="text-xs text-gray-500">If the directory does not exist, Quenda will create it. Removing a workspace never deletes its files.</p><div className="flex justify-end gap-3"><button onClick={() => setCreating(false)}>Cancel</button><button disabled={!name || create.isPending} onClick={() => create.mutate()} className="rounded-lg bg-primary-600 px-4 py-2 text-white disabled:opacity-50">Register</button></div></div></Modal>}
  </div>
}
