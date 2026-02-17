# -*- coding: utf-8 -*-
"""
BlockBreach INFINITY 14.2 - Learning Edition
Recoil Plugin - Lê config do Lunar e aplica via GHUB DLL
"""

import warnings
warnings.filterwarnings("ignore")

import sys
import os
import time
import csv
import json
import ctypes
import threading
from dataclasses import dataclass
from typing import Dict, Any, Optional, Tuple
from datetime import datetime

sys.dont_write_bytecode = True

# ==============================================================================
# PATHS
# ==============================================================================
SCRIPT_PATH = os.path.realpath(__file__)
SCRIPT_DIR = os.path.dirname(SCRIPT_PATH)
LIB_DIR = os.path.dirname(SCRIPT_DIR)

CONFIG_DIR = os.path.join(LIB_DIR, "config")
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")
DLL_PATH = os.path.join(SCRIPT_DIR, "ghub_mouse.dll")

USER_PROFILE = os.environ.get('USERPROFILE', os.path.expanduser("~"))
LEARNING_DIR = os.path.join(USER_PROFILE, "GlueLearning")
os.makedirs(LEARNING_DIR, exist_ok=True)

TELEMETRY_CSV = os.path.join(LEARNING_DIR, "telemetry.csv")
DEBUG_LOG = os.path.join(LEARNING_DIR, "debug.log")


# ==============================================================================
# DEBUG LOGGER
# ==============================================================================
def debug_log(msg: str):
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        with open(DEBUG_LOG, 'a', encoding='utf-8') as f:
            f.write(f"[{timestamp}] {msg}\n")
        print(f"[RECOIL] {msg}")
    except:
        pass

debug_log("="*70)
debug_log("Recoil Plugin v14.2 - Lunar Config + GHUB DLL")
debug_log(f"Config: {CONFIG_PATH}")
debug_log(f"DLL: {DLL_PATH}")
debug_log("="*70)


# ==============================================================================
# CONFIGURAÇÃO (Lê do config.json do Lunar)
# ==============================================================================
@dataclass
class RecoilConfig:
    enabled: bool = True
    y_strength: float = 1.8
    x_strength: float = 0.0
    ramp_up: float = 0.8
    recover: float = 4.0
    smoothing: float = 0.1
    apply_interval: float = 0.001  # 1ms (1000Hz)
    primary_key: int = 0x06


def load_config() -> RecoilConfig:
    """Carrega configurações do config.json do Lunar"""
    cfg = RecoilConfig()
    
    if not os.path.exists(CONFIG_PATH):
        debug_log(f"AVISO: Config nao encontrado em {CONFIG_PATH}")
        debug_log("Usando valores padrao")
        return cfg
    
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Lê configurações de recoil
        if 'recoil' in data:
            rec = data['recoil']
            cfg.enabled = bool(rec.get('enabled', True))
            cfg.y_strength = float(rec.get('y_strength', 1.8))
            cfg.x_strength = float(rec.get('x_strength', 0.0))
            cfg.ramp_up = float(rec.get('ramp_up', 0.8))
            cfg.recover = float(rec.get('recover', 4.0))
            cfg.smoothing = float(rec.get('smoothing', 0.1))
            cfg.apply_interval = float(rec.get('apply_interval', 0.001))
            
            debug_log(f"Recoil config: Y={cfg.y_strength}, X={cfg.x_strength}, "
                     f"Ramp={cfg.ramp_up}, Recover={cfg.recover}")
        else:
            debug_log("Secao 'recoil' nao encontrada, usando padroes")
        
        # Lê keybind primária
        if 'keybinds' in data:
            kb = data['keybinds']
            primary = kb.get('primary', '0x06')
            cfg.primary_key = int(primary, 16) if isinstance(primary, str) else int(primary)
            debug_log(f"Primary key: 0x{cfg.primary_key:02X}")
        
    except Exception as e:
        debug_log(f"ERRO ao carregar config: {e}")
        import traceback
        debug_log(traceback.format_exc())
    
    return cfg


