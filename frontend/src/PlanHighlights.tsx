import { AnimatePresence, motion } from "framer-motion";
import { Sparkles } from "lucide-react";
import type { Plan } from "./types";
export default function PlanHighlights({ plan }: { plan: Plan }) {
  const highlights =
    plan.mode === "ai" ? plan.highlights?.slice(0, 3) : undefined;
  return (
    <div className="highlights-slot">
      <AnimatePresence initial={false} mode="wait">
        {highlights?.length ? (
          <motion.div
            key="highlights"
            data-testid="plan-highlights"
            aria-label="AI plan highlights"
            className="plan-highlights"
            variants={{
              hidden: {},
              visible: { transition: { staggerChildren: 0.09 } },
            }}
            initial="hidden"
            animate="visible"
            exit={{ opacity: 0, transition: { duration: 0.15 } }}
          >
            {highlights.map((text, i) => (
              <motion.article
                key={i}
                className={`highlight-card tone-${i}`}
                title={text}
                variants={{
                  hidden: { opacity: 0, y: 6 },
                  visible: { opacity: 1, y: 0, transition: { duration: 0.3 } },
                }}
              >
                <Sparkles size={11} aria-hidden="true" />
                <span>{text}</span>
              </motion.article>
            ))}
          </motion.div>
        ) : (
          <motion.div
            key="preview"
            className="highlights-preview"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0, transition: { duration: 0.15 } }}
          >
            <Sparkles size={18} />
            <div>
              <strong>
                {plan.mode === "baseline"
                  ? "See the connections."
                  : "Your loaded week is on the map."}
              </strong>
              <p>
                {plan.mode === "baseline"
                  ? "AI finds the next paying leg across the fleet."
                  : "Select a truck to inspect its full journey."}
              </p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
