"use client";
import { useCallback, useEffect, useState } from "react";
import {
  ArrowDown,
  ArrowRight,
  BatteryMedium,
  Check,
  Clock3,
  Cpu,
  Footprints,
  Heart,
  LocateFixed,
  MapPin,
  Radio,
  RefreshCw,
  Sparkles,
  Users,
  X,
} from "lucide-react";
import type { Dashboard as DashboardData, PlaceId } from "@/lib/campus";
import { places, placeName } from "@/lib/campus";
import { Button } from "./ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from "./ui/dialog";
import { CampusMap } from "./campus-map";
import { Fly } from "./fly";
type Challenge = { id: string; question: string; hint: string };
export function Dashboard() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [connectionError, setConnectionError] = useState(false);
  const [pickup, setPickup] = useState<PlaceId>("slc");
  const [destination, setDestination] = useState<PlaceId>("e7");
  const [username, setUsername] = useState("");
  const [captchaOpen, setCaptchaOpen] = useState(false);
  const [aboutOpen, setAboutOpen] = useState(false);
  const [challenge, setChallenge] = useState<Challenge | null>(null);
  const [answer, setAnswer] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [tab, setTab] = useState("map");
  const refresh = useCallback(async () => {
    try {
      const res = await fetch("/api/flih");
      if (!res.ok) throw new Error();
      setData(await res.json());
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
    const heartbeat = () => {
      void fetch("/api/flih", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "heartbeat" }),
        keepalive: true,
      });
    };
    const timer = setInterval(heartbeat, 20_000);
    return () => clearInterval(timer);
  }, [data?.mine]);
  async function getChallenge() {
    setChallenge(null);
    setAnswer("");
    try {
      const res = await fetch("/api/flih?challenge=1");
      if (!res.ok) throw new Error();
      setChallenge(await res.json());
    } catch {
      setError("Couldn’t load the brain check. Please try again.");
    }
  }
  function beginRequest(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    if (pickup === destination) {
      setError(
        "Pick a different destination. Even a fly needs somewhere to go.",
      );
      return;
    }
    setCaptchaOpen(true);
    void getChallenge();
  }
  async function join(e: React.FormEvent) {
    e.preventDefault();
    if (!challenge) return;
    setBusy(true);
    setError("");
    try {
      const res = await fetch("/api/flih", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username,
          pickup,
          destination,
          challengeId: challenge.id,
          answer,
        }),
      });
      const result = await res.json();
      if (!res.ok) {
        setError(result.error ?? "Please try again.");
        if (result.refreshChallenge) await getChallenge();
        return;
      }
      setCaptchaOpen(false);
      setNotice(
        "You’re on the list. Your spot is saved — keep this page open for updates!",
      );
      await refresh();
    } catch {
      setError("Connection hiccup. Please try again.");
    } finally {
      setBusy(false);
    }
  }
  async function cancel() {
    setBusy(true);
    setError("");
    try {
      const res = await fetch("/api/flih", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "cancel" }),
      });
      if (!res.ok) throw new Error();
      await refresh();
      setNotice("Spot released. See you around campus!");
    } catch {
      setError("Couldn’t cancel your pickup. Please try again.");
    } finally {
      setBusy(false);
    }
  }
  const mine = data?.queue.find((e) => e.id === data.mine);
  const position = mine
    ? data!.queue.findIndex((e) => e.id === mine.id) + 1
    : 0;
  const offline = connectionError || data?.robot.status === "offline";
  function navigate(section: string) {
    setTab(section);
    document
      .getElementById(section)
      ?.scrollIntoView({ behavior: "smooth", block: "start" });
  }
  return (
    <div className="site-wrap">
      <header className="site-header">
        <a className="brand" href="#" aria-label="FLIH home">
          <Fly small />
          <span>
            FLIH<span className="brand-dot">.</span>
          </span>
        </a>
        <nav aria-label="Main navigation">
          <button
            className={tab === "map" ? "nav-active" : ""}
            onClick={() => navigate("map")}
          >
            Find the fly
          </button>
          <button
            className={tab === "how-it-works" ? "nav-active" : ""}
            onClick={() => navigate("how-it-works")}
          >
            How it works
          </button>
          <button onClick={() => setAboutOpen(true)}>
            Meet FLIH <span className="little-arrow">↗</span>
          </button>
        </nav>
        <span className="hack-badge">
          <span>✳</span> built at Hack the North
        </span>
      </header>
      <main>
        <section className="hero">
          <div className="hero-copy">
            <div className="eyebrow">
              <span className="scribble-star">✳</span> YOUR SLIGHTLY UNUSUAL
              CAMPUS GUIDE
            </div>
            <h1>
              Tiny brain.
              <br />
              <span className="underlined">Big campus.</span>
            </h1>
            <p>
              A fly brain. Four wheels. Your own Waterloo tour guide.
              <br className="desktop-break" /> Tell FLIH where to meet you.
              Then, just follow the fly.
            </p>
            <div className="hero-details">
              <span>
                <Check size={16} /> No accounts
              </span>
              <span>
                <Check size={16} /> No fares
              </span>
              <span>
                <Check size={16} /> Just fly vibes
              </span>
            </div>
          </div>
          <div className="hero-illustration">
            <div className="speech-note">
              I was built to fly.
              <br />
              Life had other plans.
            </div>
            <Fly className="hero-fly" />
            <svg
              className="hero-doodle"
              viewBox="0 0 240 60"
              aria-hidden="true"
            >
              <path
                d="M5 34q38-32 72-10t64 7q30-10 3-21t-11 34q7 13 28 5l60-17m-15-6 15 6-10 12"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeDasharray="5 5"
              />
            </svg>
            <span className="fly-caption">100% determination. 0% flight.</span>
          </div>
        </section>
        <section id="map" className="dashboard-section">
          <div className="section-heading">
            <h2>
              <span className="red-asterisk">✳</span> Where’s our little guy?
            </h2>
            <span className="live-label">
              <i className={offline ? "status-dot offline" : "status-dot"} />
              {connectionError
                ? "Reconnecting…"
                : data?.robot.demo
                  ? "Demo feed · updates every 5s"
                  : data
                    ? "Live feed · updates every 5s"
                    : "Connecting to FLIH…"}
            </span>
          </div>
          <div className="dashboard-grid">
            <div className="map-column">
              <CampusMap
                robot={data?.robot ?? null}
                pickup={mine?.pickup ?? pickup}
                destination={mine?.destination ?? destination}
                onPickup={(p) => {
                  if (!mine) setPickup(p);
                }}
              />
              <div className="robot-status paper-card">
                <div className="robot-avatar">
                  <Fly small />
                </div>
                <div className="robot-status-copy">
                  <strong>
                    FLIH <span className="version">the campus companion</span>
                  </strong>
                  <span>
                    <i
                      className={offline ? "status-dot offline" : "status-dot"}
                    />
                    {offline
                      ? "Taking a breather · robot offline"
                      : !data
                        ? "Checking in…"
                        : data.robot.status === "guiding"
                          ? "Guiding a fellow human"
                          : "Roaming around campus"}
                  </span>
                </div>
                <div className="robot-stat">
                  <BatteryMedium size={21} />
                  <strong>
                    {data ? `${Math.round(data.robot.battery)}%` : "—"}
                  </strong>
                  <span>battery</span>
                </div>
                <div className="robot-stat brain-stat">
                  <Cpu size={20} />
                  <strong>1 fly</strong>
                  <span>brain power</span>
                </div>
              </div>
            </div>
            <aside className="pickup-card paper-card">
              <span className="tape" />
              <div className="card-eyebrow">YOUR NEXT CAMPUS ADVENTURE</div>
              <h2>
                {mine ? "You’re on the list!" : "Need a little guidance?"}
              </h2>
              <p className="card-intro">
                {mine
                  ? "One small fly. Coming your way."
                  : "Get picked up. Get shown around."}
              </p>
              {mine ? (
                <div className="reservation">
                  <div className="queue-position">
                    <span>YOUR SPOT</span>
                    <strong>#{position}</strong>
                    <p>
                      {position === 1
                        ? "You’re next, human."
                        : `${position - 1} ${position === 2 ? "human" : "humans"} ahead of you.`}
                    </p>
                  </div>
                  <h3>Hey, {mine.username}!</h3>
                  <p>
                    <MapPin size={17} />
                    {placeName(mine.pickup)}
                  </p>
                  <ArrowDown size={18} />
                  <p>
                    <Footprints size={17} />
                    {placeName(mine.destination)}
                  </p>
                  <div className="reservation-note">
                    {data?.robot.demo
                      ? "This is a demo reservation. A real robot won’t arrive yet."
                      : "Stay near your pickup spot and keep this page open. Spots expire after 90 seconds away."}
                  </div>
                  <Button
                    variant="outline"
                    className="w-full"
                    disabled={busy}
                    onClick={() => void cancel()}
                  >
                    <X size={18} />{" "}
                    {busy ? "Releasing spot…" : "Leave the queue"}
                  </Button>
                </div>
              ) : (
                <form onSubmit={beginRequest}>
                  <label htmlFor="username">
                    What should we call you? <span>(your fly alias)</span>
                  </label>
                  <input
                    id="username"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    placeholder="e.g. goose_whisperer"
                    required
                    minLength={2}
                    maxLength={20}
                    pattern="[\p{L}\p{N}_ .\-]{2,20}"
                    autoComplete="nickname"
                  />
                  <div className="route-inputs">
                    <div className="route-field">
                      <span className="field-marker pickup-marker" />
                      <div>
                        <label htmlFor="pickup">Meet me at</label>
                        <select
                          id="pickup"
                          value={pickup}
                          onChange={(e) => setPickup(e.target.value as PlaceId)}
                        >
                          {places.map((p) => (
                            <option key={p.id} value={p.id}>
                              {p.name}
                            </option>
                          ))}
                        </select>
                      </div>
                    </div>
                    <div className="route-field">
                      <MapPin size={18} className="destination-marker" />
                      <div>
                        <label htmlFor="destination">Take me to</label>
                        <select
                          id="destination"
                          value={destination}
                          onChange={(e) =>
                            setDestination(e.target.value as PlaceId)
                          }
                        >
                          {places.map((p) => (
                            <option key={p.id} value={p.id}>
                              {p.name}
                            </option>
                          ))}
                        </select>
                      </div>
                    </div>
                  </div>
                  <div className="wait-estimate">
                    <Clock3 size={18} />
                    <span>
                      {data
                        ? data.queue.length === 0
                          ? "You could be first in line"
                          : `${data.queue.length} ${data.queue.length === 1 ? "human" : "humans"} in line`
                        : "Checking the queue…"}
                    </span>
                    <span className="free-tag">always free</span>
                  </div>
                  <Button
                    className="join-button w-full"
                    type="submit"
                    disabled={!data || offline}
                  >
                    Join the queue <ArrowRight size={21} />
                  </Button>
                  <p className="captcha-disclaimer">
                    One tiny brain check, then you’re in.
                  </p>
                </form>
              )}
              {error && !captchaOpen && (
                <p className="error-message" role="alert">
                  {error}
                </p>
              )}
              <div className="privacy-note">
                <Heart size={15} /> No sign-up. Just a name and a destination.
              </div>
            </aside>
          </div>
          {notice && (
            <div className="notice" role="status">
              <Check size={18} />
              {notice}
              <button
                aria-label="Dismiss notification"
                onClick={() => setNotice("")}
              >
                <X size={18} />
              </button>
            </div>
          )}
          <div className="below-grid">
            <div className="queue-card paper-card">
              <div className="queue-heading">
                <h3>
                  <Users size={21} /> The human queue{" "}
                  <span className="queue-count">
                    {data?.queue.length ?? "—"}
                  </span>
                </h3>
                <span>first come, first guided.</span>
              </div>
              {!data ? (
                <div className="empty-queue">
                  {connectionError
                    ? "The queue is temporarily unavailable. Reconnecting…"
                    : "Checking who’s waiting…"}
                </div>
              ) : data.queue.length === 0 ? (
                <div className="empty-queue">
                  <span className="empty-doodle">☷</span>
                  <div>
                    No humans in line. A rare campus phenomenon.
                    <br />
                    <span>
                      Grab the first spot. FLIH could use the company.
                    </span>
                  </div>
                  <span className="empty-arrow">↗</span>
                </div>
              ) : (
                <ol className="queue-list">
                  {data.queue.map((entry, i) => (
                    <li
                      key={entry.id}
                      className={entry.id === data.mine ? "is-me" : ""}
                    >
                      <span className="queue-number">{i + 1}</span>
                      <div>
                        <strong>
                          {entry.username}
                          {entry.id === data.mine && <em>you!</em>}
                        </strong>
                        <span>
                          {placeName(entry.pickup)} →{" "}
                          {placeName(entry.destination)}
                        </span>
                      </div>
                      <span className="queue-state">
                        {i === 0 ? "up next" : "waiting"}
                      </span>
                    </li>
                  ))}
                </ol>
              )}
            </div>
            <div className="sticky-note">
              <span className="pin" />
              <span className="note-title">a note from the brain</span>
              <p>
                “I have roughly 140,000 neurons.
                <br />
                And every single one is trying
                <br />
                to find your lecture hall.”
              </p>
              <span className="note-signature">— FLIH, probably</span>
              <Sparkles className="note-sparkle" size={26} />
            </div>
          </div>
        </section>
        <section id="how-it-works" className="how-section">
          <div className="how-title">
            <h2>Small brain. Simple plan.</h2>
            <p>Like a rideshare. Except you walk. And it’s a fly.</p>
          </div>
          <div className="steps">
            <div className="step">
              <span className="step-number">1</span>
              <div>
                <h3>Drop your pin</h3>
                <p>
                  Pick your meeting spot and
                  <br />
                  where you want to end up.
                </p>
              </div>
              <MapPin className="step-icon" />
            </div>
            <span className="step-arrow">⤳</span>
            <div className="step">
              <span className="step-number">2</span>
              <div>
                <h3>Pass the vibe check</h3>
                <p>
                  Choose an alias. Prove you’re
                  <br />
                  more human than our robot.
                </p>
              </div>
              <Cpu className="step-icon" />
            </div>
            <span className="step-arrow">⤳</span>
            <div className="step">
              <span className="step-number">3</span>
              <div>
                <h3>Follow the fly</h3>
                <p>
                  Wait your turn, meet FLIH,
                  <br />
                  and take a little campus stroll.
                </p>
              </div>
              <Footprints className="step-icon" />
            </div>
          </div>
        </section>
      </main>
      <footer>
        <span className="footer-brand">FLIH.</span>
        <span>Made with questionable ambition & a very small brain.</span>
        <span>
          Waterloo, ON <span className="footer-star">✳</span> Hack the North
        </span>
      </footer>
      <Dialog
        open={captchaOpen}
        onOpenChange={(open) => {
          if (!busy) setCaptchaOpen(open);
        }}
      >
        <DialogContent>
          <div className="modal-icon">
            <Cpu size={28} />
          </div>
          <DialogTitle className="modal-title">
            A quick human check.
          </DialogTitle>
          <DialogDescription className="modal-description">
            Our driver is a fly brain on wheels. Let’s make sure at least one of
            you can do math.
          </DialogDescription>
          <form onSubmit={join}>
            <div className="challenge-question">
              {challenge?.question ?? "The fly is thinking…"}
            </div>
            {challenge && <p className="challenge-hint">{challenge.hint}</p>}
            <label htmlFor="captcha-answer">Your answer</label>
            <input
              id="captcha-answer"
              inputMode="numeric"
              autoComplete="off"
              required
              value={answer}
              onChange={(e) => setAnswer(e.target.value)}
              placeholder="An alarming number…"
              disabled={!challenge || busy}
            />
            {error && (
              <p role="alert" className="error-message">
                {error}
              </p>
            )}
            <Button
              className="w-full mt-5"
              disabled={!challenge || busy}
              type="submit"
            >
              {busy ? "Saving your spot…" : "I think, therefore I queue"}{" "}
              <ArrowRight size={18} />
            </Button>
            <button
              className="refresh-challenge"
              type="button"
              disabled={busy}
              onClick={() => {
                setError("");
                void getChallenge();
              }}
            >
              <RefreshCw size={14} /> Give me another crisis
            </button>
          </form>
          <p className="modal-footnote">
            A playful captcha, not a philosophy degree.
          </p>
        </DialogContent>
      </Dialog>
      <Dialog open={aboutOpen} onOpenChange={setAboutOpen}>
        <DialogContent>
          <Fly className="about-fly" />
          <DialogTitle className="modal-title">
            Meet your tiniest tour guide.
          </DialogTitle>
          <DialogDescription className="modal-description">
            FLIH is a Hack the North project exploring a fly-inspired AI brain
            in a four-wheeled campus robot.
          </DialogDescription>
          <div className="about-details">
            <p>
              <Cpu size={20} /> Fly-inspired movement decisions
            </p>
            <p>
              <LocateFixed size={20} /> Cameras, 2D lidar & GPS
            </p>
            <p>
              <Radio size={20} /> A website to bring humans along
            </p>
          </div>
          <div className="reservation-note">
            {data?.robot.demo !== false
              ? "You’re exploring the demo. The queue is shared, but the illustrated position is simulated. Hardware navigation and real pickups aren’t connected yet."
              : "Hardware telemetry is connected. The map is an illustration; follow campus signs and the robot’s guidance."}
          </div>
          <p className="modal-footnote">
            Four wheels. Zero wings. A whole lot of potential.
          </p>
        </DialogContent>
      </Dialog>
    </div>
  );
}
