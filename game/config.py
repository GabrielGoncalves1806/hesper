"""Todas as constantes do jogo num lugar só.

Se tu quer mudar um número de balanceamento, uma cor ou uma receita, é aqui.
Os valores vêm do docs/GAME_BIBLE.md (§3 paletas, §4 escopo do MVP, §6 assets).
"""

from dataclasses import dataclass
from dataclasses import replace as _replace
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
    "stage_up": 0.85, "sky_clear": 0.8,
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
# Seed padrão: só do smoke, dos testes e do fundo da tela de título. O jogo de verdade usa a seed de cada
# mundo (`state.seed`, escolhida ou sorteada no "Novo mundo", game/worlds.py).
WORLD_SEED = 7
WORLD_NAME_MAX = 20             # caracteres do nome do mundo

# Duas camadas (v0.3, bíblia §9): a SUPERFÍCIE (deserto aberto, onde fica a base) e a CAVERNA (o gerador
# antigo do world.py, que entra de verdade no Marco 2). Cada uma tem o próprio mapa (game/layers.py).
SURFACE_W = SURFACE_H = 256     # deserto (game/surface_gen.py). v0.5 M3.1: era 192; o que depende do tamanho deriva daqui
GEO_REF_SIZE = 192              # tamanho do deserto pro qual os números GEO_* foram ajustados (game/geo.py escala por SURFACE/isto)
SURFACE_AREA_SCALE = SURFACE_W * SURFACE_H / GEO_REF_SIZE ** 2   # quanto a área cresceu: o que se espalha pelo mapa todo (morros, teto de rochas) segue isto
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
FORMATION = 14                  # pegada de uma formação fixa (v0.4 Marco 2): sólida, não minera, não é parede
                                # (quem desenha é o objeto da formação, game/geo.py · Formation)
CONTAINER = 15                  # contêiner lacrado atrás de um gelo-portão (v0.4 Marco 3 · M3.2): 1 tile sólido baixo,
                                # não abre nem minera (quem desenha é o render, como a caixa de saque)
SMALL_MAGMATITE = 16            # rocha pequena de magmatita (v0.4 · bíblia §12): só em volta das fumarolas
                                # (game/magmatite.py), sem veio e sem minério de parede
ORE_TILES = {IRON: "iron", SILICON: "silicon", ICE: "ice"}            # minério NA PAREDE (overlay no topo)
SMALL_ROCKS = {SMALL_IRON: "iron", SMALL_SILICON: "silicon", SMALL_ICE: "ice", SMALL_MAGMATITE: "magmatite"}
WALL_TILES = {ROCK, IRON, SILICON, ICE, BEDROCK, TERMINAL}            # paredes ALTAS (topo elevado + face)
FLAT_SOLIDS = set(SMALL_ROCKS) | {CRATER, WRECK, LOOT_CRATE, FORMATION, CONTAINER}                         # sólidos baixos: bloqueiam, mas não têm altura
SOLID_TILES = WALL_TILES | FLAT_SOLIDS
FLOOR_TILES = {FLOOR, SAND}
TILE_RESOURCE = {**ORE_TILES, **SMALL_ROCKS}                          # o que cada tile dá ao quebrar

# Terminais de lore da caverna: (distância em tiles do centro, ângulo em graus). Distâncias crescentes.
TERMINAL_SPOTS = [(19, 35), (31, 160), (45, 280)]

# Gerador do deserto (game/surface_gen.py · bíblia §9, Marco 1)
SURFACE_BORDER = (2, 3)         # cordilheira da borda: 2 ou 3 tiles de espessura (intransponível, não minera)
HILLS = (26, 34)                # quantos morros de rocha (minerável). v0.4 Marco 2: era 24–32; bacia e salar sem morro
HILL_SIZE = (3, 8)              # largura do morro em tiles
                                # (v0.4 Marco 2: a chance de minério do morro é por região, HILL_REGION_ORE_CHANCE)
SURFACE_CLEAR_RADIUS = 8        # raio de areia limpa em volta da cápsula
SURFACE_CRATER_DIST = (15, 20)  # distância (tiles) do centro da cratera até a base
SURFACE_VEINS = (3, 5)          # veios de drill na superfície: poucos, longe, obrigam a explorar
SURFACE_VEIN_MIN_DIST = 35      # nenhum tile de veio a menos disso da base
SURFACE_VEIN_MAX_DIST = 88      # ...nem a mais disso (o alcance do mapa de 192: o mapa cresce na borda, o ritmo da coleta não muda)
SURFACE_ICE_VEIN_MAX_DIST = 120  # v0.5 M3.3: o veio de gelo só nasce na faixa gelada, que começa a ~95 tiles da base (teto: metade do mapa - 8)
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
BASE_TILE = (SURFACE_W // 2, SURFACE_H // 2)  # o meio do mapa: o tile logo abaixo da cápsula, à direita do meio
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
             SMALL_IRON: 0.7, SMALL_SILICON: 0.7, SMALL_ICE: 0.7,   # rocha pequena: rapidinha
             SMALL_MAGMATITE: 0.9}                                  # magmatita: basalto, um pouco mais dura
DROP_MIN, DROP_MAX = 1, 2       # minério de parede
DROP_RANGE = {k: (2, 4) for k in SMALL_ROCKS}   # rocha pequena dá 2 a 4 (o resto usa DROP_MIN/MAX)
MINE_REACH = 2              # alcance em tiles (distância de Chebyshev a partir do tile do player)
MINE_HIT_INTERVAL = 0.25    # som de picareta a cada 0,25 s

RESOURCES = ("iron", "silicon", "ice", "magmatite")
# Os que têm veio e minério de parede (drill, caverna, sorteio dos veios da superfície). A magmatita (v0.4, bíblia
# §12) é só rocha solta em volta das fumarolas: fica fora daqui pra não mexer no sorteio dos veios.
VEIN_RESOURCES = ("iron", "silicon", "ice")
RESOURCE_LABEL = {"iron": "FERRO", "silicon": "SILICIO", "ice": "GELO", "magmatite": "MAGMATITA"}   # HUD (Silkscreen)
RESOURCE_NAME = {"iron": "ferro", "silicon": "silício", "ice": "gelo", "magmatite": "magmatita",
                 "water_capsule": "cápsula de água"}   # em frases (Pixelify); a cápsula (v0.5 M2) só entra por nome
RESOURCE_LABEL["water_capsule"] = "CÁPSULA"   # (idem: não é recurso, RESOURCES não tem ela)

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
        MachineType("heater", "Aquecedor", "+ calor", {"iron": 12, "silicon": 8, "magmatite": 3}, "heat", 4, 500,
                    "machine_heater"),
        MachineType("o2_t2", "Gerador de O₂ nv.2", "+ oxigênio", {"iron": 30, "silicon": 20, "ice": 10}, "o2", 25, 10_000, "machine_o2_t2"),
        MachineType("melter_t2", "Derretedor nv.2", "+ água", {"iron": 25, "ice": 30}, "water", 20, 10_000, "machine_melter_t2"),
        MachineType("heater_t2", "Aquecedor nv.2", "+ calor", {"iron": 35, "silicon": 25, "magmatite": 10}, "heat", 30,
                    10_000, "machine_heater_t2"),
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

