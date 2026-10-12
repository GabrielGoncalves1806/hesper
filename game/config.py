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
    "craft": 0.7, "place": 0.7, "place_low": 0.7,   # place_low = "place" mais grave (desmontar)
    # drill automática (dicas do Som): drill_collect toca NO LUGAR do pickup; drill_full é discreto;
    # drill_loop é o máximo (colado na drill), cai com a distância até sumir em ~8 tiles
    "drill_collect": 1.0, "drill_full": 0.7, "drill_loop": 0.5,
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
# Zoom do mundo (+/- ou Ctrl+rodinha). Só o mundo aproxima/afasta: HUD e menus ficam do mesmo tamanho.
# Cada nível vira uma "visão" de SCREEN/zoom px do mundo (0,75 -> 1280×720, 2 -> 480×270).
ZOOM_LEVELS = (0.75, 1.0, 1.5, 2.0)
ZOOM_DEFAULT = 1.0
ZOOM_TOAST_TIME = 1.2           # segundos do aviso "Zoom 1,5×"
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
RESOURCE_LABEL = {"iron": "FERRO", "silicon": "SILICIO", "ice": "GELO"}   # rótulos do HUD (Silkscreen)
RESOURCE_NAME = {"iron": "ferro", "silicon": "silício", "ice": "gelo"}      # em frases (Pixelify, com acento)

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
    index: str | None   # qual índice a máquina aumenta (None = não soma Ti, ex.: drill)
    rate: float         # quanto soma por segundo
    unlock_ti: int      # Ti necessário pra liberar a receita
    sprite: str         # nome do sprite (§6)
    size: int = 1       # quantos tiles de lado ela ocupa (drill = 2, em cima de um veio 2×2)
    placeable: bool = True   # False = item que sai do fabricador mas não vai pro chão (ex.: o drone)


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

# ---------------------------------------------------------------------------
# Veios e drill automática (§4 "Veios e drills automáticas")
# ---------------------------------------------------------------------------
# Veio = depósito de minério 2×2 no CHÃO (não dá pra minerar na mão). A drill é colocada em
# cima dele e extrai pra sempre, devagar, até encher; o jogador volta pra coletar com E.
# Custo e ritmo são chute inicial: quem calibra é o tools/dev/balance_sim.py.
DRILL_COST = {"iron": 12, "silicon": 6}   # balance_sim: com 20/10 + 20 s a drill não se pagava (aprovado pelo dono)
DRILL_UNLOCK_TI = 10_000        # libera no estágio Névoa
DRILL_INTERVAL = 12.0           # segundos por unidade extraída (era 20; ver reports/dev/balance.md)
DRILL_CAPACITY = 20             # cheia, para
DRILL_REACH = 56                # px entre os pés do player e a base da drill pra coletar com E
DRILL_FULL_NOTICE = 4 * TILE    # chegou perto (px) de uma drill cheia: toca drill_full uma vez
DRILL_FULL_COOLDOWN = 10.0      # ...e não repete pra mesma drill antes de 10 s
VEINS_NEAR_BASE = (8, 20)       # 1 veio de cada tipo entre 8 e 20 tiles da base
VEINS_FAR_PER_TYPE = 5          # mais longe: 5 de cada tipo (total 6 de cada)
VEINS_FAR_RANGE = (24, 58)      # distância dos veios "de longe" (tiles)

MACHINES["drill"] = MachineType("drill", "Drill automática", "+ minério", DRILL_COST, None, 0,
                                DRILL_UNLOCK_TI, "machine_drill", size=2)

MACHINE_ORDER = list(MACHINES)   # ordem no fabricador e nas teclas 1–7
MACHINE_SPRITE_SIZE = {1: (40, 56), 2: (40, 64)}   # tamanho do sprite por nível (usado pro mouse "acertar" a máquina)
DRILL_SPRITE_SIZE = (64, 80)     # 1 quadro do machine_drill.png (4 quadros na horizontal)
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
    name: str           # nome curto, usado no HUD ("PRÓXIMO: NÉVOA")


STAGES = [
    Stage(1, "dead", 0, "ESTÁGIO 1 · MORTO", "Planeta sem ar. Por enquanto.", "MORTO"),
    Stage(2, "mist", 10_000, "ESTÁGIO 2 · PRIMEIRAS CHUVAS", "Máquinas nv.2 liberadas", "NÉVOA"),
    Stage(3, "green", 100_000, "ESTÁGIO 3 · PRIMEIRO VERDE", "Ti 100.000 · fim do MVP", "VERDE"),
]

RATE_SMOOTHING = 3.0   # segundos da média móvel da taxa de Ti usada na estimativa "~50 min"

