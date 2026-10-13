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
DESERT_WIND_VOLUME = 0.45  # vento do deserto (desert_wind.wav, pendente): por cima do ambiente (0,7), só na superfície
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
DEBUG_SPEED = 2.0               # F3: player anda 2× mais rápido...
DEBUG_MINE = 5.0                # ...e a broca quebra 5× mais rápido (paredes, minério e rochas)

# ---------------------------------------------------------------------------
# Mundo
# ---------------------------------------------------------------------------
TILE = 32
WALL_LIFT = 24                  # o topo da parede é desenhado 24 px acima do tile (dá altura, estilo Core Keeper)
WORLD_SEED = 7

# Duas camadas (v0.3, bíblia §9): a SUPERFÍCIE (deserto aberto, onde fica a base) e a CAVERNA (o gerador
# antigo do world.py, que entra de verdade no Marco 2). Cada uma tem o próprio mapa (game/layers.py).
SURFACE_W = SURFACE_H = 192     # deserto (game/surface_gen.py)
CAVE_W = CAVE_H = 128           # caverna (game/world.py)
WORLD_W, WORLD_H = CAVE_W, CAVE_H   # nome antigo: tamanho padrão do World (a caverna)
CAVE_CENTER = (64, 64)          # centro da caverna, em tiles (no Marco 2 a rampa de subida fica aqui)
CAVE_HALL_RADIUS = 12           # raio médio do salão aberto da caverna (a borda é irregular por causa do noise)
CAVE_SAFE_RADIUS = 8            # dentro desse raio é sempre chão, não importa o noise
# Rampa de subida (Marco 2): 3×3 de tiles CRATER no meio do salão. Canto de cima à esquerda; o E mira no tile
# do meio de baixo (tx+1, ty+2) e o player chega/sai em (tx+1, ty+3), que é o CAVE_CENTER.
CAVE_RAMP = (CAVE_CENTER[0] - 1, CAVE_CENTER[1] - 3)
# Minério da caverna: um tile de rocha vira minério se o noise passar de  base - extra × longe  (longe = 0 no
# salão, 1 a 45+ tiles dele). Histórico: 0,66/0,11 no Marco 1 (~35% das paredes); 0,62/0,15 no Marco 2 (~48%,
# o dono achou demais no playtest); agora 0,64/0,11: ~39% (seeds 7/1/42: 40,0/40,9/36,9%), ~29% perto do
# salão e ~41% a 40–60 tiles.
CAVE_ORE_THRESHOLD = (0.64, 0.11)

# Tipos de tile (inteiros pra caber numa grade simples)
FLOOR, ROCK, IRON, SILICON, ICE, BEDROCK, TERMINAL = range(7)
SAND = 7                        # chão do deserto (superfície)
SMALL_IRON, SMALL_SILICON, SMALL_ICE = 8, 9, 10   # rocha pequena no chão: 1 tile, quebra com a broca, reaparece devagar (game/rock_respawn.py)
CRATER = 11                     # os 3×3 da cratera: obstáculo plano (no Marco 2 vira a rampa de descida)
WRECK = 12                      # área de um destroço (Marco 3): obstáculo plano, o sprite é desenhado como objeto
LOOT_CRATE = 13                 # caixa de saque de um destroço (1 tile, obstáculo plano; abre com E)
ORE_TILES = {IRON: "iron", SILICON: "silicon", ICE: "ice"}            # minério NA PAREDE (overlay no topo)
SMALL_ROCKS = {SMALL_IRON: "iron", SMALL_SILICON: "silicon", SMALL_ICE: "ice"}
WALL_TILES = {ROCK, IRON, SILICON, ICE, BEDROCK, TERMINAL}            # paredes ALTAS (topo elevado + face)
FLAT_SOLIDS = set(SMALL_ROCKS) | {CRATER, WRECK, LOOT_CRATE}                           # sólidos baixos: bloqueiam, mas não têm altura
SOLID_TILES = WALL_TILES | FLAT_SOLIDS
FLOOR_TILES = {FLOOR, SAND}
TILE_RESOURCE = {**ORE_TILES, **SMALL_ROCKS}                          # o que cada tile dá ao quebrar

