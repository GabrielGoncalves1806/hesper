"""Todas as constantes do jogo num lugar só.

Se tu quer mudar um número de balanceamento, uma cor ou uma receita, é aqui.
Os valores vêm do docs/GAME_BIBLE.md (§3 paletas, §4 escopo do MVP, §6 assets).
"""

from dataclasses import dataclass
from pathlib import Path

# ---------------------------------------------------------------------------
# Liga/desliga assets (o dono do projeto precisa aprovar antes de ligar)
# ---------------------------------------------------------------------------
ENABLE_SPRITES = True   # True = usa assets/sprites/<nome>.png (aprovados no design v2)
ENABLE_AUDIO = True     # True = tenta tocar assets/audio/<nome>.wav (aprovado pelo dono, som v3)

ROOT_DIR = Path(__file__).resolve().parent.parent
SPRITES_DIR = ROOT_DIR / "assets" / "sprites"
AUDIO_DIR = ROOT_DIR / "assets" / "audio"
FONTS_DIR = Path(__file__).resolve().parent / "fonts"

# ---------------------------------------------------------------------------
# Volumes do som (0 = mudo, 1 = volume do arquivo). Ajuste aqui depois de cada playtest.
# Os arquivos já vêm equilibrados entre si; isso é só o multiplicador por categoria.
# ---------------------------------------------------------------------------
VOLUME = {
    # mineração: playtest 1 achou alto ("muito alto de quebrar") -> bem mais baixo
    "mine_hit": 0.5, "mine_break": 0.45, "pickup": 0.7,
    # passos: playtest 1 achou alto ("andar") -> bem mais baixo
    "footstep_0": 0.3, "footstep_1": 0.3,
    # interface: ~30% abaixo do volume original (0,8)
    "ui_open": 0.56, "ui_close": 0.56, "ui_click": 0.56, "terminal_open": 0.56,
    # sobrevivência: o alarme fica alto de propósito (abaixo de 0,6 ele perde a função)
    "o2_low": 0.9, "o2_refill": 0.65, "faint": 0.7,
    # máquinas: ~30% abaixo do original (1,0)
    "craft": 0.7, "place": 0.7,
    # recompensa: o jingle de estágio continua sendo o som mais alto
    "stage_up": 0.85,
}
AMBIENT_VOLUME = 0.7    # ambiente: o dono gostou, NÃO mexer sem pedir
HUM_MAX_VOLUME = 0.6    # zumbido das máquinas quando o player está colado nelas

# ---------------------------------------------------------------------------
# Tela e tempo
# ---------------------------------------------------------------------------
SCREEN_W, SCREEN_H = 960, 540   # resolução interna (30×17 tiles)
UI_W, UI_H = 480, 270           # a UI é desenhada em metade da resolução e escalada 2× (igual ao mockup)
FPS = 60
MAX_DT = 0.05                   # nunca simula mais que 50 ms num frame (evita atravessar parede)
DEBUG_TIME_SCALE = 10           # F1: acelera O₂ e máquinas ×10
DEBUG_TI_BONUS = 10_000         # F2: soma isso no Ti

# ---------------------------------------------------------------------------
# Mundo
# ---------------------------------------------------------------------------
TILE = 32
WALL_LIFT = 24                  # o topo da parede é desenhado 24 px acima do tile (dá altura, estilo Core Keeper)
WORLD_W = WORLD_H = 128
WORLD_SEED = 7
CRATER_CENTER = (64, 64)        # em tiles
CRATER_RADIUS = 12              # raio médio da cratera (a borda é irregular por causa do noise)
CRATER_SAFE_RADIUS = 8          # dentro desse raio é sempre chão, não importa o noise

# Tipos de tile (inteiros pra caber numa grade simples)
FLOOR, ROCK, IRON, SILICON, ICE, BEDROCK, TERMINAL = range(7)
SOLID_TILES = {ROCK, IRON, SILICON, ICE, BEDROCK, TERMINAL}
ORE_TILES = {IRON: "iron", SILICON: "silicon", ICE: "ice"}

# Terminais de lore: (distância em tiles do centro, ângulo em graus). Distâncias crescentes.
TERMINAL_SPOTS = [(19, 35), (31, 160), (45, 280)]

