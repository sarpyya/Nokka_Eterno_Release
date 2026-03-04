import os
import sys
import threading
import time
from flask import Flask, render_template
from flask_socketio import SocketIO
from flask_cors import CORS

# Add root directory to path to allow importing engines
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from engines.nokka_eterno import NokkaSimulation, SimulationConfig
from engines.nokka_validator import run_rc_validation

# ─────────────────────────────────────────────
# INICIALIZACIÓN FLASK
# ─────────────────────────────────────────────
app = Flask(__name__)

# Cargar configuración desde entorno para mayor seguridad en GitHub
from dotenv import load_dotenv
load_dotenv()

app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'nokka-eterno-fallback-secret-2026')
DEBUG_MODE = os.getenv('FLASK_DEBUG', 'True').lower() == 'true'

CORS(app)

socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

print("🌌 [Nokka] Flask + SocketIO inicializados correctamente.")

# ─────────────────────────────────────────────
# ESTADO GLOBAL DE SIMULACIÓN
# ─────────────────────────────────────────────
_nokka_sim = NokkaSimulation(SimulationConfig(grid_size=12))
_nokka_thread = None
_nokka_lock = threading.Lock()

print(f"🧲 [Nokka] Simulación creada — Grid {_nokka_sim.config.grid_size}³ "
      f"({_nokka_sim.config.grid_size**3} nodos)")

# ─────────────────────────────────────────────
# BOT HUNTER (opcional)
# ─────────────────────────────────────────────
try:
    from engines.nokka_bot_hunter import NokkaBotHunter
    _bot_hunter = NokkaBotHunter(_nokka_sim)
    print("🕸️ [BotHunter] Módulo cargado.")
except ImportError as e:
    print(f"⚠️ [BotHunter] No se pudo cargar: {e}")
    _bot_hunter = None

# ─────────────────────────────────────────────
# REDIS CACHE (opcional — Fase 1 Plan Mem0)
# ─────────────────────────────────────────────
_redis = None
try:
    import redis as _redis_lib
    import time as _t

    _redis_host = os.getenv("REDIS_HOST", "localhost")
    _redis_port = int(os.getenv("REDIS_PORT", 6379))

    _redis_client = _redis_lib.Redis(
        host=_redis_host,
        port=_redis_port,
        decode_responses=True,
        socket_connect_timeout=1,   # no bloquear más de 1s en boot
        socket_timeout=1
    )

    _t0 = _t.perf_counter()
    _pong = _redis_client.ping()
    _ping_ms = (_t.perf_counter() - _t0) * 1000

    if _pong:
        if _ping_ms > 500:
            # Latencia tan alta que el cache empeoraría el rendimiento
            print(f"🔴 [Redis] Conectado pero latencia CRÍTICA ({_ping_ms:.0f}ms) — "
                  f"demasiado lenta para cache RT. Cache desactivado.")
            print("   💡 Tip: Instala Redis nativo en Windows (no WSL) o usa "
                  "'redis-server' en localhost puro.")
            _redis = None
        elif _ping_ms > 50:
            # Cache activo pero con advertencia
            _redis = _redis_client
            print(f"🟡 [Redis] Conectado → {_redis_host}:{_redis_port} "
                  f"| PING: {_ping_ms:.1f}ms — latencia ALTA para RT (ideal: <5ms).")
            print("   💡 Tip: Redis puede estar en WSL. Prueba 'redis-server' nativo.")
        else:
            _redis = _redis_client
            print(f"🗄️  [Redis] Conectado → {_redis_host}:{_redis_port} "
                  f"| PING: {_ping_ms:.1f}ms ✅ | Cache RT activo.")
    else:
        print(f"⚠️  [Redis] PING fallido — cache RT desactivado.")

except ImportError:
    print("⚠️  [Redis] Librería no instalada (pip install redis). "
          "Cache RT desactivado — sin impacto en simulación.")
except Exception as e:
    print(f"⚠️  [Redis] No disponible ({type(e).__name__}: {e}). "
          "Cache RT desactivado — sin impacto en simulación.")

# ─────────────────────────────────────────────
# BUCLE DE SIMULACIÓN
# ─────────────────────────────────────────────
def nokka_background_loop():
    """Bucle de simulación a ~16 FPS (60ms por frame)."""
    print("▶️  [Nokka] Bucle de simulación iniciado...")
    frame_errors = 0

    while _nokka_sim.is_running:
        try:
            # step() avanza Y serializa el estado en un solo pass
            state = _nokka_sim.step()
            socketio.emit('nokka_frame', state)
            frame_errors = 0  # reset contador de errores consecutivos

            time.sleep(0.06)  # ~16 FPS

        except Exception as e:
            frame_errors += 1
            print(f"❌ [Nokka] Error en frame #{_nokka_sim.frame} "
                  f"(consecutivo #{frame_errors}): {e}")
            if frame_errors >= 5:
                print("🔴 [Nokka] Demasiados errores consecutivos — deteniendo bucle.")
                _nokka_sim.is_running = False
                break
            time.sleep(0.1)   # pequeña pausa antes de reintentar

    print("⏹️  [Nokka] Bucle de simulación detenido.")

