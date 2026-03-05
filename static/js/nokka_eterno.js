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

        // ── Arrancar Raycaster educativo (después de crear sensorPoints) ──
        NokkaEduTooltips.init();

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
        NokkaEduTooltips.update();  // hover sobre nodos 3D

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

    // ── updateSensors: consume flat array del backend ──
    // Formato: flat_positions = [x0,y0,z0, x1,y1,z1,...] | flat_colors = [r0,g0,b0,...]
    function updateSensors(flat_pos, flat_col, count, flat_values) {
        activeCount = count;

        // Copiar directamente (sin reagrupación de arrays)
        for (let i = 0; i < count * 3; i++) {
            positionBuffer[i] = flat_pos[i];
            colorBuffer[i]    = flat_col[i];
        }
        for (let i = 0; i < count; i++) {
            sizeBuffer[i] = 3.0;
        }
        // Reset nodos inactivos
        for (let i = count; i < MAX_SENSORS; i++) sizeBuffer[i] = 0;

        const geom = sensorPoints.geometry;
        geom.attributes.position.needsUpdate = true;
        geom.attributes.customColor.needsUpdate = true;
        geom.attributes.size.needsUpdate = true;
        geom.setDrawRange(0, activeCount);

        // Pasar valores de campo al módulo de tooltips educativos
        if (flat_values) NokkaEduTooltips.updateValues(flat_values);
    }

    // ── updateQuiver: consume flat array del backend ──
    function updateQuiver(flat_pos, flat_dir, count) {
        const arrowScale = 0.6;

        for (let i = 0; i < count; i++) {
            const b = i * 3;
            quiverPosBuffer[i * 6]     = flat_pos[b];
            quiverPosBuffer[i * 6 + 1] = flat_pos[b + 1];
            quiverPosBuffer[i * 6 + 2] = flat_pos[b + 2];
            quiverPosBuffer[i * 6 + 3] = flat_pos[b]     + flat_dir[b]     * arrowScale;
            quiverPosBuffer[i * 6 + 4] = flat_pos[b + 1] + flat_dir[b + 1] * arrowScale;
            quiverPosBuffer[i * 6 + 5] = flat_pos[b + 2] + flat_dir[b + 2] * arrowScale;
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

    function getCamera() { return camera; }
    function getScene() { return scene; }
    function getRenderer() { return renderer; }
    function getSensorPoints() { return sensorPoints; }
    function getGridSize() { return gridSize; }

    return { init, updateSensors, updateQuiver, setGridSize,
             getCamera, getScene, getRenderer, getSensorPoints, getGridSize };
})();


// ═══════════════════════════════════════════════════════════════
// 📚 MODULE: Educational Tooltips
// ═══════════════════════════════════════════════════════════════

