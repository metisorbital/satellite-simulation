export interface RenderRateSample {
  frames: number;
  windowMs: number;
  observedAt: number;
  fps: number | null;
}

export interface SceneDiagnostics extends RenderRateSample {
  positionedSatelliteIds: string[];
}

/** Counts completed scene renders in bounded wall-time windows. */
export class RenderRateCounter {
  private frames = 0;

  constructor(private windowStartedAt: number) {}

  rendered(): void {
    this.frames += 1;
  }

  sample(now: number): RenderRateSample | null {
    const windowMs = now - this.windowStartedAt;
    if (windowMs < 1000) return null;
    const sample = {
      frames: this.frames,
      windowMs,
      observedAt: now,
      fps: this.frames > 0 ? (this.frames * 1000) / windowMs : null,
    };
    this.frames = 0;
    this.windowStartedAt = now;
    return sample;
  }
}
