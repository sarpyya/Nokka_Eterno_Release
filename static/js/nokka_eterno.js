/**
 * ═══════════════════════════════════════════════════════════════
 * 🌌 NOKKA ETERNO v2.1 — Three.js 3D Renderer (Enhanced)
 * ═══════════════════════════════════════════════════════════════
 *
 * Enhanced renderer with:
 *   - UnrealBloomPass post-processing (glow)
 *   - Animated starfield background
 *   - Camera shake on damage
 *   - Pulsing wireframe cube
 *   - Damage particle explosions
 *   - Compute metrics panel
 *
 * Dependencies (CDN):
 *   - three.js r128
 *   - OrbitControls
 *   - EffectComposer, RenderPass, UnrealBloomPass
 *   - socket.io client
 */

// ═══════════════════════════════════════════════════════════════
// 🔧 MODULE: Toast & Flash Effects
// ═══════════════════════════════════════════════════════════════

const NokkaFX = (() => {
    const flashEl = document.getElementById('event-flash');
    const toastContainer = document.getElementById('toast-container');

    function flash(type) {
        if (!flashEl) return;
        flashEl.className = 'event-flash flash-' + type + ' active';
        setTimeout(() => { flashEl.classList.remove('active'); }, 300);
    }

    function toast(message, type = 'info') {
        if (!toastContainer) return;
        const el = document.createElement('div');
        el.className = 'toast toast-' + type;
        el.textContent = message;
        toastContainer.appendChild(el);
        setTimeout(() => { el.remove(); }, 2200);
    }

    return { flash, toast };
})();


// ═══════════════════════════════════════════════════════════════
// ✨ MODULE: Particle System (damage explosions)
// ═══════════════════════════════════════════════════════════════

const NokkaParticles = (() => {
    let scene = null;
    const POOL_SIZE = 300;
    let particles = null;
    let velocities = [];
    let lifetimes = [];
    let posBuffer, colBuffer, sizeBuffer;
    let activeParticles = 0;

    function init(threeScene) {
        scene = threeScene;
        const geom = new THREE.BufferGeometry();
        posBuffer = new Float32Array(POOL_SIZE * 3);
        colBuffer = new Float32Array(POOL_SIZE * 3);
        sizeBuffer = new Float32Array(POOL_SIZE);

        geom.setAttribute('position', new THREE.BufferAttribute(posBuffer, 3));
        geom.setAttribute('customColor', new THREE.BufferAttribute(colBuffer, 3));
        geom.setAttribute('size', new THREE.BufferAttribute(sizeBuffer, 1));

        const mat = new THREE.ShaderMaterial({
            vertexShader: `
                attribute vec3 customColor;
                attribute float size;
                varying vec3 vColor;
                void main() {
                    vColor = customColor;
                    vec4 mvPos = modelViewMatrix * vec4(position, 1.0);
                    gl_PointSize = size * (200.0 / -mvPos.z);
                    gl_PointSize = clamp(gl_PointSize, 1.0, 20.0);
                    gl_Position = projectionMatrix * mvPos;
                }
            `,
            fragmentShader: `
                varying vec3 vColor;
                void main() {
                    vec2 c = 2.0 * gl_PointCoord - 1.0;
                    float r = dot(c, c);
                    if (r > 1.0) discard;
                    float glow = exp(-2.5 * r);
                    gl_FragColor = vec4(vColor * glow, (1.0 - r) * 0.9);
                }
            `,
            transparent: true,
            depthWrite: false,
            blending: THREE.AdditiveBlending,
        });

        particles = new THREE.Points(geom, mat);
        scene.add(particles);

        // Initialize arrays
        for (let i = 0; i < POOL_SIZE; i++) {
            velocities.push(new THREE.Vector3());
            lifetimes.push(0);
        }
    }

    function emit(x, y, z, count, color) {
        const r = color ? color[0] : 1.0;
        const g = color ? color[1] : 0.2;
        const b = color ? color[2] : 0.15;

        for (let i = 0; i < count; i++) {
            const idx = (activeParticles + i) % POOL_SIZE;
            posBuffer[idx * 3] = x;
            posBuffer[idx * 3 + 1] = y;
            posBuffer[idx * 3 + 2] = z;
            colBuffer[idx * 3] = r;
            colBuffer[idx * 3 + 1] = g;
            colBuffer[idx * 3 + 2] = b;
            sizeBuffer[idx] = 2.0 + Math.random() * 3.0;

            velocities[idx].set(
                (Math.random() - 0.5) * 0.4,
                (Math.random() - 0.5) * 0.4,
                (Math.random() - 0.5) * 0.4
            );
            lifetimes[idx] = 1.0;
        }
        activeParticles = (activeParticles + count) % POOL_SIZE;
    }

    function emitDamageBurst(gridSize) {
        // Emit particles at random locations within the cube
        for (let i = 0; i < 5; i++) {
            const x = Math.random() * (gridSize - 1);
            const y = Math.random() * (gridSize - 1);
            const z = Math.random() * (gridSize - 1);
            emit(x, y, z, 8, [1.0, 0.2, 0.13]);
        }
    }

    function emitHealBurst(gridSize) {
        const c = (gridSize - 1) / 2;
        emit(c, c, c, 30, [0.22, 1.0, 0.08]);
    }

    function emitRebootBurst(gridSize) {
        const c = (gridSize - 1) / 2;
        emit(c, c, c, 40, [1.0, 0.75, 0.0]);
    }

    function update(dt) {
        if (!particles) return;
        let anyActive = false;

        for (let i = 0; i < POOL_SIZE; i++) {
            if (lifetimes[i] > 0) {
                lifetimes[i] -= dt * 1.5;
                posBuffer[i * 3] += velocities[i].x;
                posBuffer[i * 3 + 1] += velocities[i].y;
                posBuffer[i * 3 + 2] += velocities[i].z;
                velocities[i].multiplyScalar(0.96); // drag
                sizeBuffer[i] = Math.max(0, sizeBuffer[i] * 0.97);
                anyActive = true;
            } else {
                sizeBuffer[i] = 0;
            }
        }

        if (anyActive) {
            particles.geometry.attributes.position.needsUpdate = true;
            particles.geometry.attributes.size.needsUpdate = true;
        }
    }

    return { init, emitDamageBurst, emitHealBurst, emitRebootBurst, update };
})();


