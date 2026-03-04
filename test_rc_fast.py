#!/usr/bin/env python3
import numpy as np
import time

# ── Parámetros ──
GRID = 12
TRANSIENT = 50
ALPHA_RIDGE = 100.0
N_SAMPLES = 1000

# ── LOOCV Analítico para Kernel Ridge ──
def loocv_fast(X, y, alpha=1.0):
    N = len(y)
    K = X @ X.T
    C = K + alpha * np.eye(N)
    C_inv = np.linalg.inv(C)
    
    # y - y_hat_loo = (C_inv @ y) / diag(C_inv)
    errors_loo = (C_inv @ y) / np.diag(C_inv)
    y_pred_loocv = y - errors_loo
    
    return (y_pred_loocv >= 0.5).astype(int)

# ── Generación de Dataset Vectorizado ──
def generate_dataset_batch(n=1000):
    np.random.seed(42)
    # y: 0 para orgánicos, 1 para bots
    y = np.zeros(n, dtype=np.int32)
    y[n//2:] = 1 
    
    # Features matrix (freq, ratio, bio, kw, low)
    features = np.zeros((n, 5), dtype=np.float32)
    
    # Orgánicos
    features[:n//2, 0] = np.random.uniform(0.1, 8.0, n//2)  # freq
    features[:n//2, 1] = np.random.uniform(1.0, 10.0, n//2) # ratio
    features[:n//2, 2] = np.random.uniform(0.5, 0.9, n//2)  # bio
    features[:n//2, 3] = (np.random.rand(n//2) < 0.1).astype(np.float32) # kw
    features[:n//2, 4] = (np.random.rand(n//2) < 0.1).astype(np.float32) # low
    
    # Bots
    features[n//2:, 0] = np.random.uniform(20.0, 100.0, n//2)  # freq
    features[n//2:, 1] = np.random.uniform(0.01, 0.2, n//2)    # ratio
    features[n//2:, 2] = np.random.uniform(0.05, 0.3, n//2)    # bio
    features[n//2:, 3] = (np.random.rand(n//2) < 0.8).astype(np.float32) # kw
    features[n//2:, 4] = (np.random.rand(n//2) < 0.8).astype(np.float32) # low
    
    # Heurística Rule-Based para baseline
    y_rb = ((features[:, 3] == 1) | (features[:, 4] == 1) | 
            ((features[:, 1] < 0.1) & (features[:, 0] > 20))).astype(np.int32)
            
    return features, y, y_rb

# ── Ejecución de Test Vectorizado ──
def test_vectorized_generalization():
    print("=" * 65)
    print(f"  [TEST 4] Generalizacion LOOCV Vectorizada sobre {N_SAMPLES} muestras")
    print("=" * 65)
    
    t0 = time.perf_counter()
    N = GRID
    features, y_true, y_rb = generate_dataset_batch(N_SAMPLES)
    
    # 1. Proyección de Features (Input Masking)
    np.random.seed(42)
    MASK = np.random.uniform(-1, 1, size=(5, N, N, N)).astype(np.float32)
    
    # Inicializar estado del lote (Phases y Grids)
    # phases: (N_SAMPLES, N, N, N)
    phases = np.zeros((N_SAMPLES, N, N, N), dtype=np.float32)
    grids  = np.zeros((N_SAMPLES, N, N, N), dtype=np.float32)
    
    # Inyección: u_feats @ MASK
    # features: (1000, 5), MASK: (5, 1728) -> results: (1000, 1728)
    phases[:] = (features @ MASK.reshape(5, -1)).reshape(N_SAMPLES, N, N, N) * 2.0
    
    # Coordenadas estáticas (pre-calculadas)
    x, y_coord, z = np.meshgrid(np.arange(N,dtype=np.float32),
                                 np.arange(N,dtype=np.float32),
                                 np.arange(N,dtype=np.float32), indexing='ij')

    # 2. Simulación en Batch (Evolución de campo)
    print("  Evolucionando reservorio en paralelo (1000 muestras)...")
    
    history_frames = []
    
    for t in range(TRANSIENT + 3):
        phases += 0.15
        noise = np.random.normal(0, 0.08, grids.shape).astype(np.float32)
        
        # grids[:] = 0.8 * sin(x*0.6 + phase) * cos(y*0.4 + phase*0.7) + 0.3 * sin(z*1.1 + t*0.08)
        term1 = 0.8 * np.sin(x*0.6 + phases) * np.cos(y_coord*0.4 + phases*0.7)
        term2 = 0.3 * np.sin(z*1.1 + t*0.08)
        grids[:] = term1 + term2 + noise
        
        if t >= TRANSIENT:
            history_frames.append(grids.reshape(N_SAMPLES, -1).copy())

    # 3. Concatenación de Delay Embedding (3 frames -> 5184D)
    X = np.concatenate(history_frames, axis=1).astype(np.float64)
    
    # 4. Estandarización y Bias
    mu = X.mean(0); sd = X.std(0) + 1e-8
    Xn = (X - mu) / sd
    Xn_bias = np.hstack([np.ones((Xn.shape[0], 1)), Xn])

    # 5. Benchmarks
    acc_rule = np.mean(y_true == y_rb)
    
    # Predicción LOOCV Analítica (Veloz)
    y_pred_loocv = loocv_fast(Xn_bias, y_true.astype(np.float64), ALPHA_RIDGE)
    acc_loocv = np.mean(y_true == y_pred_loocv)
    
    # Sanity Check (Etiquetas barajadas)
    y_rand = np.random.permutation(y_true)
    y_pred_random = loocv_fast(Xn_bias, y_rand.astype(np.float64), ALPHA_RIDGE)
    acc_random = np.mean(y_rand == y_pred_random)

    t_end = time.perf_counter()
    print(f"  Ejecucion completada en {t_end-t0:.2f}s")
    print(f"\n  [RESULTADOS] DE GENERALIZACION (LOOCV)")
    print(f"     Algoritmo Rule-Based (Heuristica) : {acc_rule*100:6.1f}%")
    print(f"     RC Readout (LOOCV Estricto)       : {acc_loocv*100:6.1f}%  <-- Metrica Real")
    print(f"     Sanity Check (Etiquetas Random)   : {acc_random*100:6.1f}%")

    delta = acc_loocv - acc_rule
    print(f"\n  [DELTA] RC vs Heuristica: {delta*100:+.1f}%")

    if acc_loocv > acc_rule and acc_random < 0.65:
        print(f"\n  [VEREDICTO] SUPERIORIDAD DEMOSTRADA")
        print(f"     El reservorio logra extraer patrones latentes que la heuristica ignora.")
    else:
        print(f"\n  [VEREDICTO] SIN VENTAJA CLARA")
        print(f"     El RC no logra batir a la heuristica basica en generalizacion.")

if __name__ == "__main__":
    test_vectorized_generalization()