const NokkaEduTooltips = (() => {
    const raycaster = new THREE.Raycaster();
    raycaster.params.Points.threshold = 0.6; // radio de detección hover en nodos
    const mouse = new THREE.Vector2();
    let _lastIdx = -1;
    let _dom = null;
    let _fieldValues = [];  // valores de campo por nodo (del backend)

    // ── Glosario educativo intuitivo (sin jerga técnica) ──
    const DEFS = {
        field: [
            { range: [0.8, 1.0],  text: '🟢 Campo ALTO: Este nodo está en resonancia máxima — como un imán a plena potencia.' },
            { range: [0.4, 0.8],  text: '🟡 Campo MEDIO: Oscilación estable. El nodo pulsa como un corazón bien calibrado.' },
            { range: [0.0, 0.4],  text: '🔴 Campo BAJO: El nodo está débil. Puede ser precursor de daño.' },
        ],
        concepts: [
            'Fase: el compsá de oscilación del nodo, como el vaivén de una ola en el océano.',
            'Healing: los nodos vecinos sanan al nodo roto compartíendo su energía, como células regenerando tejido.',
            'Entropía: nivel de desorden del campo. Alta entropía = campo caótico = más probabilidad de daño.',
            'Amplitud: con qué fuerza oscila el nodo. Bots tienen amp negativa — como un iman invertido.',
            'Reboot: reinicio total de fase aleatoria, como un Big Bang local que reorganiza todo el campo.'
        ]
    };

    function _fieldLabel(val) {
        const t = Math.abs(val);  // normalizar a positivo
        for (const d of DEFS.field) {
            if (t >= d.range[0] && t <= d.range[1]) return d.text;
        }
        return '⚪️ Campo desconocido.';
    }

    function init() {
        // Crear el div de tooltip una sola vez
        if (document.getElementById('nokka-edu-tooltip')) return;
        _dom = document.createElement('div');
        _dom.id = 'nokka-edu-tooltip';
        _dom.style.cssText = `
            position: fixed;
            pointer-events: none;
            display: none;
            z-index: 9999;
            max-width: 240px;
            padding: 10px 14px;
            border-radius: 10px;
            border: 1px solid rgba(0,255,213,0.45);
            background: rgba(5,5,20,0.92);
            backdrop-filter: blur(8px);
            color: #e0f7fa;
            font-family: 'Outfit', sans-serif;
            font-size: 12px;
            line-height: 1.5;
            box-shadow: 0 0 18px rgba(0,255,213,0.25);
            transition: opacity 0.15s;
        `;
        document.body.appendChild(_dom);

        window.addEventListener('mousemove', (e) => {
            mouse.x = (e.clientX / window.innerWidth)  * 2 - 1;
            mouse.y = -(e.clientY / window.innerHeight) * 2 + 1;
            if (_dom && _dom.style.display === 'block') {
                _dom.style.left = (e.clientX + 16) + 'px';
                _dom.style.top  = Math.min(e.clientY + 16, window.innerHeight - 180) + 'px';
            }
        });
        console.log('📚 [NokkaEduTooltips] Raycaster educativo inicializado.');
    }

    function update() {
        const cam = NokkaScene.getCamera();
        const pts = NokkaScene.getSensorPoints();
        if (!cam || !pts) return;

        raycaster.setFromCamera(mouse, cam);
        const hits = raycaster.intersectObject(pts);

        if (hits.length > 0) {
            const idx = hits[0].index;
            if (idx === _lastIdx) return;  // sin cambio
            _lastIdx = idx;

            const val  = _fieldValues[idx] ?? 0;
            const x = positionBuffer ? positionBuffer[idx*3]   : '?';
            const y = positionBuffer ? positionBuffer[idx*3+1] : '?';
            const z = positionBuffer ? positionBuffer[idx*3+2] : '?';
            const concept = DEFS.concepts[idx % DEFS.concepts.length];

            _dom.innerHTML = `
                <div style="color:#00ffd5;font-weight:700;margin-bottom:4px">
                    ⚡ Nodo [${Math.round(x)},${Math.round(y)},${Math.round(z)}]
                </div>
                <div style="margin-bottom:6px">${_fieldLabel(val)}</div>
                <div style="font-size:11px;color:#aaa;border-top:1px solid rgba(0,255,213,0.2);padding-top:6px">
                    📚 <em>${concept}</em>
                </div>
            `;
            _dom.style.display = 'block';
        } else {
            if (_lastIdx !== -1) { _lastIdx = -1; _dom.style.display = 'none'; }
        }
    }

    function updateValues(values) { _fieldValues = values; }

    return { init, update, updateValues };
})();


// ═══════════════════════════════════════════════════════════════
//  MODULE: Hardware Detection
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
    let currentMode = '3d';
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

        // Auto-detect hardware en boot (solo una vez, sin watchdog)
        const info = NokkaHardware.getInfo();
        NokkaHardware.updateHUD();

        if (info.isLowEnd) {
            console.log('🖥️ [NokkaManager] Hardware bajo detectado → modo 2D directo');
            setMode('2d');
        } else {
            setMode('3d');
        }
    }

    function setMode(mode) {
        currentMode = mode;
        console.log('🔄 [NokkaManager] Modo:', mode);

        const btn3d = document.getElementById('mode-3d');
        const btn2d = document.getElementById('mode-2d');
        if (btn3d) btn3d.classList.toggle('active', mode === '3d');
        if (btn2d) btn2d.classList.toggle('active', mode === '2d');

        if (canvases['3d']) canvases['3d'].style.display = (mode === '3d') ? 'block' : 'none';
        if (canvases['2d']) canvases['2d'].style.display = (mode === '2d') ? 'block' : 'none';

        const icon = mode === '3d' ? '🧊' : '🖥️';
        NokkaFX.toast(`${icon} Modo ${mode.toUpperCase()} activado`, 'info');
    }




// ═══════════════════════════════════════════════════════════════
// 🎵 MODULE: YouTube Audio Reactor
// ═══════════════════════════════════════════════════════════════

