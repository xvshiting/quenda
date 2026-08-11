import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { Send, Bot, User } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

export default function ChatPage() {
  const { sessionId } = useParams()
  const [message, setMessage] = useState('')
  const [messages, setMessages] = useState<any[]>([])

  const handleSend = async () => {
    if (!message.trim()) return

    // Add user message
    const userMsg = {
      id: Date.now().toString(),
      role: 'user',
      content: message,
      timestamp: new Date().toISOString(),
    }
    setMessages((prev) => [...prev, userMsg])
    setMessage('')

    // TODO: Send to API
    // For now, add placeholder response
    setTimeout(() => {
      const agentMsg = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: `Received: ${message}\n\n(This is a placeholder response. WebSocket integration pending.)`,
        timestamp: new Date().toISOString(),
      }
      setMessages((prev) => [...prev, agentMsg])
    }, 1000)
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="border-b border-gray-200 dark:border-gray-700 p-4">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
          Session {sessionId}
        </h2>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-auto p-6 space-y-4">
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex gap-3 ${
              msg.role === 'user' ? 'justify-end' : 'justify-start'
            }`}
          >
            {msg.role === 'assistant' && (
              <div className="p-2 bg-primary-100 dark:bg-primary-900 rounded-lg">
                <Bot className="w-5 h-5 text-primary-600 dark:text-primary-400" />
              </div>
            )}

            <div
              className={`max-w-2xl rounded-lg p-4 ${
                msg.role === 'user'
                  ? 'bg-primary-600 text-white'
                  : 'bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700'
              }`}
            >
              <ReactMarkdown
                className={`prose ${
                  msg.role === 'user' ? 'prose-invert' : 'dark:prose-invert'
                }`}
                remarkPlugins={[remarkGfm]}
              >
                {msg.content}
              </ReactMarkdown>
            </div>

            {msg.role === 'user' && (
              <div className="p-2 bg-gray-100 dark:bg-gray-700 rounded-lg">
                <User className="w-5 h-5 text-gray-600 dark:text-gray-400" />
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Input */}
      <div className="border-t border-gray-200 dark:border-gray-700 p-4">
        <div className="flex gap-3">
          <input
            type="text"
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && handleSend()}
            placeholder="Type a message..."
            className="flex-1 px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 dark:bg-gray-800 dark:text-white"
          />
          <button
            onClick={handleSend}
            className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors"
          >
            <Send className="w-5 h-5" />
          </button>
        </div>
      </div>
    </div>
  )
}
