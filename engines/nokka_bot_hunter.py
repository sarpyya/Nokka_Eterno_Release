import tweepy
import numpy as np
import time
import hashlib
import threading

# ================== CONFIG ==================
# ATENCIÓN: Necesitas reemplazar esto con un Bearer Token válido de Twitter/X API v2
BEARER_TOKEN = "INGRESA_TU_BEARER_TOKEN_AQUI"

class NokkaBotHunter:
    """
    Filtro Nodal 9D+1: Convierte perfiles de X en ondas magnónicas.
    Interactúa con una instancia viva de NokkaSimulation.
    """
    def __init__(self, nokka_sim):
        self.nokka = nokka_sim
        self.client = None
        self._running = False
        self._thread = None
        
        try:
            self.client = tweepy.Client(bearer_token=BEARER_TOKEN)
        except Exception as e:
            print(f"⚠️ [BotHunter] Error al iniciar Tweepy: {e}")

    def start(self, usernames=None):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._hunt_loop, args=(usernames,), daemon=True)
        self._thread.start()
        print("🕸️ [BotHunter] Filtro Nodal 9D+1 Activado. Cazando sombras...")

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
        print("🛑 [BotHunter] Cacería detenida.")

    def _hash_to_coord(self, username: str, N: int):
        h = int(hashlib.md5(username.encode()).hexdigest(), 16)
        return (h % N, (h // N) % N, (h // (N*N)) % N)

    def _profile_to_phase_distortion(self, user):
        # Vectores de comportamiento → onda 9D
        metrics = user.public_metrics
        
        # 1. Frecuencia de posteo (X)
        days_active = max(1, (time.time() - user.created_at.timestamp()) / 86400)
        freq = metrics['tweet_count'] / days_active
        
        # 2. Ratio de influencia (Y)
        ratio = metrics['followers_count'] / max(1, metrics['following_count'])
        
        # 3. Entropía de Bio (Z)
        bio = user.description.lower() if user.description else ""
        bio_entropy = len(set(bio)) / max(1, len(bio))
        
        # 4. Amplitud (Filtro Bayesiano Negativo básico)
        # Bots típicos usan bios repetitivas, sin foto, o keywords sospechosas
        amp = 1.0
        suspect_keywords = ["bot", "crypto", "giveaway", "follow back", "18+"]
        if any(kw in bio for kw in suspect_keywords) or metrics['followers_count'] < 5:
            amp = -1.0  # Onda destructiva
            
        phase_shift = np.array([
            np.sin(freq * 0.1) * 0.8,
            np.cos(ratio * 2.0) * 0.6,
            bio_entropy * 3.14
        ])
        return phase_shift, amp

    def _hunt_loop(self, usernames=None):
        if not self.client:
            print("⚠️ [BotHunter] Sin token X API. Iniciando 👻 DEMO MODE OFFLINE...")
            self._demo_loop()
            return

        # Si no se provee lista, usa estos por defecto para la demo
        if not usernames:
            usernames = ["elonmusk", "x_anxi_ety", "X", "OpenAI", "NASA"]

        while self._running:
            for username in usernames:
                if not self._running:
                    break
                    
                try:
                    user = self.client.get_user(
                        username=username, 
                        user_fields=['created_at', 'public_metrics', 'description']
                    ).data
                    
                    if not user:
                        continue
                        
                    with self.nokka._lock:
                        N = self.nokka.config.grid_size
                        coord = self._hash_to_coord(username, N)
                        distortion, amp = self._profile_to_phase_distortion(user)
                        
                        # INYECCIÓN AL RESERVORIO (Modula la fase base)
                        # Aplica el vector de distorsión al tensor 3D en la coordenada exacta
                        self.nokka._phase[coord] += np.sum(distortion) * amp * 2.0
                        
                        # Trigger de entropía/newen
                        if amp > 0:
                            # Aliado -> Fuerza curación pasiva en la malla
                            self.nokka._apply_healing() 
                            print(f"✅ [{username}] Resonancia Armónica. Nodo reforzado.")
                        else:
                            # Bot -> Daño masivo focalizado (Bayesian Negative)
                            # Simulamos daño en el nodo y vecinos
                            self.nokka._sensors_active[coord] = False
                            self.nokka._grid[coord] *= 0.01
                            print(f"🚨 [{username}] Interferencia Destructiva! (Bot/Troll detectado)")
                            
                except tweepy.errors.Unauthorized:
                    print(f"⚠️ [BotHunter] 401 Unauthorized. Token inválido. Cambiando a DEMO MODE OFFLINE...")
                    self.client = None
                    self._demo_loop()
                    return
                except Exception as e:
                    print(f"⚠️ [BotHunter] Error escaseando a {username}: {e}")
                
                # Latencia orgánica (Rate Limiting de X API)
                time.sleep(2.5) 
                
            # Pequeña pausa antes de volver a escanear la lista
            time.sleep(10.0)

    def _demo_loop(self):
        """Simula perfiles orgánicos y bots si no hay API Token"""
        demo_profiles = [
            {"name": "skymapumin", "is_bot": False, "amp": 1.5, "desc": "Aliada ancestral"},
            {"name": "bot_crypto_99", "is_bot": True, "amp": -2.0, "desc": "Interferencia Financiera"},
            {"name": "unknowgirlXR", "is_bot": False, "amp": 1.2, "desc": "Alta creatividad"},
            {"name": "troll_politico", "is_bot": True, "amp": -1.8, "desc": "Rigidez ideológica"}
        ]
        
        while self._running:
            for p in demo_profiles:
                if not self._running: break
                
                with self.nokka._lock:
                    N = self.nokka.config.grid_size
                    coord = self._hash_to_coord(p["name"], N)
                    
                    # Simular distorsión
                    distortion = np.array([np.random.rand(), np.random.rand(), np.random.rand()])
                    
                    # Inyección
                    self.nokka._phase[coord] += np.sum(distortion) * p["amp"] * 2.0
                    
                    if not p["is_bot"]:
                        self.nokka._apply_healing()
                        print(f"✅ [DEMO: {p['name']}] Resonancia Armónica. ({p['desc']})")
                    else:
                        self.nokka._sensors_active[coord] = False
                        self.nokka._grid[coord] *= 0.01
                        print(f"🚨 [DEMO: {p['name']}] Interferencia! ({p['desc']})")
                        
                time.sleep(3.0)

    def _hunt_single(self, username: str):
        """Escanea un único perfil bajo demanda (Manual Scan)"""
        try:
            if not self.client:
                raise tweepy.errors.Unauthorized(None) # Force offline mode demo
                
            user = self.client.get_user(
                username=username, 
                user_fields=['created_at', 'public_metrics', 'description']
            ).data
            
            if user:
                with self.nokka._lock:
                    N = self.nokka.config.grid_size
                    coord = self._hash_to_coord(username, N)
                    distortion, amp = self._profile_to_phase_distortion(user)
                    
                    self.nokka._phase[coord] += np.sum(distortion) * amp * 20.0 # Más fuerte visualmente
                    if amp > 0:
                        self.nokka._apply_healing()
                        print(f"✅ [MANUAL: {username}] Aliada Ancestral.")
                    else:
                        self.nokka._sensors_active[coord] = False
                        self.nokka._grid[coord] *= 0.01
                        print(f"🚨 [MANUAL: {username}] Bot/Troll Detectado.")
                        
        except Exception as e:
            # Fallback determinista si no hay API: usamos el hash para decidir si es bot
            h = int(hashlib.md5(username.encode()).hexdigest(), 16)
            is_bot = (h % 3 == 0) # 1 in 3 chance of being flagged as bot in demo
            
            with self.nokka._lock:
                N = self.nokka.config.grid_size
                coord = self._hash_to_coord(username, N)
                distortion = np.array([np.random.rand(), np.random.rand(), np.random.rand()])
                amp = -2.0 if is_bot else 1.5
                
                self.nokka._phase[coord] += np.sum(distortion) * amp * 20.0
                
                if not is_bot:
                    self.nokka._apply_healing()
                    print(f"✅ [OFFLINE-SCAN: {username}] Resonancia Simulada.")
                else:
                    self.nokka._sensors_active[coord] = False
                    self.nokka._grid[coord] *= 0.01
                    print(f"🚨 [OFFLINE-SCAN: {username}] Interferencia Simulada!")
