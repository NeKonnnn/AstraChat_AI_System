import React, { useRef, useEffect, useCallback } from 'react';

// Vertex shader: Perlin noise деформация по звуку
const vertexShader = `
  uniform float u_time;
  uniform float u_frequency;

  vec3 mod289(vec3 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
  vec4 mod289(vec4 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
  vec4 permute(vec4 x) { return mod289(((x*34.0)+10.0)*x); }
  vec4 taylorInvSqrt(vec4 r) { return 1.79284291400159 - 0.85373472095314 * r; }
  vec3 fade(vec3 t) { return t*t*t*(t*(t*6.0-15.0)+10.0); }

  float pnoise(vec3 P, vec3 rep) {
    vec3 Pi0 = mod(floor(P), rep);
    vec3 Pi1 = mod(Pi0 + vec3(1.0), rep);
    Pi0 = mod289(Pi0); Pi1 = mod289(Pi1);
    vec3 Pf0 = fract(P); vec3 Pf1 = Pf0 - vec3(1.0);
    vec4 ix = vec4(Pi0.x, Pi1.x, Pi0.x, Pi1.x);
    vec4 iy = vec4(Pi0.yy, Pi1.yy);
    vec4 iz0 = Pi0.zzzz; vec4 iz1 = Pi1.zzzz;
    vec4 ixy = permute(permute(ix) + iy);
    vec4 ixy0 = permute(ixy + iz0); vec4 ixy1 = permute(ixy + iz1);
    vec4 gx0 = ixy0 * (1.0/7.0); vec4 gy0 = fract(floor(gx0)*(1.0/7.0))-0.5;
    gx0 = fract(gx0); vec4 gz0 = vec4(0.5)-abs(gx0)-abs(gy0);
    vec4 sz0 = step(gz0, vec4(0.0)); gx0 -= sz0*(step(0.0,gx0)-0.5); gy0 -= sz0*(step(0.0,gy0)-0.5);
    vec4 gx1 = ixy1*(1.0/7.0); vec4 gy1 = fract(floor(gx1)*(1.0/7.0))-0.5;
    gx1 = fract(gx1); vec4 gz1 = vec4(0.5)-abs(gx1)-abs(gy1);
    vec4 sz1 = step(gz1, vec4(0.0)); gx1 -= sz1*(step(0.0,gx1)-0.5); gy1 -= sz1*(step(0.0,gy1)-0.5);
    vec3 g000=vec3(gx0.x,gy0.x,gz0.x); vec3 g100=vec3(gx0.y,gy0.y,gz0.y);
    vec3 g010=vec3(gx0.z,gy0.z,gz0.z); vec3 g110=vec3(gx0.w,gy0.w,gz0.w);
    vec3 g001=vec3(gx1.x,gy1.x,gz1.x); vec3 g101=vec3(gx1.y,gy1.y,gz1.y);
    vec3 g011=vec3(gx1.z,gy1.z,gz1.z); vec3 g111=vec3(gx1.w,gy1.w,gz1.w);
    vec4 norm0 = taylorInvSqrt(vec4(dot(g000,g000),dot(g010,g010),dot(g100,g100),dot(g110,g110)));
    g000*=norm0.x; g010*=norm0.y; g100*=norm0.z; g110*=norm0.w;
    vec4 norm1 = taylorInvSqrt(vec4(dot(g001,g001),dot(g011,g011),dot(g101,g101),dot(g111,g111)));
    g001*=norm1.x; g011*=norm1.y; g101*=norm1.z; g111*=norm1.w;
    float n000=dot(g000,Pf0); float n100=dot(g100,vec3(Pf1.x,Pf0.yz));
    float n010=dot(g010,vec3(Pf0.x,Pf1.y,Pf0.z)); float n110=dot(g110,vec3(Pf1.xy,Pf0.z));
    float n001=dot(g001,vec3(Pf0.xy,Pf1.z)); float n101=dot(g101,vec3(Pf1.x,Pf0.y,Pf1.z));
    float n011=dot(g011,vec3(Pf0.x,Pf1.yz)); float n111=dot(g111,Pf1);
    vec3 fxyz=fade(Pf0);
    vec4 nz=mix(vec4(n000,n100,n010,n110),vec4(n001,n101,n011,n111),fxyz.z);
    vec2 nyz=mix(nz.xy,nz.zw,fxyz.y);
    return 2.2*mix(nyz.x,nyz.y,fxyz.x);
  }

  varying vec3 vNormal;
  varying vec3 vPosition;

  void main() {
    vNormal = normalize(normalMatrix * normal);
    vPosition = position;
    vec3 posT = position + vec3(u_time * 0.8, u_time * 0.55, u_time * 0.4);
    float noise = 3.0 * pnoise(posT, vec3(10.0));
    // При голосе (u_frequency > 0) волны сильно вырастают, в тишине — мягкая пульсация
    float base = 0.35 + 0.15 * sin(u_time * 1.8);
    float displacement = (u_frequency * 9.0 + base) * (noise / 8.0);
    vec3 newPos = position + normal * displacement;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(newPos, 1.0);
  }
`;

