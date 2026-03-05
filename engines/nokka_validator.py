#!/usr/bin/env python3
import numpy as np
import time

def loocv_fast(X, y, alpha=100.0):
    """Fast analytic LOOCV for Kernel Ridge."""
    N = len(y)
    try:
        K = X @ X.T
        C = K + alpha * np.eye(N)
        C_inv = np.linalg.inv(C)
        errors_loo = (C_inv @ y) / np.diag(C_inv)
        y_pred_loocv = y - errors_loo
        return (y_pred_loocv >= 0.5).astype(int)
    except np.linalg.LinAlgError:
        print("⚠️  [loocv_fast] Singular matrix encountered. Returning zeros fallback.")
        return np.zeros(N, dtype=int)

def run_rc_validation(n_samples=1000, grid_size=12, progress_cb=None):
    """Runs a full vectorized RC validation suite and returns metrics."""
    t0 = time.perf_counter()
    N = grid_size
    transient = 50
    alpha = 100.0
    
    # 1. Dataset Generation
    np.random.seed(42)
    y_true = np.zeros(n_samples, dtype=np.int32)
    y_true[n_samples//2:] = 1 
    
    features = np.zeros((n_samples, 5), dtype=np.float32)
    # Orgánicos
    features[:n_samples//2, 0] = np.random.uniform(0.1, 8.0, n_samples//2)
    features[:n_samples//2, 1] = np.random.uniform(1.0, 10.0, n_samples//2)
    features[:n_samples//2, 2] = np.random.uniform(0.5, 0.9, n_samples//2)
    features[:n_samples//2, 3] = (np.random.rand(n_samples//2) < 0.1).astype(np.float32)
    features[:n_samples//2, 4] = (np.random.rand(n_samples//2) < 0.1).astype(np.float32)
    # Bots
    features[n_samples//2:, 0] = np.random.uniform(20.0, 100.0, n_samples//2)
    features[n_samples//2:, 1] = np.random.uniform(0.01, 0.2, n_samples//2)
    features[n_samples//2:, 2] = np.random.uniform(0.05, 0.3, n_samples//2)
    features[n_samples//2:, 3] = (np.random.rand(n_samples//2) < 0.8).astype(np.float32)
    features[n_samples//2:, 4] = (np.random.rand(n_samples//2) < 0.8).astype(np.float32)
    
    y_rb = ((features[:, 3] == 1) | (features[:, 4] == 1) | 
            ((features[:, 1] < 0.1) & (features[:, 0] > 20))).astype(np.int32)

    # 2. Vectorized Simulation
    mask = np.random.uniform(-1, 1, size=(5, N, N, N)).astype(np.float32)
    phases = (features @ mask.reshape(5, -1)).reshape(n_samples, N, N, N) * 2.0
    grids = np.zeros((n_samples, N, N, N), dtype=np.float32)
    
    x, y_coord, z = np.meshgrid(np.arange(N,dtype=np.float32),
                                 np.arange(N,dtype=np.float32),
                                 np.arange(N,dtype=np.float32), indexing='ij')

    from scipy.ndimage import convolve
    kernel = np.ones((3, 3, 3), dtype=np.float32) / 26.0
    kernel[1, 1, 1] = -1.0
    kernel_4d = kernel.reshape(1, 3, 3, 3)
    
    dt = 0.1
    lambda_neg = 0.21
    D = 0.15
    beta = 5.0

    history = []
    for t in range(transient + 3):
        phases += 0.15
        noise = np.random.normal(0, 0.08, grids.shape).astype(np.float32)
        
        theta_ancestral = (
            0.8 * np.sin(x*0.6 + phases) * np.cos(y_coord*0.4 + phases*0.7) +
            0.3 * np.sin(z*1.1 + t*0.08)
        ).astype(np.float32)
        
        laplacian = convolve(grids, kernel_4d, mode='wrap')
        H = grids**2
        rejection_factor = np.exp(-beta * H)
        means = grids.mean(axis=(1,2,3), keepdims=True)
        
        dtheta = (
            -lambda_neg * grids + 
            D * laplacian + 
            rejection_factor * (theta_ancestral - means) +
            noise
        )
        
        grids += dt * dtheta
        grids = np.clip(grids, -2.5, 2.5)
        
        if t >= transient:
            history.append(grids.reshape(n_samples, -1).copy())
        
        if progress_cb and t % 10 == 0:
            progress_cb(int((t / (transient + 3)) * 80))

    # 3. Readout & LOOCV
    X = np.concatenate(history, axis=1).astype(np.float64)
    mu = X.mean(0); sd = X.std(0) + 1e-8
    Xn = (X - mu) / sd
    Xn_bias = np.hstack([np.ones((Xn.shape[0], 1)), Xn])

    if progress_cb: progress_cb(90)
    
    acc_rule = np.mean(y_true == y_rb)
    y_pred_loocv = loocv_fast(Xn_bias, y_true.astype(np.float64), alpha)
    acc_loocv = np.mean(y_true == y_pred_loocv)
    
    y_rand = np.random.permutation(y_true)
    acc_random = np.mean(y_rand == loocv_fast(Xn_bias, y_rand.astype(np.float64), alpha))

    return {
        "acc_rule": float(acc_rule),
        "acc_rc": float(acc_loocv),
        "acc_random": float(acc_random),
        "delta": float(acc_loocv - acc_rule),
        "time_ms": int((time.perf_counter() - t0) * 1000),
        "n_samples": n_samples
    }
