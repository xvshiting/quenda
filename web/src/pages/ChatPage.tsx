import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Activity,
  Bot,
  Check,
  ChevronRight,
  File as FileIcon,
  PanelRightClose,
  PanelRightOpen,
  Paperclip,
  Pencil,
  Send,
  Square,
  Sparkles,
  User,
  Video,
  X,
} from 'lucide-react'
import { ChangeEvent, Fragment, useEffect, useRef, useState } from 'react'
import { useParams } from 'react-router-dom'
import { api } from '../api'
import MessageContent, { MessageSurface } from '../components/MessageContent'
import ModelPicker from '../components/ModelPicker'
import { shouldSendFromKeyboard } from '../utils/chatKeyboard'

type PendingFile = { file: File; preview?: string }
type ActivityItem = {
  id: string
  run_id?: string
  type: string
  title: string
  summary?: string
  status: string
  created_at: string
  duration_ms?: number
  detail?: Record<string, unknown>
}
type MessageItem = {
  id: string
  role: string
  content: string
  created_at: string
  tokens?: number
  input_tokens?: number
  output_tokens?: number
  duration_ms?: number
  attachments?: any[]
}
type InteractionOption = { id: string; label: string; description?: string; is_default?: boolean }
type InteractionQuestion = {
  id: string
  kind?: string
  title?: string
  header?: string
  message?: string
  question?: string
  options?: InteractionOption[]
  multiple?: boolean
  required?: boolean
  default_option_id?: string
}
type InteractionItem = {
  id: string
  kind: string
  title: string
  message?: string
  options: InteractionOption[]
  questions: InteractionQuestion[]
  multiple: boolean
  required: boolean
  default_option_id?: string
  status: string
  created_at: string
}
type InteractionAnswer = { question_id: string; selected_option_ids: string[]; value?: string }

const fileToBase64 = (file: File) => new Promise<string>((resolve, reject) => {
  const reader = new FileReader()
  reader.onload = () => resolve(String(reader.result).split(',', 2)[1] || '')
  reader.onerror = () => reject(reader.error)
  reader.readAsDataURL(file)
})

const formatTime = (value: string) => new Intl.DateTimeFormat(undefined, {
  hour: '2-digit', minute: '2-digit', second: '2-digit',
}).format(new Date(value))

const formatDuration = (duration?: number | null) => {
  if (!duration) return ''
  return duration < 1000 ? `${duration} ms` : `${(duration / 1000).toFixed(duration < 10_000 ? 1 : 0)} s`
}

const activityColor = (item: ActivityItem) => item.status === 'error'
  ? 'bg-red-500'
  : item.status === 'needs_input'
    ? 'bg-amber-500'
    : item.type.startsWith('tool')
      ? 'bg-violet-500'
      : item.type.startsWith('model')
        ? 'bg-blue-500'
        : 'bg-emerald-500'

function AttachmentView({ sessionId, attachment }: { sessionId?: string; attachment: any }) {
  const url = `/api/sessions/${sessionId}/attachments/${attachment.id}`
  if (attachment.media_type.startsWith('image/')) {
    return <a href={url} target="_blank" rel="noreferrer" className="group mt-3 block overflow-hidden rounded-xl border border-black/10 bg-black/5 dark:border-white/10"><img src={url} alt={attachment.name} className="max-h-96 w-full object-contain transition duration-200 group-hover:scale-[1.01]" /><span className="flex items-center justify-between border-t border-black/10 px-3 py-2 text-xs opacity-70 dark:border-white/10"><span className="truncate">{attachment.name}</span><span>{Math.ceil(attachment.size / 1024)} KB · open</span></span></a>
  }
  if (attachment.media_type.startsWith('video/')) {
    return <div className="mt-3 overflow-hidden rounded-xl border border-black/10 dark:border-white/10"><video src={url} controls className="max-h-96 w-full bg-black">Your browser cannot preview this video.</video><div className="px-3 py-2 text-xs opacity-70">{attachment.name} · {Math.ceil(attachment.size / 1024)} KB</div></div>
  }
  return <a href={url} download={attachment.name} className="group mt-3 flex items-center gap-3 rounded-xl border border-black/10 bg-black/[0.025] px-3 py-2.5 text-sm transition hover:border-primary-300 hover:bg-primary-50/50 dark:border-white/10 dark:bg-white/[0.03] dark:hover:bg-primary-950/30"><span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-white shadow-sm dark:bg-gray-900"><FileIcon className="h-4 w-4 text-primary-600" /></span><span className="min-w-0 flex-1"><strong className="block truncate text-sm">{attachment.name}</strong><span className="block text-[11px] opacity-60">{attachment.media_type} · {Math.ceil(attachment.size / 1024)} KB</span></span><span className="text-xs font-medium text-primary-600">下载</span></a>
}

