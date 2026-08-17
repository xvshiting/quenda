export type ChatKeyboardEvent = {
  key: string
  shiftKey: boolean
  nativeEvent: {
    isComposing?: boolean
    keyCode?: number
  }
}

export function shouldSendFromKeyboard(event: ChatKeyboardEvent): boolean {
  const composing = event.nativeEvent.isComposing || event.nativeEvent.keyCode === 229
  return event.key === 'Enter' && !event.shiftKey && !composing
}