const NokkaYouTubeAudio = (() => {
    // ── State ──
    let _audioCtx   = null;
    let _analyser   = null;
    let _dataArray  = null;
    let _source     = null;
    let _stream     = null;
    let _rafId      = null;
    let _emitTimer  = null;
    let _ytPlayer   = null;
    let _active     = false;

    // ── YouTube IFrame API ──
    let _ytApiReady = false;

    function _loadYTApi() {
        if (document.getElementById('yt-api-script')) return;
        const tag = document.createElement('script');
        tag.id  = 'yt-api-script';
        tag.src = 'https://www.youtube.com/iframe_api';
        document.head.appendChild(tag);
        console.log('🎵 [YTAudio] YouTube IFrame API cargada.');
    }

    // Callback global requerido por la IFrame API
    window.onYouTubeIframeAPIReady = function () {
        _ytApiReady = true;
        console.log('✅ [YTAudio] YouTube IFrame API ready.');
    };

    function _extractVideoId(input) {
        // Acepta: ID directo, URL watch?v=, youtu.be/, shorts/
        const patterns = [
            /(?:v=|\/)([\w-]{11})(?:\?|&|$|\/)/,
            /youtu\.be\/([\w-]{11})/,
            /shorts\/([\w-]{11})/,
        ];
        for (const p of patterns) {
            const m = input.match(p);
            if (m) return m[1];
        }
        // Si tiene exactamente 11 chars, asumir que ya es ID
        if (/^[\w-]{11}$/.test(input.trim())) return input.trim();
        return null;
    }

    function loadVideo() {
        const input = (document.getElementById('yt-url-input')?.value || '').trim();
        if (!input) { _setStatus('⚠️ Ingresa URL o ID'); return; }

        const videoId = _extractVideoId(input);
        if (!videoId) { _setStatus('⚠️ URL no reconocida'); return; }

        _loadYTApi();

        const container = document.getElementById('yt-player-container');
        if (container) container.style.display = 'block';

        const _tryCreate = () => {
            if (!_ytApiReady || !window.YT?.Player) {
                setTimeout(_tryCreate, 300);
                return;
            }
            if (_ytPlayer) { _ytPlayer.destroy(); _ytPlayer = null; }
            _ytPlayer = new YT.Player('yt-player', {
                width: '100%', height: '100%',
                videoId: videoId,
                playerVars: { autoplay: 1, controls: 1, rel: 0 },
                events: {
                    onReady: (e) => {
                        e.target.playVideo();
                        _setStatus('▶ Reproduciendo — captura audio');
                        console.log(`🎵 [YTAudio] Video cargado: ${videoId}`);
                    },
                    onError: (e) => _setStatus(`❌ Error YT: ${e.data}`)
                }
            });
        };
        _tryCreate();
    }

    // ── Inicializar WebAudio desde stream ──
    function _setupAnalyser(stream) {
        stopCapture();  // cerrar cualquier stream previo

        _stream   = stream;
        _audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        _analyser = _audioCtx.createAnalyser();
        _analyser.fftSize = 256;
        _analyser.smoothingTimeConstant = 0.8;
        _dataArray = new Uint8Array(_analyser.frequencyBinCount); // 128 bins

        _source = _audioCtx.createMediaStreamSource(stream);
        _source.connect(_analyser);
        // NO conectar al destination → no reproduce de vuelta (evita eco)

        _active = true;
        console.log('🎙️ [YTAudio] Analyser configurado — sampleRate:', _audioCtx.sampleRate);
        _startLoop();
        _startEmit();
    }

    async function captureTab() {
        try {
            _setStatus('⏳ Solicitando Tab Audio...');
            // getDisplayMedia {audio:true} captura el audio del tab en Chrome
            const stream = await navigator.mediaDevices.getDisplayMedia({
                video: false,
                audio: { suppressLocalAudioPlayback: false }
            });
            _setupAnalyser(stream);
            _setStatus('🖥️ Tab audio activo');
            console.log('✅ [YTAudio] Tab audio capturado.');
        } catch (e) {
            _setStatus('❌ Tab Audio: ' + e.message);
            console.warn('⚠️ [YTAudio] captureTab error:', e);
        }
    }

    async function captureMic() {
        try {
            _setStatus('⏳ Solicitando micrófono...');
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
            _setupAnalyser(stream);
            _setStatus('🎙️ Micrófono activo');
            console.log('✅ [YTAudio] Micrófono capturado.');
        } catch (e) {
            _setStatus('❌ Mic: ' + e.message);
            console.warn('⚠️ [YTAudio] captureMic error:', e);
        }
    }

    function stopCapture() {
        _active = false;
        if (_rafId) { cancelAnimationFrame(_rafId); _rafId = null; }
        if (_emitTimer) { clearInterval(_emitTimer); _emitTimer = null; }
        if (_source) { try { _source.disconnect(); } catch (e) {} _source = null; }
        if (_audioCtx) { try { _audioCtx.close(); } catch (e) {} _audioCtx = null; }
        if (_stream) { _stream.getTracks().forEach(t => t.stop()); _stream = null; }
        _setStatus('· inactivo');
        // Limpiar canvas
        const cv = document.getElementById('yt-fft-canvas');
        if (cv) { const ctx = cv.getContext('2d'); ctx.clearRect(0, 0, cv.width, cv.height); }
        console.log('⏹️  [YTAudio] Captura detenida.');
    }

    // ── Loop de visualización FFT ──────────────────────
    function _startLoop() {
        const canvas = document.getElementById('yt-fft-canvas');
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        const W = canvas.width, H = canvas.height;

        function draw() {
            if (!_active || !_analyser) return;
            _rafId = requestAnimationFrame(draw);
            _analyser.getByteFrequencyData(_dataArray);

            ctx.fillStyle = 'rgba(5,5,20,0.4)';
            ctx.fillRect(0, 0, W, H);

            const barW = W / _dataArray.length;
            for (let i = 0; i < _dataArray.length; i++) {
                const v = _dataArray[i] / 255;
                const h = v * H;
                // Gradiente por frecuencia: bass=rosa, mid=cyan, high=violeta
                const r = i < 43 ? 255 : i < 86 ? Math.round(255 * (1 - (i-43)/43)) : 0;
                const g = i < 43 ? Math.round(77 * (i/43)) : i < 86 ? 255 : Math.round(255 * (i-86)/42);
                const b = i < 43 ? 136 : i < 86 ? 213 : 255;
                ctx.fillStyle = `rgb(${r},${g},${b})`;
                ctx.fillRect(i * barW, H - h, barW - 0.5, h);
            }
        }
        draw();
    }

    // ── Extrae y emite bandas cada 200ms ───────────────
    function _startEmit() {
        if (_emitTimer) clearInterval(_emitTimer);
        _emitTimer = setInterval(() => {
            if (!_active || !_analyser) return;
            _analyser.getByteFrequencyData(_dataArray);

            const bins = _dataArray.length; // 128
            // Bass: 0–20%, Mid: 20–60%, High: 60–100%
            const bandSize = [
                [0,              Math.floor(bins * 0.20)],
                [Math.floor(bins * 0.20), Math.floor(bins * 0.60)],
                [Math.floor(bins * 0.60), bins],
            ];
            const avg = (a, b) => {
                let s = 0; for (let i = a; i < b; i++) s += _dataArray[i];
                return s / ((b - a) * 255);
            };

            const bass = avg(...bandSize[0]);
            const mid  = avg(...bandSize[1]);
            const high = avg(...bandSize[2]);
            const energy = (bass * 0.5 + mid * 0.3 + high * 0.2);

            // Actualizar HUD
            const fmt = v => v.toFixed(2);
            const elBass = document.getElementById('yt-bass');
            const elMid  = document.getElementById('yt-mid');
            const elHigh = document.getElementById('yt-high');
            if (elBass) elBass.textContent = fmt(bass);
            if (elMid)  elMid.textContent  = fmt(mid);
            if (elHigh) elHigh.textContent = fmt(high);

            // Emitir al servidor
            const mode = document.getElementById('yt-inject-mode')?.value || 'phase';
            if (window._nokkaSocket) {
                window._nokkaSocket.emit('nokka_audio_inject', {
                    bass: parseFloat(bass.toFixed(3)),
                    mid:  parseFloat(mid.toFixed(3)),
                    high: parseFloat(high.toFixed(3)),
                    energy: parseFloat(energy.toFixed(3)),
                    mode: mode
                });
            }
        }, 200);
    }

    function _setStatus(text) {
        const el = document.getElementById('yt-status');
        if (el) el.textContent = text;
    }

    return { loadVideo, captureTab, captureMic, stopCapture };
})();


    function updateData(data) {
        NokkaStats.update(data.stats, data.frame);
        const s = data.sensors;
        const q = data.quiver;

        if (currentMode === '3d') {
            NokkaScene.setGridSize(data.gridSize);
            NokkaScene.updateSensors(s.flat_positions, s.flat_colors, s.count, s.flat_values);
            NokkaScene.updateQuiver(q.flat_positions, q.flat_directions, q.count);
        } else {
            Nokka2DRenderer.setGridSize(data.gridSize);
            // 2D renderer: reagrupar flat para compatibilidad
            const positions = [];
            const colors    = [];
            for (let i = 0; i < s.count; i++) {
                positions.push([s.flat_positions[i*3], s.flat_positions[i*3+1], s.flat_positions[i*3+2]]);
                colors.push(   [s.flat_colors[i*3],    s.flat_colors[i*3+1],    s.flat_colors[i*3+2]]);
            }
            Nokka2DRenderer.updateSensors(positions, colors);
            Nokka2DRenderer.updateQuiver([], []);
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
        window._nokkaSocket = socket;  // expuesto para NokkaYouTubeAudio

        socket.on('connect', () => {
            console.log('🌌 NOKKA connected:', socket.id);
            NokkaFX.toast('Conexión establecida', 'info');
            NokkaAudio.playConnect();
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

            // Quantum Shadows (v2.7)
            if (data.quantum) NokkaQuantum.update(data.quantum);
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

            const gs = NokkaScene.getGridSize();
            const mode = NokkaManager.getMode();

            if (data.type === 'damage') {
                NokkaAudio.playDamage();
                if (mode === '3d') {
                    NokkaParticles.emitDamageBurst(gs);
                    NokkaShake.trigger(0.6);
                }
            } else if (data.type === 'heal') {
                NokkaAudio.playHeal();
                if (mode === '3d') NokkaParticles.emitHealBurst(gs);
            } else if (data.type === 'reboot') {
                NokkaAudio.playReboot();
                if (mode === '3d') {
                    NokkaParticles.emitRebootBurst(gs);
                    NokkaShake.trigger(0.3);
                }
            }
        });

        socket.on('nokka_validation_progress', (data) => {
            if (window.NokkaValidator) NokkaValidator.updateProgress(data.progress);
        });

        socket.on('nokka_validation_results', (data) => {
            if (window.NokkaValidator) NokkaValidator.showResults(data);
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
// 🔊 MODULE: NokkaAudio — WebAudio API Procedural (Upgrade #5)
// ═══════════════════════════════════════════════════════════════

const NokkaAudio = (() => {
    let ctx = null;
    let masterGain = null;
    let muted = false;
    let initialized = false;

    // ── Inicializar AudioContext (diferido: requiere gesto del usuario) ──
    function init() {
        try {
            ctx = new (window.AudioContext || window.webkitAudioContext)();
            masterGain = ctx.createGain();
            masterGain.gain.value = 0.35;
            masterGain.connect(ctx.destination);
            initialized = true;
            console.log('🔊 [NokkaAudio] WebAudio API inicializado — sampleRate:', ctx.sampleRate);
        } catch (e) {
            console.warn('⚠️ [NokkaAudio] No disponible en este browser:', e);
        }
    }

    function _resume() {
        if (ctx && ctx.state === 'suspended') ctx.resume();
    }

    // ── Heal: resonancia baja orgánica — Kultrun cósmico ──
    function playHeal() {
        if (!initialized || muted) return;
        _resume();
        try {
            const now = ctx.currentTime;

            // Sub-bass rumble (kultrun bajo)
            const osc1 = ctx.createOscillator();
            const gain1 = ctx.createGain();
            osc1.type = 'sine';
            osc1.frequency.setValueAtTime(60, now);
            osc1.frequency.exponentialRampToValueAtTime(40, now + 1.2);
            gain1.gain.setValueAtTime(0.0, now);
            gain1.gain.linearRampToValueAtTime(0.6, now + 0.08);
            gain1.gain.exponentialRampToValueAtTime(0.001, now + 1.2);
            osc1.connect(gain1); gain1.connect(masterGain);
            osc1.start(now); osc1.stop(now + 1.2);

            // Harmónico brillante (healing aura)
            const osc2 = ctx.createOscillator();
            const gain2 = ctx.createGain();
            osc2.type = 'triangle';
            osc2.frequency.setValueAtTime(528, now + 0.05);  // frecuencia Solfeggio "healing"
            osc2.frequency.linearRampToValueAtTime(432, now + 1.0);
            gain2.gain.setValueAtTime(0.0, now);
            gain2.gain.linearRampToValueAtTime(0.2, now + 0.15);
            gain2.gain.exponentialRampToValueAtTime(0.001, now + 1.5);
            osc2.connect(gain2); gain2.connect(masterGain);
            osc2.start(now + 0.05); osc2.stop(now + 1.5);

            console.log('🔊 [NokkaAudio] heal — 60Hz kultrun + 528Hz aura');
        } catch (e) { console.warn('❌ [NokkaAudio] playHeal error:', e); }
    }

    // ── Damage: whale-call distorsionado — interferencia destructiva ──
    function playDamage() {
        if (!initialized || muted) return;
        _resume();
        try {
            const now = ctx.currentTime;

            // Whale descend (freq sweep descendente)
            const osc = ctx.createOscillator();
            const dist = ctx.createWaveShaper();
            const gain = ctx.createGain();

            // Distortion curve
            const curve = new Float32Array(256);
            for (let i = 0; i < 256; i++) {
                const x = (i * 2) / 256 - 1;
                curve[i] = (Math.PI + 200) * x / (Math.PI + 200 * Math.abs(x));
            }
            dist.curve = curve;

            osc.type = 'sawtooth';
            osc.frequency.setValueAtTime(320, now);
            osc.frequency.exponentialRampToValueAtTime(55, now + 0.7);
            gain.gain.setValueAtTime(0.0, now);
            gain.gain.linearRampToValueAtTime(0.5, now + 0.04);
            gain.gain.exponentialRampToValueAtTime(0.001, now + 0.8);

            osc.connect(dist); dist.connect(gain); gain.connect(masterGain);
            osc.start(now); osc.stop(now + 0.8);

            console.log('🔊 [NokkaAudio] damage — whale-call distorsionado 320→55Hz');
        } catch (e) { console.warn('❌ [NokkaAudio] playDamage error:', e); }
    }

    // ── Reboot: burst de noise filtrado — tambor galáctico ──
    function playReboot() {
        if (!initialized || muted) return;
        _resume();
        try {
            const now = ctx.currentTime;
            const bufferSize = ctx.sampleRate * 0.6;
            const buffer = ctx.createBuffer(1, bufferSize, ctx.sampleRate);
            const data = buffer.getChannelData(0);
            for (let i = 0; i < bufferSize; i++) data[i] = Math.random() * 2 - 1;

            const source = ctx.createBufferSource();
            source.buffer = buffer;

            // BandPass filter centrado en 200Hz (tambor bajo)
            const filter = ctx.createBiquadFilter();
            filter.type = 'bandpass';
            filter.frequency.value = 200;
            filter.Q.value = 0.8;

            const gain = ctx.createGain();
            gain.gain.setValueAtTime(0.0, now);
            gain.gain.linearRampToValueAtTime(0.9, now + 0.01);
            gain.gain.exponentialRampToValueAtTime(0.001, now + 0.6);

            source.connect(filter); filter.connect(gain); gain.connect(masterGain);
            source.start(now);

            // + Sweep tonal encima
            const osc = ctx.createOscillator();
            const og = ctx.createGain();
            osc.type = 'sine';
            osc.frequency.setValueAtTime(100, now);
            osc.frequency.exponentialRampToValueAtTime(800, now + 0.5);
            og.gain.setValueAtTime(0.3, now);
            og.gain.exponentialRampToValueAtTime(0.001, now + 0.5);
            osc.connect(og); og.connect(masterGain);
            osc.start(now); osc.stop(now + 0.5);

            console.log('🔊 [NokkaAudio] reboot — tambor galáctico + sweep');
        } catch (e) { console.warn('❌ [NokkaAudio] playReboot error:', e); }
    }

    // ── Connect: ping suave de conexión ──
    function playConnect() {
        if (!initialized || muted) return;
        _resume();
        try {
            const now = ctx.currentTime;
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.type = 'sine';
            osc.frequency.setValueAtTime(880, now);
            osc.frequency.setValueAtTime(1320, now + 0.1);
            gain.gain.setValueAtTime(0.15, now);
            gain.gain.exponentialRampToValueAtTime(0.001, now + 0.4);
            osc.connect(gain); gain.connect(masterGain);
            osc.start(now); osc.stop(now + 0.4);
        } catch (e) {}
    }

    function toggleMute() {
        muted = !muted;
        if (masterGain) masterGain.gain.value = muted ? 0 : 0.35;
        const icon = muted ? '🔇' : '🔊';
        NokkaFX.toast(`${icon} Audio ${muted ? 'silenciado' : 'activado'}`, 'info');
        console.log(`🔊 [NokkaAudio] Mute: ${muted}`);
        // Actualizar botón mute si existe
        const btn = document.getElementById('btn-mute');
        if (btn) btn.textContent = muted ? '🔇' : '🔊';
    }

    function isMuted() { return muted; }

    return { init, playHeal, playDamage, playReboot, playConnect, toggleMute, isMuted };
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
                case 'KeyM':
                    NokkaAudio.toggleMute();
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
// 🛡️ MODULE: NokkaValidator
// ═══════════════════════════════════════════════════════════════

const NokkaValidator = (() => {
    let running = false;
    const btn = document.getElementById('btn-run-validation');
    const progContainer = document.getElementById('val-progress-container');
    const progBar = document.getElementById('val-progress-bar');
    const progText = document.getElementById('val-progress-text');
    const resultsGrid = document.getElementById('val-results');

    function run() {
        if (running) return;
        running = true;
        
        // UI Reset
        if (btn) {
            btn.disabled = true;
            btn.innerText = '⏳ PROCESANDO...';
            btn.style.opacity = '0.5';
        }
        if (progContainer) progContainer.style.display = 'block';
        if (progBar) progBar.style.width = '0%';
        if (progText) progText.innerText = '0%';
        if (resultsGrid) resultsGrid.style.display = 'none';

        // Socket Emit
        if (window._nokkaSocket) {
            window._nokkaSocket.emit('nokka_run_validation');
        }
    }

    function updateProgress(p) {
        if (progBar) progBar.style.width = p + '%';
        if (progText) progText.innerText = p + '%';
    }

    function showResults(data) {
        running = false;
        if (btn) {
            btn.disabled = false;
            btn.innerText = '🚀 RE-EJECUTAR LOOCV';
            btn.style.opacity = '1';
        }
        if (progContainer) progContainer.style.display = 'none';
        if (resultsGrid) {
            resultsGrid.style.display = 'grid';
            
            const rc = (data.acc_rc * 100).toFixed(1) + '%';
            const rb = (data.acc_rule * 100).toFixed(1) + '%';
            const delta = (data.delta * 100).toFixed(1);
            const sign = delta >= 0 ? '+' : '';
            
            document.getElementById('val-acc-rc').innerText = rc;
            document.getElementById('val-acc-rule').innerText = rb;
            
            const elDelta = document.getElementById('val-delta');
            elDelta.innerText = sign + delta + '%';
            elDelta.className = 'cmp-value ' + (delta >= 0 ? 'heal' : 'damage');
            
            document.getElementById('val-time').innerText = (data.time_ms / 1000).toFixed(1) + 's';
        }
    }

    return { run, updateProgress, showResults };
})();

window.NokkaValidator = NokkaValidator;


// ═══════════════════════════════════════════════════════════════
// ⚛️ MODULE: Quantum Shadows (v2.7)
// ═══════════════════════════════════════════════════════════════

const NokkaQuantum = (() => {
    const els = {
        t1Avg:          document.getElementById('qt-t1-avg'),
        switches:       document.getElementById('qt-switches'),
        uncertaintyVal: document.getElementById('qt-uncertainty-val'),
        uncertaintyBar: document.getElementById('qt-uncertainty-bar'),
        robustness:     document.getElementById('qt-robustness'),
        traceCanvas:    document.getElementById('qt-trace-canvas'),
    };

    let _traceCtx = null;
    let _lastTrace = [];

    function initSliders() {
        const sldRate   = document.getElementById('sld-tls-rate');
        const sldFactor = document.getElementById('sld-tls-factor');
        const valRate   = document.getElementById('val-tls-rate');
        const valFactor = document.getElementById('val-tls-factor');

        const emitQuantum = () => {
            if (window._nokkaSocket) {
                window._nokkaSocket.emit('nokka_update_quantum', {
                    tls_switch_rate: parseFloat(sldRate?.value || 0.1),
                    tls_max_factor:  parseFloat(sldFactor?.value || 10),
                });
            }
        };

        if (sldRate) sldRate.addEventListener('input', () => {
            if (valRate) valRate.innerText = parseFloat(sldRate.value).toFixed(2) + ' Hz';
            emitQuantum();
        });
        if (sldFactor) sldFactor.addEventListener('input', () => {
            if (valFactor) valFactor.innerText = '×' + parseFloat(sldFactor.value).toFixed(1);
            emitQuantum();
        });
    }

    function update(quantumData) {
        if (!quantumData || !quantumData.t1_avg_ms) return;

        const q = quantumData;

        // HUD values
        if (els.t1Avg)          els.t1Avg.textContent          = q.t1_avg_ms.toFixed(3);
        if (els.switches)       els.switches.textContent       = q.switches_frame;
        if (els.uncertaintyVal) els.uncertaintyVal.textContent  = q.uncertainty.toFixed(4);
        if (els.robustness)     els.robustness.textContent     = (q.robustness * 100).toFixed(1) + '%';

        // Uncertainty bar (clamp to 0-100%)
        if (els.uncertaintyBar) {
            const pct = Math.min(100, q.uncertainty * 2000); // scale for visual
            els.uncertaintyBar.style.width = pct + '%';
        }

        // Switches flash red when ×10 event
        if (els.switches && q.switches_frame > 0) {
            els.switches.style.textShadow = '0 0 12px rgba(255,77,77,0.8)';
            setTimeout(() => { if (els.switches) els.switches.style.textShadow = 'none'; }, 200);
        }

        // T₁ Trace
        if (q.t1_trace) {
            _lastTrace = q.t1_trace;
            _drawTrace();
        }
    }

    function _drawTrace() {
        if (!els.traceCanvas) return;
        if (!_traceCtx) _traceCtx = els.traceCanvas.getContext('2d');
        const ctx = _traceCtx;
        const W = els.traceCanvas.width;
        const H = els.traceCanvas.height;
        const data = _lastTrace;
        if (data.length < 2) return;

        ctx.fillStyle = 'rgba(5,5,20,0.6)';
        ctx.fillRect(0, 0, W, H);

        // Find y range
        let yMin = Infinity, yMax = -Infinity;
        for (const v of data) { if (v < yMin) yMin = v; if (v > yMax) yMax = v; }
        const yRange = Math.max(yMax - yMin, 0.001);

        // Draw line
        ctx.strokeStyle = '#ff4d88';
        ctx.lineWidth = 1.5;
        ctx.shadowBlur = 4;
        ctx.shadowColor = 'rgba(255,77,136,0.5)';
        ctx.beginPath();
        for (let i = 0; i < data.length; i++) {
            const x = (i / (data.length - 1)) * W;
            const y = H - ((data[i] - yMin) / yRange) * (H - 6) - 3;
            if (i === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
        }
        ctx.stroke();
        ctx.shadowBlur = 0;

        // Base line
        const baseY = H - ((0.17 - yMin) / yRange) * (H - 6) - 3;
        if (baseY > 0 && baseY < H) {
            ctx.setLineDash([3, 3]);
            ctx.strokeStyle = 'rgba(0,255,213,0.25)';
            ctx.lineWidth = 0.5;
            ctx.beginPath();
            ctx.moveTo(0, baseY);
            ctx.lineTo(W, baseY);
            ctx.stroke();
            ctx.setLineDash([]);
        }

        // Label
        ctx.fillStyle = 'rgba(255,77,136,0.6)';
        ctx.font = '8px JetBrains Mono';
        ctx.fillText('T₁ trace (center node)', 4, 10);
    }

    return { update, initSliders };
})();


// ═══════════════════════════════════════════════════════════════
// 🚀 BOOT
// ═══════════════════════════════════════════════════════════════

document.addEventListener('DOMContentLoaded', () => {
    console.log('🚀 [Nokka] DOMContentLoaded — iniciando módulos...');

    // ── Audio (primer gesto asegura contexto activo) ──
    NokkaAudio.init();

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
    NokkaQuantum.initSliders();  // v2.7 Quantum TLS sliders
    NokkaSocket.connect();

    setTimeout(hideLoading, 800);
    updateUI();
    updateStatus('ESPERANDO INICIO...');
    console.log('✅ [Nokka] Boot completo.');
});
