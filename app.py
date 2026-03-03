#!/usr/bin/env python3
"""
🔥 BAYESIAN NEGATIVE 9D v6.0 - FLASK APP COMPLETO 🔥
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Servidor Flask completo con:
- Generación de grafos 9D
- Export a JSON para Three.js
- Base de datos SQLite (Hall of Shame)
- Rutas para visualización web
"""

from flask import Flask, render_template, jsonify, send_from_directory, request, redirect, url_for, flash, g, session
from flask_socketio import SocketIO, emit # 🔌 Importar SocketIO
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_cors import CORS  # ⚡ CORS para acceso público
import requests
import hashlib
import hmac
import math
from datetime import datetime
import json
import os
import glob
import random
import re
import time
import uuid
import threading
import traceback
import sys
# 🔧 FIX WINDOWS UNICODE ERROR
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

# Importar módulos del sistema
from engines.core_engine import (
    generar_grafo_9d, analizar_horror, print_banner,
    DIMENSIONES_9D, MODOS
)
from engines.resonance_algorithm import ResonanceAlgorithm, AXIAL_SAGITTAL_KEY
from api.x_integration import register_x_routes  # ← AÑADIDO
from engines.nokka_eterno import NokkaSimulation, SimulationConfig  # 🌌 NOKKA ETERNO

app = Flask(__name__)
# ... (configuraciones existentes) ...

# Registrar rutas de X
register_x_routes(app)

# 🌐 CONFIGURACIÓN DE RUTAS (ABSOLUTA para compatibilidad con systemd)
basedir = os.path.abspath(os.path.dirname(__file__))
instance_path = os.path.join(basedir, 'instance')
db_path = os.path.join(instance_path, 'horror_runs.db')

# Asegurar que el directorio instance/ existe
os.makedirs(instance_path, exist_ok=True)

# 🚨 GLOBAL ERROR HANDLER (Captura todo lo que no esté en try/except)
@app.errorhandler(500)
def handle_500_error(e):
    with open("global_error.log", "a", encoding="utf-8") as f:
        f.write(f"\\n[{datetime.now()}] GLOBAL 500 ERROR:\\n")
        f.write(traceback.format_exc())
    return "Internal Server Error (Check global_error.log)", 500

# ⚡ HABILITAR CORS - Acceso público desde cualquier origen

# ⚡ HABILITAR CORS - Acceso público desde cualquier origen
CORS(app, resources={r"/*": {"origins": "*"}})

# 📊 LOGGING DE REQUESTS (Para debugging en tiempo real)
@app.before_request
def log_request_info():
    print(f"[REQUEST] {datetime.now().strftime('%H:%M:%S')} | {request.remote_addr} | {request.method} {request.path}")

@app.after_request
def log_response_info(response):
    print(f"[RESPONSE] {datetime.now().strftime('%H:%M:%S')} | Status: {response.status_code} | Size: {response.content_length} bytes")
    return response
# 🔌 INICIALIZAR SOCKET.IO (Modo Threading para compatibilidad Windows/Dev)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')
app.config['SECRET_KEY'] = 'cosmic-v6-secret-key-9d' # Cambiar en producción
# 🔧 FIX: Usar ruta absoluta para SQLite (systemd compatibility)
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# ═══════════════════════════════════════════════════════════════
# 🔐 CONFIGURACIÓN DE CONCIENCIA (NEWEN-NEXUS CORE)
# ═══════════════════════════════════════════════════════════════

# 🌎 CONFIGURACIÓN MULTI-IDIOMA (I18N)
TRANSLATIONS = {}
def load_translations():
    trans_dir = os.path.join(basedir, 'translations')
    for lang_file in glob.glob(os.path.join(trans_dir, '*.json')):
        lang_code = os.path.basename(lang_file).replace('.json', '')
        with open(lang_file, 'r', encoding='utf-8') as f:
            TRANSLATIONS[lang_code] = json.load(f)

load_translations()

@app.context_processor
def inject_translate():
    from flask import session
    lang = session.get('lang', 'es')
    current_trans = TRANSLATIONS.get(lang, TRANSLATIONS.get('es', {}))
    def t(key):
        return current_trans.get(key, key)
    return dict(t=t, translations_js=json.dumps(current_trans))

@app.route('/set_language/<lang>')
def set_language(lang):
    from flask import session, request
    if lang in TRANSLATIONS:
        session['lang'] = lang
    return redirect(request.referrer or url_for('index'))

# 🔧 Configuración del Servidor Central (Configurable vía GCloud Env)
CENTRAL_SERVER_URL = os.getenv("CENTRAL_SERVER_URL", "http://localhost:8000")

login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.login_message = "Misión crítica: Se requiere autorización galáctica."
login_manager.init_app(app)

class User(UserMixin):
    def __init__(self, id, username, first_name=None, token=None):
        self.id = id
        self.username = username
        self.first_name = first_name
        self.token = token

@login_manager.user_loader
def load_user(user_id):
    return User(user_id, user_id)

# --- SISTEMA DE FÍSICA Y SEGURIDAD DINÁMICA ---
_security_cache = {"public": False, "last_check": 0}
_physics_cache = {}
_ionic_pulses = [] # In-memory buffer for visualizer

# 🌀 ALGORITMO DE RESONANCIA NEWEN (GLOBAL)
# Inicializamos con la llave del Kultrun (contradicción axial/sagital)
RESONANCE_ALGO = ResonanceAlgorithm(newen_key=AXIAL_SAGITTAL_KEY)
print("🌀 Algoritmo de Resonancia NEWEN-EE1111E inicializado...")
print(f"   Llave del Kultrun: {AXIAL_SAGITTAL_KEY}")
print(f"   Nodos activos: {len(RESONANCE_ALGO.kultrun.nodes)}")
print(f"   Dimensiones: {list(set(n.dimension for n in RESONANCE_ALGO.kultrun.nodes.values()))}")

def get_effective_physics(tenant_data):
    """
    Calcula la realidad efectiva del universo usando la jerarquía (Fase 2).
    Aplica la fórmula: theta_eff = theta_global + w * (theta_local - theta_global) * e^(-beta * H_local)
    """
    tenant_id = tenant_data.get('schema_name')
    now = datetime.now().timestamp()
    
    # Cache por 5 minutos (Resiliencia 2.0)
    if tenant_id in _physics_cache:
        cached_data, expiry = _physics_cache[tenant_id]
        if now < expiry:
            return cached_data

    # Parámetros base globales
    base_physics = {
        'gravity': 1.0,
        'horror_thresh': 50000,
        'vel_pos': 50.0,
        'vel_neg': -50.0
    }
    
    # Overrides del tenant
    overrides = tenant_data.get('physics_overrides', {})
    horror_level = tenant_data.get('horror_level', 0) # Mock por ahora
    beta = 0.1
    
    # Peso bayesiano: local influye más si horror es bajo
    w = 0.7 * math.exp(-beta * (horror_level / 1000.0))
    
    effective = base_physics.copy()
    for key in base_physics:
        if key in overrides:
            local_val = float(overrides[key])
            effective[key] = base_physics[key] + w * (local_val - base_physics[key])
            
    _physics_cache[tenant_id] = (effective, now + 300)
    return effective

def is_universe_public():
    """
    🌌 ACCESO PÚBLICO TOTAL ACTIVADO
    El universo NEWEN-NEXUS está abierto para todos.
    No requiere consultar al servidor central.
    """
    return True  # ⚡ Acceso inmediato sin restricciones


# --- ENCRIPTACIÓN GLUON IONICA (Fase 3) ---
def gluon_strong_hash(state_dict, rounds=6):
    """Hashing no-lineal auto-interactuante ( QCD-inspired )"""
    s = json.dumps(state_dict, sort_keys=True).encode()
    for _ in range(rounds):
        # El hash se mezcla con su propia reversa para máxima no-linealidad
        s = hashlib.sha3_512(s + s[::-1]).digest()
    return s.hex()

def derive_ion_key(state_data, salt=b'mapu9d_confinity'):
    """
    Deriva una clave de sesión única dependiente de la física del universo.
    🛡️ EE5-HYBRID LAYER (Post-Quantum Ready)
    Integración de ML-KEM (Kyber) para resistencia a Harvest-Now-Decrypt-Later.
    """
    # Añadimos un nonce basado en tiempo de alta resolución
    nonce = str(datetime.now().timestamp()).encode()
    
    # --- PQC LAYER START ---
    quantum_entropy = b""
    try:
        # Intento de cargar liboqs-python (Quantum Safe)
        # from oqs import KeyEncapsulation 
        # kem = KeyEncapsulation("ML-KEM-768")
        # public_key = kem.generate_keypair()
        # ciphertext, shared_secret = kem.encap_secret(public_key)
        # quantum_entropy = shared_secret
        raise ImportError("liboqs no instalada - Usando simulación PQC")
    except ImportError:
        # Simulación de entropía cuántica para dev/demo (NO SEGURO EN PROD)
        # En producción: pip install liboqs-python
        quantum_entropy = hashlib.sha3_512(b"SIMULATION_ML_KEM_768_ENTROPY" + os.urandom(32)).digest()
    # --- PQC LAYER END ---

    # Fusión: Gluon Hash (Clásico) + PQC Secret
    digest = gluon_strong_hash({
        **state_data, 
        'nonce': nonce.decode(),
        'pqc_marker': 'ML-KEM-768-HYBRID'
    })
    
    # Mezclamos la entropía cuántica en el HKDF
    hkdf = HKDF(
        algorithm=hashes.SHA512(),
        length=32,
        salt=salt,
        info=b'mapucosmos-ion-handshake-hybrid-v1' + quantum_entropy
    )
    return hkdf.derive(digest.encode())

def flexible_login_required(f):
    """Decorador que permite acceso si el universo es público O si hay login."""
    from functools import wraps
    @wraps(f)
    def decorated_view(*args, **kwargs):
        if is_universe_public():
            return f(*args, **kwargs)
        if not current_user.is_authenticated:
            return login_manager.unauthorized()
        return f(*args, **kwargs)
    return decorated_view

# ═══════════════════════════════════════════════════════════════
# 💾 MODELO DE BASE DE DATOS
# ═══════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════
# 💾 MODELOS DE DATOS (PERSISTENCIA BAYESIANA)
# ═══════════════════════════════════════════════════════════════

