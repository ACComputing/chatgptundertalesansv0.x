 import pygame
import sys
import math
from array import array

pygame.init()

# ======================
# WINDOW
# ======================
W, H = 640, 480
screen = pygame.display.set_mode((W, H))
pygame.display.set_caption("AC's ChatGPT Undertale Engine 0.1 - Last Corridor Engine")

clock = pygame.time.Clock()

# ----------------------
# SYNTH AUDIO (NO FILES)
# ----------------------
audio_ready = False
snd_menu_open = None
snd_menu_move = None
snd_sans_char = None
snd_sans_heya = None


def _make_tone(freq, ms, vol=0.18, square=False):
    if not audio_ready:
        return None
    sr = 22050
    n = max(1, int(sr * ms / 1000.0))
    amp = int(32767 * max(0.0, min(1.0, vol)))
    buf = array("h")
    for i in range(n):
        t = i / sr
        if square:
            v = amp if math.sin(2.0 * math.pi * freq * t) >= 0 else -amp
        else:
            v = int(amp * math.sin(2.0 * math.pi * freq * t))
        buf.append(v)
    return pygame.mixer.Sound(buffer=buf.tobytes())


def _init_audio():
    global audio_ready, snd_menu_open, snd_menu_move, snd_sans_char, snd_sans_heya
    try:
        pygame.mixer.init(frequency=22050, size=-16, channels=1, buffer=256)
        audio_ready = True
        snd_menu_open = _make_tone(820, 44, vol=0.16, square=True)
        snd_menu_move = _make_tone(620, 28, vol=0.14, square=True)
        snd_sans_char = _make_tone(380, 18, vol=0.12, square=True)
        snd_sans_heya = _make_tone(470, 24, vol=0.14, square=True)
    except pygame.error:
        audio_ready = False


def play_snd(s):
    if audio_ready and s is not None:
        s.play()


_init_audio()

# ======================
# COLORS
# ======================
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED = (255, 80, 80)
GRAY = (70, 70, 70)
GOLD_DARK = (69, 55, 20)
GOLD_MID = (121, 95, 39)
GOLD_LIGHT = (177, 142, 62)
WINDOW_GLOW = (255, 240, 150)
PILLAR_SHADE = (53, 41, 16)

# ======================
# FONT
# ======================
font = pygame.font.SysFont("courier", 22)
font_big = pygame.font.SysFont("courier", 40, bold=True)

# ======================
# STATES
# ======================
STATE_TITLE = "title"
STATE_MENU = "menu"
STATE_CORRIDOR = "corridor"
STATE_BATTLE = "battle"

state = STATE_TITLE

menu = ["START", "EXIT"]
sel = 0

# ======================
# ENGINE DATA
# ======================
last_room = "last_corridor"
room_loaded = False
camera_x = 0

# Keep overworld sprite/image files disabled on purpose.
OVERWORLD_SPRITE_FILES_OFF = True
SANS_INTERACT_RADIUS = 54
SAVE_INTERACT_RADIUS = 46


def load_overworld_sprite(path):
    if OVERWORLD_SPRITE_FILES_OFF:
        return None
    raise RuntimeError("Overworld sprite files are disabled in this build.")

# ----------------------
# ROOM DEFINITION
# ----------------------
rooms = {
    "last_corridor": {
        "name": "LAST CORRIDOR",
        "bg": (9, 8, 6),
        "world_w": 2200,
        "spawn": (120, H - 114),
        "walk_bounds": pygame.Rect(82, H - 146, 2200 - 164, 94),
        "left_arch_x": 58,
        "right_arch_x": 2200 - 110,
        "window_y": 90,
        "window_w": 112,
        "window_h": 106,
        "pillar_x": [180, 370, 560, 750, 940, 1130, 1320, 1510, 1700, 1890],
        "save_point": (164, H - 188),
        "sans_pos": (1080, H - 128),
        "throne_door": pygame.Rect(2200 - 158, H - 214, 82, 148),
    }
}

current_room = None

