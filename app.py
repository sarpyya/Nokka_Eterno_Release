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

# ─────────────────────────────────────────────
# INICIALIZACIÓN FLASK
# ─────────────────────────────────────────────
app = Flask(__name__)
app.config['SECRET_KEY'] = 'nokka-eterno-standalone-secret'
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

# ─────────────────────────────────────────────
# LAUNCHER
# ─────────────────────────────────────────────
if __name__ == '__main__':
    print("=" * 60)
    print("🌌 NOKKA ETERNO STANDALONE ACTIVADO")
    print("📍 URL: http://localhost:5000/nokka")
    print("=" * 60)
    socketio.run(app, host='0.0.0.0', port=5000, debug=True, use_reloader=False)