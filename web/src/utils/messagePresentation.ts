export const LONG_MESSAGE_CHARACTERS = 2_400
export const LONG_MESSAGE_LINES = 32

export function shouldCollapseMessage(content: string): boolean {
  return content.length > LONG_MESSAGE_CHARACTERS || content.split('\n').length > LONG_MESSAGE_LINES
}