# ==============================================================================
# MOUSE DRIVER (GHUB DLL)
# ==============================================================================
class GHubMouseDriver:
    """Driver de mouse usando GHUB DLL"""
    
    def __init__(self, dll_path: str):
        self.dll = None
        self.move_count = 0
        self.total_x = 0
        self.total_y = 0
        self.initialized = False
        
        if not os.path.exists(dll_path):
            debug_log(f"ERRO: GHUB DLL nao encontrada em {dll_path}")
            debug_log("Recoil NAO sera aplicado ao mouse!")
            return
        
        try:
            self.dll = ctypes.CDLL(dll_path)
            self.dll.moveR.argtypes = [ctypes.c_int, ctypes.c_int]
            self.initialized = True
            debug_log(f"GHUB DLL carregada com sucesso: {os.path.basename(dll_path)}")
        except Exception as e:
            debug_log(f"ERRO ao carregar GHUB DLL: {e}")
    
    def move(self, x: int, y: int) -> bool:
        """Move mouse relativamente"""
        if not self.initialized or self.dll is None:
            return False
        
        # Ignora movimentos muito pequenos
        if abs(x) < 1 and abs(y) < 1:
            return False
        
        try:
            self.dll.moveR(int(x), int(y))
            self.move_count += 1
            self.total_x += x
            self.total_y += y
            return True
        except Exception as e:
            if self.move_count % 100 == 0:
                debug_log(f"Erro ao mover mouse: {e}")
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        return {
            'initialized': self.initialized,
            'move_count': self.move_count,
            'total_x': self.total_x,
            'total_y': self.total_y
        }


# ==============================================================================
# RECOIL ENGINE
# ==============================================================================
class RecoilEngine:
    """Motor de compensação de recoil"""
    
    def __init__(self, config: RecoilConfig):
        self.config = config
        self.active_time = 0.0
        self.current_y = 0.0
        self.current_x = 0.0
        self.accumulated_y = 0.0  # Acumula valores fracionários
        self.accumulated_x = 0.0
        self.peak_recoil = 0.0
        self.is_active = False
        self.total_shots = 0
        self.update_count = 0
        
        debug_log(f"RecoilEngine: Y={config.y_strength}, X={config.x_strength}, "
                 f"Enabled={config.enabled}")
    
    def update(self, is_shooting: bool, dt: float = 0.001) -> Tuple[float, float]:
        """
        Atualiza recoil e retorna valores atuais
        
        Args:
            is_shooting: Se está atirando
            dt: Delta time em segundos
            
        Returns:
            Tuple (current_x, current_y)
        """
        self.update_count += 1
        self.is_active = is_shooting
        
        if not self.config.enabled:
            return 0.0, 0.0
        
        if is_shooting:
            # Primeiro frame atirando
            if self.active_time == 0.0:
                self.total_shots += 1
                if self.total_shots <= 5:
                    debug_log(f"Shot #{self.total_shots}")
            
            # Rampa de subida
            self.active_time += dt
            ramp = min(1.0, self.active_time / self.config.ramp_up)
            
            # Calcula alvos
            target_y = ramp * self.config.y_strength
            target_x = ramp * self.config.x_strength
            
            # Suavização
            self.current_y += (target_y - self.current_y) * self.config.smoothing
            self.current_x += (target_x - self.current_x) * self.config.smoothing
            
            self.peak_recoil = max(self.peak_recoil, self.current_y)
            
        else:
            # Recuperação (decay)
            if self.active_time > 0.0:
                debug_log(f"Parou de atirar (tempo ativo: {self.active_time:.2f}s)")
            
            self.active_time = 0.0
            decay = self.config.recover * dt * 100  # Decay mais rápido
            
            self.current_y = max(0.0, self.current_y - decay)
            self.current_x *= 0.95  # Decay do X
            
            # Zera se muito pequeno
            if abs(self.current_y) < 0.01:
                self.current_y = 0.0
            if abs(self.current_x) < 0.01:
                self.current_x = 0.0
        
        return self.current_x, self.current_y
    
    def get_movement_delta(self, dt: float) -> Tuple[int, int]:
        """
        Retorna movimento incremental para aplicar ao mouse
        Acumula valores fracionários
        
        Returns:
            Tuple (delta_x, delta_y) em pixels inteiros
        """
        # Movimento necessário neste frame
        # Multiplica por dt*1000 para normalizar
        move_x = self.current_x * dt * 1000
        move_y = self.current_y * dt * 1000
        
        # Acumula
        self.accumulated_x += move_x
        self.accumulated_y += move_y
        
        # Extrai parte inteira
        int_x = int(self.accumulated_x)
        int_y = int(self.accumulated_y)
        
        # Mantém parte fracionária
        self.accumulated_x -= int_x
        self.accumulated_y -= int_y
        
        return int_x, int_y
    
    def reset(self):
        """Reseta estado"""
        self.active_time = 0.0
        self.current_y = 0.0
        self.current_x = 0.0
        self.accumulated_y = 0.0
        self.accumulated_x = 0.0
        debug_log("Recoil resetado")
    
    def get_stats(self) -> Dict[str, Any]:
        return {
            'enabled': self.config.enabled,
            'current_x': self.current_x,
            'current_y': self.current_y,
            'accumulated_x': self.accumulated_x,
            'accumulated_y': self.accumulated_y,
            'peak': self.peak_recoil,
            'active_time': self.active_time,
            'is_active': self.is_active,
            'total_shots': self.total_shots,
            'update_count': self.update_count
        }


