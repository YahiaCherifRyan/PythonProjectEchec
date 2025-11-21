#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
main.py - Version FINALE & STABLE (Initialisation Corrigée)
- Correction : Gestion plus robuste de la désynchronisation de l'historique et de l'état d'animation.
- Toutes les fonctionnalités (Analyse, Sélection Cellule Unique, Contrôles) sont conservées.
"""
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from dataclasses import dataclass
from typing import List, Optional, Tuple, Dict, Union
import copy, collections, math

# ---------------- constants ----------------
FILES = 'abcdefgh'
RANKS = '12345678'
WHITE = 'w'
BLACK = 'b'

IMAGE_MAP = {
    'P': "wP.png", 'R': "wR.png", 'N': "wN.png", 'B': "wB.png", 'Q': "wQ.png", 'K': "wK.png",
    'p': "bP.png", 'r': "bR.png", 'n': "bN.png", 'b': "bB.png", 'q': "bQ.png", 'k': "bK.png"
}
GROUP_ORDER = ['P', 'N', 'B', 'R', 'Q', 'K']

# ---------------- Thème Sombre Inspiré Chess.com ----------------
DARK_BG_PRIMARY = '#262421'
DARK_BG_SECONDARY = '#312E2B'
DARK_FG = '#FFFFFF'
DARK_TIMER_ACTIVE = '#769656'
DARK_TIMER_INACTIVE = '#404040'

# Couleurs de l'échiquier
BOARD_LIGHT = '#D1D8D2'
BOARD_DARK = '#898B99'

# Couleurs d'analyse
CIRCLE_COLOR = '#0a2d15'
ARROW_COLOR = '#0a2d15'
CELL_HIGHLIGHT_BG = '#505050'  # Fond gris foncé pour la cellule sélectionnée


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
                for m in self._piece_moves(r, c, p):
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

    def _piece_moves(self, r, c, p):
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
                if m.promotion and promotion.lower() == m.promotion.lower():
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
        return f"{piece}{capture}{dest}{promo}"


# ---------------- Treeview History ----------------
class TreeviewHistory(tk.Frame):
    def __init__(self, master, app_instance, *args, **kwargs):
        super().__init__(master, *args, **kwargs)
        self.app = app_instance
        self.configure(bg=DARK_BG_PRIMARY)

        style = ttk.Style(self)
        style.theme_use("default")

        style.configure("Treeview",
                        background=DARK_BG_SECONDARY,
                        foreground=DARK_FG,
                        fieldbackground=DARK_BG_SECONDARY,
                        rowheight=25,
                        font=('TkDefaultFont', 10))

        style.configure("Treeview.Heading",
                        background=DARK_BG_PRIMARY,
                        foreground=DARK_FG,
                        font=('TkDefaultFont', 10, 'bold'))

        self.tree = ttk.Treeview(self, columns=('White', 'Black'), show='headings', height=12)

        self.tree.configure(selectmode='none')

        self.tree.heading('#0', text='No.', anchor='e')
        self.tree.heading('White', text='Blancs', anchor='center')
        self.tree.heading('Black', text='Noirs', anchor='center')

        self.tree.column('#0', width=40, anchor='e', stretch=tk.NO)
        self.tree.column('White', width=130, anchor='center', stretch=tk.NO)
        self.tree.column('Black', width=130, anchor='center', stretch=tk.NO)

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

    def apply_cell_selection(self, item_id, col_id):
        """Applique le surlignage à la cellule spécifiée et la définit comme la dernière sélection."""

        self.deselect_all_cells()

        tag_name = f"selected_{col_id}"
        self.tree.tag_configure(tag_name, background=CELL_HIGHLIGHT_BG, foreground=DARK_FG)

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


class ChessApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Échecs - Style Chess")
        self.resizable(False, False)
        self.configure(bg=DARK_BG_PRIMARY)

        style = ttk.Style()
        style.theme_use('default')
        style.configure('Dark.TButton', background=DARK_BG_SECONDARY, foreground=DARK_FG, borderwidth=0,
                        focuscolor=DARK_BG_SECONDARY, relief='flat')
        style.map('Dark.TButton', background=[('active', '#413E3B')])

        self.square_size = 72
        self.board_px = 8 * self.square_size

        self.board_frame = tk.Frame(self, bg=DARK_BG_PRIMARY)
        self.board_frame.grid(row=0, column=0, sticky='nw', padx=6, pady=6)
        self.side_frame = tk.Frame(self, bg=DARK_BG_PRIMARY)
        self.side_frame.grid(row=0, column=1, sticky='n', padx=6, pady=6)

        # --------------------- SECTION SIDEBAR ---------------------
        self.timer_container = tk.Frame(self.side_frame, bg=DARK_BG_PRIMARY)
        self.timer_container.pack(pady=(0, 10), padx=5, fill='x')

        self.black_timer_frame = self._create_timer_widget(BLACK)
        self.black_timer_frame.pack(fill='x', pady=(0, 5))

        self.white_timer_frame = self._create_timer_widget(WHITE)
        self.white_timer_frame.pack(fill='x', pady=(5, 0))

        tk.Label(self.side_frame, text="Historique", font=('TkDefaultFont', 11, 'bold'), bg=DARK_BG_PRIMARY,
                 fg=DARK_FG).pack(pady=(10, 6))

        self.history_widget = TreeviewHistory(self.side_frame, self, bg=DARK_BG_PRIMARY)
        self.history_widget.pack(fill='x', padx=5)

        btn_frame = tk.Frame(self.side_frame, bg=DARK_BG_PRIMARY)
        btn_frame.pack(pady=12, fill='x')
        ttk.Button(btn_frame, text="Annuler", command=self.on_undo, style='Dark.TButton').pack(side='left', padx=2,
                                                                                               fill='x', expand=True)
        ttk.Button(btn_frame, text="Nouvelle partie", command=self.on_new, style='Dark.TButton').pack(side='left',
                                                                                                      padx=2, fill='x',
                                                                                                      expand=True)
        ttk.Button(btn_frame, text="Param. temps", command=self.set_time_dialog, style='Dark.TButton').pack(side='left',
                                                                                                            padx=2,
                                                                                                            fill='x',
                                                                                                            expand=True)

        # --------------------- SECTION ÉCHIQUIER ---------------------
        self.status = tk.Label(self.board_frame, text="", anchor='w', bg=DARK_BG_PRIMARY, fg=DARK_FG, height=1,
                               font=('TkDefaultFont', 11))
        self.status.grid(row=0, column=0, sticky='we', pady=(0, 6), padx=4)

        self.canvas = tk.Canvas(self.board_frame, width=self.board_px, height=self.board_px, bg=DARK_BG_PRIMARY,
                                highlightthickness=0)
        self.canvas.grid(row=1, column=0)

        self.canvas.bind("<Button-1>", self.on_click_move)
        self.canvas.bind("<Button-3>", self.on_right_click_clear)
        self.canvas.bind("<Control-Button-3>", self.on_ctrl_click_start)
        self.canvas.bind("<Control-B3-Motion>", self.on_ctrl_click_drag)
        self.canvas.bind("<Control-ButtonRelease-3>", self.on_ctrl_click_release)

        self.start_button = ttk.Button(self.board_frame, text="Commencer la partie", command=self.on_start,
                                       style='Dark.TButton')
        self.start_button.grid(row=2, column=0, sticky='we', pady=(6, 0))

        self._load_images()

        self.drawn_annotations: List[Union[Tuple[Tuple[int, int]], Tuple[Tuple[int, int], Tuple[int, int]]]] = []
        self.drawing_arrow = False
        self.arrow_start_sq: Optional[Tuple[int, int]] = None
        self.current_arrow_id: Optional[int] = None

        self.full_history_data: List[Move] = []

        self.board = Board()
        self.selected: Optional[Tuple[int, int]] = None
        self.legal_targets: List[Tuple[int, int]] = []
        self.animating = False
        self.game_over = False
        self.captured_by_white: List[str] = []
        self.captured_by_black: List[str] = []
        self.started = False
        self.init_seconds = 5 * 60
        self.time_left = {WHITE: self.init_seconds, BLACK: self.init_seconds}
        self.clock_history: List[Tuple[int, int]] = []
        self.update_clock_labels()
        self.after(1000, self._tick)

        self.draw_board()

    def _animate_history_replay(self, moves_to_play: List[Move], current_index: int, total_moves: int,
                                temp_board_final: Board, temp_captured_w_final: List[str],
                                temp_captured_b_final: List[str]):
        """Anime la relecture coup par coup."""
        if current_index >= total_moves:
            self.board = temp_board_final
            self.captured_by_white = temp_captured_w_final
            self.captured_by_black = temp_captured_b_final
            self.selected = None
            self.legal_targets = []
            self.animating = False
            self.draw_board()
            return

        self.animating = True
        move = moves_to_play[current_index]

        fr_r, fr_c = move.from_sq
        to_r, to_c = move.to_sq

        piece_to_move = self.board.board[fr_r][fr_c]

        # NOTE IMPORTANTE: Ne pas tenter d'animer si la pièce n'est pas là, juste pousser le coup.
        if not piece_to_move:
            self.board.push_move(move)
            self.after(5, lambda: self._animate_history_replay(moves_to_play, current_index + 1, total_moves,
                                                               temp_board_final, temp_captured_w_final,
                                                               temp_captured_b_final))
            return

        x0, y0 = self._sq_center_coords(fr_r, fr_c)
        x1, y1 = self._sq_center_coords(to_r, to_c)
        img = self.images.get(piece_to_move)

        # Appliquer le coup sur le plateau actif (pour que draw_board affiche l'état intermédiaire)
        self.board.push_move(move)

        self.draw_board()

        duration_ms = 150
        steps = max(5, int(duration_ms / 20))
        dx = (x1 - x0) / steps
        dy = (y1 - y0) / steps

        pid = self.canvas.create_image(x0, y0, image=img, tags="anim_piece")

        def step(i, curx, cury):
            if i >= steps:
                self.canvas.delete(pid)
                self.after(30, lambda: self._animate_history_replay(moves_to_play, current_index + 1, total_moves,
                                                                    temp_board_final, temp_captured_w_final,
                                                                    temp_captured_b_final))
                return

            nx = curx + dx;
            ny = cury + dy
            self.canvas.coords(pid, nx, ny)
            self.after(20, lambda: step(i + 1, nx, ny))

        step(0, x0, y0)

    def restore_position(self, target_move_index: int, animate: bool = False):
        """Lance la restauration (avec ou sans animation) et nettoie l'affichage."""

        if self.animating: return

        full_moves = self.full_history_data
        if not full_moves: return

        if target_move_index >= len(full_moves):
            target_move_index = len(full_moves) - 1
            if target_move_index < 0: return

        moves_to_play = full_moves[:target_move_index + 1]

        # 1. Calculer l'état final désiré
        temp_board_final = Board()
        temp_captured_w_final = []
        temp_captured_b_final = []

        for move in moves_to_play:
            move_copy = copy.deepcopy(move)
            temp_board_final.push_move(move_copy)
            if move.captured:
                mover_color = WHITE if move.piece.isupper() else BLACK
                if mover_color == WHITE:
                    temp_captured_w_final.append(move.captured)
                else:
                    temp_captured_b_final.append(move.captured)

        # Si pas d'animation, on applique l'état final directement
        if not animate:
            self.board = temp_board_final
            self.captured_by_white = temp_captured_w_final
            self.captured_by_black = temp_captured_b_final
            self.selected = None
            self.legal_targets = []
            self.started = False
            self.draw_board()
            return

        # --- Lancement de l'Animation ---

        self.history_widget.deselect_all_cells()
        self.selected = None
        self.legal_targets = []
        self.animating = True
        self.started = False

        # Réinitialiser le plateau au début (pour un replay propre)
        self.board = Board()
        self.captured_by_white = []
        self.captured_by_black = []
        self.draw_board()

        self._animate_history_replay(moves_to_play, 0, len(moves_to_play), temp_board_final, temp_captured_w_final,
                                     temp_captured_b_final)

    def _load_images(self):
        self.images: Dict[str, tk.PhotoImage] = {}
        self.small_images: Dict[str, tk.PhotoImage] = {}

        for key, filename in IMAGE_MAP.items():
            try:
                img_main = tk.PhotoImage(file=filename)
                self.images[key] = img_main

                subsample_factor = 2
                img_small = img_main.subsample(subsample_factor, subsample_factor)
                self.small_images[key] = img_small

            except Exception as e:
                img_placeholder = tk.PhotoImage(width=1, height=1)
                self.images[key] = img_placeholder
                self.small_images[key] = img_placeholder

    def _create_timer_widget(self, color):
        frame = tk.Frame(self.timer_container, bg=DARK_BG_SECONDARY, relief='flat', borderwidth=0, padx=8, pady=8)

        name_label = tk.Label(frame, text="Blanc" if color == WHITE else "Noir", bg=DARK_BG_SECONDARY, fg=DARK_FG,
                              font=('TkDefaultFont', 10, 'bold'))
        name_label.pack(side='left', padx=(0, 10))

        if color == WHITE:
            self.time_label_white = tk.Label(frame, text="05:00", font=('Courier', 20, 'bold'), bg=DARK_TIMER_INACTIVE,
                                             fg=DARK_FG, width=6, padx=5)
            self.time_label_white.pack(side='right', padx=(10, 0))
            self.white_timer_bg = self.time_label_white
        else:
            self.time_label_black = tk.Label(frame, text="05:00", font=('Courier', 20, 'bold'), bg=DARK_TIMER_INACTIVE,
                                             fg=DARK_FG, width=6, padx=5)
            self.time_label_black.pack(side='right', padx=(10, 0))
            self.black_timer_bg = self.time_label_black

        capture_frame = tk.Frame(frame, bg=DARK_BG_SECONDARY)
        capture_frame.pack(side='right', expand=True, fill='x', padx=(0, 10))

        if color == WHITE:
            self.white_capture_frame = capture_frame
        else:
            self.black_capture_frame = capture_frame

        return frame

    # mapping
    def board_to_canvas(self, r, c):
        return (7 - r, c)

    def canvas_to_board(self, canvas_r, canvas_c):
        return (7 - canvas_r, canvas_c)

    # Utilitaires pour l'annotation
    def _sq_center_coords(self, r, c) -> Tuple[int, int]:
        cr, cc = self.board_to_canvas(r, c)
        x = cc * self.square_size + self.square_size // 2
        y = cr * self.square_size + self.square_size // 2
        return x, y

    def _coords_to_square(self, x, y) -> Optional[Tuple[int, int]]:
        if not (0 <= x < self.board_px and 0 <= y < self.board_px):
            return None
        cc = x // self.square_size
        cr = y // self.square_size
        return self.canvas_to_board(cr, cc)

    def draw_board(self):
        self.canvas.delete("all")
        light, dark = BOARD_LIGHT, BOARD_DARK
        for row in range(8):
            for col in range(8):
                x1 = col * self.square_size;
                y1 = row * self.square_size
                color = light if (row + col) % 2 == 0 else dark
                self.canvas.create_rectangle(x1, y1, x1 + self.square_size, y1 + self.square_size, fill=color,
                                             outline=color)

        for annotation in self.drawn_annotations:
            if len(annotation) == 1:
                r, c = annotation[0]
                cr, cc = self.board_to_canvas(r, c)
                x1 = cc * self.square_size;
                y1 = cr * self.square_size
                x2 = x1 + self.square_size;
                y2 = y1 + self.square_size
                self.canvas.create_oval(x1 + 3, y1 + 3, x2 - 3, y2 - 3,
                                        outline=CIRCLE_COLOR, width=4, tags="circle")
            elif len(annotation) == 2:
                start_sq, end_sq = annotation
                x_start, y_start = self._sq_center_coords(*start_sq)
                x_end, y_end = self._sq_center_coords(*end_sq)

                dx = x_end - x_start
                dy = y_end - y_start
                length = math.sqrt(dx ** 2 + dy ** 2)

                if length > 10:
                    reduction_factor = 1 - (10 / length)
                    x_end_adj = x_start + dx * reduction_factor
                    y_end_adj = y_start + dy * reduction_factor
                else:
                    x_end_adj, y_end_adj = x_end, y_end

                self.canvas.create_line(x_start, y_start, x_end_adj, y_end_adj,
                                        arrow='last', arrowshape=(10, 15, 5),
                                        width=8, fill=ARROW_COLOR, tags="arrow")

        for r in range(8):
            for c in range(8):
                piece = self.board.board[7 - r][c]
                if piece:
                    x = c * self.square_size + self.square_size // 2
                    y = r * self.square_size + self.square_size // 2
                    img = self.images.get(piece)
                    if img:
                        self.canvas.create_image(x, y, image=img, tags=(f"piece_{r}_{c}", "piece"))

        if self.selected:
            cr, cc = self.board_to_canvas(*self.selected)
            x1 = cc * self.square_size;
            y1 = cr * self.square_size
            self.canvas.create_rectangle(x1, y1, x1 + self.square_size, y1 + self.square_size, outline="lime green",
                                         width=3, tags="selection")

        for (tr, tc) in self.legal_targets:
            cr, cc = self.board_to_canvas(tr, tc)
            cx = cc * self.square_size + self.square_size // 2
            cy = cr * self.square_size + self.square_size // 2
            self.canvas.create_oval(cx - 10, cy - 10, cx + 10, cy + 10, fill="yellow", outline="")

        if self.board.king_in_check(self.board.turn):
            kp = self.board.find_king(self.board.turn)
            if kp:
                cr, cc = self.board_to_canvas(*kp)
                x1 = cc * self.square_size;
                y1 = cr * self.square_size
                self.canvas.create_rectangle(x1, y1, x1 + self.square_size, y1 + self.square_size, outline="red",
                                             width=4)

        st, winner = self.board.game_status()
        if st == 'checkmate':
            if not self.game_over:
                self.game_over = True
                winner_str = 'Les Blancs' if winner == WHITE else 'Les Noirs'
                self.status.config(text=f"Échec et mat — {winner_str} ont gagné.")
                messagebox.showinfo("Partie terminée", f"Échec et mat — {winner_str} ont gagné !")
        elif st == 'stalemate':
            self.status.config(text="Pat (nulle).")
        elif st == 'draw':
            self.status.config(text="Nulle (50 coups / répétition).")
        else:
            if self.board.king_in_check(self.board.turn):
                self.status.config(text=f"{'Blancs' if self.board.turn == WHITE else 'Noirs'} : roi en échec !")
            else:
                if self.started:
                    self.status.config(text=f"{'Blancs' if self.board.turn == WHITE else 'Noirs'} à jouer")
                else:
                    self.status.config(
                        text=f"Mode Analyse ({'Blancs' if self.board.turn == WHITE else 'Noirs'} à jouer)")

        self.refresh_captured_display()
        self.refresh_history()
        self.update_clock_labels()

        self.canvas.tag_raise("piece")

        # --- Logique de mouvement (Double-Clic) ---

    def on_click_move(self, event):
        """Gère la sélection et le mouvement des pièces (mode double-clic)."""
        if self.animating: return

        # Reprendre le jeu après analyse
        if len(self.board.history) != len(self.full_history_data):
            self.restore_position(len(self.full_history_data) - 1, animate=False)

        if not self.started and self.board.game_status()[0] == 'ongoing':
            self.started = True

        if self.game_over: return

        col = event.x // self.square_size
        row = event.y // self.square_size
        if not (0 <= col < 8 and 0 <= row < 8): return
        br, bc = self.canvas_to_board(row, col)
        piece = self.board.board[br][bc]

        if self.selected is None:
            if piece and self.board.piece_color(piece) == self.board.turn:
                self.selected = (br, bc)
                self.compute_legal_targets(br, bc)
                self.draw_board()
            else:
                return
        else:
            fr, fc = self.selected

            if piece and self.board.piece_color(piece) == self.board.turn:
                self.selected = (br, bc)
                self.compute_legal_targets(br, bc)
                self.draw_board()
                return

            end_sq = (br, bc)
            legal = self.board.generate_moves(legal=True)
            candidates = [m for m in legal if m.from_sq == self.selected and m.to_sq == end_sq]

            chosen_move = None
            promos = [m for m in candidates if m.promotion]

            if promos:
                prom = self.ask_promotion()
                if prom:
                    for m in promos:
                        if m.promotion and prom.lower() == m.promotion[0].lower():
                            chosen_move = m;
                            break
            elif candidates:
                chosen_move = candidates[0]

            if chosen_move:
                move_copy_for_history = copy.deepcopy(chosen_move)
                self.full_history_data.append(move_copy_for_history)
                self.board.push_move(chosen_move)

                captured_symbol = chosen_move.captured
                if captured_symbol:
                    mover_color = WHITE if chosen_move.piece.isupper() else BLACK
                    if mover_color == WHITE:
                        self.captured_by_white.append(captured_symbol)
                    else:
                        self.captured_by_black.append(captured_symbol)

                self.drawn_annotations = []
                self.history_widget.deselect_all_cells()
                self.selected = None
                self.legal_targets = []
                self.draw_board()
            else:
                self.selected = None
                self.legal_targets = []
                self.draw_board()

    # --- Logique d'Effacement Total (Clic Droit Seul) ---
    def on_right_click_clear(self, event):
        """Efface TOUTES les annotations (Cercles et Flèches)."""
        self.drawn_annotations = []
        self.draw_board()

    # --- Logique d'Annotation (Control + Clic Droit) ---
    def on_ctrl_click_start(self, event):
        """Débute le dessin de la flèche (Control + Clic Droit) ou prépare le cercle."""
        self.drawing_arrow = True
        start_sq = self._coords_to_square(event.x, event.y)
        self.arrow_start_sq = start_sq

        if self.current_arrow_id:
            self.canvas.delete(self.current_arrow_id)
            self.current_arrow_id = None

        self.draw_board()

    def on_ctrl_click_drag(self, event):
        """Met à jour le dessin de la flèche en cours (Control + Drag)."""
        if not self.drawing_arrow or not self.arrow_start_sq: return

        if self.current_arrow_id:
            self.canvas.delete(self.current_arrow_id)

        x_start, y_start = self._sq_center_coords(*self.arrow_start_sq)
        x_end, y_end = event.x, event.y

        self.current_arrow_id = self.canvas.create_line(
            x_start, y_start, x_end, y_end,
            arrow='last', arrowshape=(10, 15, 5),
            width=8, fill=ARROW_COLOR, tags="temp_arrow"
        )
        self.canvas.tag_raise("piece")

    def on_ctrl_click_release(self, event):
        """Termine l'annotation : Cercle (Control + Clic simple) ou Flèche (Control + Drag)."""
        if not self.drawing_arrow or self.arrow_start_sq is None: return

        if self.current_arrow_id:
            self.canvas.delete(self.current_arrow_id)
            self.current_arrow_id = None

        self.drawing_arrow = False
        end_sq = self._coords_to_square(event.x, event.y)

        if end_sq is None:
            self.arrow_start_sq = None
            self.draw_board()
            return

        start_coords = self._sq_center_coords(*self.arrow_start_sq)
        end_coords = (event.x, event.y)
        distance = math.dist(start_coords, end_coords)

        if distance < 10 or self.arrow_start_sq == end_sq:
            # --- Clic simple (Cercle) ---
            new_circle = (self.arrow_start_sq,)

            if new_circle in self.drawn_annotations:
                self.drawn_annotations.remove(new_circle)
            else:
                self.drawn_annotations.append(new_circle)

        elif self.arrow_start_sq != end_sq:
            # --- Drag (Flèche) ---
            new_arrow = (self.arrow_start_sq, end_sq)

            if new_arrow in self.drawn_annotations:
                self.drawn_annotations.remove(new_arrow)
            else:
                self.drawn_annotations.append(new_arrow)

        self.arrow_start_sq = None
        self.draw_board()

    # --- Reste du code ---
    def on_undo(self):
        if not self.board.history: return

        # Annuler du côté de l'historique complet
        if self.full_history_data:
            self.full_history_data.pop()

        if self.clock_history:
            white_s, black_s = self.clock_history.pop()
            self.time_left[WHITE] = white_s
            self.time_left[BLACK] = black_s

        last_move = self.board.history[-1][0] if self.board.history else None
        if last_move and last_move.captured:
            mover_color = WHITE if last_move.piece.isupper() else BLACK
            if mover_color == WHITE:
                if self.captured_by_white: self.captured_by_white.pop()
            else:
                if self.captured_by_black: self.captured_by_black.pop()

        self.board.undo_move()
        self.selected = None;
        self.legal_targets = []
        self.game_over = False
        self.history_widget.deselect_all_cells()
        self.draw_board()

    def on_new(self):
        self.board = Board()
        self.selected = None;
        self.legal_targets = []
        self.animating = False
        self.game_over = False
        self.started = False
        self.start_button.config(text="Commencer la partie")
        self.time_left = {WHITE: self.init_seconds, BLACK: self.init_seconds}
        self.clock_history = []
        self.captured_by_white = []
        self.captured_by_black = []
        self.drawn_annotations = []
        self.full_history_data = []
        self.draw_board()

    def compute_legal_targets(self, fr, fc):
        self.legal_targets = []
        for m in self.board.generate_moves(legal=True):
            if m.from_sq == (fr, fc):
                self.legal_targets.append(m.to_sq)

    def ask_promotion(self) -> Optional[str]:
        top = tk.Toplevel(self, bg=DARK_BG_PRIMARY)
        top.title("Promotion")
        top.resizable(False, False)
        result = {'val': None}

        def pick(v):
            result['val'] = v;
            top.destroy()

        tk.Label(top, text="Choisissez la promotion :", bg=DARK_BG_PRIMARY, fg=DARK_FG).pack(padx=8, pady=8)
        frame = tk.Frame(top, bg=DARK_BG_PRIMARY);
        frame.pack(padx=6, pady=6)

        ttk.Button(frame, text="Reine", width=8, command=lambda: pick('q'), style='Dark.TButton').pack(side='left',
                                                                                                       padx=4)
        ttk.Button(frame, text="Tour", width=8, command=lambda: pick('r'), style='Dark.TButton').pack(side='left',
                                                                                                      padx=4)
        ttk.Button(frame, text="Fou", width=8, command=lambda: pick('b'), style='Dark.TButton').pack(side='left',
                                                                                                     padx=4)
        ttk.Button(frame, text="Cavalier", width=8, command=lambda: pick('n'), style='Dark.TButton').pack(side='left',
                                                                                                          padx=4)
        self.wait_window(top)
        return result['val']

    def refresh_history(self):
        self.history_widget.clear()

        moves_source = self.full_history_data
        total_moves = len(moves_source)

        if not total_moves: return

        num_full_moves = total_moves // 2 + (total_moves % 2)

        for num in range(1, num_full_moves + 1):
            i_white = 2 * (num - 1)
            i_black = 2 * (num - 1) + 1

            wm = move_to_readable(moves_source[i_white]) if i_white < total_moves else ''
            bm = move_to_readable(moves_source[i_black]) if i_black < total_moves else ''

            if wm or bm:
                self.history_widget.add_row(num, wm, bm)

        self.history_widget.tree.yview_moveto(1.0)

    def refresh_captured_display(self):
        for child in self.white_capture_frame.winfo_children(): child.destroy()
        for child in self.black_capture_frame.winfo_children(): child.destroy()

        def group_and_show(container, captured_list: List[str], for_white: bool):
            counts = collections.Counter()
            for sym in captured_list: counts[sym.upper()] += 1
            for piece_type in GROUP_ORDER:
                cnt = counts.get(piece_type, 0)
                for _ in range(cnt):
                    key = piece_type.lower() if for_white else piece_type
                    img = self.small_images.get(key)
                    if img:
                        l = tk.Label(container, image=img, bg=DARK_BG_SECONDARY)
                        l.image = img
                        l.pack(side='left', padx=1)

        group_and_show(self.black_capture_frame, self.captured_by_black, for_white=False)
        group_and_show(self.white_capture_frame, self.captured_by_white, for_white=True)

    def set_time_dialog(self):
        val = simpledialog.askinteger("Param. temps", "Temps initial (minutes) :", initialvalue=self.init_seconds // 60,
                                      minvalue=1, maxvalue=180)
        if val is None: return
        self.init_seconds = int(val) * 60
        self.time_left = {WHITE: self.init_seconds, BLACK: self.init_seconds}
        self.clock_history = []
        self.update_clock_labels()

    def update_clock_labels(self):
        self.time_label_white.config(text=self._fmt_time(self.time_left[WHITE]))
        self.time_label_black.config(text=self._fmt_time(self.time_left[BLACK]))

        if self.started and not self.game_over:
            if self.board.turn == WHITE:
                self.white_timer_bg.config(bg=DARK_TIMER_ACTIVE)
                self.black_timer_bg.config(bg=DARK_TIMER_INACTIVE)
            else:
                self.white_timer_bg.config(bg=DARK_TIMER_INACTIVE)
                self.black_timer_bg.config(bg=DARK_TIMER_ACTIVE)
        elif not self.started or self.game_over:
            self.white_timer_bg.config(bg=DARK_TIMER_INACTIVE)
            self.black_timer_bg.config(bg=DARK_TIMER_INACTIVE)

    def _fmt_time(self, secs: int) -> str:
        if secs < 0: secs = 0
        m = secs // 60
        s = secs % 60
        return f"{m:02d}:{s:02d}"

    def on_start(self):
        if not self.started:
            self.started = True
            self.start_button.config(text="En cours")
            if self.time_left[WHITE] == 0 and self.time_left[BLACK] == 0:
                self.time_left = {WHITE: self.init_seconds, BLACK: self.init_seconds}
            self.update_clock_labels()

    def _tick(self):
        if self.started and not self.animating and not self.game_over:
            current = self.board.turn
            self.time_left[current] -= 1
            if self.time_left[current] <= 0:
                self.game_over = True
                winner = self.board._opponent(current)
                winner_str = 'Les Blancs' if winner == WHITE else 'Les Noirs'
                self.update_clock_labels()
                messagebox.showinfo("Temps écoulé", f"Temps écoulé — {winner_str} ont gagné !")
            self.update_clock_labels()
        self.after(1000, self._tick)


# ---------------- main ----------------
if __name__ == "__main__":
    app = ChessApp()
    app.mainloop()