# ---------------------------------------------------------------------------
# v0.5 Marco 2: cápsula de água e o inventário do derretedor
# ---------------------------------------------------------------------------
# A cápsula é um item (empilha como máquina, STACK_MACHINE) que só sai do derretedor: não tem receita nem categoria
# (registrada DEPOIS do MACHINE_ORDER, que fica sem ela), então nenhum menu de fabricar mostra. O Dispersor de O₂ (Dev C) vai gastar.
# Derretedor (nv.1 e nv.2): inventário de 2 slots, [0] entrada de gelo e [1] saída de cápsulas. Terraforma como
# sempre; em paralelo gasta MELTER_ICE_PER_CAPSULE de gelo a cada MELTER_CAPSULE_TIME s e põe 1 cápsula na saída.
# Saída cheia (1 pilha): não faz cápsula e NÃO gasta gelo; a terraformação segue igual. Números provisórios (balanceamento depois).
MELTER_KINDS = ("melter", "melter_t2")
MELTER_ICE_SLOT, MELTER_CAPSULE_SLOT = 0, 1
MELTER_SLOTS = 2
MELTER_ICE_PER_CAPSULE = 2
MELTER_CAPSULE_TIME = {"melter": 20.0, "melter_t2": 10.0}   # segundos por cápsula (× fator da energia)
MELTER_REACH = 56               # px entre os pés do player e a base do derretedor pro E (igual à drill)

MACHINE_ORDER = list(MACHINES)   # ordem no fabricador e nas teclas 1–7
MACHINES["water_capsule"] = MachineType("water_capsule", "Cápsula de água", "água pro Dispersor", {}, None, 0, 0,
                                        "icon_water_capsule", placeable=False)
# v0.4 M3.4: máquinas de nome feminino (o aviso "Luminária submersa" / "Aquecedor submerso" concorda)
MACHINE_FEMININE = {"drill", "drone_station", "lamp", "lamp_t2", "workbench"}
DISMANTLE_KEY = "Clique direito"   # o botão de desmontar (segurar): dica do canto e aviso de submersa
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

# ---- v0.4 Marco 3 (M3.3): lagos nas bacias e chuva (números de partida; balanceamento no Marco 4) ----
# Lago: o índice de água (ppm) em que a água chega em cada marca do geo (GEO_LEVELS L1, L2, L3). Abaixo do 1º,
# seco; entre eles, a altura da água interpola; acima do último, fica em L3. Só a partir da Névoa (§3).
LAKE_WATER = (3000, 15000, 40000)
LAKE_STEP = 0.004            # a água só sobe de LAKE_STEP em LAKE_STEP de altura (o render e o mapa refazem pouco)
LAKE_SHORE = 3               # tiles: plantas na beira d'água (ou da bacia) até essa distância
# M3.5: margem orgânica (game/lake.py). Só desenho: a água continua por tile no jogo (is_water).
LAKE_BLOCK_TILES = 8         # a água é assada em blocos de 8×8 tiles (256×256 px)
LAKE_BAKE_MS = 2.0           # orçamento por quadro pra assar (no mínimo 1 bloco); o nível sobe poucas vezes por minuto
LAKE_CACHE_BLOCKS = 64       # LRU dos blocos assados
PLANT_CHANCE_SHORE = 0.30    # Verde, com geo: chance de planta na beira d'água
PLANT_CHANCE_FAR = 0.05      # Verde, com geo: chance de planta longe da água
# Chuva (game/rain.py): pancadas determinísticas pela seed. Intervalo de começo a começo, duração e 1ª pancada
# depois de entrar na Névoa. No Verde, mais curtas.
RAIN_MIST_LEN = (30.0, 60.0)
RAIN_MIST_EVERY = (60.0, 120.0)
RAIN_GREEN_LEN = (15.0, 30.0)
RAIN_GREEN_EVERY = (60.0, 120.0)
RAIN_FIRST = (15.0, 40.0)
RAIN_RAMP = 2.0              # s pra intensidade ir de 0 a 1 (e de 1 a 0)
RAIN_MAX_DROPS = 300         # traços na tela com a chuva cheia
RAIN_SPEED = 620.0           # px/s da queda
RAIN_SLANT = 0.45            # quanto o vento entorta a queda (vx = vento.x × RAIN_SPEED × RAIN_SLANT)
RAIN_LEN = (10, 18)          # px de cada traço
RAIN_ALPHA = (70, 130)       # alfa dos traços
RAIN_TINT = 34               # alfa máximo do véu cinza-azulado com a chuva cheia
VOLUME["amb_rain"] = 0.55   # chuva (v11, canal 10): volume = 0,55 × intensidade. As variações (light/heavy) usam o mesmo
# RAIN_VARIANTS_* abaixo: cada pancada sorteia uma; amb_rain é a média (a principal).
RAIN_VARIANTS_MIST = (("amb_rain", 0.6), ("amb_rain_light", 0.2), ("amb_rain_heavy", 0.2))   # (arquivo, peso)
RAIN_VARIANTS_GREEN = (("amb_rain", 0.5), ("amb_rain_light", 0.5))                         # no Verde, sem a forte
VOLUME["vent_hiss"] = 0.6   # chiado da fumarola acordada mais perto (canal 11): × fade pela distância

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
    "magmatite": ("#ff7a2e", "#a8361a"),   # laranja-lava (a fissura da pedra), sombra de brasa
    "water_capsule": ("#59d0e6", "#2a7f96"),   # v0.5 M2: só pra pepita do drone e aviso flutuante (não é minério)
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
TRANSITION_FRONT_FAR = round(SURFACE_W * 0.78)   # tiles extras que ela dispara no fim, pra chegar nas bordas do mapa (era 150 no de 192)
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
INVENTORY_SLOTS = 16            # inventário do player sem a mochila: 2 linhas de 8 (a hotbar + 1 linha)
BACKPACK_SLOTS = 8              # a mochila (equipamento do traje) acrescenta +1 linha de 8: 24 slots no total
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
LOGISTIC_ITEMS = RESOURCES + ("water_capsule",)   # itens com toggle no painel (v0.5 M2: a cápsula de água entra aqui)
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
CRAFT_VISIBLE_ROWS = 4          # fabricador (só itens): 4 linhas, o resto da coluna é a área "Diagramas" (v0.5 M1)
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

