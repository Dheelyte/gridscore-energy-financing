import { ArrowLeft, ArrowRight, Compass, X } from "lucide-react";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useLayoutEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { Button } from "@/components/ui/button";

const SEEN_KEY = "gridscore.tour.v1";
const TOOLTIP_WIDTH = 340;

export interface TourStep {
  id: string;
  title: string;
  body: ReactNode;
  /** CSS selector for the element to spotlight. Omit for a centered step. */
  selector?: string;
}

/** The product tour. Anchored steps point at the persistent top nav, so it works
 *  from any page and automatically adapts to the signed-in role (steps whose
 *  target isn't rendered for that role are skipped). */
const TOUR_STEPS: TourStep[] = [
  {
    id: "welcome",
    title: "Welcome to GridScore AI",
    body: (
      <>
        Across Africa, pay-as-you-go energy lenders each hold a thin, siloed record of who repays —
        so a reliable customer who is new to <em>you</em> looks just like a risky one.
        <br />
        <br />
        GridScore is a <strong>shared repayment data cooperative</strong>: lenders contribute
        anonymised histories and get back an <strong>Energy Credit Score</strong> that is sharper
        than any one of them could compute alone. This 60-second tour shows where everything lives.
      </>
    ),
  },
  {
    id: "console",
    selector: '[data-tour="nav-console"]',
    title: "1 · Operator console",
    body: (
      <>
        Click <strong>Console</strong> to look up a customer and score them. You get an Energy
        Credit Score, a risk tier, an approve/reject decision, and the SHAP reason codes behind it.
        This is where the headline <strong>reject → approve flip</strong> happens: score the
        borderline demo customer <em>solo</em> vs <em>pooled</em> and watch the decision change.
      </>
    ),
  },
  {
    id: "portfolio",
    selector: '[data-tour="nav-portfolio"]',
    title: "2 · Portfolio",
    body: (
      <>
        <strong>Portfolio</strong> shows your book&apos;s risk distribution — score tiers, approval
        rates and default-risk mix across all your customers at a glance.
      </>
    ),
  },
  {
    id: "upload",
    selector: '[data-tour="nav-upload"]',
    title: "3 · Contribute data",
    body: (
      <>
        <strong>Upload data</strong> is how an operator feeds repayment events into the cooperative.
        Identities are turned into salted hashes at the door — raw phone numbers and IDs are never
        stored — and every ingest is de-duplicated and audited.
      </>
    ),
  },
  {
    id: "lender",
    selector: '[data-tour="nav-lender"]',
    title: "The network effect",
    body: (
      <>
        <strong>Lender analytics</strong> is the proof the cooperative works: a chart of model
        accuracy (AUC) <strong>rising as more operators join the pool</strong>. Every operator who
        contributes makes everyone&apos;s scoring better — that&apos;s the moat.
      </>
    ),
  },
  {
    id: "admin",
    selector: '[data-tour="nav-admin"]',
    title: "Platform admin",
    body: (
      <>
        <strong>Admin</strong> is the platform view: onboard operators, manage users and API keys,
        inspect the active model, and read the <strong>immutable audit log</strong> — every score
        and data access, tamper-proof.
      </>
    ),
  },
  {
    id: "relaunch",
    selector: '[data-tour="launch"]',
    title: "Take it again anytime",
    body: (
      <>
        Your <strong>role</strong> decides which of these you can see. Re-open this tour whenever
        you like from this <strong>Tour</strong> button. Everything here runs on{" "}
        <strong>synthetic data</strong> — clearly labelled, safe to click around.
      </>
    ),
  },
];

interface TourState {
  start: () => void;
  active: boolean;
}

const TourContext = createContext<TourState | null>(null);

export function TourProvider({ children }: { children: ReactNode }) {
  const [steps, setSteps] = useState<TourStep[]>([]);
  const [index, setIndex] = useState(-1);
  const active = index >= 0 && index < steps.length;

  const start = useCallback(() => {
    // Keep only steps whose target is actually on the page (role-aware).
    const visible = TOUR_STEPS.filter((s) => !s.selector || document.querySelector(s.selector));
    setSteps(visible);
    setIndex(visible.length > 0 ? 0 : -1);
  }, []);

  const stop = useCallback(() => {
    setIndex(-1);
    try {
      localStorage.setItem(SEEN_KEY, "1");
    } catch {
      /* ignore storage failures (private mode etc.) */
    }
  }, []);

  const next = useCallback(() => {
    setIndex((i) => {
      if (i + 1 >= steps.length) {
        try {
          localStorage.setItem(SEEN_KEY, "1");
        } catch {
          /* ignore */
        }
        return -1;
      }
      return i + 1;
    });
  }, [steps.length]);

  const prev = useCallback(() => setIndex((i) => Math.max(0, i - 1)), []);

  const value = useMemo(() => ({ start, active }), [start, active]);

  return (
    <TourContext.Provider value={value}>
      {children}
      {active && (
        <TourOverlay
          step={steps[index]}
          index={index}
          total={steps.length}
          onNext={next}
          onPrev={prev}
          onClose={stop}
        />
      )}
    </TourContext.Provider>
  );
}

