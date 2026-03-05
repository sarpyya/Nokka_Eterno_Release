#!/usr/bin/env python3
"""
=================================================================
  NOKKA EVOLUTIONARY BENCHMARK v1.0
  Formal Dynamic Profile for Reservoir Computing Architectures
  -----------------------------------------------------------------
  Metrics:
    1. Eigenvalue Spectrum (spectral radius, effective dim)
    2. Maximum Lyapunov Exponent (chaos regime)
    3. Memory Horizon (fading memory)
    4. Perturbation Sensitivity (input separation)
    5. Linear Separability (Fisher discriminant + LOOCV)
  -----------------------------------------------------------------
  Usage:  python benchmark_evolution.py
  Output: benchmark_results/profile_<tag>.json + console report
=================================================================
"""

import numpy as np
import time
import json
import os
import sys

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
GRID        = 12         # Reservoir grid size (N^3 nodes)
N_TRIALS    = 10         # Independent seeds for variance estimation
N_FRAMES    = 100        # Simulation frames per trial
N_SAMPLES   = 500        # Samples for separability test
WAVE_SPEED  = 0.15       # Phase increment per frame
NOISE_STD   = 0.08       # Gaussian noise amplitude
ALPHA_RIDGE = 100.0      # Ridge regularization for LOOCV
ARCH_TAG    = "nokka_v27" # Architecture label for output file

OUTPUT_DIR  = "benchmark_results"

# ---------------------------------------------------------------------------
# Reservoir Core (Vectorized, matching nokka_eterno field dynamics)
# ---------------------------------------------------------------------------
def _make_grid_coords(N):
    """Pre-compute static grid coordinates."""
    return np.meshgrid(
        np.arange(N, dtype=np.float32),
        np.arange(N, dtype=np.float32),
        np.arange(N, dtype=np.float32),
        indexing='ij'
    )

def _evolve_step(phase, grid, x, y, z, t, noise_std=NOISE_STD):
    """One step of Nokka PDE evolution (Newen vs Horror)."""
    phase += WAVE_SPEED
    
    dt = 0.1
    lambda_neg = 0.21
    D = 0.15
    beta = 5.0
    
    theta_ancestral = (
        0.8 * np.sin(x * 0.6 + phase) * np.cos(y * 0.4 + phase * 0.7) +
        0.3 * np.sin(z * 1.1 + t * 0.08)
    )
    
    laplacian = (
        np.roll(grid, 1, axis=0) + np.roll(grid, -1, axis=0) +
        np.roll(grid, 1, axis=1) + np.roll(grid, -1, axis=1) +
        np.roll(grid, 1, axis=2) + np.roll(grid, -1, axis=2) -
        6.0 * grid
    )
    
    H = grid**2
    rejection_factor = np.exp(-beta * H)
    noise = np.random.normal(0, noise_std, grid.shape).astype(np.float32)
    
    dtheta = (
        -lambda_neg * grid +
        D * laplacian +
        rejection_factor * (theta_ancestral - grid.mean()) +
        noise
    )
    
    grid += dt * dtheta
    grid = np.clip(grid, -2.5, 2.5)
    
    return phase, grid


def _run_reservoir(N, n_frames, seed, initial_perturbation=None):
    """Run reservoir for n_frames, return trajectory (n_frames x N^3)."""
    np.random.seed(seed)
    x, y, z = _make_grid_coords(N)
    phase = np.random.uniform(0, 2 * np.pi, (N, N, N)).astype(np.float32)
    grid  = np.zeros((N, N, N), dtype=np.float32)

    if initial_perturbation is not None:
        phase += initial_perturbation

    trajectory = np.zeros((n_frames, N**3), dtype=np.float32)
    for t in range(n_frames):
        phase, grid = _evolve_step(phase, grid, x, y, z, t)
        trajectory[t] = grid.ravel()

    return trajectory