# Diagramas (v0.5 M1, antes "projetos"): item "diagram_<id>" que fica no inventário como item normal. Ler na bancada
# (GameState.read_diagram) gasta 1 e libera a receita pra sempre (state.blueprints). O save antigo tinha "bp_<id>".
BLUEPRINTS = {"o2_tank": "Tanque de O₂", "scanner": "Scanner de navegação", "lamp_t2": "Luminária forte",
              "workbench": "Bancada T2"}
WRECK_DIAGRAMS = ("o2_tank", "scanner", "lamp_t2")   # os que dão nos destroços (o da Bancada T2 se fabrica no T1)
DIAGRAM_ITEMS = {f"diagram_{k}": k for k in BLUEPRINTS}
LEGACY_DIAGRAM_ITEMS = {f"bp_{k}": f"diagram_{k}" for k in BLUEPRINTS}   # item do save antigo -> item de hoje
RECIPE_BLUEPRINT = {"o2_tank": "o2_tank", "scanner": "scanner", "lamp_t2": "lamp_t2",
                    "workbench": "workbench"}   # receita -> diagrama
# Bancada que lê cada diagrama ("t1" = o fabricador da cápsula, "t2" = a Bancada T2 do Dev B2). Diagrama de máquina
# (placeable) é lido em qualquer bancada (spec); os de item só na bancada daqui.
DIAGRAM_BENCH = {"o2_tank": "t1", "scanner": "t1", "lamp_t2": "t1", "workbench": "t1"}
BENCH_LABEL = {"t1": "FABRICADOR", "t2": "BANCADA T2"}

# Luminária forte (diagrama): raio 7 tiles. A luminária comum tem 5.
LAMP_RADIUS = {"lamp": 5, "lamp_t2": 7}
MACHINES["lamp_t2"] = MachineType("lamp_t2", "Luminária forte", "luz maior", {"iron": 2, "silicon": 2, "ice": 1},
                                  None, 0, 0, "lamp_t2")
MACHINE_ORDER.append("lamp_t2")
# Equipamento (game/equipment.py): itens que vão num slot do traje (tela do Tab), não na hotbar nem no chão.
MACHINES["o2_tank"] = MachineType("o2_tank", "Tanque de O₂", "O₂ dura 220 s", {"iron": 10, "silicon": 6, "ice": 4},
                                  None, 0, 0, "icon_o2_tank", placeable=False)
MACHINES["scanner"] = MachineType("scanner", "Scanner de navegação", "mapa [M]", {"iron": 4, "silicon": 4},
                                  None, 0, 0, "icon_scanner", placeable=False)
# v0.5 M1 B3: a mochila é equipamento do traje e dá +1 linha de BACKPACK_SLOTS no inventário (GameState.sync_backpack).
# A receita mora na Bancada T2 (T2_RECIPES, mais abaixo): o fabricador T1 não mostra ela.
MACHINES["backpack"] = MachineType("backpack", "Mochila", "+1 linha de slots", {"iron": 12, "silicon": 6},
                                   None, 0, 0, "icon_backpack", placeable=False)
MACHINE_ORDER += ["o2_tank", "scanner", "backpack"]
FAB_TABS = FAB_TABS + (("suit", "Traje"),)
MACHINE_CATEGORY.update({"lamp_t2": "light", "o2_tank": "suit", "scanner": "suit", "backpack": "suit"})
EQUIP_SLOTS = ("o2_tank", "scanner", "backpack")          # um slot por tipo de equipamento (ordem na tela)
EQUIP_LABEL = {"o2_tank": "TANQUE", "scanner": "SCANNER", "backpack": "MOCHILA"}
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
BLUEPRINT_NOTICE_TIME = 3.5     # s do aviso "DIAGRAMA: ..."
BLUEPRINT_SOUND_DELAY = 0.4     # s depois do crate_open (dica do Som)
BLUEPRINT_DUCK = (0.6, 2.0)     # ambiente a 60% por 2 s quando acha um diagrama
VOLUME.update({"crate_open": 0.9, "blueprint_found": 1.0, "equip": 0.7, "map_open": 0.6})


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
VOLUME["gust"] = 0.8            # som da rajada (sem gust.wav, fica em silêncio); vezes o storm

# ---------------------------------------------------------------------------
# v0.4 Marco 2 · Geografia nova (game/geo.py + game/surface_gen.py · bíblia §11). Mapa de referência aprovado:
# reports/design/regioes/mapa_regioes.png (tools/sprites/regions_core.gen_world, portado e variando pela seed).
# Posições em tiles, relativas à base (BASE_TILE), num deserto de GEO_REF_SIZE: o game/geo.py escala os números das
# REGIÕES (salar, basalto, faixa gelada, bacias) pelo tamanho real da superfície. O resto (cratera, formações, veios) fica absoluto.
# ---------------------------------------------------------------------------
REGIONS_PALETTES = SPRITES_DIR / "regions" / "regions_palettes.json"   # rampas, níveis, formações (Designer)
GEO_LEVELS = (0.19, 0.29, 0.385)    # altura (0..1) das marcas d'água L1 (Névoa), L2, L3 (Verde cheio)
GEO_WARP = 14                       # px: deslocamento máximo da borda entre regiões (borda orgânica)
GEO_PLATEAU_CORE = 16               # raio (tiles) em volta da base que é sempre planalto, sem bacia
# Salar: a maior bacia, uma elipse a leste. Centro relativo à base e raios (sorteio da seed entre mín e máx)
GEO_SALAR_OFFSET = ((55, 64), (6, 26))
GEO_SALAR_RADII = ((29, 34), (22, 27))
# Depressões pequenas do planalto: (deslocamento da base, raio); a seed mexe até GEO_BASIN_JITTER tiles
GEO_BASINS = (((-18, 18), 6.0), ((28, -26), 6.0), ((4, 46), 8.5))
GEO_BASIN_JITTER = 4
GEO_BASALT_X = (40, 48)             # basalto: x < ~44 (com ruído), alargando pro sudoeste a partir de y ~120...
GEO_BASALT_Y = (40, 48)             # ...e y > ~44
GEO_FROST_Y = (38, 45)              # faixa gelada: y < ~41 (com ruído) na borda norte; no mapa 256 (×sy) a borda cai a ~50–60 tiles. v0.5 M3.6.1: era (22, 26), uns 29–35

