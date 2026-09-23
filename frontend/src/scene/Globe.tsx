import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import {
  Cartesian2,
  Cartesian3,
  Color,
  ConstantProperty,
  Credit,
  CreditDisplay,
  EllipsoidTerrainProvider,
  Entity,
  HeadingPitchRange,
  ImageryLayer,
  JulianDate,
  LabelStyle,
  Math as CesiumMath,
  NearFarScalar,
  ScreenSpaceEventType,
  SingleTileImageryProvider,
  Viewer,
  VerticalOrigin,
  PolylineGlowMaterialProperty,
  TimeInterval,
} from 'cesium';
import type { PublicRunStatus, Trajectory } from '../api/generated';
import { CommittedPlayback, vector } from './playback';
import { createPositionProperty } from './sampled-position';
import { RenderRateCounter, type SceneDiagnostics } from './render-rate';
import { RunSceneState } from './run-state';

export interface SceneControls {
  reset: () => void;
  follow: (enabled: boolean) => void;
  zoom: (direction: 'in' | 'out') => void;
}

interface Props {
  playback: CommittedPlayback;
  status: PublicRunStatus | null;
  trajectory: Trajectory | null;
  revision: number;
  displaySeconds: number | null;
  selected: string;
  onSelect: (id: string) => void;
  onControls: (controls: SceneControls) => void;
  onRenderRate: (sample: SceneDiagnostics | null) => void;
}

