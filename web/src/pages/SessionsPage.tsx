import { useQuery } from '@tanstack/react-query'
import { Plus, MessageSquare, Trash2 } from 'lucide-react'
import { Link } from 'react-router-dom'
import { api } from '../api'

export default function SessionsPage() {
  const { data: sessions, isLoading } = useQuery({
    queryKey: ['sessions'],
    queryFn: () => api.get('/api/sessions').then((res) => res.data),
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
        <h2 className="text-2xl font-bold text-gray-900 dark:text-white">Sessions</h2>
        <p className="text-gray-600 dark:text-gray-400 mt-1">
          Your conversation history
        </p>
      </div>

      {/* Create button */}
      <button className="mb-6 flex items-center gap-2 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors">
        <Plus className="w-5 h-5" />
        New Session
      </button>

      {/* Session list */}
      <div className="grid gap-4">
        {sessions?.map((session: any) => (
          <Link
            key={session.id}
            to={`/sessions/${session.id}`}
            className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-6 hover:shadow-md transition-shadow block"
          >
            <div className="flex items-center justify-between">
              <div className="flex items-start gap-4">
                <div className="p-3 bg-primary-100 dark:bg-primary-900 rounded-lg">
                  <MessageSquare className="w-6 h-6 text-primary-600 dark:text-primary-400" />
                </div>
                <div>
                  <h3 className="font-semibold text-gray-900 dark:text-white">
                    {session.title || `Session ${session.id}`}
                  </h3>
                  <div className="flex items-center gap-4 mt-2 text-sm text-gray-600 dark:text-gray-400">
                    <span>{session.message_count} messages</span>
                    <span>{session.total_tokens} tokens</span>
                    <span>
                      {new Date(session.updated_at).toLocaleDateString()}
                    </span>
                  </div>
                </div>
              </div>

              <button
                onClick={(e) => {
                  e.preventDefault()
                  // TODO: Delete session
                }}
                className="p-2 text-gray-400 hover:text-red-500 transition-colors"
              >
                <Trash2 className="w-5 h-5" />
              </button>
            </div>
          </Link>
        ))}
      </div>
    </div>
  )
}
