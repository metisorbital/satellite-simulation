import type { PublicRunStatus, MeasurementFrame as TelemetryFrame } from '../api/generated';

export const MAX_BUFFER_FRAMES = 41;
export const HISTORY_FRAMES = 600;
export const PLAYBACK_LAG_WALL_S = 0.35;
export const STALE_AFTER_MS = 1500;

export function isStatusOlder(candidate: PublicRunStatus, current: PublicRunStatus): boolean {
  return (
    candidate.committed_tick < current.committed_tick ||
    (candidate.committed_tick === current.committed_tick &&
      (candidate.status_revision ?? 0) < (current.status_revision ?? 0))
  );
}

export function frameSeconds(frame: TelemetryFrame, epoch: string): number {
  return (Date.parse(frame.observed_at) - Date.parse(epoch)) / 1000;
}

export function scalar(frame: TelemetryFrame | undefined, channel: string): number | null {
  const reading = frame?.channels[channel];
  return reading &&
    reading.quality !== 'invalid' &&
    reading.quality !== 'missing' &&
    typeof reading.value === 'number' &&
    Number.isFinite(reading.value)
    ? reading.value
    : null;
}

export function vector(frame: TelemetryFrame, channel: string): [number, number, number] | null {
  const reading = frame.channels[channel];
  const value = reading?.value;
  return reading &&
    reading.quality === 'valid' &&
    Array.isArray(value) &&
    value.length === 3 &&
    value.every((v) => typeof v === 'number' && Number.isFinite(v))
    ? (value as [number, number, number])
    : null;
}

/** A bounded presentation buffer. It never integrates or predicts orbital dynamics. */
export class CommittedPlayback {
  status: PublicRunStatus | null = null;
  readonly frames = new Map<string, TelemetryFrame[]>();
  readonly history = new Map<string, TelemetryFrame[]>();
  private anchorWall = 0;
  private anchorSeconds = 0;
  private displayedSeconds: number | null = null;
  private lastAdvanceWall = 0;
  private lastCommittedTick = -1;
  private connected = false;

  setConnected(connected: boolean): void {
    this.connected = connected;
  }

  ingest(status: PublicRunStatus, incoming: TelemetryFrame[], now: number): void {
    if (this.status && this.status.run_id !== status.run_id) this.clear();
    // A slower HTTP snapshot may arrive after a newer socket batch.
    if (this.status?.run_id === status.run_id && isStatusOlder(status, this.status))
      status = this.status;
    this.status = status;
    for (const satellite of status.satellites) {
      const additions = incoming.filter((f) => f.stream_id === satellite.stream_id);
      if (additions.length === 0) continue;
      const previous = this.history.get(satellite.satellite_id) ?? [];
      const merged = new Map(previous.map((f) => [f.sequence, f]));
      for (const frame of additions) {
        if (
          Number.isSafeInteger(frame.sequence) &&
          frame.sequence >= 0 &&
          frameSeconds(frame, status.epoch_utc) <= status.committed_tick
        )
          merged.set(frame.sequence, frame);
      }
      const ordered = [...merged.values()].sort((a, b) => a.sequence - b.sequence);
      this.history.set(satellite.satellite_id, ordered.slice(-HISTORY_FRAMES));
      this.frames.set(satellite.satellite_id, ordered.slice(-MAX_BUFFER_FRAMES));
    }
    if (status.committed_tick > this.lastCommittedTick) {
      this.lastAdvanceWall = now;
      this.lastCommittedTick = status.committed_tick;
    }
    const bounds = this.bounds();
    if (!bounds) return;
    this.anchorWall = now;
    const speed = Math.max(0, status.effective_speed || status.requested_speed);
    this.anchorSeconds = Math.max(bounds[0], bounds[1] - speed * PLAYBACK_LAG_WALL_S);
    if (this.displayedSeconds === null) this.displayedSeconds = this.anchorSeconds;
    if (status.status !== 'running') this.displayedSeconds = bounds[1];
  }

  bounds(): [number, number] | null {
    if (!this.status || this.status.satellites.length === 0) return null;
    const buffers = this.status.satellites.map((s) => this.frames.get(s.satellite_id));
    if (buffers.some((b) => !b?.length)) return null;
    const epoch = this.status.epoch_utc;
    const start = Math.max(...buffers.map((b) => frameSeconds(b![0], epoch)));
    const end = Math.min(
      this.status.committed_tick,
      ...buffers.map((b) => frameSeconds(b![b!.length - 1], epoch)),
    );
    return end < start ? null : [start, end];
  }

  isStale(now: number): boolean {
    return (
      !this.connected ||
      (this.status?.status === 'running' && now - this.lastAdvanceWall > STALE_AFTER_MS)
    );
  }

  time(now: number): number | null {
    const bounds = this.bounds();
    if (!bounds || !this.status) return null;
    if (this.status.status !== 'running') return (this.displayedSeconds = bounds[1]);
    if (this.isStale(now)) return this.displayedSeconds;
    const speed = Math.max(0, this.status.effective_speed || this.status.requested_speed);
    const proposed = this.anchorSeconds + (Math.max(0, now - this.anchorWall) / 1000) * speed;
    this.displayedSeconds = Math.min(
      bounds[1],
      Math.max(bounds[0], this.displayedSeconds ?? bounds[0], proposed),
    );
    return this.displayedSeconds;
  }

  frameAt(satelliteId: string, seconds: number | null): TelemetryFrame | undefined {
    if (seconds === null || !this.status) return undefined;
    const frames = this.frames.get(satelliteId) ?? [];
    for (let i = frames.length - 1; i >= 0; i--) {
      const lag = seconds - frameSeconds(frames[i], this.status.epoch_utc);
      if (lag >= -1e-7 && lag <= 1 + 1e-7) return frames[i];
    }
    return undefined;
  }

  private clear(): void {
    this.frames.clear();
    this.history.clear();
    this.displayedSeconds = null;
    this.lastCommittedTick = -1;
  }
}
