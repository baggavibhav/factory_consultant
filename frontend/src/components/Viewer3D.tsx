import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { PointerLockControls } from "three/examples/jsm/controls/PointerLockControls.js";
import { VRButton } from "three/examples/jsm/webxr/VRButton.js";
import { Loader2 } from "lucide-react";
import type { Label } from "../lib/api";

export type LayerKey =
  | "zones" | "openings" | "equipment" | "roof" | "external" | "internal" | "cold" | "mezz" | "site"
  | "frames" | "secondary" | "bracing" | "foundations"
  | "electrical" | "water" | "drainage" | "fire" | "hvac" | "air" | "gas";

export const LAYERS: { key: LayerKey; label: string; group: "Architecture" | "Structure" | "Services"; swatch: string; nodes: string[] }[] = [
  { key: "zones", label: "Floor zones", group: "Architecture", swatch: "#f2d48c", nodes: ["zone_production", "zone_storage", "zone_cold", "zone_dispatch", "zone_office", "zone_amenity", "zone_utility"] },
  { key: "equipment", label: "Production equipment (sample)", group: "Architecture", swatch: "#bcc4cc", nodes: ["mep_equipment", "mep_equipment_future"] },
  { key: "roof", label: "Roof sheeting", group: "Architecture", swatch: "#9aa3ad", nodes: ["roof"] },
  { key: "external", label: "External walls", group: "Architecture", swatch: "#d6cfbf", nodes: ["walls_external", "plinth"] },
  { key: "internal", label: "Internal walls", group: "Architecture", swatch: "#ede8dc", nodes: ["walls_internal"] },
  { key: "cold", label: "Cold-room panels", group: "Architecture", swatch: "#8fbad4", nodes: ["cold_panels"] },
  { key: "mezz", label: "Mezzanine", group: "Architecture", swatch: "#c7b28f", nodes: ["mezzanine", "str_mezz_beam", "str_mezz_column"] },
  { key: "site", label: "Site and outbuildings", group: "Architecture", swatch: "#b8b2a3", nodes: ["boundary_wall", "outbuildings", "silos"] },
  { key: "openings", label: "Doors, docks and exits", group: "Architecture", swatch: "#1f9d55", nodes: ["openings", "exits"] },
  { key: "frames", label: "Portal frames", group: "Structure", swatch: "#c7542a", nodes: ["str_column", "str_internal_column", "str_gable_column", "str_rafter", "str_haunch", "str_eave_beam"] },
  { key: "secondary", label: "Purlins and girts", group: "Structure", swatch: "#5a7899", nodes: ["str_purlin", "str_girt"] },
  { key: "bracing", label: "Bracing", group: "Structure", swatch: "#33383f", nodes: ["str_bracing"] },
  { key: "foundations", label: "Foundation pads", group: "Structure", swatch: "#9e9e99", nodes: ["str_foundation"] },
  { key: "electrical", label: "Electrical", group: "Services", swatch: "#edb30d", nodes: ["mep_electrical", "mep_electrical_fitting", "mep_electrical_support"] },
  { key: "water", label: "Water supply", group: "Services", swatch: "#2e87de", nodes: ["mep_water", "mep_water_fitting", "mep_water_support"] },
  { key: "drainage", label: "Drainage", group: "Services", swatch: "#735433", nodes: ["mep_drainage", "mep_drainage_fitting", "mep_drainage_support"] },
  { key: "fire", label: "Fire protection", group: "Services", swatch: "#d63030", nodes: ["mep_fire", "mep_fire_fitting", "mep_fire_support"] },
  { key: "hvac", label: "Refrigeration and ventilation", group: "Services", swatch: "#009e9e", nodes: ["mep_hvac", "mep_hvac_fitting", "mep_hvac_support"] },
  { key: "air", label: "Compressed air", group: "Services", swatch: "#738599", nodes: ["mep_air", "mep_air_fitting", "mep_air_support"] },
  { key: "gas", label: "Gas", group: "Services", swatch: "#f28019", nodes: ["mep_gas", "mep_gas_fitting", "mep_gas_support"] },
];
export const SERVICE_KEYS: LayerKey[] = ["electrical", "water", "drainage", "fire", "hvac", "air", "gas"];

export type ViewName = "iso" | "structure" | "services" | "plan" | "street" | "inside" | "walk";
const WALL_NODES = ["walls_external", "walls_internal", "cold_panels", "outbuildings", "plinth"];