// ═══════════════════════════════════════════════════════════════
// 🌟 MODULE: Starfield Background
// ═══════════════════════════════════════════════════════════════

const NokkaStarfield = (() => {
    let stars = null;
    const STAR_COUNT = 1500;

    function init(scene) {
        const geom = new THREE.BufferGeometry();
        const pos = new Float32Array(STAR_COUNT * 3);
        const sizes = new Float32Array(STAR_COUNT);

        for (let i = 0; i < STAR_COUNT; i++) {
            // Distribute in sphere around the scene
            pos[i * 3] = (Math.random() - 0.5) * 200;
            pos[i * 3 + 1] = (Math.random() - 0.5) * 200;
            pos[i * 3 + 2] = (Math.random() - 0.5) * 200;
            sizes[i] = Math.random() * 1.2 + 0.3;
        }

        geom.setAttribute('position', new THREE.BufferAttribute(pos, 3));
        geom.setAttribute('size', new THREE.BufferAttribute(sizes, 1));

        const mat = new THREE.ShaderMaterial({
            uniforms: { uTime: { value: 0 } },
            vertexShader: `
                attribute float size;
                varying float vAlpha;
                uniform float uTime;
                void main() {
                    vAlpha = 0.3 + 0.7 * abs(sin(uTime * 0.5 + position.x * 0.1));
                    vec4 mvPos = modelViewMatrix * vec4(position, 1.0);
                    gl_PointSize = size * (200.0 / -mvPos.z);
                    gl_PointSize = clamp(gl_PointSize, 0.5, 4.0);
                    gl_Position = projectionMatrix * mvPos;
                }
            `,
            fragmentShader: `
                varying float vAlpha;
                void main() {
                    vec2 c = 2.0 * gl_PointCoord - 1.0;
                    float r = dot(c, c);
                    if (r > 1.0) discard;
                    gl_FragColor = vec4(0.8, 0.85, 1.0, vAlpha * (1.0 - r));
                }
            `,
            transparent: true,
            depthWrite: false,
            blending: THREE.AdditiveBlending,
        });

        stars = new THREE.Points(geom, mat);
        scene.add(stars);
    }

    function update(time) {
        if (stars && stars.material.uniforms) {
            stars.material.uniforms.uTime.value = time;
            stars.rotation.y = time * 0.003;
            stars.rotation.x = time * 0.001;
        }
    }

    return { init, update };
})();


// ═══════════════════════════════════════════════════════════════
// 📸 MODULE: Camera Shake
// ═══════════════════════════════════════════════════════════════

const NokkaShake = (() => {
    let intensity = 0;
    let basePosition = new THREE.Vector3();
    let camera = null;

    function init(cam) {
        camera = cam;
        basePosition.copy(cam.position);
        console.log('📸 [NokkaShake] Inicializado — base:', cam.position);
    }

    function trigger(power = 0.5) {
        intensity = power;
        console.log(`📸 [NokkaShake] Shake disparado — power=${power.toFixed(2)}`);
    }

    function update(dt) {
        if (!camera) return;

        if (intensity > 0) {
            // Aplica desplazamiento aleatorio
            camera.position.x = basePosition.x + (Math.random() - 0.5) * intensity * 0.8;
            camera.position.y = basePosition.y + (Math.random() - 0.5) * intensity * 0.6;
            camera.position.z = basePosition.z + (Math.random() - 0.5) * intensity * 0.8;

            intensity *= 0.88; // decay
            if (intensity < 0.01) {
                intensity = 0;
                // Restaurar posición base exacta al terminar
                camera.position.copy(basePosition);
                console.log('📸 [NokkaShake] Shake completado — cámara restaurada al baseline.');
            }
        }
    }

    // Permite actualizar la posición base cuando OrbitControls mueve la cámara
    function updateBase() {
        if (camera && intensity <= 0) basePosition.copy(camera.position);
    }

    return { init, trigger, update, updateBase };
})();


// ═══════════════════════════════════════════════════════════════
// 🎥 MODULE: Three.js Scene Manager (Enhanced)
// ═══════════════════════════════════════════════════════════════