function TourOverlay({
  step,
  index,
  total,
  onNext,
  onPrev,
  onClose,
}: {
  step: TourStep;
  index: number;
  total: number;
  onNext: () => void;
  onPrev: () => void;
  onClose: () => void;
}) {
  const [rect, setRect] = useState<DOMRect | null>(null);

  useLayoutEffect(() => {
    if (!step.selector) {
      setRect(null);
      return;
    }
    const update = () => {
      const el = document.querySelector(step.selector!);
      if (el) {
        el.scrollIntoView({ block: "nearest", inline: "nearest" });
        setRect(el.getBoundingClientRect());
      } else {
        setRect(null);
      }
    };
    update();
    window.addEventListener("resize", update);
    window.addEventListener("scroll", update, true);
    return () => {
      window.removeEventListener("resize", update);
      window.removeEventListener("scroll", update, true);
    };
  }, [step]);

  // Keyboard: Esc closes, arrows navigate.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      else if (e.key === "ArrowRight" || e.key === "Enter") onNext();
      else if (e.key === "ArrowLeft") onPrev();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose, onNext, onPrev]);

  const isLast = index === total - 1;
  const pad = 6;

  // Tooltip position: below the target (nav sits near the top, so room is ample),
  // clamped to the viewport; centered when there is no anchor.
  const tooltipStyle: React.CSSProperties = rect
    ? {
        position: "fixed",
        top: rect.bottom + 12,
        left: Math.min(Math.max(rect.left, 16), window.innerWidth - TOOLTIP_WIDTH - 16),
        width: TOOLTIP_WIDTH,
      }
    : {
        position: "fixed",
        top: "50%",
        left: "50%",
        width: TOOLTIP_WIDTH,
        transform: "translate(-50%, -50%)",
      };

  return (
    <div className="fixed inset-0 z-[60]" role="dialog" aria-modal="true" aria-label="Product tour">
      {/* Dimmer. When anchored, a big box-shadow cuts a hole around the target. */}
      {rect ? (
        <div
          className="pointer-events-none fixed rounded-lg ring-2 ring-primary transition-all duration-200"
          style={{
            top: rect.top - pad,
            left: rect.left - pad,
            width: rect.width + pad * 2,
            height: rect.height + pad * 2,
            boxShadow: "0 0 0 9999px rgba(2, 6, 23, 0.65)",
          }}
        />
      ) : (
        <div className="fixed inset-0 bg-[rgba(2,6,23,0.65)]" onClick={onClose} />
      )}

      <div
        style={tooltipStyle}
        className="rounded-lg border border-border bg-card p-4 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-2 flex items-start justify-between gap-2">
          <div className="flex items-center gap-2">
            <Compass className="h-4 w-4 text-primary" aria-hidden />
            <h2 className="text-sm font-semibold">{step.title}</h2>
          </div>
          <button
            onClick={onClose}
            aria-label="Close tour"
            className="rounded p-0.5 text-muted-foreground hover:text-foreground"
          >
            <X className="h-4 w-4" aria-hidden />
          </button>
        </div>
        <div className="text-sm leading-relaxed text-muted-foreground">{step.body}</div>

        <div className="mt-4 flex items-center justify-between">
          <div className="flex items-center gap-1.5" aria-hidden>
            {Array.from({ length: total }).map((_, i) => (
              <span
                key={i}
                className={
                  i === index
                    ? "h-1.5 w-4 rounded-full bg-primary"
                    : "h-1.5 w-1.5 rounded-full bg-border"
                }
              />
            ))}
          </div>
          <div className="flex items-center gap-2">
            {index > 0 && (
              <Button variant="ghost" size="sm" onClick={onPrev}>
                <ArrowLeft className="h-4 w-4" aria-hidden /> Back
              </Button>
            )}
            <Button size="sm" onClick={isLast ? onClose : onNext}>
              {isLast ? (
                "Done"
              ) : (
                <>
                  Next <ArrowRight className="h-4 w-4" aria-hidden />
                </>
              )}
            </Button>
          </div>
        </div>
        <p className="mt-2 text-right text-[0.65rem] text-muted-foreground">
          Step {index + 1} of {total} · Esc to skip
        </p>
      </div>
    </div>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export function useTour(): TourState {
  const ctx = useContext(TourContext);
  if (!ctx) throw new Error("useTour must be used within a TourProvider");
  return ctx;
}

/** True once the user has completed/skipped the tour at least once. */
// eslint-disable-next-line react-refresh/only-export-components
export function hasSeenTour(): boolean {
  try {
    return localStorage.getItem(SEEN_KEY) === "1";
  } catch {
    return true; // if storage is unavailable, don't nag
  }
}
