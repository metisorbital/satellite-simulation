/* Shared with the independent numerical fixture test. No extrapolation. */
globalThis.metisCreatePosition = (Cesium) => {
  const property = new Cesium.SampledPositionProperty(Cesium.ReferenceFrame.FIXED, 1);
  property.setInterpolationOptions({interpolationDegree: 3, interpolationAlgorithm: Cesium.HermitePolynomialApproximation});
  property.forwardExtrapolationType = property.backwardExtrapolationType = Cesium.ExtrapolationType.NONE;
  return property;
};

/** Merge a bounded committed window, including samples delivered late by resync. */
globalThis.metisAddSamples = (property, frames, epoch, Cesium) => {
  if (frames.length) property.removeSamples(new Cesium.TimeInterval({
    start: Cesium.JulianDate.fromIso8601(epoch),
    stop: Cesium.JulianDate.fromIso8601(frames[0].observed_at), isStopIncluded: false,
  }));
  for (const frame of frames) {
    const p = frame.channels['orbit.position_itrf_m'], v = frame.channels['orbit.velocity_itrf_m_s'];
    if (p?.quality === 'valid' && v?.quality === 'valid') {
      property.addSample(Cesium.JulianDate.fromIso8601(frame.observed_at),
        Cesium.Cartesian3.fromArray(p.value), [Cesium.Cartesian3.fromArray(v.value)]);
    }
  }
};