# Formações fixas (marcos). Pegada, âncora e região de cada uma vêm do regions_palettes.json da Designer.
GEO_FORMATIONS = {"monolith": (2, 3), "arch": (1, 2), "salt_ridge": (0, 0), "basalt_spires": (2, 3), "cone": (1, 1)}
FORMATION_MIN_BASE_DIST = 26        # tiles do centro da formação até a base (a cratera fica a 15–20)
FORMATION_SPACING = 16              # tiles entre formações (centro a centro)
FORMATION_HALO = 2                  # tiles livres em volta da pegada (os afloramentos ficam aqui; nada mais nasce)
FORMATION_HILL_GAP = 4              # morro nenhum a menos disso da pegada
# Formações pequenas (v9 · M3.0): miúdas, sem afloramento nem marcador no mapa. Por mundo, (mín, máx).
GEO_SMALL_FORMATIONS = {"split_rock": (4, 6), "salt_pillar": (0, 0), "lava_tube": (0, 0), "ice_needles": (3, 5)}
SMALL_FORMATION_MIN_BASE_DIST = 20  # tiles do centro dela até a base
SMALL_FORMATION_SPACING = 10        # tiles até qualquer outra formação (pequena ou grande), centro a centro
SMALL_FORMATION_HALO = 2            # tiles de folga em volta da pegada: na mesma região e fora de bacia
SMALL_FORMATION_BASIN_OK = ()   # dono: sal no lago dissolveria, então nenhuma formação de sal nasce em bacia
OUTCROPS = (3, 4)                   # afloramentos (rochas pequenas) por formação, a 1–2 tiles da pegada
OUTCROP_ORE = {"plateau": {"iron": 0.5, "silicon": 0.5}, "salar": {"silicon": 1.0},
               "basalt": {"iron": 1.0}, "frost": {"ice": 1.0}}

# Gelos-portão: 2 ou 3 bolsões na cordilheira do norte (anel de BEDROCK, não minera), cada um fechado por um
# gelo-portão 4×2 no corredor de baixo. Atrás: o lugar do destroço melhor e do contêiner lacrado (Marco 3).
ICE_GATES = (2, 3)
POCKET_SIZE = (8, 7)                # interior (largura, altura) em tiles, começando na linha 3
POCKET_WALL = 2                     # espessura do anel de rocha
POCKET_SPACING = 26                 # tiles entre os centros de dois bolsões

# v0.5 M3.6.2: bolsão grande da criatura (1 por mundo, lugar sorteado pela seed dentro da faixa gelada). Anel de BEDROCK
# de POCKET_WALL tiles, de forma orgânica (como os morros) em volta de um interior de até GIANT_POCKET_SIZE com o gelo
# gigante (pegada 7×3) no meio e >= 3 tiles de corredor em volta, e uma entrada GIANT_ENTRY_W de largura reta no fundo
# (virada pra fora da cordilheira do norte), aberta até a 6.3.
GIANT_POCKET_SIZE = (17, 13)        # caixa do interior (a forma orgânica cabe nela; o gelo + 3 tiles de corredor sempre dentro)
GIANT_ENTRY_W = 8                   # largura da entrada no muro de baixo (onde o portão grande entra na 6.3)
GIANT_APRON = (4, 2)                # folga livre na frente da entrada: (linhas, colunas de cada lado)
GIANT_GAP = 3                       # tiles entre o bolsão grande e os outros bolsões / formações
GIANT_MIN_BASE_DIST = 40            # tiles da base até o centro do bolsão
GIANT_VARIANTS = ("larva", "cocoon")   # as duas criaturas aprovadas pelo dono: o sorteio é pela seed
GIANT_SALT = 6203                   # sal do sorteio da variação
GIANT_BREATH_PAUSE = (9.0, 14.0)    # s parado no quadro 0 entre uma "respirada" e outra (sorteio)

# v0.4 Marco 3 · M3.2 (bíblia §12, "Gelos-portão"): os portões derretem com o calor, do 0 (o da esquerda) pro último.
# M3.5: cada portão é um amontoado de blocos (game/ice_blocks.py) e o progresso p (0..1) anda linear entre o 1º e o
# último marco de calor (pK) do trio dele (o do meio fica de referência). O 3º trio só vale com 3 bolsões.
# p é derivado do índice (layer.gate_melt, não vai no save). Números de partida: o balanceamento é no Marco 4.
THAW_GATE_HEAT = ((1500, 2500, 3500), (3500, 5000, 6500), (6000, 8000, 10000))
THAW_GATE_RECIPE_SALT = 9203        # a seed do mundo + isto escolhe a receita (A, B ou C) de cada portão
THAW_GATE_NOTICE = "Um gelo-portão abriu ao norte"
THAW_GATE_NOTICE_TIME = 4.0         # s do aviso
VOLUME.setdefault("ice_crack", 0.7)  # estalo do gelo (ice_crack.wav + ice_crack_1.wav, v11)
# Destroço rico: no wreck_spot de cada bolsão, uma nave de carga com o saque "rico" (mais material que a melhor
# nave de fora) e, se algum projeto de BLUEPRINTS não caiu nos destroços de fora, o 1º que faltar.
WRECK_RICH_KIND = "cargo"
WRECK_RICH_LOOT = {"iron": (30, 40), "silicon": (20, 28), "ice": (14, 20)}
# Contêiner lacrado no container_spot (gancho das peças raras do v0.5): não abre. O texto final passa pelo dono.
CONTAINER_LORE = "Contêiner lacrado · selo da Colônia Hesper · o lacre não cede com a ferramenta que você tem"
CONTAINER_REACH = 48                # px dos pés até a base dele (igual à caixa de saque)
CONTAINER_LORE_TIME = 4.5           # s do aviso com a dica de lore

# Morros por região (o salar quase sem morro, o basalto com mais) e o minério de cada uma
HILL_REGION_WEIGHT = {"plateau": 1.0, "salar": 0.05, "basalt": 2.2, "frost": 1.0}
HILL_REGION_ORE = {"plateau": {"iron": 0.45, "silicon": 0.35, "ice": 0.2},
                   "salar": {"silicon": 0.7, "iron": 0.15, "ice": 0.15},
                   "basalt": {"iron": 0.7, "silicon": 0.2, "ice": 0.1},
                   "frost": {"ice": 0.6, "iron": 0.2, "silicon": 0.2}}
HILL_REGION_ORE_CHANCE = {"plateau": 0.12, "salar": 0.12, "basalt": 0.16, "frost": 0.16}

