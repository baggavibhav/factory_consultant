import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { Loader2 } from "lucide-react";
import type { Label } from "../lib/api";

export type LayerKey =
  | "zones" | "roof" | "external" | "internal" | "cold" | "mezz" | "site"
  | "frames" | "secondary" | "bracing" | "foundations";

export const LAYERS: { key: LayerKey; label: string; group: "Architecture" | "Structure"; swatch: string; nodes: string[] }[] = [
  { key: "zones", label: "Floor zones", group: "Architecture", swatch: "#f2d48c", nodes: ["zone_production", "zone_storage", "zone_cold", "zone_dispatch", "zone_office", "zone_amenity", "zone_utility"] },
  { key: "roof", label: "Roof sheeting", group: "Architecture", swatch: "#9aa3ad", nodes: ["roof"] },
  { key: "external", label: "External walls", group: "Architecture", swatch: "#d6cfbf", nodes: ["walls_external"] },
  { key: "internal", label: "Internal walls", group: "Architecture", swatch: "#ede8dc", nodes: ["walls_internal"] },
  { key: "cold", label: "Cold-room panels", group: "Architecture", swatch: "#8fbad4", nodes: ["cold_panels"] },
  { key: "mezz", label: "Mezzanine", group: "Architecture", swatch: "#c7b28f", nodes: ["mezzanine"] },
  { key: "site", label: "Site and outbuildings", group: "Architecture", swatch: "#b8b2a3", nodes: ["boundary_wall", "outbuildings"] },
  { key: "frames", label: "Portal frames", group: "Structure", swatch: "#c7542a", nodes: ["str_column", "str_gable_column", "str_rafter", "str_eave_beam"] },
  { key: "secondary", label: "Purlins and girts", group: "Structure", swatch: "#5a7899", nodes: ["str_purlin", "str_girt"] },
  { key: "bracing", label: "Bracing", group: "Structure", swatch: "#33383f", nodes: ["str_bracing"] },
  { key: "foundations", label: "Foundation pads", group: "Structure", swatch: "#9e9e99", nodes: ["str_foundation"] },
];

export type ViewName = "iso" | "structure" | "plan" | "street" | "inside";
const WALL_NODES = ["walls_external", "walls_internal", "cold_panels", "outbuildings"];

interface Props {
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
    plan: { p: [0, w * 1.45, 0.01], t: [0, 0, 0] },
    street: { p: [-w * 0.1, 6, d * 1.6], t: [0, 4, 0] },
    inside: { p: [-w * 0.2, 3, d * 0.07], t: [-w * 0.47, 3.2, -d * 0.33] },
  };
}

export default function Viewer3D({ url, labels, size, layers, xray, showLabels, view }: Props) {
  const host = useRef<HTMLDivElement>(null);
  const labelHost = useRef<HTMLDivElement>(null);
  const state = useRef<{
    nodes: Record<string, THREE.Mesh>;
    camera?: THREE.PerspectiveCamera;
    controls?: OrbitControls;
    ground?: THREE.MeshLambertMaterial;
    edge?: THREE.LineBasicMaterial;
    anim?: { t0: number; p0: THREE.Vector3; q0: THREE.Vector3; p1: THREE.Vector3; q1: THREE.Vector3 };
  }>({ nodes: {} });
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");
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
  const props = useRef({ layers, xray, showLabels });
  props.current = { layers, xray, showLabels };

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

    const tmp = new THREE.Vector3();
    let raf = 0;
    const loop = (now: number) => {
      raf = requestAnimationFrame(loop);
      const a = st.anim;
      if (a) {
        const k = Math.min(1, (now - a.t0) / 850);
        const e = k < 0.5 ? 2 * k * k : 1 - Math.pow(-2 * k + 2, 2) / 2;
        camera.position.lerpVectors(a.p0, a.p1, e);
        controls.target.lerpVectors(a.q0, a.q1, e);
        if (k >= 1) st.anim = undefined;
      }
      controls.update();
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
    raf = requestAnimationFrame(loop);

    return () => {
      disposed = true;
      cancelAnimationFrame(raf);
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
    const see = layers.foundations;
    if (st.ground) { st.ground.opacity = see ? 0.35 : 1; st.ground.depthWrite = !see; }
    const slab = st.nodes.floor_slab;
    if (slab) {
      const m = slab.material as THREE.MeshStandardMaterial;
      m.transparent = see; m.opacity = see ? 0.35 : 1; m.needsUpdate = true;
    }
  }, [layers, xray, status]);

  // Camera presets.
  useEffect(() => {
    const st = state.current;
    if (!st.camera || !st.controls) return;
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
      {status === "loading" && <div className="v-loading"><Loader2 className="spin" size={22} /> Loading model</div>}
      {status === "error" && <div className="v-loading">The 3D model couldn't be loaded. Rebuild the model and try again.</div>}
    </div>
  );
}
