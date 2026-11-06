/** Deterministic selection so the same date or seed always deals the same dive. */
import type { Prompt } from "./types";

export function hashSeed(input: string): number {
  let hash = 2166136261;
  for (let i = 0; i < input.length; i += 1) {
    hash ^= input.charCodeAt(i);
    hash = Math.imul(hash, 16777619);
  }
  return hash >>> 0;
}

export function mulberry32(seed: number): () => number {
  let state = seed >>> 0;
  return () => {
    state = (state + 0x6d2b79f5) >>> 0;
    let t = state;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function shuffle<T>(items: T[], random: () => number): T[] {
  const copy = items.slice();
  for (let i = copy.length - 1; i > 0; i -= 1) {
    const j = Math.floor(random() * (i + 1));
    [copy[i], copy[j]] = [copy[j], copy[i]];
  }
  return copy;
}

/** Seven prompts, one per category where possible, stable for a seed. */
export function selectPrompts(prompts: Prompt[], seed: number, count = 7): Prompt[] {
  const random = mulberry32(seed);
  const shuffled = shuffle(prompts, random);
  const picked: Prompt[] = [];
  const seenCategories = new Set<string>();
  for (const prompt of shuffled) {
    if (picked.length >= count) break;
    if (seenCategories.has(prompt.cat)) continue;
    seenCategories.add(prompt.cat);
    picked.push(prompt);
  }
  for (const prompt of shuffled) {
    if (picked.length >= count) break;
    if (picked.includes(prompt)) continue;
    picked.push(prompt);
  }
  return picked;
}

/** The number a dive label carries ("semente 8842" → 8842), or null. */
export function seedFromLabel(label: string): number | null {
  const digits = /semente\s+(\d{1,4})/.exec(label)?.[1];
  if (!digits) return null;
  const seed = Number(digits);
  return seed >= 1 && seed <= 9999 ? seed : null;
}

/**
 * A seed nobody chose: 1–9999, drawn from the platform RNG.
 * Used by the unlimited mode, which only tells the player the number at the end.
 */
export function randomSeed(): number {
  const top = 9999;
  if (typeof crypto !== "undefined" && typeof crypto.getRandomValues === "function") {
    const buffer = new Uint32Array(1);
    crypto.getRandomValues(buffer);
    return (buffer[0] % top) + 1;
  }
  return Math.floor(Math.random() * top) + 1;
}

export function todayKey(now = new Date()): string {
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

export function dailySeed(label: string): number {
  return hashSeed(`garimpo:${label}`);
}

export function prettyDate(label: string): string {
  const [, month, day] = label.split("-");
  const months = [
    "jan",
    "fev",
    "mar",
    "abr",
    "mai",
    "jun",
    "jul",
    "ago",
    "set",
    "out",
    "nov",
    "dez",
  ];
  return `${day} ${months[Number(month) - 1] ?? ""}`;
}