const NokkaScene = (() => {
    let scene, camera, renderer, controls;
    let composer = null;           // EffectComposer for bloom
    let sensorPoints = null;
    let quiverLines = null;
    let gridHelper = null;
    let gridSize = 12;

    const MAX_SENSORS = 100 * 100 * 100; // Supports up to N=100
    let positionBuffer, colorBuffer, sizeBuffer;
    let activeCount = 0;

    const MAX_QUIVER = 50 * 50 * 50; // Supports up to N=100 with step=2
    let quiverPosBuffer;

    function init(canvasId) {
        const canvas = document.getElementById(canvasId);

        // ── Renderer ──
        renderer = new THREE.WebGLRenderer({
            canvas: canvas,
            antialias: true,
            alpha: false,
        });
        renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
        renderer.setSize(window.innerWidth, window.innerHeight);
        renderer.setClearColor(0x050510, 1);
        renderer.toneMapping = THREE.ACESFilmicToneMapping;
        renderer.toneMappingExposure = 1.2;

        // ── Scene ──
        scene = new THREE.Scene();
        scene.fog = new THREE.FogExp2(0x050510, 0.005);

        // ── Camera ──
        camera = new THREE.PerspectiveCamera(55, window.innerWidth / window.innerHeight, 0.1, 500);
        camera.position.set(20, 18, 22);

        // ── Controls ──
        controls = new THREE.OrbitControls(camera, renderer.domElement);
        controls.enableDamping = true;
        controls.dampingFactor = 0.08;
        controls.minDistance = 5;
        controls.maxDistance = 80;
        controls.target.set(5.5, 5.5, 5.5);
        controls.autoRotate = true;
        controls.autoRotateSpeed = 0.4;
        controls.update();

        // ── Lights ──
        scene.add(new THREE.AmbientLight(0x303050, 0.6));

        const mainLight = new THREE.PointLight(0x00ffd5, 1.5, 100);
        mainLight.position.set(18, 28, 18);
        scene.add(mainLight);

        const accent1 = new THREE.PointLight(0xff00ff, 0.6, 80);
        accent1.position.set(-8, -5, 20);
        scene.add(accent1);

        const accent2 = new THREE.PointLight(0xffbb00, 0.3, 60);
        accent2.position.set(15, -10, -5);
        scene.add(accent2);

        // ── Starfield ──
        NokkaStarfield.init(scene);

        // ── Sensor Points ──
        const geom = new THREE.BufferGeometry();
        positionBuffer = new Float32Array(MAX_SENSORS * 3);
        colorBuffer = new Float32Array(MAX_SENSORS * 3);
        sizeBuffer = new Float32Array(MAX_SENSORS);

        geom.setAttribute('position', new THREE.BufferAttribute(positionBuffer, 3));
        geom.setAttribute('customColor', new THREE.BufferAttribute(colorBuffer, 3));
        geom.setAttribute('size', new THREE.BufferAttribute(sizeBuffer, 1));

        const sensorMat = new THREE.ShaderMaterial({
            uniforms: { uTime: { value: 0 } },
            vertexShader: `
                attribute vec3 customColor;
                attribute float size;
                varying vec3 vColor;
                varying float vAlpha;
                uniform float uTime;
                void main() {
                    vColor = customColor;
                    // Subtle breathing effect
                    float breath = 1.0 + 0.08 * sin(uTime * 2.0 + position.x * 0.5 + position.y * 0.3);
                    vAlpha = 0.95;
                    vec4 mvPosition = modelViewMatrix * vec4(position, 1.0);
                    gl_PointSize = size * breath * (250.0 / -mvPosition.z);
                    gl_PointSize = clamp(gl_PointSize, 2.0, 30.0);
                    gl_Position = projectionMatrix * mvPosition;
                }
            `,
            fragmentShader: `
                varying vec3 vColor;
                varying float vAlpha;
                void main() {
                    vec2 cxy = 2.0 * gl_PointCoord - 1.0;
                    float r = dot(cxy, cxy);
                    if (r > 1.0) discard;
                    float glow = exp(-2.5 * r);
                    float core = exp(-8.0 * r); // bright core
                    vec3 col = vColor * glow + vec3(1.0) * core * 0.3;
                    gl_FragColor = vec4(col, vAlpha * (1.0 - r * 0.4));
                }
            `,
            transparent: true,
            depthWrite: false,
            blending: THREE.AdditiveBlending,
        });

        sensorPoints = new THREE.Points(geom, sensorMat);
        scene.add(sensorPoints);

        // ── Quiver Lines ──
        const quiverGeom = new THREE.BufferGeometry();
        quiverPosBuffer = new Float32Array(MAX_QUIVER * 6);
        quiverGeom.setAttribute('position', new THREE.BufferAttribute(quiverPosBuffer, 3));

        const quiverMat = new THREE.LineBasicMaterial({
            color: 0x00ffd5,
            transparent: true,
            opacity: 0.3,
            blending: THREE.AdditiveBlending,
        });

        quiverLines = new THREE.LineSegments(quiverGeom, quiverMat);
        scene.add(quiverLines);

        // ── Grid Wireframe ──
        gridHelper = createCubeWireframe(gridSize);
        scene.add(gridHelper);

        // ── Particles ──
        NokkaParticles.init(scene);

        // ── Camera Shake ──
        NokkaShake.init(camera);

        // ── Post-Processing (Bloom) ──
        try {
            composer = new THREE.EffectComposer(renderer);
            const renderPass = new THREE.RenderPass(scene, camera);
            composer.addPass(renderPass);

            const bloomPass = new THREE.UnrealBloomPass(
                new THREE.Vector2(window.innerWidth, window.innerHeight),
                0.8,   // strength
                0.4,   // radius
                0.3    // threshold
            );
            composer.addPass(bloomPass);
        } catch (e) {
            console.warn('Bloom not available, falling back to standard rendering:', e);
            composer = null;
        }

        // ── Resize ──
        window.addEventListener('resize', onResize);

        // ── Start render loop ──
        animate();
    }

    function createCubeWireframe(n) {
        const s = n - 1;
        const boxGeom = new THREE.BoxGeometry(s, s, s);
        const edges = new THREE.EdgesGeometry(boxGeom);
        const mat = new THREE.LineBasicMaterial({
            color: 0x00ffd5,
            transparent: true,
            opacity: 0.15,
        });
        const wireframe = new THREE.LineSegments(edges, mat);
        wireframe.position.set(s / 2, s / 2, s / 2);
        return wireframe;
    }

    function onResize() {
        camera.aspect = window.innerWidth / window.innerHeight;
        camera.updateProjectionMatrix();
        renderer.setSize(window.innerWidth, window.innerHeight);
        if (composer) composer.setSize(window.innerWidth, window.innerHeight);
    }

    let _time = 0;
    let _lastFrame = performance.now();

    function animate() {
        requestAnimationFrame(animate);
        const now = performance.now();
        const dt = (now - _lastFrame) / 1000;
        _lastFrame = now;
        _time += dt;

        controls.update();
        // Sincronizar basePosition del shake con la posición actual de la cámara (tras drag)
        NokkaShake.updateBase();

        // Update modules
        if (sensorPoints && sensorPoints.material.uniforms) {
            sensorPoints.material.uniforms.uTime.value = _time;
        }
        NokkaStarfield.update(_time);
        NokkaParticles.update(dt);
        NokkaShake.update(dt);

        // Pulsing wireframe
        if (gridHelper) {
            const pulse = 0.12 + 0.06 * Math.sin(_time * 1.5);
            gridHelper.material.opacity = pulse;
        }

        // Render with bloom or fallback
        if (composer) {
            composer.render();
        } else {
            renderer.render(scene, camera);
        }
    }

    function updateSensors(positions, colors) {
        activeCount = positions.length;

        for (let i = 0; i < activeCount; i++) {
            const p = positions[i];
            const c = colors[i];
            positionBuffer[i * 3] = p[0];
            positionBuffer[i * 3 + 1] = p[1];
            positionBuffer[i * 3 + 2] = p[2];
            colorBuffer[i * 3] = c[0];
            colorBuffer[i * 3 + 1] = c[1];
            colorBuffer[i * 3 + 2] = c[2];
            sizeBuffer[i] = 3.0;
        }

        for (let i = activeCount; i < MAX_SENSORS; i++) {
            sizeBuffer[i] = 0;
        }

        const geom = sensorPoints.geometry;
        geom.attributes.position.needsUpdate = true;
        geom.attributes.customColor.needsUpdate = true;
        geom.attributes.size.needsUpdate = true;
        geom.setDrawRange(0, activeCount);
    }

    function updateQuiver(positions, directions) {
        const count = positions.length;
        const arrowScale = 0.6;

        for (let i = 0; i < count; i++) {
            const p = positions[i];
            const d = directions[i];
            quiverPosBuffer[i * 6] = p[0];
            quiverPosBuffer[i * 6 + 1] = p[1];
            quiverPosBuffer[i * 6 + 2] = p[2];
            quiverPosBuffer[i * 6 + 3] = p[0] + d[0] * arrowScale;
            quiverPosBuffer[i * 6 + 4] = p[1] + d[1] * arrowScale;
            quiverPosBuffer[i * 6 + 5] = p[2] + d[2] * arrowScale;
        }

        const geom = quiverLines.geometry;
        geom.attributes.position.needsUpdate = true;
        geom.setDrawRange(0, count * 2);
    }

    function setGridSize(n) {
        if (n !== gridSize) {
            gridSize = n;
            scene.remove(gridHelper);
            gridHelper = createCubeWireframe(n);
            scene.add(gridHelper);
            controls.target.set((n - 1) / 2, (n - 1) / 2, (n - 1) / 2);
        }
    }

    function getGridSize() { return gridSize; }

    return { init, updateSensors, updateQuiver, setGridSize, getGridSize };
})();