// Fragment shader: сочный градиент голубой → фиолетовый → пурпурный
const fragmentShader = `
  uniform float u_frequency;
  varying vec3 vNormal;
  varying vec3 vPosition;

  void main() {
    vec3 n = normalize(vNormal);
    float pulse = 0.8 + 0.2 * u_frequency;

    vec3 cyan    = vec3(0.05, 0.95, 1.0);
    vec3 blue    = vec3(0.2,  0.45, 1.0);
    vec3 purple  = vec3(0.65, 0.1,  1.0);
    vec3 magenta = vec3(1.0,  0.05, 0.55);

    float t  = clamp(vPosition.y / 4.0 * 0.5 + 0.5, 0.0, 1.0);
    float t2 = clamp(vPosition.x / 4.0 * 0.5 + 0.5, 0.0, 1.0);

    vec3 color = mix(mix(magenta, purple, t2), mix(blue, cyan, t2), t);
    color *= pulse;

    // Усиленное свечение краёв при активном голосе
    float rim = pow(1.0 - abs(dot(n, vec3(0.0, 0.0, 1.0))), 0.7);
    color += vec3(0.35, 0.55, 1.0) * rim * (0.8 + 0.6 * u_frequency);
    color = clamp(color, 0.0, 1.0);

    gl_FragColor = vec4(color, 1.0);
  }
`;

export interface VoiceVisualization3DProps {
  stream: MediaStream | null;
  className?: string;
  style?: React.CSSProperties;
}

