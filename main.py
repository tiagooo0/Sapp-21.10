# CO Quiz Adventure - Click-Rapid Minigames + Quiz
# Archivo: co_quiz_adventure.py
# Juego educativo en Pygame: responder preguntas y completar minijuegos de clic rápido
# Objetivo: limpiar la ciudad de CO ganando progreso en cada zona

import pygame
import random
import sys
import os
import math
from pathlib import Path
import wave
import struct

# ---------------- CONFIG ----------------
ANCHO, ALTO = 1000, 700
FPS = 60
RECURSOS = Path('recursos')
RECURSOS.mkdir(exist_ok=True)

# Sonidos - si no existen, se generan simples WAV
S_CORRECT = RECURSOS / 'correct.wav'
S_WRONG = RECURSOS / 'wrong.wav'
S_CLICK = RECURSOS / 'click.wav'
S_BG = RECURSOS / 'bg_loop.wav'

def generar_tono(path, freq=440.0, dur=0.12, volume=0.4, sample_rate=22050):
    n = int(sample_rate * dur)
    with wave.open(str(path), 'w') as w:
        w.setparams((1, 2, sample_rate, n, 'NONE', 'not compressed'))
        max_amp = int(32767 * volume)
        for i in range(n):
            t = i / sample_rate
            val = int(max_amp * math.sin(2 * math.pi * freq * t))
            w.writeframes(struct.pack('<h', val))

# crear si faltan
if not S_CORRECT.exists(): generar_tono(S_CORRECT, freq=880, dur=0.08, volume=0.5)
if not S_WRONG.exists(): generar_tono(S_WRONG, freq=220, dur=0.14, volume=0.6)
if not S_CLICK.exists(): generar_tono(S_CLICK, freq=520, dur=0.06, volume=0.4)
if not S_BG.exists(): generar_tono(S_BG, freq=200, dur=2.0, volume=0.15)

# ---------------- PYGAME INIT ----------------
pygame.init()
pygame.mixer.init()
screen = pygame.display.set_mode((ANCHO, ALTO))
pygame.display.set_caption('CO Quiz Adventure')
clock = pygame.time.Clock()

# cargar sonidos
snd_correct = pygame.mixer.Sound(str(S_CORRECT))
snd_wrong = pygame.mixer.Sound(str(S_WRONG))
snd_click = pygame.mixer.Sound(str(S_CLICK))
snd_bg = pygame.mixer.Sound(str(S_BG))
try:
    snd_bg.play(loops=-1)
except Exception:
    pass

# colores y fuentes
WHITE = (255,255,255)
BLACK = (10,12,15)
DARK = (28,36,44)
ACCENT = (40,160,200)
GOOD = (80,200,120)
BAD = (220,60,60)
FONT_L = pygame.font.SysFont('arial', 34)
FONT_M = pygame.font.SysFont('arial', 22)
FONT_S = pygame.font.SysFont('arial', 16)

# ---------------- DATOS EDUCATIVOS ----------------
# preguntas: (pregunta, [op1, op2, op3], index_correct)
QUESTIONS = [
    ("¿El monóxido de carbono tiene olor?", ["Sí", "No", "A veces"], 1),
    ("¿Qué debes hacer si sospechás exposición a CO?", ["Beber agua", "Ir a la azotea", "Salir al aire libre y buscar ayuda"], 2),
    ("¿Dónde conviene instalar detectores de CO?", ["Cerca de dormitorios", "En el baño", "En el altillo"], 0),
    ("¿Usar un brasero en interior es seguro?", ["Sí, si hay ventana", "No, peligroso", "Sólo con máscara"], 1),
    ("¿El CO puede causar mareos y náuseas?", ["No", "Sí", "Sólo en ancianos"], 1),
]
random.shuffle(QUESTIONS)

# ---------------- ESTADO DEL JUEGO ----------------
zones = [
    { 'name': 'Barrio - Casa', 'description': 'Ventila habitaciones y apaga estufas', 'goal': 100 },
    { 'name': 'Garage', 'description': 'Saca autos, apaga motores', 'goal': 120 },
    { 'name': 'Escuela', 'description': 'Enseña a estudiantes', 'goal': 140 },
]
zone_index = 0
progress = 0  # progreso de limpieza
lives = 3
score = 0

# estados: menu, quiz, minigame, transition, final
state = 'menu'
question_index = 0
selected_option = None
quiz_feedback_timer = 0

