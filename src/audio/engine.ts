import type { ToolId } from "../art/sprites.ts";
import type { DigTiming } from "../game/score.ts";
import { buildDig, buildSting, createOutputChain, MASTER_LEVEL, type DigVoice } from "./dig.ts";

/**
 * Procedural audio: no files, everything synthesized at runtime.
 * Everything runs through a compressor/limiter (peak ≤ -3 dBFS) and only starts after a gesture.
 */
export class MineAudio {
  private ctx: AudioContext | null = null;
  private master: GainNode | null = null;
  private noise: AudioBuffer | null = null;
  private enabled = true;
  private digVoice: DigVoice | null = null;
  private digTool: ToolId | null = null;

  setEnabled(value: boolean): void {
    this.enabled = value;
    if (!value) {
      this.stopDig();
      this.silence();
    } else if (this.master && this.ctx) {
      this.master.gain.cancelScheduledValues(this.ctx.currentTime);
      this.master.gain.setTargetAtTime(MASTER_LEVEL, this.ctx.currentTime, 0.02);
    }
  }

  /**
   * Starts the dig sound for `tool`, following the dig's timeline: the dig
   * itself up to the impact, then the find sting. Calling it again replaces the
   * previous one.
   */
  dig(tool: ToolId, timing: DigTiming): void {
    const ctx = this.ensure();
    if (!ctx || !this.master) return;
    this.digVoice?.stop(ctx.currentTime);
    const voice = buildDig(
      ctx,
      this.master,
      tool,
      ctx.currentTime + 0.01,
      (timing.charge + timing.travel) / 1000,
      timing.charge / 1000,
    );
    this.digVoice = voice;
    this.digTool = tool;
    const left = Math.max(0, voice.end - ctx.currentTime) * 1000 + 200;
    setTimeout(() => {
      if (this.digVoice === voice) this.digVoice = null;
    }, left);
  }

  /** Stops any running dig sound quickly (≈80 ms fade), e.g. when the player skips the animation. */
  stopDig(): void {
    if (this.digVoice && this.ctx) this.digVoice.stop(this.ctx.currentTime);
    this.digVoice = null;
  }

  /**
   * The player skipped the animation. Before the impact the dig is cut and the
   * find sting plays right away; after it, the sting is already ringing and is
   * left alone.
   */
  skipDig(): void {
    const ctx = this.ctx;
    const voice = this.digVoice;
    if (!ctx || !this.master || !voice || !this.digTool) return;
    if (ctx.currentTime >= voice.impact - 0.05) return;
    voice.stop(ctx.currentTime);
    this.digVoice = null;
    buildSting(ctx, this.master, this.digTool, ctx.currentTime + 0.03);
  }

  private silence(): void {
    if (this.master && this.ctx) {
      this.master.gain.cancelScheduledValues(this.ctx.currentTime);
      this.master.gain.setTargetAtTime(0, this.ctx.currentTime, 0.02);
    }
  }

