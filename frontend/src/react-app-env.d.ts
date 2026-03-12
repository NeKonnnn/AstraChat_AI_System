/// <reference types="react-scripts" />

declare module 'three' {
  export const Scene: new () => any;
  export const PerspectiveCamera: new (a: number, b: number, c: number, d: number) => any;
  export const WebGLRenderer: new (params?: any) => any;
  export const ShaderMaterial: new (params?: any) => any;
  export const Mesh: new (geo: any, mat: any) => any;
  export const IcosahedronGeometry: new (r: number, d: number) => any;
  export const Vector2: new (x?: number, y?: number) => any;
  export const Clock: new () => any;
  export const DoubleSide: number;
  export const SRGBColorSpace: number;
}
declare module 'three/examples/jsm/postprocessing/EffectComposer';
declare module 'three/examples/jsm/postprocessing/RenderPass';
declare module 'three/examples/jsm/postprocessing/UnrealBloomPass';
declare module 'three/examples/jsm/postprocessing/OutputPass';