# ═══════════════════════════════════════════════════════════════════
# METRIC 1: Eigenvalue Spectrum
# ═══════════════════════════════════════════════════════════════════
def measure_eigenvalue_spectrum(N, n_frames, seed):
    """Compute eigenvalue spectrum of reservoir state covariance."""
    traj = _run_reservoir(N, n_frames, seed)

    # Center the trajectory
    traj -= traj.mean(axis=0)

    # Compute covariance using np.cov for numerical stability + bias=True to match population covariance
    C = np.cov(traj.T, bias=True)
    
    eigvals = np.linalg.eigvalsh(C)[::-1]  # Descending

    spectral_radius = float(eigvals[0])
    total_var = eigvals.sum()
    cumulative  = np.cumsum(eigvals) / (total_var + 1e-12)
    effective_dim = int(np.searchsorted(cumulative, 0.95) + 1)

    # Decay rate: fit log(eigenvalue) ~ slope * index
    valid = eigvals > 1e-10
    if valid.sum() > 2:
        indices = np.arange(valid.sum())
        log_eig = np.log(eigvals[valid])
        slope = np.polyfit(indices, log_eig, 1)[0]
    else:
        slope = 0.0

    return {
        "spectral_radius": spectral_radius,
        "effective_dim": effective_dim,
        "total_dims": N**3,
        "decay_rate": float(slope),
        "top_10_eigenvalues": eigvals[:10].tolist()
    }