# Água: quanto mais baixo o limiar, menos poças. Só aparece a partir da Névoa (§3).
WATER_THRESHOLD = {1: 0.0, 2: 0.24, 3: 0.33}   # estágio 1 (Morto) não tem água nenhuma (§3)
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

# ---------------------------------------------------------------------------
# Transição gradual de estágio (game/transition.py)
# Nos últimos 35% da barra até o próximo estágio, o visual novo entra tile por tile,
# como uma mancha que nasce na base e nas máquinas e se espalha pras bordas.
# ---------------------------------------------------------------------------
TRANSITION_WINDOW = 0.35        # fração final da barra de progresso em que a mancha cresce
TRANSITION_STEPS = 100          # "degraus" da janela: o visual só muda a cada 1% (deixa cachear)
TRANSITION_FRONT_NEAR = 14      # tiles que a frente da mancha anda "em linha reta" ao longo da janela
TRANSITION_FRONT_FAR = 100      # tiles extras que ela dispara no fim, pra chegar nas bordas do mapa
TRANSITION_FRONT_POWER = 8      # quão no fim é esse disparo (maior = mais concentrado no final)
TRANSITION_NOISE_SCALE = 0.11   # tamanho das "manchas" do ruído (menor = manchas maiores)
TRANSITION_WOBBLE = 0.7         # quanto o ruído estica/encolhe a distância (0 = círculo perfeito)
TRANSITION_GRAIN = 1.5          # sorteio por tile na fronteira, em tiles (esfarela a borda)

# ---------------------------------------------------------------------------
# Save/load e tela de título (game/save.py, game/title.py)
# ---------------------------------------------------------------------------
AUTOSAVE_INTERVAL = 120.0   # autosave a cada 2 min jogando (pausa, menus e tela de título não contam)
SAVED_NOTICE_TIME = 2.0     # quanto tempo o aviso "Jogo salvo" fica no HUD (segundos)
VOLUME["save"] = 0.6        # som discreto ao salvar (sem o arquivo save.wav, fica em silêncio)

# ---------------------------------------------------------------------------
# Energia global, sem fios (bíblia §8, Marco 2) · a lógica fica em game/energy.py
# A produção total (kW) é comparada com o consumo total. Se faltar energia, TODAS as
# máquinas rodam no mesmo ritmo: fator = produção / consumo (nunca desliga de vez).
# Sem bateria e sem dia/noite no v0.2.
# ---------------------------------------------------------------------------
POD_POWER = 5            # kW fixos da cápsula, pro começo do jogo funcionar
# Quanto cada máquina consome (kW). Quem não está na tabela consome 0 (painel solar, baú...).
POWER_USE = {
    "o2": 1, "melter": 1, "heater": 2,
    "o2_t2": 3, "melter_t2": 3, "heater_t2": 4,
    "drill": 2,
    "drone_station": 1,  # estação de drones (Marco 3): era 3 kW quando vinha com 2 drones de graça
}
POWER_GEN = {"solar": 3}  # quanto cada máquina gera (kW)
ENERGY_TIGHT = 0.8        # consumo ≥ 80% da produção: medidor amarelo ("perto do limite")
ENERGY_REARM_TIME = 5.0   # o som power_low só toca de novo depois de 5 s seguidos sem déficit
C_ENERGY = "#ffd84a"      # cor do raio do medidor

# Painel solar: +3 kW, não soma Ti. O sprite "solar_panel" e o ícone "icon_solar" ainda estão
# pendentes de aprovação: enquanto não existirem, o jogo desenha o fallback (art.solar_panel).
MACHINES["solar"] = MachineType("solar", "Painel solar", "+ energia", {"iron": 8, "silicon": 6}, None, 0,
                                0, "solar_panel")
MACHINE_ORDER.append("solar")   # no fim da lista do fabricador; fabricado, vira item no inventário
VOLUME["power_low"] = 0.7       # o déficit de energia começou (toca uma vez)
# Inventário com slots, hotbar e baú (v0.2 · bíblia §8 "Inventário com slots" e "Baú")
# A lógica fica em game/inventory.py; aqui só os números.
# ---------------------------------------------------------------------------
INVENTORY_SLOTS = 16            # mochila do player: 2 linhas de 8
HOTBAR_SLOTS = 8                # a hotbar É a primeira linha da mochila (slots 0 a 7), teclas 1–8
STACK_RESOURCE = 50             # recursos empilham até 50 por slot
STACK_MACHINE = 5               # máquinas fabricadas viram itens e empilham até 5
CHEST_SLOTS = 24                # baú: 3 linhas de 8
CHEST_REACH = 48                # px entre os pés do player e a base do baú pra abrir com E
CHEST_SPRITE_SIZE = (32, 40)    # chest.png / chest_open.png (bíblia §8, contrato de assets)
CHEST_SPRITE_APPROVED = True    # chest/chest_open/icon_chest aprovados pelo dono (v0.2); False = desenho de fallback
NOTICE_TIME = 2.0               # segundos que um aviso ("Inventário cheio") fica na tela
CHEST_DEFAULT_NAME = "Baú"      # nome de todo baú novo (e de nome apagado)
CHEST_NAME_MAX = 16             # máximo de caracteres no nome do baú
CHEST_NAME_BLINK = 1.0          # segundos de um ciclo do cursor piscando na edição do nome