# ======================
# PLAYER
# ======================
player = pygame.Rect(0, 0, 18, 18)
speed = 4
dialog_active = False
dialog_lines = []
dialog_idx = 0
dialog_speaker = "sans"
sans_prompt_visible = False
save_prompt_visible = False
inventory_open = False
inventory_items = ["Bandage", "Pie Slice", "Stick"]
player_max_hp = 20
player_hp = 20
last_saved_at = None
checkpoint_pos = None
status_msg = ""
status_msg_timer = 0
sans_defeated = False

battle_menu = ["FIGHT", "ACT", "ITEM", "MERCY"]
battle_menu_idx = 0
battle_phase = "menu"
battle_msg = ""
sans_max_hp = 92
sans_hp = sans_max_hp
attack_meter_x = 0
attack_meter_dir = 1
dodge_timer = 0
dodge_box = pygame.Rect(180, 250, 280, 120)
battle_soul = pygame.Rect(dodge_box.centerx - 6, dodge_box.centery - 6, 12, 12)
bones = []
soul_iframes = 0
dialog_reveal_idx = 0
dialog_reveal_tick = 0
dialog_reveal_speed = 2
dialog_last_beep_tick = 0
dialog_pending_battle = False

SANS_DIALOG_DEFAULT = [
    "heya. you've been busy, huh.",
    "you've walked a long road to get here.",
    "the choices you made are still with you.",
    "well... only you can decide what comes next.",
]


# ======================
# LOAD ROOM (ENGINE CORE)
# ======================
def load_room(room_id):
    global current_room, room_loaded, player, camera_x, dialog_active, dialog_idx
    global dialog_lines, inventory_open, checkpoint_pos, status_msg_timer, status_msg
    global dialog_reveal_idx, dialog_reveal_tick, dialog_pending_battle

    current_room = rooms[room_id]
    player.x, player.y = current_room["spawn"]
    camera_x = 0
    dialog_active = False
    dialog_lines = []
    dialog_idx = 0
    inventory_open = False
    checkpoint_pos = tuple(current_room["spawn"])
    status_msg = ""
    status_msg_timer = 0
    dialog_reveal_idx = 0
    dialog_reveal_tick = 0
    dialog_pending_battle = False
    room_loaded = True


def set_status(text, frames=180):
    global status_msg, status_msg_timer
    status_msg = text
    status_msg_timer = frames


def save_nearby(room):
    sx, sy = room["save_point"]
    dx = player.centerx - sx
    # The star floats above the walk lane, so interaction checks against floor-aligned offset.
    dy = player.centery - (sy + 74)
    return dx * dx + dy * dy <= SAVE_INTERACT_RADIUS * SAVE_INTERACT_RADIUS


def trigger_save_checkpoint(room):
    global player_hp, last_saved_at, checkpoint_pos
    player_hp = player_max_hp
    last_saved_at = pygame.time.get_ticks()
    checkpoint_pos = (player.x, player.y)
    set_status("* FILE SAVED. HP restored.", 210)


def sans_nearby(room):
    sx, sy = room["sans_pos"]
    dx = (player.centerx - sx)
    dy = (player.centery - sy)
    return dx * dx + dy * dy <= SANS_INTERACT_RADIUS * SANS_INTERACT_RADIUS


def start_sans_dialog(start_battle=False):
    global dialog_active, dialog_lines, dialog_idx, dialog_speaker
    global dialog_reveal_idx, dialog_reveal_tick, dialog_pending_battle
    dialog_active = True
    dialog_lines = list(SANS_DIALOG_DEFAULT)
    dialog_idx = 0
    dialog_speaker = "sans"
    dialog_reveal_idx = 0
    dialog_reveal_tick = 0
    dialog_pending_battle = start_battle


def advance_dialog():
    global dialog_active, dialog_idx, dialog_lines, dialog_reveal_idx, dialog_reveal_tick
    global dialog_pending_battle
    if not dialog_active:
        return
    cur = dialog_lines[dialog_idx]
    if dialog_reveal_idx < len(cur):
        dialog_reveal_idx = len(cur)
        return
    dialog_idx += 1
    if dialog_idx >= len(dialog_lines):
        dialog_active = False
        dialog_lines = []
        dialog_idx = 0
        dialog_reveal_idx = 0
        dialog_reveal_tick = 0
        if dialog_pending_battle:
            dialog_pending_battle = False
            begin_sans_battle()
        return
    dialog_reveal_idx = 0
    dialog_reveal_tick = 0


