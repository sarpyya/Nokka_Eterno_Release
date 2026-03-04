#!/usr/bin/env python3
"""
🌌 NOKKA ETERNO — Reservoir Validation Suite v2
Ejecutar: python test_reservoir.py
"""
import sys, os, time, hashlib, io, contextlib
import numpy as np

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from engines.nokka_eterno import NokkaSimulation, SimulationConfig

# ── Suprimir prints de NokkaSimulation ───────────────────
@contextlib.contextmanager
def _quiet():
    with contextlib.redirect_stdout(io.StringIO()):
        yield

def _make_sim(cfg):
    with _quiet():
        return NokkaSimulation(cfg)

# ── Evolución RÁPIDA (solo campo, sin serialización) ─────
def _fast_step(grid, phase, x, y, z, wave_speed, noise_std, t):
    """Avanza el campo sin overhead de SocketIO ni stats."""
    phase += wave_speed
    grid[:] = (0.8 * np.sin(x*0.6 + phase) * np.cos(y*0.4 + phase*0.7)
               + 0.3 * np.sin(z*1.1 + t*0.08)
               + np.random.normal(0, noise_std, grid.shape).astype(np.float32))

# ── Parámetros ───────────────────────────────────────────
GRID      = 12
T_STEPS   = 300
T_SIGMA   = 100     # frames por punto del barrido σ (rápido)
TRANSIENT = 50
DELTA     = 0.1
ALPHA     = 1.0
SEP = "─" * 62

def header(t): print(f"\n{SEP}\n  🧪 {t}\n{SEP}", flush=True)

# ── Ridge numpy puro ─────────────────────────────────────
def ridge_fit(X, y, alpha=1.0):
    A = X.T @ X + alpha * np.eye(X.shape[1])
    return np.linalg.solve(A, X.T @ y)

def clf_report(y_true, y_pred):
    for i, name in enumerate(("Organic","Bot")):
        tp = np.sum((y_true==i)&(y_pred==i))
        fp = np.sum((y_true!=i)&(y_pred==i))
        fn = np.sum((y_true==i)&(y_pred!=i))
        p = tp/max(tp+fp,1); r = tp/max(tp+fn,1); f1 = 2*p*r/max(p+r,1e-9)
        print(f"     {name:<10} P={p:.2f} R={r:.2f} F1={f1:.2f} n={int(np.sum(y_true==i))}")


# ═══════════════════════════════════════════════════════════
# TEST 1 — Echo State Property
# ═══════════════════════════════════════════════════════════
def test_echo_state():
    header("TEST 1: Echo State Property (Fading Memory)")
    N   = GRID
    cfg = SimulationConfig(grid_size=N)
    sa  = _make_sim(cfg); sb = _make_sim(cfg)

    # Copiar estado inicial: B = A + Δ en un nodo
    sb._phase[:] = sa._phase.copy()
    sb._grid[:]  = sa._grid.copy()
    sb._phase[0,0,0] += DELTA

    print(f"  Δ={DELTA} | T={T_STEPS} | Grid={N}³={N**3}\n")
    print(f"  {'Frame':>6}  {'||δΦ|| L2':>11}  {'log||δΦ||':>11}  Δ", flush=True)

    divs = []
    for t in range(T_STEPS):
        with _quiet(): sa.step(); sb.step()
        l2 = float(np.linalg.norm(sa._grid - sb._grid))
        divs.append(l2)
        if t < 10 or t % 50 == 0:
            arr = "↗" if len(divs)>1 and divs[-1]>divs[-2] else "↘"
            print(f"  {t:>6}  {l2:>11.5f}  {np.log(l2):>11.5f}  {arr}", flush=True)

    divs = np.array(divs)
    pk_f = int(np.argmax(divs))
    fin  = float(divs[-1])
    print(f"\n  Pico   : {divs[pk_f]:.5f} (frame {pk_f})")
    print(f"  Final  : {fin:.5f}")
    print(f"  Rango  : [{divs.min():.4f}, {divs.max():.4f}] | CV={divs.std()/divs.mean():.4f}\n")

    if fin < divs[pk_f]*0.95:
        tag = "✅ FADING MEMORY — contracción post-peak"
    else:
        tag = "⚠️  ACOTADO (no contractive) — sistema driven-stochastic; λ define el régimen"
    print(f"  🎯 {tag}", flush=True)
    return divs


