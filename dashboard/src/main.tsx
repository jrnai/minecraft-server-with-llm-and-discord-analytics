import React, { useEffect, useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { Activity, Bot, MessageSquare, Radio, Send, Shield, Users } from 'lucide-react';
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import './styles.css';

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';
const WS_URL = import.meta.env.VITE_WS_URL ?? 'ws://localhost:8000/ws/dashboard';
const DEFAULT_ADMIN_TOKEN = import.meta.env.VITE_ADMIN_TOKEN ?? 'dev-admin-token';

type Status = {
  server: string;
  online: boolean;
  onlinePlayers: number;
  aiName: string;
  llmProvider: string;
  llmModel: string;
  lastEventAt: string | null;
};

type EventRow = {
  id: number;
  type: string;
  timestamp: string;
  player: { uuid: string | null; name: string | null };
  data: Record<string, unknown>;
};

type Player = {
  uuid: string;
  name: string;
  discordId: string | null;
  lastSeenAt: string | null;
  online: boolean;
};

type AiLog = {
  id: number;
  provider: string;
  model: string;
  response: string;
  action: string;
  target: string | null;
  latencyMs: number;
  createdAt: string;
};

function App() {
  const [status, setStatus] = useState<Status | null>(null);
  const [events, setEvents] = useState<EventRow[]>([]);
  const [players, setPlayers] = useState<Player[]>([]);
  const [aiLogs, setAiLogs] = useState<AiLog[]>([]);
  const [metrics, setMetrics] = useState({ joins: 0, leaves: 0, chatMessages: 0 });
  const [broadcast, setBroadcast] = useState('');
  const [adminToken, setAdminToken] = useState(() => localStorage.getItem('adminToken') ?? DEFAULT_ADMIN_TOKEN);
  const [connected, setConnected] = useState(false);

  async function refresh() {
    const [statusData, eventData, playerData, aiData, metricsData] = await Promise.all([
      api<Status>('/api/status'),
      api<EventRow[]>('/api/events?limit=80'),
      api<Player[]>('/api/players'),
      api<AiLog[]>('/api/ai/logs?limit=50'),
      api<typeof metrics>('/api/metrics/uptime')
    ]);
    setStatus(statusData);
    setEvents(eventData);
    setPlayers(playerData);
    setAiLogs(aiData);
    setMetrics(metricsData);
  }

  useEffect(() => {
    refresh();
    const socket = new WebSocket(WS_URL);
    socket.onopen = () => setConnected(true);
    socket.onclose = () => setConnected(false);
    socket.onmessage = () => refresh();
    return () => socket.close();
  }, []);

  const chartData = useMemo(() => {
    const buckets = new Map<string, number>();
    for (const event of events) {
      const label = new Date(event.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
      buckets.set(label, (buckets.get(label) ?? 0) + 1);
    }
    return [...buckets.entries()].reverse().map(([time, count]) => ({ time, count }));
  }, [events]);

  async function sendBroadcast() {
    const message = broadcast.trim();
    if (!message) return;
    await fetch(`${API_BASE}/api/admin/broadcast`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Admin-Token': adminToken
      },
      body: JSON.stringify({ message })
    });
    setBroadcast('');
    await refresh();
  }

  return (
    <main className="shell">
      <section className="topbar">
        <div>
          <p className="eyebrow">Minecraft LLM Ops</p>
          <h1>{status?.server ?? 'main'} server</h1>
        </div>
        <div className={connected ? 'status online' : 'status'}>
          <Radio size={18} />
          {connected ? 'live' : 'offline'}
        </div>
      </section>

      <section className="metrics-grid">
        <Metric icon={<Users />} label="Online players" value={status?.onlinePlayers ?? 0} />
        <Metric icon={<Bot />} label="Assistant" value={status?.aiName ?? 'Guide'} detail={status?.llmModel} />
        <Metric icon={<Activity />} label="Chat messages" value={metrics.chatMessages} />
        <Metric icon={<Shield />} label="Provider" value={status?.llmProvider ?? 'mock'} />
      </section>

      <section className="content-grid">
        <Panel title="Activity" icon={<Activity />}>
          <div className="chart">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData}>
                <XAxis dataKey="time" tick={{ fontSize: 11 }} />
                <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
                <Tooltip />
                <Line type="monotone" dataKey="count" stroke="#4f8cff" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </Panel>

        <Panel title="Players" icon={<Users />}>
          <div className="list">
            {players.length === 0 && <Empty label="No players recorded yet" />}
            {players.map((player) => (
              <div className="row" key={player.uuid}>
                <span className={player.online ? 'dot online-dot' : 'dot'} />
                <div>
                  <strong>{player.name}</strong>
                  <small>{player.discordId ? `Discord ${player.discordId}` : 'No Discord link'}</small>
                </div>
              </div>
            ))}
          </div>
        </Panel>

        <Panel title="Chat & Events" icon={<MessageSquare />}>
          <div className="feed">
            {events.length === 0 && <Empty label="No events yet" />}
            {events.slice(0, 18).map((event) => (
              <article key={event.id}>
                <span>{event.type}</span>
                <strong>{event.player.name ?? 'server'}</strong>
                <p>{String(event.data.message ?? event.data.reason ?? JSON.stringify(event.data))}</p>
              </article>
            ))}
          </div>
        </Panel>

        <Panel title="AI Logs" icon={<Bot />}>
          <div className="feed">
            {aiLogs.length === 0 && <Empty label="No AI responses yet" />}
            {aiLogs.slice(0, 12).map((log) => (
              <article key={log.id}>
                <span>{Math.round(log.latencyMs)} ms</span>
                <strong>{log.action}</strong>
                <p>{log.response}</p>
              </article>
            ))}
          </div>
        </Panel>

        <Panel title="Admin Broadcast" icon={<Send />} wide>
          <div className="admin-form">
            <input
              className="token-input"
              value={adminToken}
              onChange={(event) => {
                setAdminToken(event.target.value);
                localStorage.setItem('adminToken', event.target.value);
              }}
              placeholder="Admin token"
            />
            <input
              value={broadcast}
              onChange={(event) => setBroadcast(event.target.value)}
              placeholder="Broadcast a safe server notice"
              maxLength={500}
            />
            <button onClick={sendBroadcast}>
              <Send size={16} />
              Send
            </button>
          </div>
        </Panel>
      </section>
    </main>
  );
}

function Metric({ icon, label, value, detail }: { icon: React.ReactNode; label: string; value: React.ReactNode; detail?: React.ReactNode }) {
  return (
    <div className="metric">
      <div className="metric-icon">{icon}</div>
      <span>{label}</span>
      <strong>{value}</strong>
      {detail && <small>{detail}</small>}
    </div>
  );
}

function Panel({ title, icon, children, wide = false }: { title: string; icon: React.ReactNode; children: React.ReactNode; wide?: boolean }) {
  return (
    <section className={wide ? 'panel wide' : 'panel'}>
      <header>
        {icon}
        <h2>{title}</h2>
      </header>
      {children}
    </section>
  );
}

function Empty({ label }: { label: string }) {
  return <p className="empty">{label}</p>;
}

async function api<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`);
  if (!response.ok) throw new Error(`API error ${response.status}`);
  return response.json();
}

createRoot(document.getElementById('root')!).render(<App />);