def update_dialog_typewriter():
    global dialog_reveal_idx, dialog_reveal_tick, dialog_last_beep_tick
    if not dialog_active or not dialog_lines:
        return
    line = dialog_lines[dialog_idx]
    if dialog_reveal_idx >= len(line):
        return
    dialog_reveal_tick += 1
    if dialog_reveal_tick < dialog_reveal_speed:
        return
    dialog_reveal_tick = 0
    dialog_reveal_idx += 1
    ch = line[dialog_reveal_idx - 1]
    if not ch.isalnum():
        return
    now = pygame.time.get_ticks()
    if now - dialog_last_beep_tick < 16:
        return
    dialog_last_beep_tick = now
    lower = line.lower()
    hs = lower.find("heya")
    use_heya = hs != -1 and hs <= (dialog_reveal_idx - 1) < hs + 4
    play_snd(snd_sans_heya if use_heya else snd_sans_char)


def begin_sans_battle():
    global state, battle_menu_idx, battle_phase, battle_msg
    global sans_hp, attack_meter_x, attack_meter_dir, dodge_timer, bones
    global soul_iframes, battle_soul
    state = STATE_BATTLE
    battle_menu_idx = 0
    battle_phase = "menu"
    battle_msg = "* Sans blocks the way."
    sans_hp = sans_max_hp
    attack_meter_x = 0
    attack_meter_dir = 1
    dodge_timer = 0
    bones = []
    soul_iframes = 0
    battle_soul.topleft = (dodge_box.centerx - 6, dodge_box.centery - 6)


def spawn_bones():
    global bones
    bones = []
    top = dodge_box.y + 12
    for i in range(6):
        y = top + i * 16
        vx = 4 if i % 2 == 0 else -4
        x = dodge_box.left - 40 if vx > 0 else dodge_box.right + 10
        bones.append({"rect": pygame.Rect(x, y, 32, 8), "vx": vx})


def start_enemy_turn():
    global battle_phase, dodge_timer, battle_msg, soul_iframes
    battle_phase = "dodge"
    dodge_timer = 210
    soul_iframes = 0
    battle_soul.topleft = (dodge_box.centerx - 6, dodge_box.centery - 6)
    spawn_bones()
    battle_msg = "* Survive Sans's attack!"


def draw_sans(room):
    sx, sy = room["sans_pos"]
    px = sx - camera_x
    py = sy
    if px < -40 or px > W + 40:
        return

    # simple procedural Sans silhouette
    pygame.draw.circle(screen, WHITE, (px + 9, py + 8), 8)                      # head
    pygame.draw.rect(screen, (30, 100, 210), (px + 2, py + 18, 14, 9))          # jacket
    pygame.draw.rect(screen, BLACK, (px + 3, py + 27, 5, 7))                    # left leg
    pygame.draw.rect(screen, BLACK, (px + 10, py + 27, 5, 7))                   # right leg
    pygame.draw.circle(screen, BLACK, (px + 6, py + 8), 1)                       # eye
    pygame.draw.circle(screen, BLACK, (px + 12, py + 8), 1)                      # eye
    pygame.draw.line(screen, BLACK, (px + 6, py + 12), (px + 12, py + 12), 1)    # smile


def draw_dialog_box():
    if not dialog_active or not dialog_lines:
        return
    box = pygame.Rect(16, H - 132, W - 32, 116)
    pygame.draw.rect(screen, BLACK, box)
    pygame.draw.rect(screen, WHITE, box, 3)

    who = font.render("* " + dialog_speaker, True, WHITE)
    line_txt = dialog_lines[dialog_idx][:dialog_reveal_idx]
    line = font.render(line_txt, True, WHITE)
    cont = font.render("Z/ENTER", True, GRAY)
    screen.blit(who, (box.x + 14, box.y + 12))
    screen.blit(line, (box.x + 14, box.y + 46))
    screen.blit(cont, (box.right - 108, box.bottom - 28))


