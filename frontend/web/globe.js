/* Rendering boundary only: all samples, paths and the clock originate in Dart. */
window.metisGlobe = (() => {
  const scenes = new Map();
  const C = window.Cesium;
  function frameEarth(scene) {
    const viewer = scene.viewer;
    if (!viewer || viewer.isDestroyed() || !scene.autoFrame || scene.follow) return;
    if (!viewer.canvas.clientWidth || !viewer.canvas.clientHeight) return;
    // Cesium uses horizontal FOV for wide canvases; fit the smaller angle.
    viewer.resize();
    const frustum = viewer.camera.frustum;
    const vertical = frustum.fovy / 2;
    const horizontal = Math.atan(Math.tan(vertical) * frustum.aspectRatio);
    const radius = viewer.scene.globe.ellipsoid.maximumRadius;
    const altitude = Math.max(13700000, radius * 1.25 / Math.sin(Math.min(vertical, horizontal)) - radius);
    viewer.camera.setView({ destination: C.Cartesian3.fromDegrees(120, 18, altitude) });
  }
  function updateClock(scene, epoch, seconds) {
    const viewer = scene.viewer;
    viewer.clock.currentTime = C.JulianDate.addSeconds(
      C.JulianDate.fromIso8601(epoch), seconds, new C.JulianDate());
    const sun = scene.sun?.getValue(viewer.clock.currentTime);
    const available = sun && C.Cartesian3.magnitudeSquared(sun) > 0;
    viewer.scene.globe.enableLighting = Boolean(available);
    // A missing/out-of-range ephemeris must not leave a stale terminator visible.
    if (viewer.scene.skyAtmosphere) viewer.scene.skyAtmosphere.show = Boolean(available);
    scene.lightingError = available ? null : 'Day/night lighting unavailable at this time.';
    if (available) {
      // Backend vectors point Earth -> Sun; light rays travel the opposite way.
      C.Cartesian3.normalize(sun, scene.light.direction);
      C.Cartesian3.negate(scene.light.direction, scene.light.direction);
    }
  }
  return {
    create(element, onSelect) {
      const scene = { viewer: null, run: null, selected: '', hidden: new Set(), paths: '', follow: false, autoFrame: true, resizeObserver: null, cameraInput: null, sun: null, light: null, lightingError: null, error: null, fps: null, count: 0, began: performance.now() };
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
        scene.light = new C.DirectionalLight({ direction: new C.Cartesian3(1, 0, 0) });
        viewer.scene.light = scene.light;
        viewer.scene.globe.enableLighting = false;
        viewer.scene.globe.dynamicAtmosphereLighting = true;
        viewer.scene.globe.dynamicAtmosphereLightingFromSun = false;
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
        const pointers = new Map();
        const releasePointer = event => pointers.delete(event.pointerId);
        scene.cameraInput = {
          pointerdown(event) {
            pointers.set(event.pointerId, [event.clientX, event.clientY]);
            if (pointers.size > 1) scene.autoFrame = false;
          },
          pointermove(event) {
            const start = pointers.get(event.pointerId);
            // A marker click keeps responsive framing; an actual drag takes over.
            if (start && Math.hypot(event.clientX - start[0], event.clientY - start[1]) >= 4) {
              scene.autoFrame = false;
            }
          },
          pointerup: releasePointer,
          pointercancel: releasePointer,
          pointerleave: releasePointer,
          wheel() { scene.autoFrame = false; },
        };
        for (const [type, handler] of Object.entries(scene.cameraInput)) {
          viewer.canvas.addEventListener(type, handler, { passive: true });
        }
        scene.resizeObserver = new ResizeObserver(() => frameEarth(scene));
        scene.resizeObserver.observe(element);
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
        scene.run = status.run_id; scene.paths = ''; scene.follow = false; scene.sun = null;
      }
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
        // All satellites share the same geocentric Sun, sampled by Astropy.
        scene.sun = new C.SampledProperty(C.Cartesian3);
        for (const sample of trajectory.satellites[0]?.samples ?? []) {
          const vector = sample.sun_position_itrs_m;
          if (Array.isArray(vector) && vector.length === 3 && vector.every(Number.isFinite)) {
            scene.sun.addSample(C.JulianDate.fromIso8601(sample.observed_at), C.Cartesian3.fromArray(vector));
          }
        }
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
      updateClock(scene, status.epoch_utc, seconds ?? 0);
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
      const scene = scenes.get(id);
      if (scene?.viewer) updateClock(scene, epoch, seconds);
    },
    command(id, action) {
      const scene = scenes.get(id), viewer = scene?.viewer;
      if (!viewer) return;
      if (action === 'reset') {
        scene.follow = false; viewer.trackedEntity = undefined;
        scene.autoFrame = true;
        frameEarth(scene);
      } else if (action === 'follow') {
        scene.autoFrame = false;
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
      else if (action === 'in' || action === 'out') {
        scene.autoFrame = false;
        const distance = viewer.camera.positionCartographic.height * .3;
        if (action === 'in') viewer.camera.zoomIn(distance);
        else viewer.camera.zoomOut(distance);
      }
    },
    diagnostics(id) {
      const scene = scenes.get(id);
      return JSON.stringify({ error: scene?.error ?? scene?.lightingError ?? null, fps: scene?.fps ?? null });
    },
    destroy(id) {
      const scene = scenes.get(id);
      scene?.resizeObserver?.disconnect();
      if (scene?.viewer) {
        for (const [type, handler] of Object.entries(scene.cameraInput ?? {})) {
          scene.viewer.canvas.removeEventListener(type, handler);
        }
        scene.viewer.destroy();
      }
      scenes.delete(id);
    }
  };
})();
