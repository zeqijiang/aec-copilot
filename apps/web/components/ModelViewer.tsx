"use client";

import { useEffect, useRef } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";

export type ElementRecord = Record<string, any> & { id: string; type: string };

const colors: Record<string, number> = {
  wall: 0x92a8b8,
  column: 0x31556d,
  slab: 0xc8d4dc,
  door: 0xe88355,
  window: 0x49b9cf,
  part: 0x65b891,
  assembly: 0x65b891,
};

function addBox(group: THREE.Group, size: [number, number, number], position: [number, number, number], color: number) {
  const mesh = new THREE.Mesh(
    new THREE.BoxGeometry(...size),
    new THREE.MeshStandardMaterial({ color, roughness: 0.72, metalness: 0.04 }),
  );
  mesh.position.set(...position);
  mesh.castShadow = true;
  mesh.receiveShadow = true;
  group.add(mesh);
  return mesh;
}

function makeModel(elements: ElementRecord[]) {
  const group = new THREE.Group();
  const byId = new Map(elements.map((element) => [element.id, element]));
  for (const element of elements) {
    const color = colors[element.type] ?? 0x8ca2af;
    if (element.type === "wall") {
      const a = element.start, b = element.end;
      const length = Math.hypot(b[0] - a[0], b[1] - a[1]);
      const mesh = addBox(group, [length, element.height, element.thickness], [(a[0] + b[0]) / 2, a[2] + element.height / 2, (a[1] + b[1]) / 2], color);
      mesh.rotation.y = -Math.atan2(b[1] - a[1], b[0] - a[0]);
    } else if (element.type === "column") {
      addBox(group, [element.width, element.height, element.depth], [element.center[0], element.center[2] + element.height / 2, element.center[1]], color);
    } else if (element.type === "slab") {
      const xs = element.boundary.map((p: number[]) => p[0]);
      const zs = element.boundary.map((p: number[]) => p[1]);
      const minX = Math.min(...xs), maxX = Math.max(...xs), minZ = Math.min(...zs), maxZ = Math.max(...zs);
      addBox(group, [maxX - minX, element.thickness, maxZ - minZ], [(minX + maxX) / 2, element.elevation + element.thickness / 2, (minZ + maxZ) / 2], color);
    } else if (element.type === "door" || element.type === "window") {
      const host = byId.get(element.host_id);
      if (host) {
        const dx = host.end[0] - host.start[0], dz = host.end[1] - host.start[1];
        const length = Math.hypot(dx, dz);
        const x = host.start[0] + dx / length * (element.offset + element.width / 2);
        const z = host.start[1] + dz / length * (element.offset + element.width / 2);
        const mesh = addBox(group, [element.width, element.height, host.thickness * 1.08], [x, host.start[2] + element.bottom + element.height / 2, z], color);
        mesh.rotation.y = -Math.atan2(dz, dx);
      }
    } else if (element.type === "part") {
      if (element.shape === "cylinder") {
        const [diameter, height] = element.size;
        const mesh = new THREE.Mesh(new THREE.CylinderGeometry(diameter / 2, diameter / 2, height, 48), new THREE.MeshStandardMaterial({ color }));
        mesh.position.set(element.origin[0], element.origin[2] + height / 2, element.origin[1]);
        group.add(mesh);
      } else {
        const [width, depth, height] = element.size;
        addBox(group, [width, height, depth], [element.origin[0] + width / 2, element.origin[2] + height / 2, element.origin[1] + depth / 2], color);
      }
    } else if (element.type === "polyline") {
      const points = element.points.map((p: number[]) => new THREE.Vector3(p[0], p[2] + 2, p[1]));
      if (element.closed) points.push(points[0].clone());
      group.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(points), new THREE.LineBasicMaterial({ color: 0x286b82 })));
    }
  }
  return group;
}

export default function ModelViewer({ elements }: { elements: ElementRecord[] }) {
  const mount = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!mount.current) return;
    const container = mount.current;
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0xeff4f6);
    scene.fog = new THREE.Fog(0xeff4f6, 30000, 110000);
    const camera = new THREE.PerspectiveCamera(42, container.clientWidth / Math.max(container.clientHeight, 1), 1, 500000);
    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(container.clientWidth, container.clientHeight);
    renderer.shadowMap.enabled = true;
    container.replaceChildren(renderer.domElement);
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    scene.add(new THREE.HemisphereLight(0xf4fbff, 0x62717a, 2.4));
    const sun = new THREE.DirectionalLight(0xffffff, 2.2);
    sun.position.set(10000, 18000, 8000);
    sun.castShadow = true;
    scene.add(sun);
    const model = makeModel(elements);
    scene.add(model);
    const bounds = new THREE.Box3().setFromObject(model);
    const size = bounds.isEmpty() ? new THREE.Vector3(1000, 1000, 1000) : bounds.getSize(new THREE.Vector3());
    const center = bounds.isEmpty() ? new THREE.Vector3() : bounds.getCenter(new THREE.Vector3());
    const radius = Math.max(size.length() / 2, 200);
    const grid = new THREE.GridHelper(radius * 5, 40, 0xb5c6ce, 0xd5e0e5);
    grid.position.set(center.x, bounds.isEmpty() ? -2 : bounds.min.y - 2, center.z);
    scene.add(grid);
    camera.position.set(center.x + radius * 1.65, center.y + radius * 1.25, center.z + radius * 1.65);
    camera.near = Math.max(radius / 1000, 0.1);
    camera.far = Math.max(radius * 100, 100000);
    camera.updateProjectionMatrix();
    controls.target.copy(center);
    controls.update();
    let frame = 0;
    const animate = () => { frame = requestAnimationFrame(animate); controls.update(); renderer.render(scene, camera); };
    animate();
    const observer = new ResizeObserver(() => {
      if (!container.clientWidth || !container.clientHeight) return;
      camera.aspect = container.clientWidth / container.clientHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(container.clientWidth, container.clientHeight);
    });
    observer.observe(container);
    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
      controls.dispose();
      scene.traverse((object) => {
        if (object instanceof THREE.Mesh || object instanceof THREE.Line) {
          object.geometry.dispose();
          const materials = Array.isArray(object.material) ? object.material : [object.material];
          materials.forEach((material) => material.dispose());
        }
      });
      renderer.dispose();
      container.replaceChildren();
    };
  }, [elements]);

  return <div className="model-viewer" ref={mount} aria-label="可旋转的三维模型预览" />;
}