function ActivityList({ activities, selectedId, idPrefix = 'activity' }: { activities: ActivityItem[]; selectedId?: string; idPrefix?: string }) {
  return <div className="space-y-2">{activities.slice().reverse().map((item) => <details
    id={`${idPrefix}-${item.id}`}
    key={item.id}
    open={item.id === selectedId || undefined}
    className={`group scroll-mt-4 rounded-xl border bg-white p-3 transition dark:bg-gray-800 ${item.id === selectedId ? 'border-primary-400 ring-2 ring-primary-100' : 'border-gray-200 dark:border-gray-700'}`}
  >
    <summary className="cursor-pointer list-none">
      <div className="flex items-start gap-2.5">
        <span className={`mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full ${activityColor(item)}`} />
        <div className="min-w-0 flex-1">
          <strong className="block truncate text-sm text-gray-800 dark:text-white">{item.title}</strong>
          <span className="mt-0.5 block text-xs leading-5 text-gray-500">{item.summary || item.type.replace(/_/g, ' ')}</span>
          <span className="mt-1 block text-[10px] text-gray-400">{formatTime(item.created_at)}{item.duration_ms ? ` · ${formatDuration(item.duration_ms)}` : ''}</span>
        </div>
        <ChevronRight className="mt-1 h-4 w-4 shrink-0 text-gray-400 transition group-open:rotate-90" />
      </div>
    </summary>
    <pre className="mt-3 max-h-80 overflow-auto whitespace-pre-wrap break-all rounded-lg bg-gray-950 p-3 text-[11px] text-gray-200">{JSON.stringify(item.detail, null, 2)}</pre>
  </details>)}{activities.length === 0 && <div className="rounded-xl border border-dashed p-5 text-center text-sm leading-6 text-gray-500">Model calls, routing decisions and tool results will appear here.</div>}</div>
}

function ActivityPanel({ activities, selectedId, onHide }: { activities: ActivityItem[]; selectedId?: string; onHide: () => void }) {
  return <aside className="hidden w-[22rem] shrink-0 flex-col border-l bg-gray-50/90 xl:flex dark:bg-gray-900">
    <div className="flex items-center justify-between border-b px-4 py-3">
      <div><h3 className="flex items-center gap-2 font-semibold dark:text-white"><Activity className="h-4 w-4 text-primary-600" />Activity</h3><p className="mt-0.5 text-[11px] text-gray-400">Live model and tool trace</p></div>
      <div className="flex items-center gap-2"><span className="rounded-full bg-gray-200 px-2 py-0.5 text-xs text-gray-600 dark:bg-gray-700 dark:text-gray-300">{activities.length}</span><button type="button" title="Hide activity panel" onClick={onHide} className="rounded-lg p-2 text-gray-400 transition hover:bg-gray-200 dark:hover:bg-gray-800"><PanelRightClose className="h-4 w-4" /></button></div>
    </div>
    <div className="flex-1 overflow-auto p-4"><ActivityList activities={activities} selectedId={selectedId} /></div>
  </aside>
}