# ---------------- MINIJUEGO (CLICK-RAPIDO) ----------------
# Objetos peligrosos que hay que clickear para desactivar: estufa, auto, brasero
class Hazard(pygame.sprite.Sprite):
    def __init__(self, kind, x, y, speed):
        super().__init__()
        self.kind = kind
        self.speed = speed
        self.size = 48
        self.image = pygame.Surface((self.size, self.size), pygame.SRCALPHA)
        self.rect = self.image.get_rect(center=(x,y))
        self._render()
        self.timer = 0

    def _render(self):
        self.image.fill((0,0,0,0))
        if self.kind == 'stove':
            pygame.draw.rect(self.image, (160,80,40), (8, 12, 32, 20), border_radius=6)
            pygame.draw.circle(self.image, (255,140,0), (24, 10), 6)
        elif self.kind == 'car':
            pygame.draw.rect(self.image, (80,80,200), (6,18,36,18), border_radius=6)
            pygame.draw.circle(self.image, (20,20,20), (16,38), 6)
            pygame.draw.circle(self.image, (20,20,20), (32,38), 6)
        elif self.kind == 'charcoal':
            pygame.draw.circle(self.image, (60,40,40), (24,24), 18)
            pygame.draw.circle(self.image, (255,80,20), (24,18), 6)

    def update(self):
        self.rect.y += int(self.speed)
        self.timer += 1

hazards = pygame.sprite.Group()
minigame_timer = 0
minigame_duration = 9.0  # segundos
minigame_active = False