# ---------------------------------------------------------------------------
# Base (cápsula) e player
# ---------------------------------------------------------------------------
# A cápsula ocupa 2 tiles de largura na linha 63. A âncora é o centro da base (chão).
POD_TILES = [(63, 63), (64, 63)]
POD_ANCHOR = (64 * TILE, 64 * TILE)           # pixel: centro da base da cápsula
BASE_CENTER = (64 * TILE, 64 * TILE - 16)     # centro da zona de O₂
BASE_RADIUS = 5 * TILE                        # raio da zona de O₂ (5 tiles)
SPAWN_POS = (64 * TILE, 65 * TILE + 8)        # onde o player nasce/acorda (pés)

PLAYER_SPEED = 120          # px/s (~3,7 tiles por segundo)
PLAYER_BOX_W, PLAYER_BOX_H = 14, 8   # caixa de colisão nos pés

# ---------------------------------------------------------------------------
# Mineração (§4 Mineração)
# ---------------------------------------------------------------------------
MINE_TIME = {ROCK: 0.6, IRON: 1.0, SILICON: 1.2, ICE: 0.8}
DROP_MIN, DROP_MAX = 1, 2
MINE_REACH = 2              # alcance em tiles (distância de Chebyshev a partir do tile do player)
MINE_HIT_INTERVAL = 0.25    # som de picareta a cada 0,25 s

RESOURCES = ("iron", "silicon", "ice")
RESOURCE_LABEL = {"iron": "FERRO", "silicon": "SILICIO", "ice": "GELO"}

# ---------------------------------------------------------------------------
# Sobrevivência (§4 Sobrevivência)
# ---------------------------------------------------------------------------
O2_MAX = 100.0
O2_DRAIN = 1.0              # por segundo, fora da zona
O2_REFILL = 20.0            # por segundo, dentro da zona
O2_LOW = 25.0               # abaixo disso: alarme, tela vermelha, seta
FAINT_RESPAWN_AT = 1.5      # segundos depois de desmaiar: teleporta pra cápsula (tela preta)
FAINT_DURATION = 3.0        # segundos até devolver o controle

# ---------------------------------------------------------------------------
# Máquinas e índices (§4 Máquinas e índices)
# ---------------------------------------------------------------------------
INDEX_UNIT = {"o2": "ppq", "heat": "pK", "water": "ppm"}
INDEX_LABEL = {"o2": "O2", "heat": "CALOR", "water": "AGUA"}


@dataclass(frozen=True)
class MachineType:
    key: str
    name: str
    desc: str
    cost: dict          # recurso -> quantidade
    index: str          # qual índice a máquina aumenta
    rate: float         # quanto soma por segundo
    unlock_ti: int      # Ti necessário pra liberar a receita
    sprite: str         # nome do sprite (§6)


MACHINES = {
    m.key: m
    for m in [
        MachineType("o2", "Gerador de O2", "+ oxigênio", {"iron": 10, "silicon": 4}, "o2", 3, 0, "machine_o2"),
        MachineType("melter", "Derretedor de gelo", "+ água", {"iron": 6, "ice": 10}, "water", 2, 0, "machine_melter"),
        MachineType("heater", "Aquecedor", "+ calor", {"iron": 12, "silicon": 8}, "heat", 4, 500, "machine_heater"),
        MachineType("o2_t2", "Gerador de O2 nv.2", "+ oxigênio", {"iron": 30, "silicon": 20, "ice": 10}, "o2", 25, 10_000, "machine_o2_t2"),
        MachineType("melter_t2", "Derretedor nv.2", "+ água", {"iron": 25, "ice": 30}, "water", 20, 10_000, "machine_melter_t2"),
        MachineType("heater_t2", "Aquecedor nv.2", "+ calor", {"iron": 35, "silicon": 25}, "heat", 30, 10_000, "machine_heater_t2"),
    ]
}
MACHINE_ORDER = list(MACHINES)   # ordem no fabricador e nas teclas 1–6
PLACE_REACH = 4                  # alcance pra colocar máquina (tiles)

# ---------------------------------------------------------------------------
# Estágios de terraformação (§4 Estágios)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Stage:
    number: int
    key: str            # usado nos nomes de sprite: floor_dead_0 etc.
    ti: int             # Ti mínimo
    title: str
    subtitle: str


