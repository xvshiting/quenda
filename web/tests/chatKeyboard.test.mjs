import assert from 'node:assert/strict'
import test from 'node:test'

import { shouldSendFromKeyboard } from '../src/utils/chatKeyboard.ts'

const keyboardEvent = (overrides = {}) => ({
  key: 'Enter',
  shiftKey: false,
  nativeEvent: { isComposing: false, keyCode: 13 },
  ...overrides,
})

test('Enter sends a completed message', () => {
  assert.equal(shouldSendFromKeyboard(keyboardEvent()), true)
})

test('Shift+Enter inserts a newline', () => {
  assert.equal(shouldSendFromKeyboard(keyboardEvent({ shiftKey: true })), false)
})

test('Enter used to confirm an IME candidate does not send', () => {
  assert.equal(shouldSendFromKeyboard(keyboardEvent({
    nativeEvent: { isComposing: true, keyCode: 13 },
  })), false)
})

test('legacy IME Enter with keyCode 229 does not send', () => {
  assert.equal(shouldSendFromKeyboard(keyboardEvent({
    nativeEvent: { isComposing: false, keyCode: 229 },
  })), false)
})