def draw_inventory_overlay():
    if not inventory_open:
        return
    panel = pygame.Rect(54, 44, W - 108, H - 88)
    pygame.draw.rect(screen, BLACK, panel)
    pygame.draw.rect(screen, WHITE, panel, 3)

    title = font.render("INVENTORY", True, WHITE)
    screen.blit(title, (panel.x + 14, panel.y + 12))
    pygame.draw.line(screen, WHITE, (panel.x + 12, panel.y + 44), (panel.right - 12, panel.y + 44), 2)

    if inventory_items:
        for i, item in enumerate(inventory_items):
            line = font.render(f"{i+1}. {item}", True, WHITE)
            screen.blit(line, (panel.x + 18, panel.y + 58 + i * 30))
    else:
        empty = font.render("* empty", True, GRAY)
        screen.blit(empty, (panel.x + 18, panel.y + 58))

    hint = font.render("E / ESC / X = CLOSE", True, GRAY)
    screen.blit(hint, (panel.x + 18, panel.bottom - 34))


def draw_status_line():
    if status_msg_timer <= 0 or not status_msg:
        return
    text = font.render(status_msg, True, WINDOW_GLOW)
    screen.blit(text, (20, 36))


def draw_frisk_sprite(x, y, scale=2, blink=False):
    # Clean OG-style Frisk traced as pure pixel blocks (transparent background).
    hair = (97, 62, 35)
    skin = (246, 213, 175)
    shirt_blue = (45, 86, 190)
    shirt_stripe = (208, 78, 52)
    pants = (46, 52, 132)
    shoes = (64, 38, 24)
    if blink:
        hair = (125, 98, 72)
        skin = (255, 236, 220)

    # 8x12 template. Only painted pixels are drawn, so bg remains transparent.
    px = [
        # Hair
        (1, 0, 6, 1, hair),
        (0, 1, 8, 1, hair),
        (0, 2, 2, 1, hair), (6, 2, 2, 1, hair),
        (0, 3, 1, 1, hair), (7, 3, 1, 1, hair),
        # Face
        (2, 2, 4, 2, skin),
        (1, 3, 1, 1, skin), (6, 3, 1, 1, skin),
        (2, 4, 4, 1, skin),
        # Shirt (blue + magenta stripes)
        (1, 5, 6, 1, shirt_blue),
        (1, 6, 6, 1, shirt_stripe),
        (1, 7, 6, 1, shirt_blue),
        # Arms / lower shirt edges
        (0, 6, 1, 2, skin), (7, 6, 1, 2, skin),
        # Pants
        (2, 8, 4, 2, pants),
        (2, 10, 1, 1, pants), (5, 10, 1, 1, pants),
        # Shoes
        (1, 11, 2, 1, shoes), (5, 11, 2, 1, shoes),
    ]
    for rx, ry, rw, rh, col in px:
        pygame.draw.rect(screen, col, (x + rx * scale, y + ry * scale, rw * scale, rh * scale))


def draw_frisk_world(x, y):
    # Corridor/world visual target ~16x32 (Undertale-like overworld height).
    draw_frisk_sprite(x + 1, y - 30, scale=2, blink=False)


def draw_frisk_battle(x, y, blink=False):
    # Proportional mini version for battle dodge box.
    draw_frisk_sprite(x - 8, y - 12, scale=1, blink=blink)