STAGES = [
    Stage(1, "dead", 0, "ESTÁGIO 1 · MORTO", "Um planeta sem ar. Por enquanto."),
    Stage(2, "mist", 10_000, "ESTÁGIO 2 · PRIMEIRAS CHUVAS", "Ti 10.000 · máquinas nv.2 desbloqueadas"),
    Stage(3, "green", 100_000, "ESTÁGIO 3 · PRIMEIRO VERDE", "Ti 100.000 · fim do MVP"),
]

# Água: quanto mais baixo o limiar, menos poças. Estágio 1 tem "poucas poças" (§3).
WATER_THRESHOLD = {1: 0.10, 2: 0.24, 3: 0.33}
PLANT_CHANCE = 0.11   # estágio 3: chance de um tile de chão ter planta

# ---------------------------------------------------------------------------
# Lore (§2)
# ---------------------------------------------------------------------------
LOGS = [
    "Dia 3. Pouso perfeito. A cratera é maior do que as sondas mostraram. "
    "Começamos a montar os geradores amanhã.",
    "Dia 97. O índice subiu rápido demais esse mês. A Dra. Ilves pediu pra desacelerar. "
    "A diretoria disse que o cronograma não espera.",
    "Dia 212. O derretedor 4 parou de novo. A Dra. Ilves jura que o gelo daqui não é só água, "
    "que tem alguma coisa dentro dele. Ninguém quis ouvir. Amanhã a gente desce pro nível 2 de qualquer jeito.",
]
TERMINAL_REACH = 48   # px entre os pés do player e a base do terminal

# ---------------------------------------------------------------------------
# Cores (§3)
# ---------------------------------------------------------------------------
PALETTES = {
    "dead": {
        "floor": ["#7b402c", "#743b29", "#814430"], "patch": "#6a3424", "dot": "#5c2d1f",
        "peb": "#94553b", "peb_hi": "#b0704f", "crack": "#57291c",
        "rock": "#4b3332", "rock2": "#563a38", "rock_hi": "#6e4b47", "rock_dot": "#352323", "edge": "#7f5b56",
        "face": "#2f1f1f", "face_hi": "#5f4240", "face_dark": "#221616",
        "water": "#3d6f86", "water_d": "#2f5a70", "foam": "#b8e2ee",
        "ambient": (26, 8, 12, 87),
    },
    "mist": {
        "floor": ["#6e5a4f", "#685448", "#75604f"], "patch": "#5e4c42", "dot": "#54443b",
        "peb": "#85715f", "peb_hi": "#a08b78", "crack": None,
        "rock": "#4a4447", "rock2": "#544d50", "rock_hi": "#6c6467", "rock_dot": "#343033", "edge": "#7c757d",
        "face": "#2b272a", "face_hi": "#5d5659", "face_dark": "#1f1c1e",
        "water": "#3f7690", "water_d": "#315f78", "foam": "#b8e2ee",
        "ambient": (16, 24, 34, 56),
    },
    "green": {
        "floor": ["#4d7a39", "#477235", "#548140"], "patch": "#426b31", "dot": "#3a5f2c",
        "peb": "#7a8a6a", "peb_hi": "#9aa88a", "crack": None,
        "grass": "#79b04f", "grass2": "#5e9640", "moss": "#5c9a43", "moss2": "#7cba58",
        "rock": "#4b4a45", "rock2": "#55544e", "rock_hi": "#6d6c64", "rock_dot": "#353530", "edge": "#76805f",
        "face": "#2c2c28", "face_hi": "#5c5b54", "face_dark": "#1f1f1c",
        "water": "#2c7ea6", "water_d": "#22668a", "foam": "#b8e2ee",
        "ambient": (10, 22, 12, 31),
    },
}

ORE_COLORS = {  # cor, sombra
    "iron": ("#e8a066", "#a5582c"),
    "silicon": ("#c3d1e2", "#7d8ca3"),
    "ice": ("#a6ecff", "#4fb3d6"),
}

# UI
C_O2 = "#59d0e6"
C_ACCENT = "#e2733a"
C_TI = "#f2c46d"
C_OK = "#7fd67a"
C_ALERT = "#ff6a55"
C_TEXT = "#efe5da"
C_MUTED = "#9c8d82"
C_HEAT = "#ff8a3d"
C_WATER = "#6aa8ff"
C_TERMINAL = "#6fe3a0"
INDEX_COLOR = {"o2": C_O2, "heat": C_HEAT, "water": C_WATER}
STAGE_COLOR = {1: C_ACCENT, 2: "#9fd2e6", 3: "#a6e07a"}