# ---------------- UTIL ----------------
def draw_text_center(surf, text, y, font=FONT_M, color=WHITE):
    r = font.render(text, True, color)
    surf.blit(r, (ANCHO//2 - r.get_width()//2, y))

# ---------------- FUNCIONES DE NIVELES ----------------
def start_quiz():
    global state, selected_option, quiz_feedback_timer
    state = 'quiz'
    selected_option = None
    quiz_feedback_timer = 0

def start_minigame():
    global state, hazards, minigame_timer, minigame_active
    state = 'minigame'
    hazards.empty()
    minigame_timer = pygame.time.get_ticks()/1000.0
    minigame_active = True
    # generar algunos peligros iniciales
    for i in range(3 + zone_index):
        spawn_hazard()

def spawn_hazard():
    kind = random.choice(['stove','car','charcoal'])
    x = random.randint(80, ANCHO-80)
    y = random.randint(-120, -40)
    speed = random.uniform(1.2 + zone_index*0.4, 2.2 + zone_index*0.6)
    h = Hazard(kind, x, y, speed)
    hazards.add(h)

# ---------------- LOOP PRINCIPAL ----------------
running = True
while running:
    dt = clock.tick(FPS)/1000.0
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        if event.type == pygame.KEYDOWN:
            if state == 'menu' and event.key == pygame.K_RETURN:
                state = 'quiz'; question_index = 0
            elif state == 'quiz':
                if event.key in (pygame.K_1, pygame.K_KP1): selected_option = 0
                if event.key in (pygame.K_2, pygame.K_KP2): selected_option = 1
                if event.key in (pygame.K_3, pygame.K_KP3): selected_option = 2
                if event.key == pygame.K_RETURN and selected_option is not None:
                    # evaluar respuesta
                    q, opts, corr = QUESTIONS[question_index]
                    if selected_option == corr:
                        snd_correct.play()
                        score += 10
                        progress += 18 + zone_index*2
                        quiz_feedback_timer = pygame.time.get_ticks()/1000.0
                        question_index += 1
                        # si contestó todas -> minijuego
                        if question_index >= 2 + zone_index:
                            start_minigame()
                    else:
                        snd_wrong.play()
                        score = max(0, score-5)
                        lives -= 1
                        quiz_feedback_timer = pygame.time.get_ticks()/1000.0
                        question_index += 1
                        if lives <= 0:
                            state = 'final'
            elif state == 'minigame':
                # clicks manejados en MOUSEBUTTONDOWN
                pass
            elif state == 'final' and event.key == pygame.K_RETURN:
                # reiniciar todo
                zone_index = 0; progress = 0; lives = 3; score = 0; state = 'menu'

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx,my = event.pos
            if state == 'minigame':
                for h in list(hazards):
                    if h.rect.collidepoint((mx,my)):
                        # click correcto: desactivar
                        snd_click.play()
                        hazards.remove(h)
                        score += 5
                        progress += 10 + zone_index*2
                        # pequeño spawn adicional
                        if random.random() < 0.35:
                            spawn_hazard()
                        break
            elif state == 'menu':
                # click para comenzar
                if  ANCHO//2-150 < mx < ANCHO//2+150 and ALTO//2+80 < my < ALTO//2+120:
                    state = 'quiz'; question_index = 0

    # ACTUALIZACIONES por estado
    if state == 'minigame' and minigame_active:
        # spawn continuo
        nowt = pygame.time.get_ticks()/1000.0
        if nowt - minigame_timer > 0.9:
            minigame_timer = nowt
            if len(hazards) < 7 + zone_index*2:
                spawn_hazard()
        hazards.update()
        # si llegan al suelo -> penalizan
        for h in list(hazards):
            if h.rect.top > ALTO-120:
                hazards.remove(h)
                lives -= 1
                snd_wrong.play()
                progress = max(0, progress - 12)
                if lives <= 0:
                    state = 'final'
        # fin del minijuego
        if pygame.time.get_ticks()/1000.0 - minigame_timer_start if 'minigame_timer_start' in globals() else 0 > minigame_duration:
            # this path not used; use time by counting based on spawn start
            pass
        # alternate: minigame ends when enough progress
        if progress >= zones[zone_index]['goal']:
            # zona limpia
            snd_correct.play()
            zone_index += 1
            if zone_index >= len(zones):
                state = 'final'
            else:
                state = 'transition'
                trans_start = pygame.time.get_ticks()/1000.0
                # small reset for next zone
                hazards.empty()
    # manejo quiz timer/feedback
    if state == 'quiz':
        # si se acabaron las preguntas del pool -> minijuego
        if question_index >= len(QUESTIONS):
            start_minigame()
        # limitar índice para la ronda
        question_index = min(question_index, len(QUESTIONS)-1)

    # DIBUJADO
    screen.fill((20,26,34))
    # header
    pygame.draw.rect(screen, (12,18,22), (0,0,ANCHO,84))
    header = FONT_L.render('CO Quiz Adventure', True, ACCENT)
    screen.blit(header, (20,18))
    # estado de ciudad
    zone_txt = zones[zone_index]['name'] if zone_index < len(zones) else 'Ciudad limpia'
    screen.blit(FONT_M.render(f'Zona: {zone_txt}', True, WHITE), (20,56))
    # barra progreso
    pygame.draw.rect(screen, (60,60,60), (20,100, ANCHO-40, 26), border_radius=8)
    prog_w = int(((progress)/ (zones[zone_index]['goal'] if zone_index < len(zones) else 100)) * (ANCHO-44))
    pygame.draw.rect(screen, (80,200,150), (22,102, max(0,prog_w), 22), border_radius=6)
    screen.blit(FONT_S.render(f'Progreso: {int(progress)}/{zones[zone_index]["goal"] if zone_index < len(zones) else 100}', True, WHITE), (24,104))

    # vidas y puntaje
    screen.blit(FONT_S.render(f'Vidas: {lives}   Puntaje: {score}', True, WHITE), (ANCHO-260,56))

    if state == 'menu':
        draw_text_center(screen, 'Bienvenido a CO Quiz Adventure', 180, FONT_L, WHITE)
        draw_text_center(screen, 'Responde preguntas y completa minijuegos para limpiar la ciudad', 240, FONT_M)
        # boton iniciar
        pygame.draw.rect(screen, ACCENT, (ANCHO//2-150, ALTO//2+80, 300, 40), border_radius=8)
        draw_text_center(screen, 'Presiona ENTER o clic para comenzar', ALTO//2+88, FONT_M, BLACK)

    elif state == 'quiz':
        q, opts, corr = QUESTIONS[question_index]
        draw_text_center(screen, f'Pregunta {question_index+1}: {q}', 150, FONT_M)
        # opciones
        base_y = 220
        for i, opt in enumerate(opts):
            box = pygame.Rect(ANCHO//2-320, base_y + i*70, 640, 56)
            pygame.draw.rect(screen, (40,44,50), box, border_radius=8)
            if selected_option == i:
                pygame.draw.rect(screen, (80,120,160), box, 3, border_radius=8)
            txt = FONT_M.render(f'{i+1}. {opt}', True, WHITE)
            screen.blit(txt, (box.x+18, box.y+12))
        draw_text_center(screen, 'Elige 1-2-3 y presiona ENTER', ALTO-80, FONT_S, (200,200,200))
        # feedback breve
        if quiz_feedback_timer:
            if pygame.time.get_ticks()/1000.0 - quiz_feedback_timer < 1.2:
                # mostrar correcto/incorrecto del último
                pass
            else:
                quiz_feedback_timer = 0

    elif state == 'minigame':
        # instrucciones
        draw_text_center(screen, 'MINIJUEGO: Haz click rápido en objetos peligrosos para desactivarlos', 130, FONT_M)
        draw_text_center(screen, f'Tiempo restante: {int(max(0, minigame_duration - (pygame.time.get_ticks()/1000.0 - minigame_timer)))}s', 170, FONT_S)
        hazards.draw(screen)
        # actualizar y dibujar cada hazard con label
        y_draw = 220
        for h in hazards:
            screen.blit(h.image, h.rect)
        # prueba de termino: si no hay hazards y ya avanzó bastante
        if len(hazards) == 0:
            # pequeña recompensa
            progress += 8
            start_quiz()

    elif state == 'transition':
        draw_text_center(screen, f'¡Zona {zones[zone_index-1]["name"]} limpia!', 220, FONT_L, GOOD)
        draw_text_center(screen, 'Preparando siguiente zona...', 280, FONT_M)
        if pygame.time.get_ticks()/1000.0 - trans_start > 2.0:
            state = 'quiz'; question_index = 0

    elif state == 'final':
        draw_text_center(screen, 'RESULTADO FINAL', 170, FONT_L)
        draw_text_center(screen, f'Puntaje: {score}  |  Progreso total: {progress}', 230, FONT_M)
        if lives <= 0:
            draw_text_center(screen, 'Perdiste: quedaste sin vidas. Presiona ENTER para reiniciar.', 320, FONT_M, BAD)
        else:
            draw_text_center(screen, '¡Felicidades! La ciudad está más segura. Presiona ENTER para volver al menú.', 320, FONT_M, GOOD)

    pygame.display.flip()

pygame.quit()
sys.exit()