# Terminais de lore da caverna: (distância em tiles do centro, ângulo em graus). Distâncias crescentes.
TERMINAL_SPOTS = [(19, 35), (31, 160), (45, 280)]

# Gerador do deserto (game/surface_gen.py · bíblia §9, Marco 1)
SURFACE_BORDER = (2, 3)         # cordilheira da borda: 2 ou 3 tiles de espessura (intransponível, não minera)
HILLS = (24, 32)                # quantos morros de rocha (a única parede da superfície, minerável)
HILL_SIZE = (3, 8)              # largura do morro em tiles
HILL_ORE_CHANCE = 0.12          # chance de um tile de morro ter minério (pouco: o volume fica na caverna)
SURFACE_CLEAR_RADIUS = 8        # raio de areia limpa em volta da cápsula
SURFACE_CRATER_DIST = (15, 20)  # distância (tiles) do centro da cratera até a base
SURFACE_VEINS = (3, 5)          # veios de drill na superfície: poucos, longe, obrigam a explorar
SURFACE_VEIN_MIN_DIST = 35      # nenhum tile de veio a menos disso da base
SURFACE_VEIN_SPACING = 14       # distância mínima entre veios (tiles)
SMALL_ROCK_CHANCE = 0.013       # chance de um tile de areia virar rocha pequena (~430 no mapa; era 0,011/~357 com os soltos)
SMALL_ROCK_MIN_DIST = SURFACE_CLEAR_RADIUS   # a área da cápsula fica limpa
SMALL_ROCK_WEIGHTS = {"iron": 0.45, "silicon": 0.3, "ice": 0.25}

# Rochas pequenas reaparecendo (game/rock_respawn.py · bíblia §9, Marco 1). Entraram no lugar dos recursos soltos.
ROCK_RESPAWN = 15.0             # segundos por rocha nova (= 4 por minuto, ~12 unidades/min)
ROCK_MAX = 520                  # teto de rochas no mapa (o reaparecimento para aqui)
ROCK_BASE_DIST = 12             # reaparece só a 12+ tiles da base...
ROCK_HIDDEN = (21, 13)          # ...e fora da tela: meia-tela em tiles no zoom 0,75 (1280×720 = 20×11) + folga