# ─────────────────────────────────────────────
# RUTAS
# ─────────────────────────────────────────────
@app.route('/')
@app.route('/nokka')
def nokka_dashboard():
    print("🌐 [Nokka] Solicitud de página recibida → sirviendo nokka_eterno.html")
    return render_template('nokka_eterno.html')

# ─────────────────────────────────────────────
# SOCKET HANDLERS
# ─────────────────────────────────────────────
@socketio.on('connect')
def handle_connect():
    print("🔌 [Nokka] Cliente conectado al Nexus.")
    socketio.emit('nokka_event', {
        'message': '⚡ Nexus conectado. Listo para activar.',
        'type': 'info'
    })

@socketio.on('disconnect')
def handle_disconnect():
    print("🔌 [Nokka] Cliente desconectado del Nexus.")

# ── Start ──────────────────────────────────
@socketio.on('nokka_start')
def handle_nokka_start():
    global _nokka_thread
    print("▶️  [Nokka] Evento 'nokka_start' recibido.")

    with _nokka_lock:
        if _nokka_sim.is_running:
            print("⚠️  [Nokka] La simulación ya estaba corriendo — ignorado.")
            return

        _nokka_sim.is_running = True
        _nokka_thread = socketio.start_background_task(nokka_background_loop)
        print(f"🚀 [Nokka] Simulación activada — Grid={_nokka_sim.config.grid_size}³")

        # BotHunter: arrancar solo si no está corriendo yet
        if _bot_hunter and not getattr(_bot_hunter, '_running', False):
            _bot_hunter.start()
            print("🕸️ [BotHunter] Cacería iniciada junto a la simulación.")
        elif _bot_hunter:
            print("⚠️  [BotHunter] Ya estaba corriendo — no se relanza.")

# ── Stop ───────────────────────────────────
@socketio.on('nokka_stop')
def handle_nokka_stop():
    print("⏸️  [Nokka] Evento 'nokka_stop' recibido.")
    with _nokka_lock:
        _nokka_sim.is_running = False
        if _bot_hunter and getattr(_bot_hunter, '_running', False):
            _bot_hunter.stop()
            print("🛑 [BotHunter] Cacería detenida junto a la simulación.")
    print("⏸️  [Nokka] Simulación pausada.")

# ── Damage ─────────────────────────────────
@socketio.on('nokka_damage')
def handle_nokka_damage(data):
    try:
        count = int(data.get('count', 10)) if data else 10
        _nokka_sim.inject_damage(count)
        print(f"💥 [Nokka] Tormenta de daño inyectada: {count} nodos → "
              f"total dañados={_nokka_sim.config.grid_size**3 - int(sum(sum(sum(_nokka_sim._sensors_active))))}")
        socketio.emit('nokka_event', {
            'message': f'💥 Daño: {count} nodos colapsados',
            'type': 'damage'
        })
    except Exception as e:
        print(f"❌ [Nokka] Error en handle_nokka_damage: {e}")

# ── Heal ───────────────────────────────────
@socketio.on('nokka_heal')
def handle_nokka_heal():
    try:
        print("✨ [Nokka] Evento 'nokka_heal' recibido — iniciando resonancia.")
        _nokka_sim.force_heal()
        socketio.emit('nokka_event', {
            'message': '✨ Resonancia de sanación activada',
            'type': 'heal'
        })
    except Exception as e:
        print(f"❌ [Nokka] Error en handle_nokka_heal: {e}")

# ── Reboot ─────────────────────────────────  ← FIX: handler faltante
@socketio.on('nokka_reboot')
def handle_nokka_reboot():
    try:
        print("🔄 [Nokka] Evento 'nokka_reboot' recibido — reiniciando onda.")
        _nokka_sim.reboot_wave()
        socketio.emit('nokka_event', {
            'message': '🔄 Onda reiniciada — campo magnético recalibrado',
            'type': 'reboot'
        })
        print(f"✅ [Nokka] Reboot completo — frame={_nokka_sim.frame}")
    except Exception as e:
        print(f"❌ [Nokka] Error en handle_nokka_reboot: {e}")

