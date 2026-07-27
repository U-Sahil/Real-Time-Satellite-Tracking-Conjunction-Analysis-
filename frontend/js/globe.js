/*
  globe.js (v2)
  -------------
  Renders a photorealistic Earth (real NASA-derived texture) with:
   - a "swarm" of thousands of satellites as a point cloud, like a real
     tracking site (this is what makes it feel alive instead of a toy)
   - individually highlighted markers for satellites you've selected/saved
   - smooth, continuous real-time motion via client-side interpolation,
     instead of the marker jumping every time new data arrives

  HOW THE MOTION IS SMOOTH:
  The backend's /positions/bulk endpoint returns, for every satellite,
  its position NOW and its predicted position ~6 seconds from now. Every
  animation frame (60x/second), we linearly interpolate between those two
  points based on how much of that 6-second window has elapsed. When
  fresh data arrives from the next poll, we simply swap in a new
  "from -> to" pair and keep interpolating. The satellite never jumps —
  it glides continuously, the same illusion real tracking dashboards use.
*/

const Globe = (() => {
  const EARTH_RADIUS = 4;
  const KM_PER_UNIT = 6371 / EARTH_RADIUS;

  let scene, camera, renderer, earthGroup;
  let swarmPoints, swarmGeometry;
  let swarmData = [];
  let highlightMeshes = {};
  let conjunctionLineGroup;
  let dragState = { active: false, lastX: 0, lastY: 0 };
  let rotationY = 0.6, rotationX = -0.15;
  let autoRotate = true;
  const INTERP_WINDOW_MS = 6000;

  function latLonAltToVector3(latDeg, lonDeg, altKm) {
    const radius = EARTH_RADIUS + (altKm || 0) / KM_PER_UNIT;
    const lat = (latDeg * Math.PI) / 180;
    const lon = (lonDeg * Math.PI) / 180;
    const x = radius * Math.cos(lat) * Math.cos(lon);
    const y = radius * Math.sin(lat);
    const z = radius * Math.cos(lat) * Math.sin(-lon);
    return new THREE.Vector3(x, y, z);
  }

  function shortestLon(from, to) {
    let diff = to - from;
    if (diff > 180) diff -= 360;
    if (diff < -180) diff += 360;
    return from + diff;
  }

  function lerpLatLonAlt(from, to, frac) {
    return {
      lat: from.lat + (to.lat - from.lat) * frac,
      lon: (() => {
        const target = shortestLon(from.lon, to.lon);
        return from.lon + (target - from.lon) * frac;
      })(),
      alt: from.alt + (to.alt - from.alt) * frac,
    };
  }

  function init(canvas) {
    const container = canvas.parentElement;
    scene = new THREE.Scene();

    camera = new THREE.PerspectiveCamera(45, container.clientWidth / container.clientHeight, 0.1, 1000);
    camera.position.set(0, 1.5, 11.5);

    renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.setSize(container.clientWidth, container.clientHeight);

    earthGroup = new THREE.Group();
    scene.add(earthGroup);

    const sun = new THREE.DirectionalLight(0xfff2df, 1.15);
    sun.position.set(6, 3, 5);
    scene.add(sun);
    scene.add(new THREE.AmbientLight(0x404550, 1.1));

    const loader = new THREE.TextureLoader();
    loader.crossOrigin = "anonymous";
    const earthMaterial = new THREE.MeshPhongMaterial({
      map: loader.load("https://threejs.org/examples/textures/planets/earth_atmos_2048.jpg"),
      specularMap: loader.load("https://threejs.org/examples/textures/planets/earth_specular_2048.jpg"),
      specular: new THREE.Color(0x333333),
      shininess: 6,
    });
    const earth = new THREE.Mesh(new THREE.SphereGeometry(EARTH_RADIUS, 64, 48), earthMaterial);
    earthGroup.add(earth);

    const cloudMaterial = new THREE.MeshPhongMaterial({
      map: loader.load("https://threejs.org/examples/textures/planets/earth_clouds_1024.png"),
      transparent: true,
      opacity: 0.28,
      depthWrite: false,
    });
    const clouds = new THREE.Mesh(new THREE.SphereGeometry(EARTH_RADIUS * 1.008, 64, 48), cloudMaterial);
    earthGroup.add(clouds);

    const gridGeom = new THREE.SphereGeometry(EARTH_RADIUS * 1.002, 24, 12);
    const gridMat = new THREE.MeshBasicMaterial({
      color: 0xffd9a0,
      wireframe: true,
      transparent: true,
      opacity: 0.08,
    });
    earthGroup.add(new THREE.Mesh(gridGeom, gridMat));

    const atmosphereMat = new THREE.MeshBasicMaterial({
      color: 0xffb35c,
      transparent: true,
      opacity: 0.06,
      side: THREE.BackSide,
    });
    earthGroup.add(new THREE.Mesh(new THREE.SphereGeometry(EARTH_RADIUS * 1.06, 48, 32), atmosphereMat));

    swarmGeometry = new THREE.BufferGeometry();
    const swarmMaterial = new THREE.PointsMaterial({
      color: 0xff4d4d,
      size: 0.045,
      sizeAttenuation: true,
      transparent: true,
      opacity: 0.85,
    });
    swarmPoints = new THREE.Points(swarmGeometry, swarmMaterial);
    earthGroup.add(swarmPoints);

    conjunctionLineGroup = new THREE.Group();
    earthGroup.add(conjunctionLineGroup);

    const starGeometry = new THREE.BufferGeometry();
    const starCount = 2000;
    const starPositions = new Float32Array(starCount * 3);
    for (let i = 0; i < starCount * 3; i++) starPositions[i] = (Math.random() - 0.5) * 400;
    starGeometry.setAttribute("position", new THREE.BufferAttribute(starPositions, 3));
    scene.add(new THREE.Points(starGeometry, new THREE.PointsMaterial({ color: 0x666666, size: 0.55 })));

    setupDragControls(container);
    window.addEventListener("resize", () => onResize(container));
    animate();
  }

  function setupDragControls(container) {
    container.addEventListener("mousedown", (e) => {
      dragState = { active: true, lastX: e.clientX, lastY: e.clientY };
      autoRotate = false;
    });
    window.addEventListener("mouseup", () => (dragState.active = false));
    window.addEventListener("mousemove", (e) => {
      if (!dragState.active) return;
      rotationY += (e.clientX - dragState.lastX) * 0.005;
      rotationX = Math.max(-1.3, Math.min(1.3, rotationX + (e.clientY - dragState.lastY) * 0.005));
      dragState.lastX = e.clientX;
      dragState.lastY = e.clientY;
    });
    container.addEventListener(
      "wheel",
      (e) => {
        e.preventDefault();
        camera.position.z = Math.max(5.5, Math.min(22, camera.position.z + e.deltaY * 0.01));
      },
      { passive: false }
    );
  }

  function onResize(container) {
    camera.aspect = container.clientWidth / container.clientHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(container.clientWidth, container.clientHeight);
  }

  function animate() {
    requestAnimationFrame(animate);
    if (autoRotate) rotationY += 0.0006;
    earthGroup.rotation.y = rotationY;
    earthGroup.rotation.x = rotationX;

    updateSwarmPositions();
    updateHighlightPositions();

    renderer.render(scene, camera);
  }

  function setSwarmData(entries) {
    const now = performance.now();
    swarmData = entries.map((e) => ({
      norad_id: e.norad_id,
      from: { lat: e.lat0, lon: e.lon0, alt: e.alt0 },
      to: { lat: e.lat1, lon: e.lon1, alt: e.alt1 },
      t0: now,
    }));
    const positions = new Float32Array(swarmData.length * 3);
    swarmGeometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
  }

  function updateSwarmPositions() {
    if (!swarmData.length) return;
    const positions = swarmGeometry.attributes.position;
    if (!positions) return;
    const now = performance.now();
    for (let i = 0; i < swarmData.length; i++) {
      const entry = swarmData[i];
      const frac = Math.min(1, (now - entry.t0) / INTERP_WINDOW_MS);
      const p = lerpLatLonAlt(entry.from, entry.to, frac);
      const v = latLonAltToVector3(p.lat, p.lon, p.alt);
      positions.setXYZ(i, v.x, v.y, v.z);
    }
    positions.needsUpdate = true;
  }

  function setHighlightData(entries, selectedNoradId) {
    const now = performance.now();
    const incomingIds = new Set(entries.map((e) => e.norad_id));

    Object.keys(highlightMeshes).forEach((idStr) => {
      const id = Number(idStr);
      if (!incomingIds.has(id)) {
        earthGroup.remove(highlightMeshes[id].mesh);
        highlightMeshes[id].mesh.geometry.dispose();
        highlightMeshes[id].mesh.material.dispose();
        delete highlightMeshes[id];
      }
    });

    entries.forEach((e) => {
      const isSelected = e.norad_id === selectedNoradId;
      const to = { lat: e.lat1, lon: e.lon1, alt: e.alt1 };
      const from = { lat: e.lat0, lon: e.lon0, alt: e.alt0 };

      if (!highlightMeshes[e.norad_id]) {
        const size = isSelected ? 0.11 : 0.06;
        const color = isSelected ? 0xffc86b : 0xffa63c;
        const mesh = new THREE.Mesh(
          new THREE.SphereGeometry(size, 12, 12),
          new THREE.MeshBasicMaterial({ color })
        );
        earthGroup.add(mesh);
        highlightMeshes[e.norad_id] = { mesh, from, to, t0: now, isSelected };
      } else {
        const entry = highlightMeshes[e.norad_id];
        entry.from = entry.to;
        entry.to = to;
        entry.t0 = now;
        entry.isSelected = isSelected;
        const size = isSelected ? 0.11 : 0.06;
        const color = isSelected ? 0xffc86b : 0xffa63c;
        entry.mesh.geometry.dispose();
        entry.mesh.geometry = new THREE.SphereGeometry(size, 12, 12);
        entry.mesh.material.color.setHex(color);
      }
    });
  }

  function updateHighlightPositions() {
    const now = performance.now();
    Object.values(highlightMeshes).forEach((entry) => {
      const frac = Math.min(1, (now - entry.t0) / INTERP_WINDOW_MS);
      const p = lerpLatLonAlt(entry.from, entry.to, frac);
      entry.mesh.position.copy(latLonAltToVector3(p.lat, p.lon, p.alt));
    });
  }

  function drawConjunctionLines(pairs) {
    while (conjunctionLineGroup.children.length) {
      const child = conjunctionLineGroup.children.pop();
      child.geometry.dispose();
      child.material.dispose();
    }
    pairs.forEach(({ posA, posB }) => {
      const a = latLonAltToVector3(posA.lat, posA.lon, posA.alt);
      const b = latLonAltToVector3(posB.lat, posB.lon, posB.alt);
      const geometry = new THREE.BufferGeometry().setFromPoints([a, b]);
      const material = new THREE.LineBasicMaterial({ color: 0xff5f5f, transparent: true, opacity: 0.9 });
      conjunctionLineGroup.add(new THREE.Line(geometry, material));
    });
  }

  function focusOn(latDeg, lonDeg) {
    autoRotate = false;
    rotationY = -((lonDeg * Math.PI) / 180) - Math.PI / 2;
    rotationX = -((latDeg * Math.PI) / 180) * 0.6;
  }

  return {
    init,
    setSwarmData,
    setHighlightData,
    drawConjunctionLines,
    focusOn,
    latLonAltToVector3,
  };
})();
