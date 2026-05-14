// WebSocket API — replaces VS Code postMessage bridge
const WS_URL = import.meta.env.DEV
  ? "ws://localhost:3456"
  : `ws://${window.location.host}`;

let ws: WebSocket | null = null;
let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
let reconnectDelay = 2000;

export function connectWebSocket(): void {
  ws = new WebSocket(WS_URL);

  ws.onopen = () => {
    reconnectDelay = 2000; // reset backoff on successful connection
    console.log("Connected to pixel-agents server");
    ws?.send(JSON.stringify({ type: "webviewReady" }));
  };

  ws.onmessage = (event) => {
    // Dispatch as window message to match upstream useExtensionMessages hook
    const data = JSON.parse(event.data);
    window.dispatchEvent(new MessageEvent("message", { data }));
  };

  ws.onclose = () => {
    console.log(`Disconnected, reconnecting in ${reconnectDelay / 1000}s...`);
    reconnectTimer = setTimeout(() => {
      reconnectDelay = Math.min(reconnectDelay * 2, 30_000); // cap at 30s
      connectWebSocket();
    }, reconnectDelay);
  };

  ws.onerror = () => ws?.close();
}

export function sendMessage(msg: unknown): void {
  if (ws?.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify(msg));
  }
}

export function cleanup(): void {
  if (reconnectTimer) clearTimeout(reconnectTimer);
  ws?.close();
}
