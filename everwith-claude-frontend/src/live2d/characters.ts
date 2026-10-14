/**
 * Frozen per-character runtime pins (verification/MODEL_PINS.json) and face framing
 * calibration (reference/frontend/character-calibration/feed-face-framing.json).
 * Identity is source_id + version → character key. Never chosen by display name.
 */
export type CharacterKey = 'arthur' | 'lena' | 'marcus' | 'nora' | 'iris'
export type ExpressionMode = 'discrete' | 'blink_swap' | 'carrier'
export type CharacterRuntimeConfig = {
  key: CharacterKey; sourceId: string; version: '1'; candidateId: string | null
  model3: string; mocSha256: string; textureSha256: string
  headCaps: {x: number; y: number; z: number}
  gazeEnabled: false | null
  /** Authored idle loop (12 s) for characters that ship one; procedural otherwise. */
  idle: {kind: 'authored'; motion: string; scale: {x: number; y: number; z: number}} | {kind: 'procedural'}
  expressionMode: ExpressionMode
  /** featureSafety and referenceFace boxes in model units: [xmin, xmax, ymin, ymax]. */
  faceBox: [number, number, number, number]
  referenceFace: [number, number, number, number]
  /** Procedural seed so two characters never move in lockstep. */
  seed: number
  staticPortrait: string
}
const L = '/handoff/assets/live2d'
const P = '/handoff/assets/companions/portraits'
export const CHARACTERS: Record<CharacterKey, CharacterRuntimeConfig> = {
  arthur: {key: 'arthur', sourceId: 'official-arthur', version: '1', candidateId: 'arthur-dynamic-continuity-r7',
    model3: `${L}/arthur/arthur-expressions.model3.json`, mocSha256: '047e051a47f4eac96f68446d96a8e5d993a828319992eec05fcebb1da803785f', textureSha256: '64bd1c45f9f75e1228107b5c99ea5c8a8d14c44bd7a2878c15b78441f188a33a',
    headCaps: {x: 8, y: 4, z: 2.5}, gazeEnabled: null, idle: {kind: 'procedural'}, expressionMode: 'discrete',
    faceBox: [-0.2191279052851829, 0.21654016320604141, -0.08003866869688367, 0.4117642282839455], referenceFace: [-0.1631538676163058, 0.16058922978759538, -0.035257008684704806, 0.36681102610410304],
    seed: 7, staticPortrait: `${P}/arthur-r7-neutral.png`},
  lena: {key: 'lena', sourceId: 'official-lena', version: '1', candidateId: 'lena-soft-anime-v2-rebound-20261008',
    model3: `${L}/lena/lena-soft-anime-v2.model3.json`, mocSha256: '91ade7978c80712860740e997eba5393686bb1f4948b622791eb6980659548c1', textureSha256: 'cc41ed45da39ec00463401a0a8b72e0d5f4a7833f6a75a57731980a816deb18d',
    headCaps: {x: 8, y: 2, z: 1.5}, gazeEnabled: null, idle: {kind: 'authored', motion: 'lena-soft-anime-v2.idle.motion3.json', scale: {x: 1, y: .5, z: .3}}, expressionMode: 'blink_swap',
    faceBox: [-0.22483677648678516, 0.17014762023557162, -0.02338236550358241, 0.41680199203841456], referenceFace: [-0.18631876165307384, 0.13164158593546016, 0.011334810144414162, 0.38141980736865894],
    seed: 13, staticPortrait: `${P}/lena-soft-anime-v2-neutral.png`},
  marcus: {key: 'marcus', sourceId: 'official-marcus', version: '1', candidateId: 'marcus-related-face-r3-20261007',
    model3: `${L}/marcus/marcus-live2d.model3.json`, mocSha256: 'd50f76fa6a7902a06add8d5c76f9287c987dc82fd0efd467cd3989bf9ddc0c60', textureSha256: '44c0b0979b5c11f441aa85a8f1f1a72e4f2035b7c7cd38ae7ee977a2edf12d7e',
    headCaps: {x: 8, y: 2, z: 1.5}, gazeEnabled: null, idle: {kind: 'authored', motion: 'marcus-live2d.idle.motion3.json', scale: {x: 1, y: .5, z: .3}}, expressionMode: 'blink_swap',
    faceBox: [-0.2146165896195292, 0.14144645500183106, -0.10949443454649993, 0.31477644123145654], referenceFace: [-0.17261634241930185, 0.088256528939232, -0.07407007280791592, 0.27887558506137683],
    seed: 29, staticPortrait: `${P}/marcus-r3-neutral.png`},
  nora: {key: 'nora', sourceId: 'official-nora', version: '1', candidateId: 'nora-eye-contact-r4',
    model3: `${L}/nora/nora-expressions.model3.json`, mocSha256: 'd3eb973f5044ac9e7d14f2e348ef5c6c0d2b7b3b1f4c46814f4f9c1c427c2b5c', textureSha256: 'e1674a86cade714845c4531b3d4c7910e3c682191986443a1e2f7d238b3dfe86',
    headCaps: {x: 3, y: 1, z: 1}, gazeEnabled: false, idle: {kind: 'authored', motion: 'nora-expressions.idle.motion3.json', scale: {x: 1, y: .5, z: .3}}, expressionMode: 'blink_swap',
    faceBox: [-0.22058783745073712, 0.2532342399360804, -0.17106284177828168, 0.44940440879291654], referenceFace: [-0.17970930893848552, 0.21248404022403025, -0.13310085794185714, 0.41074058026426175],
    seed: 41, staticPortrait: `${P}/nora-r4-neutral.png`},
  iris: {key: 'iris', sourceId: 'official-iris', version: '1', candidateId: 'accepted-iris-draw-order-carrier',
    model3: `${L}/iris/iris-expressions.model3.json`, mocSha256: 'a53e1e6898e5ddb216052d5da3a743636ce24532a42a94d24c72ba70a159d53e', textureSha256: '27ad28e7b28994fd4b9f47145d332ff10dc896fac0810f1d0007e46f0bdf31e2',
    headCaps: {x: 3, y: 1, z: 1}, gazeEnabled: null, idle: {kind: 'procedural'}, expressionMode: 'carrier',
    faceBox: [-0.22174425709547516, 0.22352484281679533, -0.11010866583902296, 0.39697999930645794], referenceFace: [-0.18693994162433292, 0.18874300341900757, -0.07811520948926297, 0.36447020282016995],
    seed: 53, staticPortrait: `${P}/iris-local-neutral.png`},
}
export function characterFor(sourceId: string | null | undefined, version: string | null | undefined): CharacterRuntimeConfig | null {
  if (version !== '1' || !sourceId?.startsWith('official-')) return null
  const key = sourceId.slice('official-'.length) as CharacterKey
  return CHARACTERS[key] ?? null
}
export type FramingPreset = 'stage' | 'card' | 'rail' | 'zoom' | 'thumb'