# ---------------------------------------------------------------------------
# Chão assado da superfície (v0.4 Marco 2 · trilha B · bíblia §11): game/ground.py. Só vale com layer.geo.
# A arte (texturas 512×512, decalques, rampas por estágio) mora em assets/sprites/regions/.
# ---------------------------------------------------------------------------
REGIONS_DIR = SPRITES_DIR / "regions"
GROUND_BLOCK_TILES = 16          # o chão é assado em blocos de 16×16 tiles (512×512 px, o tamanho da textura)
GROUND_CACHE_BLOCKS = 40         # LRU: blocos guardados (cada um ~1,4 MB: índice + metade do mapa de tiles + RGB)
GROUND_BAKE_MS = 3.0             # orçamento por quadro pra assar (faixas de 32 linhas; no mínimo 1 por quadro)
GROUND_BAKE_ROWS = 32            # linhas por faixa do assado (cada faixa custa ~2,5 ms)
GROUND_PREFETCH_PX = 320         # assa antes os blocos até essa distância da tela (pra chegar pronto)
GROUND_DECAL_MARGIN = 128        # px: um decalque pode invadir o bloco vizinho até aqui (o maior tem 224×96)
GROUND_BASE_CLEAR = 6            # tiles: sem decalque nem decoração solta em volta da base
GROUND_DECOR_P = 0.035           # chance de decoração solta (lasca, cristal, gelo) por tile de basalto/salar/gelo
# Cobertura do estágio por cima do chão assado (v0.4 Marco 3 · porte do `Scene.cover_layer` da Designer · bíblia §11)
GROUND_COVER_CELL = 5.0          # tiles: tamanho da célula do ruído das manchas (fbm de 3 oitavas, domínio deformado)
GROUND_COVER_SEED = 313          # seed do ruído das manchas (soma a seed do mundo)
GROUND_GRASS_THR = (0.45, 0.70, 0.58, 2.0, 0.40)    # limiar da grama por classe: planalto, salar, basalto, gelada, leito (planalto 0,47 → 0,45: o dono quis mais grama no Verde, ~58% → ~65%; gelada 2,0 = nunca: o dono não quer grama na neve, v0.5 M3.3)
GROUND_GRASS_NEAR = 0.12         # perto da bacia o limiar cai isso (mais grama na beira)
GROUND_MIST_THR = 0.56           # Névoa: acima disso o chão fica úmido
GROUND_MIST_DAMP = (0.80, 0.84, 0.90)   # Névoa: multiplicador RGB do chão úmido
GROUND_MIST_EDGE = 0.90          # Névoa: a borda de cima da mancha escurece mais isso
GROUND_GRASS = ("#2f5a2a", "#3f6e30", "#4d7a39", "#5f9442", "#79b04f", "#9ccc62")   # rampa da grama (0 sem uso)
GROUND_MOSS = ("#22331f", "#2c4127", "#38502e", "#466338", "#5c7d45", "#75985a")    # rampa do musgo (basalto)

# ---------------------------------------------------------------------------
# Morros orgânicos da superfície (v0.4 Marco 2 · trilha C · bíblia §11): game/hills.py. A caverna fica igual.
# ---------------------------------------------------------------------------
ORGANIC_HILLS = True            # False = paredes da superfície do jeito antigo (tile + face)
ORGANIC_CAVE = True             # v0.5 M3.4 (game/cave_rocks.py): False = rocha da caverna quadrada, como antes
HILL_BLOCK = 8                  # morros assados em blocos de 8×8 tiles (256 px): ~3 ms por bloco
HILL_FACE = 24                  # px da face (a silhueta do topo extrudada pra baixo)
HILL_CACHE_BLOCKS = 96          # teto de blocos assados guardados (LRU): ~3 telas no zoom 0,75
HILL_PREFETCH = 1               # blocos de folga em volta da tela, assados no máximo 1 por frame

# Cratera de impacto (v0.4 Marco 2 · trilha C · C4): crater_impact_0..4.png + crater_ejecta.png (game/hills.py).
# A tampa de gelo (layer.crater_ice) vai de 0 (tampada) a CRATER_ICE_STAGES (vazia, rampa exposta); fechada,
# bloqueia a descida. No M2 fica sempre tampada: o derretimento pelo calor é do Marco 3.
CRATER_ICE_STAGES = 4

# v0.4 Marco 3 · M3.1: a cratera derrete com o calor e as fumarolas do basalto acordam (game/thaw.py · bíblia §12).
# Números de partida: o balanceamento é no Marco 4 (balance_sim registra em quanto tempo o casual abre a cratera).
GATE_HINT_HEIGHT_TILES = 5   # dica do gelo-portão: a caixa do portão e mais uns tiles pra cima (os blocos são altos)
THAW_CRATER_HEAT = (40, 90, 150, 220)   # pK: o calor em que a tampa baixa pra etapa 1, 2, 3 e 4 (~1 min de 1 aquecedor)
# Fumarolas (v9.1 da Designer, regions_palettes.json: formations.vent_*, smoke, vent_density). Cada uma acorda num
# limiar próprio entre THAW_FUMAROLE_HEAT[0] e [1] (o `wake` do JSON: entre a etapa 1 e a 4 da tampa da cratera).
THAW_FUMAROLE_HEAT = (THAW_CRATER_HEAT[0], THAW_CRATER_HEAT[-1])
THAW_FUMAROLE_HALO = 2           # tiles de folga em volta da pegada, todos no basalto e fora de bacia
THAW_FUMAROLE_SPACING = 8        # tiles entre duas fumarolas (centro a centro)
THAW_FUMAROLE_FORM_GAP = 6       # tiles até a formação mais perto (centro a centro)
THAW_FUMAROLE_CLUSTER = 0.6      # fração sorteada em volta do cone de escória (campo de fumarolas)...
THAW_FUMAROLE_NEAR_CONE = (10, 30)   # ...nesse anel (tiles do centro do cone); o resto é livre no basalto
THAW_FUMAROLE_SEED = 9151        # o sorteio delas tem rng próprio (seed + isso): não mexe no das outras formações
# Vento da fumaça (px/s) por estágio, vezes a direção do state.weather (e o `wind` 0,45 do bloco smoke do JSON).
# Na rajada da tempestade sopra até 2×. Números das prévias da Designer (regions_v91.WIND).
THAW_FUMAROLE_WIND = {"storm": 34.0, "arid": 9.0, "mist": 5.0, "green": 7.0}
THAW_FUMAROLE_WIND_Y = 0.25      # o vento pro norte/sul conta só 1/4 na tela (senão o vento pro sul segura a subida)
THAW_FUMAROLE_WAKE_S = 1.0       # s da fumaça subindo de 1/3 da taxa até a taxa cheia quando ela acorda
THAW_FUMAROLE_MAX_PUFFS = 220    # teto de puffs vivos na tela (com culling, sobra muito)
# M3.5 (pedido do dono: no basalto escuro a fumaça sumia): por cima do bloco `smoke` do JSON da Designer, sem mexer
# no asset. Puff nasce mais claro e mais opaco, vive um pouco mais, e a boca ganha um brilho quente bem leve.
SMOKE_OVERRIDE = {
    "color": ["#f6f3ee", "#d9d3cb", "#aaa49d"],   # antes #e9e4dc / #c4bdb4 / #958e88
    "alpha": [185, 135, 85],                      # antes 150 / 110 / 70 (por terço da vida)
    "life": [3.2, 4.2],                           # s; antes 2,6–3,4
}
THAW_FUMAROLE_GLOW = (255, 132, 56)   # brilho quente na boca da fumarola acordada (somado na tela)
THAW_FUMAROLE_GLOW_R = 7              # px de raio do brilho
THAW_FUMAROLE_GLOW_MAX = 56           # intensidade no centro (0..255, somada), pulsando devagar entre 60% e 100%
THAW_CRATER_NOTICE_S = 3.5        # s do aviso "O gelo da cratera está cedendo" / "A cratera abriu"
VOLUME["ice_crack"] = 0.7        # gelo estalando (ice_crack.wav / ice_crack_1.wav, v11): etapas 1–3 da cratera
VOLUME["ice_collapse"] = 0.8     # o gelo desabando (ice_collapse.wav, v11): cratera aberta (etapa 4) e gelo-portão na 3
ICE_COLLAPSE_CAVE_VOLUME = 0.5   # na caverna o desabamento sai a 0,5 (abafado pela rocha)
# Contador de desempenho (game/perf_meter.py): F5 liga/desliga; ligado por padrão enquanto o jogo está em desenvolvimento
# Cenário pausado pelo dono (catálogo do cenário, reports/design/catalogo_cenario): some do mundo, o sorteio não
# muda. Tira o nome da lista pra voltar.
SCENERY_PAUSED = frozenset({
    "decor_shards", "decor_salt_crystals", "decor_ice_chunks",        # soltos v8
    "decor_slabs", "decor_mud_curls", "decor_salt_mound", "decor_salt_slabs", "decor_pebbles",   # soltos v9
    "decal_gravel",                                                    # decalque v8
})
PERF_METER_ON = True
# Colisão da rocha pequena: só a base do desenho (x, y, w, h dentro do tile), não o tile inteiro (o sprite ocupa
# x 1–30, y 9–31; com o tile todo sólido o player travava no ar, longe da pedra · playtest do dono)
SMALL_ROCK_RECT = (3, 16, 26, 14)
PERF_WINDOW_S = 0.5             # janela da média e do pior quadro (s)
FRAME_BUDGET_MS = 1000 / 60     # orçamento de um quadro a 60 FPS
PERF_MS_LEVELS = (10.0, 14.0)   # média até 10 ms verde, até 14 amarelo, acima vermelho
DEBUG_MELT_CRATER = True        # F4 derrete a tampa na hora (atalho de debug, no mesmo esquema do F1–F3)