# O baú é uma "máquina" sem índice: não soma Ti, não consome energia, só guarda itens.
CHEST_FILTERS = ("all",) + RESOURCES   # o que os drones entregam no baú ("all" = qualquer minério)
MACHINES["chest"] = MachineType("chest", "Baú", "guarda 24 pilhas", {"iron": 6}, None, 0, 0, "chest")
MACHINE_ORDER.insert(MACHINE_ORDER.index("heater") + 1, "chest")   # no fabricador, junto das receitas do começo

# Sons novos: o Som ainda vai entregar os .wav. Enquanto o arquivo não existe, o play() fica em silêncio.
VOLUME.update({"inv_move": 0.5, "chest_open": 0.7, "chest_close": 0.7, "inv_full": 0.5})

# ---------------------------------------------------------------------------
# Estação de drones (bíblia §8, Marco 3) · a lógica fica em game/drones.py
# A estação (2×2, em chão livre fora de veio) solta drones que voam em linha reta, por cima das
# paredes, até as drills; trazem o minério e entregam nos baús perto da estação, pelo filtro (ou no buffer).
# ---------------------------------------------------------------------------
DRONE_STATION_COST = {"iron": 12, "silicon": 8, "ice": 3}   # vem VAZIA: os drones são fabricados à parte
DRONE_STATION_UNLOCK_TI = 10_000   # libera na Névoa, junto com a drill
STATION_DRONE_SLOTS = 4         # slots de drone da estação (1 drone por slot = 1 drone ativo)
DRONE_COST = {"iron": 6, "silicon": 4}   # o item drone (fabricador), libera junto com a estação
DRONE_RANGE = 30                # tiles, do centro da estação até o centro da drill
DRONE_SPEED = 4.0               # tiles por segundo (× fator da energia)
DRONE_MIN_PICKUP = 5            # só busca drill que já tem pelo menos isso guardado
DRONE_CHEST_RADIUS = 6          # entrega nos baús a até 6 tiles da estação (filtrado > "all" > buffer)
DRONE_PICKUP_TIME = 0.8         # segundos parado em cima da drill "coletando"
DRONE_DROP_TIME = 0.6           # segundos pousado "entregando"
STATION_BUFFER = 50             # unidades que a estação guarda quando não tem baú (ou ele está cheio)
STATION_REACH = 56              # px entre os pés do player e a base da estação pra coletar com E
DRONE_STATION_SPRITE_SIZE = (64, 72)       # drone_station.png, âncora no centro da base 2×2
# Onde cada slot pousa, relativo ao canto do PNG da estação: slots 1 e 2 nos pads (H), 3 e 4 "estacionados"
# um pouco à frente e à direita (o PNG só tem 2 pads; o drone da frente cobre metade do de trás).
DRONE_PADS = ((18, 44), (46, 44), (25, 55), (53, 55))
DRONE_SPRITE = 16               # drone.png: 4 quadros de 16×16 lado a lado
DRONE_FPS = 15
DRONE_SHADOW_DROP = 18          # a sombra fica 18 px abaixo do centro do drone voando
DRONE_SPRITES_APPROVED = True   # drone_station/drone/icon_drone_station aprovados (v0.2); False = fallback

MACHINES["drone_station"] = MachineType("drone_station", "Estação de drones", "drones trazem minério",
                                        DRONE_STATION_COST, None, 0, DRONE_STATION_UNLOCK_TI,
                                        "drone_station", size=2)
MACHINE_ORDER.insert(MACHINE_ORDER.index("drill") + 1, "drone_station")   # no fabricador, logo depois da drill
# O drone é um item: sai do fabricador, empilha até 5 e vai num slot da estação (não se coloca no chão).
MACHINES["drone"] = MachineType("drone", "Drone", "vai na estação", DRONE_COST, None, 0, DRONE_STATION_UNLOCK_TI,
                                "drone", placeable=False)
MACHINE_ORDER.insert(MACHINE_ORDER.index("drone_station") + 1, "drone")
VOLUME.update({"drone_loop": 0.5, "drone_deliver": 0.8, "solar_hum": 0.5})
