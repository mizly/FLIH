"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { ArrowRight, BatteryMedium, Check, ChevronDown, Footprints, MapPin, RotateCcw, Sparkles, X } from "lucide-react";
import type { Dashboard as DashboardData, PlaceId } from "@/lib/campus";
import { placeName, places } from "@/lib/campus";
import { CampusMap } from "./campus-map";
import { Fly } from "./fly";
import { Button } from "./ui/button";
import Link from "next/link";
import { Gamepad2 } from "lucide-react";

export function Dashboard() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [connectionError, setConnectionError] = useState(false);
  const [pickup, setPickup] = useState<PlaceId | null>(null);
  const [end, setEnd] = useState<PlaceId | null>(null);
  const [introOpen, setIntroOpen] = useState(false);
  const [username, setUsername] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const refresh = useCallback(async () => {
    try {
      const response = await fetch("/api/flih");
      if (!response.ok) throw new Error();
      setData(await response.json());
      setConnectionError(false);
    } catch {
      setConnectionError(true);
    }
  }, []);

  useEffect(() => {
    void refresh();
    const timer = setInterval(() => void refresh(), 5000);
    return () => clearInterval(timer);
  }, [refresh]);

  useEffect(() => {
    if (!data?.mine) return;
    const heartbeat = () => void fetch("/api/flih", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: "heartbeat" }),
      keepalive: true,
    });
    const timer = setInterval(heartbeat, 20_000);
    return () => clearInterval(timer);
  }, [data?.mine]);

  const mine = data?.queue.find((entry) => entry.id === data.mine);
  const position = useMemo(() => mine ? (data?.queue.findIndex((entry) => entry.id === mine.id) ?? -1) + 1 : 0, [data?.queue, mine]);
  const shownPickup = mine?.pickup ?? pickup;
  const shownEnd = mine?.end ?? end;
  const offline = connectionError || data?.robot.status === "offline";

  function chooseEnd(id: PlaceId) {
    setEnd(id);
    setError("");
  }

  async function updateQueuedRoute(nextPickup: PlaceId, nextEnd: PlaceId) {
    if (!mine || nextPickup === nextEnd) return;
    const previousPickup = mine.pickup;
    const previousEnd = mine.end;
    setError("");
    setData((current) => current ? {
      ...current,
      queue: current.queue.map((entry) => entry.id === mine.id ? { ...entry, pickup: nextPickup, end: nextEnd } : entry),
    } : current);
    try {
      const response = await fetch("/api/flih", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "update-route", pickup: nextPickup, end: nextEnd }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error ?? "Couldnâ€™t update your route.");
    } catch (updateError) {
      setData((current) => current ? {
        ...current,
        queue: current.queue.map((entry) => entry.id === mine.id ? { ...entry, pickup: previousPickup, end: previousEnd } : entry),
      } : current);
      setError(updateError instanceof Error ? updateError.message : "Couldnâ€™t update your route.");
    }
  }

  function changePickup(id: PlaceId) {
    if (mine && shownEnd) void updateQueuedRoute(id, shownEnd);
    else {
      setPickup(id);
      setError("");
    }
  }

  function changeEnd(id: PlaceId) {
    if (mine && shownPickup) void updateQueuedRoute(shownPickup, id);
    else chooseEnd(id);
  }

  async function requestGuide(event: React.FormEvent) {
    event.preventDefault();
    if (!pickup || !end) return setError("Choose a starting point and end.");
    if (pickup === end) return setError("Choose two different locations.");
    setBusy(true);
    setError("");
    try {
      const response = await fetch("/api/flih", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, pickup, end }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error ?? "Please try again.");
      setNotice("Guide requested. Keep this page open for live updates.");
      await refresh();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Please try again.");
    } finally {
      setBusy(false);
    }
  }

  async function cancel() {
    setBusy(true);
    setError("");
    try {
      const response = await fetch("/api/flih", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "cancel" }),
      });
      if (!response.ok) throw new Error();
      await refresh();
      setNotice("Your request was cancelled.");
    } catch {
      setError("Couldn’t cancel your request. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  function restart() {
    setError("");
    setPickup(null);
    setEnd(null);
  }

  return (
    <main className="app-shell">
      <header className="floating-header">
        <div className="brand-menu">
          <button className="brand" type="button" aria-controls="brand-menu-action">
            <Fly small /><span>FLIH<span className="brand-dot">.</span></span><ChevronDown className="brand-chevron" size={16} />
          </button>
          <button id="brand-menu-action" className="brand-about" type="button" onClick={() => setIntroOpen(true)}>what is flih?</button>
        </div>
        <div className="header-actions">
          <Link className="control-link" href="/control"><Gamepad2 size={18} /> Drive</Link>
          <div className="live-status" aria-live="polite">
            <span className={offline ? "status-dot offline" : "status-dot"} />
            {connectionError ? "Reconnecting" : data ? "Live" : "Connecting"}
          </div>
        </div>
      </header>

      <section className="map-workspace" aria-label="FLIH route map">
        <CampusMap
          robot={data?.robot ?? null}
          pickup={shownPickup}
          end={shownEnd}
          onPickup={changePickup}
          onEnd={changeEnd}
        />
      </section>

      <aside className="route-panel" aria-label="Your route">
          <div className="route-panel-content">
          <div className="panel-handle" aria-hidden="true" />
          <div className="panel-heading">
            <div><span className="panel-kicker"><Sparkles size={14} /> Your route</span><h1>{shownPickup && shownEnd ? "Ready to go" : "Plan your route"}</h1></div>
            <button className="icon-button" type="button" onClick={restart} aria-label="Clear route" disabled={Boolean(mine)}><RotateCcw size={17} /></button>
          </div>
          <div className="route-editor">
            <div className="route-line" aria-hidden="true"><span /><i /><span /></div>
            <label><span>Starting from</span>
              <select aria-label="Starting from" value={shownPickup ?? ""} onChange={(event) => changePickup(event.target.value as PlaceId)}>
                <option value="" disabled>Select start</option>
                {places.map((place) => <option key={place.id} value={place.id}>{place.name}</option>)}
              </select>
            </label>
            <label><span>Going to</span>
              <select aria-label="Going to" value={shownEnd ?? ""} onChange={(event) => changeEnd(event.target.value as PlaceId)}>
                <option value="" disabled>Select end</option>
                {places.map((place) => <option key={place.id} value={place.id}>{place.name}</option>)}
              </select>
            </label>
          </div>
          {shownPickup && shownEnd && shownPickup === shownEnd && <p className="error-message" role="alert">Choose two different locations.</p>}
          <div className="trip-summary"><span><Footprints size={16} /> {shownPickup && shownEnd ? "Follow the highlighted route" : "Choose start and end"}</span><span><BatteryMedium size={16} /> {data ? `${Math.round(data.robot.battery)}%` : "—"}</span></div>
          {mine ? (
            <div className="queue-result">
              <div className="success-badge"><Check size={18} /> Guide requested</div>
              <p>You’re #{position} in line. Stay near {placeName(mine.pickup)}.</p>
              <Button variant="outline" className="w-full" disabled={busy} onClick={() => void cancel()}><X size={17} /> {busy ? "Cancelling…" : "Cancel request"}</Button>
            </div>
          ) : (
            <form className="guide-form" onSubmit={requestGuide}>
              <label htmlFor="username"><span>Want FLIH to guide you?</span></label>
              <div className="name-row">
                <input id="username" aria-label="Your name" value={username} onChange={(event) => setUsername(event.target.value)} placeholder="Your name" required minLength={2} maxLength={20} pattern="[\p{L}\p{N}_ .\-]{2,20}" autoComplete="nickname" />
                <Button type="submit" disabled={busy || offline || !pickup || !end || pickup === end}>{busy ? "Requesting…" : "Request guide"} <ArrowRight size={18} /></Button>
              </div>
              <small>No account needed.</small>
            </form>
          )}
          {error && <p className="error-message" role="alert">{error}</p>}
          </div>
        </aside>

      {introOpen && (
        <div className="wizard-overlay">
          <section className="wizard-card intro-card" role="dialog" aria-modal="true" aria-labelledby="wizard-title">
            <button className="intro-close" type="button" onClick={() => setIntroOpen(false)} aria-label="Close"><X size={19} /></button>
              <div className="intro-step">
                <div className="wizard-fly"><Fly /></div>
                <span className="wizard-eyebrow">Meet your campus guide</span>
                <h1 id="wizard-title">Get there with FLIH.</h1>
                <p>FLIH is a tiny-brained, four-wheeled guide that helps you navigate the E5 and E7 sixth floor.</p>
                <div className="intro-points"><span><MapPin size={18} /> Choose where you are</span><span><ArrowRight size={18} /> Pick where you’re going</span><span><Footprints size={18} /> Follow your route</span></div>
                <Button className="wizard-primary" onClick={() => setIntroOpen(false)}>Got it <Check size={20} /></Button>
              </div>
          </section>
        </div>
      )}

      {notice && <div className="toast" role="status"><Check size={18} /> {notice}<button type="button" onClick={() => setNotice("")} aria-label="Dismiss"><X size={17} /></button></div>}
    </main>
  );
}
