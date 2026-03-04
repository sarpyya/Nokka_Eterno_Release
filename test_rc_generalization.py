#!/usr/bin/env python3
"""
🌌 NOKKA ETERNO — Reservoir Generalization Validation
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Evaluación RC estricta (LOOCV, Dummy Baseline, Sanity Checks)
Sin dependencias externas (100% numpy).

python test_rc_generalization.py
"""
import io, contextlib, sys, os, time, hashlib
import numpy as np

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from engines.nokka_eterno import NokkaSimulation, SimulationConfig

@contextlib.contextmanager
def _quiet():
    with contextlib.redirect_stdout(io.StringIO()):
        yield

def _sim(cfg):
    with _quiet(): return NokkaSimulation(cfg)

def _step(sim):
    with _quiet(): return sim.step()

# ── Parámetros de la Evaluación Estricta ──
GRID        = 12
TRANSIENT   = 50
ALPHA_RIDGE = 100.0   # Mayor regularización para combatir 5184D
SEP = "─" * 70
def header(t): print(f"\n{SEP}\n  🧪 {t}\n{SEP}")

def ridge_fit(X, y, alpha=1.0):
    # D >> N  (Dimensionalidad inmensa, pocas muestras)
    # Usar Dual Ridge Regression (Kernel Lineal / Identidad de Woodbury)
    # w = X^T (X X^T + alpha * I_N)^-1 y
    N_samples = X.shape[0]
    K = X @ X.T + alpha * np.eye(N_samples)
    dual_coefs = np.linalg.solve(K, y)
    return X.T @ dual_coefs

def loocv(X, y, alpha=1.0):
    """Leave-One-Out Cross-Validation (Numpy Puro)."""
    N = len(y)
    preds = np.zeros(N)
    for i in range(N):
        # Split
        idx_train = [j for j in range(N) if j != i]
        X_train, y_train = X[idx_train], y[idx_train]
        X_test = X[i:i+1]
        
        # Fit en N-1
        W = ridge_fit(X_train, y_train, alpha)
        
        # Eval en 1
        score = X_test @ W
        preds[i] = 1 if score[0] >= 0.5 else 0
    return preds