// ═══════════════════════════════════════════════════════════════
// � MODULE: Hardware Detection
// ═══════════════════════════════════════════════════════════════

const NokkaHardware = (() => {
    function getInfo() {
        const mem = navigator.deviceMemory || '??';
        let webgl = false;
        try {
            const canvas = document.createElement('canvas');
            webgl = !!(window.WebGLRenderingContext && (canvas.getContext('webgl') || canvas.getContext('experimental-webgl')));
        } catch (e) { webgl = false; }

        const isLowEnd = (typeof mem === 'number' && mem <= 4) || !webgl;

        return { mem, webgl, isLowEnd };
    }

    function updateHUD() {
        const el = document.getElementById('hw-detect');
        if (!el) return;
        const info = getInfo();
        el.textContent = `${info.mem}GB RAM | ${info.webgl ? 'GPU OK' : 'NO GPU'}`;
        if (info.isLowEnd) el.style.color = 'var(--amber)';
    }

    return { getInfo, updateHUD };
})();


// ═══════════════════════════════════════════════════════════════
// 🟦 MODULE: 2D Canvas Renderer (Low Performance Fallback)
// ═══════════════════════════════════════════════════════════════

const Nokka2DRenderer = (() => {
    let canvas, ctx;
    let sensors = { positions: [], colors: [] };
    let quiver = { positions: [], directions: [] };
    let gridSize = 12;

    function init(canvasId) {
        canvas = document.getElementById(canvasId);
        ctx = canvas.getContext('2d', { alpha: false });
        window.addEventListener('resize', onResize);
        onResize();
        animate();
    }

    function onResize() {
        if (!canvas) return;
        canvas.width = window.innerWidth;
        canvas.height = window.innerHeight;
    }

    function animate() {
        if (!canvas || canvas.style.display === 'none') {
            requestAnimationFrame(animate);
            return;
        }

        ctx.fillStyle = '#050510';
        ctx.fillRect(0, 0, canvas.width, canvas.height);

        const centerX = canvas.width / 2;
        const centerY = canvas.height / 2;
        const spacing = Math.min(canvas.width, canvas.height) / (gridSize * 1.5);
        const offset = (gridSize - 1) * spacing / 2;

        // Draw basic grid background
        ctx.strokeStyle = 'rgba(0, 255, 213, 0.05)';
        ctx.lineWidth = 1;
        for (let i = 0; i < gridSize; i++) {
            const x = centerX - offset + i * spacing;
            ctx.beginPath(); ctx.moveTo(x, centerY - offset); ctx.lineTo(x, centerY + offset); ctx.stroke();
            const y = centerY - offset + i * spacing;
            ctx.beginPath(); ctx.moveTo(centerX - offset, y); ctx.lineTo(centerX + offset, y); ctx.stroke();
        }

        // Draw Sensors (Projected simply as 2D slice/stack)
        sensors.positions.forEach((p, i) => {
            const c = sensors.colors[i];
            const x = centerX - offset + p[0] * spacing;
            const y = centerY - offset + p[1] * spacing;
            const z = p[2];

            // Use Z for size and alpha to simulate depth in 2D
            const size = 2 + (z / gridSize) * 4;
            const alpha = 0.3 + (z / gridSize) * 0.7;

            ctx.fillStyle = `rgba(${c[0] * 255}, ${c[1] * 255}, ${c[2] * 255}, ${alpha})`;
            ctx.beginPath();
            ctx.arc(x, y, size, 0, Math.PI * 2);
            ctx.fill();

            if (z > gridSize * 0.8) {
                ctx.shadowBlur = 10;
                ctx.shadowColor = `rgb(${c[0] * 255}, ${c[1] * 255}, ${c[2] * 255})`;
                ctx.fill();
                ctx.shadowBlur = 0;
            }
        });

        // Draw Quiver (Arrows)
        ctx.strokeStyle = 'rgba(0, 255, 213, 0.3)';
        quiver.positions.forEach((p, i) => {
            const d = quiver.directions[i];
            const x1 = centerX - offset + p[0] * spacing;
            const y1 = centerY - offset + p[1] * spacing;
            const x2 = x1 + d[0] * spacing * 0.5;
            const y2 = y1 + d[1] * spacing * 0.5;

            ctx.beginPath();
            ctx.moveTo(x1, y1);
            ctx.lineTo(x2, y2);
            ctx.stroke();
        });

        requestAnimationFrame(animate);
    }

    function updateSensors(pos, col) { sensors = { positions: pos, colors: col }; }
    function updateQuiver(pos, dir) { quiver = { positions: pos, directions: dir }; }
    function setGridSize(n) { gridSize = n; }

    return { init, updateSensors, updateQuiver, setGridSize };
})();