export interface CameraSync { pos: THREE.Vector3 | null; tgt: THREE.Vector3 | null; v: number; from: string }
export interface Highlight { rooms?: { points: [number, number][]; color: string }[]; markers?: { x: number; y: number; color: string }[]; origin: [number, number] }

export interface WalkSetup { start: [number, number]; origin: [number, number]; ffl: number; rooms: { name: string; points: [number, number][] }[] }
const COLLIDERS = ["walls_external", "walls_internal", "cold_panels", "outbuildings", "mep_equipment", "boundary_wall", "plinth"];
const WHITE_NODES: Record<string, string> = {
  walls_external: "#f4f4f2", walls_internal: "#f7f7f5", cold_panels: "#e9eff3", outbuildings: "#efefec", floor_slab: "#dcdcd8",
  roof: "#e8e8e6", mezzanine: "#e2e2de", plinth: "#e3e3e0", str_column: "#d9d9d6", str_rafter: "#d9d9d6", str_haunch: "#d9d9d6",
  str_eave_beam: "#dededb", str_purlin: "#e6e6e3", str_girt: "#e6e6e3", str_gable_column: "#d9d9d6", str_internal_column: "#d9d9d6",
};

function inPolygon(x: number, y: number, pts: [number, number][]): boolean {
  let inside = false;
  for (let i = 0, j = pts.length - 1; i < pts.length; j = i++) {
    const [xi, yi] = pts[i], [xj, yj] = pts[j];
    if ((yi > y) !== (yj > y) && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) inside = !inside;
  }
  return inside;
}

interface Props {
  sync?: CameraSync;
  walk?: WalkSetup | null;
  white?: boolean;
  onRoom?: (name: string | null) => void;
  onWalkEnd?: () => void;
  highlight?: Highlight | null;
  url: string;
  labels: Label[];
  size: [number, number];
  layers: Record<LayerKey, boolean>;
  xray: boolean;
  showLabels: boolean;
  view: ViewName;
}

function views(w: number, d: number): Record<ViewName, { p: number[]; t: number[] }> {
  return {
    iso: { p: [-w * 0.95, w * 0.7, d * 2.0], t: [0, 0, 0] },
    structure: { p: [-w * 0.85, w * 0.55, d * 1.75], t: [0, 3, 0] },
    services: { p: [-w * 0.6, w * 0.6, d * 1.9], t: [0, 0, d * 0.1] },
    plan: { p: [0, w * 1.45, 0.01], t: [0, 0, 0] },
    street: { p: [-w * 0.1, 6, d * 1.6], t: [0, 4, 0] },
    inside: { p: [-w * 0.2, 3, d * 0.07], t: [-w * 0.47, 3.2, -d * 0.33] },
    walk: { p: [-w * 0.2, 3, d * 0.07], t: [-w * 0.47, 3.2, -d * 0.33] },
  };
}