# ---------------------------------------------------------------------------
# Magmatita (v0.4 · bíblia §12 "Magmatita"; game/magmatite.py). Só nasce como rocha pequena (C.SMALL_MAGMATITE) em
# volta das fumarolas (geo.vents): nunca na pegada nem no halo dela (keep_clear), nem em bacia, e sempre com os 8
# vizinhos livres (não fecha caminho). Rng próprio pela seed: as rochas de antes não mudam.
# O Aquecedor custa MACHINES["heater"].cost["magmatite"] (3) e o nv.2 10; a rocha dá 2–4 (DROP_RANGE).
# ---------------------------------------------------------------------------
MAGMATITE_SEED = 7717              # rng próprio (seed + isso) do sorteio na geração e do reaparecimento
MAGMATITE_RING = (3, 5)            # tiles (Chebyshev) da caixa da pegada até a rocha: logo depois do halo de 2
MAGMATITE_DORMANT = (2, 3)         # rochas em volta de cada fumarola DORMENTE no mapa da seed: 2 já dão ≥ 4 (1 aquecedor)
MAGMATITE_DORMANT_MAX = 3          # dormente: reaparece até ter isso em volta...
MAGMATITE_DORMANT_RESPAWN = 120.0  # ...uma a cada 120 s
MAGMATITE_AWAKE_MAX = 6            # acordada: expele até 6 em volta...
MAGMATITE_AWAKE_RESPAWN = 20.0     # ...uma a cada 20 s
OBJECTIVE_HINT_TIME = 9.0          # s da dica do objetivo ("Os sensores detectaram calor a oeste..."), embaixo dele

# ---------------------------------------------------------------------------
# v0.4 M4 balanceamento: a rodada de tudo do v0.4 num bloco só (relatório: reports/dev/balanceamento_v04.md).
# Estes valores valem POR CIMA das definições acima, que guardam os números de partida do M1–M3 (o "era" de cada linha).
# Medido no tools/dev/balance_sim.py (5 seeds, 5 estratégias; casual = o jogador de referência), já com a magmatita.
# Ordem de jogo que sai daí, no casual: Ti 500 ~2 min · 1º aquecedor ~4 min · cratera ~8 min · Árido ~8m30s · Névoa +
# 1º lago ~10 min · portões ~16 / 22 / 28 min · lago médio ~16 min · lago cheio ~27 min · Verde ~35 min.
# ---------------------------------------------------------------------------
SMALL_ROCK_CHANCE = 0.019       # era 0,013 (~430 rochas no mapa, agora ~600): a bacia sem rocha e a ida à magmatita deixaram o casual em ~41 min; agora ~35
ROCK_MAX = round(700 * SURFACE_AREA_SCALE)   # (700 no mapa de 192; v0.5 M3.1: acompanha a área, já que as rochas pequenas são por tile) era 520: com ~600 rochas na partida o teto de 520 desligaria o reaparecimento (folga de ~100, como antes)
STAGES = [_replace(_s, ti=7_000) if _s.key == "arid" else _s for _s in STAGES]   # Árido: era 6.500 (com as rochas a mais o casual chegava em ~7m45s; a meta é 8–12 min, agora ~8m30s)
# Cratera (feedback do dono: abria rápido demais, ~55 s depois do 1º aquecedor): agora ~4 min de 1 aquecedor (4 pK/s),
# ~2 min com 2. As fumarolas seguem a mesma faixa (acordam uma a uma entre 1 e 4 min de aquecimento): a magmatita
# acordada (1 a cada 20 s) está lá bem antes do Aquecedor nv.2 (10 magmatita, Ti 10.000 ~ 10 min).
THAW_CRATER_HEAT = (200, 450, 750, 1000)   # era (40, 90, 150, 220)
THAW_FUMAROLE_HEAT = (THAW_CRATER_HEAT[0], THAW_CRATER_HEAT[-1])   # era (40, 220): continua atrelado à cratera
# Gelos-portão (feedback do dono: abriam rápido demais): recompensa de meio pro fim. O 1º abre no meio da partida (~45%),
# o 2º por volta de 65% e o último (precisa de Aquecedor nv.2) perto do Verde (~80%).
THAW_GATE_HEAT = ((2800, 4300, 5800), (5800, 8000, 10200), (14000, 18000, 22000))   # era ((1500, 2500, 3500), (3500, 5000, 6500), (6000, 8000, 10000))
# v0.5 M3.6.3 · portão grande (entrada do bolsão da criatura): o ÚLTIMO a derreter. Começa onde o 3º portão termina
# (22.000), então só abre depois de todos os outros. O calor que o jogo alcança até o Verde (balance_sim, 6 partidas
# casual/guloso/variado) fica entre ~28.000 e ~52.000 pK (casual: 28.000–31.500); a fresta abre com p ~0,57 (~25.400 pK,
# ~94% da partida do casual) e o gelo some em 28.000: perto do fim, nunca "nunca".
# Provisório, balancear depois (a passada única de números).
THAW_GIANT_HEAT = (22000, 25000, 28000)
LAKE_WATER = (2500, 7000, 15000)   # era (3000, 15000, 40000): L1 junto com a Névoa, L2 no meio do jogo (era ~32 min), L3 antes do Verde (o 40.000 nunca chegava)
# Mantidos de propósito: STAGES Névoa 10.000 e Verde 100.000, RAIN_* (o dono aprovou a chuva no playtest), O₂, receitas.