# ---------------------------------------------------------------------------
# Base (cápsula) e player · a base fica no CENTRO da superfície
# ---------------------------------------------------------------------------
BASE_TILE = (SURFACE_W // 2, SURFACE_H // 2)  # (96, 96): o tile logo abaixo da cápsula, à direita do meio
# A cápsula ocupa 2 tiles de largura na linha de cima do BASE_TILE. A âncora é o centro da base (chão).
POD_TILES = [(BASE_TILE[0] - 1, BASE_TILE[1] - 1), (BASE_TILE[0], BASE_TILE[1] - 1)]
POD_ANCHOR = (BASE_TILE[0] * TILE, BASE_TILE[1] * TILE)           # pixel: centro da base da cápsula
BASE_CENTER = (BASE_TILE[0] * TILE, BASE_TILE[1] * TILE - 16)     # centro da zona de O₂
BASE_RADIUS = 5 * TILE                                            # raio da zona de O₂ (5 tiles)
SPAWN_POS = (BASE_TILE[0] * TILE, (BASE_TILE[1] + 1) * TILE + 8)  # onde o player nasce/acorda (pés)

# Pontos de luz da cápsula (janela e beacon), relativos ao canto de cima à esquerda do pod.png (64×72).
# O redesenho do pod (v4.0 da Designer, em _pending) mudou os pontos: quando ele for promovido, troque
# POD_SPRITE_REDESIGN pra True.
POD_LIGHTS = {"v3": {"window": (20, 31), "beacon": (50, 4)},
              "v4": {"window": (19, 36), "beacon": (51, 4), "led": (31, 41)}}
POD_SPRITE_REDESIGN = True

PLAYER_SPEED = 120          # px/s (~3,7 tiles por segundo)
PLAYER_BOX_W, PLAYER_BOX_H = 14, 8   # caixa de colisão nos pés

# ---------------------------------------------------------------------------
# Mineração (§4 Mineração)
# ---------------------------------------------------------------------------
MINE_TIME = {ROCK: 0.6, IRON: 1.0, SILICON: 1.2, ICE: 0.8,
             SMALL_IRON: 0.7, SMALL_SILICON: 0.7, SMALL_ICE: 0.7}   # rocha pequena: rapidinha
DROP_MIN, DROP_MAX = 1, 2       # minério de parede
DROP_RANGE = {k: (2, 4) for k in SMALL_ROCKS}   # rocha pequena dá 2 a 4 (o resto usa DROP_MIN/MAX)
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
INDEX_LABEL = {"o2": "O₂", "heat": "CALOR", "water": "AGUA"}


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
        MachineType("o2", "Gerador de O₂", "+ oxigênio", {"iron": 10, "silicon": 4}, "o2", 3, 0, "machine_o2"),
        MachineType("melter", "Derretedor de gelo", "+ água", {"iron": 6, "ice": 10}, "water", 2, 0, "machine_melter"),
        MachineType("heater", "Aquecedor", "+ calor", {"iron": 12, "silicon": 8}, "heat", 4, 500, "machine_heater"),
        MachineType("o2_t2", "Gerador de O₂ nv.2", "+ oxigênio", {"iron": 30, "silicon": 20, "ice": 10}, "o2", 25, 10_000, "machine_o2_t2"),
        MachineType("melter_t2", "Derretedor nv.2", "+ água", {"iron": 25, "ice": 30}, "water", 20, 10_000, "machine_melter_t2"),
        MachineType("heater_t2", "Aquecedor nv.2", "+ calor", {"iron": 35, "silicon": 25}, "heat", 30, 10_000, "machine_heater_t2"),
    ]
}

# ---------------------------------------------------------------------------
# Veios e drill automática (§4 "Veios e drills automáticas")
# ---------------------------------------------------------------------------
# Veio = depósito de minério 2×2 no CHÃO (não dá pra minerar na mão). A drill é colocada em
# cima dele e extrai pra sempre, devagar, até encher (inventário de 1 slot); E abre o painel, Shift+E coleta.
# Custo e ritmo são chute inicial: quem calibra é o tools/dev/balance_sim.py.
DRILL_COST = {"iron": 12, "silicon": 6}   # balance_sim: com 20/10 + 20 s a drill não se pagava (aprovado pelo dono)
DRILL_UNLOCK_TI = 10_000        # libera no estágio Névoa
DRILL_INTERVAL = 12.0           # segundos por unidade extraída (era 20; ver reports/dev/balance.md)
DRILL_CAPACITY = 20             # cheia, para
DRILL_SLOTS = 1                 # inventário da drill: 1 slot, só do minério dela (o limite é o DRILL_CAPACITY)
DRILL_REACH = 56                # px entre os pés do player e a base da drill pro E (painel) e Shift+E (coleta)
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
    key: str            # "storm", "arid", "mist", "green" (a arte sai do STAGE_ART: floor_dead_0 etc.)
    ti: int             # Ti mínimo
    title: str
    subtitle: str
    name: str           # nome curto, usado no HUD ("PRÓXIMO: NÉVOA")