function InlineActivity({ activities, running, onSelect }: { activities: ActivityItem[]; running?: boolean; onSelect: (id: string) => void }) {
  if (activities.length === 0 && !running) return null
  const latest = activities[activities.length - 1]
  return <details className="group mx-auto my-3 w-full max-w-3xl rounded-xl border border-gray-200 bg-white/70 shadow-sm backdrop-blur dark:border-gray-700 dark:bg-gray-800/70">
    <summary className="flex cursor-pointer list-none items-center gap-3 px-4 py-2.5 text-sm">
      <span className={`h-2.5 w-2.5 shrink-0 rounded-full ${latest ? activityColor(latest) : 'animate-pulse bg-primary-500'}`} />
      <span className="min-w-0 flex-1 truncate text-gray-600 dark:text-gray-300">{latest ? latest.summary || latest.title : 'Starting agent…'}</span>
      {running && <span className="text-[11px] font-medium text-primary-600">Working</span>}
      <span className="text-[11px] text-gray-400">{activities.length} activit{activities.length === 1 ? 'y' : 'ies'}</span>
      <ChevronRight className="h-4 w-4 text-gray-400 transition group-open:rotate-90" />
    </summary>
    <div className="border-t px-2 py-2">{activities.map((item) => <button key={item.id} type="button" onClick={() => onSelect(item.id)} className="flex w-full items-start gap-3 rounded-lg px-2 py-2 text-left transition hover:bg-gray-100 dark:hover:bg-gray-700">
      <span className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${activityColor(item)}`} />
      <span className="min-w-0 flex-1"><strong className="block truncate text-xs font-medium text-gray-700 dark:text-gray-200">{item.title}</strong><span className="block truncate text-xs text-gray-500">{item.summary || item.type.replace(/_/g, ' ')}</span></span>
      <span className="shrink-0 text-[10px] text-gray-400">{item.duration_ms ? formatDuration(item.duration_ms) : formatTime(item.created_at)}</span>
    </button>)}</div>
  </details>
}

function MessageBubble({ item, sessionId }: { item: MessageItem; sessionId?: string }) {
  const isUser = item.role === 'user'
  return <div className={`mx-auto flex w-full max-w-5xl gap-3 ${isUser ? 'justify-end' : 'justify-start'}`}>
    {!isUser && <div className="mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-primary-100 text-primary-700 dark:bg-primary-950"><Bot className="h-4 w-4" /></div>}
    <div className={`min-w-0 ${isUser ? 'max-w-[min(42rem,84%)]' : 'max-w-[min(54rem,90%)]'}`}>
      <MessageSurface><div className={`rounded-[1.25rem] px-5 py-4 shadow-sm sm:px-6 sm:py-5 ${isUser ? 'rounded-tr-md bg-primary-600 text-white shadow-primary-900/10' : 'rounded-tl-md border border-slate-200/90 bg-white text-slate-700 shadow-slate-900/[0.045] ring-1 ring-slate-900/[0.015] dark:border-slate-700 dark:bg-gray-800 dark:text-slate-200'}`}>
        {item.content && <MessageContent content={item.content} isUser={isUser} />}
        {item.attachments?.map((attachment) => <AttachmentView key={attachment.id} sessionId={sessionId} attachment={attachment} />)}
      </div></MessageSurface>
      <div className={`mt-1 flex flex-wrap items-center gap-x-2 px-1 text-[10px] text-gray-400 ${isUser ? 'justify-end' : 'justify-start'}`}>
        <span>{formatTime(item.created_at)}</span>
        {item.input_tokens != null && <span title="Input tokens"><span className="text-gray-300 dark:text-gray-600">输入</span> {item.input_tokens.toLocaleString()}</span>}
        {item.output_tokens != null && <span title="Output tokens"><span className="text-gray-300 dark:text-gray-600">输出</span> {item.output_tokens.toLocaleString()}</span>}
        {!!item.duration_ms && <span>{formatDuration(item.duration_ms)}</span>}
      </div>
    </div>
    {isUser && <div className="mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-gray-200 text-gray-600 dark:bg-gray-700 dark:text-gray-200"><User className="h-4 w-4" /></div>}
  </div>
}

function InteractionCard({ interaction, pending, onSubmit }: { interaction: InteractionItem; pending: boolean; onSubmit: (answers: InteractionAnswer[]) => void }) {
  const questions: InteractionQuestion[] = interaction.questions.length > 0
    ? interaction.questions
    : [{ id: interaction.id, kind: interaction.kind, title: interaction.title, message: interaction.message, options: interaction.options, multiple: interaction.multiple, required: interaction.required, default_option_id: interaction.default_option_id }]
  const initialSelections = Object.fromEntries(questions.map((question) => {
    const defaultId = question.default_option_id || question.options?.find((option) => option.is_default)?.id
    return [question.id, defaultId ? [defaultId] : []]
  }))
  const [selections, setSelections] = useState<Record<string, string[]>>(initialSelections)
  const [values, setValues] = useState<Record<string, string>>({})
  const toggle = (question: InteractionQuestion, optionId: string) => setSelections((current) => {
    const selected = current[question.id] || []
    if (!question.multiple) return { ...current, [question.id]: [optionId] }
    return { ...current, [question.id]: selected.includes(optionId) ? selected.filter((id) => id !== optionId) : [...selected, optionId] }
  })
  const complete = questions.every((question) => question.required === false || (question.kind === 'input' ? !!values[question.id]?.trim() : (selections[question.id]?.length || 0) > 0))
  const submit = () => onSubmit(questions.map((question) => ({ question_id: question.id, selected_option_ids: selections[question.id] || [], value: values[question.id]?.trim() || undefined })))

  return <section className="mx-auto w-full max-w-3xl overflow-hidden rounded-2xl border border-amber-200 bg-white shadow-lg shadow-amber-100/50 dark:border-amber-800 dark:bg-gray-800 dark:shadow-none">
    <div className="border-b border-amber-100 bg-amber-50 px-5 py-4 dark:border-amber-900 dark:bg-amber-950/40">
      <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-amber-700 dark:text-amber-400"><span className="h-2 w-2 animate-pulse rounded-full bg-amber-500" />Agent needs your input</div>
      <h3 className="mt-1 text-lg font-semibold text-gray-900 dark:text-white">{interaction.title}</h3>
      {interaction.message && <p className="mt-1 text-sm leading-6 text-gray-600 dark:text-gray-300">{interaction.message}</p>}
    </div>
    <div className="space-y-5 p-5">{questions.map((question, index) => {
      const kind = question.kind || interaction.kind
      const options = question.options || []
      return <fieldset key={question.id} className="space-y-3">
        <legend className="text-sm font-semibold text-gray-800 dark:text-gray-100">{questions.length > 1 && <span className="mr-2 text-xs text-gray-400">{index + 1}/{questions.length}</span>}{question.title || question.header || (questions.length > 1 ? 'Question' : interaction.title)}</legend>
        {(question.message || question.question) && <p className="text-sm text-gray-500">{question.message || question.question}</p>}
        {kind === 'input' ? <textarea value={values[question.id] || ''} onChange={(event) => setValues((current) => ({ ...current, [question.id]: event.target.value }))} rows={3} placeholder="Type your answer…" className="w-full rounded-xl border border-gray-300 bg-white px-3 py-2 text-sm outline-none transition focus:border-primary-500 focus:ring-2 focus:ring-primary-100 dark:border-gray-600 dark:bg-gray-900 dark:text-white" /> : <div className="grid gap-2 sm:grid-cols-2">{options.map((option) => {
          const selected = (selections[question.id] || []).includes(option.id)
          return <button key={option.id} type="button" aria-pressed={selected} onClick={() => toggle(question, option.id)} className={`flex items-start gap-3 rounded-xl border p-3 text-left transition ${selected ? 'border-primary-500 bg-primary-50 ring-2 ring-primary-100 dark:bg-primary-950/40' : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50 dark:border-gray-700 dark:hover:bg-gray-700'}`}><span className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center ${question.multiple ? 'rounded-md' : 'rounded-full'} border ${selected ? 'border-primary-600 bg-primary-600 text-white' : 'border-gray-300'}`}>{selected && <Check className="h-3 w-3" />}</span><span><strong className="block text-sm text-gray-800 dark:text-white">{option.label}</strong>{option.description && <span className="mt-0.5 block text-xs leading-5 text-gray-500">{option.description}</span>}</span></button>
        })}</div>}
      </fieldset>
    })}</div>
    <div className="flex items-center justify-between border-t bg-gray-50 px-5 py-3 dark:bg-gray-900/60"><span className="text-xs text-gray-500">The Agent will continue after your answer.</span><button type="button" onClick={submit} disabled={!complete || pending} className="rounded-xl bg-primary-600 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-primary-700 disabled:cursor-not-allowed disabled:opacity-50">{pending ? 'Continuing…' : 'Continue'}</button></div>
  </section>
}

