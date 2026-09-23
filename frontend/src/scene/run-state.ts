import type { Entity, JulianDate, SampledPositionProperty, Viewer } from 'cesium';

/** Keeps render samples and paths scoped to one mission, even when IDs are reused. */
export class RunSceneState {
  readonly entities = new Map<string, Entity>();
  readonly properties = new Map<string, SampledPositionProperty>();
  private runId: string | null = null;

  positionedIds(time: JulianDate): string[] {
    return [...this.entities].flatMap(([id, entity]) =>
      entity.position?.getValue(time) ? [id] : [],
    );
  }

  setRun(runId: string | null, viewer: Pick<Viewer, 'entities' | 'trackedEntity'>): void {
    if (this.runId === runId) return;
    viewer.trackedEntity = undefined;
    viewer.entities.removeAll();
    this.entities.clear();
    this.properties.clear();
    this.runId = runId;
  }
}