# ==============================================================================
# LEARNING SYSTEM
# ==============================================================================
class LearningSystem:
    def __init__(self):
        self.session_start = time.time()
        self.telemetry_count = 0
        self._init_files()
    
    def _init_files(self):
        if not os.path.exists(TELEMETRY_CSV):
            try:
                with open(TELEMETRY_CSV, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow([
                        "Timestamp", "Recoil_Y", "Mouse_Moved_Y",
                        "Is_Shooting", "Total_Shots"
                    ])
            except:
                pass
    
    def log(self, recoil_y: float, mouse_y: int, is_shooting: bool, total_shots: int):
        try:
            self.telemetry_count += 1
            with open(TELEMETRY_CSV, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                    f"{recoil_y:.3f}",
                    mouse_y,
                    is_shooting,
                    total_shots
                ])
        except:
            pass


# ==============================================================================
# INSTÂNCIAS GLOBAIS
# ==============================================================================
_config: Optional[RecoilConfig] = None
_engine: Optional[RecoilEngine] = None
_mouse: Optional[GHubMouseDriver] = None
_learning: Optional[LearningSystem] = None
_initialized = False
_auto_running = False
_session_id = ""


# ==============================================================================
# API PÚBLICA
# ==============================================================================

def init(config: Any = None) -> bool:
    """Inicializa o plugin"""
    global _config, _engine, _mouse, _learning, _initialized, _session_id
    
    if _initialized:
        return True
    
    debug_log("init() chamado")
    
    try:
        _config = load_config()
        _engine = RecoilEngine(_config)
        _mouse = GHubMouseDriver(DLL_PATH)
        _learning = LearningSystem()
        _session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        _initialized = True
        
        debug_log(f"Plugin inicializado! Session: {_session_id}")
        debug_log(f"  Mouse Driver: {'OK' if _mouse.initialized else 'FAILED'}")
        
        return True
    except Exception as e:
        debug_log(f"ERRO em init(): {e}")
        import traceback
        debug_log(traceback.format_exc())
        return False


def start() -> bool:
    """Inicia o plugin e loop de auto-update"""
    if not _initialized:
        init()
    
    _start_auto_loop()
    return _initialized


def stop():
    """Para o plugin"""
    global _initialized, _auto_running
    _auto_running = False
    _initialized = False
    debug_log("Plugin parado")


def reload_config():
    """Recarrega config do Lunar"""
    global _config
    debug_log("Recarregando config...")
    _config = load_config()
    if _engine:
        _engine.config = _config
    debug_log("Config recarregado")


def get_stats() -> Dict[str, Any]:
    """Retorna estatísticas"""
    if not _initialized:
        return {'initialized': False}
    
    return {
        'initialized': _initialized,
        'auto_running': _auto_running,
        'session_id': _session_id,
        'engine': _engine.get_stats() if _engine else {},
        'mouse': _mouse.get_stats() if _mouse else {}
    }