export default function ChatPage() {
  const { sessionId } = useParams()
  const [message, setMessage] = useState('')
  const [files, setFiles] = useState<PendingFile[]>([])
  const [isRunning, setIsRunning] = useState(false)
  const [streamingContent, setStreamingContent] = useState('')
  const [activityPanelOpen, setActivityPanelOpen] = useState(true)
  const [mobileActivityOpen, setMobileActivityOpen] = useState(false)
  const [selectedActivity, setSelectedActivity] = useState<string>()
  const fileInput = useRef<HTMLInputElement>(null)
  const conversationEnd = useRef<HTMLDivElement>(null)
  const socketRef = useRef<WebSocket | null>(null)
  const queryClient = useQueryClient()
  const session = useQuery({ queryKey: ['session', sessionId], enabled: !!sessionId, queryFn: () => api.get(`/api/sessions/${sessionId}`).then((r) => r.data) })
  const messages = useQuery<MessageItem[]>({ queryKey: ['messages', sessionId], enabled: !!sessionId, queryFn: () => api.get(`/api/sessions/${sessionId}/messages`).then((r) => r.data), refetchInterval: isRunning ? 750 : false })
  const activities = useQuery<ActivityItem[]>({ queryKey: ['activities', sessionId], enabled: !!sessionId, queryFn: () => api.get(`/api/sessions/${sessionId}/activities`).then((r) => r.data), refetchInterval: isRunning ? 750 : false })
  const interactions = useQuery<InteractionItem[]>({ queryKey: ['interactions', sessionId], enabled: !!sessionId, queryFn: () => api.get(`/api/sessions/${sessionId}/interactions`, { params: { pending_only: true } }).then((r) => r.data), refetchInterval: isRunning ? 750 : false })
  const pendingInteraction = interactions.data?.[interactions.data.length - 1]
  const commandInput = message.startsWith('/') ? message : ''
  const commands = useQuery({ queryKey: ['commands', sessionId, commandInput], enabled: !!sessionId && !!commandInput, queryFn: () => api.get(`/api/sessions/${sessionId}/commands`, { params: { input: commandInput } }).then((r) => r.data), staleTime: 10_000 })

  useEffect(() => {
    conversationEnd.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [messages.data?.length, pendingInteraction?.id, streamingContent])

  const send = useMutation({
    mutationFn: async ({ content, pendingFiles }: { content: string; pendingFiles: PendingFile[] }) => {
      const attachments = await Promise.all(pendingFiles.map(async ({ file }) => ({ name: file.name, media_type: file.type || 'application/octet-stream', data: await fileToBase64(file) })))
      return new Promise<void>((resolve, reject) => {
        const endpoint = new URL(import.meta.env.VITE_API_URL || window.location.origin, window.location.origin)
        endpoint.protocol = endpoint.protocol === 'https:' ? 'wss:' : 'ws:'
        endpoint.pathname = `/ws/sessions/${sessionId}`
        endpoint.search = ''
        let settled = false
        const finish = (error?: Error) => {
          if (settled) return
          settled = true
          error ? reject(error) : resolve()
        }
        const socket = new WebSocket(endpoint)
        socketRef.current = socket
        socket.onopen = () => socket.send(JSON.stringify({ type: 'user_message', content, attachments }))
        socket.onmessage = (event) => {
          const payload = JSON.parse(event.data)
          if (payload.type === 'stream_start') setStreamingContent('')
          if (payload.type === 'stream_chunk') setStreamingContent((current) => current + String(payload.content || ''))
          if (payload.type === 'stream_end' || payload.type === 'interaction_requested' || payload.type === 'stream_interrupted') {
            socket.close()
            finish()
          }
          if (payload.type === 'error') {
            socket.close()
            finish(new Error(String(payload.content || 'WebSocket request failed')))
          }
        }
        socket.onerror = () => finish(new Error('WebSocket connection failed'))
        socket.onclose = () => {
          if (socketRef.current === socket) socketRef.current = null
          finish(new Error('WebSocket connection closed before the turn completed'))
        }
      })
    },
    onMutate: () => { setIsRunning(true); setStreamingContent('') },
    onSettled: async () => {
      setIsRunning(false)
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['messages', sessionId] }),
        queryClient.invalidateQueries({ queryKey: ['activities', sessionId] }),
        queryClient.invalidateQueries({ queryKey: ['interactions', sessionId] }),
        queryClient.invalidateQueries({ queryKey: ['session', sessionId] }),
      ])
      setStreamingContent('')
    },
  })
  const respond = useMutation({
    mutationFn: ({ interactionId, answers }: { interactionId: string; answers: InteractionAnswer[] }) => api.post(`/api/sessions/${sessionId}/interactions/${interactionId}/respond`, { answers }),
    onMutate: () => setIsRunning(true),
    onSettled: () => {
      setIsRunning(false)
      queryClient.invalidateQueries({ queryKey: ['messages', sessionId] })
      queryClient.invalidateQueries({ queryKey: ['activities', sessionId] })
      queryClient.invalidateQueries({ queryKey: ['interactions', sessionId] })
      queryClient.invalidateQueries({ queryKey: ['session', sessionId] })
    },
  })
  const switchModel = useMutation({
    mutationFn: ({ provider, model }: { provider: string | null; model: string | null }) => api.put(`/api/sessions/${sessionId}`, { provider, model }).then((r) => r.data),
    onSuccess: (updated) => queryClient.setQueryData(['session', sessionId], updated),
  })
  const renameSession = useMutation({
    mutationFn: (title: string) => api.put(`/api/sessions/${sessionId}`, { title }).then((r) => r.data),
    onSuccess: (updated) => queryClient.setQueryData(['session', sessionId], updated),
  })

  const handleFiles = (event: ChangeEvent<HTMLInputElement>) => {
    const selected = [...(event.target.files || [])].slice(0, Math.max(0, 8 - files.length))
    setFiles((current) => [...current, ...selected.map((file) => ({ file, preview: file.type.startsWith('image/') ? URL.createObjectURL(file) : undefined }))])
    event.target.value = ''
  }
  const handleSend = () => {
    const content = message.trim()
    if ((!content && files.length === 0) || send.isPending) return
    const pendingFiles = files
    setMessage('')
    setFiles([])
    send.mutate({ content, pendingFiles })
  }
  const handleStop = () => {
    const socket = socketRef.current
    if (!socket) return
    const interrupt = () => socket.send(JSON.stringify({ type: 'interrupt' }))
    if (socket.readyState === WebSocket.OPEN) interrupt()
    else if (socket.readyState === WebSocket.CONNECTING) socket.addEventListener('open', interrupt, { once: true })
  }
  const chooseCommand = (candidate: any) => {
    if (candidate.kind === 'command') return setMessage(`${candidate.value} `)
    const parts = message.split(' ')
    parts[parts.length - 1] = candidate.value
    setMessage(`${parts.join(' ')} `)
  }
  const selectActivity = (id: string) => {
    setSelectedActivity(id)
    setActivityPanelOpen(true)
    const mobile = window.matchMedia('(max-width: 1279px)').matches
    if (mobile) setMobileActivityOpen(true)
    window.setTimeout(() => document.getElementById(`${mobile ? 'mobile-activity' : 'activity'}-${id}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' }), 80)
  }
  const activitiesForTurn = (index: number) => {
    const messageItems = messages.data || []
    const start = new Date(messageItems[index].created_at).getTime()
    const nextUser = messageItems.slice(index + 1).find((item) => item.role === 'user')
    const end = nextUser ? new Date(nextUser.created_at).getTime() : Number.POSITIVE_INFINITY
    return (activities.data || []).filter((item) => {
      const timestamp = new Date(item.created_at).getTime()
      return timestamp >= start && timestamp < end
    })
  }
  const lastUserIndex = (messages.data || []).reduce((last, item, index) => item.role === 'user' ? index : last, -1)
  const error: any = messages.error || activities.error || interactions.error || send.error || respond.error || switchModel.error || renameSession.error

  return <div className="flex h-full min-h-0 bg-slate-50 dark:bg-gray-950">
    <div className="flex min-w-0 flex-1 flex-col">
      <header className="relative z-40 flex items-center justify-between gap-3 border-b bg-white/95 px-4 py-1.5 shadow-sm backdrop-blur sm:px-5 dark:bg-gray-900/95">
        <div className="min-w-0"><div className="flex items-center gap-1"><h2 className="truncate text-sm font-semibold text-gray-900 dark:text-white">{session.data?.title || `Session ${sessionId}`}</h2><button title="Rename session" onClick={() => { const title = window.prompt('Session title', session.data?.title || ''); if (title?.trim()) renameSession.mutate(title.trim()) }} className="rounded p-0.5 text-gray-400 transition hover:bg-gray-100 dark:hover:bg-gray-800"><Pencil className="h-3 w-3" /></button></div><p className="max-w-[60vw] truncate text-[10px] leading-4 text-gray-500"><span className="font-medium text-gray-600 dark:text-gray-300">{session.data?.agent_name}</span> · {session.data?.workspace_name || 'Default workspace'} · {session.data?.workspace_path}</p></div>
        <div className="flex shrink-0 items-center gap-1.5"><button type="button" title={activityPanelOpen ? 'Hide activity panel' : 'Show activity panel'} onClick={() => { if (window.matchMedia('(max-width: 1279px)').matches) setMobileActivityOpen(true); else setActivityPanelOpen((value) => !value) }} className="relative flex h-7 w-7 items-center justify-center rounded-md border bg-white text-gray-500 transition hover:border-primary-300 hover:text-primary-600 dark:bg-gray-800">{activityPanelOpen ? <PanelRightClose className="h-3.5 w-3.5" /> : <PanelRightOpen className="h-3.5 w-3.5" />}{(activities.data?.length || 0) > 0 && <span className="absolute -right-1.5 -top-1.5 min-w-4 rounded-full bg-primary-600 px-1 text-center text-[9px] leading-4 text-white">{activities.data?.length}</span>}</button><ModelPicker provider={session.data?.provider} model={session.data?.model} onChange={(provider, model) => switchModel.mutate({ provider, model })} /></div>
      </header>
      <main className="flex-1 space-y-4 overflow-auto px-4 py-6 sm:px-8">
        {error && <div className="mx-auto max-w-4xl rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error.response?.data?.detail || error.message}</div>}
        {(messages.data || []).map((item, index) => <Fragment key={item.id}>
          <MessageBubble item={item} sessionId={sessionId} />
          {item.role === 'user' && <InlineActivity activities={activitiesForTurn(index)} running={isRunning && index === lastUserIndex} onSelect={selectActivity} />}
        </Fragment>)}
        {send.isPending && streamingContent && <MessageBubble item={{ id: 'streaming-response', role: 'assistant', content: streamingContent, created_at: new Date().toISOString() }} sessionId={sessionId} />}
        {send.isPending && lastUserIndex === -1 && <InlineActivity activities={activities.data || []} running onSelect={selectActivity} />}
        {pendingInteraction && <InteractionCard key={pendingInteraction.id} interaction={pendingInteraction} pending={respond.isPending} onSubmit={(answers) => respond.mutate({ interactionId: pendingInteraction.id, answers })} />}
        <div ref={conversationEnd} />
        {!messages.isLoading && (messages.data?.length || 0) === 0 && !send.isPending && <div className="mx-auto flex max-w-xl flex-col items-center py-20 text-center"><div className="mb-4 rounded-2xl bg-primary-100 p-4 text-primary-700 dark:bg-primary-950"><Sparkles className="h-7 w-7" /></div><h3 className="font-semibold text-gray-800 dark:text-white">Start a conversation</h3><p className="mt-2 text-sm leading-6 text-gray-500">Ask a question, run a Slash command, activate a Skill, or attach a file.</p></div>}
      </main>
      <footer className="relative border-t bg-white/95 px-3 py-1.5 backdrop-blur sm:px-4 sm:py-2 dark:bg-gray-900/95">
        {commandInput && commands.data?.length > 0 && <div className="absolute bottom-full left-3 right-3 z-40 mb-2 max-h-72 overflow-auto rounded-2xl border bg-white p-2 shadow-2xl sm:left-4 sm:right-4 dark:bg-gray-800">{commands.data.map((command: any, index: number) => <button key={`${command.name}-${command.value}-${index}`} onClick={() => chooseCommand(command)} className="flex w-full items-start gap-3 rounded-xl px-3 py-2.5 text-left transition hover:bg-gray-100 dark:hover:bg-gray-700"><span className="font-mono text-sm font-semibold text-primary-600">{command.label}</span><span className="text-sm text-gray-500">{command.description || command.usage}</span></button>)}</div>}
        {files.length > 0 && <div className="mx-auto mb-2 flex max-w-5xl flex-wrap gap-1.5">{files.map((item, index) => <div key={`${item.file.name}-${index}`} className="relative flex h-8 items-center gap-1.5 rounded-lg border bg-gray-50 px-2 text-[11px] dark:bg-gray-800">{item.preview ? <img src={item.preview} className="h-6 w-6 rounded-md object-cover" /> : item.file.type.startsWith('video/') ? <Video className="h-3.5 w-3.5" /> : <FileIcon className="h-3.5 w-3.5" />}<span className="max-w-36 truncate">{item.file.name}</span><button title="Remove attachment" onClick={() => setFiles((current) => current.filter((_, itemIndex) => itemIndex !== index))} className="rounded p-0.5 text-gray-400 hover:bg-gray-200"><X className="h-3 w-3" /></button></div>)}</div>}
        <div className={`mx-auto flex max-w-5xl items-end gap-1.5 rounded-xl border bg-white p-1.5 shadow-sm transition focus-within:border-primary-400 focus-within:ring-2 focus-within:ring-primary-100 dark:bg-gray-800 ${pendingInteraction ? 'opacity-60' : ''}`}><input ref={fileInput} type="file" multiple className="hidden" onChange={handleFiles} /><button title="Attach images, video or files" onClick={() => fileInput.current?.click()} disabled={files.length >= 8 || send.isPending || !!pendingInteraction} className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-gray-500 transition hover:bg-gray-100 disabled:opacity-40 dark:hover:bg-gray-700"><Paperclip className="h-4 w-4" /></button><textarea value={message} onChange={(event) => setMessage(event.target.value)} onKeyDown={(event) => { if (shouldSendFromKeyboard(event)) { event.preventDefault(); handleSend() } }} disabled={!!pendingInteraction || send.isPending} rows={1} placeholder={pendingInteraction ? 'Answer the interaction above to continue…' : 'Message, /command, or attach files…'} className="max-h-32 min-h-8 min-w-0 flex-1 resize-none border-0 bg-transparent px-1 py-1.5 text-sm leading-5 outline-none dark:text-white" />{send.isPending ? <button title="Stop generating" onClick={handleStop} className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-red-600 text-white shadow-sm transition hover:bg-red-700"><Square className="h-3.5 w-3.5 fill-current" /></button> : <button title="Send message" onClick={handleSend} disabled={!!pendingInteraction || (!message.trim() && files.length === 0)} className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-primary-600 text-white shadow-sm transition hover:bg-primary-700 disabled:opacity-50"><Send className="h-4 w-4" /></button>}</div>
      </footer>
    </div>
    {activityPanelOpen && <ActivityPanel activities={activities.data || []} selectedId={selectedActivity} onHide={() => setActivityPanelOpen(false)} />}
    {mobileActivityOpen && <div className="fixed inset-0 z-50 flex justify-end bg-slate-950/50 xl:hidden" onMouseDown={() => setMobileActivityOpen(false)}><aside className="flex h-full w-[min(24rem,92vw)] flex-col bg-gray-50 shadow-2xl dark:bg-gray-900" onMouseDown={(event) => event.stopPropagation()}><div className="flex items-center justify-between border-b p-4"><div><h3 className="flex items-center gap-2 font-semibold dark:text-white"><Activity className="h-4 w-4 text-primary-600" />Activity</h3><p className="text-[11px] text-gray-400">Live model and tool trace</p></div><button type="button" title="Close activity" onClick={() => setMobileActivityOpen(false)} className="rounded-lg p-2 text-gray-500 hover:bg-gray-200"><X className="h-4 w-4" /></button></div><div className="flex-1 overflow-auto p-4"><ActivityList activities={activities.data || []} selectedId={selectedActivity} idPrefix="mobile-activity" /></div></aside></div>}
  </div>
}