# ---------------------------------------------------------------------------
# v0.5 Marco 1 · Construtor e desmontar (spec docs/superpowers/specs/2026-10-14-v05-base-e-expedicao-design.md).
# Máquina não é mais item: o CONSTRUTOR (item da hotbar, 1ª receita do fabricador) é o único jeito de pôr máquina no
# chão. Com ele na mão, E abre o menu de construção (abas FAB_TABS); clique esquerdo constrói gastando a receita SÓ do
# inventário (travas de Ti e diagrama iguais). O fabricador da cápsula fica só com itens (o que não é `placeable`).
# A aba "Fabricar" do Tab (fabricar em campo, FIELD_RECIPES) saiu: as receitas dela eram todas máquinas.
# ---------------------------------------------------------------------------
MACHINES["constructor"] = MachineType("constructor", "Construtor", "constrói máquinas [E]", {"iron": 5}, None, 0, 0,
                                      "icon_constructor", placeable=False)
MACHINE_ORDER.insert(0, "constructor")      # 1ª receita do fabricador
MACHINE_CATEGORY["constructor"] = "tools"
# Abas do fabricador (só itens). As do construtor são as FAB_TABS sem a "Traje" (equipamento não vai pro chão).
CRAFT_TABS = (("tools", "Ferramentas"), ("automation", "Automação"), ("suit", "Traje"))
FAB_TABS = tuple(t for t in FAB_TABS if t[0] != "suit")
BUILD_TIME = 1.35               # s da máquina "se construindo" (scanner de baixo pra cima): parada, sem Ti nem energia.
                                # 1,35 = o clack do build.wav (Som): ela fica pronta junto com ele
DISMANTLE_HOLD = 2.0            # s segurando o botão direito em cima da máquina pra desmontar
# Luz de scanner (procedural no render: Renderer.draw_scan). Números de partida da Designer (reports/design/
# v05_m1_construtor, "Pro Dev integrar"; referência tools/sprites/v05_m1_construtor.py · scan_frame), ainda sem o ok
# do dono. Regra única nos dois sentidos: abaixo da faixa, a máquina; acima, o holograma (o contorno do sprite em
# SCAN_GHOST). Construir: a faixa sobe; desmontar: desce.
SCAN_FPS = 12                   # passos por segundo (a faixa anda em pixel inteiro, um passo por vez)
SCAN_CORE = "#ffffff"           # núcleo da faixa (1 px), só sobre a silhueta
SCAN_EDGE = "#c8f6ff"           # 1 px de cada lado do núcleo, sobre a silhueta
SCAN_PULSE = "#59d0e6"          # +1 px de cada lado nos passos ímpares (a faixa alterna 3 ↔ 5 px)
SCAN_PLANE = "#59d0e6"          # na linha do núcleo, SCAN_PLANE_OUT px pra fora da silhueta de cada lado...
SCAN_NODE = "#ffffff"           # ...com 1 px desse na ponta (o emissor)
SCAN_PLANE_OUT = 2
SCAN_GHOST = "#2b8fb3"          # holograma: o contorno (SCAN_OUTLINE) da parte ainda não construída
SCAN_OUTLINE = "#1b1630"        # a cor do contorno dos sprites (o que vira holograma)
SCAN_FRESH_ADD = (24, 56, 64)   # soma RGB (BLEND_RGB_ADD) nas linhas recém-reveladas logo abaixo da faixa...
SCAN_FRESH_ROWS = 2             # ...nessas 2 linhas
SCAN_SPARKS = 2                 # faíscas por passo (1 px, alternando núcleo/borda), só em pixel vazio
SCAN_SPARK_UP = (2, 5)          # de 2 a 5 px acima do núcleo
SCAN_FLASH_STEPS = 1            # fim da construção: 1 passo com a máquina inteira + SCAN_FRESH_ADD (dentro do BUILD_TIME)
SCAN_BLINK_STEPS = 3            # fim do desmonte: holograma apagado, aceso, apagado (e some)
DISMANTLE_BAR = (22, 3)         # barrinha do desmonte em cima da máquina (largura, altura em px do mundo)
# Sons do construtor (Som, aprovados pelo dono): o charge toca num canal só, começa junto com a barrinha e sai em
# fadeout curto se soltar; o dismantle_done (no lugar do place_low) entra no mesmo frame do desmonte completo.
VOLUME.update({"build": 0.55, "dismantle_charge": 0.45, "dismantle_done": 0.6,
               "diagram_read": 0.6})   # diagram_read: do Dev B (ler diagrama na bancada), só o volume
DISMANTLE_CHARGE_FADE_MS = 60   # soltou antes de completar: o charge sai em 60 ms (nunca um stop seco)


# ---------------------------------------------------------------------------
# v0.5 Marco 1 · B2 · Bancada T2 (spec 2026-10-14-v05-base-e-expedicao-design.md)
# Máquina de chão (construtor), trancada pelo diagrama "workbench", que o fabricador T1 fabrica. O E perto dela abre o
# mesmo painel do fabricador com as receitas dela (T2_RECIPES): materiais SÓ do inventário (posto avançado).
# ---------------------------------------------------------------------------
BENCH_COST = {"iron": 20, "silicon": 10}          # número de partida (balanceamento depois)
BENCH_DIAGRAM_COST = {"iron": 15, "silicon": 8}   # o item diagram_workbench no fabricador T1 (partida)
BENCH_REACH = CHEST_REACH       # px dos pés até a base da bancada pro E (igual ao baú)
BENCH_SPRITE_SIZE = (32, 40)    # machine_workbench.png (parada) e cada quadro da tira anim_machine_workbench.png
BENCH_WORK_TIME = 2.0           # s que ela anima depois de fabricar (1 ciclo: 8 quadros a 4 fps)
BENCH_FPS = 4
MACHINES["workbench"] = MachineType("workbench", "Bancada T2", "fabrica fora da base", BENCH_COST, None, 0, 0,
                                    "machine_workbench")