// ═══════════════════════════════════════════════════════════════
// �📊 MODULE: Stats HUD
// ═══════════════════════════════════════════════════════════════

const NokkaStats = (() => {
    const els = {
        frame: document.getElementById('stat-frame'),
        active: document.getElementById('stat-active'),
        damaged: document.getElementById('stat-damaged'),
        healed: document.getElementById('stat-healed'),
        dmgEvents: document.getElementById('stat-dmg-events'),
        fieldMean: document.getElementById('stat-field-mean'),
        fieldStd: document.getElementById('stat-field-std'),
        healthBar: document.getElementById('health-bar-fill'),
        frameCounter: document.getElementById('frame-counter'),
    };

    function update(stats, frame) {
        if (!stats) return;
        if (els.frame) els.frame.textContent = frame;
        if (els.active) els.active.textContent = stats.activeSensors;
        if (els.damaged) els.damaged.textContent = stats.damagedSensors;
        if (els.healed) els.healed.textContent = stats.totalHealEvents;
        if (els.dmgEvents) els.dmgEvents.textContent = stats.totalDamageEvents;
        if (els.fieldMean) els.fieldMean.textContent = stats.fieldMean.toFixed(3);
        if (els.fieldStd) els.fieldStd.textContent = stats.fieldStd.toFixed(3);

        if (els.healthBar && stats.totalSensors > 0) {
            const pct = (stats.activeSensors / stats.totalSensors) * 100;
            els.healthBar.style.width = pct + '%';
        }
        if (els.frameCounter) els.frameCounter.textContent = 'F' + String(frame).padStart(4, '0');
    }

    return { update };
})();


// ═══════════════════════════════════════════════════════════════
// 🧮 MODULE: Compute Metrics
// ═══════════════════════════════════════════════════════════════

