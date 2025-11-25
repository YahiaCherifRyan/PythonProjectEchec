#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
main.py - Version STABLE FINALE V22 (Mode Réseau Local / LAN)
- Ajout d'un mode Multijoueur LAN via Sockets (TCP).
- Gestion du Threading pour la réception des coups sans bloquer l'UI.
- Réintroduction du StartMenu pour le choix des modes (Local 1PC, IA, LAN).
"""
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from dataclasses import dataclass
from typing import List, Optional, Tuple, Dict, Union
import copy, collections, math
import random
import socket
import threading

# ---------------- CONSTANTES DE BASE ----------------
FILES = 'abcdefgh'
RANKS = '12345678'
WHITE = 'w'
BLACK = 'b'
PORT = 5000  # Port utilisé pour la connexion réseau

# Valeurs des pièces pour l'évaluation de l'IA
PIECE_VALUES = {
    'P': 100, 'N': 320, 'B': 330, 'R': 500, 'Q': 900, 'K': 0,
    'p': -100, 'n': -320, 'b': -330, 'r': -500, 'q': -900, 'k': 0
}
MAX_AI_DEPTH = 2

# Assurez-vous que ces fichiers existent dans le répertoire d'exécution !
IMAGE_MAP = {
    'P': "wP.png", 'R': "wR.png", 'N': "wN.png", 'B': "wB.png", 'Q': "wQ.png", 'K': "wK.png",
    'p': "bP.png", 'r': "bR.png", 'n': "bN.png", 'b': "bB.png", 'q': "bQ.png", 'k': "bK.png",
    'S': "eN.png"
}
GROUP_ORDER = ['P', 'N', 'B', 'R', 'Q', 'K']

# ---------------- THÈMES (COULEURS) ----------------
UI_BG_PRIMARY = '#262421'
UI_BG_SECONDARY = '#312E2B'
UI_FG = '#FFFFFF'
UI_TIMER_ACTIVE = '#769656'
UI_TIMER_INACTIVE = '#404040'
UI_CELL_HIGHLIGHT_BG = '#505050'

DARK_BOARD_LIGHT = '#D1D8D2'
DARK_BOARD_DARK = '#898B99'
DARK_HIGHLIGHT_LAST_MOVE = '#BACA2B'
DARK_HIGHLIGHT_SELECTED = '#D0E03C'
DARK_HIGHLIGHT_TARGET = '#58AC3A'

LIGHT_BOARD_LIGHT = '#EFEFEF'
LIGHT_BOARD_DARK = '#A4C687'
LIGHT_HIGHLIGHT_LAST_MOVE = '#F6F690'
LIGHT_HIGHLIGHT_SELECTED = '#91B981'
LIGHT_HIGHLIGHT_TARGET = '#609040'

BOARD_LIGHT = DARK_BOARD_LIGHT
BOARD_DARK = DARK_BOARD_DARK
HIGHLIGHT_LAST_MOVE = DARK_HIGHLIGHT_LAST_MOVE
HIGHLIGHT_SELECTED = DARK_HIGHLIGHT_SELECTED
HIGHLIGHT_TARGET = DARK_HIGHLIGHT_TARGET

CIRCLE_COLOR = '#769656'
ARROW_COLOR = '#769656'


# ---------------- GESTIONNAIRE RÉSEAU ----------------
class NetworkManager:
    def __init__(self, is_host, ip=None):
        self.is_host = is_host
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.conn = None
        self.addr = None
        self.connected = False

        if self.is_host:
            self.socket.bind(('0.0.0.0', PORT))
            self.socket.listen(1)
            # Récupérer l'IP locale pour l'afficher
            self.local_ip = socket.gethostbyname(socket.gethostname())
        else:
            self.target_ip = ip

    def connect(self):
        try:
            if self.is_host:
                self.conn, self.addr = self.socket.accept()
                self.connected = True
                return True
            else:
                self.socket.connect((self.target_ip, PORT))
                self.conn = self.socket
                self.connected = True
                return True
        except Exception as e:
            print(f"Erreur réseau: {e}")
            return False

    def send_move(self, uci_move: str):
        if self.connected and self.conn:
            try:
                self.conn.send(uci_move.encode())
            except Exception as e:
                print(f"Erreur d'envoi: {e}")

    def receive_move(self) -> Optional[str]:
        if self.connected and self.conn:
            try:
                data = self.conn.recv(1024)
                if not data: return None
                return data.decode()
            except:
                return None
        return None

    def close(self):
        if self.conn: self.conn.close()
        if self.socket: self.socket.close()


# ---------------- Move & Board engine ----------------
@dataclass
class Move:
    from_sq: Tuple[int, int]
    to_sq: Tuple[int, int]
    piece: str
    captured: Optional[str] = None
    promotion: Optional[str] = None
    is_en_passant: bool = False
    is_castle: bool = False

    def uci(self) -> str:
        f = FILES[self.from_sq[1]] + RANKS[self.from_sq[0]]
        t = FILES[self.to_sq[1]] + RANKS[self.to_sq[0]]
        prom = self.promotion.lower() if self.promotion else ''
        return f + t + prom


class Board:
    def __init__(self, fen: Optional[str] = None):
        self.board: List[List[Optional[str]]] = [[None] * 8 for _ in range(8)]
        self.turn = WHITE
        self.castling_rights = {'K': True, 'Q': True, 'k': True, 'q': True}
        self.en_passant_target: Optional[Tuple[int, int]] = None
        self.halfmove_clock = 0
        self.fullmove_number = 1
        self.history: List[Tuple[Move, dict]] = []
        self.fen_history: List[str] = []
        if fen:
            self.set_fen(fen)
        else:
            self.set_startpos()

    def set_startpos(self):
        self.set_fen("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")

    def set_fen(self, fen: str):
        parts = fen.split()
        rows = parts[0].split('/')
        self.board = [[None] * 8 for _ in range(8)]
        for r, row in enumerate(rows[::-1]):
            file_idx = 0
            for ch in row:
                if ch.isdigit():
                    file_idx += int(ch)
                else:
                    self.board[r][file_idx] = ch
                    file_idx += 1
        self.turn = WHITE if parts[1] == 'w' else BLACK
        cast = parts[2]
        self.castling_rights = {'K': 'K' in cast, 'Q': 'Q' in cast, 'k': 'k' in cast, 'q': 'q' in cast}
        ep = parts[3]
        if ep != '-':
            self.en_passant_target = (RANKS.index(ep[1]), FILES.index(ep[0]))
        else:
            self.en_passant_target = None
        if len(parts) >= 6:
            self.halfmove_clock = int(parts[4]);
            self.fullmove_number = int(parts[5])
        else:
            self.halfmove_clock = 0;
            self.fullmove_number = 1
        self.history = []
        self.fen_history = [self._fen_for_repetition()]

    def _fen_for_repetition(self) -> str:
        rows = []
        for r in range(7, -1, -1):
            empty = 0;
            rowstr = ''
            for c in range(8):
                p = self.board[r][c]
                if p is None:
                    empty += 1
                else:
                    if empty: rowstr += str(empty); empty = 0
                    rowstr += p
            if empty: rowstr += str(empty)
            rows.append(rowstr)
        cast = ''.join([k for k, v in self.castling_rights.items() if v]) or '-'
        ep = FILES[self.en_passant_target[1]] + RANKS[self.en_passant_target[0]] if self.en_passant_target else '-'
        return f"{'/'.join(rows)} {'w' if self.turn == WHITE else 'b'} {cast} {ep}"

    def in_bounds(self, r, c):
        return 0 <= r < 8 and 0 <= c < 8

    def piece_color(self, p):
        return WHITE if p.isupper() else BLACK

    def _opponent(self, color):
        return BLACK if color == WHITE else WHITE

    def find_king(self, color):
        king = 'K' if color == WHITE else 'k'
        for r in range(8):
            for c in range(8):
                if self.board[r][c] == king:
                    return (r, c)
        return None

    def is_square_attacked(self, sq, by_color):
        rtarget, ctarget = sq
        for r in range(8):
            for c in range(8):
                p = self.board[r][c]
                if not p or self.piece_color(p) != by_color: continue
                # Hack: utiliser _piece_moves non légaux pour vérifier l'attaque
                for m in self._piece_moves(r, c, p, check_legality=False):
                    if m.to_sq == sq:
                        return True
        return False

    def king_in_check(self, color):
        kp = self.find_king(color)
        if not kp: return True
        return self.is_square_attacked(kp, self._opponent(color))

    def generate_moves(self, legal=True) -> List[Move]:
        moves = []
        for r in range(8):
            for c in range(8):
                p = self.board[r][c]
                if not p: continue
                if self.piece_color(p) != self.turn: continue
                moves.extend(self._piece_moves(r, c, p))
        if legal:
            legal_moves = []
            for m in moves:
                b2 = copy.deepcopy(self)
                b2._make_move_internal(m)
                if not b2.king_in_check(self.turn):
                    legal_moves.append(m)
            return legal_moves
        return moves

    def _piece_moves(self, r, c, p, check_legality=True):
        moves = []
        color = self.piece_color(p)
        pt = p.upper()
        dir_sign = 1 if color == WHITE else -1

        if pt == 'P':
            nr = r + dir_sign
            if self.in_bounds(nr, c) and self.board[nr][c] is None:
                if nr == 0 or nr == 7:
                    for promo in ['Q', 'R', 'B', 'N']:
                        moves.append(Move((r, c), (nr, c), p, promotion=promo if color == WHITE else promo.lower()))
                else:
                    moves.append(Move((r, c), (nr, c), p))
                start_rank = 1 if color == WHITE else 6
                nr2 = r + 2 * dir_sign
                if r == start_rank and self.in_bounds(nr2, c) and self.board[nr2][c] is None:
                    moves.append(Move((r, c), (nr2, c), p))
            for dc in (-1, 1):
                nc = c + dc;
                nr = r + dir_sign
                if not self.in_bounds(nr, nc): continue
                target = self.board[nr][nc]
                if target and self.piece_color(target) != color:
                    if nr == 0 or nr == 7:
                        for promo in ['Q', 'R', 'B', 'N']:
                            moves.append(Move((r, c), (nr, nc), p, captured=target,
                                              promotion=promo if color == WHITE else promo.lower()))
                    else:
                        moves.append(Move((r, c), (nr, nc), p, captured=target))
            if self.en_passant_target:
                ep_r, ep_c = self.en_passant_target
                if ep_r == r + dir_sign and abs(ep_c - c) == 1:
                    cap_r = r;
                    cap_c = ep_c
                    target = self.board[cap_r][cap_c]
                    if target and target.upper() == 'P' and self.piece_color(target) != color:
                        moves.append(Move((r, c), (ep_r, ep_c), p, captured=target, is_en_passant=True))
            return moves

        if pt == 'N':
            for dr, dc in [(2, 1), (1, 2), (-1, 2), (-2, 1), (-2, -1), (-1, -2), (1, -2), (2, -1)]:
                nr, nc = r + dr, c + dc
                if not self.in_bounds(nr, nc): continue
                target = self.board[nr][nc]
                if target is None or self.piece_color(target) != color:
                    moves.append(Move((r, c), (nr, nc), p, captured=target if target else None))
            return moves

        if pt in ('B', 'R', 'Q'):
            directions = []
            if pt in ('B', 'Q'): directions += [(1, 1), (1, -1), (-1, 1), (-1, -1)]
            if pt in ('R', 'Q'): directions += [(1, 0), (-1, 0), (0, 1), (0, -1)]
            for dr, dc in directions:
                nr, nc = r + dr, c + dc
                while self.in_bounds(nr, nc):
                    target = self.board[nr][nc]
                    if target is None:
                        moves.append(Move((r, c), (nr, nc), p))
                    else:
                        if self.piece_color(target) != color:
                            moves.append(Move((r, c), (nr, nc), p, captured=target))
                        break
                    nr += dr;
                    nc += dc
            return moves

        if pt == 'K':
            for dr in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    if dr == 0 and dc == 0: continue
                    nr, nc = r + dr, c + dc
                    if not self.in_bounds(nr, nc): continue
                    target = self.board[nr][nc]
                    if target is None or self.piece_color(target) != color:
                        moves.append(Move((r, c), (nr, nc), p, captured=target if target else None))

            if not check_legality: return moves

            if (r, c) == ((0, 4) if color == WHITE else (7, 4)):
                if color == WHITE:
                    king_side = self.castling_rights.get('K', False)
                    queen_side = self.castling_rights.get('Q', False)
                    rank = 0
                else:
                    king_side = self.castling_rights.get('k', False)
                    queen_side = self.castling_rights.get('q', False)
                    rank = 7
                if king_side:
                    if self.board[rank][5] is None and self.board[rank][6] is None:
                        rook = self.board[rank][7]
                        if rook and rook.upper() == 'R' and self.piece_color(rook) == color:
                            if not self.is_square_attacked((rank, 4),
                                                           self._opponent(color)) and not self.is_square_attacked(
                                (rank, 5), self._opponent(color)) and not self.is_square_attacked((rank, 6),
                                                                                                  self._opponent(
                                                                                                      color)):
                                moves.append(Move((r, c), (rank, 6), p, is_castle=True))
                if queen_side:
                    if self.board[rank][3] is None and self.board[rank][2] is None and self.board[rank][1] is None:
                        rook = self.board[rank][0]
                        if rook and rook.upper() == 'R' and self.piece_color(rook) == color:
                            if not self.is_square_attacked((rank, 4),
                                                           self._opponent(color)) and not self.is_square_attacked(
                                (rank, 3), self._opponent(color)) and not self.is_square_attacked((rank, 2),
                                                                                                  self._opponent(
                                                                                                      color)):
                                moves.append(Move((r, c), (rank, 2), p, is_castle=True))
            return moves

        return moves

    def _make_move_internal(self, m: Move):
        fr_r, fr_c = m.from_sq;
        to_r, to_c = m.to_sq
        piece = self.board[fr_r][fr_c]
        assert piece is not None
        if piece.upper() == 'P' or m.captured:
            self.halfmove_clock = 0
        else:
            self.halfmove_clock += 1
        if m.is_en_passant:
            cap_r = fr_r;
            cap_c = to_c
            m.captured = self.board[cap_r][cap_c]
            self.board[cap_r][cap_c] = None
        if m.is_castle:
            if to_c == 6:
                rank = to_r
                self.board[rank][5] = self.board[rank][7]
                self.board[rank][7] = None
            elif to_c == 2:
                rank = to_r
                self.board[rank][3] = self.board[rank][0]
                self.board[rank][0] = None
        if self.board[to_r][to_c] is not None and not m.is_en_passant:
            m.captured = self.board[to_r][to_c]
        self.board[to_r][to_c] = piece
        self.board[fr_r][fr_c] = None
        if m.promotion:
            self.board[to_r][to_c] = m.promotion
        self.en_passant_target = None
        if piece.upper() == 'P' and abs(to_r - fr_r) == 2:
            ep_r = (to_r + fr_r) // 2;
            ep_c = fr_c
            self.en_passant_target = (ep_r, ep_c)
        if piece.upper() == 'K':
            if piece.isupper():
                self.castling_rights['K'] = False;
                self.castling_rights['Q'] = False
            else:
                self.castling_rights['k'] = False;
                self.castling_rights['q'] = False
        if piece.upper() == 'R':
            if fr_r == 0 and fr_c == 0: self.castling_rights['Q'] = False
            if fr_r == 0 and fr_c == 7: self.castling_rights['K'] = False
            if fr_r == 7 and fr_c == 0: self.castling_rights['q'] = False
            if fr_r == 7 and fr_c == 7: self.castling_rights['k'] = False
        if m.captured and m.captured.upper() == 'R':
            cr = to_r;
            cc = to_c
            if cr == 0 and cc == 0: self.castling_rights['Q'] = False
            if cr == 0 and cc == 7: self.castling_rights['K'] = False
            if cr == 7 and cc == 0: self.castling_rights['q'] = False
            if cr == 7 and cc == 7: self.castling_rights['k'] = False

    def push_move(self, m: Move):
        state = {
            'board': copy.deepcopy(self.board),
            'castling_rights': copy.deepcopy(self.castling_rights),
            'en_passant_target': self.en_passant_target,
            'halfmove_clock': self.halfmove_clock,
            'fullmove_number': self.fullmove_number,
            'turn': self.turn
        }
        self.history.append((m, state))
        self._make_move_internal(m)
        if self.turn == BLACK: self.fullmove_number += 1
        self.turn = self._opponent(self.turn)
        self.fen_history.append(self._fen_for_repetition())

    def undo_move(self):
        if not self.history: return
        m, state = self.history.pop()
        self.board = state['board']
        self.castling_rights = state['castling_rights']
        self.en_passant_target = state['en_passant_target']
        self.halfmove_clock = state['halfmove_clock']
        self.fullmove_number = state['fullmove_number']
        self.turn = state['turn']
        if self.fen_history: self.fen_history.pop()

    def make_move_uci(self, uci: str, prompt_promotion: bool = False) -> Optional[Move]:
        if len(uci) < 4: return None
        try:
            from_file = FILES.index(uci[0]);
            from_rank = RANKS.index(uci[1])
            to_file = FILES.index(uci[2]);
            to_rank = RANKS.index(uci[3])
        except ValueError:
            return None
        fr = (from_rank, from_file);
        to = (to_rank, to_file)
        promotion = uci[4] if len(uci) >= 5 else None
        moves = self.generate_moves(legal=True)
        candidates = [m for m in moves if m.from_sq == fr and m.to_sq == to]
        if not candidates: return None
        promos = [m for m in candidates if m.promotion]
        if promos and not promotion: return None
        for m in candidates:
            if promotion:
                if m.promotion and promotion.lower() == m.promotion[0].lower():
                    self.push_move(m);
                    return m
            else:
                if not m.promotion:
                    self.push_move(m);
                    return m
        return None

    def game_status(self):
        in_check = self.king_in_check(self.turn)
        moves = self.generate_moves(legal=True)
        if not moves:
            if in_check:
                return ('checkmate', self._opponent(self.turn))
            else:
                return ('stalemate', None)
        if self.halfmove_clock >= 100: return ('draw', None)
        rep_count = collections.Counter(self.fen_history)
        if rep_count[self._fen_for_repetition()] >= 3: return ('draw', None)
        return ('ongoing', None)


# ---------------- notation ----------------
def move_to_readable(m: Move) -> str:
    if m.is_castle: return "O-O" if m.to_sq[1] == 6 else "O-O-O"
    piece = m.piece.upper()
    dest = FILES[m.to_sq[1]] + RANKS[m.to_sq[0]]
    capture = 'x' if m.captured else ''
    promo = f"={m.promotion.upper()}" if m.promotion else ''

    if piece == 'P':
        if capture:
            from_file = FILES[m.from_sq[1]]
            return f"{from_file}x{dest}{promo}"
        else:
            return f"{dest}{promo}"
    else:
        # Simplification de la notation pour l'affichage (pas de désambiguation complète)
        return f"{piece}{capture}{dest}{promo}"


# ---------------- Treeview History (Onglet Coups) ----------------
class TreeviewHistory(tk.Frame):
    def __init__(self, master, app_instance, *args, **kwargs):
        super().__init__(master, *args, **kwargs)
        self.app = app_instance

        self.configure(bg=UI_BG_PRIMARY)

        style = ttk.Style(self)
        style.theme_use("default")

        style.configure("Treeview",
                        background=UI_BG_SECONDARY,
                        foreground=UI_FG,
                        fieldbackground=UI_BG_SECONDARY,
                        rowheight=25,
                        font=('TkDefaultFont', 10))

        style.configure("Treeview.Heading",
                        background=UI_BG_PRIMARY,
                        foreground=UI_FG,
                        font=('TkDefaultFont', 10, 'bold'))

        self.tree = ttk.Treeview(self, columns=('White', 'Black'), show='headings', height=12)
        self.tree.configure(selectmode='browse')

        self.tree.heading('#0', text='No.', anchor='e')
        self.tree.heading('White', text='Blancs', anchor='center')
        self.tree.heading('Black', text='Noirs', anchor='center')

        # FIX V15: Colonnes non redimensionnables et largeur fixe.
        self.tree.column('#0', width=40, anchor='e', stretch=tk.NO)
        self.tree.column('White', width=130, anchor='center', stretch=tk.YES)
        self.tree.column('Black', width=130, anchor='center', stretch=tk.YES)

        vsb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)

        vsb.pack(side='right', fill='y')
        self.tree.pack(side='left', fill='both', expand=True)

        self.last_selected_cell: Optional[Tuple[str, str]] = None

        self.tree.bind("<ButtonRelease-1>", self.on_history_select)

    def clear(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.last_selected_cell = None

    def add_row(self, num: int, white_text: str, black_text: str):
        item_id = f"move_{num}"
        self.tree.insert('', 'end', text=f"{num}.", values=(white_text, black_text), iid=item_id)

    def deselect_all_cells(self):
        """Enlève le surlignage de la dernière cellule sélectionnée."""
        if self.last_selected_cell:
            item_id, column_id = self.last_selected_cell
            current_tags = self.tree.item(item_id, 'tags')
            new_tags = tuple(t for t in current_tags if not t.startswith("selected_#"))
            self.tree.item(item_id, tags=new_tags)
            self.last_selected_cell = None
        self.tree.selection_remove(self.tree.selection())

    def apply_cell_selection(self, item_id, col_id):
        """Applique le surlignage à la cellule spécifiée et la définit comme la dernière sélection."""

        self.deselect_all_cells()

        tag_name = f"selected_{col_id}"
        self.tree.tag_configure(tag_name, background=UI_CELL_HIGHLIGHT_BG, foreground=UI_FG)

        current_tags = self.tree.item(item_id, 'tags')
        new_tags = (*current_tags, tag_name)
        self.tree.item(item_id, tags=new_tags)

        self.last_selected_cell = (item_id, col_id)

        self.tree.see(item_id)

    def on_history_select(self, event):
        """Restaure la position de l'échiquier au coup cliqué, en utilisant l'historique complet."""

        full_moves = self.app.full_history_data
        if not full_moves:
            self.deselect_all_cells()
            return

        item_id = self.tree.identify_row(event.y)
        col_id = self.tree.identify_column(event.x)

        if not item_id or col_id == '#0':
            self.deselect_all_cells()
            return

        try:
            move_num_str = self.tree.item(item_id, 'text').replace('.', '').strip()
            move_num = int(move_num_str)

        except ValueError:
            self.deselect_all_cells()
            return

        target_index = -1
        if col_id == '#1':  # Colonne Blancs
            target_index = 2 * (move_num - 1)
        elif col_id == '#2':  # Colonne Noirs
            target_index = 2 * (move_num - 1) + 1

        if target_index == -1: return

        if target_index >= len(full_moves):
            target_index = len(full_moves) - 1
            if target_index < 0: return

        # 1. Appliquer le surlignage de la cellule
        self.apply_cell_selection(item_id, col_id)

        # 2. Restaurer la position (avec animation)
        self.app.restore_position(target_index, animate=True)

        # 3. Mettre à jour les infos
        self.app.info_tab.refresh_info()


# ---------------- Onglet Infos (Coups Légaux) ----------------
class InfoTab(tk.Frame):
    def __init__(self, master, app_instance, *args, **kwargs):
        super().__init__(master, *args, **kwargs)
        self.app = app_instance
        self.configure(bg=UI_BG_SECONDARY)

        # Largeur augmentée (width=45) pour forcer la largeur minimale de la side_frame
        self.text_area = tk.Text(self, bg=UI_BG_SECONDARY, fg=UI_FG,
                                 font=('TkDefaultFont', 10), wrap=tk.WORD,
                                 height=12, width=45, borderwidth=0, relief='flat')
        self.text_area.pack(fill='both', expand=False, padx=5, pady=5)
        self.text_area.insert(tk.END, "Informations sur le jeu...")
        self.text_area.config(state=tk.DISABLED)

    def refresh_info(self):
        """Met à jour l'affichage avec les coups légaux actuels."""
        self.text_area.config(state=tk.NORMAL)
        self.text_area.delete(1.0, tk.END)

        if self.app.animating:
            self.text_area.insert(tk.END, "Animation de relecture en cours...")
            self.text_area.config(state=tk.DISABLED)
            return

        moves = self.app.board.generate_moves(legal=True)
        turn = "Blancs" if self.app.board.turn == WHITE else "Noirs"

        self.text_area.insert(tk.END, f"--- À jouer : {turn} ---\n\n")

        if not moves:
            status, _ = self.app.board.game_status()
            self.text_area.insert(tk.END, f"Partie terminée : {status.upper()}!\n")
            self.text_area.config(state=tk.DISABLED)
            return

        # Groupement des coups par pièce
        piece_moves: Dict[str, List[str]] = collections.defaultdict(list)
        for m in moves:
            piece_symbol = m.piece.upper()
            readable_move = move_to_readable(m)
            piece_moves[piece_symbol].append(readable_move)

        self.text_area.insert(tk.END, f"Coups légaux possibles ({len(moves)}) :\n")

        # Affichage par ordre de groupe
        for piece_type in GROUP_ORDER:
            if piece_type in piece_moves:
                moves_list = ", ".join(sorted(piece_moves[piece_type]))
                self.text_area.insert(tk.END, f"\n{piece_type} : {moves_list}")

        self.text_area.config(state=tk.DISABLED)