# ==============================================================================
# AUTO-UPDATE LOOP (Aplica recoil automaticamente)
# ==============================================================================
def _auto_update_loop():
    """Loop que monitora input e aplica recoil via GHUB DLL"""
    global _auto_running
    
    debug_log("="*70)
    debug_log("AUTO-UPDATE LOOP INICIADO")
    debug_log("Aplicando recoil automaticamente via GHUB DLL")
    debug_log("="*70)
    
    if not _mouse or not _mouse.initialized:
        debug_log("ERRO: Mouse driver nao inicializado!")
        debug_log("Recoil sera calculado mas NAO aplicado!")
    
    u32 = ctypes.windll.user32
    last_t = time.perf_counter()
    last_log = time.time()
    last_shooting = False
    
    _auto_running = True
    
    interval = _config.apply_interval if _config else 0.001
    debug_log(f"Intervalo de aplicacao: {interval*1000:.1f}ms")
    
    while _auto_running and _initialized:
        try:
            curr_t = time.perf_counter()
            dt = curr_t - last_t
            last_t = curr_t
            
            # Detecta se está atirando
            primary_key = _config.primary_key if _config else 0x06
            is_shooting = (u32.GetAsyncKeyState(primary_key) & 0x8000) != 0
            
            # Log mudança de estado
            if is_shooting != last_shooting:
                debug_log(f"{'Comecou' if is_shooting else 'Parou de'} atirar")
                last_shooting = is_shooting
            
            # Atualiza engine
            if _engine:
                _engine.update(is_shooting, dt)
                
                # Pega movimento incremental
                move_x, move_y = _engine.get_movement_delta(dt)
                
                # Aplica ao mouse se houver movimento
                if _mouse and _mouse.initialized and (move_x != 0 or move_y != 0):
                    _mouse.move(move_x, move_y)
                
                # Log telemetria a cada 60 updates
                if _learning and _engine.update_count % 60 == 0:
                    _learning.log(
                        _engine.current_y,
                        move_y,
                        is_shooting,
                        _engine.total_shots
                    )
            
            # Log a cada 5 segundos
            if time.time() - last_log >= 5.0:
                stats = _engine.get_stats() if _engine else {}
                mouse_stats = _mouse.get_stats() if _mouse else {}
                
                debug_log(f"[AUTO] Shots: {stats.get('total_shots', 0)} | "
                         f"Recoil: {stats.get('current_y', 0):.3f} | "
                         f"Mouse Moves: {mouse_stats.get('move_count', 0)} | "
                         f"Active: {is_shooting}")
                
                last_log = time.time()
            
            # Sleep
            time.sleep(interval)
            
        except Exception as e:
            debug_log(f"ERRO no auto-update loop: {e}")
            time.sleep(1)
    
    debug_log("AUTO-UPDATE LOOP FINALIZADO")


def _start_auto_loop():
    """Inicia thread de auto-update"""
    global _auto_running
    
    if not _auto_running:
        debug_log("Iniciando auto-update thread...")
        thread = threading.Thread(target=_auto_update_loop, daemon=True, name="RecoilAuto")
        thread.start()
        debug_log("Auto-update thread iniciada!")


# ==============================================================================
# CLASSE PLUGIN
# ==============================================================================
class Plugin:
    name = "recoil"
    version = "14.2-LUNAR-GHUB"
    
    def __init__(self):
        debug_log("Plugin.__init__() chamado")
        self.initialized = False
    
    def init(self, config=None):
        self.initialized = init(config)
        return self.initialized
    
    def start(self):
        return start()
    
    def stop(self):
        return stop()
    
    def reload_config(self):
        return reload_config()
    
    def get_stats(self):
        return get_stats()


class RecoilPlugin(Plugin):
    pass


plugin = Plugin()
recoil_plugin = plugin


# ==============================================================================
# AUTO-INIT E START
# ==============================================================================
debug_log("Executando auto-init...")
init()

debug_log("Iniciando auto-update em 3 segundos...")

def _delayed_start():
    time.sleep(3)
    debug_log("="*70)
    debug_log("ATIVANDO RECOIL AUTOMATICO")
    debug_log("Lendo config de: " + CONFIG_PATH)
    debug_log("Aplicando via: GHUB DLL")
    debug_log("="*70)
    start()

threading.Thread(target=_delayed_start, daemon=True).start()


# ==============================================================================
# STANDALONE
# ==============================================================================
if __name__ == "__main__":
    os.system('cls' if os.name == 'nt' else 'clear')
    
    print("=" * 70)
    print(" RECOIL PLUGIN - LUNAR CONFIG + GHUB DLL")
    print("=" * 70)
    
    print(f"\n[CONFIG] Path: {CONFIG_PATH}")
    print(f"[CONFIG] Enabled: {_config.enabled if _config else 'N/A'}")
    print(f"[CONFIG] Y Strength: {_config.y_strength if _config else 'N/A'}")
    print(f"[CONFIG] Primary Key: 0x{_config.primary_key if _config else 0x06:02X}")
    
    print(f"\n[DLL] Path: {DLL_PATH}")
    print(f"[DLL] Loaded: {_mouse.initialized if _mouse else False}")
    
    print(f"\n[LOGS] {LEARNING_DIR}")
    
    print("\n[INFO] Aguardando auto-start...")
    print("[INFO] Pressione Ctrl+C para parar\n")
    
    try:
        while True:
            time.sleep(1)
            stats = get_stats()
            if stats.get('auto_running'):
                engine_stats = stats.get('engine', {})
                mouse_stats = stats.get('mouse', {})
                
                print(f"\r[LIVE] Shots: {engine_stats.get('total_shots', 0)} | "
                      f"Recoil: {engine_stats.get('current_y', 0):.3f} | "
                      f"Mouse: {mouse_stats.get('move_count', 0)}   ", 
                      end='', flush=True)
    except KeyboardInterrupt:
        print("\n\n[EXIT] Parando...")
        stop()