import { describe, expect, it } from 'vitest';
import {
  Cartesian3,
  Entity,
  EntityCollection,
  ExtrapolationType,
  HermitePolynomialApproximation,
  JulianDate,
  ReferenceFrame,
  SampledPositionProperty,
} from 'cesium';
import {
  CommittedPlayback,
  HISTORY_FRAMES,
  MAX_BUFFER_FRAMES,
  scalar,
} from '../src/scene/playback';
import { EPOCH, frameAt, framesBetween, statusAt } from './fixtures';
import { RenderRateCounter } from '../src/scene/render-rate';
import { RunSceneState } from '../src/scene/run-state';
import { createPositionProperty } from '../src/scene/sampled-position';

it('clears Cesium positions, paths, and tracking before reused IDs enter another run', () => {
  const scene = new RunSceneState();
  const viewer = {
    entities: new EntityCollection(),
    trackedEntity: undefined as Entity | undefined,
  };
  const time = JulianDate.fromIso8601(EPOCH);
  scene.setRun('first-run', viewer);
  const oldPosition = createPositionProperty();
  oldPosition.addSample(time, new Cartesian3(7000000, 0, 0), [Cartesian3.ZERO]);
  const oldEntity = viewer.entities.add({ id: 'METIS-01', position: oldPosition });
  viewer.entities.add({ id: 'orbit-METIS-01' });
  scene.entities.set(oldEntity.id, oldEntity);
  scene.properties.set(oldEntity.id, oldPosition);
  viewer.trackedEntity = oldEntity;
  expect(scene.positionedIds(time)).toEqual(['METIS-01']);

  scene.setRun('replacement-run', viewer);
  expect(viewer.entities.values).toHaveLength(0);
  expect(viewer.trackedEntity).toBeUndefined();
  expect(scene.entities.size).toBe(0);
  expect(scene.properties.size).toBe(0);
  expect(scene.positionedIds(time)).toEqual([]);

  const newPosition = createPositionProperty();
  expect(newPosition.getValue(time)).toBeUndefined();
  const newEntity = viewer.entities.add({ id: 'METIS-01', position: newPosition });
  scene.entities.set(newEntity.id, newEntity);
  scene.properties.set(newEntity.id, newPosition);
  expect(scene.positionedIds(time)).toEqual([]);
  newPosition.addSample(time, new Cartesian3(0, 7000000, 0), [Cartesian3.ZERO]);
  scene.setRun('replacement-run', viewer);
  expect(scene.properties.get('METIS-01')?.getValue(time)).toEqual(new Cartesian3(0, 7000000, 0));
  expect(viewer.entities.getById('METIS-01')).toBe(newEntity);
  expect(scene.positionedIds(time)).toEqual(['METIS-01']);
  expect(scene.positionedIds(JulianDate.addSeconds(time, 1, new JulianDate()))).toEqual([]);
});

describe('Measured scene render rate', () => {
  it('publishes actual render counts no more than once per wall second', () => {
    const counter = new RenderRateCounter(0);
    for (let frame = 0; frame < 42; frame++) counter.rendered();
    expect(counter.sample(999)).toBeNull();
    expect(counter.sample(1050)).toEqual({ frames: 42, windowMs: 1050, observedAt: 1050, fps: 40 });
    for (let frame = 0; frame < 3; frame++) counter.rendered();
    expect(counter.sample(2049)).toBeNull();
    expect(counter.sample(2050)).toEqual({ frames: 3, windowMs: 1000, observedAt: 2050, fps: 3 });
  });

  it('reports unavailable when no scene renders were observed', () => {
    const counter = new RenderRateCounter(0);
    expect(counter.sample(1000)?.fps).toBeNull();
    expect(counter.sample(3000)).toEqual({
      frames: 0,
      windowMs: 2000,
      observedAt: 3000,
      fps: null,
    });
  });
});

