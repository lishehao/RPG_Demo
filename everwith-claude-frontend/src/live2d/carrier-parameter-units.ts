/** Derived internal parameter units; the source remains track.parameters, after its existing gate. */
export const CARRIER_SP_PARAMETER = 'ParamCarrierSP16384';
export const CARRIER_SP_SCALE = 16384;
export function carrierSurpriseValues(sourceParameter: number) {
  if (!Number.isFinite(sourceParameter)) throw new Error('Nonfinite surprise input');
  const logical = Math.fround(Math.max(0, Math.min(1, sourceParameter)));
  // Multiplication by 2^14 is exact for the bounded Float32 inputs used here.
  const encoded = Math.fround(logical * CARRIER_SP_SCALE);
  if (Math.fround(encoded / CARRIER_SP_SCALE) !== logical) throw new Error('Parameter units lost a Float32 value');
  return { logical, encoded };
}
export function applyCarrierSurprise(
  model: { setParameterValueByIndex(index: number, value: number, weight?: number): void },
  originalSurpriseIndex: number, carrierSurpriseIndex: number, sourceParameter: number,
) {
  if (originalSurpriseIndex < 0 || carrierSurpriseIndex < 0 || originalSurpriseIndex === carrierSurpriseIndex) throw new Error('Invalid parameter inventory');
  const values = carrierSurpriseValues(sourceParameter);
  model.setParameterValueByIndex(originalSurpriseIndex, values.logical, 1);
  model.setParameterValueByIndex(carrierSurpriseIndex, values.encoded, 1);
  return values;
}
