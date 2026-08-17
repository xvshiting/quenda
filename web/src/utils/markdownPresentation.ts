type MarkdownNode = {
  type?: string
  value?: string
  children?: MarkdownNode[]
}

/**
 * CommonMark deliberately leaves some emphasis adjacent to CJK characters
 * literal (for example `只输出**稀疏修正**而不是`). Models produce this form
 * frequently, so repair only text that the parser did not already recognize.
 */
export function repairLiteralStrong(root: MarkdownNode): void {
  if (!root.children) return
  root.children = root.children.flatMap((child) => {
    if (child.type !== 'text' || !child.value?.includes('**')) {
      repairLiteralStrong(child)
      return [child]
    }
    const parts: MarkdownNode[] = []
    const pattern = /\*\*([^*\n]+)\*\*/g
    let cursor = 0
    let match: RegExpExecArray | null
    while ((match = pattern.exec(child.value)) !== null) {
      if (match.index > cursor) parts.push({ type: 'text', value: child.value.slice(cursor, match.index) })
      parts.push({ type: 'strong', children: [{ type: 'text', value: match[1] }] })
      cursor = match.index + match[0].length
    }
    if (cursor === 0) return [child]
    if (cursor < child.value.length) parts.push({ type: 'text', value: child.value.slice(cursor) })
    return parts
  })
}

export function remarkModelMarkdown() {
  return repairLiteralStrong
}