def update_battle():
    global battle_phase, attack_meter_x, attack_meter_dir, dodge_timer
    global soul_iframes, player_hp, state, battle_msg, sans_defeated
    if battle_phase == "attack_meter":
        attack_meter_x += 7 * attack_meter_dir
        if attack_meter_x >= 240:
            attack_meter_x = 240
            attack_meter_dir = -1
        elif attack_meter_x <= 0:
            attack_meter_x = 0
            attack_meter_dir = 1

    elif battle_phase == "dodge":
        keys = pygame.key.get_pressed()
        mv = 4
        if keys[pygame.K_LEFT]:
            battle_soul.x -= mv
        if keys[pygame.K_RIGHT]:
            battle_soul.x += mv
        if keys[pygame.K_UP]:
            battle_soul.y -= mv
        if keys[pygame.K_DOWN]:
            battle_soul.y += mv
        battle_soul.x = max(dodge_box.left, min(dodge_box.right - battle_soul.width, battle_soul.x))
        battle_soul.y = max(dodge_box.top, min(dodge_box.bottom - battle_soul.height, battle_soul.y))

        if soul_iframes > 0:
            soul_iframes -= 1
        dodge_timer -= 1

        for b in bones:
            r = b["rect"]
            r.x += b["vx"]
            if b["vx"] > 0 and r.left > dodge_box.right + 20:
                r.right = dodge_box.left - 20
            elif b["vx"] < 0 and r.right < dodge_box.left - 20:
                r.left = dodge_box.right + 20
            if soul_iframes == 0 and battle_soul.colliderect(r):
                player_hp = max(0, player_hp - 2)
                soul_iframes = 18

        if player_hp <= 0:
            state = STATE_CORRIDOR
            player_hp = player_max_hp
            if checkpoint_pos is not None:
                player.x, player.y = checkpoint_pos
            set_status("* You were defeated... Returned to checkpoint.", 240)
            battle_phase = "menu"
            return

        if dodge_timer <= 0:
            battle_phase = "menu"
            battle_msg = "* Sans grins."

    if sans_hp <= 0:
        sans_defeated = True
        state = STATE_CORRIDOR
        set_status("* You defeated Sans.", 260)
        battle_phase = "menu"


def draw_battle():
    screen.fill(BLACK)
    pygame.draw.rect(screen, WHITE, (24, 24, W - 48, 78), 2)
    # Sans portrait-ish shape
    pygame.draw.circle(screen, WHITE, (96, 63), 18)
    pygame.draw.rect(screen, (30, 100, 210), (78, 82, 36, 16))
    pygame.draw.circle(screen, BLACK, (89, 62), 2)
    pygame.draw.circle(screen, BLACK, (103, 62), 2)
    pygame.draw.line(screen, BLACK, (88, 70), (105, 70), 2)

    sans_name = font.render("SANS", True, WHITE)
    screen.blit(sans_name, (144, 42))
    pygame.draw.rect(screen, GRAY, (220, 52, 240, 14))
    pygame.draw.rect(screen, GOLD_LIGHT, (220, 52, int(240 * max(0, sans_hp) / sans_max_hp), 14))

    hp_label = font.render(f"HP {player_hp}/{player_max_hp}", True, WHITE)
    screen.blit(hp_label, (24, H - 150))
    pygame.draw.rect(screen, GRAY, (132, H - 142, 180, 12))
    pygame.draw.rect(screen, RED, (132, H - 142, int(180 * player_hp / player_max_hp), 12))

    msg = font.render(battle_msg, True, WHITE)
    screen.blit(msg, (24, H - 112))

    if battle_phase == "menu":
        for i, item in enumerate(battle_menu):
            col = GOLD_LIGHT if i == battle_menu_idx else WHITE
            x = 24 + i * 150
            pygame.draw.rect(screen, col, (x, H - 72, 130, 36), 2)
            t = font.render(item, True, col)
            screen.blit(t, (x + 18, H - 64))

    elif battle_phase == "attack_meter":
        m = pygame.Rect(190, H - 80, 260, 24)
        pygame.draw.rect(screen, WHITE, m, 2)
        center = m.x + m.w // 2
        pygame.draw.rect(screen, RED, (center - 8, m.y + 2, 16, m.h - 4))
        cx = m.x + attack_meter_x
        pygame.draw.line(screen, WINDOW_GLOW, (cx, m.y), (cx, m.bottom), 3)
        tip = font.render("PRESS Z/ENTER TO HIT", True, WHITE)
        screen.blit(tip, (192, H - 112))

    elif battle_phase == "dodge":
        pygame.draw.rect(screen, WHITE, dodge_box, 3)
        for b in bones:
            pygame.draw.rect(screen, WHITE, b["rect"])
        blink = soul_iframes > 0 and soul_iframes % 4 >= 2
        draw_frisk_battle(battle_soul.centerx, battle_soul.centery, blink=blink)
        timer_text = font.render(f"DODGE {max(0, dodge_timer // 60 + 1)}", True, WHITE)
        screen.blit(timer_text, (24, H - 72))