# ═══════════════════════════════════════════════════════════════════
# METRIC 2: Maximum Lyapunov Exponent
# ═══════════════════════════════════════════════════════════════════
def measure_lyapunov(N, n_frames, seed, delta0=1e-8):
    """Estimate maximum Lyapunov exponent via twin trajectory divergence."""
    # Trajectory A: unperturbed
    traj_A = _run_reservoir(N, n_frames, seed)

    # Trajectory B: perturbed initial state
    perturbation = np.random.RandomState(seed + 9999).normal(0, delta0, (N, N, N)).astype(np.float32)
    traj_B = _run_reservoir(N, n_frames, seed, initial_perturbation=perturbation)

    # Divergence over time
    divergence = np.linalg.norm(traj_A - traj_B, axis=1)
    divergence = np.maximum(divergence, 1e-30)  # Avoid log(0)

    # Compute local Lyapunov exponents
    log_div = np.log(divergence)
    # lambda_max ~ slope of log(divergence) vs time
    t_axis = np.arange(n_frames)
    
    if n_frames > 10:
        slope, intercept = np.polyfit(t_axis[10:], log_div[10:], 1)
    else:
        slope, intercept = np.polyfit(t_axis, log_div, 1)

    # Classify regime
    if slope > 0.01:
        regime = "CHAOTIC"
    elif slope > -0.01:
        regime = "EDGE-OF-CHAOS"
    else:
        regime = "ORDERED"

    return {
        "lambda_max": float(slope),
        "regime": regime,
        "initial_divergence": float(divergence[0]),
        "final_divergence": float(divergence[-1]),
        "divergence_curve": divergence[::max(1, n_frames//20)].tolist()
    }


# ═══════════════════════════════════════════════════════════════════
# METRIC 3: Memory Horizon
# ═══════════════════════════════════════════════════════════════════
def measure_memory_horizon(N, n_frames, seed, epsilon_ratio=0.01):
    """How many frames until an impulse perturbation fades below epsilon."""
    # Baseline trajectory
    traj_base = _run_reservoir(N, n_frames, seed)

    # Impulse: strong localized perturbation at t=0
    impulse = np.zeros((N, N, N), dtype=np.float32)
    center = N // 2
    impulse[center-1:center+2, center-1:center+2, center-1:center+2] = 1.0
    traj_impulse = _run_reservoir(N, n_frames, seed, initial_perturbation=impulse)

    # Echo magnitude over time
    echo = np.linalg.norm(traj_impulse - traj_base, axis=1)
    initial_echo = echo[0] if echo[0] > 1e-10 else 1.0
    epsilon = initial_echo * epsilon_ratio

    # Find first frame where echo drops below epsilon
    below = np.where(echo < epsilon)[0]
    tau_memory = int(below[0]) if len(below) > 0 else n_frames

    # Quality assessment
    if tau_memory > n_frames * 0.5:
        quality = "LONG (strong fading memory)"
    elif tau_memory > n_frames * 0.2:
        quality = "GOOD"
    elif tau_memory > n_frames * 0.05:
        quality = "SHORT"
    else:
        quality = "NEGLIGIBLE"

    return {
        "tau_memory_frames": tau_memory,
        "initial_echo": float(initial_echo),
        "final_echo": float(echo[-1]),
        "quality": quality,
        "echo_curve": echo[::max(1, n_frames//20)].tolist()
    }


# ═══════════════════════════════════════════════════════════════════
# METRIC 4: Perturbation Sensitivity
# ═══════════════════════════════════════════════════════════════════
def measure_perturbation_sensitivity(N, n_frames, seed):
    """Response curve: how final state diverges as initial perturbation varies."""
    deltas = [1e-8, 1e-6, 1e-4, 1e-2, 1e-1]
    traj_base = _run_reservoir(N, n_frames, seed)
    final_base = traj_base[-1]

    responses = []
    for delta in deltas:
        pert = np.random.RandomState(seed + 7777).normal(0, delta, (N, N, N)).astype(np.float32)
        traj_p = _run_reservoir(N, n_frames, seed, initial_perturbation=pert)
        divergence = float(np.linalg.norm(traj_p[-1] - final_base))
        responses.append(divergence)

    # Linearity score: correlation between log(delta) and log(response)
    log_d = np.log10(deltas)
    log_r = np.log10(np.maximum(responses, 1e-30))
    if np.std(log_r) > 1e-10:
        corr = float(np.corrcoef(log_d, log_r)[0, 1])
    else:
        corr = 0.0

    return {
        "deltas": deltas,
        "responses": responses,
        "linearity_score": corr,
        "sensitivity_at_1e-8": responses[0],
        "sensitivity_at_1e-2": responses[3]
    }


# ═══════════════════════════════════════════════════════════════════
# METRIC 5: Linear Separability (Fisher Discriminant + LOOCV)
# ═══════════════════════════════════════════════════════════════════
def _loocv_fast(X, y, alpha=ALPHA_RIDGE):
    """Analytic LOOCV for Kernel Ridge Regression."""
    K = X @ X.T
    C = K + alpha * np.eye(len(y))
    C_inv = np.linalg.inv(C)
    errors = (C_inv @ y) / np.diag(C_inv)
    return (y - errors >= 0.5).astype(int)


def _generate_bot_dataset(n):
    """Generate synthetic bot/organic feature dataset."""
    y = np.zeros(n, dtype=np.int32)
    y[n//2:] = 1
    feats = np.zeros((n, 5), dtype=np.float32)

    # Organic
    feats[:n//2, 0] = np.random.uniform(0.1, 8.0, n//2)
    feats[:n//2, 1] = np.random.uniform(1.0, 10.0, n//2)
    feats[:n//2, 2] = np.random.uniform(0.5, 0.9, n//2)
    feats[:n//2, 3] = (np.random.rand(n//2) < 0.1).astype(np.float32)
    feats[:n//2, 4] = (np.random.rand(n//2) < 0.1).astype(np.float32)

    # Bots
    feats[n//2:, 0] = np.random.uniform(20.0, 100.0, n//2)
    feats[n//2:, 1] = np.random.uniform(0.01, 0.2, n//2)
    feats[n//2:, 2] = np.random.uniform(0.05, 0.3, n//2)
    feats[n//2:, 3] = (np.random.rand(n//2) < 0.8).astype(np.float32)
    feats[n//2:, 4] = (np.random.rand(n//2) < 0.8).astype(np.float32)

    y_rb = ((feats[:, 3] == 1) | (feats[:, 4] == 1) |
            ((feats[:, 1] < 0.1) & (feats[:, 0] > 20))).astype(np.int32)

    return feats, y, y_rb


def measure_linear_separability(N, n_samples, seed, transient=50):
    """Fisher Discriminant Ratio + LOOCV accuracy through reservoir."""
    np.random.seed(seed)
    feats, y_true, y_rb = _generate_bot_dataset(n_samples)

    # Input masking (project features into reservoir space)
    mask = np.random.uniform(-1, 1, size=(5, N, N, N)).astype(np.float32)
    phases = (feats @ mask.reshape(5, -1)).reshape(n_samples, N, N, N) * 2.0
    grids  = np.zeros((n_samples, N, N, N), dtype=np.float32)

    x, y_c, z = _make_grid_coords(N)

    # Evolve reservoir in batch
    history = []
    for t in range(transient + 3):
        phases += WAVE_SPEED
        term1 = 0.8 * np.sin(x * 0.6 + phases) * np.cos(y_c * 0.4 + phases * 0.7)
        term2 = 0.3 * np.sin(z * 1.1 + t * 0.08)
        grids[:] = term1 + term2 + np.random.normal(0, NOISE_STD, grids.shape).astype(np.float32)
        if t >= transient:
            history.append(grids.reshape(n_samples, -1).copy())

    # State matrix
    X = np.concatenate(history, axis=1).astype(np.float64)
    mu = X.mean(0); sd = X.std(0) + 1e-8
    Xn = (X - mu) / sd
    Xn_bias = np.hstack([np.ones((Xn.shape[0], 1)), Xn])

    # Fisher Discriminant Ratio (on first 100 principal dims for efficiency)
    from_class0 = Xn[y_true == 0]
    from_class1 = Xn[y_true == 1]
    mu0 = from_class0.mean(axis=0)
    mu1 = from_class1.mean(axis=0)
    var0 = from_class0.var(axis=0)
    var1 = from_class1.var(axis=0)
    denom = var0 + var1 + 1e-12
    fisher_per_dim = (mu0 - mu1) ** 2 / denom
    fisher_ratio = float(np.mean(np.sort(fisher_per_dim)[-100:]))  # Top 100 dims

    # LOOCV accuracy
    acc_rule = float(np.mean(y_true == y_rb))
    y_pred = _loocv_fast(Xn_bias, y_true.astype(np.float64))
    acc_rc = float(np.mean(y_true == y_pred))

    # Sanity check
    y_rand = np.random.permutation(y_true)
    acc_random = float(np.mean(y_rand == _loocv_fast(Xn_bias, y_rand.astype(np.float64))))

    return {
        "fisher_ratio": fisher_ratio,
        "loocv_accuracy": acc_rc,
        "rule_based_accuracy": acc_rule,
        "random_accuracy": acc_random,
        "delta_vs_rule": acc_rc - acc_rule,
        "state_dims": X.shape[1]
    }


# ═══════════════════════════════════════════════════════════════════
# MULTI-TRIAL RUNNER
# ═══════════════════════════════════════════════════════════════════
def _stats(values):
    """Compute mean +/- std from a list of floats."""
    arr = np.array(values)
    return {"mean": float(arr.mean()), "std": float(arr.std()), "values": values}


def benchmark_evolution(grid_size=GRID, n_trials=N_TRIALS, n_frames=N_FRAMES,
                        n_samples=N_SAMPLES, arch_tag=ARCH_TAG):
    """Run the full 5-metric benchmark across multiple seeds."""

    print("=" * 64)
    print("  NOKKA EVOLUTIONARY BENCHMARK v1.0")
    print(f"  Architecture: {arch_tag}")
    print(f"  Grid: {grid_size}^3 ({grid_size**3} nodes) | "
          f"Trials: {n_trials} | Frames: {n_frames}")
    print("=" * 64)

    results = {
        "architecture": arch_tag,
        "grid_size": grid_size,
        "n_trials": n_trials,
        "n_frames": n_frames,
        "n_samples": n_samples,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "metrics": {}
    }

    base_seeds = list(range(42, 42 + n_trials))

    # ── Metric 1: Eigenvalue Spectrum ──────────────────────────
    print(f"\n  [1/5] EIGENVALUE SPECTRUM ({n_trials} trials)...")
    t0 = time.perf_counter()
    eig_results = [measure_eigenvalue_spectrum(grid_size, n_frames, s) for s in tqdm(base_seeds, desc="Eig")]
    spectral_radii = [r["spectral_radius"] for r in eig_results]
    eff_dims       = [r["effective_dim"] for r in eig_results]
    decay_rates    = [r["decay_rate"] for r in eig_results]

    results["metrics"]["eigenvalue_spectrum"] = {
        "spectral_radius": _stats(spectral_radii),
        "effective_dim": _stats(eff_dims),
        "decay_rate": _stats(decay_rates),
    }
    sr = results["metrics"]["eigenvalue_spectrum"]
    print(f"        Spectral Radius    : {sr['spectral_radius']['mean']:.2f} "
          f"+/- {sr['spectral_radius']['std']:.2f}")
    print(f"        Effective Dim      : {sr['effective_dim']['mean']:.0f}/{grid_size**3} "
          f"({sr['effective_dim']['mean']/grid_size**3*100:.1f}%)")
    print(f"        Decay Rate         : {sr['decay_rate']['mean']:.4f}")
    print(f"        [{time.perf_counter()-t0:.1f}s]")

    # ── Metric 2: Lyapunov Exponent ────────────────────────────
    print(f"\n  [2/5] LYAPUNOV EXPONENT ({n_trials} trials)...")
    t0 = time.perf_counter()
    lyap_results = [measure_lyapunov(grid_size, n_frames, s) for s in tqdm(base_seeds, desc="Lyap")]
    lambdas = [r["lambda_max"] for r in lyap_results]
    regimes = [r["regime"] for r in lyap_results]

    results["metrics"]["lyapunov"] = {
        "lambda_max": _stats(lambdas),
        "dominant_regime": max(set(regimes), key=regimes.count),
        "regime_counts": {r: regimes.count(r) for r in set(regimes)}
    }
    lm = results["metrics"]["lyapunov"]
    print(f"        lambda_max         : {lm['lambda_max']['mean']:.6f} "
          f"+/- {lm['lambda_max']['std']:.6f}")
    print(f"        Regime             : {lm['dominant_regime']}")
    print(f"        [{time.perf_counter()-t0:.1f}s]")

    # ── Metric 3: Memory Horizon ───────────────────────────────
    print(f"\n  [3/5] MEMORY HORIZON ({n_trials} trials)...")
    t0 = time.perf_counter()
    mem_results = [measure_memory_horizon(grid_size, n_frames, s) for s in tqdm(base_seeds, desc="Mem")]
    taus     = [r["tau_memory_frames"] for r in mem_results]
    qualities = [r["quality"] for r in mem_results]

    results["metrics"]["memory_horizon"] = {
        "tau_memory": _stats(taus),
        "dominant_quality": max(set(qualities), key=qualities.count)
    }
    mh = results["metrics"]["memory_horizon"]
    print(f"        tau_memory         : {mh['tau_memory']['mean']:.1f} "
          f"+/- {mh['tau_memory']['std']:.1f} frames")
    print(f"        Fading Quality     : {mh['dominant_quality']}")
    print(f"        [{time.perf_counter()-t0:.1f}s]")

    # ── Metric 4: Perturbation Sensitivity ─────────────────────
    print(f"\n  [4/5] PERTURBATION SENSITIVITY ({n_trials} trials)...")
    t0 = time.perf_counter()
    pert_results = [measure_perturbation_sensitivity(grid_size, n_frames, s) for s in tqdm(base_seeds, desc="Pert")]
    lin_scores = [r["linearity_score"] for r in pert_results]
    resp_small = [r["sensitivity_at_1e-8"] for r in pert_results]
    resp_large = [r["sensitivity_at_1e-2"] for r in pert_results]

    results["metrics"]["perturbation_sensitivity"] = {
        "linearity_score": _stats(lin_scores),
        "response_1e-8": _stats(resp_small),
        "response_1e-2": _stats(resp_large),
        "deltas": pert_results[0]["deltas"],
        "mean_responses": np.mean([r["responses"] for r in pert_results], axis=0).tolist()
    }
    ps = results["metrics"]["perturbation_sensitivity"]
    print(f"        Response at 1e-8   : {ps['response_1e-8']['mean']:.6f}")
    print(f"        Response at 1e-2   : {ps['response_1e-2']['mean']:.4f}")
    print(f"        Linearity Score    : {ps['linearity_score']['mean']:.3f}")
    print(f"        [{time.perf_counter()-t0:.1f}s]")

    # ── Metric 5: Linear Separability ──────────────────────────
    print(f"\n  [5/5] LINEAR SEPARABILITY ({n_trials} trials, {n_samples} samples)...")
    t0 = time.perf_counter()
    sep_results = [measure_linear_separability(grid_size, n_samples, s) for s in tqdm(base_seeds, desc="LinSep")]
    fishers   = [r["fisher_ratio"] for r in sep_results]
    acc_rcs   = [r["loocv_accuracy"] for r in sep_results]
    acc_rules = [r["rule_based_accuracy"] for r in sep_results]

    results["metrics"]["linear_separability"] = {
        "fisher_ratio": _stats(fishers),
        "loocv_accuracy": _stats(acc_rcs),
        "rule_based_accuracy": _stats(acc_rules),
        "delta_vs_rule": _stats([r["delta_vs_rule"] for r in sep_results])
    }
    ls = results["metrics"]["linear_separability"]
    print(f"        Fisher Ratio       : {ls['fisher_ratio']['mean']:.4f} "
          f"+/- {ls['fisher_ratio']['std']:.4f}")
    print(f"        LOOCV Accuracy     : {ls['loocv_accuracy']['mean']*100:.1f}% "
          f"+/- {ls['loocv_accuracy']['std']*100:.1f}%")
    print(f"        Rule-Based         : {ls['rule_based_accuracy']['mean']*100:.1f}%")
    print(f"        Delta (RC - Rule)  : {ls['delta_vs_rule']['mean']*100:+.1f}%")
    print(f"        [{time.perf_counter()-t0:.1f}s]")

    # ── Save Results ───────────────────────────────────────────
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    out_path = os.path.join(OUTPUT_DIR, f"profile_{arch_tag}.json")
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\n{'=' * 64}")
    print(f"  DYNAMIC PROFILE SAVED: {out_path}")
    print(f"{'=' * 64}")

    return results


# ═══════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    benchmark_evolution()
