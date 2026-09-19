"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { ArrowLeft, ArrowRight, BatteryMedium, Check, Footprints, LocateFixed, MapPin, Navigation, RotateCcw, Sparkles, X } from "lucide-react";
import type { Dashboard as DashboardData, PlaceId } from "@/lib/campus";
import { placeName, places } from "@/lib/campus";
import { CampusMap } from "./campus-map";
import { Fly } from "./fly";
import { Button } from "./ui/button";

type WizardStep = "intro" | "pickup" | "destination" | "done";

export function Dashboard() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [connectionError, setConnectionError] = useState(false);
  const [pickup, setPickup] = useState<PlaceId>("slc");
  const [destination, setDestination] = useState<PlaceId>("e7");
  const [step, setStep] = useState<WizardStep>("intro");
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
  const shownDestination = mine?.destination ?? destination;
  const offline = connectionError || data?.robot.status === "offline";

  function chooseDestination(id: PlaceId) {
    setDestination(id);
    setError("");
  }

  async function updateQueuedRoute(nextPickup: PlaceId, nextDestination: PlaceId) {
    if (!mine || nextPickup === nextDestination) return;
    const previousPickup = mine.pickup;
    const previousDestination = mine.destination;
    setError("");
    setData((current) => current ? {
      ...current,
      queue: current.queue.map((entry) => entry.id === mine.id ? { ...entry, pickup: nextPickup, destination: nextDestination } : entry),
    } : current);
    try {
      const response = await fetch("/api/flih", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "update-route", pickup: nextPickup, destination: nextDestination }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error ?? "Couldnâ€™t update your route.");
    } catch (updateError) {
      setData((current) => current ? {
        ...current,
        queue: current.queue.map((entry) => entry.id === mine.id ? { ...entry, pickup: previousPickup, destination: previousDestination } : entry),
      } : current);
      setError(updateError instanceof Error ? updateError.message : "Couldnâ€™t update your route.");
    }
  }

  function changePickup(id: PlaceId) {
    if (mine) void updateQueuedRoute(id, shownDestination);
    else setPickup(id);
  }

  function changeDestination(id: PlaceId) {
    if (mine) void updateQueuedRoute(shownPickup, id);
    else chooseDestination(id);
  }

  function finishWizard() {
    if (pickup === destination) {
      setError("Choose a destination that is different from your starting point.");
      return;
    }
    setError("");
    setStep("done");
  }

  async function requestGuide(event: React.FormEvent) {
    event.preventDefault();
    if (pickup === destination) return setError("Choose two different locations.");
    setBusy(true);
    setError("");
    try {
      const response = await fetch("/api/flih", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, pickup, destination }),
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
    setStep("intro");
  }

  return (
    <main className="app-shell">
      <header className="floating-header">
        <button className="brand" type="button" onClick={restart} aria-label="Start over">
          <Fly small /><span>FLIH<span className="brand-dot">.</span></span>
        </button>
        <div className="live-status" aria-live="polite">
          <span className={offline ? "status-dot offline" : "status-dot"} />
          {connectionError ? "Reconnecting" : data ? "Live" : "Connecting"}
        </div>
      </header>

      <section className="map-workspace" aria-label="FLIH route map">
        <CampusMap
          robot={data?.robot ?? null}
          pickup={shownPickup}
          destination={shownDestination}
          onPickup={changePickup}
          onDestination={changeDestination}
        />
      </section>

      {step === "done" && (
        <aside className="route-panel" aria-label="Your route">
          <div className="collapsed-route-icon" aria-hidden="true"><Navigation size={25} /></div>
          <div className="route-panel-content">
          <div className="panel-handle" aria-hidden="true" />
          <div className="panel-heading">
            <div><span className="panel-kicker"><Sparkles size={15} /> Your route</span><h1>Ready to go</h1></div>
            <button className="icon-button" type="button" onClick={restart} aria-label="Start over"><RotateCcw size={19} /></button>
          </div>
          <div className="route-editor">
            <div className="route-line" aria-hidden="true"><span /><i /><span /></div>
            <label><span>Starting from</span>
              <select aria-label="Starting from" value={shownPickup} onChange={(event) => changePickup(event.target.value as PlaceId)}>
                {places.map((place) => <option key={place.id} value={place.id}>{place.name}</option>)}
              </select>
            </label>
            <label><span>Going to</span>
              <select aria-label="Going to" value={shownDestination} onChange={(event) => changeDestination(event.target.value as PlaceId)}>
                {places.map((place) => <option key={place.id} value={place.id}>{place.name}</option>)}
              </select>
            </label>
          </div>
          {shownPickup === shownDestination && <p className="error-message" role="alert">Choose two different locations.</p>}
          <div className="trip-summary"><span><Footprints size={17} /> Follow the highlighted route</span><span><BatteryMedium size={17} /> {data ? `${Math.round(data.robot.battery)}%` : "—"}</span></div>
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
                <Button type="submit" disabled={busy || offline || pickup === destination}>{busy ? "Requesting…" : "Request guide"} <ArrowRight size={18} /></Button>
              </div>
              <small>No account needed.</small>
            </form>
          )}
          {error && <p className="error-message" role="alert">{error}</p>}
          </div>
        </aside>
      )}

      {step !== "done" && (
        <div className="wizard-overlay">
          <section className="wizard-card" role="dialog" aria-modal="true" aria-labelledby="wizard-title">
            <div className="progress-dots" aria-label={`Step ${step === "intro" ? 1 : step === "pickup" ? 2 : 3} of 3`}>
              {["intro", "pickup", "destination"].map((item, index) => <span key={item} className={item === step ? "active" : ""}>{index + 1}</span>)}
            </div>
            {step === "intro" && (
              <div className="intro-step">
                <div className="wizard-fly"><Fly /></div>
                <span className="wizard-eyebrow">Meet your campus guide</span>
                <h1 id="wizard-title">Get there with FLIH.</h1>
                <p>FLIH is a tiny-brained, four-wheeled guide that helps you navigate the E5 and E7 sixth floor.</p>
                <div className="intro-points"><span><MapPin size={18} /> Choose where you are</span><span><Navigation size={18} /> Pick where you’re going</span><span><Footprints size={18} /> Follow your route</span></div>
                <Button className="wizard-primary" onClick={() => setStep("pickup")}>Plan my route <ArrowRight size={20} /></Button>
              </div>
            )}
            {step === "pickup" && <LocationStep title="Where are you now?" description="Choose the closest room or corridor. You can change this later." value={pickup} onChange={setPickup} onBack={() => setStep("intro")} onNext={() => setStep("destination")} icon={<LocateFixed size={25} />} />}
            {step === "destination" && <LocationStep title="Where do you want to go?" description={`Starting at ${placeName(pickup)}`} value={destination} onChange={chooseDestination} onBack={() => setStep("pickup")} onNext={finishWizard} icon={<MapPin size={25} />} nextLabel="Show my route" excluded={pickup} error={error} />}
          </section>
        </div>
      )}

      {notice && <div className="toast" role="status"><Check size={18} /> {notice}<button type="button" onClick={() => setNotice("")} aria-label="Dismiss"><X size={17} /></button></div>}
    </main>
  );
}

