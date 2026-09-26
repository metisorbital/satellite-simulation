/* Rendering boundary only: all samples, paths and the clock originate in Dart. */
window.metisGlobe = (() => {
  const scenes = new Map();
  const C = window.Cesium;
  return {
    create(element, onSelect) {
      const scene = { viewer: null, run: null, selected: '', hidden: new Set(), paths: '', follow: false, error: null, fps: null, count: 0, began: performance.now() };
      scenes.set(element.id, scene);
      try {
        C.CreditDisplay.cesiumCredit = new C.Credit('<a href="https://cesium.com/cesiumjs/" target="_blank" rel="noreferrer">CesiumJS</a>', true);
        const viewer = scene.viewer = new C.Viewer(element, {
          animation: false, baseLayerPicker: false, fullscreenButton: false,
          geocoder: false, homeButton: false, infoBox: false,
          navigationHelpButton: false, sceneModePicker: false, selectionIndicator: false,
          timeline: false, shouldAnimate: false, baseLayer: false,
          terrainProvider: new C.EllipsoidTerrainProvider(), requestRenderMode: false,
          showRenderLoopErrors: false,
          contextOptions: { webgl: { alpha: true, antialias: true } },
        });
        viewer.scene.backgroundColor = C.Color.TRANSPARENT;
        if (viewer.scene.skyBox) viewer.scene.skyBox.show = false;
        viewer.scene.globe.baseColor = C.Color.fromCssColorString('#173148');
        viewer.scene.globe.enableLighting = true;
        viewer.scene.globe.dynamicAtmosphereLighting = true;
        viewer.scene.globe.dynamicAtmosphereLightingFromSun = true;
        viewer.scene.globe.atmosphereLightIntensity = 11;
        if (viewer.scene.skyAtmosphere) {
          viewer.scene.skyAtmosphere.hueShift = -0.06;
          viewer.scene.skyAtmosphere.brightnessShift = -0.12;
        }
        viewer.scene.postProcessStages.fxaa.enabled = true;
        viewer.scene.fog.enabled = false;
        viewer.scene.screenSpaceCameraController.minimumZoomDistance = 1500000;
        viewer.scene.screenSpaceCameraController.maximumZoomDistance = 60000000;
        if (viewer.scene.moon) viewer.scene.moon.show = false;
        if (viewer.scene.sun) viewer.scene.sun.show = false;
        viewer.scene.postRender.addEventListener(() => {
          scene.count++;
          const now = performance.now();
          if (now - scene.began >= 1000) {
            scene.fps = scene.count * 1000 / (now - scene.began);
            scene.count = 0; scene.began = now;
          }
        });
        viewer.scene.renderError.addEventListener(() => { scene.error = 'Globe renderer paused. Reload to restore the 3D view.'; scene.fps = null; });
        viewer.screenSpaceEventHandler.setInputAction((event) => {
          const picked = viewer.scene.pick(event.position);
          const pickedId = picked?.id?.id;
          if (typeof pickedId === 'string' && !pickedId.startsWith('orbit-') && !scene.hidden.has(pickedId)) onSelect(pickedId);
        }, C.ScreenSpaceEventType.LEFT_CLICK);
        viewer.screenSpaceEventHandler.removeInputAction(C.ScreenSpaceEventType.LEFT_DOUBLE_CLICK);
        C.SingleTileImageryProvider.fromUrl('/assets/earth_atmos_2048.jpg', {credit: 'Earth imagery · three.js contributors (MIT)'})
          .then(provider => { if (!viewer.isDestroyed()) viewer.imageryLayers.addImageryProvider(provider); }).catch(() => {});
        this.command(element.id, 'reset');
      } catch (_) { scene.error = 'The 3D view needs WebGL 2. Satellite measurements remain available.'; }
    },
    update(id, serialized) {
      const scene = scenes.get(id);
      if (!scene?.viewer) return;
      const { status, frames, seconds, selected, trajectory, hidden_satellite_ids: hiddenSatelliteIds = [] } = JSON.parse(serialized);
      const viewer = scene.viewer;
      if (!status) return;
      scene.hidden = new Set(Array.isArray(hiddenSatelliteIds) ? hiddenSatelliteIds : []);
      if (scene.run !== status.run_id) {
        viewer.trackedEntity = undefined;
        viewer.entities.removeAll();
        scene.run = status.run_id; scene.paths = ''; scene.follow = false;
      }
      viewer.clock.currentTime = C.JulianDate.addSeconds(C.JulianDate.fromIso8601(status.epoch_utc), seconds ?? 0, new C.JulianDate());
      viewer.clock.shouldAnimate = false;
      viewer.clock.multiplier = 0;
      scene.selected = selected;
      for (const satellite of status.satellites) {
        const visible = !scene.hidden.has(satellite.satellite_id);
        let entity = viewer.entities.getById(satellite.satellite_id);
        if (!entity) {
          const position = window.metisCreatePosition(C);
          entity = viewer.entities.add({ id: satellite.satellite_id, position,
            point: { color: C.Color.fromCssColorString(satellite.color), pixelSize: 8, outlineWidth: 2, outlineColor: C.Color.BLACK },
            label: { text: satellite.satellite_id, font: '12px sans-serif', pixelOffset: new C.Cartesian2(0,-20), fillColor: C.Color.fromCssColorString(satellite.color) } });
        }
        entity.show = visible;
        const buffer = frames[satellite.satellite_id] ?? [];
        if (status.source_kind !== 'observed') {
          globalThis.metisAddSamples(entity.position, buffer, status.epoch_utc, C);
        }
        entity.point.pixelSize = satellite.satellite_id === selected ? 11 : 7;
      }
      const pathKey = JSON.stringify([trajectory, selected, [...scene.hidden].sort()]);
      const trajectoryAllowed = status.source_kind !== 'observed' || trajectory?.kind === 'configured_orbit';
      if (trajectoryAllowed && trajectory?.run_id === status.run_id && pathKey !== scene.paths) {
        scene.paths = pathKey;
        for (const path of trajectory.satellites) {
          viewer.entities.removeById(`orbit-${path.satellite_id}`);
          const descriptor = status.satellites.find(s => s.satellite_id === path.satellite_id);
          if (!descriptor) continue;
          if (status.source_kind === 'observed') {
            const entity = viewer.entities.getById(path.satellite_id);
            // Presentation only: interpolate backend orbit points on the replay clock.
            entity.position = window.metisCreatePosition(C);
            for (const sample of path.samples) {
              entity.position.addSample(C.JulianDate.fromIso8601(sample.observed_at),
                C.Cartesian3.fromArray(sample.position_itrs_m),
                [C.Cartesian3.fromArray(sample.velocity_itrs_m_s)]);
            }
          }
          const orbit = viewer.entities.add({ id: `orbit-${path.satellite_id}`, polyline: {
            positions: path.samples.map(s => C.Cartesian3.fromArray(s.position_itrs_m)), arcType: C.ArcType.NONE,
            width: path.satellite_id === selected ? 2 : 1,
            material: C.Color.fromCssColorString(descriptor.color).withAlpha(path.satellite_id === selected ? .65 : .2) } });
          orbit.show = !scene.hidden.has(path.satellite_id);
        }
      }
      if (scene.follow) {
        if (scene.hidden.has(selected)) {
          scene.follow = false;
          viewer.trackedEntity = undefined;
        } else {
          viewer.trackedEntity = viewer.entities.getById(selected);
        }
      }
    },
    clock(id, epoch, seconds) {
      const viewer = scenes.get(id)?.viewer;
      if (viewer) viewer.clock.currentTime = C.JulianDate.addSeconds(C.JulianDate.fromIso8601(epoch), seconds, new C.JulianDate());
    },
    command(id, action) {
      const scene = scenes.get(id), viewer = scene?.viewer;
      if (!viewer) return;
      if (action === 'reset') {
        scene.follow = false; viewer.trackedEntity = undefined;
        viewer.camera.setView({ destination: C.Cartesian3.fromDegrees(120, 18, 13700000) });
      } else if (action === 'follow') {
        if (scene.follow) {
          scene.follow = false;
          viewer.trackedEntity = undefined;
        } else if (scene.hidden.has(scene.selected)) {
          viewer.trackedEntity = undefined;
        } else {
          scene.follow = true;
          viewer.trackedEntity = viewer.entities.getById(scene.selected);
        }
      }
      else if (action === 'in') viewer.camera.zoomIn(viewer.camera.positionCartographic.height * .3);
      else if (action === 'out') viewer.camera.zoomOut(viewer.camera.positionCartographic.height * .3);
    },
    diagnostics(id) {
      const scene = scenes.get(id);
      return JSON.stringify({ error: scene?.error ?? null, fps: scene?.fps ?? null });
    },
    destroy(id) { const scene = scenes.get(id); scene?.viewer?.destroy(); scenes.delete(id); }
  };
})();
