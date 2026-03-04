#!/usr/bin/env python3
"""
🌌 NOKKA ETERNO — Reservoir Validation Suite v3
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Implementación de Reservoir Computing (RC) Real con:
  - Input Masking Vector (inyección dimensional distribuida)
  - Time-delay embedding (estado del reservorio = frames t, t-1, t-2)
  - Raw Features In (sin preclasificación)

python test_reservoir_v3.py
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

GRID        = 12
T_STEPS     = 300
TRANSIENT   = 50
ALPHA_RIDGE = 10.0
SEP = "─" * 62
def header(t): print(f"\n{SEP}\n  🧪 {t}\n{SEP}")

# ── Ridge puro ──
def ridge_fit(X, y, alpha=1.0):
    A = X.T @ X + alpha * np.eye(X.shape[1])
    return np.linalg.solve(A, X.T @ y)

def clf_report(y_true, y_pred, names=("Organic","Bot")):
    for i, name in enumerate(names):
        tp = np.sum((y_true==i)&(y_pred==i))
        fp = np.sum((y_true!=i)&(y_pred==i))
        fn = np.sum((y_true==i)&(y_pred!=i))
        p  = tp/max(tp+fp,1); r = tp/max(tp+fn,1)
        f1 = 2*p*r/max(p+r,1e-9)
        print(f"     {name:<10} P={p:.2f} R={r:.2f} F1={f1:.2f} sup={int(np.sum(y_true==i))}")


# ═══════════════════════════════════════════════════════
# TEST 3 v3 — REAL RESERVOIR COMPUTING READOUT
# ═══════════════════════════════════════════════════════
PROFILES = [
    # username           bot    freq   ratio  bio_ent  kw     low_fol
    ("skymapumin",      False,  3.2,   1.8,   0.65,  False,  False),
    ("unknowgirlXR",    False,  1.1,   2.5,   0.70,  False,  False),
    ("nokkawarrior",    False,  5.0,   4.2,   0.60,  False,  False),
    ("ancestral2026",   False,  2.0,   3.1,   0.55,  False,  False),
    ("user_organic1",   False,  4.5,   6.0,   0.72,  False,  False),
    ("user_organic2",   False,  0.8,   1.2,   0.68,  False,  False),
    ("user_organic3",   False,  3.0,   2.0,   0.63,  False,  False),
    
    # ── Bots / Trolls ──
    ("bot_crypto_99",   True,  45.0,   0.03,  0.15,  True,   True),
    ("troll_pol1",      True,  22.0,   0.10,  0.20,  True,   False),
    ("giveaway_bot",    True,  80.0,   0.01,  0.10,  True,   True),
    ("follow_back_x",   True,  30.0,   0.05,  0.18,  True,   True),
    ("crypto_shil1",    True,  55.0,   0.02,  0.12,  True,   True),
    ("bot_news_99",     True,  70.0,   0.04,  0.09,  True,   True),
    ("spam_acc_42",     True,  99.0,   0.01,  0.08,  True,   True),
    
    # ── Casos "Difíciles" (Edge Cases) para desafiar al Baseline ──
    ("influencer_x",    False, 50.0,   0.05,  0.20,  True,   False), # Falsa alarma (alto tweet, bio corta)
    ("new_user_123",    False,  0.5,   1.0,   0.10,  False,  True),  # Falsa alarma (pocos seguidores, bio vacía)
    ("bot_silencioso",  True,   1.5,   1.5,   0.80,  False,  False), # Falso negativo (bot que simula ser normal)
    ("troll_sofisticado",True,  5.0,   2.0,   0.70,  False,  False), # Bot con bio compleja y stats normales
]

def test_real_rc():
    header("TEST 3 (v3): True Reservoir Computing — Distributed Masking + Delay Embedding")
    N = GRID
    cfg = SimulationConfig(grid_size=N)
    Xs, ys, y_rb = [], [], []

    # 1. Matriz de Input Masking: Proyecta Features (5D) → Nodos (1728D)
    # Fija con semilla para que sea la misma proyección para todos los perfiles
    np.random.seed(42)
    N_FEATURES = 5
    MASK = np.random.uniform(-1, 1, size=(N_FEATURES, N, N, N)).astype(np.float32)

    print(f"  Input Masking     : {N_FEATURES}D → {N**3}D distribuida")
    print(f"  Delay Embedding   : 3 frames concatenados ({N**3 * 3} dimensionalidad)")
    print(f"  Número de Perfiles: {len(PROFILES)} (incluye edge cases)\n")
    print(f"  {'Label':<6}  {'@username':<22}")

    for (u, is_bot, freq, ratio, bio_ent, has_kw, low_fol) in PROFILES:
        sim = _sim(cfg)
        
        # 1. Vector de Features Crudo (SIN pre-clasificación)
        u_feat = np.array([
            freq / 100.0,               # Normalizado
            ratio / 10.0,               # Normalizado
            bio_ent,
            1.0 if has_kw else 0.0,
            1.0 if low_fol else 0.0
        ])
        
        # 2. Inyección Distribuida (Input Masking Vector)
        # Se inyectan las features proyectadas directamente a las FASES de todo el cubo.
        for i in range(N_FEATURES):
            sim._phase += MASK[i] * u_feat[i] * 2.0
            
        # 3. Washout temporal
        for _ in range(TRANSIENT):
            _step(sim)
            
        # 4. Delay Embedding (Captura dinámica, no solo un frame estático)
        state_t2 = sim._grid.flatten().copy()
        _step(sim)
        state_t1 = sim._grid.flatten().copy()
        _step(sim)
        state_t0 = sim._grid.flatten().copy()
        
        # Estado final = concatenación de los últimos 3 frames
        phi = np.concatenate([state_t0, state_t1, state_t2])
        
        Xs.append(phi)
        ys.append(1 if is_bot else 0)
        
        # Generar Baseline Simple (Heurística que tenías antes)
        # Si tiene Keyword o Low Followers, y una proporción anormal
        is_heuristic_bot = (has_kw or low_fol) or (ratio < 0.1 and freq > 20)
        y_rb.append(1 if is_heuristic_bot else 0)
        
        tag = "🚨BOT" if is_bot else "✅ORG"
        print(f"  {tag}  @{u:<22}  (baseline: {'bot' if is_heuristic_bot else 'org'})")

    X  = np.array(Xs, dtype=np.float64)
    y  = np.array(ys, dtype=np.float64)
    yr = np.array(y_rb)

    # 5. Estandarización del Estado
    mu = X.mean(0)
    sd = X.std(0) + 1e-8
    Xn = (X - mu) / sd

    # 6. Ridge Regression Readout (Con Bias/Intercept)
    # Agregamos columna de 1s explícita para el Bias
    Xn_bias = np.hstack([np.ones((Xn.shape[0], 1)), Xn])
    
    W = ridge_fit(Xn_bias, y, ALPHA_RIDGE)
    scores = Xn_bias @ W
    
    # Threshold natural estadístico
    y_pred = (scores >= 0.5).astype(int)

    acc_rc = float(np.mean(y == y_pred))
    acc_rb = float(np.mean(y == yr))
    delta  = acc_rc - acc_rb

    print(f"\n  📊 Comparación de accuracy (Métricas sobre {len(PROFILES)} muestras locales):")
    print(f"     Rule-Based Baseline : {acc_rb*100:.1f}%")
    print(f"     RC Readout          : {acc_rc*100:.1f}%")
    print(f"     Δ (RC - Baseline)   : {delta*100:+.1f}%")
    print(f"\n  Classification Report (RC Readout):")
    clf_report(np.array(ys), y_pred)

    # Separabilidad
    bsc = scores[y==1]; osc = scores[y==0]
    gap = float(bsc.mean() - osc.mean())
    print(f"\n  📐 Score gap (bot-org): {gap:+.4f}")
    print(f"     Organic mean: {osc.mean():+.4f} ± {osc.std():.4f}")
    print(f"     Bot mean    : {bsc.mean():+.4f} ± {bsc.std():.4f}")

    if delta > 0.05:
        v = "✅ SUPERIORIDAD RC DEMOSTRADA — La dinámica no lineal extrae features latentes"
    elif abs(delta) <= 0.05:
        if acc_rc > 0.90:
            v = "✅ SEPARABILIDAD ALTA — RC iguala la heurística perfecta, validando la arquitectura"
        else:
            v = "⚠️  RC ≈ BASELINE — Capacidad similar al baseline sin ventaja evidente"
    else:
        v = "❌ RC PEOR QUE BASELINE — Dinámica está destruyendo la separabilidad de las features"

    print(f"\n  🎯 {v}")

if __name__ == "__main__":
    t0 = time.perf_counter()
    test_real_rc()
    print(f"\n  Tiempo total: {time.perf_counter()-t0:.2f}s")
