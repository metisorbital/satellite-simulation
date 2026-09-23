import {
  ExtrapolationType,
  HermitePolynomialApproximation,
  ReferenceFrame,
  SampledPositionProperty,
} from 'cesium';

/** Interpolate supplied ITRS positions and velocities; never extrapolate a future state. */
export function createPositionProperty(): SampledPositionProperty {
  const property = new SampledPositionProperty(ReferenceFrame.FIXED, 1);
  property.setInterpolationOptions({
    interpolationDegree: 3,
    interpolationAlgorithm: HermitePolynomialApproximation,
  });
  property.forwardExtrapolationType = ExtrapolationType.NONE;
  property.backwardExtrapolationType = ExtrapolationType.NONE;
  return property;
}