const NokkaCompute = (() => {
    const els = {
        stepMs: document.getElementById('cmp-step-ms'),
        serializeMs: document.getElementById('cmp-serialize-ms'),
        totalMs: document.getElementById('cmp-total-ms'),
        estFlops: document.getElementById('cmp-flops'),
        opsPerFrame: document.getElementById('cmp-ops-frame'),
        cumulativeOps: document.getElementById('cmp-cumulative'),
        fieldEvals: document.getElementById('cmp-field-evals'),
        neighborLookups: document.getElementById('cmp-neighbor'),
        colormapCalcs: document.getElementById('cmp-colormap'),
        quiverCalcs: document.getElementById('cmp-quiver'),
        bandwidth: document.getElementById('cmp-bandwidth'),
        fpsGauge: document.getElementById('cmp-fps'),
        throughput: document.getElementById('cmp-throughput'),
    };

    let _lastFrameTime = performance.now();
    let _frameCount = 0;
    let _fps = 0;
    let _bytesAccum = 0;
    let _bwTimer = performance.now();
    let _bandwidth = 0;

    function formatNumber(n) {
        if (n >= 1e9) return (n / 1e9).toFixed(1) + 'G';
        if (n >= 1e6) return (n / 1e6).toFixed(1) + 'M';
        if (n >= 1e3) return (n / 1e3).toFixed(1) + 'K';
        return String(n);
    }

    function update(compute, rawPayloadSize) {
        if (!compute) return;

        // FPS calculation
        _frameCount++;
        const now = performance.now();
        if (now - _lastFrameTime > 1000) {
            _fps = _frameCount;
            _frameCount = 0;
            _lastFrameTime = now;
        }

        // Bandwidth (bytes/sec)
        _bytesAccum += rawPayloadSize || 0;
        if (now - _bwTimer > 1000) {
            _bandwidth = _bytesAccum;
            _bytesAccum = 0;
            _bwTimer = now;
        }

        if (els.stepMs) els.stepMs.textContent = compute.stepMs.toFixed(1);
        if (els.serializeMs) els.serializeMs.textContent = compute.serializeMs.toFixed(1);
        if (els.totalMs) els.totalMs.textContent = compute.totalMs.toFixed(1);
        if (els.estFlops) els.estFlops.textContent = formatNumber(compute.estFLOPS);
        if (els.opsPerFrame) els.opsPerFrame.textContent = formatNumber(compute.opsPerFrame);
        if (els.cumulativeOps) els.cumulativeOps.textContent = formatNumber(compute.cumulativeOps);
        if (els.fieldEvals) els.fieldEvals.textContent = formatNumber(compute.fieldEvals);
        if (els.neighborLookups) els.neighborLookups.textContent = formatNumber(compute.neighborLookups);
        if (els.colormapCalcs) els.colormapCalcs.textContent = formatNumber(compute.colormapCalcs);
        if (els.quiverCalcs) els.quiverCalcs.textContent = formatNumber(compute.quiverCalcs);
        if (els.bandwidth) els.bandwidth.textContent = formatNumber(_bandwidth);
        if (els.fpsGauge) els.fpsGauge.textContent = _fps;
        if (els.throughput) els.throughput.textContent = formatNumber(_fps * (compute.opsPerFrame || 0));
    }

    return { update };
})();


// ═══════════════════════════════════════════════════════════════
// 🎮 MODULE: Render Manager (Switch 2D/3D)
// ═══════════════════════════════════════════════════════════════

const NokkaManager = (() => {
    let currentMode = '3d'; // Default
    let canvases = {
        '3d': document.getElementById('nokka-canvas'),
        '2d': document.getElementById('nokka-canvas-2d')
    };

    function init() {
        canvases['3d'] = document.getElementById('nokka-canvas');
        canvases['2d'] = document.getElementById('nokka-canvas-2d');

        const btn3d = document.getElementById('mode-3d');
        const btn2d = document.getElementById('mode-2d');

        if (btn3d) btn3d.addEventListener('click', () => setMode('3d'));
        if (btn2d) btn2d.addEventListener('click', () => setMode('2d'));

        // Auto-detect hardware
        const info = NokkaHardware.getInfo();
        NokkaHardware.updateHUD();

        if (info.isLowEnd) {
            console.log('🚀 Low-end hardware detected, defaulting to 2D');
            setMode('2d');
        } else {
            setMode('3d');
        }
    }

    function setMode(mode) {
        currentMode = mode;
        console.log('🔄 Switched to mode:', mode);

        // UI Update
        const btn3d = document.getElementById('mode-3d');
        const btn2d = document.getElementById('mode-2d');
        if (btn3d) btn3d.classList.toggle('active', mode === '3d');
        if (btn2d) btn2d.classList.toggle('active', mode === '2d');

        // Canvas Visibility
        if (canvases['3d']) canvases['3d'].style.display = (mode === '3d') ? 'block' : 'none';
        if (canvases['2d']) canvases['2d'].style.display = (mode === '2d') ? 'block' : 'none';

        NokkaFX.toast(`Modo ${mode.toUpperCase()} activado`, 'info');
    }

    function updateData(data) {
        // Shared updates
        NokkaStats.update(data.stats, data.frame);

        // Dispatch to active renderer
        if (currentMode === '3d') {
            NokkaScene.setGridSize(data.gridSize);
            NokkaScene.updateSensors(data.sensors.positions, data.sensors.colors);
            NokkaScene.updateQuiver(data.quiver.positions, data.quiver.directions);
        } else {
            Nokka2DRenderer.setGridSize(data.gridSize);
            Nokka2DRenderer.updateSensors(data.sensors.positions, data.sensors.colors);
            Nokka2DRenderer.updateQuiver(data.quiver.positions, data.quiver.directions);
        }
    }

    return { init, setMode, updateData, getMode: () => currentMode };
})();