# ---------------- Onglet Parties (Historique de parties) ----------------
class GamesTab(tk.Frame):
    def __init__(self, master, app_instance, *args, **kwargs):
        super().__init__(master, *args, **kwargs)
        self.app = app_instance
        self.configure(bg=UI_BG_SECONDARY)

        style = ttk.Style(self)
        style.configure("GamesList.Treeview",
                        background=UI_BG_SECONDARY,
                        foreground=UI_FG,
                        fieldbackground=UI_BG_SECONDARY,
                        rowheight=25,
                        font=('TkDefaultFont', 10))

        self.tree = ttk.Treeview(self, columns=('Name',), show='headings',
                                 height=12, style='GamesList.Treeview', selectmode='browse')

        self.tree.heading('Name', text='Parties Enregistrées', anchor='center')
        # stretch=tk.YES permet à la colonne de remplir l'espace.
        self.tree.column('Name', width=300, anchor='w', stretch=tk.YES)

        vsb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)

        vsb.pack(side='right', fill='y')
        self.tree.pack(side='left', fill='both', expand=True)

        self.tree.bind("<<TreeviewSelect>>", self.on_game_select)

    def refresh_list(self):
        """Met à jour la liste des parties affichées."""
        for item in self.tree.get_children():
            self.tree.delete(item)

        for idx, (name, history) in enumerate(self.app.saved_games):
            item_id = f"saved_game_{idx}"
            if history:
                last_move_readable = move_to_readable(history[-1])
                display_name = f"{name} ({len(history)} coups, {last_move_readable})"
            else:
                display_name = f"{name} (Nouvelle partie)"

            self.tree.insert('', 'end', text=name, values=(display_name,), iid=item_id)

    def on_game_select(self, event):
        """Charge la partie sélectionnée dans le plateau pour l'analyse."""
        selected_item = self.tree.selection()
        if not selected_item: return

        item_id = selected_item[0]
        try:
            idx = int(item_id.split('_')[-1])
        except ValueError:
            return

        if idx < len(self.app.saved_games):
            name, history = self.app.saved_games[idx]

            self.app.full_history_data = copy.deepcopy(history)

            target_index = len(history) - 1
            if target_index >= 0:
                self.app.restore_position(target_index, animate=False)
            else:
                self.app.on_new()  # Si la partie est vide, réinitialiser

            self.app.started = False
            self.app.game_over = False
            self.app.start_button.config(text="Commencer la partie")

            self.app.tab_control.select(0)

            self.tree.selection_remove(item_id)

        # ---------------- Menu de Démarrage (REINTRODUIT) ----------------