export default function Viewer3D({ url, labels, size, layers, xray, showLabels, view, sync, highlight, walk, white, onRoom, onWalkEnd }: Props) {
  const host = useRef<HTMLDivElement>(null);
  const labelHost = useRef<HTMLDivElement>(null);
  const state = useRef<{
    nodes: Record<string, THREE.Mesh>;
    camera?: THREE.PerspectiveCamera;
    controls?: OrbitControls;
    ground?: THREE.MeshLambertMaterial;
    edge?: THREE.LineBasicMaterial;
    anim?: { t0: number; p0: THREE.Vector3; q0: THREE.Vector3; p1: THREE.Vector3; q1: THREE.Vector3 };
    scene?: THREE.Scene;
    marks?: THREE.Group;
  }>({ nodes: {} });
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");
  const [room, setRoom] = useState<string | null>(null);
  const [me, setMe] = useState<{ x: number; y: number; heading: number } | null>(null);
  const labelRefs = useRef<{ el: HTMLDivElement; v: THREE.Vector3 }[]>([]);

  // Room-name labels (they can arrive after the model starts loading).
  useEffect(() => {
    const lh = labelHost.current!;
    lh.innerHTML = "";
    labelRefs.current.length = 0;
    for (const l of labels) {
      const d = document.createElement("div");
      d.className = `v-label${l.cold ? " cold" : ""}`;
      d.textContent = l.text.replace(/^\((.*)\)/, "$1");
      d.style.display = "none";
      lh.appendChild(d);
      labelRefs.current.push({ el: d, v: new THREE.Vector3(...l.pos) });
    }
  }, [labels]);
  const props = useRef<{ layers: typeof layers; xray: boolean; showLabels: boolean; walk?: WalkSetup | null;
    onRoom?: (r: string | null) => void; onWalkEnd?: () => void }>({ layers, xray, showLabels, walk, onRoom, onWalkEnd });
  props.current = { layers, xray, showLabels, walk, onRoom: (r: string | null) => { setRoom(r); onRoom?.(r); }, onWalkEnd };
  const walkApi = useRef<{ enter: () => void; exit: () => void } | null>(null);

  // Scene setup, model load and render loop (once per model URL).
  useEffect(() => {
    const el = host.current!;
    const st = state.current;
    st.nodes = {};
    setStatus("loading");

    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    el.appendChild(renderer.domElement);
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(38, 1, 0.3, 3000);
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    controls.maxPolarAngle = Math.PI * 0.495;
    st.camera = camera;
    st.controls = controls;
    st.scene = scene;
    const me = Math.random().toString(36).slice(2);
    let applying = false;
    let seen = -1;
    if (sync) {
      controls.enableDamping = false; // keep two linked viewers perfectly in step
      controls.addEventListener("change", () => {
        if (applying) return;
        sync.pos = camera.position.clone(); sync.tgt = controls.target.clone(); sync.v += 1; sync.from = me; seen = sync.v;
      });
    }

    scene.add(new THREE.HemisphereLight(0xffffff, 0x7d8a95, 1.6));
    const sun = new THREE.DirectionalLight(0xffffff, 1.6);
    sun.position.set(-60, 90, 70);
    scene.add(sun);
    const ground = new THREE.MeshLambertMaterial({ color: 0xd5dce1, transparent: true, opacity: 1 });
    const gm = new THREE.Mesh(new THREE.PlaneGeometry(800, 800), ground);
    gm.rotation.x = -Math.PI / 2;
    gm.position.y = -0.02;
    scene.add(gm);
    st.ground = ground;
    const grid = new THREE.GridHelper(800, 160, 0x000000, 0x000000);
    (grid.material as THREE.Material).transparent = true;
    (grid.material as THREE.Material).opacity = 0.06;
    scene.add(grid);

    const theme = () => {
      const cs = getComputedStyle(document.documentElement);
      scene.background = new THREE.Color(cs.getPropertyValue("--scene-bg").trim() || "#e4e9ec");
      ground.color.set(cs.getPropertyValue("--scene-ground").trim() || "#d5dce1");
      const dark = (scene.background as THREE.Color).getHSL({ h: 0, s: 0, l: 0 }).l < 0.3;
      (grid.material as THREE.LineBasicMaterial).color.set(dark ? 0xffffff : 0x000000);
    };
    theme();
    const mo = new MutationObserver(theme);
    mo.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    const mq = matchMedia("(prefers-color-scheme: dark)");
    mq.addEventListener("change", theme);

    const edge = new THREE.LineBasicMaterial({ color: 0x1d2a35, transparent: true, opacity: 0.3 });
    st.edge = edge;
    let disposed = false;
    new GLTFLoader().load(
      url,
      (gltf) => {
        if (disposed) return;
        gltf.scene.traverse((o) => {
          const m = o as THREE.Mesh;
          if (!m.isMesh) return;
          const mat = m.material as THREE.MeshStandardMaterial;
          mat.side = THREE.DoubleSide;
          if (mat.transparent) mat.depthWrite = false;
          m.userData.baseOpacity = mat.opacity;
          m.userData.baseTransparent = mat.transparent;
          st.nodes[m.name] = m;
        });
        for (const n of ["walls_external", "walls_internal", "cold_panels"]) {
          const m = st.nodes[n];
          if (m) m.add(new THREE.LineSegments(new THREE.EdgesGeometry(m.geometry, 30), edge));
        }
        scene.add(gltf.scene);
        setStatus("ready");
      },
      undefined,
      () => !disposed && setStatus("error"),
    );

    const labelEls = labelRefs.current;

    let w = 1, h = 1;
    const resize = () => {
      w = el.clientWidth || 1; h = el.clientHeight || 1;
      renderer.setSize(w, h, false);
      renderer.domElement.style.width = `${w}px`;
      renderer.domElement.style.height = `${h}px`;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
    };
    const ro = new ResizeObserver(resize);
    ro.observe(el);
    resize();

    const v = views(size[0], size[1]).iso;
    camera.position.set(v.p[0], v.p[1], v.p[2]);
    controls.target.set(v.t[0], v.t[1], v.t[2]);

    // ---- Walkthrough: first-person movement with collisions; VR via WebXR ----
    const rig = new THREE.Group();
    scene.add(rig);
    rig.add(camera);
    renderer.xr.enabled = true;
    renderer.xr.setReferenceSpaceType("local-floor");
    let vrButton: HTMLElement | null = null;
    const xr = (navigator as Navigator & { xr?: { isSessionSupported: (m: string) => Promise<boolean> } }).xr;
    xr?.isSessionSupported("immersive-vr").then((ok) => {
      if (!ok || disposed) return; // only offer VR when a headset can actually be used
      vrButton = VRButton.createButton(renderer);
      vrButton.classList.add("vr-button");
      el.appendChild(vrButton);
    }).catch(() => {});
    const plc = new PointerLockControls(camera, renderer.domElement);
    const keys: Record<string, boolean> = {};
    const onKey = (down: boolean) => (e: KeyboardEvent) => { keys[e.code] = down; };
    const kd = onKey(true), ku = onKey(false);
    window.addEventListener("keydown", kd);
    window.addEventListener("keyup", ku);
    let walking = false;
    let saved: { p: THREE.Vector3; t: THREE.Vector3 } | null = null;
    const eye = 1.7;
    const ray = new THREE.Raycaster();
    const colliders = () => COLLIDERS.map((n) => st.nodes[n]).filter((m): m is THREE.Mesh => !!m && m.visible);
    const blocked = (from: THREE.Vector3, dir: THREE.Vector3, dist: number) => {
      const cs = colliders();
      for (const hgt of [-1.2, -0.5]) {
        ray.set(new THREE.Vector3(from.x, from.y + hgt, from.z), dir);
        ray.far = dist + 0.35;
        if (ray.intersectObjects(cs, false).length) return true;
      }
      return false;
    };
    const toGl = (x: number, y: number, z: number, o: [number, number]) => new THREE.Vector3(x - o[0], z, -(y - o[1]));
    let lastRoom: string | null = null;
    let roomTick = 0;
    const reportRoom = () => {
      const w = props.current.walk;
      if (!w || !props.current.onRoom) return;
      const pos = renderer.xr.isPresenting ? rig.position : camera.position;
      const x = pos.x + w.origin[0], y = w.origin[1] - pos.z;
      const room = w.rooms.find((r) => inPolygon(x, y, r.points))?.name ?? null;
      const dir = new THREE.Vector3();
      camera.getWorldDirection(dir);
      setMe({ x, y, heading: Math.atan2(-dir.z, dir.x) });
      if (room !== lastRoom) { lastRoom = room; props.current.onRoom(room); }
    };
    walkApi.current = {
      enter: () => {
        const w = props.current.walk;
        if (!w) return;
        saved = { p: camera.position.clone(), t: controls.target.clone() };
        controls.enabled = false;
        st.anim = undefined;
        const p = toGl(w.start[0], w.start[1], w.ffl + eye, w.origin);
        camera.position.copy(p);
        camera.rotation.set(0, 0, 0, "YXZ");
        camera.near = 0.05; camera.updateProjectionMatrix();
        walking = true;
      },
      exit: () => {
        walking = false;
        if (plc.isLocked) plc.unlock();
        controls.enabled = true;
        camera.near = 0.3; camera.updateProjectionMatrix();
        if (saved) { camera.position.copy(saved.p); controls.target.copy(saved.t); controls.update(); }
      },
    };
    const onCanvasClick = () => { if (walking && !plc.isLocked) plc.lock(); };
    renderer.domElement.addEventListener("click", onCanvasClick);
    // Touch: drag to look, two buttons in the overlay move forward/back.
    let touchLook: { x: number; y: number } | null = null;
    const onPD = (e: PointerEvent) => { if (walking && e.pointerType === "touch") touchLook = { x: e.clientX, y: e.clientY }; };
    const onPM = (e: PointerEvent) => {
      if (!walking || !touchLook) return;
      const euler = new THREE.Euler(0, 0, 0, "YXZ").setFromQuaternion(camera.quaternion);
      euler.y -= (e.clientX - touchLook.x) * 0.005;
      euler.x = Math.max(-1.4, Math.min(1.4, euler.x - (e.clientY - touchLook.y) * 0.005));
      camera.quaternion.setFromEuler(euler);
      touchLook = { x: e.clientX, y: e.clientY };
    };
    const onPU = () => { touchLook = null; };
    renderer.domElement.addEventListener("pointerdown", onPD);
    renderer.domElement.addEventListener("pointermove", onPM);
    renderer.domElement.addEventListener("pointerup", onPU);
    const onEsc = () => { /* pointer lock released: stay in walk mode, click to resume */ };
    plc.addEventListener("unlock", onEsc);
    renderer.xr.addEventListener("sessionstart", () => {
      const w = props.current.walk;
      if (w) rig.position.copy(toGl(w.start[0], w.start[1], w.ffl, w.origin));
      camera.position.set(0, 0, 0);
    });
    renderer.xr.addEventListener("sessionend", () => { rig.position.set(0, 0, 0); walkApi.current?.exit(); });

    const clock = new THREE.Clock();
    const fwd = new THREE.Vector3(), right = new THREE.Vector3(), step = new THREE.Vector3();
    const walkStep = (dt: number) => {
      const run = keys.ShiftLeft || keys.ShiftRight ? 3.2 : 1.4;
      const mf = (keys.KeyW || keys.ArrowUp || (st as { touchFwd?: boolean }).touchFwd ? 1 : 0) - (keys.KeyS || keys.ArrowDown || (st as { touchBack?: boolean }).touchBack ? 1 : 0);
      const ms = (keys.KeyD ? 1 : 0) - (keys.KeyA ? 1 : 0);
      const turn = (keys.ArrowLeft || keys.KeyQ ? 1 : 0) - (keys.ArrowRight || keys.KeyE ? 1 : 0);
      if (turn) {
        const eu = new THREE.Euler(0, 0, 0, "YXZ").setFromQuaternion(camera.quaternion);
        eu.y += turn * 1.6 * dt;
        camera.quaternion.setFromEuler(eu);
      }
      if (!mf && !ms) return;
      camera.getWorldDirection(fwd); fwd.y = 0; fwd.normalize();
      right.crossVectors(fwd, new THREE.Vector3(0, 1, 0)).normalize();
      step.set(0, 0, 0).addScaledVector(fwd, mf).addScaledVector(right, ms).normalize();
      const dist = run * dt;
      if (!blocked(camera.position, step, dist)) { camera.position.addScaledVector(step, dist); return; }
      // Slide along the wall instead of stopping dead (door frames, corners).
      for (const axis of [new THREE.Vector3(Math.sign(step.x), 0, 0), new THREE.Vector3(0, 0, Math.sign(step.z))]) {
        const part = Math.abs(axis.x ? step.x : step.z);
        if (part > 0.2 && !blocked(camera.position, axis, dist * part)) { camera.position.addScaledVector(axis, dist * part); return; }
      }
    };
    const xrStep = (dt: number) => {
      const session = renderer.xr.getSession();
      if (!session) return;
      for (const src of session.inputSources) {
        const gp = src.gamepad;
        if (!gp || gp.axes.length < 4) continue;
        const [, , sx, sy] = gp.axes;
        if (Math.abs(sx) < 0.15 && Math.abs(sy) < 0.15) continue;
        const xrCam = renderer.xr.getCamera();
        xrCam.getWorldDirection(fwd); fwd.y = 0; fwd.normalize();
        right.crossVectors(fwd, new THREE.Vector3(0, 1, 0)).normalize();
        step.set(0, 0, 0).addScaledVector(fwd, -sy).addScaledVector(right, sx);
        const head = new THREE.Vector3().setFromMatrixPosition(xrCam.matrixWorld);
        const len = step.length();
        if (len > 0 && !blocked(head, step.clone().normalize(), 1.4 * dt * len)) rig.position.addScaledVector(step, 1.4 * dt);
      }
    };

    const tmp = new THREE.Vector3();
    const loop = (now: number) => {
      const dt = Math.min(clock.getDelta(), 0.1);
      if (renderer.xr.isPresenting) { xrStep(dt); }
      else if (walking) { walkStep(dt); }
      if ((roomTick += dt) > 0.3) { roomTick = 0; if (walking || renderer.xr.isPresenting) reportRoom(); }
      const a = st.anim;
      if (a) {
        const k = Math.min(1, (now - a.t0) / 850);
        const e = k < 0.5 ? 2 * k * k : 1 - Math.pow(-2 * k + 2, 2) / 2;
        camera.position.lerpVectors(a.p0, a.p1, e);
        controls.target.lerpVectors(a.q0, a.q1, e);
        if (k >= 1) st.anim = undefined;
      }
      if (sync && sync.v !== seen && sync.from !== me && sync.pos && sync.tgt) {
        applying = true;
        camera.position.copy(sync.pos); controls.target.copy(sync.tgt); controls.update();
        applying = false; seen = sync.v;
      }
      if (!walking && !renderer.xr.isPresenting) controls.update();
      renderer.render(scene, camera);
      if (props.current.showLabels) {
        for (const L of labelEls) {
          tmp.copy(L.v).project(camera);
          if (tmp.z > 1 || tmp.z < -1) { L.el.style.display = "none"; continue; }
          L.el.style.display = "block";
          L.el.style.left = `${((tmp.x + 1) / 2) * w}px`;
          L.el.style.top = `${((1 - tmp.y) / 2) * h}px`;
        }
      }
    };
    renderer.setAnimationLoop(loop);

    return () => {
      disposed = true;
      renderer.setAnimationLoop(null);
      window.removeEventListener("keydown", kd);
      window.removeEventListener("keyup", ku);
      renderer.domElement.removeEventListener("click", onCanvasClick);
      plc.dispose();
      vrButton?.remove();
      walkApi.current = null;
      ro.disconnect();
      mo.disconnect();
      mq.removeEventListener("change", theme);
      controls.dispose();
      renderer.dispose();
      scene.traverse((o) => {
        const m = o as THREE.Mesh;
        if (m.geometry) m.geometry.dispose();
      });
      el.removeChild(renderer.domElement);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [url]);

  // Layer visibility and x-ray.
  useEffect(() => {
    const st = state.current;
    if (status !== "ready") return;
    for (const L of LAYERS) for (const n of L.nodes) if (st.nodes[n]) st.nodes[n].visible = layers[L.key];
    for (const n of WALL_NODES) {
      const m = st.nodes[n];
      if (!m) continue;
      const mat = m.material as THREE.MeshStandardMaterial;
      mat.transparent = xray || m.userData.baseTransparent;
      mat.opacity = xray ? 0.16 : m.userData.baseOpacity;
      mat.depthWrite = !xray;
      mat.needsUpdate = true;
    }
    if (st.edge) st.edge.opacity = xray ? 0.06 : 0.3;
    const see = layers.foundations || layers.drainage || layers.fire;
    if (st.ground) { st.ground.opacity = see ? 0.35 : 1; st.ground.depthWrite = !see; }
    const slab = st.nodes.floor_slab;
    if (slab) {
      const m = slab.material as THREE.MeshStandardMaterial;
      m.transparent = see; m.opacity = see ? 0.35 : 1; m.needsUpdate = true;
    }
  }, [layers, xray, status]);

  // Change highlights (compare view): coloured floor overlays and markers.
  useEffect(() => {
    const st = state.current;
    if (!st.scene) return;
    if (st.marks) { st.scene.remove(st.marks); st.marks.traverse((o) => (o as THREE.Mesh).geometry?.dispose()); }
    if (!highlight) { st.marks = undefined; return; }
    const g = new THREE.Group();
    const [cx, cy] = highlight.origin;
    for (const r of highlight.rooms ?? []) {
      const shape = new THREE.Shape(r.points.map(([x, y]) => new THREE.Vector2(x - cx, y - cy)));
      const m = new THREE.Mesh(new THREE.ShapeGeometry(shape),
        new THREE.MeshBasicMaterial({ color: r.color, transparent: true, opacity: 0.55, depthWrite: false, side: THREE.DoubleSide }));
      m.rotation.x = -Math.PI / 2; m.position.y = 0.8; m.renderOrder = 10;
      g.add(m);
    }
    for (const k of highlight.markers ?? []) {
      const m = new THREE.Mesh(new THREE.CylinderGeometry(0.9, 0.9, 5, 16),
        new THREE.MeshBasicMaterial({ color: k.color, transparent: true, opacity: 0.8, depthWrite: false }));
      m.position.set(k.x - cx, 2.5, -(k.y - cy)); m.renderOrder = 11;
      g.add(m);
    }
    st.scene.add(g);
    st.marks = g;
  }, [highlight, status]);

  // Walk mode on/off.
  useEffect(() => {
    if (status !== "ready") return;
    if (view === "walk" && walk) walkApi.current?.enter();
    else walkApi.current?.exit();
  }, [view, walk, status]);

  // Clean white architecture (services stand out, as in MEP coordination models).
  useEffect(() => {
    const st = state.current;
    if (status !== "ready") return;
    for (const [n, c] of Object.entries(WHITE_NODES)) {
      const m = st.nodes[n];
      if (!m) continue;
      const mat = m.material as THREE.MeshStandardMaterial;
      if (!m.userData.baseColor) m.userData.baseColor = mat.color.clone();
      mat.color.set(white ? c : m.userData.baseColor);
    }
  }, [white, status]);

  // Camera presets.
  useEffect(() => {
    const st = state.current;
    if (!st.camera || !st.controls || view === "walk") return;
    const v = views(size[0], size[1])[view];
    st.anim = {
      t0: performance.now(),
      p0: st.camera.position.clone(), q0: st.controls.target.clone(),
      p1: new THREE.Vector3(v.p[0], v.p[1], v.p[2]), q1: new THREE.Vector3(v.t[0], v.t[1], v.t[2]),
    };
  }, [view, size]);

  return (
    <div className="viewer">
      <div ref={host} style={{ position: "absolute", inset: 0 }} />
      <div ref={labelHost} className="v-labels" style={{ display: showLabels ? "block" : "none" }} />
      {view === "walk" && status === "ready" && (
        <div className="walk-hud">
          <div className="walk-room">{room ?? "Outside"}</div>
          {walk && (() => {
            const xs = walk.rooms.flatMap((r) => r.points.map((p) => p[0]));
            const ys = walk.rooms.flatMap((r) => r.points.map((p) => p[1]));
            const x0 = Math.min(...xs) - 2, x1 = Math.max(...xs) + 2, y0 = Math.min(...ys) - 2, y1 = Math.max(...ys) + 2;
            return (
              <svg className="walk-map" viewBox={`${x0} ${-y1} ${x1 - x0} ${y1 - y0}`} preserveAspectRatio="xMidYMid meet" aria-label="Mini-map">
                {walk.rooms.map((r, i) => (
                  <polygon key={i} points={r.points.map(([x, y]) => `${x},${-y}`).join(" ")}
                    fill={r.name === room ? "#f2b705" : "#e7ebee"} stroke="#6b7680" strokeWidth={(x1 - x0) / 400} />
                ))}
                {me && (
                  <g transform={`translate(${me.x},${-me.y}) rotate(${(-me.heading * 180) / Math.PI})`}>
                    <circle r={(x1 - x0) / 70} fill="#17222c" />
                    <path d={`M0,0 L${(x1 - x0) / 25},0`} stroke="#17222c" strokeWidth={(x1 - x0) / 150} />
                  </g>
                )}
              </svg>
            );
          })()}
          <div className="walk-help">W / ↑ forward · S / ↓ back · ← → turn · A D step sideways · Shift run · click the view to look with the mouse, Esc to release</div>
          <div className="walk-pad">
            <button aria-label="Walk forward" onPointerDown={() => { (state.current as { touchFwd?: boolean }).touchFwd = true; }}
              onPointerUp={() => { (state.current as { touchFwd?: boolean }).touchFwd = false; }}
              onPointerLeave={() => { (state.current as { touchFwd?: boolean }).touchFwd = false; }}>▲</button>
            <button aria-label="Walk back" onPointerDown={() => { (state.current as { touchBack?: boolean }).touchBack = true; }}
              onPointerUp={() => { (state.current as { touchBack?: boolean }).touchBack = false; }}
              onPointerLeave={() => { (state.current as { touchBack?: boolean }).touchBack = false; }}>▼</button>
          </div>
          {onWalkEnd && <button className="btn sm walk-exit" onClick={onWalkEnd}>Exit walkthrough</button>}
        </div>
      )}
            {status === "loading" && <div className="v-loading"><Loader2 className="spin" size={22} /> Loading model</div>}
      {status === "error" && <div className="v-loading">The 3D model couldn't be loaded. Rebuild the model and try again.</div>}
    </div>
  );
}