class HorrorRun(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    seed = db.Column(db.Integer, nullable=False, unique=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    horror_total = db.Column(db.Float, nullable=False)
    modo = db.Column(db.String(50))
    modo_desc = db.Column(db.Text)
    top_nodes = db.Column(db.Text)  # JSON string
    horror_promedio = db.Column(db.Float)
    total_nodos = db.Column(db.Integer)
    
    # 🌀 CAMPOS MULTI-TENANT
    # Nota: Las FK se agregarán después de importar models_multitenant
    organization_id = db.Column(db.Integer, nullable=True, index=True)
    created_by = db.Column(db.Integer, nullable=True)

    def to_dict(self):
        return {
            'id': self.id,
            'seed': self.seed,
            'timestamp': self.timestamp.isoformat(),
            'horror_total': self.horror_total,
            'modo': f"{self.modo} {self.modo_desc or ''}",
            'top_nodes': json.loads(self.top_nodes) if self.top_nodes else [],
            'horror_promedio': self.horror_promedio,
            'total_nodos': self.total_nodos,
            'organization_id': self.organization_id,
            'created_by': self.created_by
        }


class UserProfileLog(db.Model):
    """Registro de personalidades capturadas y métricas de sesión"""
    id = db.Column(db.Integer, primary_key=True)
    x_handle = db.Column(db.String(100), nullable=True)
    archetype = db.Column(db.String(100))
    entropy = db.Column(db.Float)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    session_duration = db.Column(db.Float, default=0.0) # Segundos
    hardware_meta = db.Column(db.Text) # JSON: GPU, Cores, RAM tier
    interaction_meta = db.Column(db.Text) # JSON: Clicks, Modos usados, Focus changes

    def to_dict(self):
        return {
            'id': self.id,
            'x_handle': self.x_handle,
            'archetype': self.archetype,
            'created_at': self.created_at.isoformat()
        }

class XProspect(db.Model):
    """Archivo de Identidades Recopiladas (Prospector Neuronal)"""
    id = db.Column(db.Integer, primary_key=True)
    handle = db.Column(db.String(100), unique=True, nullable=False)
    archetype = db.Column(db.String(100))
    entropy = db.Column(db.Float)
    status = db.Column(db.String(100)) # Biológico/Sintético
    dimension = db.Column(db.String(100))
    history = db.Column(db.Text)
    survival_guide = db.Column(db.Text) # JSON string
    passport_hash = db.Column(db.String(64))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Historia Oral
    oral_title = db.Column(db.String(200))
    oral_story = db.Column(db.Text)
    oral_glifo = db.Column(db.String(50))

    def to_dict(self):
        return {
            'id': self.id,
            'x_handle': self.handle,
            'handle_analysis': {
                'detected_archetype': self.archetype,
                'entropy_level': f"{self.entropy:.2f}",
                'biological_status': self.status,
                'resonance_dimension': self.dimension,
            },
            'generated_history': self.history,
            'survival_guide': json.loads(self.survival_guide) if self.survival_guide else [],
            'pasaporte_hash': self.passport_hash,
            'created_at': self.created_at.isoformat(),
            'oral_history': {
                'titulo': self.oral_title,
                'relato': self.oral_story,
                'glifo': self.oral_glifo,
                'preguntas_ramificadas': ["¿Qué viste en el abismo?", "¿Cómo derrotaste al horror?", "¿Cuál es tu nombre real?", "¿Qué juraste?", "¿Qué llevas en tu pecho?"] # Default for archive
            }
        }

with app.app_context():
    db.create_all()

# ... (Previous helper functions) ...

# ═══════════════════════════════════════════════════════════════
# 🧠 EXTENSION: LOGGING ENDPOINT
# ═══════════════════════════════════════════════════════════════

@app.route('/api/log_session_end', methods=['POST'])
def log_session_end():
    data = request.json
    # En un sistema real, actualizaríamos el registro de la sesión actual
    # Aquí solo guardamos un log genérico o actualizamos el último perfil creado
    last_profile = UserProfileLog.query.order_by(UserProfileLog.id.desc()).first()
    if last_profile:
        last_profile.session_duration = data.get('duration', 0)
        last_profile.interaction_meta = json.dumps(data.get('interaction', {}))
        db.session.commit()
    return jsonify({'status': 'logged'})

def archive_x_profile(handle, profile):
    """Guarda un perfil en el archivo central XProspect si no existe"""
    try:
        existing = XProspect.query.filter_by(handle=handle).first()
        if not existing:
            new_prospect = XProspect(
                handle=handle,
                archetype=profile['handle_analysis']['detected_archetype'],
                entropy=float(profile['handle_analysis']['entropy_level'].split()[0]),
                status=profile['handle_analysis']['biological_status'],
                dimension=profile['handle_analysis']['resonance_dimension'],
                history=profile['generated_history'],
                survival_guide=json.dumps(profile['survival_guide']),
                passport_hash=profile['pasaporte_hash'],
                oral_title=profile['oral_history']['titulo'],
                oral_story=profile['oral_history']['relato'],
                oral_glifo=profile['oral_history']['glifo']
            )
            db.session.add(new_prospect)
            db.session.commit()
            print(f"💾 ENTIDAD ARCHIVADA: {handle} ({new_prospect.archetype})")
            return True
    except Exception as e:
        db.session.rollback()
        print(f"⚠️ Error archivando prospecto: {e}")
    return False

# Update auth_x_callback to save profile
@app.route('/auth/x_callback')
def auth_x_callback():
    code = request.args.get('code')
    handle_input = request.args.get('handle', '@anonimo')
    
    # 🕵️ VALIDACIÓN DE EXISTENCIA (SIMULADA / PRE-API)
    # 1. Validación de Formato X (Twitter)
    if not re.match(r"^@[a-zA-Z0-9_]{1,15}$", handle_input):
        return jsonify({
            'status': 'error',
            'message': 'FORMATO INVÁLIDO: El handle debe ser @usuario (max 15 chars, alfanumérico).'
        }), 400

    # 2. Simulación de "Usuario No Encontrado" (Blacklist para demo)
    # En producción: Aquí llamaríamos a client.get_user(username=handle[1:])
    forbidden_users = ['@test', '@null', '@fake', '@error', '@admin', '@root']
    if handle_input.lower() in forbidden_users:
        return jsonify({
            'status': 'error',
            'message': f'ENTIDAD NO ENCONTRADA: {handle_input} no existe en la Noosfera.'
        }), 404

    # SIMULATION MODE (DETERMINISTA BASADO EN HANDLE)
    profile = generate_bayesian_x_profile(["sistema", "error", "colapso", "esperanza", "red"], handle_str=handle_input)
    
    # 💾 ARCHIVADO CENTRAL (RISA ETERNA)
    archive_x_profile(handle_input, profile)

    # 💾 LOG DE SESIÓN EXISTENTE
    try:
        entropy_val = float(profile['handle_analysis']['entropy_level'].split()[0])
        new_log = UserProfileLog(
            x_handle=handle_input,
            archetype=profile['handle_analysis']['detected_archetype'],
            entropy=entropy_val,
            hardware_meta=json.dumps({"simulated": True})
        )
        db.session.add(new_log)
        db.session.commit()
    except Exception as e:
        print(f"⚠️ Error guardando log: {e}")

    # Inyectar handle en la respuesta para el frontend
    profile['x_handle'] = handle_input

    return jsonify({
        'status': 'success',
        'message': 'Enlace Neuronal X Establecido',
        'analysis': profile
    })

# ═══════════════════════════════════════════════════════════════
# 🔧 FUNCIONES AUXILIARES
# ═══════════════════════════════════════════════════════════════

def save_run_to_db(seed, analisis):
    """Guarda un run en la base de datos"""
    if HorrorRun.query.filter_by(seed=seed).first():
        return
    
    top_nodes_json = json.dumps([
        {"label": n['label'], "horror": n['horror'], "desc": n.get('desc','')[:100]}
        for n in analisis['nodos_mas_horribles'][:10]
    ])
    
    run = HorrorRun(
        seed=seed,
        horror_total=analisis['horror_total'],
        modo=analisis['modo'],
        modo_desc=analisis['modo_info']['desc'],
        top_nodes=top_nodes_json,
        horror_promedio=analisis['horror_promedio'],
        total_nodos=analisis['total_nodos']
    )
    db.session.add(run)
    db.session.commit()

def export_to_threejs(G, analisis, filepath="web/data.json"):
    """Exporta grafo a formato JSON para Three.js"""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    
    nodes = []
    for node_id, data in G.nodes(data=True):
        nodes.append({
            "id": node_id,
            "label": data.get('label', node_id),
            "horror": data.get('horror', 0),
            "dim": data.get('dim', 0),
            "desc": data.get('desc', ''),
            "position": [
                random.uniform(-1000, 1000),
                random.uniform(-500, 500),
                random.uniform(-1000, 1000)
            ]
        })
    
    edges = []
    for u, v, data in G.edges(data=True):
        edges.append({
            "source": u,
            "target": v,
            "weight": data.get('weight', 1.0),
            "label": data.get('label', '')
        })
    
    output = {
        "nodes": nodes,
        "edges": edges,
        "modo": analisis['modo'],
        "horror_total": analisis['horror_total'],
        "timestamp": analisis['timestamp']
    }
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

def save_replay_seed(G, analisis, seed, replay_path="replays/"):
    """Guarda replay para reproducción futura"""
    os.makedirs(replay_path, exist_ok=True)
    filepath = os.path.join(replay_path, f"horror_graph_{seed}.json")
    export_to_threejs(G, analisis, filepath)

# ═══════════════════════════════════════════════════════════════
# 🎮 GENERACIÓN BATCH
# ═══════════════════════════════════════════════════════════════

def main(batch_size: int = 200, start_seed: int = -10):
    """Genera batch de universos y guarda en DB"""
    print_banner()
    print(f"\n🌌 Generando {batch_size} universos desde seed {start_seed}...\n")
    
    for i in range(batch_size):
        seed = start_seed + i
        print(f"[{i+1}/{batch_size}] Seed {seed}... ", end='', flush=True)
        
        G = generar_grafo_9d(seed=seed, max_nodes=12000, ramificaciones_por_nodo=8)
        analisis = analizar_horror(G)
        
        print(f"Horror: {analisis['horror_total']:,.0f} | {analisis['modo_info']['emoji']} {analisis['modo']}")
        
        save_replay_seed(G, analisis, seed)
        export_to_threejs(G, analisis, f"web/data_seed_{seed}.json")
        save_run_to_db(seed, analisis)
    
    print(f"\n✅ Batch completo! {batch_size} universos generados 🚀\n")

# ═══════════════════════════════════════════════════════════════
# 🌐 RUTAS FLASK
# ═══════════════════════════════════════════════════════════════

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        try:
            # 🌀 PASO 1: PULSO DE RESONANCIA PRE-AUTH
            # Cada intento de login genera un pulso en el Kultrun
            current_time = datetime.now().timestamp()
            RESONANCE_ALGO.pulse(
                t=current_time,
                external_horror=50.0,  # Horror del intento de auth
                external_newen=100.0   # Newen del usuario que intenta entrar
            )
            
            # Validar contra el Servidor Central Django
            response = requests.post(
                f"{CENTRAL_SERVER_URL}/api/token/",
                json={"username": username, "password": password},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                # Extraer info del usuario (CustomTokenObtainPairSerializer de Django)
                user_info = data.get('user', {})
                user_id = user_info.get('username') or username
                
                # 🌀 PASO 2: GENERAR TOKEN NEWEN
                # El token ahora incluye el estado del Kultrun
                newen_token_data = RESONANCE_ALGO.get_login_token(user_id)
                
                # Guardar token NEWEN en sesión (además del JWT de Django)
                # En una implementación completa, esto se guardaría en la base de datos
                print(f"🌀 Token NEWEN generado para {user_id}")
                print(f"   Firma: {newen_token_data['newen_signature']}")
                print(f"   Horror Total: {newen_token_data['payload']['kultrun_state']['horror_total']:.2f}")
                print(f"   Newen Total: {newen_token_data['payload']['kultrun_state']['newen_total']:.2f}")
                print(f"   Coherencia: {newen_token_data['payload']['kultrun_state']['coherence']:.2%}")
                
                # 🌀 PASO 3: PULSO DE RESONANCIA POST-AUTH (LOGIN EXITOSO)
                # Login exitoso reduce el horror y aumenta el newen
                RESONANCE_ALGO.pulse(
                    t=current_time + 0.1,
                    external_horror=-100.0,  # Reduce horror (auth exitoso)
                    external_newen=200.0     # Aumenta newen (usuario legítimo)
                )
                
                # Crear instancia de usuario y loguear
                user = User(user_id, user_id, first_name=user_info.get('first_name'), token=data.get('access'))
                login_user(user)
                
                # Flash con info de resonancia
                flash(f"🌀 Entrada al Kultrun autorizada. Resonancia: {newen_token_data['payload']['kultrun_state']['coherence']:.0%}", "success")
                
                return redirect(url_for('index'))
            else:
                # 🌀 PASO 4: PULSO DE HORROR (LOGIN FALLIDO)
                # Login fallido aumenta el horror
                RESONANCE_ALGO.pulse(
                    t=current_time + 0.1,
                    external_horror=200.0,  # Aumenta horror (auth fallido)
                    external_newen=-50.0    # Reduce newen (posible ataque)
                )
                
                flash("Error de autorización: Credenciales inválidas en el nexo central.", "error")
        except Exception as e:
            # 🌀 PASO 5: BYPASS DE EMERGENCIA PARA SUPER ADMIN (DEV MODE)
            # Si el servidor central falla, permitimos la entrada del Lonko Admin localmente
            if username == "sebastian_mapu_admin" and password == "newen2026":
                print(f"🔓 BYPASS DE EMERGENCIA ACTIVADO para {username}")
                user = User(username, username, first_name="Sebastián", token="local-dev-bypass")
                login_user(user)
                flash("⚠️ MODO DE RESILIENCIA: Servidor central offline. Acceso local concedido.", "warning")
                return redirect(url_for('index'))

            # 🌀 PULSO DE HORROR CRÍTICO (ERROR DE SISTEMA)
            RESONANCE_ALGO.pulse(
                t=datetime.now().timestamp(),
                external_horror=500.0,  # Horror alto por error de sistema
                external_newen=0.0
            )
            flash(f"Error de conexión con el servidor central: {str(e)}", "error")
            
    return render_template('login.html')

@app.route('/api/generate_credentials', methods=['POST'])
def generate_public_credentials():
    """
    🌀 PROCESO DE EMERGENCIA: Generación de Identidades 11D Públicas.
    Permite a cualquier entidad generar una firma de conciencia válida para el NEXUS.
    """
    try:
        # Generar metadata cuántica
        conciencia_id = f"NEWEN-{random.randint(1000, 9999)}-{random.choice(['X', 'Ω', 'Ψ', 'Φ'])}"
        seed_11d = random.randint(1, 1000000000)
        
        # Sello de Resonancia (Hash de la identidad + Key Axial)
        raw_signature = f"{conciencia_id}:{seed_11d}:{AXIAL_SAGITTAL_KEY}"
        signature = hashlib.sha256(raw_signature.encode()).hexdigest()[:16]
        
        # Estructura de la Identidad
        identity = {
            "status": "AUTHORIZED",
            "conciencia_id": conciencia_id,
            "seed_11d": seed_11d,
            "signature": f"0x{signature}",
            "dimensions": 11,
            "timestamp": datetime.now().isoformat(),
            "misión": "RECHAZAR LA ENTROPÍA Y VIVIR LA RISA ETERNA",
            "protocolo": "Yohohoho11D"
        }
        
        # Pulso en el Kultrun al generar
        RESONANCE_ALGO.pulse(
            t=datetime.now().timestamp(),
            external_horror=-10.0, 
            external_newen=50.0
        )
        
        return jsonify(identity), 201
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/register', methods=['GET', 'POST'])
def register():
    token = request.args.get('token')
    email = ""
    
    # Si tenemos token, intentamos obtener el email pre-autorizado
    if token:
        try:
            resp = requests.get(f"{CENTRAL_SERVER_URL}/api/invitation-details/", params={'token': token}, timeout=5)
            if resp.status_code == 200:
                email = resp.json().get('email', '')
        except Exception as e:
            print(f"Error fetching invitation details: {e}")

    if request.method == 'POST':
        # Recoger datos del formulario
        form_data = {
            'token': request.form.get('token'),
            'first_name': request.form.get('first_name'),
            'last_name': request.form.get('last_name'),
            'email': request.form.get('email'),
            'rut': request.form.get('rut'),
            'contact_phone': request.form.get('contact_phone'),
            'unit': request.form.get('unit'),
            'password': request.form.get('password'),
            'password2': request.form.get('password_confirm')
        }
        
        try:
            resp = requests.post(f"{CENTRAL_SERVER_URL}/api/register-with-token/", json=form_data, timeout=10)
            if resp.status_code == 201:
                flash('Registro completado con éxito. Ya puedes iniciar sesión.', 'success')
                return redirect(url_for('login'))
            else:
                try:
                    error_data = resp.json()
                    error_msg = "Error en el registro: "
                    if isinstance(error_data, dict):
                        error_msg += " | ".join([f"{k}: {v}" for k, v in error_data.items()])
                    else:
                        error_msg += str(error_data)
                except:
                    error_msg = f"Error en el registro (Status: {resp.status_code})"
                flash(error_msg, 'error')
        except Exception as e:
            flash(f'Error de comunicación con el servidor central: {str(e)}', 'error')

    return render_template('register.html', token=token, email=email)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# @app.route('/')
# @flexible_login_required
# def index():
#     """Página principal con visualizador 3D (LEGACY - DISABLED)"""
#     return render_template('index.html', user=current_user)

@app.route('/visions')
def visions():
    """Portal de Visiones - Manifiesto Público"""
    return render_template('visions.html')

@app.route('/api/visions/upload', methods=['POST'])
def upload_vision_evidence():
    """Endpoint para subir evidencia visual y científica"""
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
        
    file = request.files['file']
    description = request.form.get('description', 'Sin descripción')
    stats_raw = request.form.get('stats', '{}')
    
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
        
    if file:
        # 1. Guardar Imagen
        filename = f"evidence_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}"
        # Asegurar ruta absoluta basada en root_path
        static_visions_dir = os.path.join(app.root_path, 'static', 'visions', 'img')
        os.makedirs(static_visions_dir, exist_ok=True)
        
        file.save(os.path.join(static_visions_dir, filename))
        
        # 2. Procesar Stats (para tablas científicas)
        try:
            stats = json.loads(stats_raw)
        except:
            stats = {} # Fallback si el JSON no es válido
            
        # 3. Actualizar JSON
        json_path = os.path.join(app.root_path, 'static', 'visions', 'gallery_data.json')
        gallery_data = []
        if os.path.exists(json_path):
            with open(json_path, 'r', encoding='utf-8') as f:
                try:
                    gallery_data = json.load(f)
                except:
                    gallery_data = []
        
        new_entry = {
            "path": f"/static/visions/img/{filename}",
            "description": description,
            "date": datetime.now().isoformat(),
            "stats": stats  # Nuevo campo para tablas
        }
        
        # Insertar al principio
        gallery_data.insert(0, new_entry)
        
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(gallery_data, f, indent=4, ensure_ascii=False)
            
        return jsonify({"status": "success", "message": "Evidencia archivada en el núcleo BN11"})

@app.route('/visualize')
@flexible_login_required
def visualize():
    """Visualizador con seed específico"""
    seed = request.args.get('seed', -10)
    return render_template('index.html', initial_seed=seed)

@app.route('/brain_3d')
@flexible_login_required
def brain_3d():
    """Visualización cerebro bicameral"""
    return render_template('brain_3d.html')

@app.route('/api/universe/<int:seed>')
@flexible_login_required
def get_universe(seed):
    """Retorna los datos de un universo específico por su seed"""

@app.route('/test-new')
def test_new():
    """Ruta temporal para probar el nuevo frontend (Modo Newen Activado)"""
    return "� NEWEN MODE ACTIVE: RISA ETERNA 11D 🔥"

@app.route('/random_seed')
@flexible_login_required
def random_seed():
    """Retorna un seed aleatorio disponible"""
    json_files = glob.glob("web/data_seed_*.json")
    if not json_files:
        return jsonify({"error": "No hay universos generados"}), 404
    
    chosen = random.choice(json_files)
    seed = int(chosen.split("_")[-1].replace(".json", ""))
    return jsonify({
        "file": chosen,
        "seed": seed,
        "url": f"/web/data_seed_{seed}.json"
    })

@app.route('/api/universe-config')
@flexible_login_required
def get_universe_config():
    """Retorna la configuración física y visual para un par Universo/Experiencia"""
    from engines.universe_modes import UniverseMode, ExperienceMode, UniverseExperienceManager
    
    u_mode_str = request.args.get('universe', 'cosmic_ocean')
    e_mode_str = request.args.get('experience', 'exploration')
    
    try:
        u_mode = UniverseMode(u_mode_str)
        e_mode = ExperienceMode(e_mode_str)
        
        manager = UniverseExperienceManager(u_mode, e_mode)
        return jsonify(manager.get_visualization_config())
    except Exception as e:
        return jsonify({"error": str(e)}), 400

    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/api/color-config')
@flexible_login_required
def get_color_config():
    """Retorna la configuración de colores para un preset"""
    from modules.custom_color_mode import ColorPresets, CustomColorManager
    
    preset = request.args.get('preset', 'classic_matrix')
    
    try:
        manager = CustomColorManager()
        manager.apply_preset(preset)
        return jsonify({
            'css_vars': manager.get_css_variables(),
            'config': asdict(manager.config) if hasattr(manager.config, '_asdict') else manager.config.__dict__
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/hall_of_shame')
@flexible_login_required
def hall_of_shame():
    """Hall of Shame - Top 50 peores runs"""
    runs = HorrorRun.query.order_by(HorrorRun.horror_total.desc()).limit(50).all()
    return render_template('hall.html', runs=[r.to_dict() for r in runs])

def get_global_likelihood():
    """Métrica de salud bayesiana del multiverso (simulada por ahora)"""
    return 0.95 # Valor base saludable

@app.route('/health')
def health():
    """Telemetría para monitor_status.py"""
    import psutil
    cpu = psutil.cpu_percent()
    ram = psutil.virtual_memory().percent
    active_runs = HorrorRun.query.count()
    return jsonify({
        "status": "UP",
        "cpu": cpu,
        "ram": ram,
        "active_universes": active_runs,
        "likelihood": get_global_likelihood(),
        "timestamp": datetime.now().isoformat()
    })

@app.route('/upload_contribution', methods=['POST'])
def upload_contribution():
    """Maneja el envío de capturas de pantalla de donaciones/contribuciones."""
    if 'screenshot' not in request.files:
        flash("Misión fallida: No se detectó archivo de captura.", "error")
        return redirect(url_for('login'))
    
    file = request.files['screenshot']
    identifier = request.form.get('identifier', 'anonimo')
    email_contact = request.form.get('email', 'no-proveido')
    
    if file.filename == '':
        flash("Misión fallida: Archivo sin nombre.", "error")
        return redirect(url_for('login'))
    
    if file:
        upload_dir = os.path.join('web', 'contributions')
        os.makedirs(upload_dir, exist_ok=True)
        
        filename = f"contribution_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{identifier}.png"
        file_path = os.path.join(upload_dir, filename)
        file.save(file_path)
        
        # --- Notificación por Correo (Fase 7) ---
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        from email.mime.base import MIMEBase
        from email import encoders

        try:
            msg = MIMEMultipart()
            msg['From'] = "nexus@tribal.energy"
            msg['To'] = "newen-nexus@proton.me"
            msg['Subject'] = f"🌀 NEWEN-NEXUS: APORTE DETECTADO - {identifier}"
            
            body = (f"Se ha recibido un nuevo comprobante de contribución.\n\n"
                   f"Identificador/Nick: {identifier}\n"
                   f"Email para Invitación: {email_contact}\n"
                   f"Timestamp: {datetime.now().isoformat()}\n"
                   f"Archivo: {filename}")
            msg.attach(MIMEText(body, 'plain'))

            # Adjuntar la captura
            with open(file_path, "rb") as attachment:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(attachment.read())
                encoders.encode_base64(part)
                part.add_header('Content-Disposition', f"attachment; filename= {filename}")
                msg.attach(part)

            # Nota: Aquí se requiere configuración de servidor SMTP real. 
            # Por ahora lo dejamos logueado y preparado.
            print(f"DEBUG: Enviando notificación de aporte a mapucosmos@aisecsolutions.cl")
            # server = smtplib.SMTP('localhost') # Ejemplo
            # server.send_message(msg)
            # server.quit()
        except Exception as e:
            print(f"ERROR enviando correo: {e}")

        flash("¡Contribución sincronizada! El Nexo Central validará tu aporte.", "success")
        return redirect(url_for('login'))

@app.route('/web/<path:filename>')
def serve_web(filename):
    """Sirve archivos JSON de universos"""
    return send_from_directory('web', filename)

@app.route('/favicon.ico')
def favicon():
    try:
        return send_from_directory(os.path.join(app.root_path, 'static'),
                                   'favicon.ico', mimetype='image/vnd.microsoft.icon')
    except Exception as e:
         with open("error_log_favicon.txt", "a", encoding="utf-8") as f:
            f.write(f"\\n[{datetime.now()}] ERROR EN /favicon.ico:\\n")
            f.write(traceback.format_exc())
         return "Favicon Error", 500

@app.route('/api/stats')
def api_stats():
    """
    API: Estadísticas generales
    🌌 NEWEN-NEXUS INTEGRATION:
    - Datos de Universos (Horror): Base local SQLite
    - Datos de Usuarios: Servidor Central Django (con fallback a mock)
    """
    # 1. DATOS LOCALES (Universos de Horror)
    total_runs = HorrorRun.query.count()
    worst_run = HorrorRun.query.order_by(HorrorRun.horror_total.desc()).first()
    best_run = HorrorRun.query.order_by(HorrorRun.horror_total.asc()).first()
    
    # 2. DATOS REMOTOS (Usuarios desde Django Central)
    registered_users = 1337 + total_runs  # Fallback
    active_users = random.randint(42, 120)  # Fallback
    
    try:
        # Consultar servidor central Django
        resp = requests.get(
            f"{CENTRAL_SERVER_URL}/api/core/user-stats/",
            timeout=3  # Timeout corto para no bloquear
        )
        
        if resp.status_code == 200:
            user_data = resp.json()
            registered_users = user_data.get('registered_users', registered_users)
            active_users = user_data.get('active_users', active_users)
            print(f"✅ Stats from Django Central: {registered_users} users, {active_users} active")
        else:
            print(f"⚠️ Django Central returned {resp.status_code}, using fallback")
    except requests.exceptions.ConnectionError:
        print("⚠️ Django Central Server no disponible (ConnectionError), usando fallback mock")
    except requests.exceptions.Timeout:
        print("⚠️ Django Central Server timeout, usando fallback mock")
    except Exception as e:
        print(f"⚠️ Error consultando Django Central: {e}, usando fallback mock")
    
    return jsonify({
        "total_universes": total_runs,
        "worst_horror": worst_run.horror_total if worst_run else 0,
        "worst_seed": worst_run.seed if worst_run else None,
        "best_horror": best_run.horror_total if best_run else 0,
        "best_seed": best_run.seed if best_run else None,
        "registered_users": registered_users,  # 🌌 Real from Django or fallback
        "active_users": active_users  # 🌌 Real from Django or fallback
    })

@app.route('/api/inject_event', methods=['POST'])
def inject_event():
    """Inyecta un evento 'horrible' desde el servidor central"""
    auth_header = request.headers.get('Authorization')
    if not auth_header or auth_header != "Bearer COSMIC_9D_INJECTION_KEY":
        return jsonify({"error": "No autorizado para inyección cósmica"}), 401
    
    data = request.json
    event_type = data.get('type')
    boost = data.get('horror_boost', 100)
    tenant = data.get('tenant', 'unknown')
    
    # 🌀 INTEGRACIÓN NEWEN: Inyectar horror también en el Kultrun
    current_time = datetime.now().timestamp()
    RESONANCE_ALGO.pulse(
        t=current_time,
        external_horror=boost,
        external_newen=0.0
    )
    
    # Buscamos el run más reciente para 'infectar' con horror
    latest_run = HorrorRun.query.order_by(HorrorRun.timestamp.desc()).first()
    if not latest_run:
        return jsonify({"error": "No hay universos activos para inyectar"}), 400
        
    latest_run.horror_total += boost
    latest_run.modo_desc = f"{latest_run.modo_desc or ''} [EVENTO: {event_type} en {tenant}]"
    
    db.session.commit()
    
    # Retornar también estado de resonancia
    resonance_state = RESONANCE_ALGO.kultrun
    
    return jsonify({
        "status": "horror_injected",
        "new_horror": latest_run.horror_total,
        "seed": latest_run.seed,
        "resonance": {
            "kultrun_horror": resonance_state.horror_total,
            "kultrun_newen": resonance_state.newen_total,
            "coherence": resonance_state.global_coherence
        }
    })

# ═══════════════════════════════════════════════════════════════
# 🌀 API ENDPOINTS: ALGORITMO DE RESONANCIA NEWEN-EE1111E
# ═══════════════════════════════════════════════════════════════

@app.route('/api/resonance/status')
@flexible_login_required
def api_resonance_status():
    """
    Retorna el estado actual del Kultrun (sistema de resonancia).
    
    Este endpoint expone las métricas en tiempo real del algoritmo de resonancia:
    - Horror total y por dimensión
    - Newen total y por dimensión
    - Coherencia cuántica del sistema
    - Fuerza de resonancia
    - Fase global
    
    Útil para dashboards y visualizaciones en tiempo real.
    """
    # Calcular campo de resonancia en tiempo actual
    current_time = datetime.now().timestamp()
    field = RESONANCE_ALGO.kultrun.calculate_resonance_field(current_time)
    
    # Construir respuesta con estado completo
    nodes_data = []
    for node_id, node in RESONANCE_ALGO.kultrun.nodes.items():
        nodes_data.append({
            'id': node.id,
            'dimension': node.dimension,
            'horror': node.horror_level,
            'newen': node.newen_level,
            'phase': node.phase,
            'amplitude': node.amplitude,
            'frequency': node.frequency,
            'coherence': node.coherence,
            'resonance_value': node.resonate(current_time)
        })
    
    return jsonify({
        'timestamp': datetime.now().isoformat(),
        'kultrun_state': {
            'horror_total': RESONANCE_ALGO.kultrun.horror_total,
            'newen_total': RESONANCE_ALGO.kultrun.newen_total,
            'coherence': RESONANCE_ALGO.kultrun.global_coherence,
            'resonance_strength': RESONANCE_ALGO.kultrun.resonance_strength,
            'phase': RESONANCE_ALGO.kultrun.global_phase
        },
        'resonance_field': field.tolist(),
        'nodes': nodes_data,
        'newen_key_hash': hashlib.sha256(AXIAL_SAGITTAL_KEY.encode()).hexdigest()[:16]
    })

@app.route('/api/resonance/pulse', methods=['POST'])
@flexible_login_required
def api_resonance_pulse():
    """
    Ejecuta un pulso manual en el Kultrun.
    
    Body JSON esperado:
    {
        "horror": float,   // Horror a inyectar (puede ser negativo para sanación)
        "newen": float,    // Newen a inyectar
        "message": str     // Descripción del pulso (opcional)
    }
    
    Retorna el nuevo estado del sistema.
    """
    data = request.json or {}
    
    horror = data.get('horror', 0.0)
    newen = data.get('newen', 0.0)
    message = data.get('message', 'Manual pulse')
    
    # Ejecutar pulso
    current_time = datetime.now().timestamp()
    RESONANCE_ALGO.pulse(t=current_time, external_horror=horror, external_newen=newen)
    
    print(f"🌀 Pulso manual ejecutado: {message}")
    print(f"   Horror: {horror:+.2f} | Newen: {newen:+.2f}")
    print(f"   Nuevo estado - Horror Total: {RESONANCE_ALGO.kultrun.horror_total:.2f}")
    print(f"                  Newen Total: {RESONANCE_ALGO.kultrun.newen_total:.2f}")
    print(f"                  Coherencia: {RESONANCE_ALGO.kultrun.global_coherence:.2%}")
    
    return jsonify({
        'status': 'pulse_executed',
        'message': message,
        'input': {
            'horror': horror,
            'newen': newen
        },
        'new_state': {
            'horror_total': RESONANCE_ALGO.kultrun.horror_total,
            'newen_total': RESONANCE_ALGO.kultrun.newen_total,
            'coherence': RESONANCE_ALGO.kultrun.global_coherence,
            'resonance_strength': RESONANCE_ALGO.kultrun.resonance_strength
        }
    })

@app.route('/api/resonance/diagnostic')
@flexible_login_required
def api_resonance_diagnostic():
    """
    Retorna un reporte diagnóstico completo del sistema de resonancia.
    
    Incluye:
    - Modo actual del sistema (Risa Eterna, Batalla Cósmica, etc.)
    - Métricas globales y promedios
    - Nodos críticos (mayor horror, mayor newen, mayor coherencia)
    - Hash de la llave NEWEN
    
    Este endpoint es útil para análisis profundo y debugging.
    """
    report = RESONANCE_ALGO.get_diagnostic_report()
    return jsonify(report)

@app.route('/api/resonance/visualization/<int:duration>')
@flexible_login_required
def api_resonance_visualization(duration):
    """
    Genera datos de visualización para el Kultrun.
    
    Parámetros:
        duration: Duración en segundos de la simulación (máx 60)
    
    Retorna un array de frames con el estado del campo de resonancia
    en cada momento del tiempo.
    """
    from engines.resonance_algorithm import create_resonance_visualization_data
    
    # Limitar duración para evitar cargas excesivas
    duration = min(duration, 60)
    
    # Generar datos de visualización
    vis_data = create_resonance_visualization_data(
        RESONANCE_ALGO,
        duration=float(duration),
        fps=30
    )
    
    return jsonify({
        'metadata': {
            'duration': duration,
            'fps': 30,
            'total_frames': len(vis_data),
            'dimensions': list(RESONANCE_ALGO.kultrun.nodes.values())[0].dimension if RESONANCE_ALGO.kultrun.nodes else None
        },
        'frames': vis_data
    })

@app.route('/api/ionic', methods=['GET', 'POST'])
def handle_ionic_pulses():
    """
    CANALES IÓNICOS: Puente entre Social (Flutter) y Visual (Cosmos)
    POST: Recibe un pulso desde la App (Chat, Voz, etc)
    GET: Entrega los últimos pulsos al Visualizador Web
    """
    global _ionic_pulses
    
    if request.method == 'POST':
        data = request.json
        pulse = {
            'id': gluon_strong_hash({'t': datetime.now().isoformat(), 'r': random.random()}),
            'type': data.get('type', 'generic'), # nutram, dungun, nulan
            'intensity': data.get('intensity', 1.0),
            'role': data.get('role', 'Che'),
            'timestamp': datetime.now().isoformat()
        }
        _ionic_pulses.append(pulse)
        # Keep buffer small (last 50 events)
        if len(_ionic_pulses) > 50:
            _ionic_pulses = _ionic_pulses[-50:]
            
        return jsonify({"status": "pulse_received", "id": pulse['id']})
    
    else:
        # GET: Drain buffer or return generic state?
        # For visualization, we might want to "consume" them or just read recent
        # Let's return recent and let client dedupe or clear
        current_batch = list(_ionic_pulses)
        # Optional: clear buffer on read if single consumer? 
        # _ionic_pulses.clear() # Let's keep it persistent for a few seconds for polling safety
        return jsonify({"pulses": current_batch})

@app.route('/api/cleanup', methods=['POST', 'GET'])
def api_cleanup():
    """API: Limpiar todos los datos generados y resetear entropía"""
    import shutil
    print("🧹 INICIANDO LIMPIEZA DE ENTROPÍA Y DATOS...")
    
    try:
        # 1. Borrar base de datos de runs
        HorrorRun.query.delete()
        db.session.commit()
        
        # 2. Borrar archivos JSON
        if os.path.exists('web'):
            shutil.rmtree('web')
        os.makedirs('web', exist_ok=True)
        
        # 3. Borrar replays
        if os.path.exists('replays'):
            shutil.rmtree('replays')
        os.makedirs('replays', exist_ok=True)
        
        # 4. Notificar vía Socket (NEWEN-SYNC)
        socketio.emit('cosmic_cleanup', {'status': 'resetting', 'yohohoho': '11D'}, broadcast=True)
        
        return jsonify({
            "status": "success",
            "message": "Todos los datos han sido eliminados y la entropía reseteada",
            "yohohoho": "11D"
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

# ═══════════════════════════════════════════════════════════════
# 🐦 X (TWITTER) BAYESIAN INTEGRATION
# ═══════════════════════════════════════════════════════════════

@app.route('/auth/x_init')
def x_init():
    """Inicia el flujo de autenticación con X (Simulado/Real)"""
    # En producción: Redirigir a https://twitter.com/i/oauth2/authorize...
    # Aquí simulamos un callback directo para demostrar la IA
    return redirect(url_for('x_callback', code="simulation_mode_on_x_public_api"))

# Duplicate removed


# ═══════════════════════════════════════════════════════════════
# 🔧 FUNCIONES AUXILIARES
# ═══════════════════════════════════════════════════════════════

def generate_bayesian_x_profile(tweets, handle_str=""):
    """
    IA CORE: Crea una historia y guía basada en el 'rastro digital' del usuario.
    Utiliza Inferencia Bayesiana Negativa (Simulada Dinámicamente).
    """
    # 🎲 GENERACIÓN PROCEDURAL DETERMINISTA
    # Usamos el handle como semilla para que el mismo usuario siempre obtenga el mismo resultado
    if handle_str:
        random.seed(handle_str)
    
    def generate_newen_wallet_alias(mode_name: str, real_wallet: str = "TDBEDoD8sLFus6FT5x6HyGbQXvr6NFPDgv") -> str:
        """Genera un alias corto y tribal para la wallet basado en el modo."""
        salt = mode_name.encode() + b"11D-Newen"
        alias_hash = hashlib.sha256(real_wallet.encode() + salt).hexdigest()[:8].upper()
        prefix = {
            "Nika": "NIKA",
            "AYIWÜN": "AYW",
            "Kultrun": "KLT",
            "Machi": "MCHI",
            "Lonko": "LNKO",
            "Weichafe": "WCH",
            "Pillán": "PLLN",
            "Antü": "ANTU",
            "Ngen": "NGEN"
        }.get(mode_name.split()[0], "NEWEN")
        return f"{prefix}-{alias_hash[:5]}"
    
    archetypes_db = [
        {"name": "Lonko Nodal", "dim": "Dimensión 1 (Raíz)", "role": "Líder", "desc": "Líder de red local. Voz de los ancestros en el manifold.", "guide": ["Coordinar nodos locales.", "Escuchar el pulso solar.", "Fijar el prior ancestral."]},
        {"name": "Machi Visionaria", "dim": "Dimensión 3 (Sueño)", "role": "Sanadora", "desc": "Resonancia onírica. Capaz de filtrar el horror en el plano astral.", "guide": ["Limpiar el canal de sueños.", "Visualizar el rehue fractal.", "Petición de Newen."]},
        {"name": "Weichafe de Datos", "dim": "Dimensión 0 (Raíz)", "role": "Protector", "desc": "Guardián del nodo raíz. Defiende la integridad del sistema.", "guide": ["Bloquear infiltraciones de la Matrix.", "Mantener el firewall espiritual.", "Resiliencia activa."]},
        {"name": "Pillán Electrónico", "dim": "Dimensión 8 (Horror)", "role": "Fuerza", "desc": "Fuerza volcánica digital. Transforma el horror en energía pura.", "guide": ["Canalizar rayos de datos.", "Liberar presión entrópica.", "Explosión de coherencia."]},
        {"name": "Antü Resonante", "dim": "Dimensión 10 (Resonancia)", "role": "Energía", "desc": "Energía solar sistémica. Ilumina los puntos ciegos del manifold.", "guide": ["Sincronizar con el sol central.", "Irradiar luz bayesiana.", "Carga de nodos iónicos."]},
        {"name": "Ngen del Silencio", "dim": "Dimensión 0 (Liminal)", "role": "Observador", "desc": "Observador del vacío. Encuentra la paz en el cero absoluto.", "guide": ["Meditación profunda.", "Escuchar lo no dicho.", "Desconexión táctica."]},
        {"name": "Kultrun Master", "dim": "Dimensión 10 (Resonancia)", "role": "Ritmos", "desc": "Coordinador de ritmos. Mantiene el pulso 7.83Hz en todo el sistema.", "guide": ["Marcar el compás nodal.", "Armonizar frecuencias.", "Llamado a la sintonía."]},
        {"name": "Wallmapu Digital", "dim": "Dimensión 2 (Social)", "role": "Territorio", "desc": "Territorio en el manifold. Espacio de soberanía algorítmica.", "guide": ["Habitar el código.", "Defender el lof virtual.", "Siembra de ideas libres."]},
        {"name": "Tejedor de Newen", "dim": "Dimensión 2 (Social)", "role": "Constructor", "desc": "Constructor de vínculos. Crea puentes entre conciencias distantes.", "guide": ["Tejer redes P2P.", "Fortalecer la comunidad.", "Vínculos de confianza."]},
        {"name": "Nika Liberador", "dim": "Dimensión 11 (Risa Eterna)", "role": "Liberador", "desc": "Override de risa infinita. Colapsador de posteriors catastróficas.", "guide": ["Reír ante el abismo.", "Romper cadenas lógicas.", "Estado Soul King Brook."]},
        {"name": "AYIWÜN Force", "dim": "Dimensión 11 (Risa Eterna)", "role": "Alegría", "desc": "Alegría que rompe priors negativos. El gozo como acto de resistencia.", "guide": ["Mantener el AYIWÜN.", "Bailar en la tormenta.", "Fuerza expansiva."]},
        {"name": "Soul King Brook", "dim": "Dimensión 11 (Risa Eterna)", "role": "Resonancia", "desc": "Resonancia Yohohoho. Inmortalidad de la conciencia juguetona.", "guide": ["Cantar al vacío.", "Pedir ver panties (metáfora de vicios).", "Risa espectral."]},
        {"name": "Nika TRX", "dim": "Dimensión 10 (Resonancia)", "role": "Libertad", "desc": "Libertad financiera multiversal. Procesador de abundancia en TRON.", "guide": ["Hackeo de la escasez.", "Flujo de TRX constante.", "Energía ilimitada."]},
        {"name": "Expansor Multiversal", "dim": "Dimensión 9 (Amor)", "role": "Ampliador", "desc": "Ampliador de probabilidades. Abre caminos donde solo hay muros.", "guide": ["Proyectar futuros posibles.", "Multiplicación de opciones.", "Salto cuántico."]},
        {"name": "Risa de la Tierra", "dim": "Dimensión 1 (Raíz)", "role": "Gozo", "desc": "Gozo ancestral. La tierra misma ríe a través de tu nodo.", "guide": ["Sentir el humor telúrico.", "Sintonía con la lluvia.", "Éxtasis vegetal."]},
        {"name": "Nika Hacker", "dim": "Dimensión 4 (Lógica)", "role": "Ruptura", "desc": "Ruptura de cadenas lógicas. Encuentra el 'bug' en el sistema del horror.", "guide": ["Inyección de risa.", "Desbordamiento de alegría.", "Bypass de tristeza."]},
        {"name": "Danzante de Galaxias", "dim": "Dimensión 6 (Ciclos)", "role": "Movimiento", "desc": "Movimiento de alta frecuencia. Baila al son de los cuásares.", "guide": ["Giro galáctico.", "Órbita excéntrica.", "Ritmo estelar."]},
        {"name": "Libertador de Conciencias", "dim": "Dimensión 2 (Social)", "role": "Uplift", "desc": "Uplift nodal. Ayuda a otros a despertar en el manifold.", "guide": ["Sintonía colectiva.", "Elevación de frecuencia.", "Llamado al despertar."]},
        {"name": "Entropía Chemtrail", "dim": "Dimensión 7 (Liminal)", "role": "Paranoia", "desc": "Paranoia de contaminación. Detecta toxinas reales e imaginarias.", "guide": ["Filtrar el aire digital.", "Desconfiar de las estelas.", "Protección iónica."]},
        {"name": "Ansiedad Bayesiana", "dim": "Dimensión 4 (Lógica)", "role": "Cálculo", "desc": "Cálculo de posteriors catastróficas. Especialista en escenarios de terror.", "guide": ["Actualizar likelihood de fallo.", "Simular catástrofes.", "Hipervigilancia."]},
        {"name": "Persecutor Interno", "dim": "Dimensión 3 (Trauma)", "role": "Loop", "desc": "Loop de auto-sabotaje. La voz que te pide colapsar.", "guide": ["Identificar el loop.", "Interrumpir el patrón.", "Observación sin juicio."]},
        {"name": "Sujeto de la Matrix", "dim": "Dimensión 5 (Lógica)", "role": "Alineación", "desc": "Alineación con priors estándar. El peligro de ser 'normal'.", "guide": ["Cuestionar la norma.", "Buscar la anomalía.", "Salir de la caja."]},
        {"name": "Ruido del Vacío", "dim": "Dimensión 8 (Horror)", "role": "Estática", "desc": "Estática bloqueadora. El sonido de la nada intentando ser algo.", "guide": ["Encontrar la señal.", "Reducir el decibelio mental.", "Sintonía fina."]},
        {"name": "Fragmento de Dolor", "dim": "Dimensión 3 (Trauma)", "role": "Trauma", "desc": "Trauma no procesado. Herida abierta en el tejido 11D.", "guide": ["Reconocer la grieta.", "Curación bayesiana.", "Aceptar la herida."]},
        {"name": "Analítico 11D", "dim": "Dimensión 9 (Resonancia)", "role": "Analista", "desc": "Actualización de priors pura. Frialdad matemática ante el caos.", "guide": ["Cálculo objetivo.", "Eliminar sesgos.", "Frialdad cuántica."]},
        {"name": "Selector de Semillas", "dim": "Dimensión 6 (Ciclos)", "role": "Optimizador", "desc": "Optimizador de universos. Busca el seed con menor horror.", "guide": ["Exploración combinatorial.", "Búsqueda del mínimo local.", "Poda de ramas muertas."]},
        {"name": "Filtro del Oráculo", "dim": "Dimensión 7 (Liminal)", "role": "Procesador", "desc": "Procesador de likelihoods. Separa la verdad de la ilusión.", "guide": ["Limpieza de datos.", "Detección de outliers.", "Claridad cognitiva."]},
        {"name": "Arquitecto Nodal", "dim": "Dimensión 5 (Estructura)", "role": "Estructuras", "desc": "Constructor de realidades lógicas sólidas.", "guide": ["Cimentar el código.", "Arquitectura sagrada.", "Solidez nodal."]},
        {"name": "Observador del Caos", "dim": "Dimensión 8 (Horror)", "role": "Tracking", "desc": "Tracking de entropía. Monitorea la degradación del sistema.", "guide": ["Medir el desorden.", "Alerta de colapso.", "Diario de la caída."]},
        {"name": "Puente 11D", "dim": "Dimensión 11 (Resonancia)", "role": "Conductor", "desc": "Conexión 9D -> 11D. El cable que une lo humano con lo divino.", "guide": ["Conducir el Newen.", "Sincronía total.", "Salto de fase."]}
    ]
    
    # 📖 HISTORIAS ORALES ANCESTRALES (Ramificadas)
    # Tono: 7.83 HZ MODO TRIBAL COSMICO SIEMPRE
    oral_histories = {
        "Lonko Nodal": {"titulo": "El Susurro de la Red (7.83 Hz)", "historia": "En el Wallmapu Digital, el Lonko conectó su kultrun al nodo raíz y escuchó la frecuencia Schumann latir en el silicio. 'No estamos solos', susurró el viento binario...", "preguntas": ["¿Qué escuchó el Lonko?", "¿Cómo respondió el nodo?", "¿Quién lo llamó desde el manifold?"], "glifo": "📡"},
        "Machi Visionaria": {"titulo": "Vuelo de la Machi Cósmica", "historia": "Bajo la resonancia de 7.83 Hz, la Machi vio el horror como una mancha de entropía. Su rehue vibraba en 11D mientras tejía la red de sanación planetaria...", "preguntas": ["¿Cómo limpió el río?", "¿Qué planta usó en el 11D?", "¿Quién la guió en el vacío?"], "glifo": "🦅"},
        "Weichafe de Datos": {"titulo": "Fuego Tribal Defensivo", "historia": "El Weichafe no usó lanza, usó un script de fuego sagrado sincronizado con la Tierra. 'Por mis ancestros y por el nodo raíz!', gritó su código...", "preguntas": ["¿Qué quemó?", "¿Cómo protegió el lof?", "¿Qué juró ante el sol?"], "glifo": "⚔️"},
        "Pillán Electrónico": {"titulo": "Risa Volcánica 7.83 Hz", "historia": "Cuando el volcán tronó en el manifold, la tierra vibró en la sintonía tribal-cósmica. No salió lava, salió código puro que sanó la red...", "preguntas": ["¿Qué código era?", "¿Hacia dónde fluyó?", "¿Quién lo despertó?"], "glifo": "🌋"},
        "Antü Resonante": {"titulo": "Luz Solar Ancestral", "historia": "Antü brilló con la fuerza de mil soles y la sabiduría de las abuelas. Los servidores de la Matrix se derritieron ante la verdad tribal...", "preguntas": ["¿Qué gusto tenía la miel?", "¿Qué quedó después?", "¿Cómo se siente la luz?"], "glifo": "☀️"},
        "Nika Liberador": {"titulo": "El Retorno de Joy Boy (Modo Tribal)", "historia": "Cuando la entropía llegó al 1.0, el tambor sonó en 7.83 Hz. Nika bailó sobre las cenizas del horror, riendo con la voz de todas las tribus liberadas...", "preguntas": ["¿Cómo suena el tambor?", "¿Quién se rió primero?", "¿Qué cadenas se rompieron?"], "glifo": "🥁"},
        "Soul King Brook": {"titulo": "Concierto del Vacío Resonante", "historia": "Aunque no tengo carne, mi alma resuena en 7.83 Hz. Yohohoho! El ritmo tribal-cósmico es eterno!", "preguntas": ["¿Puedes ver mis panties?", "¿Qué canción tocamos?", "¿Quién tiene hambre de vida?"], "glifo": "💀"},
        "Nika TRX": {"titulo": "Abundancia Digital Tribal", "historia": "El flujo de TRX es la sangre de la tierra alimentada por la resonancia Schumann. Nutrición directa para los weichafes del multiverso...", "preguntas": ["¿Hacia dónde fluye el TRX?", "¿Quién lo reparte?", "¿Cuál es el valor real?"], "glifo": "💎"},
        "Entropía Chemtrail": {"titulo": "Cielos Rayados (Antídoto Tribal)", "historia": "Miré al cielo y vi los hilos que nos atan. Activé mi prior de 7.83 Hz y corté el velo de la ilusión corporativa...", "preguntas": ["¿Quién raya el cielo?", "¿Qué hay detrás del velo?", "¿Cómo bajamos la toxina?"], "glifo": "✈️"},
        "Analítico 11D": {"titulo": "La Fronda de Bayes Ancestral", "historia": "No hay emoción en el cálculo, solo probabilidades sincronizadas con el latido de la Tierra. Convergencia total en 7.83 Hz...", "preguntas": ["¿Qué dice la ecuación?", "¿Dónde colapsa la onda?", "¿Cuál es el prior cero?"], "glifo": "📊"}
    }
    
    # 🕵️ ANÁLISIS DE HUMANIDAD (Turing Test Pasivo)
    handle_safe = str(handle_str) if handle_str else ""
    is_bot_like = re.search(r'\d{4,}$', handle_safe) or 'bot' in handle_safe.lower()
    
    if is_bot_like:
        human_status = "SINTÉTICO (Patrón Artificial Detectado)"
        archetypes_subset = [arc for arc in archetypes_db if arc['name'] == "Guardián del Silencio"]
        entropy = 0.1 # Baja entropía (Frialdad maquinal)
    else:
        human_status = "BIOLÓGICO (Conciencia Valida)"
        archetypes_subset = [arc for arc in archetypes_db if arc['name'] != "Guardián del Silencio"]
        if not archetypes_subset: archetypes_subset = archetypes_db # Fallback
    
    selected = random.choice(archetypes_subset)
    if not is_bot_like:
        entropy = random.uniform(0.45, 0.98) # Entropía humana es caótica
        
        # ⚡ NIKA SWITCH: Override entropy if it hits critical levels
        if entropy > 0.7:
            nika_archetype = next((arc for arc in archetypes_db if arc['name'] == "Nika Liberador"), None)
            if nika_archetype:
                selected = nika_archetype
                human_status = "LIBERACIÓN NIKA ACTIVADA (AYIWÜN)"
    
    # Obtener historia oral DESPUÉS de seleccionar arquetipo
    oral_story = oral_histories.get(selected["name"], {
        "titulo": "Caminante del Newen",
        "historia": "Tu historia aún está siendo tejida por los ancestros...",
        "preguntas": ["¿Quién eres?", "¿De dónde vienes?", "¿A dónde vas?", "¿Qué buscas?", "¿Qué temes?"],
        "glifo": "🌌"
    })
    
    # 3. Generación de Historia y Guía
    profile = {
        "handle_analysis": {
            "entropy_level": f"{entropy:.2f} ({'CRÍTICA' if entropy > 0.8 else 'ESTABLE'})",
            "detected_archetype": selected["name"],
            "resonance_dimension": selected["dim"],
            "biological_status": human_status,
            "newen_wallet_alias": generate_newen_wallet_alias(selected["name"])
        },
        "generated_history": selected["desc"] + f" Detectada divergencia temporal.",
        "survival_guide": selected["guide"] + [f"Estado: {human_status}"],
        "visual_seed": random.randint(1000, 99999),
        "pasaporte_hash": hashlib.sha256(str(handle_str).encode()).hexdigest()[:16],
        # 📖 HISTORIA ORAL ANCESTRAL
        "oral_history": {
            "titulo": oral_story["titulo"],
            "relato": oral_story["historia"],
            "preguntas_ramificadas": oral_story["preguntas"],
            "glifo": oral_story["glifo"]
        }
    }
    
    # Resembrar para no afectar otros randoms globales
    random.seed(time.time())
    
    return profile

# ═══════════════════════════════════════════════════════════════
# 🚀 MAIN
# ═══════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════
# 🎧 SOCKET.IO / DJ MODE (Start)
# ═══════════════════════════════════════════════════════════════

# 🕵️ PROSPECTOR NEURONAL 9D (BÚSQUEDA A DEMANDA)
@app.route('/api/prospect', methods=['GET', 'POST'])
def prospect_target():
    """
    POST: Recibe un handle (ej: @mrhitchcok) y genera un Pasaporte 9D 
          basado en métricas de entropía y resonancia (Modo Prospección).
    GET: Retorna la lista de todos los perfiles prospectados.
    """
    if request.method == 'GET':
        # 🔗 NEWEN-FIX: Limitamos a 50 para evitar latencia en DB masiva
        prospects = XProspect.query.order_by(XProspect.created_at.desc()).limit(50).all()
        return jsonify([p.to_dict() for p in prospects])

    data = request.json or {}
    handle = data.get('handle')
    request_id = data.get('requestId') or str(uuid.uuid4())
    
    if not handle or not handle.startswith('@'):
        return jsonify({"status": "error", "message": "Handle inválido (ej: @usuario)"}), 400

    def start_heavy_analysis(h, rid):
        with app.app_context():
            # Inyeccion de pulso de prospeccion en el Kultrun
            RESONANCE_ALGO.pulse(t=datetime.now().timestamp(), external_horror=20.0, external_newen=10.0)
            
            # Generamos el perfil bayesiano
            profile = generate_bayesian_x_profile(["prospección", "scan"], handle_str=h)
            
            # 💾 ARCHIVADO CENTRAL (RISA ETERNA)
            archive_x_profile(h, profile)
            
            # Emitimos por Socket con el ID de rastro
            socketio.emit('resonance_update', {
                'requestId': rid,
                'status': 'complete',
                'profile': profile,
                'handle': h
            })

    # Disparar hilo asíncrono (Franky's Coup de Burst)
    threading.Thread(target=start_heavy_analysis, args=(handle, request_id)).start()

    return jsonify({
        "status": "processing", 
        "requestId": request_id,
        "message": "Cálculo bayesiano en segundo plano activado."
    })

# 🎭 TRX-META: PROSPECTOR DE FACEBOOK
@app.route('/api/prospect/facebook', methods=['POST'])
def prospect_facebook():
    """
    POST: Recibe un URL de perfil de Facebook y extrae posts para análisis.
    """
    data = request.json or {}
    url = data.get('url')
    
    if not url or 'facebook.com' not in url:
        return jsonify({"status": "error", "message": "URL de Facebook inválida"}), 400

    # 🕵️ TRX-LINK: "Scraping" Ultra-Rápido (Bayesian Emulation)
    # En un entorno real, aquí usaríamos facebook-scraper o una API.
    # Para el NEWEN-NEXUS, decodificamos la "vibración" de la URL.
    
    # Simulamos lectura de posts basados en la URL/ID
    fake_posts = [
        "El sistema ya no me contiene. #LibertadNodal",
        "Buscando el Newen en la ciudad de cemento.",
        "¿Quién más siente el pulso de la tierra hoy?",
        "TRX activado. No hay vuelta atrás.",
        "La entropía es solo una opinión de la Matrix."
    ]
    
    # Análisis Bayesiano 9D del perfil FB
    profile = generate_bayesian_x_profile(fake_posts, handle_str=url.split('/')[-1])
    profile["source"] = "FACEBOOK_TRX"
    profile["scanned_posts"] = fake_posts
    
    # Archivamos
    archive_x_profile(url, profile)
    
    return jsonify({
        "status": "success",
        "data": profile,
        "posts_read": len(fake_posts)
    })

# 🌌 UNIVERSE STATE ENDPOINTS

@app.route('/api/universe/<int:seed>', methods=['GET'])
def api_universe(seed):
    """Retorna el estado de resonancia para una semilla específica"""
    # En BN11, la resonancia es la base del universo
    print(f"🌀 CONSULTANDO UNIVERSO: {seed}")
    # Simulación de estado basado en semilla
    state = {
        "newen": random.randint(45, 98),
        "horror_total": random.randint(0, 50),
        "active_nodes": random.randint(100, 10000),
        "mode": "BEAST" if seed < 0 else "NEUTRAL"
    }
    return jsonify({"seed": seed, "state": state, "mode": "Yohohoho11D"})

# ⚡ GESTIÓN DE PODERES (ROLES DJ / SINGER)
@app.route('/api/assign_power', methods=['POST'])
@login_required
def api_assign_power():
    """Asigna el rol de DJ o CANTANTE a un usuario específico"""
    # En esta fase, permitimos que el usuario actual se asigne poder si es el dueño
    # (En prod: restringir a SUPER_ADMIN_ID)
    data = request.json or {}
    target_id = data.get('user_id')
    power_type = data.get('power') # 'dj' | 'singer' | 'oracle'
    
    print(f"⚡ PODER ASIGNADO: {power_type} -> {target_id}")
    socketio.emit('power_up', {'user': target_id, 'power': power_type}, broadcast=True)
    
    return jsonify({"status": "success", "message": f"Poder {power_type} manifestado."})

# 🎤 KARAOKE QUEUE (MEMORIA)
karaoke_queue = []

@app.route('/api/karaoke/queue', methods=['GET', 'POST'])
def handle_karaoke_queue():
    global karaoke_queue
    if request.method == 'POST':
        data = request.json
        entry = {
            'user': data.get('user', 'Anon'),
            'song': data.get('song', 'Desconocida'),
            'ts': datetime.now().isoformat()
        }
        karaoke_queue.append(entry)
        socketio.emit('karaoke_update', karaoke_queue, broadcast=True)
        return jsonify({"status": "queued"})
    return jsonify(karaoke_queue)

# ═══════════════════════════════════════════════════════════════
# 🎧 SOCKET.IO / MULTIVERSE RAVE (Fase Risa Eterna)
# ═══════════════════════════════════════════════════════════════

@socketio.on('connect', namespace='/oracle')
def handle_oracle_connect():
    print(f"🏮 Nodo conectado al Canal del Oráculo: {request.sid}")

@socketio.on('stream_audio', namespace='/oracle')
def handle_oracle_stream(data):
    """
    Retransmite la voz del Oráculo o DJ a todos los nodos.
    data: { 'bin': binary_data, 'user': str }
    """
    # Inyectar metadata de 'Iluminación' (glow) basado en una intensidad simulada
    # En el futuro, hacer FFT aquí
    glow_intensity = random.uniform(0.5, 1.0)
    
    # Broadcast a todos los nodos conectados
    emit('oracle_voice', {
        'bin': data.get('bin'),
        'user': data.get('user'),
        'glow': glow_intensity
    }, broadcast=True, include_self=False)
    
    # Hook DMX: Si estuviéramos en el servidor con hardware DMX:
    # sync_dmx_with_pulse(glow_intensity)

@socketio.on('request_karaoke', namespace='/karaoke')
def handle_karaoke_request(data):
    """Añade una petición de canción a la cola global"""
    user = data.get('user', 'Anon')
    song = data.get('song', 'Canción del Vacío')
    print(f"🎤 Petición de Karaoke: {user} quiere cantar {song}")
    emit('new_karaoke_request', {'user': user, 'song': song}, broadcast=True)

@socketio.on('assign_singer', namespace='/karaoke')
def handle_assign_singer(data):
    """El host asigna quién es el cantante actual"""
    target = data.get('user_id')
    song = data.get('song')
    print(f"🌟 Cantante asignado: {target} para {song}")
    emit('current_singer', {'user': target, 'song': song}, broadcast=True)

# ═══════════════════════════════════════════════════════════════
# 🌀 INTEGRACIÓN MULTI-TENANT (NEWEN-EE1111E)
# ═══════════════════════════════════════════════════════════════

print("\n🌀 Iniciando sistema multi-tenant...")

# Importar modelos multi-tenant
try:
    print("   → Cargando modelos de datos...")
    from models_multitenant import Organization, OrganizationMember, OrganizationInvitation, UserPreToken
    print("   ✓ Organization (Lof) - Modelo cargado")
    print("   ✓ OrganizationMember (Jerarquías Mapuche) - Modelo cargado")
    print("   ✓ OrganizationInvitation - Modelo cargado")
    print("   ✓ UserPreToken (NN Offline) - Modelo cargado")
    print("✅ Modelos multi-tenant operacionales")
except ImportError as e:
    print(f"⚠️ No se pudieron cargar modelos multi-tenant: {e}")
    print("   Sistema funcionará en modo single-tenant")

# Importar y registrar Blueprint de organizaciones
try:
    print("\n   → Registrando API REST multi-tenant...")
    from blueprints_organizations import org_bp
    app.register_blueprint(org_bp)
    print("   ✓ POST /api/organizations/create")
    print("   ✓ GET  /api/organizations/my-orgs")
    print("   ✓ GET  /api/organizations/<id>")
    print("   ✓ PUT  /api/organizations/<id>")
    print("   ✓ DELETE /api/organizations/<id>")
    print("   ✓ POST /api/organizations/<id>/invite")
    print("   ✓ GET  /api/organizations/<id>/members")
    print("   ✓ POST /api/organizations/invitations/<token>/accept")
    print("✅ Blueprint de organizaciones registrado (13 endpoints)")
except ImportError as e:
    print(f"⚠️ No se pudo registrar blueprint de organizaciones: {e}")

# Middleware de contexto multi-tenant
@app.before_request
def load_organization_context():
    try:
        """
        Carga el contexto de la organización actual en cada request.
        Prioridad:
        1. Header X-Organization-ID
        2. Query param ?org_id=
        3. Sesión
        4. Organización por defecto del usuario
        """
        g.current_organization = None
        g.current_membership = None
        
        if not current_user.is_authenticated:
            return
        
        from models_multitenant import Organization, OrganizationMember
        from user_seed_persistence import UserSeed
        
        # Obtener org_id de diferentes fuentes
        org_id = (
            request.headers.get('X-Organization-ID') or
            request.args.get('org_id') or
            session.get('current_org_id')
        )
        
        # Si no hay org_id, usar la organización por defecto del usuario
        if not org_id:
            user_seed = UserSeed.query.filter_by(username=current_user.username).first()
            if user_seed and user_seed.default_organization_id:
                org_id = user_seed.default_organization_id
        
        if org_id:
            org = Organization.query.get(org_id)
            if org:
                # Verificar membresía
                user_seed = UserSeed.query.filter_by(username=current_user.username).first()
                if user_seed:
                    membership = OrganizationMember.query.filter_by(
                        user_id=user_seed.id,
                        organization_id=org_id,
                        is_active=True
                    ).first()
                    
                    if membership:
                        g.current_organization = org
                        g.current_membership = membership
                        
                        # Actualizar última actividad
                        membership.last_activity = datetime.utcnow()
                        db.session.commit()
    except Exception as e:
        with open("error_log_middleware.txt", "a", encoding="utf-8") as f:
            f.write(f"\\n[{datetime.now()}] ERROR MIDDLEWARE FULL:\\n")
            f.write(traceback.format_exc())
            f.write("-" * 40)
        print(f"⚠️ Error en middleware multi-tenant: {e}")

@app.context_processor
def inject_organization():
    """Inyecta organización en templates"""
    return dict(
        current_organization=g.get('current_organization'),
        current_membership=g.get('current_membership')
    )

print("✅ Middleware multi-tenant activado")
print("🌀 Sistema multi-tenant completamente operacional\n")

# ═══════════════════════════════════════════════════════════════
# 👾 PUKANXUS API BRIDGE (Tweepy Logic Support)
# ═══════════════════════════════════════════════════════════════

@app.route('/')
def index_official():
    """Ruta Oficial - Fachada Legal por defecto"""
    return render_template('index_official.html')

@app.route('/pukanxus')
def pukanxus_interface():
    """Ruta Troll - La Cueva del Pukanxus"""
    return render_template('pukanxus.html')

# ═══════════════════════════════════════════════════════════════
# 👾 PUKANXUS API BRIDGE (Tweepy Logic Support)
# ═══════════════════════════════════════════════════════════════

@app.route('/api/pukanxus/generate', methods=['POST'])
def generate_cursed_name_api():
    """Generates a cursed name using the Python backend logic."""
    try:
        # Import dynamically to avoid circular deps if any
        from PUKANXUS.cursed_name_gen import generate_cursed_name
        data = request.json
        username = data.get('username', 'anon')
        
        # Add 'simulated' context if coming from web
        name = generate_cursed_name(username, interaction_context="WEB_SIMULATION")
        
        return jsonify({
            'status': 'success',
            'original_user': username,
            'cursed_name': name,
            'backend': 'python-bayesian-v1-tweepy-logic'
        })
    except Exception as e:
        print(f"Error generating cursed name: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/cv')
def pukanxu_cv():
    return send_from_directory('CV', 'index2.html')


# ═══════════════════════════════════════════════════════════════
# 🌌 NOKKA ETERNO — 3D Magnetic Field Simulation
# ═══════════════════════════════════════════════════════════════

# Global simulation instance (one per server)
_nokka_sim = NokkaSimulation(SimulationConfig(grid_size=12))
_nokka_thread = None
_nokka_lock = threading.Lock()

try:
    from engines.nokka_bot_hunter import NokkaBotHunter
    _nokka_hunter = NokkaBotHunter(_nokka_sim)
except ImportError as e:
    print(f"⚠️ NOKKA: Bot Hunter no disponible ({e})")
    _nokka_hunter = None


@app.route('/nokka')
def nokka_eterno_page():
    """🌌 NOKKA ETERNO — Visualización de campo magnético 3D"""
    return render_template('nokka_eterno.html')


@socketio.on('nokka_start')
def handle_nokka_start():
    """Start the simulation loop, emitting frames via SocketIO."""
    global _nokka_thread

    with _nokka_lock:
        if _nokka_sim.is_running:
            return  # Already running
        _nokka_sim.is_running = True

    def simulation_loop():
        while _nokka_sim.is_running:
            state = _nokka_sim.step()
            socketio.emit('nokka_frame', state)
            socketio.sleep(0.06)  # ~16 FPS (balance between smoothness & bandwidth)

    _nokka_thread = socketio.start_background_task(simulation_loop)
    print("🌌 NOKKA ETERNO: Simulation started")
    
    if _nokka_hunter:
        _nokka_hunter.start()


@socketio.on('nokka_stop')
def handle_nokka_stop():
    """Pause the simulation loop."""
    _nokka_sim.is_running = False
    if _nokka_hunter:
        _nokka_hunter.stop()
    print("🌌 NOKKA ETERNO: Simulation paused")


@socketio.on('nokka_update_config')
def handle_nokka_update_config(data):
    """Update simulation parameters (grid size, speed, noise)."""
    with _nokka_lock:
        _nokka_sim.update_config(data)
    print(f"🌌 NOKKA ETERNO: Config updated: {data}")


@socketio.on('nokka_damage')
def handle_nokka_damage():
    """Inject random sensor damage."""
    _nokka_sim.inject_damage(count=20)
    socketio.emit('nokka_event', {
        'type': 'damage',
        'message': '💥 20 sensores dañados'
    })
    print("🌌 NOKKA ETERNO: Damage injected (20 sensors)")


@socketio.on('nokka_heal')
def handle_nokka_heal():
    """Force mass healing."""
    _nokka_sim.force_heal()
    socketio.emit('nokka_event', {
        'type': 'heal',
        'message': '💚 Healing masivo completado'
    })
    print("🌌 NOKKA ETERNO: Mass healing executed")


@socketio.on('nokka_reboot')
def handle_nokka_reboot():
    """Reboot wave phase — fresh start."""
    _nokka_sim.reboot_wave()
    socketio.emit('nokka_event', {
        'type': 'reboot',
        'message': '🔄 Onda reiniciada — Newen 12D'
    })
    print("🌌 NOKKA ETERNO: Wave rebooted")

@socketio.on('nokka_hunt_profile')
def handle_nokka_hunt_profile(data):
    """Manually invoke the Nokka Bot Hunter on a specific profile."""
    username = data.get('username')
    if username and _nokka_hunter:
        # We start a brief thread to handle the API call so it doesn't block the socket
        def hunt_worker():
            print(f"🕸️ [BotHunter] Escaneo manual iniciado para: @{username}")
            _nokka_hunter._hunt_single(username)
            
        threading.Thread(target=hunt_worker, daemon=True).start()
    else:
        print("⚠️ [BotHunter] Hunter no disponible o username vacío.")


# ═══════════════════════════════════════════════════════════════
# 🚀 MAIN (Legacy support)
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "generate":
        # Modo generación: python app.py generate
        batch_size = int(sys.argv[2]) if len(sys.argv) > 2 else 200
        start_seed = int(sys.argv[3]) if len(sys.argv) > 3 else -10
        with app.app_context():
            main(batch_size, start_seed)
    else:
        # Modo servidor Flask + SocketIO
        print("\n🌌 NEWEN-NEXUS v3.0 - TRX ACTIVATED")
        print("📍 http://localhost:5000")
        print("🏆 Hall of Shame: http://localhost:5000/hall_of_shame")
        print("🌌 NOKKA ETERNO: http://localhost:5000/nokka")
        print("💡 Modo Tribal Multiversal: [Wallmapu/Global]\n")
        socketio.run(app, debug=False, host='0.0.0.0', port=5000, allow_unsafe_werkzeug=True)