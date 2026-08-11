import { useQuery } from '@tanstack/react-query'
import { Plus, FolderOpen, Check } from 'lucide-react'
import { api } from '../api'

export default function WorkspacesPage() {
  const { data: workspaces, isLoading } = useQuery({
    queryKey: ['workspaces'],
    queryFn: () => api.get('/api/workspaces').then((res) => res.data),
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
        <h2 className="text-2xl font-bold text-gray-900 dark:text-white">Workspaces</h2>
        <p className="text-gray-600 dark:text-gray-400 mt-1">
          Manage your project workspaces
        </p>
      </div>

      {/* Create button */}
      <button className="mb-6 flex items-center gap-2 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors">
        <Plus className="w-5 h-5" />
        Create Workspace
      </button>

      {/* Workspace list */}
      <div className="grid gap-4">
        {workspaces?.map((workspace: any) => (
          <div
            key={workspace.id}
            className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-6 hover:shadow-md transition-shadow"
          >
            <div className="flex items-center justify-between">
              <div className="flex items-start gap-4">
                <div className="p-3 bg-primary-100 dark:bg-primary-900 rounded-lg">
                  <FolderOpen className="w-6 h-6 text-primary-600 dark:text-primary-400" />
                </div>
                <div>
                  <h3 className="font-semibold text-gray-900 dark:text-white">
                    {workspace.name}
                  </h3>
                  <p className="text-sm text-gray-600 dark:text-gray-400 font-mono mt-1">
                    {workspace.path}
                  </p>
                  {workspace.description && (
                    <p className="text-sm text-gray-600 dark:text-gray-400 mt-2">
                      {workspace.description}
                    </p>
                  )}
                </div>
              </div>

              {workspace.is_active && (
                <div className="flex items-center gap-2 px-3 py-1 bg-green-100 dark:bg-green-900 text-green-700 dark:text-green-300 rounded-full text-sm">
                  <Check className="w-4 h-4" />
                  Active
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