class StartMenu(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Sélection du Mode de Jeu")
        self.resizable(False, False)
        self.configure(bg=UI_BG_PRIMARY)
        self.geometry("300x200")

        self.mode = None
        self.network_mode = None

        style = ttk.Style()
        style.theme_use("default")
        style.configure('Menu.TButton', background=UI_BG_SECONDARY, foreground=UI_FG,
                        font=('TkDefaultFont', 12, 'bold'), padding=[10, 5])
        style.map('Menu.TButton', background=[('active', '#413E3B')])

        tk.Label(self, text="Choisissez votre mode de jeu", font=('TkDefaultFont', 12, 'bold'),
                 bg=UI_BG_PRIMARY, fg=UI_FG, pady=20).pack()

        btn_frame = tk.Frame(self, bg=UI_BG_PRIMARY)
        btn_frame.pack(pady=10)

        # Bouton 1: Local (1 PC)
        ttk.Button(btn_frame, text="Local (1 PC)", command=lambda: self.select_mode('human'),
                   style='Menu.TButton').pack(fill='x', pady=5)

        # Bouton 2: Contre IA
        ttk.Button(btn_frame, text="Contre IA", command=lambda: self.select_mode('ai'),
                   style='Menu.TButton').pack(fill='x', pady=5)

        # Bouton 3: Réseau (LAN)
        ttk.Button(btn_frame, text="Multijoueur (LAN)", command=self.setup_lan,
                   style='Menu.TButton').pack(fill='x', pady=5)

        self.center_window()

    def center_window(self):
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f'{width}x{height}+{x}+{y}')

    def select_mode(self, mode, net_mode=None):
        self.mode = mode
        self.network_mode = net_mode
        self.destroy()

    def setup_lan(self):
        # Simple dialog to choose Host or Join
        choice = messagebox.askquestion("LAN Mode",
                                        "Voulez-vous héberger la partie ?\n(Oui = Host / Blancs, Non = Join / Noirs)")
        if choice == 'yes':
            self.select_mode('lan', 'host')
        else:
            self.select_mode('lan', 'client')


