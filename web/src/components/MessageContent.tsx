import { Check, ChevronDown, ChevronUp, Copy, ExternalLink } from 'lucide-react'
import { ReactNode, useState } from 'react'
import ReactMarkdown, { Components } from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { remarkModelMarkdown } from '../utils/markdownPresentation'
import { shouldCollapseMessage } from '../utils/messagePresentation'

function CodeBlock({ className, children }: { className?: string; children?: ReactNode }) {
  const [copied, setCopied] = useState(false)
  const language = className?.replace(/^language-/, '') || 'text'
  const source = String(children ?? '').replace(/\n$/, '')
  const copy = async () => {
    await navigator.clipboard.writeText(source)
    setCopied(true)
    window.setTimeout(() => setCopied(false), 1600)
  }

  return <div className="group/code my-5 overflow-hidden rounded-xl border border-slate-800 bg-[#0b1220] shadow-lg shadow-slate-950/10">
    <div className="flex h-9 items-center justify-between border-b border-white/10 bg-white/[0.035] px-3 text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-400">
      <span>{language}</span>
      <button type="button" onClick={copy} className="inline-flex items-center gap-1.5 rounded-md px-2 py-1 normal-case tracking-normal text-slate-400 transition hover:bg-white/10 hover:text-white">
        {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
        {copied ? '已复制' : '复制'}
      </button>
    </div>
    <pre className="overflow-x-auto p-4 text-[13px] leading-6 text-slate-100"><code className={`${className || ''} font-mono`}>{children}</code></pre>
  </div>
}

const markdownComponents: Components = {
  h1: ({ children }) => <h1 className="mb-4 mt-8 border-b border-slate-200 pb-3 text-[1.55rem] font-bold leading-tight tracking-tight text-slate-950 first:mt-0 dark:border-slate-700 dark:text-white">{children}</h1>,
  h2: ({ children }) => <h2 className="mb-3 mt-7 flex items-center gap-2 text-xl font-bold leading-snug tracking-tight text-slate-950 first:mt-0 dark:text-white"><span className="h-5 w-1 rounded-full bg-sky-500" />{children}</h2>,
  h3: ({ children }) => <h3 className="mb-2.5 mt-6 text-[1.05rem] font-bold leading-snug text-slate-900 first:mt-0 dark:text-slate-50">{children}</h3>,
  h4: ({ children }) => <h4 className="mb-2 mt-5 text-[0.95rem] font-semibold text-slate-800 first:mt-0 dark:text-slate-100">{children}</h4>,
  p: ({ children }) => <p className="my-3 leading-[1.85] first:mt-0 last:mb-0">{children}</p>,
  ul: ({ children }) => <ul className="my-3 list-disc space-y-1.5 pl-6 marker:text-sky-500">{children}</ul>,
  ol: ({ children }) => <ol className="my-3 list-decimal space-y-2 pl-6 marker:font-semibold marker:text-sky-600">{children}</ol>,
  li: ({ children }) => <li className="pl-1.5 leading-[1.75] [&>p]:my-1">{children}</li>,
  blockquote: ({ children }) => <blockquote className="my-5 rounded-r-xl border-l-4 border-sky-400 bg-sky-50/80 px-4 py-3 text-slate-600 dark:border-sky-600 dark:bg-sky-950/30 dark:text-slate-300">{children}</blockquote>,
  hr: () => <hr className="my-7 border-slate-200 dark:border-slate-700" />,
  a: ({ href, children }) => <a href={href} target="_blank" rel="noreferrer" className="inline-flex items-baseline gap-1 font-medium text-sky-700 underline decoration-sky-300 underline-offset-2 transition hover:text-sky-600 dark:text-sky-400"><span>{children}</span><ExternalLink className="h-3 w-3 shrink-0" /></a>,
  table: ({ children }) => <div className="my-5 overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm dark:border-slate-700 dark:bg-slate-900"><table className="w-full min-w-[36rem] border-separate border-spacing-0 text-left text-[13px] leading-5">{children}</table></div>,
  thead: ({ children }) => <thead className="bg-slate-50 text-[11px] font-semibold uppercase tracking-wide text-slate-500 dark:bg-slate-950 dark:text-slate-400">{children}</thead>,
  tbody: ({ children }) => <tbody className="divide-y divide-slate-100 dark:divide-slate-800">{children}</tbody>,
  tr: ({ children }) => <tr className="transition-colors hover:bg-sky-50/40 dark:hover:bg-sky-950/20">{children}</tr>,
  th: ({ children }) => <th className="border-b border-slate-200 px-4 py-3 align-bottom font-semibold first:w-[32%] dark:border-slate-700">{children}</th>,
  td: ({ children }) => <td className="px-4 py-3 align-top text-slate-700 first:font-medium first:text-slate-900 dark:text-slate-300 dark:first:text-slate-100 [&>p]:my-0">{children}</td>,
  pre: ({ children }) => <>{children}</>,
  code: ({ className, children }) => className
    ? <CodeBlock className={className}>{children}</CodeBlock>
    : <code className="whitespace-nowrap rounded-md border border-slate-200 bg-slate-100 px-1.5 py-0.5 font-mono text-[0.88em] text-fuchsia-700 dark:border-slate-700 dark:bg-slate-900 dark:text-fuchsia-300">{children}</code>,
  strong: ({ children }) => <strong className="font-semibold text-slate-950 dark:text-white">{children}</strong>,
}

export default function MessageContent({ content, isUser }: { content: string; isUser: boolean }) {
  const collapsible = shouldCollapseMessage(content)
  const [expanded, setExpanded] = useState(false)
  const markdown = <ReactMarkdown remarkPlugins={[remarkGfm, remarkModelMarkdown]} components={markdownComponents}>{content}</ReactMarkdown>
  if (!collapsible) return <div className={isUser ? 'user-markdown' : 'assistant-markdown'}>{markdown}</div>

  return <div>
    <div className={`relative overflow-hidden transition-[max-height] duration-300 ${expanded ? 'max-h-none' : 'max-h-[38rem]'}`}>
      <div className={isUser ? 'user-markdown' : 'assistant-markdown'}>{markdown}</div>
      {!expanded && <div className={`pointer-events-none absolute inset-x-0 bottom-0 h-32 bg-gradient-to-t ${isUser ? 'from-primary-600' : 'from-white dark:from-gray-800'} to-transparent`} />}
    </div>
    <div className={`relative z-10 mt-3 flex ${isUser ? 'justify-end' : 'justify-center'}`}>
      <button type="button" onClick={() => setExpanded((value) => !value)} className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-medium shadow-sm transition ${isUser ? 'border-white/20 bg-white/15 text-white hover:bg-white/25' : 'border-slate-200 bg-white text-slate-600 hover:border-sky-300 hover:text-sky-700 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-200'}`}>{expanded ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}{expanded ? '收起内容' : '展开完整内容'}</button>
    </div>
  </div>
}

export function MessageSurface({ children }: { children: ReactNode }) {
  return <div className="message-surface text-[15px] leading-7 antialiased">{children}</div>
}
