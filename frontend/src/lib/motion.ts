/**
 * Motion tokens: one easing curve and three durations, used everywhere.
 * CSS mirrors these as --pw-ease / --pw-dur-1..3 in global.css; keep both in sync.
 * Reduced motion is handled globally (MotionConfig reducedMotion="user" + a CSS media query).
 */
const ease = [0.22, 1, 0.36, 1] as const;

export const MOTION = {
  ease,
  /** Seconds, for the `motion` library. */
  s: { fast: 0.15, base: 0.25, slow: 0.45 },
  /** Milliseconds, for Mantine transition props. */
  ms: { fast: 150, base: 250, slow: 450 },
  css: { ease: `cubic-bezier(${ease.join(', ')})` },
  /** Delay between items in a staggered entrance. */
  stagger: 0.05,
} as const;