  private ensure(): AudioContext | null {
    if (!this.enabled) return null;
    if (this.ctx) {
      if (this.ctx.state === "suspended") void this.ctx.resume();
      return this.ctx;
    }
    // SAFETY: Safari exposes only the prefixed constructor; both share the same
    // AudioContext interface, which is all this module uses.
    const Ctor =
      window.AudioContext ??
      (window as Window & { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
    if (!Ctor) return null;
    this.ctx = new Ctor();
    this.master = this.ctx.createGain();
    this.master.gain.value = MASTER_LEVEL;
    this.master.connect(createOutputChain(this.ctx, this.ctx.destination));
    const frames = Math.floor(this.ctx.sampleRate * 0.4);
    const buffer = this.ctx.createBuffer(1, frames, this.ctx.sampleRate);
    const data = buffer.getChannelData(0);
    let last = 0;
    for (let i = 0; i < frames; i += 1) {
      const white = Math.random() * 2 - 1;
      last = last * 0.55 + white * 0.45;
      data[i] = last;
    }
    this.noise = buffer;
    return this.ctx;
  }

  private swell(at: number, duration: number, peak: number): GainNode | null {
    const ctx = this.ctx;
    if (!ctx || !this.master) return null;
    const gain = ctx.createGain();
    gain.gain.setValueAtTime(0.0001, at);
    gain.gain.exponentialRampToValueAtTime(peak, at + 0.008);
    gain.gain.exponentialRampToValueAtTime(0.0001, at + duration);
    gain.connect(this.master);
    return gain;
  }

  private burst(
    at: number,
    duration: number,
    peak: number,
    type: BiquadFilterType,
    frequency: number,
    q = 1,
  ): void {
    const ctx = this.ctx;
    if (!ctx || !this.noise) return;
    const source = ctx.createBufferSource();
    source.buffer = this.noise;
    const filter = ctx.createBiquadFilter();
    filter.type = type;
    filter.frequency.setValueAtTime(frequency, at);
    filter.frequency.exponentialRampToValueAtTime(Math.max(80, frequency * 0.35), at + duration);
    filter.Q.value = q;
    const gain = this.swell(at, duration, peak);
    if (!gain) return;
    source.connect(filter).connect(gain);
    source.start(at);
    source.stop(at + duration + 0.05);
  }

  private tone(
    at: number,
    duration: number,
    peak: number,
    frequency: number,
    type: OscillatorType = "sine",
    glide = 1,
  ): void {
    const ctx = this.ctx;
    if (!ctx) return;
    const osc = ctx.createOscillator();
    osc.type = type;
    osc.frequency.setValueAtTime(frequency, at);
    if (glide !== 1) osc.frequency.exponentialRampToValueAtTime(frequency * glide, at + duration);
    const gain = this.swell(at, duration, peak);
    if (!gain) return;
    osc.connect(gain);
    osc.start(at);
    osc.stop(at + duration + 0.05);
  }

  /** Pickaxe into rock. Hard, short, woody. */
  strike(points: number): void {
    const ctx = this.ensure();
    if (!ctx) return;
    const at = ctx.currentTime + 0.01;
    const weight = 0.05 + Math.min(0.06, points * 0.006);
    this.burst(at, 0.14, weight, "bandpass", 1500, 1.1);
    this.tone(at, 0.1, weight * 0.8, 118, "sine", 0.6);
    this.tone(at + 0.01, 0.06, weight * 0.3, 320, "triangle", 0.7);
  }

  /** Gem found: two detuned partials, long decay. Higher tiers ring brighter. */
  gem(tier: number): void {
    const ctx = this.ensure();
    if (!ctx) return;
    const at = ctx.currentTime + 0.02;
    const base = [523.25, 587.33, 659.25, 783.99, 880, 1046.5][Math.min(5, Math.max(0, tier - 1))];
    this.tone(at, 0.9, 0.05, base, "sine");
    this.tone(at + 0.01, 0.75, 0.035, base * 1.5, "sine");
    this.tone(at + 0.02, 0.5, 0.02, base * 2.02, "triangle");
  }

  /** Stone crumbling as the shaft deepens. */
  crumble(meters: number): void {
    const ctx = this.ensure();
    if (!ctx) return;
    const at = ctx.currentTime + 0.01;
    const depth = Math.min(1, meters / 700);
    this.burst(at + 0.06, 0.5, 0.03 + depth * 0.03, "lowpass", 900 - depth * 500, 0.7);
    this.tone(at + 0.08, 0.45, 0.02 + depth * 0.02, 62 - depth * 18, "sine", 0.82);
  }

  tick(): void {
    const ctx = this.ensure();
    if (!ctx) return;
    this.tone(ctx.currentTime + 0.005, 0.035, 0.012, 1180, "square", 1);
  }

  /** The dive is over. Down, then settled. */
  bottom(reached: boolean): void {
    const ctx = this.ensure();
    if (!ctx) return;
    const at = ctx.currentTime + 0.02;
    this.tone(at, 0.6, 0.05, reached ? 196 : 147, "sine", reached ? 0.5 : 0.75);
    this.tone(at + 0.12, 0.8, 0.03, reached ? 294 : 110, "triangle", 0.85);
  }
}
