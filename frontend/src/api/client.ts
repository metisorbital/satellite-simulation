import type { PublicRunStatus, Snapshot, Trajectory, VisualMessage } from './generated';

export interface Bootstrap {
  csrf_token: string;
  run: PublicRunStatus;
}
export type ControlAction = 'start' | 'pause' | 'resume' | 'stop' | 'set_speed';

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(path, { credentials: 'same-origin', ...options });
  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as {
      message?: string;
      detail?: string | { message?: string };
    } | null;
    const detail = payload?.detail;
    throw new Error(
      payload?.message ??
        (typeof detail === 'string'
          ? detail
          : (detail?.message ?? `Request failed (${response.status})`)),
    );
  }
  return response.json() as Promise<T>;
}

let pendingBootstrap: Promise<Bootstrap> | null = null;

/** Share overlapping session requests so their cookies and CSRF response cannot race. */
function bootstrap(): Promise<Bootstrap> {
  if (!pendingBootstrap) {
    pendingBootstrap = request<Bootstrap>('/v1/viewer/bootstrap').finally(() => {
      pendingBootstrap = null;
    });
  }
  return pendingBootstrap;
}

export const api = {
  bootstrap,
  snapshot: (runId: string) =>
    request<Snapshot>(`/v1/runs/${encodeURIComponent(runId)}/snapshot?history=41`),
  trajectory: (run: PublicRunStatus, from: number) =>
    request<Trajectory>(
      `/v1/runs/${encodeURIComponent(run.run_id)}/trajectory?from=${Math.floor(from)}&to=${Math.min(run.duration_s, Math.floor(from) + 3600)}&step_s=20`,
    ),
  control: (
    runId: string,
    token: string,
    action: ControlAction,
    speed?: number,
    key: string = crypto.randomUUID(),
  ) =>
    request<PublicRunStatus>(`/v1/runs/${encodeURIComponent(runId)}/control`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Idempotency-Key': key,
        'X-CSRF-Token': token,
      },
      body: JSON.stringify(action === 'set_speed' ? { action, speed } : { action }),
    }),
};

export function visualSocket(runId: string): WebSocket {
  const url = new URL(`/v1/runs/${encodeURIComponent(runId)}/visual`, location.href);
  url.protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
  return new WebSocket(url);
}

export function parseVisual(data: unknown): VisualMessage | null {
  if (typeof data !== 'string') return null;
  try {
    const value = JSON.parse(data) as VisualMessage;
    return value.visual_schema_version === 'visual.v1' && typeof value.run_id === 'string'
      ? value
      : null;
  } catch {
    return null;
  }
}
