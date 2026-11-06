import type { ToolId } from "../art/sprites.ts";

/** What an answer of this tier turns up in the ground. */
export type FindId = "carvao" | "ferro" | "cobre" | "ouro" | "rubi" | "diamante";

export type Tier = {
  id: number;
  /** Rarity label shown to the player. */
  label: string;
  /** Tool that digs for an answer of this rarity. */
  tool: ToolId;
  toolName: string;
  /** Fixed metres (= points) this tier digs. Same scale as Krillion: 10 to 100. */
  meters: number;
  /** Lowest rarity percentile (0–1) that lands in this tier. */
  minRarity: number;
  find: FindId;
  /** "Você encontrou …" */
  findName: string;
  fill: string;
};

/**
 * Six fixed steps, 25 m to 100 m. Even the obvious answer digs something, so the
 * player is never pinned to the first layer; a perfect seven reaches 700 m.
 *
 * `minRarity` are even deciles of the within-prompt rarity percentile
 * (tools/dataset/measure.py: uniform_rarity), so every band exists in every
 * prompt: 10% of a pool always reaches 100 m, and the last answer of any pool is
 * a real 1.0. Same ladder everywhere, whatever the pool size.
 */
export const TIERS: Tier[] = [
  {
    id: 1,
    label: "Óbvia",
    tool: "pa",
    toolName: "Pá",
    meters: 25,
    minRarity: 0,
    find: "carvao",
    findName: "carvão",
    fill: "#8f8274",
  },
  {
    id: 2,
    label: "Comum",
    tool: "aspirador",
    toolName: "Aspirador",
    meters: 40,
    minRarity: 0.1,
    find: "ferro",
    findName: "ferro",
    fill: "#d9d2c3",
  },
  {
    id: 3,
    label: "Boa",
    tool: "escavadeira",
    toolName: "Escavadeira",
    meters: 55,
    minRarity: 0.3,
    find: "cobre",
    findName: "cobre",
    fill: "#f2b65a",
  },
  {
    id: 4,
    label: "Rara",
    tool: "broca",
    toolName: "Broca",
    meters: 70,
    minRarity: 0.5,
    find: "ouro",
    findName: "ouro",
    fill: "#e2733b",
  },
  {
    id: 5,
    label: "Raríssima",
    tool: "broca-ultra",
    toolName: "Broca ultra",
    meters: 85,
    minRarity: 0.7,
    find: "rubi",
    findName: "um rubi",
    fill: "#d8344f",
  },
  {
    id: 6,
    label: "Uma em um milhão",
    tool: "dinamite",
    toolName: "Dinamite",
    meters: 100,
    minRarity: 0.9,
    find: "diamante",
    findName: "um diamante",
    fill: "#2fd4c8",
  },
];

export const MAX_DEPTH = 700;

export function clamp01(value: number): number {
  return Math.min(1, Math.max(0, Number.isFinite(value) ? value : 0));
}

/** Tier of a single answer, from its rarity percentile. */
export function tierForRarity(rarity: number): Tier {
  const p = clamp01(rarity);
  let tier = TIERS[0];
  for (const item of TIERS) if (p >= item.minRarity) tier = item;
  return tier;
}

/** Points for one answer. Points and metres are the same number. */
export const pointsFor = (rarity: number) => tierForRarity(rarity).meters;

/** One answer's contribution to the shaft, in whole metres (10 to 100). */
export const dig = (rarity: number) => tierForRarity(rarity).meters;

/** Overall rank of a finished dive, from its total depth. */
export function tierForDepth(depth: number): Tier {
  const average = depth / 7;
  let tier = TIERS[0];
  for (const item of TIERS) if (average >= item.meters) tier = item;
  return tier;
}

export function styleScale(oneIn: number | null): string {
  if (!oneIn || oneIn < 2) return "1 em 2";
  if (oneIn >= 1000) return `1 em ${Math.round(oneIn / 100) * 100}`;
  if (oneIn >= 100) return `1 em ${Math.round(oneIn / 10) * 10}`;
  return `1 em ${Math.round(oneIn)}`;
}