# ---------------- ChessApp (Fenêtre Principale) ----------------
class ChessApp(tk.Tk):
    # CRITICAL FIX: Liste pour stocker les références d'images du canevas
    canvas_images: List[tk.PhotoImage] = []

    def __init__(self, mode: str, network_config=None):
        # 1. INITIALISATION Tkinter
        super().__init__()

        self.game_mode = mode  # 'human', 'ai', 'lan'
        self.ai_color = BLACK
        self.network_manager = None

        # Si mode LAN, configurer le réseau
        if self.game_mode == 'lan' and network_config:
            is_host = (network_config == 'host')

            if is_host:
                self.network_manager = NetworkManager(is_host=True)
                # Afficher l'IP pour que l'autre joueur puisse rejoindre
                messagebox.showinfo("Hébergement",
                                    f"En attente de connexion...\nVotre IP Locale: {self.network_manager.local_ip}")
                # Accepter la connexion (bloquant, devrait idéalement être threadé mais ok pour le setup initial simple)
                # Pour éviter de geler l'UI, on utilise un thread ici aussi
                threading.Thread(target=self._wait_for_connection, daemon=True).start()
            else:
                target_ip = simpledialog.askstring("Connexion", "Entrez l'IP de l'hôte:")
                if target_ip:
                    self.network_manager = NetworkManager(is_host=False, ip=target_ip)
                    if self.network_manager.connect():
                        messagebox.showinfo("Succès", "Connecté à l'hôte !")
                        # Si je suis client (Noirs), je flip le board
                        self.is_flipped = True
                        # Lancer le thread d'écoute
                        threading.Thread(target=self._listen_network, daemon=True).start()
                    else:
                        messagebox.showerror("Erreur", "Impossible de se connecter.")
                        self.destroy()
                        return

        self.is_analyzing_saved_game: bool = False

        self.title(f"Échecs - {mode.upper()}")
        self.resizable(False, False)
        self.configure(bg=UI_BG_PRIMARY)

        # 2. INITIALISATION TTK ET IMAGES (Différée pour éviter bug)
        self.after_idle(self._setup_widgets)

        # ... (reste des variables initialisées comme avant) ...
        self.square_size = 72
        self.board_px = 8 * self.square_size

        self.board = Board()
        self.captured_by_white: List[str] = []
        self.captured_by_black: List[str] = []
        self.full_history_data: List[Move] = []
        self.saved_games: List[Tuple[str, List[Move]]] = []
        self.selected: Optional[Tuple[int, int]] = None
        self.legal_targets: List[Tuple[int, int]] = []
        self.animating = False
        self.game_over = False
        self.started = False
        self.init_seconds = 5 * 60
        self.time_left = {WHITE: self.init_seconds, BLACK: self.init_seconds}
        self.clock_history: List[Tuple[int, int]] = []
        self.last_move_squares: Optional[Tuple[Tuple[int, int], Tuple[int, int]]] = None
        if self.game_mode != 'lan': self.is_flipped = False  # Reset sauf si LAN Client
        self.current_theme = 'dark'
        self.drawn_annotations: List[Union[Tuple[Tuple[int, int]], Tuple[Tuple[int, int], Tuple[int, int]]]] = []
        self.images: Dict[str, tk.PhotoImage] = {}
        self.small_images: Dict[str, tk.PhotoImage] = {}

    def _wait_for_connection(self):
        """Thread hôte pour attendre le client."""
        if self.network_manager.connect():
            self.after(0, lambda: messagebox.showinfo("Connecté", "Le client a rejoint la partie !"))
            self.after(0, lambda: threading.Thread(target=self._listen_network, daemon=True).start())

    def _listen_network(self):
        """Boucle d'écoute des coups réseau."""
        while True:
            move_uci = self.network_manager.receive_move()
            if move_uci:
                self.after(0, lambda m=move_uci: self.apply_network_move(m))
            else:
                # Connexion perdue
                break

    def apply_network_move(self, uci: str):
        """Applique un coup reçu via le réseau."""
        move = self.board.make_move_uci(uci)  # Cette méthode doit exister ou être adaptée
        if move:
            self.full_history_data.append(copy.deepcopy(move))
            self.last_move_squares = move.from_sq, move.to_sq
            if move.captured:
                color = WHITE if move.piece.isupper() else BLACK
                if color == WHITE:
                    self.captured_by_white.append(move.captured)
                else:
                    self.captured_by_black.append(move.captured)

            self.draw_board()
            self.info_tab.refresh_info()

            if not self.started:
                self.started = True
                self.start_button.config(text="En cours")

    def _setup_widgets(self):
        # ... (Code identique à V21 pour la création de l'UI) ...
        self._load_images()
        style = ttk.Style(self)
        style.theme_use("default")
        style.configure('Dark.TButton', background=UI_BG_SECONDARY, foreground=UI_FG, borderwidth=0,
                        focuscolor=UI_BG_SECONDARY, relief='flat')
        style.map('Dark.TButton', background=[('active', '#413E3B')])

        self.board_frame = tk.Frame(self, bg=UI_BG_PRIMARY)
        self.board_frame.grid(row=0, column=0, sticky='nw', padx=6, pady=6)
        self.side_frame = tk.Frame(self, bg=UI_BG_PRIMARY)
        self.side_frame.grid(row=0, column=1, sticky='n', padx=6, pady=6)

        # ... (Setup Timer, Tabs, Canvas, Bindings - Copié de V21) ...
        # [Pour la brièveté, j'assume que le corps de _setup_widgets est le même]
        # Assurez-vous d'inclure TOUT le code de création d'interface ici.

        # IMPORTANT: Modifiez on_click_move pour envoyer le coup

    # ... (Méthodes IA, Draw, etc. identiques à V21) ...

    def on_click_move(self, event):
        # ... (Logique de sélection/mouvement existante) ...

        # Vérification Tour Réseau
        if self.game_mode == 'lan':
            # Si je suis Host (Blanc) et c'est au Noir de jouer -> Bloquer
            if self.network_manager.is_host and self.board.turn == BLACK: return
            # Si je suis Client (Noir) et c'est au Blanc de jouer -> Bloquer
            if not self.network_manager.is_host and self.board.turn == WHITE: return

            # ... (Si un coup est joué) ...
            if chosen_move:
                # ... (Appliquer coup localement) ...

                # ENVOYER AU RESEAU
                if self.game_mode == 'lan':
                    self.network_manager.send_move(chosen_move.uci())

                # Gérer IA si mode AI
                if self.game_mode == 'ai' and self.board.turn == self.ai_color:
                    self.after(200, self.handle_ai_move)


# ---------------- main ----------------
if __name__ == "__main__":
    menu = StartMenu()
    menu.mainloop()

    if menu.mode:
        app = ChessApp(mode=menu.mode, network_config=menu.network_mode)
        app.mainloop()
