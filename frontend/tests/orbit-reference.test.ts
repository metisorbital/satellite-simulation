import { describe, expect, it } from 'vitest';
import { Cartesian3, JulianDate, ReferenceFrame } from 'cesium';
import references from '../../tests/fixtures/orbit-interpolation.json';
import { createPositionProperty } from '../src/scene/sampled-position';

describe('P09: rendered orbital interpolation against independent dense integration', () => {
  it('matches authoritative samples and independent subsecond positions for three orbits', () => {
    let maximumError = 0;
    for (const interval of references.cases) {
      const property = createPositionProperty();
      for (const sample of interval.endpoints) {
        property.addSample(
          JulianDate.fromIso8601(sample.at),
          Cartesian3.fromArray(sample.position_m),
          [Cartesian3.fromArray(sample.velocity_m_s)],
        );
      }
      expect(property.referenceFrame).toBe(ReferenceFrame.FIXED);
      for (const sample of interval.endpoints) {
        const rendered = property.getValue(JulianDate.fromIso8601(sample.at));
        expect(rendered).toBeDefined();
        expect(
          Cartesian3.distance(rendered!, Cartesian3.fromArray(sample.position_m)),
        ).toBeLessThan(references.sample_tolerance_m);
      }
      for (const sample of interval.references) {
        const rendered = property.getValue(JulianDate.fromIso8601(sample.at));
        expect(rendered).toBeDefined();
        const error = Cartesian3.distance(rendered!, Cartesian3.fromArray(sample.position_m));
        maximumError = Math.max(maximumError, error);
        expect(error).toBeLessThan(references.tolerance_m);
      }
      const after = JulianDate.addSeconds(
        JulianDate.fromIso8601(interval.endpoints[1].at),
        0.01,
        new JulianDate(),
      );
      expect(property.getValue(after)).toBeUndefined();
    }
    console.info(
      `P09: ${references.cases.length * 3} independent positions; max error ${maximumError} m`,
    );
  });
});