# ═══════════════════════════════════════════════════════════
# TEST 2 — Lyapunov + barrido σ (implementación rápida directa)
# ═══════════════════════════════════════════════════════════
def _lambda_fast(sigma, N=GRID, T=T_SIGMA, delta=DELTA, tr=20, wave_speed=0.15):
    """Calcula λ usando numpy raw arrays — sin overhead de NokkaSimulation."""
    x, y, z = np.meshgrid(np.arange(N,dtype=np.float32),
                           np.arange(N,dtype=np.float32),
                           np.arange(N,dtype=np.float32), indexing='ij')
    ph_a = np.random.rand(N,N,N).astype(np.float32)*2*np.pi
    ph_b = ph_a.copy(); ph_b[0,0,0] += delta
    g_a  = np.zeros((N,N,N), dtype=np.float32)
    g_b  = np.zeros((N,N,N), dtype=np.float32)
    divs = []
    for t in range(T):
        _fast_step(g_a, ph_a, x, y, z, wave_speed, sigma, t)
        _fast_step(g_b, ph_b, x, y, z, wave_speed, sigma, t)
        divs.append(max(float(np.linalg.norm(g_a-g_b)), 1e-12))
    log_r = np.diff(np.log(np.array(divs[tr:])))
    return float(np.mean(log_r))

def test_lyapunov(divs):
    header("TEST 2: Lyapunov Exponent + barrido λ vs σ")
    clean = np.clip(divs[TRANSIENT:], 1e-12, None)
    lam   = float(np.mean(np.diff(np.log(clean))))
    std_r = float(np.std(np.diff(np.log(clean))))
    print(f"  λ_max (σ=0.08 default): {lam:+.6f}  ±{std_r:.6f}\n")

    sigmas = [0.00, 0.02, 0.05, 0.08, 0.12, 0.20]
    print(f"  {'σ':>5}  {'λ_max':>10}  Régimen")
    lambdas = []
    for s in sigmas:
        lv = _lambda_fast(s)
        lambdas.append(lv)
        if   lv <  -0.001: reg = "🟢 Estable"
        elif lv <   0.005: reg = "✅ Edge-of-Chaos (RC óptimo)"
        elif lv <   0.10:  reg = "🟡 Caótico suave"
        else:              reg = "🔴 Caótico fuerte"
        print(f"  {s:>5.2f}  {lv:>+10.6f}  {reg}", flush=True)

    lams = np.array(lambdas)
    crosses = [(sigmas[i], sigmas[i+1])
               for i in range(len(lams)-1) if lams[i]*lams[i+1] < 0]
    if crosses:
        print(f"\n  📌 Cruce λ=0: σ={crosses[0][0]:.2f}→{crosses[0][1]:.2f}")
        print(f"     ✅ Control del régimen dinámico confirmado")
    else:
        print(f"\n  📌 λ≈0 en todo el rango → régimen crítico persistente")
    
    if   abs(lam) < 0.005: verdict = "✅ EDGE OF CHAOS — óptimo para RC"
    elif lam < 0:           verdict = "🟢 ESTABLE — aumentar wave_speed"
    else:                   verdict = "🟡 CAÓTICO — reducir noise_std"
    print(f"\n  🎯 λ={lam:+.6f} → {verdict}", flush=True)
    return lam, dict(zip(sigmas, lambdas))


# ═══════════════════════════════════════════════════════════
# TEST 3 — Linear Readout (Ridge puro) vs Rule-Based
# ═══════════════════════════════════════════════════════════
PROFILES = [
    # username           bot    freq   ratio  bio_ent  kw     low_fol
    ("skymapumin",      False,  3.2,   1.8,   0.65,  False,  False),
    ("unknowgirlXR",    False,  1.1,   2.5,   0.70,  False,  False),
    ("nokkawarrior",    False,  5.0,   4.2,   0.60,  False,  False),
    ("ancestral2026",   False,  2.0,   3.1,   0.55,  False,  False),
    ("user_organic1",   False,  4.5,   6.0,   0.72,  False,  False),
    ("user_organic2",   False,  0.8,   1.2,   0.68,  False,  False),
    ("user_organic3",   False,  3.0,   2.0,   0.63,  False,  False),
    ("bot_crypto_99",   True,  45.0,   0.03,  0.15,  True,   True),
    ("troll_pol1",      True,  22.0,   0.10,  0.20,  True,   False),
    ("giveaway_bot",    True,  80.0,   0.01,  0.10,  True,   True),
    ("follow_back_x",   True,  30.0,   0.05,  0.18,  True,   True),
    ("crypto_shil1",    True,  55.0,   0.02,  0.12,  True,   True),
    ("bot_news_99",     True,  70.0,   0.04,  0.09,  True,   True),
    ("spam_acc_42",     True,  99.0,   0.01,  0.08,  True,   True),
]