# ════════════════════════════════════════════════════════════════════
# DATASET SINTÉTICO ROTUNDO (50 muestras balanceadas)
# ════════════════════════════════════════════════════════════════════
def generate_dataset(n=50):
    np.random.seed(42)
    profiles = []
    
    # 25 Orgánicos
    for i in range(n//2):
        u = f"org_user_{i}"
        freq = np.random.uniform(0.1, 8.0)
        ratio = np.random.uniform(1.0, 10.0)
        bio = np.random.uniform(0.5, 0.9)
        # Edge cases 10% del tiempo
        kw = True if np.random.rand() < 0.1 else False
        low = True if np.random.rand() < 0.1 else False
        profiles.append((u, False, freq, ratio, bio, kw, low))
        
    # 25 Bots
    for i in range(n//2):
        u = f"bot_spmr_{i}"
        freq = np.random.uniform(20.0, 100.0)
        ratio = np.random.uniform(0.01, 0.2)
        bio = np.random.uniform(0.05, 0.3)
        # Bots camuflados (sin keywords obvias 20% del tiempo)
        kw = False if np.random.rand() < 0.2 else True
        low = False if np.random.rand() < 0.2 else True
        profiles.append((u, True, freq, ratio, bio, kw, low))
        
    return profiles

PROFILES = generate_dataset(50)

def test_generalization():
    header(f"TEST 4: Generalización LOOCV sobre {len(PROFILES)} muestras")
    N = GRID
    cfg = SimulationConfig(grid_size=N)
    Xs, ys, y_rb = [], [], []

    np.random.seed(42)
    N_FEATURES = 5
    MASK = np.random.uniform(-1, 1, size=(N_FEATURES, N, N, N)).astype(np.float32)

    print(f"  Procesando dinámicas de {len(PROFILES)} perfiles en Nokka Eterno...")
    
    t_start = time.perf_counter()
    for (u, is_bot, freq, ratio, bio_ent, has_kw, low_fol) in PROFILES:
        sim = _sim(cfg)
        u_feat = np.array([freq/100.0, ratio/10.0, bio_ent, float(has_kw), float(low_fol)])
        
        for i in range(N_FEATURES):
            sim._phase += MASK[i] * u_feat[i] * 2.0
            
        for _ in range(TRANSIENT):
            _step(sim)
            
        state_t2 = sim._grid.flatten().copy(); _step(sim)
        state_t1 = sim._grid.flatten().copy(); _step(sim)
        state_t0 = sim._grid.flatten().copy()
        phi = np.concatenate([state_t0, state_t1, state_t2])
        
        Xs.append(phi)
        ys.append(1 if is_bot else 0)
        is_heuristic_bot = (has_kw or low_fol) or (ratio < 0.1 and freq > 20)
        y_rb.append(1 if is_heuristic_bot else 0)

    print(f"  Extracción completada en {time.perf_counter()-t_start:.1f}s\n")

    X = np.array(Xs, dtype=np.float64)
    y = np.array(ys, dtype=np.float64)
    y_rb = np.array(y_rb)

    # Standarize
    mu = X.mean(0); sd = X.std(0) + 1e-8
    Xn = (X - mu) / sd
    Xn_bias = np.hstack([np.ones((Xn.shape[0], 1)), Xn])

    # 1. Baseline Rules
    acc_rule = np.mean(y == y_rb)
    
    # 2. RC Readout (Overfitted - Mismo Train y Test)
    W = ridge_fit(Xn_bias, y, ALPHA_RIDGE)
    y_pred_overfit = (Xn_bias @ W >= 0.5).astype(int)
    acc_overfit = np.mean(y == y_pred_overfit)

    # 3. RC Readout Duros (LOOCV)
    y_pred_loocv = loocv(Xn_bias, y, ALPHA_RIDGE)
    acc_loocv = np.mean(y == y_pred_loocv)
    
    # 4. Sanity Check - Barajar Etiquetas (Y Random)
    y_rand = np.random.permutation(y)
    y_pred_random = loocv(Xn_bias, y_rand, ALPHA_RIDGE)
    acc_random = np.mean(y_rand == y_pred_random)

    print(f"  📊 RESULTADOS DE GENERALIZACIÓN (Test Definitivo)")
    print(f"     Algoritmo Rule-Based (Heurística) : {acc_rule*100:6.1f}%")
    print(f"     RC Readout (Train=Test Ovefit)    : {acc_overfit*100:6.1f}%")
    print(f"     RC Readout (LOOCV Estricto)       : {acc_loocv*100:6.1f}%  <-- Métrica Real")
    print(f"     Sanity Check (Etiquetas Random)   : {acc_random*100:6.1f}%  <-- Si es ~50%, modelo es robusto")

    delta_loocv = acc_loocv - acc_rule
    print(f"\n  🎯 DELTA RC vs Heurística en Test OOD (LOOCV): {delta_loocv*100:+.1f}%")

    if acc_loocv > acc_rule and acc_random < 0.65:
        print(f"\n  🏆 VEREDICTO DE PEER-REVIEW: APROBADO")
        print(f"     La dimensionalidad 5184D extraída por la dinámica de Nokka generaliza")
        print(f"     patrones latentes mejor que la heurística humana codificada en duro.")
        print(f"     El sanity check descarta que el Ridge esté memorizando ruido.")
    elif acc_loocv <= acc_rule:
        print(f"\n  ⚠️  VEREDICTO: EL RESERVORIO SUFRE DE CURSE OF DIMENSIONALITY")
        print(f"     RC {acc_loocv*100:.0f}% vs Rule {acc_rule*100:.0f}%. Las features crudas bastan.")
    elif acc_random >= 0.65:
        print(f"\n  ❌ VEREDICTO: FALSO POSITIVO EN RIDGE")
        print(f"     El sanity check Random ({acc_random*100:.0f}%) falló. α es muy bajo para 50 muestras y 5184D.")

if __name__ == "__main__":
    test_generalization()