/** Cesium consumes backend Cartesian samples only; no orbit is computed here. */
export function Globe({
  playback,
  status,
  trajectory,
  revision,
  displaySeconds,
  selected,
  onSelect,
  onControls,
  onRenderRate,
}: Props) {
  const container = useRef<HTMLDivElement>(null);
  const viewer = useRef<Viewer | null>(null);
  const [sceneState] = useState(() => new RunSceneState());
  const selectedRef = useRef(selected);
  const onSelectRef = useRef(onSelect);
  const [ready, setReady] = useState(false);
  const [renderError, setRenderError] = useState<string | null>(null);
  selectedRef.current = selected;
  onSelectRef.current = onSelect;

  useEffect(() => {
    if (!container.current) return;
    let disposed = false;
    onRenderRate(null);
    let instance: Viewer;
    try {
      CreditDisplay.cesiumCredit = new Credit(
        '<a href="https://cesium.com/cesiumjs/" target="_blank" rel="noreferrer">CesiumJS</a>',
        true,
      );
      instance = new Viewer(container.current, {
        animation: false,
        baseLayerPicker: false,
        fullscreenButton: false,
        geocoder: false,
        homeButton: false,
        infoBox: false,
        navigationHelpButton: false,
        sceneModePicker: false,
        selectionIndicator: false,
        timeline: false,
        shouldAnimate: false,
        baseLayer: false,
        terrainProvider: new EllipsoidTerrainProvider(),
        skyBox: undefined,
        requestRenderMode: false,
        showRenderLoopErrors: false,
        contextOptions: { webgl: { alpha: true, antialias: true } },
      });
    } catch {
      setRenderError('The 3D view needs WebGL 2. Satellite measurements remain available.');
      return;
    }
    viewer.current = instance;
    const renderCounter = new RenderRateCounter(performance.now());
    const stopCountingRenders = instance.scene.postRender.addEventListener(() => {
      renderCounter.rendered();
    });
    let renderingAvailable = true;
    const renderRateTimer = window.setInterval(() => {
      if (disposed || !renderingAvailable) return;
      const sample = renderCounter.sample(performance.now());
      if (sample)
        onRenderRate({
          ...sample,
          positionedSatelliteIds: sceneState.positionedIds(instance.clock.currentTime),
        });
    }, 1000);
    instance.scene.backgroundColor = Color.TRANSPARENT;
    if (instance.scene.skyBox) instance.scene.skyBox.show = false;
    instance.scene.globe.baseColor = Color.fromCssColorString('#173148');
    instance.scene.globe.enableLighting = true;
    instance.scene.globe.dynamicAtmosphereLighting = true;
    instance.scene.globe.dynamicAtmosphereLightingFromSun = true;
    instance.scene.globe.showGroundAtmosphere = true;
    instance.scene.globe.depthTestAgainstTerrain = false;
    instance.scene.globe.atmosphereLightIntensity = 11;
    instance.scene.globe.nightFadeOutDistance = 10000000;
    instance.scene.globe.nightFadeInDistance = 50000000;
    instance.scene.fog.enabled = false;
    if (instance.scene.moon) instance.scene.moon.show = false;
    if (instance.scene.sun) instance.scene.sun.show = false;
    if (instance.scene.skyAtmosphere) {
      instance.scene.skyAtmosphere.hueShift = -0.06;
      instance.scene.skyAtmosphere.brightnessShift = -0.12;
    }
    instance.scene.postProcessStages.fxaa.enabled = true;
    instance.scene.screenSpaceCameraController.minimumZoomDistance = 1500000;
    instance.scene.screenSpaceCameraController.maximumZoomDistance = 60000000;
    instance.clock.shouldAnimate = false;
    instance.clock.multiplier = 0;
    const reset = () => {
      instance.trackedEntity = undefined;
      instance.camera.flyTo({
        destination: Cartesian3.fromDegrees(120, 18, 13700000),
        orientation: { heading: 0, pitch: -CesiumMath.PI_OVER_TWO, roll: 0 },
        duration: 0.8,
      });
    };
    instance.camera.setView({
      destination: Cartesian3.fromDegrees(120, 18, 13700000),
      orientation: { heading: 0, pitch: -CesiumMath.PI_OVER_TWO, roll: 0 },
    });
    onControls({
      reset,
      follow: (enabled) => {
        const entity = sceneState.entities.get(selectedRef.current);
        instance.trackedEntity = enabled ? entity : undefined;
        if (enabled && entity)
          void instance.flyTo(entity, {
            duration: 0.7,
            offset: new HeadingPitchRange(0, -0.55, 7000000),
          });
      },
      zoom: (direction) => {
        const amount = instance.camera.positionCartographic.height * 0.3;
        if (direction === 'in') instance.camera.zoomIn(amount);
        else instance.camera.zoomOut(amount);
      },
    });
    instance.screenSpaceEventHandler.setInputAction((movement: { position: Cartesian2 }) => {
      const picked = instance.scene.pick(movement.position) as { id?: Entity } | undefined;
      if (picked?.id && sceneState.entities.has(picked.id.id)) onSelectRef.current(picked.id.id);
    }, ScreenSpaceEventType.LEFT_CLICK);
    instance.screenSpaceEventHandler.removeInputAction(ScreenSpaceEventType.LEFT_DOUBLE_CLICK);
    const stopRendering = instance.scene.renderError.addEventListener(() => {
      if (!disposed) {
        renderingAvailable = false;
        onRenderRate(null);
        setRenderError('The globe renderer paused. Reload to restore the 3D view.');
      }
    });
    void SingleTileImageryProvider.fromUrl('/assets/earth_atmos_2048.jpg', {
      credit: 'Earth imagery · three.js contributors (MIT)',
    })
      .then((provider) => {
        if (!disposed) {
          const layer = new ImageryLayer(provider);
          instance.imageryLayers.add(layer);
          layer.brightness = 1.12;
          layer.contrast = 1.12;
          layer.saturation = 0.7;
          layer.gamma = 0.9;
        }
      })
      .catch(() => {
        /* The local untextured ellipsoid remains a complete fallback. */
      });
    setReady(true);
    return () => {
      disposed = true;
      window.clearInterval(renderRateTimer);
      stopCountingRenders();
      onRenderRate(null);
      stopRendering();
      sceneState.setRun(null, instance);
      instance.destroy();
      viewer.current = null;
    };
  }, [playback, onControls, onRenderRate, sceneState]);

  // Satellite IDs can be reused by a new mission with different epochs and orbits.
  // Clear the complete scene before painting that mission's first clock instant.
  useLayoutEffect(() => {
    const instance = viewer.current;
    const runId = status?.run_id ?? null;
    if (!instance || !ready) return;
    sceneState.setRun(runId, instance);
  }, [status?.run_id, ready, sceneState]);

  // The DOM readings and Cesium clock are committed in the same React update.
  // An independent globe clock could get ahead of a 1 Hz measurement at 20×.
  useLayoutEffect(() => {
    if (viewer.current && status) {
      viewer.current.clock.currentTime = JulianDate.addSeconds(
        JulianDate.fromIso8601(status.epoch_utc),
        displaySeconds ?? 0,
        new JulianDate(),
      );
      viewer.current.clock.multiplier = 0;
      viewer.current.clock.shouldAnimate = false;
    }
  }, [displaySeconds, status?.epoch_utc, ready]);

  useEffect(() => {
    const instance = viewer.current;
    if (!instance || !status || !ready) return;
    for (const satellite of status.satellites) {
      let property = sceneState.properties.get(satellite.satellite_id);
      if (!property) {
        property = createPositionProperty();
        sceneState.properties.set(satellite.satellite_id, property);
        const color = Color.fromCssColorString(satellite.color);
        sceneState.entities.set(
          satellite.satellite_id,
          instance.entities.add({
            id: satellite.satellite_id,
            name: satellite.name,
            position: property,
            point: {
              color,
              pixelSize: 8,
              outlineColor: Color.fromCssColorString('#091521'),
              outlineWidth: 3,
            },
            label: {
              text: satellite.satellite_id,
              font: '500 11px monospace',
              fillColor: color,
              outlineColor: Color.fromCssColorString('#04121e'),
              outlineWidth: 3,
              style: LabelStyle.FILL_AND_OUTLINE,
              verticalOrigin: VerticalOrigin.BOTTOM,
              pixelOffset: new Cartesian2(0, -17),
              scaleByDistance: new NearFarScalar(1e6, 1.1, 5e7, 0.8),
            },
          }),
        );
      }
      const frames = playback.frames.get(satellite.satellite_id) ?? [];
      if (!frames.length) continue;
      // Prune Cesium's internal interpolation store as well as the JS frame buffer.
      property.removeSamples(
        new TimeInterval({
          start: JulianDate.fromIso8601(status.epoch_utc),
          stop: JulianDate.fromIso8601(frames[0].observed_at),
          isStopIncluded: false,
        }),
      );
      for (const frame of frames) {
        const position = vector(frame, 'orbit.position_itrf_m');
        const velocity = vector(frame, 'orbit.velocity_itrf_m_s');
        if (position && velocity)
          property.addSample(
            JulianDate.fromIso8601(frame.observed_at),
            Cartesian3.fromArray(position),
            [Cartesian3.fromArray(velocity)],
          );
      }
    }
  }, [status, revision, playback, ready, sceneState]);

  useEffect(() => {
    const instance = viewer.current;
    if (!instance || !trajectory || !status || trajectory.run_id !== status.run_id || !ready)
      return;
    for (const path of trajectory.satellites) {
      instance.entities.removeById(`orbit-${path.satellite_id}`);
      const descriptor = status.satellites.find((s) => s.satellite_id === path.satellite_id);
      if (!descriptor) continue;
      instance.entities.add({
        id: `orbit-${path.satellite_id}`,
        polyline: {
          positions: path.samples.map((sample) => Cartesian3.fromArray(sample.position_itrs_m)),
          width: path.satellite_id === selected ? 2 : 1,
          material: new PolylineGlowMaterialProperty({
            color: Color.fromCssColorString(descriptor.color).withAlpha(
              path.satellite_id === selected ? 0.62 : 0.18,
            ),
            glowPower: 0.1,
          }),
          arcType: 0,
        },
      });
    }
  }, [trajectory, status?.run_id, ready, selected]);

  useEffect(() => {
    for (const [id, entity] of sceneState.entities) {
      if (entity.point) entity.point.pixelSize = new ConstantProperty(id === selected ? 11 : 7);
    }
    const instance = viewer.current;
    if (instance?.trackedEntity) instance.trackedEntity = sceneState.entities.get(selected);
  }, [selected, revision, sceneState]);

  return (
    <div
      className="globe"
      data-simulation-seconds={displaySeconds ?? undefined}
      aria-label="Interactive Earth and satellite orbit view"
    >
      <div ref={container} className="globe-canvas" />
      {renderError && (
        <div className="render-error" role="status">
          {renderError}
        </div>
      )}
    </div>
  );
}
