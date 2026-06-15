"use client";

/* eslint-disable @next/next/no-img-element */

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { api, apiUrl, wsUrl } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import { useAuthStore } from "@/store/auth";
import type { ProctorEvent, ProctorSummary } from "@/types";

function eventName(event: ProctorEvent) {
  return event.event_type ?? event.type ?? "event";
}

export default function LiveProctorPage() {
  const { attemptId } = useParams<{ attemptId: string }>();
  const token = useAuthStore((s) => s.accessToken)!;
  const [summary, setSummary] = useState<ProctorSummary | null>(null);
  const [events, setEvents] = useState<ProctorEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .getProctorSummary(token, attemptId)
      .then((data) => {
        setSummary(data);
        setEvents(data.events.slice().reverse());
      })
      .catch(() => setError("Could not load proctoring summary yet."));
  }, [attemptId, token]);

  useEffect(() => {
    const ws = new WebSocket(wsUrl(`/ws/proctor/${attemptId}`, token));
    ws.onopen = () => setConnected(true);
    ws.onclose = () => setConnected(false);
    ws.onerror = () => setConnected(false);
    ws.onmessage = (message) => {
      try {
        const event = JSON.parse(message.data) as ProctorEvent;
        if (event.event_type || event.type) {
          setEvents((prev) => [event, ...prev].slice(0, 100));
        }
      } catch {
        // Ignore malformed websocket messages.
      }
    };
    return () => ws.close();
  }, [attemptId, token]);

  const counts = useMemo(() => {
    const result: Record<string, number> = {};
    events.forEach((event) => {
      const name = eventName(event);
      result[name] = (result[name] ?? 0) + 1;
    });
    return Object.keys(result).length ? result : summary?.event_counts ?? {};
  }, [events, summary]);

  const latestSnapshot = events.find((event) => event.snapshot_url)?.snapshot_url;

  return (
    <div className="space-y-6">
      <Link href="/recruiter" className="text-sm text-muted hover:text-accent">
        Back to dashboard
      </Link>

      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="font-sans text-3xl font-extrabold">Live Proctoring</h1>
          <p className="mt-1 font-mono text-xs text-muted">{attemptId}</p>
        </div>
        <span
          className={`rounded border px-3 py-1 text-xs uppercase ${
            connected
              ? "border-green/40 bg-green/10 text-green"
              : "border-red/40 bg-red/10 text-red"
          }`}
        >
          {connected ? "Live connected" : "Waiting"}
        </span>
      </div>

      {error && <p className="text-sm text-gold">{error}</p>}

      <div className="grid gap-4 md:grid-cols-4">
        <div className="card-panel">
          <p className="text-xs uppercase tracking-wider text-muted">Events</p>
          <p className="mt-2 font-sans text-3xl font-extrabold text-accent">{events.length}</p>
        </div>
        <div className="card-panel">
          <p className="text-xs uppercase tracking-wider text-muted">Risk</p>
          <p className="mt-2 font-sans text-3xl font-extrabold text-gold">
            {summary?.cheating_risk ?? "live"}
          </p>
        </div>
        <div className="card-panel md:col-span-2">
          <p className="text-xs uppercase tracking-wider text-muted">Event Counts</p>
          <div className="mt-3 flex flex-wrap gap-2">
            {Object.entries(counts).map(([name, count]) => (
              <span key={name} className="badge border border-border text-muted">
                {name}: {count}
              </span>
            ))}
          </div>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-[360px_1fr]">
        <section className="card-panel">
          <h2 className="font-sans text-lg font-bold">Latest Snapshot</h2>
          {latestSnapshot ? (
            <img
              src={apiUrl(latestSnapshot)}
              alt="Latest proctoring snapshot"
              className="mt-4 aspect-video w-full rounded-lg border border-border bg-bg object-cover"
            />
          ) : (
            <div className="mt-4 flex aspect-video items-center justify-center rounded-lg border border-border bg-surface text-sm text-muted">
              No snapshot yet
            </div>
          )}
        </section>

        <section className="card-panel">
          <h2 className="font-sans text-lg font-bold">Live Event Feed</h2>
          {events.length === 0 ? (
            <p className="mt-4 text-sm text-muted">No proctoring events received yet.</p>
          ) : (
            <div className="mt-4 max-h-[520px] space-y-3 overflow-y-auto pr-1">
              {events.map((event, index) => (
                <div key={`${event.event_id ?? event.id ?? index}`} className="rounded-lg border border-border bg-surface p-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="font-sans text-sm font-bold text-accent">{eventName(event)}</span>
                    <span className="text-xs text-muted">{formatDate(event.timestamp)}</span>
                  </div>
                  {event.metadata && (
                    <p className="mt-2 break-all font-mono text-xs text-muted">
                      {JSON.stringify(event.metadata)}
                    </p>
                  )}
                  {event.snapshot_url && (
                    <img
                      src={apiUrl(event.snapshot_url)}
                      alt="Proctoring snapshot"
                      className="mt-3 h-28 rounded border border-border object-cover"
                    />
                  )}
                </div>
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