MACHINE_ORDER.append("workbench")
MACHINE_CATEGORY["workbench"] = "automation"
POWER_USE["workbench"] = 1
# O item do diagrama: sai do fabricador T1 (aba Ferramentas), vai pro inventário e é lido como qualquer diagrama.
MACHINES["diagram_workbench"] = MachineType("diagram_workbench", "Diagrama: Bancada T2", "libera a Bancada T2",
                                            BENCH_DIAGRAM_COST, None, 0, 0, "icon_diagram", placeable=False)
MACHINE_ORDER.append("diagram_workbench")
MACHINE_CATEGORY["diagram_workbench"] = "tools"
# Receitas da Bancada T2 (itens, ids de MACHINES). O fabricador T1 não mostra estas (fabricator.craft_kinds).
T2_RECIPES: tuple[str, ...] = ("backpack",)   # a mochila (B3); a broca nv.2 entra no M4
T2_TABS = (("t2", "Itens"),)    # a Bancada T2 tem uma aba só por enquanto


# ---------------------------------------------------------------------------
# v0.5 Marco 2 · Base respirável (spec 2026-10-14-v05-base-e-expedicao-design.md · lógica em game/base.py)
# Blocos do construtor (chão, parede, porta solo e porta dupla), a vedação (flood fill a partir do Dispersor) e o
# Dispersor de O₂. Arte aprovada: reports/design/v05_m2_base (v1.2, porta na variante B). Números PROVISÓRIOS
# (balanceamento depois).
# ---------------------------------------------------------------------------
BASE_FLOOR, BASE_WALL, BASE_DOOR, BASE_DOOR2 = "base_floor", "base_wall", "base_door", "base_door2"
BASE_KINDS = (BASE_FLOOR, BASE_WALL, BASE_DOOR, BASE_DOOR2)
BASE_DOOR_KINDS = (BASE_DOOR, BASE_DOOR2)
BASE_COST = {BASE_FLOOR: {"iron": 1}, BASE_WALL: {"iron": 2},
             BASE_DOOR: {"iron": 4, "silicon": 2}, BASE_DOOR2: {"iron": 8, "silicon": 4}}
BASE_NAME = {BASE_FLOOR: ("Chão da base", "piso, aceita máquina"), BASE_WALL: ("Parede da base", "bloqueia, veda"),
             BASE_DOOR: ("Porta", "abre sozinha, veda"), BASE_DOOR2: ("Porta dupla", "2 tiles · R gira")}
BASE_ICON = {BASE_FLOOR: "icon_base_floor", BASE_WALL: "icon_base_wall", BASE_DOOR: "icon_base_door",
             BASE_DOOR2: "icon_base_door_double"}
FLOOR_PICK = (0, 0, 0, 0, 1, 1, 2, 3)     # sorteio do chão por hash do tile: (tx·73856093 ^ ty·19349663) & 7
BASE_WALL_LIFT = 24                       # a parede da base tem a altura da parede de rocha (WALL_LIFT)
BASE_FACE_Y = 8                           # a face (32×24) começa 8 px abaixo do topo do tile
DOOR_OPEN_RANGE = 1.5 * TILE              # a porta abre com o player a até 1,5 tile do tile (de qualquer tile da dupla)
DOOR_FPS = 12                             # 4 quadros (0 fechada .. 3 aberta) a ~12 fps
DOOR_FRAMES = 4
DOOR_XRAY_FRAMES = 2                      # quadros 0–1 entram no raio-x; 2–3 (passagem aberta) não
DOOR_VOLUME_RANGE = (3, 12)               # tiles: o som da porta cheio até 3, some em 12
# Vedação
BASE_MIN_FLOOR = 9                        # o 3×3 mínimo, em qualquer formato
BASE_MIN_DOORS = 1
BASE_MAX_FLOOR = 200                      # acima disso o flood fill para (barato) e a base não vale
BASE_LOG_KEEP = 64                        # mudanças de bloco lembradas pro recálculo só quando mexe perto
# Dispersor de O₂
DISPENSER = "o2_dispenser"
DISPENSER_SLOTS = 1                       # 1 slot, só cápsula de água
DISPENSER_CAPSULE_SLOT = 0
DISPENSER_CAPSULE_TIME = 180.0            # s (3 min) que 1 cápsula dura, contados só com a base vedada e ligado
DISPENSER_REACH = MELTER_REACH
DISPENSER_SPRITE_SIZE = (32, 48)          # machine_o2_dispenser.png e cada quadro das tiras (4 quadros, ~6 fps)
DISPENSER_FPS = 6
LEAK_BLINK_HZ = 2.5                       # leak_blink.png: 2 quadros (aceso, apagado) alternando, 0,2 s cada
LEAK_ALERT_EVERY = 4.0                    # s entre os leak_alert enquanto vaza...
LEAK_ALERT_RANGE = 12                     # ...com o player a até 12 tiles da base (Dispersor ou tile furado)
SEAL_SOUND_COOLDOWN = 3.0                 # s: o base_sealed não repete antes disso (colocar/tirar parede)
STATE_LABEL = {"sealed": "Vedado ✓", "leak": "Vazamento", "dry": "Sem água", "nopower": "Sem energia",
               "small": "Base pequena", "nodoor": "Sem porta", "big": "Base grande", "nofloor": "Sem chão"}
STATE_COLOR = {"sealed": "#7fd67a", "leak": "#ffb347", "dry": "#8fa3b8", "nopower": "#ff6a55",
               "small": "#ffb347", "nodoor": "#ffb347", "big": "#ffb347", "nofloor": "#ffb347"}

for _kind in BASE_KINDS:
    _name, _desc = BASE_NAME[_kind]
    MACHINES[_kind] = MachineType(_kind, _name, _desc, BASE_COST[_kind], None, 0, 0, BASE_ICON[_kind])
    MACHINE_ORDER.append(_kind)
    MACHINE_CATEGORY[_kind] = "base"
MACHINES[DISPENSER] = MachineType(DISPENSER, "Dispersor de O₂", "base respirável", {"iron": 14, "silicon": 8},
                                  None, 0, 0, "machine_o2_dispenser")
MACHINE_ORDER.append(DISPENSER)
MACHINE_CATEGORY[DISPENSER] = "base"
POWER_USE[DISPENSER] = 1                  # 1 kW na rede, como as outras máquinas
FAB_TABS = FAB_TABS + (("base", "Base"),)  # o menu do construtor ganha a aba "Base" (o fabricador não: CRAFT_TABS)
# Sons (Som, v13.1, aprovados). door_*: sibilo curto, pitch 0,95–1,05; hum: loop com fade de 0,8 s (0,3 s ao secar)
VOLUME.update({"door_open": 0.45, "door_close": 0.45, "base_sealed": 0.6, "dispenser_hum": 0.35,
               "leak_alert": 0.55, "dispenser_dry": 0.5})
DISPENSER_HUM_FADE_MS, DISPENSER_HUM_DRY_FADE_MS = 800, 300
