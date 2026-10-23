/**
 * A model label counts as abnormal unless it is a normal beat estimate or an
 * inconclusive (poor-signal) result. Anything else is an ectopic/abnormal beat
 * class that warrants a "take this to a clinician" nudge.
 *
 * Single source of truth shared by the ECG Lab and the live ECG test so the
 * clinical definition of "abnormal" lives in exactly one place.
 */
export const isAbnormalLabel = (label: string | null | undefined): boolean =>
  !!label && !/^(normal|inconclusive)/i.test(label.trim());