function LocationStep({ title, description, value, onChange, onBack, onNext, icon, nextLabel = "Continue", excluded, error }: { title: string; description: string; value: PlaceId; onChange: (id: PlaceId) => void; onBack: () => void; onNext: () => void; icon: React.ReactNode; nextLabel?: string; excluded?: PlaceId; error?: string }) {
  return (
    <div className="location-step">
      <div className="wizard-icon">{icon}</div><h1 id="wizard-title">{title}</h1><p>{description}</p>
      <div className="location-list" role="radiogroup" aria-label={title}>
        {places.map((place) => (
          <button key={place.id} type="button" role="radio" aria-checked={value === place.id} disabled={place.id === excluded} className={value === place.id ? "location-option selected" : "location-option"} onClick={() => onChange(place.id)}>
            <span className="option-pin"><MapPin size={17} /></span><span><strong>{place.short}</strong><small>{place.name}</small></span><i>{value === place.id && <Check size={16} />}</i>
          </button>
        ))}
      </div>
      {error && <p className="error-message" role="alert">{error}</p>}
      <div className="wizard-actions"><Button variant="ghost" onClick={onBack}><ArrowLeft size={18} /> Back</Button><Button onClick={onNext}>{nextLabel} <ArrowRight size={18} /></Button></div>
    </div>
  );
}
