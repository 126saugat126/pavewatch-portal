import { animate, motion, useReducedMotion } from 'motion/react';
import { useEffect, useRef, type ReactNode } from 'react';
import { MOTION } from '../lib/motion';

/**
 * A number that counts up when it first appears and glides to new values when the data changes
 * (e.g. after a background refresh). Renders the final value immediately for reduced motion,
 * and always exposes the real value to assistive tech.
 */
export function CountUp({ value, format = (n) => String(Math.round(n)) }: { value: number; format?: (n: number) => string }) {
  const ref = useRef<HTMLSpanElement>(null);
  const shown = useRef(0);
  const reduce = useReducedMotion();

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (reduce) {
      shown.current = value;
      el.textContent = format(value);
      return;
    }
    const controls = animate(shown.current, value, {
      duration: shown.current === 0 ? 0.9 : 0.6,
      ease: MOTION.ease,
      onUpdate: (n) => {
        shown.current = n;
        el.textContent = format(n);
      },
    });
    return () => controls.stop();
    // `format` is expected to be stable in behaviour; re-running on identity change would restart the count.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value, reduce]);

  return (
    <span ref={ref} aria-label={format(value)} className="pw-tabular">
      {reduce ? format(value) : format(0)}
    </span>
  );
}

/** Renders numbers through CountUp; anything else passes through unchanged. */
export function AnimatedValue({ value }: { value: ReactNode }) {
  return typeof value === 'number' ? <CountUp value={value} /> : <>{value}</>;
}

/** Fade + slight rise when a page mounts. Keyed by the router on pathname, so filters and query changes don't replay it. */
export function PageTransition({ children }: { children: ReactNode }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: MOTION.s.slow, ease: MOTION.ease }}
    >
      {children}
    </motion.div>
  );
}
