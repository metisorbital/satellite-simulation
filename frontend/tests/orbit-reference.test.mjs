import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { test } from 'node:test';
import * as Cesium from 'cesium';
import '../web/sampled-position.js';
const references = JSON.parse(await readFile(new URL('../../tests/fixtures/orbit-interpolation.json', import.meta.url)));
test('Hermite renderer matches independent dense orbit integration without extrapolation', () => {
  let maximumError = 0;
  for (const interval of references.cases) {
    const property = globalThis.metisCreatePosition(Cesium);
    for (const sample of interval.endpoints) property.addSample(Cesium.JulianDate.fromIso8601(sample.at), Cesium.Cartesian3.fromArray(sample.position_m), [Cesium.Cartesian3.fromArray(sample.velocity_m_s)]);
    assert.equal(property.referenceFrame, Cesium.ReferenceFrame.FIXED);
    for (const sample of [...interval.endpoints, ...interval.references]) {
      const rendered = property.getValue(Cesium.JulianDate.fromIso8601(sample.at));
      assert.ok(rendered);
      const error = Cesium.Cartesian3.distance(rendered, Cesium.Cartesian3.fromArray(sample.position_m));
      maximumError = Math.max(maximumError, error);
      assert.ok(error < (interval.endpoints.includes(sample) ? references.sample_tolerance_m : references.tolerance_m));
    }
    assert.equal(property.getValue(Cesium.JulianDate.addSeconds(Cesium.JulianDate.fromIso8601(interval.endpoints[1].at), .01, new Cesium.JulianDate())), undefined);
  }
  console.log(`Independent interpolation maximum error: ${maximumError} m`);
});

test('resync fills older sequence gaps after newer samples were rendered', () => {
  const property = globalThis.metisCreatePosition(Cesium);
  const epoch = '2026-01-01T00:00:00Z';
  const frame = (sequence, position) => ({sequence,
    observed_at: new Date(Date.parse(epoch) + sequence * 1000).toISOString(),
    channels: {'orbit.position_itrf_m': {quality:'valid', value:position},
      'orbit.velocity_itrf_m_s': {quality:'valid', value:[0,0,0]}}});
  const first = frame(0,[1,2,3]), last = frame(4,[4,5,6]), late = frame(2,[99,88,77]);
  globalThis.metisAddSamples(property, [first,last], epoch, Cesium);
  globalThis.metisAddSamples(property, [first,late,last], epoch, Cesium);
  assert.deepEqual(property.getValue(Cesium.JulianDate.fromIso8601(late.observed_at)), new Cesium.Cartesian3(99,88,77));
});
