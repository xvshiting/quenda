import assert from 'node:assert/strict'
import test from 'node:test'

import { repairLiteralStrong } from '../src/utils/markdownPresentation.ts'

test('repairs model emphasis left literal next to CJK text', () => {
  const root = {
    type: 'root',
    children: [{ type: 'paragraph', children: [{ type: 'text', value: '只输出**稀疏修正**而不是全文' }] }],
  }

  repairLiteralStrong(root)

  assert.deepEqual(root.children[0].children, [
    { type: 'text', value: '只输出' },
    { type: 'strong', children: [{ type: 'text', value: '稀疏修正' }] },
    { type: 'text', value: '而不是全文' },
  ])
})

test('does not disturb plain text without literal emphasis', () => {
  const root = { type: 'root', children: [{ type: 'text', value: '普通文本' }] }
  repairLiteralStrong(root)
  assert.deepEqual(root.children, [{ type: 'text', value: '普通文本' }])
})
