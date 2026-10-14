/**
 * WebSocket 组合式封装（自动带 JWT、指数退避重连）。
 * - 控制台：useConsoleSocket()
 * - 议价室：useNegotiationSocket(id)
 */
import { onBeforeUnmount, ref } from 'vue'
import { getToken } from '@/utils/storage'

function wsUrl(path: string): string {
  const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
  const host = window.location.hostname
  const port = window.location.port ? `:${window.location.port}` : ''
  return `${proto}://${host}${port}${path}`
}

type Handler = (data: any) => void

export function useSocket(path: string, onMessage: Handler) {
  const connected = ref(false)
  let ws: WebSocket | null = null
  let closedByUser = false
  let retry = 0
  let timer: number | undefined

  function connect() {
    const url = wsUrl(path)
    ws = new WebSocket(url)
    ws.onopen = () => {
      connected.value = true
      retry = 0
    }
    ws.onmessage = (ev) => {
      try {
        onMessage(JSON.parse(ev.data))
      } catch {
        /* 忽略非 JSON 帧 */
      }
    }
    ws.onclose = () => {
      connected.value = false
      if (!closedByUser) {
        retry += 1
        timer = window.setTimeout(connect, Math.min(1000 * retry, 5000))
      }
    }
    ws.onerror = () => ws?.close()
  }

  function send(data: unknown) {
    if (ws && connected.value) ws.send(JSON.stringify(data))
  }

  function close() {
    closedByUser = true
    if (timer) window.clearTimeout(timer)
    ws?.close()
  }

  connect()
  onBeforeUnmount(close)
  return { connected, send, close }
}

export function useConsoleSocket(onMessage: Handler) {
  return useSocket(`/api/console/ws/control?token=${encodeURIComponent(getToken() || '')}`, onMessage)
}

export function useNegotiationSocket(negotiationId: number, onMessage: Handler) {
  return useSocket(
    `/api/ws/negotiation/${negotiationId}?token=${encodeURIComponent(getToken() || '')}`,
    onMessage,
  )
}