def _hcoord(u, N):
    h = int(hashlib.md5(u.encode()).hexdigest(), 16)
    return (h%N, (h//N)%N, (h//(N*N))%N)

def test_readout():
    header("TEST 3: Linear Readout — RC vs Rule-Based Baseline")
    N   = GRID
    cfg = SimulationConfig(grid_size=N)
    Xs, ys, yr = [], [], []

    print(f"  {len(PROFILES)} perfiles | Washout={TRANSIENT} frames")
    print(f"\n  {'Label':<6}  {'@username':<22}  coord         amp")

    for (u, is_bot, freq, ratio, bio_ent, has_kw, low_fol) in PROFILES:
        sim   = _make_sim(cfg)
        coord = _hcoord(u, N)
        amp   = -1.0 if (has_kw or low_fol) else 1.0
        ps    = np.sin(freq*0.1)*0.8 + np.cos(ratio*2.0)*0.6 + bio_ent*3.14
        sim._phase[coord] += ps * amp * 2.0
        for _ in range(TRANSIENT):
            with _quiet(): sim.step()
        Xs.append(sim._grid.flatten())
        ys.append(1 if is_bot else 0)
        yr.append(1 if (has_kw or low_fol) else 0)
        tag = "🚨BOT" if is_bot else "✅ORG"
        print(f"  {tag}  @{u:<22}  {str(coord):<14}  {amp:+.1f}", flush=True)

    X  = np.array(Xs, dtype=np.float64)
    y  = np.array(ys, dtype=np.float64)
    yr = np.array(yr)

    # Normalización estándar
    mu = X.mean(0); sd = X.std(0)+1e-8; Xn = (X-mu)/sd

    # Ridge fit
    W      = ridge_fit(Xn, y, ALPHA)
    scores = Xn @ W
    y_pred = (scores >= 0.5).astype(int)

    acc_rc = float(np.mean(y == y_pred))
    acc_rb = float(np.mean(np.array(ys) == yr))
    delta  = acc_rc - acc_rb

    print(f"\n  📊 Comparación de accuracy:")
    print(f"     Rule-Based       : {acc_rb*100:.1f}%")
    print(f"     RC Readout       : {acc_rc*100:.1f}%")
    print(f"     Δ (RC - Rule)    : {delta*100:+.1f}%")
    print(f"\n  Classification Report (RC Readout):")
    clf_report(np.array(ys), y_pred)

    # Score gap
    bsc = scores[y==1]; osc = scores[y==0]
    gap = float(bsc.mean() - osc.mean())
    sep = abs(gap) > max(bsc.std(), osc.std())
    print(f"\n  📐 Score gap (bot-org): {gap:+.4f}")
    print(f"     Organic mean: {osc.mean():+.4f} ± {osc.std():.4f}")
    print(f"     Bot mean    : {bsc.mean():+.4f} ± {bsc.std():.4f}")
    print(f"     Sep. lineal : {'✅ SÍ' if sep else '❌ NO'} (|gap|{'>' if sep else '<'}std)")

    if   delta > 0.05:        v = "✅ RC MEJORA AL BASELINE — reservorio agrega capacidad real"
    elif abs(delta) <= 0.05:  v = "⚠️  RC ≈ RULE-BASED — encoding MD5 no preserva semántica\n     → Fix: proyección estructurada de features antes de inyección"
    else:                     v = "❌ RC DEGRADA — fase no discriminativa en este régimen"
    print(f"\n  🎯 {v}", flush=True)
    return acc_rc, acc_rb


# ═══════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════
if __name__ == "__main__":
    print(f"\n{'='*62}")
    print("  🌌 NOKKA ETERNO — Reservoir Validation Suite v2")
    print("  NEWEN Protocol 2026 | 100% numpy, sin deps externas")
    print(f"{'='*62}")
    print(f"  Grid={GRID}³={GRID**3}n | T={T_STEPS} | T_σ={T_SIGMA} | Δ={DELTA}", flush=True)

    t0 = time.perf_counter()
    divs           = test_echo_state()
    lam, sigma_map = test_lyapunov(divs)
    acc_rc, acc_rb = test_readout()
    elapsed = time.perf_counter() - t0

    decay = divs[-1] < divs.max()*0.95
    print(f"\n{SEP}")
    print("  📋 RESUMEN EJECUTIVO")
    print(SEP)
    rows = [
        ("Echo State",           "✅ contractivo" if decay else "⚠️  acotado (driven)"),
        ("λ_max (σ=0.08)",       f"{lam:+.6f}  " + ("✅ edge-of-chaos" if abs(lam)<0.005 else "")),
        ("RC Readout acc.",       f"{acc_rc*100:.1f}%"),
        ("Rule-Based acc.",       f"{acc_rb*100:.1f}%"),
        ("Δ RC vs Baseline",     f"{(acc_rc-acc_rb)*100:+.1f}%"),
        ("Tiempo total",          f"{elapsed:.2f}s"),
    ]
    for k,v in rows:
        print(f"  {k:<26} {v}")
    print(f"\n  El Newen fluye. Los tambores no paran. 🪘💥🌌")
    print(SEP)