// ═══════════════════════════════════════════════════════════════
// 📡 MODULE: SocketIO Client
// ═══════════════════════════════════════════════════════════════

const NokkaSocket = (() => {
    let socket = null;
    let running = false;

    function connect() {
        socket = io({ transports: ['polling', 'websocket'] });

        socket.on('connect', () => {
            console.log('🌌 NOKKA connected:', socket.id);
            NokkaFX.toast('Conexión establecida', 'info');
        });

        socket.on('disconnect', () => {
            console.log('🌌 NOKKA disconnected');
            running = false;
            updateUI();
        });

        socket.on('nokka_frame', (data) => {
            NokkaManager.updateData(data);
            updateStatus(data.status);

            // Compute metrics
            const payloadSize = JSON.stringify(data).length;
            NokkaCompute.update(data.compute, payloadSize);

            // Consumo & Resource metrics
            if (data.consumo) {
                const con = data.consumo;
                const els = {
                    energy: document.getElementById('con-energy'),
                    load: document.getElementById('con-load'),
                    stress: document.getElementById('con-stress'),
                    sync: document.getElementById('con-sync'),
                    cpu: document.getElementById('con-cpu'),
                    ram: document.getElementById('con-ram'),
                    gpu: document.getElementById('con-gpu'),
                    bar: document.getElementById('energy-bar')
                };

                if (els.energy) els.energy.innerText = con.energy_nw.toFixed(4);
                if (els.load) els.load.innerText = con.load_pct + '%';
                if (els.stress) els.stress.innerText = con.field_stress;
                if (els.cpu) els.cpu.innerText = con.cpu_usage.toFixed(1) + '%';
                if (els.ram) els.ram.innerText = con.ram_usage.toFixed(1) + '%';
                if (els.gpu) els.gpu.innerText = con.gpu_load.toFixed(1) + '%';
                if (els.sync) {
                    els.sync.innerText = con.sync_level;
                    els.sync.className = 'stat-value ' + (con.sync_level === 'OPTIMAL' ? 'heal' : 'damage');
                }
                if (els.bar) els.bar.style.width = con.load_pct + '%';
            }
        });

        // ── Slider Event Listeners ──────────────────────────
        const sldGrid = document.getElementById('sld-grid');
        const sldSpeed = document.getElementById('sld-speed');
        const sldNoise = document.getElementById('sld-noise');

        const valGrid = document.getElementById('val-grid');
        const valSpeed = document.getElementById('val-speed');
        const valNoise = document.getElementById('val-noise');

        const emitConfig = () => {
            socket.emit('nokka_update_config', {
                grid_size: parseInt(sldGrid.value),
                wave_speed: parseFloat(sldSpeed.value),
                noise_level: parseFloat(sldNoise.value)
            });
        };

        if (sldGrid) sldGrid.addEventListener('input', () => {
            if (valGrid) valGrid.innerText = sldGrid.value;
            emitConfig();
        });

        if (sldSpeed) sldSpeed.addEventListener('input', () => {
            if (valSpeed) valSpeed.innerText = sldSpeed.value;
            emitConfig();
        });

        if (sldNoise) sldNoise.addEventListener('input', () => {
            if (valNoise) valNoise.innerText = sldNoise.value;
            emitConfig();
        });

        socket.on('nokka_event', (data) => {
            NokkaFX.toast(data.message, data.type);
            NokkaFX.flash(data.type);

            // Particle effects + camera shake
            const gs = NokkaScene.getGridSize();
            const mode = NokkaManager.getMode();

            if (data.type === 'damage') {
                if (mode === '3d') {
                    NokkaParticles.emitDamageBurst(gs);
                    NokkaShake.trigger(0.6);
                }
            } else if (data.type === 'heal') {
                if (mode === '3d') NokkaParticles.emitHealBurst(gs);
            } else if (data.type === 'reboot') {
                if (mode === '3d') {
                    NokkaParticles.emitRebootBurst(gs);
                    NokkaShake.trigger(0.3);
                }
            }
        });
    }

    function start() {
        if (socket && !running) {
            socket.emit('nokka_start');
            running = true;
            updateUI();
            NokkaFX.toast('Simulación iniciada', 'info');
        }
    }

    function stop() {
        if (socket && running) {
            socket.emit('nokka_stop');
            running = false;
            updateUI();
            NokkaFX.toast('Simulación pausada', 'info');
        }
    }

    function toggle() { running ? stop() : start(); }

    function damage() {
        if (socket) {
            socket.emit('nokka_damage');
            NokkaFX.flash('damage');
        }
    }

    function heal() {
        if (socket) {
            socket.emit('nokka_heal');
            NokkaFX.flash('heal');
        }
    }

    function reboot() {
        if (socket) {
            socket.emit('nokka_reboot');
            NokkaFX.flash('reboot');
        }
    }

    function isRunning() { return running; }

    function huntProfile(username) {
        if (socket && running) {
            socket.emit('nokka_hunt_profile', { username: username });
        }
    }

    return { connect, start, stop, toggle, damage, heal, reboot, isRunning, huntProfile };
})();


