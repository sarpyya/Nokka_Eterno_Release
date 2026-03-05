#!/usr/bin/env python3
"""
🌌 NOKKA ETERNO v2.7 — Quantum Shadow Injector
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Motor de simulación de campo magnético 3D con auto-healing
+ decoherencia cuántica TLS (arXiv:2506.09576).

Módulo standalone: sin dependencias de Flask.
Se integra vía SocketIO desde app.py.
"""

import numpy as np
import random
import time
import threading

try:
    import psutil
except ImportError:
    psutil = None
    print("⚠️  [Nokka Engine] psutil no disponible — métricas de CPU/RAM usarán estimaciones.")

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


def _sanitize_for_json(obj):
    """Recursively convert numpy types to native Python types for JSON serialization."""
    if isinstance(obj, dict):
        return {k: _sanitize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [_sanitize_for_json(v) for v in obj]
    elif isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    return obj


# ═══════════════════════════════════════════════════════════════
# 🎨 NOKKA COLORMAP: Negro → Cyan → Lima → Amarillo → Blanco
# ═══════════════════════════════════════════════════════════════

PLASMA_STOPS = [
    # ── Cyan oscuro (lowest intensity) ──
    (0.00, 0.30, 0.28),
    (0.00, 0.50, 0.45),
    (0.00, 0.75, 0.65),
    (0.00, 1.00, 0.83),
    # ── Negro (transición baja) ──
    (0.00, 0.50, 0.40),
    (0.02, 0.15, 0.12),
    (0.02, 0.02, 0.02),
    # ── Amarillo ──
    (0.40, 0.35, 0.00),
    (0.80, 0.70, 0.00),
    (1.00, 1.00, 0.00),
    # ── Blanco ──
    (1.00, 1.00, 0.50),
    (1.00, 1.00, 0.85),
    (1.00, 1.00, 1.00),
    # ── Verde Lima (highest intensity) ──
    (0.50, 1.00, 0.30),
    (0.22, 1.00, 0.08),
]


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def plasma_color(value: float, vmin: float = -1.5, vmax: float = 1.5) -> Tuple[float, float, float]:
    """Map a scalar value to an RGB tuple using the plasma colormap."""
    t = max(0.0, min(1.0, (value - vmin) / (vmax - vmin)))
    idx = t * (len(PLASMA_STOPS) - 1)
    lo = int(idx)
    hi = min(lo + 1, len(PLASMA_STOPS) - 1)
    frac = idx - lo
    r = _lerp(PLASMA_STOPS[lo][0], PLASMA_STOPS[hi][0], frac)
    g = _lerp(PLASMA_STOPS[lo][1], PLASMA_STOPS[hi][1], frac)
    b = _lerp(PLASMA_STOPS[lo][2], PLASMA_STOPS[hi][2], frac)
    return (r, g, b)


# ═══════════════════════════════════════════════════════════════
# 🧲 NOKKA SIMULATION CORE
# ═══════════════════════════════════════════════════════════════

@dataclass
class SimulationConfig:
    """Immutable configuration for a NOKKA simulation."""
    grid_size: int = 12
    wave_speed: float = 0.15
    noise_std: float = 0.08
    damage_probability: float = 0.03
    healing_passes: int = 3
    quiver_step: int = 2
    vmin: float = -1.5
    vmax: float = 1.5


class NokkaSimulation:
    """
    3D Magnetic Field Simulation with Self-Healing.

    The simulation manages:
    - A 3D scalar field (intensity) evolving via trigonometric waves + noise
    - A boolean mask of active/damaged sensors
    - An auto-healing mechanism (neighbor averaging)
    - Quiver vectors representing the magnetic field direction

    All state is serializable to a dict for WebSocket streaming.
    """

    def __init__(self, config: Optional[SimulationConfig] = None):
        self.config = config or SimulationConfig()
        self._frame = 0
        self._running = False
        self._healed_this_frame = False
        self._lock = threading.Lock()

        # Stats
        self._total_damage_events = 0
        self._total_heal_events = 0

        # Performance timing
        self._last_step_ms = 0.0
        self._last_serialize_ms = 0.0
        self._last_payload_bytes = 0
        self._cumulative_ops = 0

        # Quantum TLS Injector (v2.7)
        self.quantum_injector = None

        self._init_simulation()
        N = self.config.grid_size
        print(f"🧲 [NokkaSimulation] Inicializada — Grid={N}³ ({N**3} nodos) | "
              f"wave_speed={self.config.wave_speed} | noise_std={self.config.noise_std}")

        # Plasma LUT precalculada (256 niveles) para aceleración brutal
        self._plasma_lut = np.zeros((256, 3), dtype=np.float32)
        for i in range(256):
            t = i / 255.0
            val = self.config.vmin + t * (self.config.vmax - self.config.vmin)
            self._plasma_lut[i] = plasma_color(val, self.config.vmin, self.config.vmax)

    def _init_simulation(self):
        """Initialize simulation arrays from current config."""
        N = self.config.grid_size

        try:
            # Scalar field & sensor mask
            self._grid = np.zeros((N, N, N), dtype=np.float32)
            self._sensors_active = np.ones((N, N, N), dtype=bool)

            # Phase accumulator for wave evolution
            self._phase = np.random.rand(N, N, N).astype(np.float32) * 2.0 * np.pi

            # Pre-compute coordinate meshgrids (memory-efficient float32)
            self._x, self._y, self._z = np.meshgrid(
                np.arange(N, dtype=np.float32),
                np.arange(N, dtype=np.float32),
                np.arange(N, dtype=np.float32),
                indexing='ij'
            )

            # Pre-compute quiver grid coordinates
            qs = self.config.quiver_step
            self._qx, self._qy, self._qz = np.meshgrid(
                np.arange(0, N, qs, dtype=np.float32),
                np.arange(0, N, qs, dtype=np.float32),
                np.arange(0, N, qs, dtype=np.float32),
                indexing='ij'
            )

            # Pre-allocate healing buffers (evita alloc en cada frame)
            self._neighbor_sum = np.zeros((N, N, N), dtype=np.float32)
            self._neighbor_count = np.zeros((N, N, N), dtype=np.int32)

            # Performance timing reset
            self._last_step_ms = 0.0
            self._last_serialize_ms = 0.0
            self._last_payload_bytes = 0
            self._cumulative_ops = 0

            # Quantum TLS Injector (v2.7)
            from engines.quantum_tls_injector import QuantumTLSInjector
            self.quantum_injector = QuantumTLSInjector(grid_size=N)

            print(f"[NokkaSimulation] Arrays inicializados -- "
                  f"Grid={N}^3 | Phase shape={self._phase.shape} | "
                  f"Quiver step={qs} -> {len(self._qx.ravel())} vectores | "
                  f"Quantum TLS activo")

        except Exception as e:
            print(f"❌ [NokkaSimulation] Error crítico en _init_simulation: {e}")
            raise

    # ─── Core Simulation Step ────────────────────────────────

    def step(self) -> dict:
        """Advance one frame and return the full renderable state."""
        with self._lock:
            try:
                t0 = time.perf_counter()

                self._frame += 1
                self._healed_this_frame = False

                self._evolve_field()
                self._apply_damage()
                self._apply_healing()

                t1 = time.perf_counter()
                self._last_step_ms = (t1 - t0) * 1000.0

                state = self.get_state()

                t2 = time.perf_counter()
                self._last_serialize_ms = (t2 - t1) * 1000.0

                # Log de desempeño cada 100 frames
                if self._frame % 100 == 0:
                    total_ms = self._last_step_ms + self._last_serialize_ms
                    active = int(np.sum(self._sensors_active))
                    total = self.config.grid_size ** 3
                    damaged = total - active
                    heal_icon = "💚" if self._healed_this_frame else "🔵"
                    print(f"📊 [Frame #{self._frame}] "
                          f"step={self._last_step_ms:.1f}ms | "
                          f"serial={self._last_serialize_ms:.1f}ms | "
                          f"total={total_ms:.1f}ms | "
                          f"activos={active}/{total} | "
                          f"dañados={damaged} {heal_icon}")

                return state

            except Exception as e:
                print(f"❌ [NokkaSimulation] Error en step() frame#{self._frame}: {e}")
                raise

    def _evolve_field(self):
        """Update the scalar field via Newen vs Horror Reaction-Diffusion PDE."""
        try:
            cfg = self.config
            N = cfg.grid_size
            n3 = N * N * N
            self._phase += cfg.wave_speed
            
            # --- PDE Parameters (Newen vs Horror) ---
            dt = 0.1                      # Integration step (Euler stability)
            lambda_neg = 0.21             # Baseline decay (drives toward stable dim)
            D = 0.15                      # Diffusion coefficient (spatial coupling)
            beta = 5.0                    # Horror rejection strength
            
            # 1. Base input field (The geometric 'ancestral' signal)
            theta_ancestral = (
                0.8 * np.sin(self._x * 0.6 + self._phase) * 
                np.cos(self._y * 0.4 + self._phase * 0.7) + 
                0.3 * np.sin(self._z * 1.1 + self._frame * 0.08)
            ).astype(np.float32)
            
            # 2. Laplacian calculation (Discrete 3D spatial coupling)
            from scipy.ndimage import convolve
            kernel = np.ones((3, 3, 3), dtype=np.float32) / 26.0
            kernel[1, 1, 1] = -1.0
            laplacian = convolve(self._grid, kernel, mode='wrap')
            
            # 3. Systemic Horror Rejection (Squash function)
            H = self._grid**2
            rejection_factor = np.exp(-beta * H)
            
            # 4. Total Differential Step
            noise = np.random.normal(0, cfg.noise_std, self._grid.shape).astype(np.float32)
            
            dtheta = (
                -lambda_neg * self._grid + 
                D * laplacian + 
                rejection_factor * (theta_ancestral - self._grid.mean()) +
                noise
            )
            
            # 5. Euler Integration (Recurrence)
            self._grid += dt * dtheta
            self._grid = np.clip(self._grid, -2.5, 2.5) # Prevent numerical explosion

            # ── Quantum Shadow Injector (v2.8 - dt dinámico) ──
            if self.quantum_injector is not None:
                t_now = time.perf_counter()
                dt_real_ms = (t_now - self._last_quantum_time) * 1000 if hasattr(self, '_last_quantum_time') else 60.0
                self._last_quantum_time = t_now

                gamma, gamma_est, uncertainty, n_sw = self.quantum_injector.step(dt_ms=dt_real_ms)

                # Probabilistic quantum damage: low T₁ -> node collapses
                damage_prob = self.quantum_injector.get_damage_probability()
                quantum_damage_mask = (np.random.rand(N, N, N) < damage_prob * 0.05)
                if np.any(quantum_damage_mask):
                    quantum_hit = quantum_damage_mask & self._sensors_active
                    self._sensors_active[quantum_hit] = False
                    self._grid[quantum_hit] *= 0.05
                    n_qdmg = int(np.sum(quantum_hit))
                    self._total_damage_events += n_qdmg

            self._cumulative_ops += N**3 * 18  # Approx ops for PDE + quantum





        except Exception as e:
            print(f"❌ [NokkaSimulation] Error en _evolve_field frame#{self._frame}: {e}")
            raise

    def _apply_damage(self):
        """Stochastic sensor failure (natural degradation)."""
        try:
            if np.random.rand() < self.config.damage_probability:
                N = self.config.grid_size
                dx, dy, dz = (random.randint(0, N - 1) for _ in range(3))
                self._sensors_active[dx, dy, dz] = False
                self._grid[dx, dy, dz] *= 0.1
                self._total_damage_events += 1
                # Log ocasional de daño natural
                if self._total_damage_events % 20 == 0:
                    print(f"⚡ [NokkaSimulation] Daño estocástico acumulado: "
                          f"{self._total_damage_events} eventos | "
                          f"Dañados activos: {int(np.sum(~self._sensors_active))}")
        except Exception as e:
            print(f"❌ [NokkaSimulation] Error en _apply_damage frame#{self._frame}: {e}")

    def _apply_healing(self):
        """Vectorized healing: average from active neighbors using rolls."""
        if np.all(self._sensors_active):
            return  # Nothing to heal

        try:
            directions = [
                (1, 0, 0), (-1, 0, 0),
                (0, 1, 0), (0, -1, 0),
                (0, 0, 1), (0, 0, -1)
            ]

            damaged_mask = ~self._sensors_active
            healed_this_pass_total = 0

            for _ in range(self.config.healing_passes):
                if not np.any(damaged_mask):
                    break

                # Reusar buffers pre-alocados
                self._neighbor_sum.fill(0)
                self._neighbor_count.fill(0)

                for shift in directions:
                    shifted_grid = np.roll(self._grid, shift, axis=(0, 1, 2))
                    shifted_active = np.roll(self._sensors_active, shift, axis=(0, 1, 2))
                    valid = shifted_active & damaged_mask
                    self._neighbor_sum[valid] += shifted_grid[valid]
                    self._neighbor_count[valid] += 1

                can_heal = (self._neighbor_count > 0) & damaged_mask

                if np.any(can_heal):
                    self._grid[can_heal] = self._neighbor_sum[can_heal] / self._neighbor_count[can_heal]
                    self._sensors_active[can_heal] = True
                    healed_count = int(np.sum(can_heal))
                    self._total_heal_events += healed_count
                    healed_this_pass_total += healed_count
                    damaged_mask[can_heal] = False

            if healed_this_pass_total > 0:
                self._healed_this_frame = True

        except Exception as e:
            print(f"❌ [NokkaSimulation] Error en _apply_healing frame#{self._frame}: {e}")

    # ─── User Actions ────────────────────────────────────────

    def inject_damage(self, count: int = 20):
        """Inject a burst of random sensor failures."""
        try:
            N = self.config.grid_size
            for _ in range(count):
                dx, dy, dz = (random.randint(0, N - 1) for _ in range(3))
                self._sensors_active[dx, dy, dz] = False
                self._grid[dx, dy, dz] *= 0.05
                self._total_damage_events += 1
            damaged = int(np.sum(~self._sensors_active))
            print(f"💥 [NokkaSimulation] inject_damage: {count} nodos colapsados | "
                  f"Total dañados={damaged}/{N**3} | "
                  f"Salud={100*(N**3-damaged)/N**3:.1f}%")
        except Exception as e:
            print(f"❌ [NokkaSimulation] Error en inject_damage: {e}")

    def force_heal(self):
        """Force-heal ALL damaged sensors with many propagation passes."""
        try:
            N = self.config.grid_size
            original_damaged = int(np.sum(~self._sensors_active))

            if original_damaged == 0:
                print("✅ [NokkaSimulation] force_heal: Sin nodos dañados — nada que sanar.")
                return

            print(f"💚 [NokkaSimulation] force_heal iniciado — {original_damaged} nodos a sanar...")

            max_passes = N * 3
            directions = [
                (1, 0, 0), (-1, 0, 0),
                (0, 1, 0), (0, -1, 0),
                (0, 0, 1), (0, 0, -1)
            ]

            healed_total = 0
            for pass_num in range(max_passes):
                damaged_mask = ~self._sensors_active
                if not np.any(damaged_mask):
                    print(f"✅ [NokkaSimulation] force_heal completado en {pass_num} passes — "
                          f"{healed_total} nodos restaurados.")
                    break

                neighbor_sum = np.zeros_like(self._grid)
                neighbor_count = np.zeros_like(self._grid, dtype=np.int32)

                for shift in directions:
                    shifted_grid = np.roll(self._grid, shift, axis=(0, 1, 2))
                    shifted_active = np.roll(self._sensors_active, shift, axis=(0, 1, 2))
                    valid = shifted_active & damaged_mask
                    neighbor_sum[valid] += shifted_grid[valid]
                    neighbor_count[valid] += 1

                can_heal = (neighbor_count > 0) & damaged_mask

                if np.any(can_heal):
                    self._grid[can_heal] = neighbor_sum[can_heal] / neighbor_count[can_heal]
                    self._sensors_active[can_heal] = True
                    healed_count = int(np.sum(can_heal))
                    healed_total += healed_count
                    self._total_heal_events += healed_count
            else:
                remaining = int(np.sum(~self._sensors_active))
                print(f"⚠️  [NokkaSimulation] force_heal: límite de {max_passes} passes alcanzado — "
                      f"{remaining} nodos aún dañados (posible cluster aislado).")

            if healed_total > 0:
                self._healed_this_frame = True
                print(f"💚 [NokkaSimulation] force_heal fin: {healed_total}/{original_damaged} nodos sanados.")

        except Exception as e:
            print(f"❌ [NokkaSimulation] Error en force_heal: {e}")

    def reboot_wave(self):
        """Reset phase with new random seed — strong wave reboot."""
        try:
            old_frame = self._frame
            old_damage = self._total_damage_events
            self._phase = np.random.rand(*self._phase.shape).astype(np.float32) * 2.0 * np.pi
            self._sensors_active[:] = True
            self._total_damage_events = 0
            self._total_heal_events = 0
            print(f"🔄 [NokkaSimulation] reboot_wave completado — "
                  f"frame={old_frame} | daños previos reseteados: {old_damage} | "
                  f"fase aleatoria nueva generada.")
        except Exception as e:
            print(f"❌ [NokkaSimulation] Error en reboot_wave: {e}")

    # ─── State Serialization ─────────────────────────────────

    def get_state(self) -> dict:
        """
        Return the full simulation state as a JSON-serializable dict.

        Structure:
        {
            "frame": int,
            "sensors": { "positions": [[x,y,z],...], "colors": [[r,g,b],...] },
            "quiver": { "positions": [[x,y,z],...], "directions": [[ux,uy,uz],...] },
            "stats": { ... },
            "status": "HEALING ACTIVADO" | "PROCESANDO GALÁCTICO"
        }
        """
        try:
            cfg = self.config

            # ── Active sensor positions & colors ──
            active_idx = np.argwhere(self._sensors_active)
            values = self._grid[self._sensors_active]

            # Compute colors via plasma colormap (vectorized LUT lookup)
            t_col = np.clip((values - cfg.vmin) / (cfg.vmax - cfg.vmin), 0.0, 1.0)
            idx_col = (t_col * 255).astype(np.int32)
            colors = self._plasma_lut[idx_col]

            # ── Quiver vectors ──
            f = self._frame
            ux = np.sin(f * 0.1 + self._qx * 0.5) * 0.6
            uy = np.cos(f * 0.12 + self._qy * 0.4) * 0.6
            uz = np.sin(f * 0.08 + self._qz * 0.7) * 0.6

            q_pos = np.stack([self._qx, self._qy, self._qz], axis=-1).reshape(-1, 3)
            q_dir = np.stack([ux, uy, uz], axis=-1).reshape(-1, 3)

            # ── Build response ──
            N = cfg.grid_size
            total_sensors = N * N * N
            active_count = int(np.sum(self._sensors_active))
            quiver_count = len(q_pos)

            self._cumulative_ops += quiver_count * 6
            self._cumulative_ops += active_count * 5

            total_step_sec = (self._last_step_ms + self._last_serialize_ms) / 1000.0
            est_flops = (total_sensors * 12 + quiver_count * 6 + active_count * 5) / max(total_step_sec, 1e-9)

            result = {
                "frame": int(self._frame),
                "gridSize": int(N),
                "sensors": {
                    # Flat array: [x0,y0,z0, x1,y1,z1, ...] — JS reagrupa de a 3
                    # Reduce ~35% overhead vs lista-de-listas en Python
                    "flat_positions": active_idx.flatten().tolist(),
                    "flat_colors": np.round(colors, 3).flatten().tolist(),
                    "flat_values":  np.round(values, 3).tolist(),  # valor de campo por nodo (para tooltips)
                    "count": int(active_count),
                },
                "quiver": {
                    "flat_positions":   q_pos.flatten().tolist(),
                    "flat_directions":  np.round(q_dir, 3).flatten().tolist(),
                    "count": int(quiver_count),
                },
                "stats": {
                    "totalSensors": int(total_sensors),
                    "activeSensors": int(active_count),
                    "damagedSensors": int(total_sensors - active_count),
                    "totalDamageEvents": int(self._total_damage_events),
                    "totalHealEvents": int(self._total_heal_events),
                    "fieldMean": float(np.mean(self._grid)),
                    "fieldStd": float(np.std(self._grid)),
                },
                "compute": {
                    "stepMs": float(round(self._last_step_ms, 2)),
                    "serializeMs": float(round(self._last_serialize_ms, 2)),
                    "totalMs": float(round(self._last_step_ms + self._last_serialize_ms, 2)),
                    "estFLOPS": int(round(est_flops)),
                    "cumulativeOps": int(self._cumulative_ops),
                    "opsPerFrame": int(total_sensors * 12 + quiver_count * 6 + active_count * 5),
                    "fieldEvals": int(total_sensors * 3),
                    "neighborLookups": int(np.sum(~self._sensors_active)) * 6,
                    "colormapCalcs": int(active_count * 3),
                    "quiverCalcs": int(quiver_count * 3),
                },
                "consumo": {
                    "energy_nw": float(round(self._cumulative_ops * 0.0000001, 4)),
                    "load_pct": float(round(min(100, (est_flops / 500000.0) * 100), 1)),
                    "field_stress": float(round(np.sum(~self._sensors_active) * 1.5 + np.mean(np.abs(self._grid)) * 10, 2)),
                    "sync_level": "OPTIMAL" if active_count / total_sensors > 0.9 else "DEGRADED",
                    "cpu_usage": psutil.cpu_percent() if psutil else float(round(min(100, (est_flops / 1000000.0) * 80), 1)),
                    "ram_usage": psutil.virtual_memory().percent if psutil else 42.5,
                    "gpu_load": float(round(min(100, (total_sensors / 32768.0) * 90 + random.uniform(0, 5)), 1))
                },
                "quantum": self.quantum_injector.get_telemetry() if self.quantum_injector else {},
                "status": "HEALING ACTIVADO" if self._healed_this_frame else "PROCESANDO GALÁCTICO",
            }

            return _sanitize_for_json(result)

        except Exception as e:
            print(f"❌ [NokkaSimulation] Error crítico en get_state() frame#{self._frame}: {e}")
            raise

    def update_config(self, new_config: dict):
        """Update simulation configuration in real-time."""
        with self._lock:
            try:
                old_grid_size = self.config.grid_size
                changed_fields = []

                if "grid_size" in new_config:
                    val = int(new_config["grid_size"])
                    if val != self.config.grid_size:
                        self.config.grid_size = val
                        changed_fields.append(f"grid_size={val}")

                if "wave_speed" in new_config:
                    val = float(new_config["wave_speed"])
                    self.config.wave_speed = val
                    changed_fields.append(f"wave_speed={val:.3f}")

                # FIX: el frontend envía 'noise_level', mapeamos a noise_std
                noise_val = new_config.get("noise_level") or new_config.get("noise_std")
                if noise_val is not None:
                    val = float(noise_val)
                    self.config.noise_std = val
                    changed_fields.append(f"noise_std={val:.3f}")

                # Quantum TLS config (v2.7)
                if self.quantum_injector and ("tls_switch_rate" in new_config or "tls_max_factor" in new_config):
                    self.quantum_injector.update_config(new_config)

                if changed_fields:
                    print(f"⚙️  [NokkaSimulation] update_config: {' | '.join(changed_fields)}")

                # Re-initialize if grid size changed
                if self.config.grid_size != old_grid_size:
                    self._init_simulation()
                    print(f"📐 [NokkaSimulation] Grid redimensionado: "
                          f"{old_grid_size}³ → {self.config.grid_size}³ "
                          f"({self.config.grid_size**3} nodos)")

            except Exception as e:
                print(f"❌ [NokkaSimulation] Error en update_config: {e} | data={new_config}")

    # ─── Properties ──────────────────────────────────────────

    @property
    def frame(self) -> int:
        return self._frame

    @property
    def is_running(self) -> bool:
        return self._running

    @is_running.setter
    def is_running(self, value: bool):
        prev = self._running
        self._running = value
        if prev != value:
            icon = "▶️ " if value else "⏸️ "
            print(f"{icon} [NokkaSimulation] is_running: {prev} → {value}")