# v0.4 Marco 1: 4 estágios. A Tempestade é o começo do jogo; o Árido é o "céu limpo" com o chão de hoje.
# O Ti do Árido sai do tools/dev/balance_sim.py (meta: chegar entre 8 e 12 min no casual). Com 2.500 o casual
# chegava em ~5 min; com 6.500, em 8m15s–8m24s (seeds 1–3). Névoa e Verde ficaram iguais (o total não mudou).
STAGES = [
    Stage(1, "storm", 0, "ESTÁGIO 1 · TEMPESTADE", "Sobreviva e monte a base", "TEMPESTADE"),
    Stage(2, "arid", 6_500, "ESTÁGIO 2 · CÉU LIMPO", "A poeira baixou", "ÁRIDO"),
    Stage(3, "mist", 10_000, "ESTÁGIO 3 · PRIMEIRAS CHUVAS", "Máquinas nv.2 liberadas", "NÉVOA"),
    Stage(4, "green", 100_000, "ESTÁGIO 4 · PRIMEIRO VERDE", "Ti 100.000 · fim do MVP", "VERDE"),
]
STORM_STAGE = 1      # estágio da tempestade de poeira (passou dele, a tempestade some)
ARID_STAGE = 2
MIST_STAGE = 3       # a água e as máquinas nv.2 começam aqui
GREEN_STAGE = 4      # plantas e fim do jogo
STORM_FADE_S = 20.0  # s pra tempestade sumir depois de entrar no Árido (state.storm de 1.0 a 0.0)
# Arte de cada estágio (sprites floor_{arte}_N, PALETTES[arte]...): a Tempestade e o Árido usam a do Morto.
STAGE_ART = {"storm": "dead", "arid": "dead", "mist": "mist", "green": "green"}

RATE_SMOOTHING = 3.0   # segundos da média móvel da taxa de Ti usada na estimativa "~50 min"

# Água: quanto mais baixo o limiar, menos poças. Só aparece a partir da Névoa (§3).
WATER_THRESHOLD = {1: 0.0, 2: 0.0, 3: 0.24, 4: 0.33}   # Tempestade e Árido não têm água nenhuma (§3)
PLANT_CHANCE = 0.11   # estágio Verde: chance de um tile de chão ter planta

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
# LOGs dos destroços (v0.3 Marco 3, aprovados pelo dono · docs/lore/logs_v03_rascunho.md).
# Os índices em LOGS nunca mudam (o save guarda índices): o número que o jogador vê sai da cronologia (LOG_ORDER).
LOGS += [
    "Dia 188. Cargueira VÉSPER-7, manifesto de retorno. Carga: 12 toneladas de gelo de núcleo, lacrado em contêiner "
    "frio, prioridade da diretoria. Motivo do retorno: tripulação pediu pra não levar. Pedido negado.",
    "Dia 140. A Dra. Ilves colocou uma amostra do gelo do fundo da cratera no microscópio e ficou em silêncio a tarde "
    "inteira. À noite ela trancou o laboratório e levou a chave. Disse só: 'cresce quando ninguém olha'.",
    "Dia 41. Sonda de mapeamento S-3. Leitura térmica anômala abaixo da cratera principal: o calor sobe sozinho, sem "
    "fonte conhecida. Recomendação automática: não perfurar. Status da recomendação: ignorada.",
    "Dia 230. Última mensagem da Colônia Hesper. Desligamos os derretedores. Todos. Se alguém achar isto: "
    "o planeta não está morto. Ele está esperando. Não acorde o gelo.",
]
# Título da tela de leitura de cada LOG (mesma ordem do LOGS)
LOG_TITLES = ["TERMINAL · COLONIA HESPER"] * 3 + [
    "REGISTRO DE BORDO · VÉSPER-7", "TERMINAL · MODULO DA COLONIA",
    "SONDA S-3 · LEITURA AUTOMATICA", "TERMINAL · MODULO DA COLONIA"]
# Dia da história de cada LOG (mesma ordem do LOGS). A aba LOGs do inventário lista nessa ordem, e o
# "LOG 01".."LOG 07" exibido é a posição cronológica (não o índice em LOGS).
LOG_DAYS = [3, 97, 212, 188, 140, 41, 230]
LOG_ORDER = sorted(range(len(LOGS)), key=LOG_DAYS.__getitem__)   # índices em LOGS, do dia mais cedo pro mais tarde