// ═══════════════════════════════════════════════════════════════
// 🎮 MODULE: Controls & Keyboard
// ═══════════════════════════════════════════════════════════════

const NokkaControls = (() => {
    function init() {
        const btnStart = document.getElementById('btn-start');
        const btnStop = document.getElementById('btn-stop');
        const btnDamage = document.getElementById('btn-damage');
        const btnHeal = document.getElementById('btn-heal');
        const btnReboot = document.getElementById('btn-reboot');
        const btnHunt = document.getElementById('btn-hunt');
        const inputHunt = document.getElementById('hunter-target');

        if (btnStart) btnStart.addEventListener('click', NokkaSocket.start);
        if (btnStop) btnStop.addEventListener('click', NokkaSocket.stop);
        if (btnDamage) btnDamage.addEventListener('click', NokkaSocket.damage);
        if (btnHeal) btnHeal.addEventListener('click', NokkaSocket.heal);
        if (btnReboot) btnReboot.addEventListener('click', NokkaSocket.reboot);
        
        if (btnHunt && inputHunt) {
            btnHunt.addEventListener('click', () => {
                const target = inputHunt.value.trim().replace('@', '');
                if (target) {
                    if (NokkaSocket.isRunning()) {
                        NokkaFX.toast(`Inyectando escaner para @${target}...`, 'info');
                        NokkaSocket.huntProfile(target);
                        inputHunt.value = '';
                    } else {
                        NokkaFX.toast('Inicia la simulación primero', 'warning');
                    }
                }
            });
            inputHunt.addEventListener('keypress', (e) => {
                if(e.key === 'Enter') btnHunt.click();
            });
        }

        document.addEventListener('keydown', (e) => {
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;

            switch (e.code) {
                case 'Space':
                    e.preventDefault();
                    NokkaSocket.damage();
                    break;
                case 'KeyH':
                    NokkaSocket.heal();
                    break;
                case 'KeyP':
                    NokkaSocket.reboot();
                    break;
                case 'KeyS':
                    NokkaSocket.toggle();
                    break;
            }
        });
    }

    return { init };
})();


// ═══════════════════════════════════════════════════════════════
// 🖥️ UI Helpers
// ═══════════════════════════════════════════════════════════════

function updateUI() {
    const btnStart = document.getElementById('btn-start');
    const btnStop = document.getElementById('btn-stop');
    const running = NokkaSocket.isRunning();

    if (btnStart) btnStart.style.display = running ? 'none' : 'flex';
    if (btnStop) btnStop.style.display = running ? 'flex' : 'none';
}

function updateStatus(status) {
    const banner = document.getElementById('status-banner');
    if (!banner) return;
    banner.textContent = status;
    banner.className = 'status-banner glass-panel';

    if (status.includes('HEALING')) {
        banner.classList.add('status-healing');
    } else if (status.includes('PROCESANDO')) {
        banner.classList.add('status-processing');
    } else {
        banner.classList.add('status-idle');
    }
}

function hideLoading() {
    const overlay = document.getElementById('loading-overlay');
    if (overlay) {
        overlay.classList.add('hidden');
        setTimeout(() => overlay.remove(), 600);
    }
}


// ═══════════════════════════════════════════════════════════════
// 🚀 BOOT
// ═══════════════════════════════════════════════════════════════

document.addEventListener('DOMContentLoaded', () => {
    console.log('🚀 [Nokka] DOMContentLoaded — iniciando módulos...');

    // ── Inicializar valores de sliders en el DOM (evita mostrar "?") ──
    const sldGrid  = document.getElementById('sld-grid');
    const sldSpeed = document.getElementById('sld-speed');
    const sldNoise = document.getElementById('sld-noise');
    const valGrid  = document.getElementById('val-grid');
    const valSpeed = document.getElementById('val-speed');
    const valNoise = document.getElementById('val-noise');
    if (sldGrid  && valGrid)  valGrid.innerText  = sldGrid.value;
    if (sldSpeed && valSpeed) valSpeed.innerText = sldSpeed.value;
    if (sldNoise && valNoise) valNoise.innerText = sldNoise.value;
    console.log(`⚙️  [Nokka] Sliders inicializados — grid=${sldGrid?.value} | speed=${sldSpeed?.value} | noise=${sldNoise?.value}`);

    // ── Init All Modules ──
    try {
        NokkaScene.init('nokka-canvas');
        console.log('✅ [NokkaScene] 3D inicializado.');
    } catch (e) {
        console.error('❌ [NokkaScene] Fallo al inicializar 3D:', e);
    }

    try {
        Nokka2DRenderer.init('nokka-canvas-2d');
        console.log('✅ [Nokka2DRenderer] 2D inicializado.');
    } catch (e) {
        console.error('❌ [Nokka2DRenderer] Fallo al inicializar 2D:', e);
    }

    NokkaManager.init(); // Auto-switch basado en hardware
    NokkaControls.init();
    NokkaSocket.connect();

    setTimeout(hideLoading, 800);
    updateUI();
    updateStatus('ESPERANDO INICIO...');
    console.log('✅ [Nokka] Boot completo.');
});
