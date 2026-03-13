/** Chat message */
export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  timestamp: number;
  isError?: boolean;
  toolResults?: ToolResultItem[];
}

/** Tool execution result (collapsible card) */
export interface ToolResultItem {
  toolName: string;
  args: Record<string, unknown>;
  result: string;
  isError: boolean;
  duration: number; // ms
}

/** Webview -> Extension messages */
export type WebviewMessage =
  | { type: 'sendMessage'; text: string }
  | { type: 'cancelRequest' }
  | { type: 'ready' };

/** Extension -> Webview messages */
export type ExtensionMessage =
  | { type: 'addMessage'; message: ChatMessage }
  | { type: 'setLoading'; loading: boolean }
  | { type: 'clearChat' }
  | { type: 'setInput'; text: string }
  | { type: 'toolResult'; result: ToolResultItem };
