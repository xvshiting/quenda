import assert from 'node:assert/strict'
import test from 'node:test'

import { shouldCollapseMessage } from '../src/utils/messagePresentation.ts'

test('short messages remain fully visible', () => {
  assert.equal(shouldCollapseMessage('A concise response.'), false)
})

test('long prose is collapsed', () => {
  assert.equal(shouldCollapseMessage('x'.repeat(2_401)), true)
})

test('many short lines are collapsed', () => {
  assert.equal(shouldCollapseMessage(Array.from({ length: 33 }, (_, i) => `line ${i}`).join('\n')), true)
})
