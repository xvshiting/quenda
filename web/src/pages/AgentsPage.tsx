import { useQuery } from '@tanstack/react-query'
import { Plus, Bot } from 'lucide-react'
import { api } from '../api'

export default function AgentsPage() {
  const { data: agents, isLoading } = useQuery({
    queryKey: ['agents'],
    queryFn: () => api.get('/api/agents').then((res) => res.data),
  })

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-gray-500">Loading...</div>
      </div>
    )
  }

  return (
    <div className="p-8">
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-gray-900 dark:text-white">Agents</h2>
        <p className="text-gray-600 dark:text-gray-400 mt-1">
          Manage your AI agents
        </p>
      </div>

      {/* Create button */}
      <button className="mb-6 flex items-center gap-2 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors">
        <Plus className="w-5 h-5" />
        Create Agent
      </button>

      {/* Agent list */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {agents?.map((agent: any) => (
          <div
            key={agent.id}
            className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-6 hover:shadow-md transition-shadow cursor-pointer"
          >
            <div className="flex items-start gap-4">
              <div className="p-3 bg-primary-100 dark:bg-primary-900 rounded-lg">
                <Bot className="w-6 h-6 text-primary-600 dark:text-primary-400" />
              </div>
              <div className="flex-1">
                <h3 className="font-semibold text-gray-900 dark:text-white">
                  {agent.name}
                </h3>
                {agent.description && (
                  <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
                    {agent.description}
                  </p>
                )}
                <div className="flex items-center gap-4 mt-3 text-xs text-gray-500 dark:text-gray-400">
                  {agent.model && (
                    <span className="px-2 py-1 bg-gray-100 dark:bg-gray-700 rounded">
                      {agent.model}
                    </span>
                  )}
                  <span>{agent.tool_count} tools</span>
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
