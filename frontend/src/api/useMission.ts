import { useCallback, useEffect, useRef, useState } from 'react';
import type { PublicRunStatus, Trajectory } from './generated';
import { api, parseVisual, visualSocket, type ControlAction } from './client';
import { CommittedPlayback, isStatusOlder } from '../scene/playback';

export function useMission() {
  const playback = useRef(new CommittedPlayback()).current;
  const token = useRef('');
  const connectionGeneration = useRef(0);
  const [status, setStatus] = useState<PublicRunStatus | null>(null);
  const [trajectory, setTrajectory] = useState<Trajectory | null>(null);
  const [revision, setRevision] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [retry, setRetry] = useState(0);
  const [connected, setConnected] = useState(false);
  const nextTrajectoryRefresh = useRef(0);

  useEffect(() => {
    const generation = ++connectionGeneration.current;
    let stopped = false;
    let activeRunId: string | null = null;
    let socket: WebSocket | null = null;
    let reconnect: ReturnType<typeof setTimeout> | undefined;
    let reconnectDelay = 1000;
    const ingest = (next: PublicRunStatus, frames: Parameters<CommittedPlayback['ingest']>[1]) => {
      if (stopped || next.run_id !== activeRunId) return;
      playback.ingest(next, frames, performance.now());
      setStatus(playback.status);
      setRevision((value) => value + 1);
    };
    const resync = async (runId: string) => {
      const snapshot = await api.snapshot(runId);
      ingest(snapshot.status, snapshot.frames);
    };
    const connect = (runId: string) => {
      if (stopped) return;
      socket = visualSocket(runId);
      socket.onopen = () => {
        if (stopped) return;
        playback.setConnected(true);
        setConnected(true);
        setError(null);
        reconnectDelay = 1000;
      };
      socket.onmessage = (event) => {
        const message = parseVisual(event.data);
        if (!message || message.run_id !== runId || stopped) return;
        if (message.type === 'resync_required') {
          void resync(runId).catch((e) => {
            if (!stopped) setError((e as Error).message);
          });
        } else if (message.type === 'error') {
          setError(message.message ?? 'The simulation stream reported an error.');
        } else if (message.status) {
          ingest(message.status, message.frames ?? []);
        }
      };
      socket.onclose = (event) => {
        if (stopped) return;
        playback.setConnected(false);
        setConnected(false);
        if ([1008, 4401, 4403].includes(event.code)) {
          setError('Mission session expired. Reconnect to continue.');
          return;
        }
        reconnect = setTimeout(() => {
          void resync(runId)
            .then(() => connect(runId))
            .catch(() => connect(runId));
        }, reconnectDelay);
        reconnectDelay = Math.min(10000, reconnectDelay * 2);
      };
    };
    token.current = '';
    setBusy(true);
    setConnected(false);
    setTrajectory(null);
    nextTrajectoryRefresh.current = 0;
    setError(null);
    void api
      .bootstrap()
      .then(async (bootstrap) => {
        if (stopped) return;
        activeRunId = bootstrap.run.run_id;
        token.current = bootstrap.csrf_token;
        ingest(bootstrap.run, []);
        await resync(bootstrap.run.run_id);
        if (stopped) return;
        connect(bootstrap.run.run_id);
        void api
          .trajectory(bootstrap.run, Math.max(0, bootstrap.run.committed_tick))
          .then((path) => {
            if (!stopped && path.run_id === activeRunId) {
              setTrajectory(path);
              nextTrajectoryRefresh.current =
                (Math.floor(Math.max(0, bootstrap.run.committed_tick) / 1800) + 1) * 1800;
            }
          })
          .catch((e) => {
            if (!stopped) setError((e as Error).message);
          });
      })
      .catch((e) => {
        if (!stopped) setError((e as Error).message);
      })
      .finally(() => {
        if (!stopped) setBusy(false);
      });
    return () => {
      stopped = true;
      if (connectionGeneration.current === generation) {
        connectionGeneration.current += 1;
        token.current = '';
      }
      clearTimeout(reconnect);
      socket?.close();
      playback.setConnected(false);
    };
  }, [playback, retry]);

  useEffect(() => {
    if (
      !status ||
      !trajectory ||
      trajectory.run_id !== status.run_id ||
      status.committed_tick < nextTrajectoryRefresh.current ||
      status.committed_tick >= status.duration_s
    )
      return;
    nextTrajectoryRefresh.current = (Math.floor(status.committed_tick / 1800) + 1) * 1800;
    const generation = connectionGeneration.current;
    let cancelled = false;
    void api
      .trajectory(status, status.committed_tick)
      .then((path) => {
        if (
          !cancelled &&
          connectionGeneration.current === generation &&
          path.run_id === status.run_id
        )
          setTrajectory(path);
      })
      .catch(() => {
        /* Keep the last explicitly labelled orbit preview. */
      });
    return () => {
      cancelled = true;
    };
  }, [status?.run_id, Math.floor((status?.committed_tick ?? 0) / 1800)]);

  const control = useCallback(
    async (action: ControlAction, speed?: number) => {
      if (!status || busy || !token.current || playback.status?.run_id !== status.run_id) return;
      const generation = connectionGeneration.current;
      const runId = status.run_id;
      const isCurrent = () =>
        connectionGeneration.current === generation && playback.status?.run_id === runId;
      setBusy(true);
      setError(null);
      try {
        const acknowledged = await api.control(runId, token.current, action, speed);
        if (!isCurrent() || acknowledged.run_id !== runId) return;
        // A pause may acknowledge a newer endpoint than the last socket batch. Read it
        // before applying the stopped clock, so globe and measurements drain together.
        const snapshot = await api.snapshot(runId);
        if (!isCurrent() || snapshot.status.run_id !== runId) return;
        playback.ingest(
          isStatusOlder(snapshot.status, acknowledged) ? acknowledged : snapshot.status,
          snapshot.frames,
          performance.now(),
        );
        setStatus(playback.status);
        setRevision((value) => value + 1);
      } catch (e) {
        if (isCurrent()) setError((e as Error).message);
      } finally {
        if (isCurrent()) setBusy(false);
      }
    },
    [status, busy, playback],
  );

  return {
    playback,
    status,
    trajectory,
    revision,
    error,
    busy,
    connected,
    control,
    retry: () => setRetry((n) => n + 1),
  };
}