export default function VoiceVisualization3D({ stream, className, style }: VoiceVisualization3DProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const sceneRef    = useRef<any>(null);
  const cameraRef   = useRef<any>(null);
  const rendererRef = useRef<any>(null);
  const meshRef     = useRef<any>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const dataRef     = useRef<Uint8Array | null>(null);
  const rafRef      = useRef<number | null>(null);
  const uniformsRef = useRef<{ u_time: { value: number }; u_frequency: { value: number } } | null>(null);

  const cleanup = useCallback(() => {
    if (rafRef.current !== null) { cancelAnimationFrame(rafRef.current); rafRef.current = null; }
    try { audioCtxRef.current?.close(); } catch (_) {}
    audioCtxRef.current = null; analyserRef.current = null; dataRef.current = null;
    if (rendererRef.current) {
      try { rendererRef.current.dispose(); rendererRef.current.forceContextLoss(); } catch (_) {}
      rendererRef.current = null;
    }
    sceneRef.current = null; cameraRef.current = null; meshRef.current = null; uniformsRef.current = null;
  }, []);

  useEffect(() => {
    if (!stream || !containerRef.current) return;

    // Динамически импортируем three, чтобы не тащить типы
    let THREE_local: any;
    let cancelled = false;
    const container = containerRef.current;

    import('three').then((mod) => {
      if (cancelled) return;
      THREE_local = mod;

      const width  = container.clientWidth  || 360;
      const height = container.clientHeight || 360;

      // Сцена
      const scene = new THREE_local.Scene();
      sceneRef.current = scene;

      const camera = new THREE_local.PerspectiveCamera(45, width / height, 0.1, 1000);
      camera.position.set(0, -2, 14);
      camera.lookAt(0, 0, 0);
      cameraRef.current = camera;

      // Рендерер с полностью прозрачным фоном
      const renderer = new THREE_local.WebGLRenderer({ antialias: true, alpha: true, premultipliedAlpha: false });
      renderer.setSize(width, height);
      renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
      renderer.outputColorSpace = THREE_local.SRGBColorSpace;
      renderer.setClearColor(0x000000, 0);  // полностью прозрачный
      renderer.domElement.style.background = 'transparent';
      renderer.domElement.style.position   = 'absolute';
      renderer.domElement.style.top        = '0';
      renderer.domElement.style.left       = '0';
      container.appendChild(renderer.domElement);
      rendererRef.current = renderer;

      // Материал и меш
      const uniforms = { u_time: { value: 0 }, u_frequency: { value: 0 } };
      uniformsRef.current = uniforms;

      const material = new THREE_local.ShaderMaterial({
        uniforms,
        vertexShader,
        fragmentShader,
        side: THREE_local.DoubleSide,
        wireframe: true,
      });

      const geometry = new THREE_local.IcosahedronGeometry(4, 30);
      const mesh = new THREE_local.Mesh(geometry, material);
      scene.add(mesh);
      meshRef.current = mesh;

      // Аудио-анализ из микрофона
      try {
        const audioCtx: AudioContext = new (
          window.AudioContext ||
          (window as any).webkitAudioContext
        )();
        const src = audioCtx.createMediaStreamSource(stream);
        const analyser = audioCtx.createAnalyser();
        analyser.fftSize = 256;
        src.connect(analyser);
        const buf = new Uint8Array(analyser.frequencyBinCount);
        audioCtxRef.current = audioCtx;
        analyserRef.current = analyser;
        dataRef.current = buf;
      } catch (e) {
        console.warn('VoiceVisualization3D: audio error', e);
      }

      const clock = new THREE_local.Clock();

      const animate = () => {
        if (!uniformsRef.current) return;
        uniformsRef.current.u_time.value = clock.getElapsedTime();
        if (analyserRef.current && dataRef.current) {
          analyserRef.current.getByteFrequencyData(dataRef.current as any);
          const avg = dataRef.current.reduce((s, v) => s + v, 0) / dataRef.current.length;
          uniformsRef.current.u_frequency.value = Math.min(avg / 255, 1);
        }
        if (meshRef.current) meshRef.current.rotation.y += 0.002;
        // Прямой рендер без EffectComposer — фон остаётся прозрачным
        renderer.render(scene, camera);
        rafRef.current = requestAnimationFrame(animate);
      };
      animate();

      const onResize = () => {
        if (!container || !cameraRef.current || !rendererRef.current) return;
        const w = container.clientWidth;
        const h = container.clientHeight;
        cameraRef.current.aspect = w / h;
        cameraRef.current.updateProjectionMatrix();
        rendererRef.current.setSize(w, h);
      };
      window.addEventListener('resize', onResize);

      // Сохраняем cleanup в замыкании
      (container as any).__vv3d_cleanup = () => {
        window.removeEventListener('resize', onResize);
        cleanup();
        if (container.contains(renderer.domElement)) container.removeChild(renderer.domElement);
      };
    });

    return () => {
      cancelled = true;
      const fn = (container as any).__vv3d_cleanup;
      if (fn) { fn(); delete (container as any).__vv3d_cleanup; }
      else cleanup();
    };
  }, [stream, cleanup]);

  if (!stream) return null;

  return (
    <div
      ref={containerRef}
      className={className}
      style={{
        position: 'absolute',
        top: 0,
        left: 0,
        width: '100%',
        height: '100%',
        background: 'transparent',
        pointerEvents: 'none',
        // CSS bloom: яркое свечение вместо EffectComposer
        filter: 'drop-shadow(0 0 22px rgba(130, 60, 255, 0.9)) drop-shadow(0 0 50px rgba(60, 180, 255, 0.65))',
        ...style,
      }}
      aria-hidden
    />
  );
}
