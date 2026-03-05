#!/usr/bin/env python3
"""
⚛️ QUANTUM TLS INJECTOR v2.7 — Nokka Eterno
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Simula fluctuaciones TLS telegráficas en T₁ de qubits
superconductores, basado en arXiv:2506.09576 (Phys. Rev. X 2026).

T₁ switches ×10 en decenas de ms, TLS switching hasta 10 Hz,
Bayesian estimation adaptativa (Kalman-like para CPU real-time).

Módulo standalone: se integra en NokkaSimulation._evolve_field().
"""

import numpy as np
from collections import deque


class QuantumTLSInjector:
    """
    Inyector de decoherencia cuántica TLS (Two-Level System) telegráfica.

    Simula:
    - Fluctuaciones telegráficas de γ = 1/T₁ por nodo del grid 3D
    - Tracker bayesiano adaptativo (Kalman-like) para estimar γ en real-time
    - Telemetría para frontend: T₁ avg, switches/frame, uncertainty

    Parámetros del paper:
    - T₁ base ~0.17 ms (γ_base ≈ 5.88 /ms)
    - Switches ×10 en decenas de ms
    - TLS switching rate ~0.1–10 Hz
    """

    def __init__(self, grid_size: int = 12, switch_rate: float = 0.1,
                 max_switch_factor: float = 10.0):
        self.grid_size = grid_size
        self.N = grid_size ** 3

        # ── Parámetros físicos (paper) ──
        self.base_t1_ms = 0.17                          # T₁ promedio paper
        self.base_gamma = 1.0 / self.base_t1_ms         # γ = 1/T₁ ≈ 5.88
        self.switch_rate = switch_rate                   # Hz (0.01–10)
        self.max_factor = max_switch_factor              # ×3–×15

        # ── Estado del campo γ (3D grid) ──
        shape = (grid_size, grid_size, grid_size)
        self.gamma = np.full(shape, self.base_gamma, dtype=np.float32)

        # ── Bayesian tracker por nodo (posterior gaussiano) ──
        self.posterior_mean = self.gamma.copy()
        self.posterior_var = np.ones(shape, dtype=np.float32) * 0.05
        self.measurement_noise = 0.02

        # ── Telemetría ──
        self.tau = 0.0                               # tiempo simulado (ms)
        self._switches_this_frame = 0
        self._total_switches = 0

        # ── Trace T₁ de un nodo centrado (para gráfico frontend) ──
        center = grid_size // 2
        self._trace_coord = (center, center, center)
        self._t1_trace = deque(maxlen=120)  # últimos 120 frames (~2s @60fps)

        print(f"[QuantumTLS] Inicializado -- grid={grid_size}^3 | "
              f"T1_base={self.base_t1_ms}ms | switch_rate={switch_rate}Hz | "
              f"max_factor=x{max_switch_factor}")

    def step(self, dt_ms: float = 60.0):
        """
        Avanza un frame cuántico.

        Args:
            dt_ms: Duración del frame en ms (~60ms para 16 FPS)

        Returns:
            tuple: (gamma, posterior_mean, posterior_var, switches_count)
        """
        self.tau += dt_ms

        # ── 1. Telegraphic Switching (exacto como paper) ──
        # Probabilidad de switch por nodo en este dt
        switch_prob = self.switch_rate * dt_ms / 1000.0  # rate en Hz, dt en ms
        mask = np.random.rand(*self.gamma.shape) < switch_prob

        n_switches = int(mask.sum())
        if n_switches > 0:
            # Cada nodo que switchea multiplica su γ por factor o 1/factor
            factors = np.random.choice(
                [1.0 / self.max_factor, self.max_factor],
                size=n_switches
            ).astype(np.float32)
            self.gamma[mask] *= factors

            # Clamp γ para evitar explosión numérica
            np.clip(self.gamma, self.base_gamma * 0.01,
                    self.base_gamma * self.max_factor * 2.0,
                    out=self.gamma)

        self._switches_this_frame = n_switches
        self._total_switches += n_switches

        # ── 2. Bayesian Update (Kalman-like, real-time) ──
        # Medición ruidosa de relajación observada
        observed = self.gamma + np.random.normal(
            0, self.measurement_noise, self.gamma.shape
        ).astype(np.float32)

        # Kalman gain
        K = self.posterior_var / (self.posterior_var + self.measurement_noise ** 2)
        self.posterior_mean += K * (observed - self.posterior_mean)
        self.posterior_var *= (1.0 - K)

        # Prevenir varianza de colapsar a cero (process noise)
        process_noise = 0.001 * switch_prob
        self.posterior_var += process_noise

        # ── 3. T₁ trace del nodo central ──
        c = self._trace_coord
        t1_center = 1.0 / max(self.gamma[c], 1e-6)
        self._t1_trace.append(float(t1_center))

        return self.gamma, self.posterior_mean, self.posterior_var, n_switches

    def get_damage_probability(self) -> np.ndarray:
        """
        Calcula probabilidad de daño cuántico por nodo.
        T₁ bajo → más probable daño catastrófico.

        Returns:
            ndarray: Probabilidad de daño [0, 1] por nodo
        """
        t1 = 1.0 / np.maximum(self.gamma, 1e-6)
        # Normalizar: T₁ < base → daño proporcional
        damage_prob = np.clip(1.0 - (t1 / self.base_t1_ms), 0.0, 0.8)
        return damage_prob

    def get_healing_strength(self) -> np.ndarray:
        """
        Calcula multiplicador de healing basado en incertidumbre bayesiana.
        Incertidumbre alta → healing más fuerte (principio bayesiano negativo).

        Returns:
            ndarray: Multiplicador de healing [0.5, 2.0] por nodo
        """
        return np.clip(1.0 / (1.0 + self.posterior_var * 10.0), 0.5, 2.0)

    def get_telemetry(self) -> dict:
        """
        Retorna telemetría cuántica para el frontend.
        """
        t1_grid = 1.0 / np.maximum(self.gamma, 1e-6)
        mean_uncertainty = float(np.mean(self.posterior_var))

        return {
            "t1_avg_ms": float(np.mean(t1_grid)),
            "t1_min_ms": float(np.min(t1_grid)),
            "t1_max_ms": float(np.max(t1_grid)),
            "switches_frame": int(self._switches_this_frame),
            "switches_total": int(self._total_switches),
            "uncertainty": float(mean_uncertainty),
            "robustness": float(1.0 - min(1.0, mean_uncertainty)),
            "t1_trace": list(self._t1_trace),
            "tau_ms": float(self.tau),
            "switch_rate": float(self.switch_rate),
            "max_factor": float(self.max_factor),
        }

    def get_t1_color_weights(self) -> np.ndarray:
        """
        Retorna peso de color rojo por nodo basado en T₁ bajo.
        0.0 = normal, 1.0 = T₁ mínimo (rojo pulsátil).

        Returns:
            ndarray (N,N,N): Peso de sombra cuántica [0, 1]
        """
        t1 = 1.0 / np.maximum(self.gamma, 1e-6)
        # Normalizar inversamente al ratio T₁/T₁_base
        weight = np.clip(1.0 - (t1 / (self.base_t1_ms * 2.0)), 0.0, 1.0)
        return weight.astype(np.float32)

    def update_config(self, data: dict):
        """Actualiza parámetros TLS en runtime desde sliders."""
        changed = []
        if "tls_switch_rate" in data:
            val = max(0.01, min(10.0, float(data["tls_switch_rate"])))
            self.switch_rate = val
            changed.append(f"switch_rate={val:.2f}Hz")
        if "tls_max_factor" in data:
            val = max(3.0, min(15.0, float(data["tls_max_factor"])))
            self.max_factor = val
            changed.append(f"max_factor=×{val:.1f}")
        if changed:
            print(f"[QuantumTLS] Config actualizada: {' | '.join(changed)}")