def draw_delta_rune(cx, cy, scale, col):
    # Stylized procedural emblem for corridor windows.
    top = (cx, cy - 12 * scale)
    left = (cx - 12 * scale, cy + 9 * scale)
    right = (cx + 12 * scale, cy + 9 * scale)
    pygame.draw.polygon(screen, col, [top, left, right], 2)
    pygame.draw.circle(screen, col, (cx, cy + 3 * scale), 4 * scale, 1)


def draw_last_corridor_background(room):
    world_w = room["world_w"]

    # Main gold-tinted hall body.
    screen.fill(room["bg"])
    pygame.draw.rect(screen, GOLD_DARK, (0, 42, W, H - 42))
    pygame.draw.rect(screen, GOLD_MID, (0, H - 128, W, 60))
    pygame.draw.rect(screen, GOLD_LIGHT, (0, H - 68, W, 18))
    pygame.draw.rect(screen, GOLD_DARK, (0, H - 50, W, 50))

    # Corridor boundary arches (left and right room transitions).
    for arch_x in (room["left_arch_x"], room["right_arch_x"]):
        sx = arch_x - camera_x
        outer = pygame.Rect(sx, 58, 52, H - 118)
        inner = pygame.Rect(sx + 10, 72, 32, H - 146)
        pygame.draw.rect(screen, GOLD_LIGHT, outer)
        pygame.draw.rect(screen, room["bg"], inner)
        pygame.draw.rect(screen, PILLAR_SHADE, outer, 2)

    # Repeating pillars and windows to mimic Last Corridor rhythm.
    win_y = room["window_y"]
    win_w = room["window_w"]
    win_h = room["window_h"]
    for px in room["pillar_x"]:
        sx = px - camera_x
        if sx < -70 or sx > W + 70:
            continue

        # Rear pillar.
        rear = pygame.Rect(sx - 12, 58, 24, H - 160)
        pygame.draw.rect(screen, GOLD_MID, rear)
        pygame.draw.rect(screen, PILLAR_SHADE, rear, 2)
        pygame.draw.line(screen, GOLD_LIGHT, (rear.x + 3, rear.y), (rear.x + 3, rear.bottom), 1)

        # Window panel and glow.
        wx = sx + 24
        if wx < W and wx + win_w > 0:
            frame = pygame.Rect(wx, win_y, win_w, win_h)
            glass = pygame.Rect(wx + 8, win_y + 8, win_w - 16, win_h - 16)
            pygame.draw.rect(screen, GOLD_LIGHT, frame)
            pygame.draw.rect(screen, WINDOW_GLOW, glass)
            pygame.draw.rect(screen, GOLD_DARK, frame, 2)
            draw_delta_rune(glass.centerx, glass.centery + 2, 2, GOLD_DARK)

    # Foreground floor trim and checker-like lane strips.
    lane_top = H - 120
    lane_h = 58
    pygame.draw.rect(screen, GOLD_LIGHT, (0, lane_top, W, 4))
    for i in range(0, W, 36):
        c = GOLD_MID if (i // 36) % 2 == 0 else GOLD_DARK
        pygame.draw.rect(screen, c, (i, lane_top + 10, 36, lane_h))

    # Save point marker (left side).
    spx, spy = room["save_point"]
    star_x = spx - camera_x
    t = pygame.time.get_ticks() // 130
    pulse = (t % 2) * 2
    star_points = [
        (star_x, spy - 12 - pulse),
        (star_x + 4, spy - 2),
        (star_x + 14 + pulse, spy),
        (star_x + 4, spy + 2),
        (star_x, spy + 12 + pulse),
        (star_x - 4, spy + 2),
        (star_x - 14 - pulse, spy),
        (star_x - 4, spy - 2),
    ]
    pygame.draw.polygon(screen, (255, 232, 80), star_points)

    # Throne room side door cue (far right).
    door = room["throne_door"].copy()
    door.x -= camera_x
    pygame.draw.rect(screen, GOLD_LIGHT, door)
    pygame.draw.rect(screen, PILLAR_SHADE, door, 3)
    pygame.draw.rect(screen, room["bg"], (door.x + 12, door.y + 12, door.w - 24, door.h - 24))
    pygame.draw.circle(screen, GOLD_LIGHT, (door.right - 16, door.centery), 3)


# ======================
# TITLE
# ======================
def draw_title():
    screen.fill(BLACK)

    t1 = font_big.render("AC'S CHATGPT", True, WHITE)
    t2 = font_big.render("UNDERTALE ENGINE 0.1", True, WHITE)

    screen.blit(t1, (80, 140))
    screen.blit(t2, (40, 200))

    prompt = font.render("PRESS Z OR ENTER", True, RED)
    screen.blit(prompt, (200, 320))


# ======================
# MENU
# ======================
def draw_menu():
    screen.fill(BLACK)

    title = font.render("MAIN MENU", True, WHITE)
    screen.blit(title, (260, 120))

    for i, item in enumerate(menu):
        prefix = "> " if i == sel else "  "
        color = RED if i == sel else WHITE
        text = font.render(prefix + item, True, color)
        screen.blit(text, (260, 200 + i * 40))

    controls_title = font.render("HOW TO PLAY / CONTROLS", True, WHITE)
    screen.blit(controls_title, (134, 300))
    controls = [
        "UP/DOWN = MENU",
        "Z/ENTER = SELECT / TALK",
        "ARROWS = MOVE",
        "E = INVENTORY",
        "X = BACK TO MENU",
    ]
    for i, line in enumerate(controls):
        t = font.render(line, True, GRAY if i < 4 else WHITE)
        screen.blit(t, (170, 328 + i * 24))


# ======================
# CORRIDOR ENGINE
# ======================
def draw_corridor():
    global camera_x, sans_prompt_visible, save_prompt_visible
    room = current_room

    keys = pygame.key.get_pressed()

    # Movement in world coordinates.
    if not dialog_active and not inventory_open:
        if keys[pygame.K_LEFT]:
            player.x -= speed
        if keys[pygame.K_RIGHT]:
            player.x += speed
        if keys[pygame.K_UP]:
            player.y -= speed
        if keys[pygame.K_DOWN]:
            player.y += speed

    # Clamp to walkable lane bounds.
    walk = room["walk_bounds"]
    player.x = max(walk.left, min(walk.right - player.width, player.x))
    player.y = max(walk.top, min(walk.bottom - player.height, player.y))

    # Camera follows player across long corridor.
    world_w = room["world_w"]
    camera_x = player.centerx - W // 2
    camera_x = max(0, min(world_w - W, camera_x))

    draw_last_corridor_background(room)
    draw_sans(room)

    save_prompt_visible = (not inventory_open) and save_nearby(room)
    sans_prompt_visible = (not inventory_open) and (not save_prompt_visible) and sans_nearby(room)
    if save_prompt_visible:
        spx, spy = room["save_point"]
        prompt = font.render("PRESS Z TO SAVE", True, WINDOW_GLOW)
        screen.blit(prompt, (spx - camera_x - 52, spy - 26))
    if sans_prompt_visible:
        prompt = font.render("PRESS Z", True, WHITE)
        sx, sy = room["sans_pos"]
        screen.blit(prompt, (sx - camera_x - 24, sy - 22))

    # Player draw (sprite files OFF -> procedural Frisk).
    px = player.x - camera_x
    py = player.y
    draw_frisk_world(px, py)

    # room label
    label = font.render(room["name"], True, WHITE)
    screen.blit(label, (20, 10))
    hint = font.render("X = BACK TO MENU", True, (220, 220, 220))
    screen.blit(hint, (W - 196, 10))
    draw_status_line()
    draw_dialog_box()
    draw_inventory_overlay()


# ======================
# LOOP
# ======================
running = True

while running:
    clock.tick(60)
    if status_msg_timer > 0:
        status_msg_timer -= 1

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

        if event.type == pygame.KEYDOWN:

            # TITLE
            if state == STATE_TITLE:
                if event.key in [pygame.K_z, pygame.K_RETURN]:
                    state = STATE_MENU
                    play_snd(snd_menu_open)

            # MENU
            elif state == STATE_MENU:
                if event.key == pygame.K_UP:
                    new_sel = (sel - 1) % len(menu)
                    if new_sel != sel:
                        sel = new_sel
                        play_snd(snd_menu_move)

                if event.key == pygame.K_DOWN:
                    new_sel = (sel + 1) % len(menu)
                    if new_sel != sel:
                        sel = new_sel
                        play_snd(snd_menu_move)

                if event.key in [pygame.K_z, pygame.K_RETURN]:

                    if menu[sel] == "START":
                        load_room(last_room)
                        state = STATE_CORRIDOR

                    elif menu[sel] == "EXIT":
                        pygame.quit()
                        sys.exit()

            # CORRIDOR EXIT
            elif state == STATE_CORRIDOR:
                if event.key == pygame.K_e:
                    inventory_open = not inventory_open

                elif inventory_open and event.key in [pygame.K_ESCAPE, pygame.K_x]:
                    inventory_open = False

                elif event.key in [pygame.K_z, pygame.K_RETURN] and not inventory_open:
                    if dialog_active:
                        advance_dialog()
                    elif save_nearby(current_room):
                        trigger_save_checkpoint(current_room)
                    elif sans_nearby(current_room):
                        if sans_defeated:
                            set_status("* There's only silence now.", 180)
                        else:
                            start_sans_dialog(start_battle=True)

                elif event.key == pygame.K_x and (not dialog_active) and (not inventory_open):
                    state = STATE_MENU
                    room_loaded = False
                    play_snd(snd_menu_open)

            elif state == STATE_BATTLE:
                if event.key in [pygame.K_LEFT, pygame.K_a] and battle_phase == "menu":
                    battle_menu_idx = (battle_menu_idx - 1) % len(battle_menu)
                elif event.key in [pygame.K_RIGHT, pygame.K_d] and battle_phase == "menu":
                    battle_menu_idx = (battle_menu_idx + 1) % len(battle_menu)
                elif event.key in [pygame.K_z, pygame.K_RETURN]:
                    if battle_phase == "menu":
                        pick = battle_menu[battle_menu_idx]
                        if pick == "FIGHT":
                            battle_phase = "attack_meter"
                            attack_meter_x = 0
                            attack_meter_dir = 1
                            battle_msg = "* Time your strike."
                        elif pick == "ACT":
                            battle_msg = "* You ask Sans to stop smiling."
                            start_enemy_turn()
                        elif pick == "ITEM":
                            if inventory_items:
                                inventory_items.pop(0)
                                player_hp = min(player_max_hp, player_hp + 7)
                                battle_msg = "* You recovered 7 HP."
                            else:
                                battle_msg = "* No items left."
                            start_enemy_turn()
                        elif pick == "MERCY":
                            battle_msg = "* You show MERCY. Sans does not."
                            start_enemy_turn()
                    elif battle_phase == "attack_meter":
                        center_dist = abs(attack_meter_x - 130)
                        dmg = max(4, 28 - center_dist // 6)
                        sans_hp = max(0, sans_hp - dmg)
                        battle_msg = f"* Hit! {dmg} damage."
                        if sans_hp > 0:
                            start_enemy_turn()
                elif event.key in [pygame.K_x, pygame.K_ESCAPE]:
                    battle_msg = "* You cannot escape."

    # RENDER
    if state == STATE_TITLE:
        draw_title()

    elif state == STATE_MENU:
        draw_menu()

    elif state == STATE_CORRIDOR:
        update_dialog_typewriter()
        draw_corridor()
    elif state == STATE_BATTLE:
        update_battle()
        draw_battle()

    pygame.display.flip()

pygame.quit()
sys.exit()
