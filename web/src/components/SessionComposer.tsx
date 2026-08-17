import { useMutation, useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'
import Modal, { ErrorBanner, inputClass } from './Modal'
import ModelPicker from './ModelPicker'

export default function SessionComposer({ initialAgentId = '', onClose }: { initialAgentId?: string; onClose: () => void }) {
  const navigate = useNavigate()
  const [agentId, setAgentId] = useState(initialAgentId)
  const [workspaceId, setWorkspaceId] = useState('')
  const [title, setTitle] = useState('')
  const [selectedModel, setSelectedModel] = useState('')
  const agents = useQuery({ queryKey: ['agents'], queryFn: () => api.get('/api/agents').then((r) => r.data) })
  const workspaces = useQuery({ queryKey: ['workspaces'], queryFn: () => api.get('/api/workspaces').then((r) => r.data) })
  const create = useMutation({
    mutationFn: () => { const [provider, model] = selectedModel.split('\u0000'); return api.post('/api/sessions', { agent_id: agentId, workspace_id: workspaceId || null, title: title || null, provider: provider || null, model: model || null }).then((r) => r.data) },
    onSuccess: (session) => navigate(`/sessions/${session.id}`),
  })
  return <Modal title="Start a conversation" onClose={onClose}>
    <ErrorBanner error={agents.error || workspaces.error || create.error} />
    <div className="space-y-4">
      <label className="block text-sm font-medium text-gray-700 dark:text-gray-200">Agent<select value={agentId} onChange={(e) => setAgentId(e.target.value)} className={`${inputClass} mt-1`}><option value="">Choose an agent…</option>{agents.data?.map((agent: any) => <option key={agent.id} value={agent.id}>{agent.name}</option>)}</select></label>
      <label className="block text-sm font-medium text-gray-700 dark:text-gray-200">Workspace<select value={workspaceId} onChange={(e) => setWorkspaceId(e.target.value)} className={`${inputClass} mt-1`}><option value="">Agent default workspace</option>{workspaces.data?.map((workspace: any) => <option key={workspace.id} value={workspace.id}>{workspace.name} — {workspace.path}</option>)}</select></label>
      <label className="block text-sm font-medium text-gray-700 dark:text-gray-200">Model<ModelPicker className="mt-1" provider={selectedModel.split('\u0000')[0] || null} model={selectedModel.split('\u0000')[1] || null} onChange={(provider, model) => setSelectedModel(provider && model ? `${provider}\u0000${model}` : '')} /></label>
      <label className="block text-sm font-medium text-gray-700 dark:text-gray-200">Title<input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Optional conversation title" className={`${inputClass} mt-1`} /></label>
      <div className="rounded-lg bg-blue-50 p-3 text-sm text-blue-700">Without a selected workspace, the conversation runs in the Agent Home's default workspace.</div>
      <div className="flex justify-end gap-3"><button onClick={onClose} className="rounded-lg px-4 py-2 text-gray-600">Cancel</button><button disabled={!agentId || create.isPending} onClick={() => create.mutate()} className="rounded-lg bg-primary-600 px-4 py-2 text-white disabled:opacity-50">{create.isPending ? 'Creating…' : 'Create and open'}</button></div>
    </div>
  </Modal>
}