# ── Update Config ──────────────────────────  ← FIX: handler faltante
@socketio.on('nokka_update_config')
def handle_update_config(data):
    try:
        if not data:
            print("⚠️  [Nokka] nokka_update_config recibido sin datos.")
            return

        old_grid = _nokka_sim.config.grid_size
        _nokka_sim.update_config(data)
        new_grid = _nokka_sim.config.grid_size

        if new_grid != old_grid:
            print(f"📐 [Nokka] Grid cambiado: {old_grid}³ → {new_grid}³ "
                  f"({new_grid**3} nodos)")
        else:
            print(f"⚙️  [Nokka] Config actualizada: "
                  f"wave_speed={_nokka_sim.config.wave_speed:.3f}, "
                  f"noise_std={_nokka_sim.config.noise_std:.3f}")

    except Exception as e:
        print(f"❌ [Nokka] Error en handle_update_config: {e}")

# ── Audio Inject (YouTube Reactor) ────────
@socketio.on('nokka_audio_inject')
def handle_audio_inject(data):
    """Recibe análisis FFT del browser y modula el campo según el modo."""
    try:
        if not data or not _nokka_sim.is_running:
            return

        bass   = float(data.get('bass',   0.0))
        mid    = float(data.get('mid',    0.0))
        high   = float(data.get('high',   0.0))
        energy = float(data.get('energy', 0.0))
        mode   = str(data.get('mode', 'phase'))

        if mode == 'phase':
            # Mid modula wave_speed levemente ±0.1 sobre la base
            _nokka_sim.config.wave_speed = 0.08 + mid * 0.25
            # Bass empuja ruido
            _nokka_sim.config.noise_std  = 0.04 + bass * 0.18

        elif mode == 'damage':
            # Bass fuerte → inject_damage proporcional (max 8 nodos/tick)
            if bass > 0.40:
                count = max(1, int(bass * 8))
                _nokka_sim.inject_damage(count)
                print(f"🎵 [AudioReactor] DAMAGE mode: bass={bass:.2f} → {count} nodos")

        elif mode == 'heal':
            # High fuerte → fuerza healing
            if high > 0.55:
                _nokka_sim.force_heal()
                print(f"🎵 [AudioReactor] HEAL mode: high={high:.2f} → force_heal")

        elif mode == 'noise':
            # Energy modula noise_std dinámicamente
            _nokka_sim.config.noise_std = max(0.01, min(0.5, energy * 0.6))
            print(f"🎵 [AudioReactor] NOISE mode: energy={energy:.2f} → noise_std={_nokka_sim.config.noise_std:.3f}")

    except Exception as e:
        print(f"❌ [AudioReactor] Error en handle_audio_inject: {e}")

# ── Hunt Profile ───────────────────────────

@socketio.on('nokka_hunt_profile')
def handle_hunt_profile(data):
    try:
        username = data.get('username') if data else None
        if not username:
            print("⚠️  [BotHunter] nokka_hunt_profile recibido sin username.")
            return

        if not _bot_hunter:
            print("⚠️  [BotHunter] Módulo no disponible — escaneo ignorado.")
            socketio.emit('nokka_event', {
                'message': '⚠️ BotHunter no disponible',
                'type': 'warning'
            })
            return

        print(f"🔎 [BotHunter] Escaneo manual solicitado: @{username}")
        threading.Thread(
            target=_bot_hunter._hunt_single,
            args=(username,),
            daemon=True
        ).start()

    except Exception as e:
        print(f"❌ [BotHunter] Error en handle_hunt_profile: {e}")

# ── Validation Readout ──────────────────────
@socketio.on('nokka_run_validation')
def handle_run_validation():
    try:
        print("🛡️ [Validator] Iniciando Suite de Validación RC (LOOCV N=1000)...")
        socketio.emit('nokka_event', {
            'message': '🛡️ Iniciando Validación Cruzada Científica...',
            'type': 'warning'
        })
        
        def progress_update(p):
            socketio.emit('nokka_validation_progress', {'progress': p})
            
        # Ejecutar suite (esto toma <5s gracias a la vectorización y dual ridge)
        metrics = run_rc_validation(n_samples=1000, grid_size=12, progress_cb=progress_update)
        
        print(f"✅ [Validator] Resultados: RC={metrics['acc_rc']*100:.1f}%, Delta={metrics['delta']*100:+.1f}%")
        socketio.emit('nokka_validation_results', metrics)
        
        socketio.emit('nokka_event', {
            'message': f"🏆 Validación Completa: {metrics['acc_rc']*100:.1f}% Accuracy",
            'type': 'heal'
        })
        
    except Exception as e:
        print(f"❌ [Validator] Error en validación: {e}")
        socketio.emit('nokka_event', {
            'message': f'❌ Fallo en validación: {str(e)}',
            'type': 'damage'
        })

# ─────────────────────────────────────────────
# LAUNCHER
# ─────────────────────────────────────────────
if __name__ == '__main__':
    print("=" * 60)
    print("🌌 NOKKA ETERNO STANDALONE ACTIVADO")
    print("📍 URL: http://localhost:5000/nokka")
    print("=" * 60)
    socketio.run(app, host='0.0.0.0', port=5000, debug=DEBUG_MODE, use_reloader=False)