def log_number(log: int) -> int:
    """Número exibido do LOG `log` (índice em LOGS): a posição dele na cronologia, a partir de 1."""
    return LOG_ORDER.index(log) + 1


def log_label(log: int) -> str:
    """"LOG 01".."LOG 07" do LOG `log` (índice em LOGS)."""
    return f"LOG {log_number(log):02d}"

TERMINAL_REACH = 48   # px entre os pés do player e a base do terminal

# Rampa entre as camadas (v0.3 Marco 2 · game/layers.py e GameState.start_ramp)
RAMP_REACH = 64         # px dos pés até o meio da borda de baixo da rampa (quem chega já está no alcance)
RAMP_SWITCH_AT = 0.6    # s: no meio do fade preto troca de camada
RAMP_DURATION = 1.3     # s: fade completo (escurece, "Descendo..."/"Subindo...", clareia)

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
        "sand": ["#a4583a", "#985034", "#af6343"], "sand_dark": "#86452c", "sand_hi": "#bf7350",
        "ambient": (26, 8, 12, 87),
    },
    "mist": {
        "floor": ["#6e5a4f", "#685448", "#75604f"], "patch": "#5e4c42", "dot": "#54443b",
        "peb": "#85715f", "peb_hi": "#a08b78", "crack": None,
        "rock": "#4a4447", "rock2": "#544d50", "rock_hi": "#6c6467", "rock_dot": "#343033", "edge": "#7c757d",
        "face": "#2b272a", "face_hi": "#5d5659", "face_dark": "#1f1c1e",
        "water": "#3f7690", "water_d": "#315f78", "foam": "#b8e2ee",
        "sand": ["#787677", "#6e6c6e", "#838183"], "sand_dark": "#605e61", "sand_hi": "#959397",
        "ambient": (16, 24, 34, 56),
    },
    "green": {
        "floor": ["#4d7a39", "#477235", "#548140"], "patch": "#426b31", "dot": "#3a5f2c",
        "peb": "#7a8a6a", "peb_hi": "#9aa88a", "crack": None,
        "grass": "#79b04f", "grass2": "#5e9640", "moss": "#5c9a43", "moss2": "#7cba58",
        "rock": "#4b4a45", "rock2": "#55544e", "rock_hi": "#6d6c64", "rock_dot": "#353530", "edge": "#76805f",
        "face": "#2c2c28", "face_hi": "#5c5b54", "face_dark": "#1f1f1c",
        "water": "#2c7ea6", "water_d": "#22668a", "foam": "#b8e2ee",
        "sand": ["#a08e66", "#94835d", "#ab9a71"], "sand_dark": "#80714e", "sand_hi": "#bcab82",
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
STAGE_COLOR = {1: C_ACCENT, 2: "#e8b37a", 3: "#9fd2e6", 4: "#a6e07a"}

# ---------------------------------------------------------------------------
# Transição gradual de estágio (game/transition.py)
# Nos últimos 35% da barra até o próximo estágio, o visual novo entra tile por tile,
# como uma mancha que nasce na base e nas máquinas e se espalha pras bordas.
# ---------------------------------------------------------------------------
TRANSITION_WINDOW = 0.35        # fração final da barra de progresso em que a mancha cresce
TRANSITION_STEPS = 100          # "degraus" da janela: o visual só muda a cada 1% (deixa cachear)
TRANSITION_FRONT_NEAR = 14      # tiles que a frente da mancha anda "em linha reta" ao longo da janela
TRANSITION_FRONT_FAR = 150      # tiles extras que ela dispara no fim, pra chegar nas bordas do mapa (deserto 192×192)
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
POWER_GEN = {"solar": 4}  # quanto cada máquina gera (kW)
ENERGY_TIGHT = 0.8        # consumo ≥ 80% da produção: medidor amarelo ("perto do limite")
ENERGY_REARM_TIME = 5.0   # o som power_low só toca de novo depois de 5 s seguidos sem déficit
C_ENERGY = "#ffd84a"      # cor do raio do medidor

# Painel solar: +4 kW, não soma Ti. O sprite "solar_panel" e o ícone "icon_solar" ainda estão
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
MACHINES["chest"] = MachineType("chest", "Baú", "guarda 24 pilhas", {"iron": 6}, None, 0, 0, "chest")
MACHINE_ORDER.insert(MACHINE_ORDER.index("heater") + 1, "chest")   # no fabricador, junto das receitas do começo

# Sons novos: o Som ainda vai entregar os .wav. Enquanto o arquivo não existe, o play() fica em silêncio.
VOLUME.update({"inv_move": 0.5, "chest_open": 0.7, "chest_close": 0.7, "inv_full": 0.5})

# ---------------------------------------------------------------------------
# Estação de drones (bíblia §8, Marco 3) · a lógica fica em game/drones.py
# A estação (2×2, em chão livre fora de veio) é a casa dos drones: eles voam em linha reta, por cima das
# paredes, de um inventário que Envia um item pra outro que Recebe esse item (baús e drills, mapa inteiro).
# ---------------------------------------------------------------------------
DRONE_STATION_COST = {"iron": 12, "silicon": 8, "ice": 3}   # vem VAZIA: os drones são fabricados à parte
DRONE_STATION_UNLOCK_TI = 10_000   # libera na Névoa, junto com a drill
STATION_DRONE_SLOTS = 4         # slots de drone da estação (1 drone por slot = 1 drone ativo)
DRONE_COST = {"iron": 6, "silicon": 4}   # o item drone (fabricador), libera junto com a estação
CRAFT_BATCH = 5                 # Shift+Enter / Shift+clique no fabricador: fabrica até 5 de uma vez
# Sem alcance: os drones atendem o mapa inteiro (logística estilo Planet Crafter, bíblia §8).
DRONE_SPEED = 6.0               # tiles por segundo (× fator da energia). Era 4: com o mapa todo, ~13 s numa viagem de 80 tiles
DRONE_PICKUP_TIME = 0.8         # segundos parado em cima da origem "pegando"
DRONE_DROP_TIME = 0.6           # segundos parado em cima do destino "soltando"
DRONE_IDLE_RETRY = 0.5          # drone pousado sem tarefa procura de novo a cada 0,5 s
# Logística (baú e drill): o que os drones tiram (Envia) e trazem (Recebe), e o lote por viagem.
LOGISTIC_ITEMS = RESOURCES      # itens com toggle no painel (conjunto de ids: dá pra crescer depois)
DRONE_BATCH_OPTIONS = (1, 5, 10, 20)
DRONE_BATCH_DEFAULT = 10
STATION_BUFFER = 50             # legado (save ≤ v4): o buffer não recebe mais nada, só dá pra tirar as sobras
STATION_REACH = 56              # px entre os pés do player e a base da estação pro E (painel)
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

# ---------------------------------------------------------------------------
# Abas do fabricador (game/fabricator.py). Máquina nova: é só pôr a categoria dela aqui.
# A ordem dentro de cada aba é a do MACHINE_ORDER.
# ---------------------------------------------------------------------------
FAB_TABS = (("terraform", "Terraformação"), ("energy", "Energia"),
            ("automation", "Automação"), ("storage", "Armazenamento"), ("light", "Luz"))
MACHINE_CATEGORY = {
    "o2": "terraform", "melter": "terraform", "heater": "terraform",
    "o2_t2": "terraform", "melter_t2": "terraform", "heater_t2": "terraform",
    "solar": "energy",
    "drill": "automation", "drone_station": "automation", "drone": "automation",
    "chest": "storage",
    "lamp": "light",
}
FAB_VISIBLE_ROWS = 6            # receitas que cabem de uma vez na aba (lista do redesign B2); com mais, rola

# ---------------------------------------------------------------------------
# Luminária (v0.3 Marco 2 · bíblia §9): luz de chão pra caverna. 1 Fe + 1 Si, liberada desde o começo, sem
# energia, colocável nas duas camadas. A luz (raio ~5 tiles) vem do game/lighting.py (lamp(tx, ty)).
# Sprites lamp.png (16×32) e icon_lamp.png (16×16) pendentes: até lá, art.lamp / art.lamp_icon.
# ---------------------------------------------------------------------------
MACHINES["lamp"] = MachineType("lamp", "Luminária", "luz na caverna", {"iron": 1, "silicon": 1}, None, 0, 0, "lamp")
MACHINE_ORDER.append("lamp")
LAMP_SPRITE_SIZE = (16, 32)
# Sons da caverna (assets/audio/, pendentes de aprovação: sem o arquivo, silêncio)
VOLUME.update({"ramp_down": 0.8, "ramp_up": 0.8, "lamp_place": 0.8})
CAVE_AMBIENT_OUT_MS = 1500      # descendo/subindo: o ambiente que sai (e o vento) some em 1,5 s...
CAVE_AMBIENT_IN_MS = 2500       # ...e o novo entra em 2,5 s...
CAVE_AMBIENT_DELAY = 0.5        # ...meio segundo depois (dica do Som)

# ---------------------------------------------------------------------------
# v0.3 Marco 3 · destroços, projetos, equipamento e scanner (bíblia §9)
# ---------------------------------------------------------------------------
# Destroços (game/wrecks.py): 6 a 8 no deserto, do mais perto (~30 tiles da base) ao mais longe (perto da borda).
WRECK_COUNT = (6, 8)
WRECK_DIST = (30, 84)           # distância (tiles) do centro do 1º e do último destroço até a base
WRECK_SPACING = 14              # distância mínima entre destroços (tiles, centro a centro)
WRECK_MARGIN = 2                # folga de areia livre em volta do destroço e da caixa (sem rocha pequena)
CRATE_SLOTS = 8                 # caixa de saque: 1 linha de 8
CRATE_REACH = 48                # px dos pés até a base da caixa (igual ao baú)
WRECK_VISIT_DIST = 6            # tiles: chegou "perto" de um destroço (objetivo "Ache um destroço")
LOOT_CRATE_SIZE = (32, 32)

# Projetos (chips de blueprint): item "bp_<id>" que, ao sair da caixa, libera a receita e some.
BLUEPRINTS = {"o2_tank": "Tanque de O₂", "scanner": "Scanner de navegação", "lamp_t2": "Luminária forte"}
BLUEPRINT_ITEMS = {f"bp_{k}": k for k in BLUEPRINTS}
RECIPE_BLUEPRINT = {"o2_tank": "o2_tank", "scanner": "scanner", "lamp_t2": "lamp_t2"}   # receita -> projeto

# Luminária forte (projeto): raio 7 tiles. A luminária comum tem 5.
LAMP_RADIUS = {"lamp": 5, "lamp_t2": 7}
MACHINES["lamp_t2"] = MachineType("lamp_t2", "Luminária forte", "luz maior", {"iron": 2, "silicon": 2, "ice": 1},
                                  None, 0, 0, "lamp_t2")
MACHINE_ORDER.append("lamp_t2")
# Equipamento (game/equipment.py): itens que vão num slot do traje (tela do Tab), não na hotbar nem no chão.
MACHINES["o2_tank"] = MachineType("o2_tank", "Tanque de O₂", "O₂ dura 220 s", {"iron": 10, "silicon": 6, "ice": 4},
                                  None, 0, 0, "icon_o2_tank", placeable=False)
MACHINES["scanner"] = MachineType("scanner", "Scanner de navegação", "mapa [M]", {"iron": 4, "silicon": 4},
                                  None, 0, 0, "icon_scanner", placeable=False)
MACHINE_ORDER += ["o2_tank", "scanner"]
FAB_TABS = FAB_TABS + (("suit", "Traje"),)
MACHINE_CATEGORY.update({"lamp_t2": "light", "o2_tank": "suit", "scanner": "suit"})
EQUIP_SLOTS = ("o2_tank", "scanner")          # um slot por tipo de equipamento (ordem na tela)
EQUIP_LABEL = {"o2_tank": "TANQUE", "scanner": "SCANNER"}
O2_TANK_MAX = 220.0             # O₂ máximo com o tanque equipado (sem ele: O2_MAX = 100)

# Explorado (game/explore.py): o jogo registra o que o jogador viu desde o começo, em cada camada.
EXPLORE_INTERVAL = 0.2          # s entre atualizações
EXPLORE_SURFACE = (20, 12)      # superfície: meia-largura/meia-altura (tiles) do que se vê (a tela no zoom 0,75)
EXPLORE_HELMET = 4              # caverna: o que a luz revela (raios em tiles, iguais aos do game/lighting.py)
EXPLORE_RAMP = 3.5
EXPLORE_TERMINAL = 2
EXPLORE_MACHINE = 1.8
MINIMAP_TILES = 64              # o minimapa mostra 64×64 tiles em volta do player (2 px nativos por tile)
MAP_OPEN_COOLDOWN = 0.3         # M: no máximo 1 som de abrir a cada 0,3 s
BLUEPRINT_NOTICE_TIME = 3.5     # s do aviso "PROJETO: ..."
BLUEPRINT_SOUND_DELAY = 0.4     # s depois do crate_open (dica do Som)
BLUEPRINT_DUCK = (0.6, 2.0)     # ambiente a 60% por 2 s quando acha um projeto
VOLUME.update({"crate_open": 0.9, "blueprint_found": 1.0, "equip": 0.7, "map_open": 0.6})

# ---------------------------------------------------------------------------
# Fabricar em campo (kit de campo · bíblia §9): aba "Fabricar" do Tab, longe da base. Mesmas receitas, custo e
# travas (Ti e projeto) do fabricador, mas gasta SÓ do inventário (não puxa dos baús da base). Terraformação,
# energia, drones e equipamentos ficam só no fabricador: é o motivo de ainda voltar pra base.
# ---------------------------------------------------------------------------
FIELD_RECIPES = ("drill", "lamp", "lamp_t2", "chest")

# ---------------------------------------------------------------------------
# Tempestade de poeira (v0.4 Marco 1 · bíblia, seção da tempestade): o clima mora em game/weather.py.
# Tudo aqui é multiplicado pela intensidade da tempestade (state.storm, 1 = cheia, 0 = sem tempestade).
# ---------------------------------------------------------------------------
STORM_VIEW_TILES = 7.0          # raio de visão na tempestade (tiles)
STORM_GUST_VIEW_TILES = 4.0     # raio de visão no pico da rajada
STORM_GUST_EVERY = (20.0, 40.0)  # s entre o começo de uma rajada e o da próxima (sorteio com seed)
STORM_GUST_FIRST = (10.0, 20.0)  # s até a 1ª rajada (mais cedo, pro jogador conhecer a mecânica)
STORM_GUST_LEN = (3.0, 5.0)     # s de duração de cada rajada
STORM_GUST_MIN_STORM = 0.99    # rajada nova só com a tempestade cheia (na transição pro Árido elas param)
STORM_GUST_RAMP = 0.5           # s pro gust ir de 0 a 1 (e de 1 a 0): sobe e desce suave
STORM_PUSH = 0.35               # empurrão no pico da rajada, em fração da PLAYER_SPEED (dá pra vencer andando)
STORM_O2_MULT = 1.25            # O₂ gasta ×1,25 fora da base na tempestade cheia (interpola com o storm)
STORM_WIND_TURN = 8.0           # °/s: o vento vira no máximo isso (variação lenta)
STORM_WIND_SWAY = 40.0          # °: quanto o vento foge da direção dominante (sorteada pela seed)
STORM_WIND_RETARGET = (6.0, 14.0)  # s entre um novo alvo de direção e o próximo
STORM_GUST_WARN = 0.3           # gust acima disso: aviso "RAJADA" no HUD
VOLUME["gust"] = 0.7            # som da rajada (sem gust.wav, fica em silêncio); vezes o storm