describe('Committed presentation semantics', () => {
  it('clamps 20× playback to complete committed sample brackets and freezes stale data', () => {
    const playback = new CommittedPlayback();
    playback.setConnected(true);
    playback.ingest(statusAt(40), framesBetween(0, 40), 1000);
    expect(playback.time(1000)).toBe(33);
    expect(playback.time(2000)).toBe(40);
    expect(playback.isStale(2600)).toBe(true);
    expect(playback.time(8000)).toBe(40);
    playback.setConnected(false);
    expect(playback.time(9000)).toBe(40);
  });

  it('never shows future or older-than-one-second measurements at the display instant', () => {
    const playback = new CommittedPlayback();
    playback.ingest(statusAt(40), framesBetween(0, 40), 0);
    expect(playback.frameAt('METIS-01', 35.75)?.sequence).toBe(35);
    expect(playback.frameAt('METIS-01', 42)).toBeUndefined();
    expect(playback.frameAt('METIS-01', -0.1)).toBeUndefined();
    expect(playback.frameAt('METIS-01', null)).toBeUndefined();
  });

  it('drains a pause to its acknowledged complete endpoint, with matching readings', () => {
    const playback = new CommittedPlayback();
    playback.setConnected(true);
    playback.ingest(statusAt(40), framesBetween(0, 40), 1000);
    playback.time(1100);
    playback.ingest(statusAt(44, 'paused'), framesBetween(4, 44), 1200);
    expect(playback.time(999999)).toBe(44);
    expect(playback.frameAt('METIS-02', playback.time(999999))?.sequence).toBe(44);
  });

  it('bounds each satellite buffer and deduplicates snapshot/stream overlap', () => {
    const playback = new CommittedPlayback();
    playback.ingest(statusAt(1000), framesBetween(0, 1000), 0);
    playback.ingest(statusAt(1000), framesBetween(990, 1000), 10);
    for (const id of ['METIS-01', 'METIS-02', 'METIS-03']) {
      expect(playback.frames.get(id)).toHaveLength(MAX_BUFFER_FRAMES);
      expect(playback.history.get(id)).toHaveLength(HISTORY_FRAMES);
      expect(new Set(playback.frames.get(id)?.map((f) => f.sequence)).size).toBe(MAX_BUFFER_FRAMES);
    }
  });

  it('waits for all spacecraft before advancing and rejects uncommitted frames', () => {
    const playback = new CommittedPlayback();
    playback.ingest(statusAt(20), [frameAt(20, 1), frameAt(21, 1)], 0);
    expect(playback.time(100)).toBeNull();
    expect(playback.frames.get('METIS-01')).toHaveLength(1);
    playback.ingest(statusAt(20), [frameAt(18, 2), frameAt(19, 3)], 100);
    expect(playback.bounds()).toBeNull();
  });

  it('does not substitute zero for absent, invalid, or missing measurements', () => {
    const frame = frameAt(1);
    frame.channels['eps.solar_power_w'] = { value: null, quality: 'missing' };
    expect(scalar(frame, 'eps.solar_power_w')).toBeNull();
    expect(scalar(undefined, 'eps.solar_power_w')).toBeNull();
    expect(scalar(frame, 'unsupported')).toBeNull();
  });

  it('honors a speed transition without moving outside committed bounds', () => {
    const playback = new CommittedPlayback();
    playback.setConnected(true);
    playback.ingest(statusAt(10, 'running', 1), framesBetween(0, 10), 0);
    const before = playback.time(100)!;
    playback.ingest(statusAt(10, 'running', 20), framesBetween(0, 10), 100);
    expect(playback.time(100)).toBeGreaterThanOrEqual(before);
    expect(playback.time(500)).toBeLessThanOrEqual(10);
  });

  it('does not regress to an older HTTP snapshot arriving after a socket batch', () => {
    const playback = new CommittedPlayback();
    playback.setConnected(true);
    playback.ingest(statusAt(44), framesBetween(4, 44), 100);
    const displayed = playback.time(200)!;
    playback.ingest(statusAt(40), framesBetween(0, 40), 250);
    expect(playback.status?.committed_tick).toBe(44);
    expect(playback.time(250)).toBeGreaterThanOrEqual(displayed);
  });

  it('preserves pause and speed acknowledgements against older revisions at the same tick while merging frames', () => {
    const playback = new CommittedPlayback();
    playback.setConnected(true);
    playback.ingest(
      { ...statusAt(40, 'paused', 5), status_revision: 9 },
      framesBetween(39, 40),
      100,
    );
    playback.ingest(
      { ...statusAt(40, 'running', 20), status_revision: 8 },
      framesBetween(37, 38),
      200,
    );
    expect(playback.status?.status).toBe('paused');
    expect(playback.status?.requested_speed).toBe(5);
    expect(playback.status?.status_revision).toBe(9);
    expect(playback.frames.get('METIS-01')?.map((frame) => frame.sequence)).toEqual([
      37, 38, 39, 40,
    ]);
    expect(playback.time(10000)).toBe(40);
  });
});

describe('Cesium frame and interpolation contract', () => {
  it('uses fixed-frame velocities to reproduce a cubic trajectory at endpoints and intermediate times', () => {
    const property = new SampledPositionProperty(ReferenceFrame.FIXED, 1);
    property.setInterpolationOptions({
      interpolationDegree: 3,
      interpolationAlgorithm: HermitePolynomialApproximation,
    });
    property.forwardExtrapolationType = ExtrapolationType.NONE;
    property.backwardExtrapolationType = ExtrapolationType.NONE;
    const origin = JulianDate.fromIso8601(EPOCH);
    const time = (t: number) => JulianDate.addSeconds(origin, t, new JulianDate());
    const position = (t: number) =>
      new Cartesian3(
        7000000 + 100 * t + t ** 3,
        2000000 - 200 * t + 2 * t ** 2,
        -1500000 + 300 * t,
      );
    const velocity = (t: number) => new Cartesian3(100 + 3 * t ** 2, -200 + 4 * t, 300);
    for (const t of [0, 1]) property.addSample(time(t), position(t), [velocity(t)]);
    for (const t of [0, 0.1, 0.5, 0.9, 1])
      expect(Cartesian3.distance(property.getValue(time(t))!, position(t))).toBeLessThan(0.01);
    expect(property.referenceFrame).toBe(ReferenceFrame.FIXED);
    expect(property.getValue(time(-1))).toBeUndefined();
    expect(property.getValue(time(2))).toBeUndefined();
  });
});
