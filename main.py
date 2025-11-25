#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
main.py - Version STABLE FINALE V29 (Fix Init Variables)
- Correction de l'AttributeError 'is_flipped'.
- Toutes les variables de jeu (board, is_flipped, theme, etc.) sont initialisées AVANT
  la création de l'interface graphique pour éviter les crashs au dessin.
"""
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from dataclasses import dataclass
from typing import List, Optional, Tuple, Dict, Union
import copy, collections, math
import random
import socket
import threading
import traceback

# ---------------- CONSTANTES DE BASE ----------------
FILES = 'abcdefgh'
RANKS = '12345678'
WHITE = 'w'
BLACK = 'b'
PORT = 5000

# Images
IMAGE_MAP = {
    'P': "wP.png", 'R': "wR.png", 'N': "wN.png", 'B': "wB.png", 'Q': "wQ.png", 'K': "wK.png",
    'p': "bP.png", 'r': "bR.png", 'n': "bN.png", 'b': "bB.png", 'q': "bQ.png", 'k': "bK.png",
    'S': "eN.png"
}
GROUP_ORDER = ['P', 'N', 'B', 'R', 'Q', 'K']

# ---------------- THÈMES ----------------
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
        self.local_ip = "127.0.0.1"

        if self.is_host:
            try:
                self.socket.bind(('0.0.0.0', PORT))
                self.socket.listen(1)
                self.local_ip = socket.gethostbyname(socket.gethostname())
            except Exception as e:
                messagebox.showerror("Erreur Réseau", f"Impossible de démarrer le serveur: {e}")
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
        try:
            if self.conn: self.conn.close()
            if self.socket: self.socket.close()
        except:
            pass


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
        return f"{piece}{capture}{dest}{promo}"


# ---------------- Treeview History ----------------
class TreeviewHistory(tk.Frame):
    def __init__(self, master, app_instance, *args, **kwargs):
        super().__init__(master, *args, **kwargs)
        self.app = app_instance
        self.configure(bg=UI_BG_PRIMARY)

        style = ttk.Style(self)
        style.configure("Treeview", background=UI_BG_SECONDARY, foreground=UI_FG, fieldbackground=UI_BG_SECONDARY,
                        rowheight=25, font=('TkDefaultFont', 10))
        style.configure("Treeview.Heading", background=UI_BG_PRIMARY, foreground=UI_FG,
                        font=('TkDefaultFont', 10, 'bold'))

        self.tree = ttk.Treeview(self, columns=('White', 'Black'), show='headings', height=12)
        self.tree.configure(selectmode='browse')
        self.tree.heading('#0', text='No.', anchor='e')
        self.tree.heading('White', text='Blancs', anchor='center')
        self.tree.heading('Black', text='Noirs', anchor='center')

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
        for item in self.tree.get_children(): self.tree.delete(item)
        self.last_selected_cell = None

    def add_row(self, num: int, white_text: str, black_text: str):
        item_id = f"move_{num}"
        self.tree.insert('', 'end', text=f"{num}.", values=(white_text, black_text), iid=item_id)

    def deselect_all_cells(self):
        if self.last_selected_cell:
            item_id, column_id = self.last_selected_cell
            current_tags = self.tree.item(item_id, 'tags')
            new_tags = tuple(t for t in current_tags if not t.startswith("selected_#"))
            self.tree.item(item_id, tags=new_tags)
            self.last_selected_cell = None
        self.tree.selection_remove(self.tree.selection())

    def apply_cell_selection(self, item_id, col_id):
        self.deselect_all_cells()
        tag_name = f"selected_{col_id}"
        self.tree.tag_configure(tag_name, background=UI_CELL_HIGHLIGHT_BG, foreground=UI_FG)
        current_tags = self.tree.item(item_id, 'tags')
        new_tags = (*current_tags, tag_name)
        self.tree.item(item_id, tags=new_tags)
        self.last_selected_cell = (item_id, col_id)
        self.tree.see(item_id)

    def on_history_select(self, event):
        full_moves = self.app.full_history_data
        if not full_moves: self.deselect_all_cells(); return
        item_id = self.tree.identify_row(event.y)
        col_id = self.tree.identify_column(event.x)
        if not item_id or col_id == '#0': self.deselect_all_cells(); return
        try:
            move_num = int(self.tree.item(item_id, 'text').replace('.', '').strip())
        except ValueError:
            self.deselect_all_cells(); return
        target_index = 2 * (move_num - 1) if col_id == '#1' else 2 * (move_num - 1) + 1
        if target_index < 0: return
        if target_index >= len(full_moves): target_index = len(full_moves) - 1;
        if target_index < 0: return
        self.apply_cell_selection(item_id, col_id)
        self.app.restore_position(target_index, animate=True)
        self.app.info_tab.refresh_info()


# ---------------- Onglet Infos ----------------
class InfoTab(tk.Frame):
    def __init__(self, master, app_instance, *args, **kwargs):
        super().__init__(master, *args, **kwargs)
        self.app = app_instance
        self.configure(bg=UI_BG_SECONDARY)
        self.text_area = tk.Text(self, bg=UI_BG_SECONDARY, fg=UI_FG, font=('TkDefaultFont', 10), wrap=tk.WORD,
                                 height=12, width=45, borderwidth=0, relief='flat')
        self.text_area.pack(fill='both', expand=False, padx=5, pady=5)
        self.text_area.insert(tk.END, "Informations sur le jeu...")
        self.text_area.config(state=tk.DISABLED)

    def refresh_info(self):
        self.text_area.config(state=tk.NORMAL);
        self.text_area.delete(1.0, tk.END)
        if self.app.animating: self.text_area.insert(tk.END, "Animation..."); self.text_area.config(
            state=tk.DISABLED); return
        moves = self.app.board.generate_moves(legal=True)
        turn = "Blancs" if self.app.board.turn == WHITE else "Noirs"
        self.text_area.insert(tk.END, f"--- À jouer : {turn} ---\n\n")
        if not moves:
            st, _ = self.app.board.game_status()
            self.text_area.insert(tk.END, f"Partie terminée : {st.upper()}!\n")
            self.text_area.config(state=tk.DISABLED);
            return
        piece_moves = collections.defaultdict(list)
        for m in moves: piece_moves[m.piece.upper()].append(move_to_readable(m))
        self.text_area.insert(tk.END, f"Coups légaux ({len(moves)}) :\n")
        for p in GROUP_ORDER:
            if p in piece_moves: self.text_area.insert(tk.END, f"\n{p} : {', '.join(sorted(piece_moves[p]))}")
        self.text_area.config(state=tk.DISABLED)


# ---------------- Onglet Parties ----------------
class GamesTab(tk.Frame):
    def __init__(self, master, app_instance, *args, **kwargs):
        super().__init__(master, *args, **kwargs)
        self.app = app_instance
        self.configure(bg=UI_BG_SECONDARY)
        style = ttk.Style(self)
        style.configure("GamesList.Treeview", background=UI_BG_SECONDARY, foreground=UI_FG,
                        fieldbackground=UI_BG_SECONDARY, rowheight=25, font=('TkDefaultFont', 10))
        self.tree = ttk.Treeview(self, columns=('Name',), show='headings', height=12, style='GamesList.Treeview',
                                 selectmode='browse')
        self.tree.heading('Name', text='Parties Enregistrées', anchor='center')
        self.tree.column('Name', width=300, anchor='w', stretch=tk.YES)
        vsb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side='right', fill='y')
        self.tree.pack(side='left', fill='both', expand=True)
        self.tree.bind("<<TreeviewSelect>>", self.on_game_select)

    def refresh_list(self):
        for item in self.tree.get_children(): self.tree.delete(item)
        for idx, (name, history) in enumerate(self.app.saved_games):
            item_id = f"saved_game_{idx}"
            display = f"{name} ({len(history)} coups)" if history else f"{name} (Vide)"
            self.tree.insert('', 'end', text=name, values=(display,), iid=item_id)

    def on_game_select(self, event):
        sel = self.tree.selection()
        if not sel: return
        try:
            idx = int(sel[0].split('_')[-1])
        except:
            return
        if idx < len(self.app.saved_games):
            name, history = self.app.saved_games[idx]
            self.app.full_history_data = copy.deepcopy(history)
            target = len(history) - 1
            if target >= 0:
                self.app.restore_position(target, animate=False)
            else:
                self.app.on_new()
            self.app.started = False;
            self.app.game_over = False
            self.app.start_button.config(text="Commencer la partie")
            self.app.is_analyzing_saved_game = True
            self.app.tab_control.select(0)
            self.tree.selection_remove(sel[0])


# ---------------- Menu de Démarrage ----------------
class StartMenu(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Sélection du Mode de Jeu")
        self.resizable(False, False)
        self.configure(bg=UI_BG_PRIMARY)
        self.geometry("300x300")  # Hauteur augmentée

        self.mode = None
        self.network_config = None

        style = ttk.Style()
        style.theme_use("default")
        style.configure('Menu.TButton', background=UI_BG_SECONDARY, foreground=UI_FG,
                        font=('TkDefaultFont', 12, 'bold'), padding=[20, 10])
        style.map('Menu.TButton', background=[('active', '#413E3B')])

        main_frame = tk.Frame(self, bg=UI_BG_PRIMARY, padx=20, pady=20)
        main_frame.pack(expand=True, fill='both')

        tk.Label(main_frame, text="CHESS APP", font=('TkDefaultFont', 16, 'bold'),
                 bg=UI_BG_PRIMARY, fg=UI_FG, pady=10).pack()

        # Section LOCAL
        tk.Label(main_frame, text="Mode Local", font=('TkDefaultFont', 10, 'bold'),
                 bg=UI_BG_PRIMARY, fg=UI_FG, pady=5, anchor='w').pack(fill='x')

        ttk.Button(main_frame, text="Local (1 PC)", command=lambda: self.select_mode('human'),
                   style='Menu.TButton').pack(fill='x', pady=5)

        # Section RESEAU
        tk.Label(main_frame, text="Mode Réseau (LAN)", font=('TkDefaultFont', 10, 'bold'),
                 bg=UI_BG_PRIMARY, fg=UI_FG, anchor='w').pack(fill='x', pady=(15, 5))

        lan_frame = tk.Frame(main_frame, bg=UI_BG_PRIMARY)
        lan_frame.pack(fill='x')

        ttk.Button(lan_frame, text="Héberger", command=lambda: self.select_mode('lan', 'host'),
                   style='Menu.TButton').pack(side='left', expand=True, fill='x', padx=(0, 5))

        ttk.Button(lan_frame, text="Rejoindre", command=lambda: self.select_mode('lan', 'client'),
                   style='Menu.TButton').pack(side='right', expand=True, fill='x', padx=(5, 0))

        self.center_window()

    def center_window(self):
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f'{width}x{height}+{x}+{y}')

    def select_mode(self, mode, net_config=None):
        self.mode = mode
        self.network_config = net_config
        self.destroy()


# ---------------- ChessApp (Fenêtre Principale) ----------------
class ChessApp(tk.Tk):
    canvas_images: List[tk.PhotoImage] = []

    def __init__(self, mode: str, network_config=None):
        super().__init__()

        # 1. INITIALISATION DES VARIABLES EN PREMIER (FIX CRITIQUE ATTRIBUTE ERROR)
        self.game_mode = mode
        self.network_manager = None
        self.is_host = False
        self.is_analyzing_saved_game = False
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
        self.is_flipped = False
        self.current_theme = 'dark'
        self.drawn_annotations: List[Union[Tuple[Tuple[int, int]], Tuple[Tuple[int, int], Tuple[int, int]]]] = []
        self.images: Dict[str, tk.PhotoImage] = {}
        self.small_images: Dict[str, tk.PhotoImage] = {}

        # Config Réseau
        if self.game_mode == 'lan':
            self.is_host = (network_config == 'host')
            if self.is_host:
                try:
                    self.network_manager = NetworkManager(is_host=True)
                    self.after(100, lambda: messagebox.showinfo("Hébergement",
                                                                f"En attente de connexion...\nIP: {self.network_manager.local_ip}"))
                    threading.Thread(target=self._wait_for_connection, daemon=True).start()
                except:
                    pass
            else:
                target_ip = simpledialog.askstring("Connexion", "Entrez l'IP de l'hôte:")
                if target_ip:
                    self.network_manager = NetworkManager(is_host=False, ip=target_ip)
                    if self.network_manager.connect():
                        self.is_flipped = True
                        threading.Thread(target=self._listen_network, daemon=True).start()
                    else:
                        messagebox.showerror("Erreur", "Impossible de se connecter à l'hôte.")
                        self.destroy();
                        return
                else:
                    self.destroy();
                    return

        self.title(f"Échecs - {mode.upper()}")
        self.resizable(False, False)
        self.configure(bg=UI_BG_PRIMARY)

        # 2. LANCEMENT DE L'INITIALISATION DIFFÉRÉE
        self.after_idle(self._setup_widgets_safe)

    def _setup_widgets_safe(self):
        try:
            self._setup_widgets()
        except Exception as e:
            err = traceback.format_exc()
            messagebox.showerror("Erreur Critique", f"Erreur lors du chargement :\n\n{err}")
            self.destroy()

    def _wait_for_connection(self):
        if self.network_manager.connect():
            self.after(0, lambda: messagebox.showinfo("Info", "Client connecté !"))
            threading.Thread(target=self._listen_network, daemon=True).start()

    def _listen_network(self):
        while True:
            move_uci = self.network_manager.receive_move()
            if move_uci:
                self.after(0, lambda m=move_uci: self.apply_network_move(m))
            else:
                break

    def apply_network_move(self, uci: str):
        move = self.board.make_move_uci(uci)
        if move:
            self.full_history_data.append(copy.deepcopy(move))
            self.last_move_squares = move.from_sq, move.to_sq
            if move.captured:
                c = WHITE if move.piece.isupper() else BLACK
                if c == WHITE:
                    self.captured_by_white.append(move.captured)
                else:
                    self.captured_by_black.append(move.captured)

            self.draw_board()
            self.info_tab.refresh_info()
            if not self.started:
                self.started = True
                self.start_button.config(text="En cours")

    def _setup_widgets(self):
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

        self.timer_container = tk.Frame(self.side_frame, bg=UI_BG_PRIMARY)
        self.timer_container.pack(pady=(0, 10), padx=5, fill='x')
        self.black_timer_frame = self._create_timer_widget(BLACK)
        self.black_timer_frame.pack(fill='x', pady=(0, 5))
        self.white_timer_frame = self._create_timer_widget(WHITE)
        self.white_timer_frame.pack(fill='x', pady=(5, 0))

        control_frame = tk.Frame(self.side_frame, bg=UI_BG_PRIMARY)
        control_frame.pack(fill='x', pady=(10, 0))
        self.settings_img = self.images.get('S_icon')
        self.theme_btn = ttk.Button(control_frame, image=self.settings_img, command=self.open_settings_window,
                                    style='Dark.TButton', width=2)
        self.theme_btn.pack(side='right', padx=(5, 0))
        tk.Label(control_frame, text="Analyse", font=('TkDefaultFont', 11, 'bold'), bg=UI_BG_PRIMARY, fg=UI_FG).pack(
            side='right', padx=(10, 5))

        style.configure('TNotebook', background=UI_BG_PRIMARY, borderwidth=0)
        style.configure('TNotebook.Tab', background=UI_BG_SECONDARY, foreground=UI_FG, font=('TkDefaultFont', 11),
                        padding=[15, 5])
        style.map('TNotebook.Tab', background=[('selected', UI_BG_PRIMARY)], foreground=[('selected', UI_FG)])

        self.tab_control = ttk.Notebook(self.side_frame)
        self.tab_control.pack(fill='x', padx=5, pady=(5, 0))
        history_frame = tk.Frame(self.tab_control, bg=UI_BG_PRIMARY)
        self.history_widget = TreeviewHistory(history_frame, self, bg=UI_BG_PRIMARY)
        self.history_widget.pack(fill='both', expand=True)
        self.tab_control.add(history_frame, text="Coups")
        info_frame = tk.Frame(self.tab_control, bg=UI_BG_SECONDARY)
        self.info_tab = InfoTab(info_frame, self)
        self.info_tab.pack(fill='both', expand=True)
        self.tab_control.add(info_frame, text="Infos")
        games_frame = tk.Frame(self.tab_control, bg=UI_BG_SECONDARY)
        self.games_tab = GamesTab(games_frame, self)
        self.games_tab.pack(fill='both', expand=True)
        self.tab_control.add(games_frame, text="Parties")

        btn_frame = tk.Frame(self.side_frame, bg=UI_BG_PRIMARY)
        btn_frame.pack(pady=12, fill='x')
        ttk.Button(btn_frame, text="Annuler", command=self.on_undo, style='Dark.TButton').pack(side='left', padx=2,
                                                                                               fill='x', expand=True)
        ttk.Button(btn_frame, text="Nouvelle partie", command=self.on_new, style='Dark.TButton').pack(side='left',
                                                                                                      padx=2, fill='x',
                                                                                                      expand=True)

        self.status = tk.Label(self.board_frame, text="", anchor='w', bg=UI_BG_PRIMARY, fg=UI_FG, height=1,
                               font=('TkDefaultFont', 11))
        self.status.grid(row=0, column=0, sticky='we', pady=(0, 6), padx=4)
        self.canvas = tk.Canvas(self.board_frame, width=self.board_px, height=self.board_px, bg=UI_BG_PRIMARY,
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

        # Application directe du thème (Fix Compatibilité Python 3.14)
        global BOARD_LIGHT, BOARD_DARK, HIGHLIGHT_LAST_MOVE, HIGHLIGHT_SELECTED, HIGHLIGHT_TARGET
        BOARD_LIGHT = DARK_BOARD_LIGHT
        BOARD_DARK = DARK_BOARD_DARK
        HIGHLIGHT_LAST_MOVE = DARK_HIGHLIGHT_LAST_MOVE
        HIGHLIGHT_SELECTED = DARK_HIGHLIGHT_SELECTED
        HIGHLIGHT_TARGET = DARK_HIGHLIGHT_TARGET

        self.update_clock_labels()
        self.after(1000, self._tick)

        self.update_idletasks()
        self.draw_board()
        self.info_tab.refresh_info()

    def _load_images(self):
        self.images: Dict[str, tk.PhotoImage] = {}
        self.small_images: Dict[str, tk.PhotoImage] = {}
        target_icon_size = 24
        for key, filename in IMAGE_MAP.items():
            try:
                img_main = tk.PhotoImage(file=filename)
                self.images[key] = img_main
                if key != 'S':
                    img_small = img_main.subsample(2, 2)
                    self.small_images[key] = img_small
                else:
                    scale_x = img_main.width() // target_icon_size
                    scale_y = img_main.height() // target_icon_size
                    scale = max(1, scale_x, scale_y)
                    self.images['S_icon'] = img_main.subsample(scale, scale)
            except Exception as e:
                img_placeholder = tk.PhotoImage(width=target_icon_size, height=target_icon_size)
                self.images[key] = img_placeholder
                if key != 'S':
                    self.small_images[key] = img_placeholder
                else:
                    self.images['S_icon'] = img_placeholder

    def _create_timer_widget(self, color):
        frame = tk.Frame(self.timer_container, bg=UI_BG_SECONDARY, relief='flat', borderwidth=0, padx=8, pady=8)
        name_label = tk.Label(frame, text="Blanc" if color == WHITE else "Noir", bg=UI_BG_SECONDARY, fg=UI_FG,
                              font=('TkDefaultFont', 10, 'bold'))
        name_label.pack(side='left', padx=(0, 10))
        if color == WHITE:
            self.time_label_white = tk.Label(frame, text="05:00", font=('Courier', 20, 'bold'), bg=UI_TIMER_INACTIVE,
                                             fg=UI_FG, width=6, padx=5)
            self.time_label_white.pack(side='right', padx=(10, 0))
            self.white_timer_bg = self.time_label_white
        else:
            self.time_label_black = tk.Label(frame, text="05:00", font=('Courier', 20, 'bold'), bg=UI_TIMER_INACTIVE,
                                             fg=UI_FG, width=6, padx=5)
            self.time_label_black.pack(side='right', padx=(10, 0))
            self.black_timer_bg = self.time_label_black
        capture_frame = tk.Frame(frame, bg=UI_BG_SECONDARY)
        capture_frame.pack(side='right', expand=True, fill='x', padx=(0, 10))
        if color == WHITE:
            self.white_capture_frame = capture_frame
        else:
            self.black_capture_frame = capture_frame
        return frame

    # ... (Méthodes de jeu standards) ...
    def board_to_canvas(self, r, c):
        if self.is_flipped:
            return (r, 7 - c)
        else:
            return (7 - r, c)

    def canvas_to_board(self, canvas_r, canvas_c):
        if self.is_flipped:
            return (canvas_r, 7 - canvas_c)
        else:
            return (7 - canvas_r, canvas_c)

    def _sq_center_coords(self, r, c) -> Tuple[int, int]:
        cr, cc = self.board_to_canvas(r, c)
        x = cc * self.square_size + self.square_size // 2
        y = cr * self.square_size + self.square_size // 2
        return x, y

    def _coords_to_square(self, x, y) -> Optional[Tuple[int, int]]:
        if not (0 <= x < self.board_px and 0 <= y < self.board_px): return None
        cc = x // self.square_size
        cr = y // self.square_size
        return self.canvas_to_board(cr, cc)

    def draw_board(self):
        self.canvas.delete("all")
        ChessApp.canvas_images = []
        light, dark = BOARD_LIGHT, BOARD_DARK
        coord_color = '#333333' if BOARD_LIGHT == LIGHT_BOARD_LIGHT else UI_FG

        for row in range(8):
            for col in range(8):
                x1 = col * self.square_size;
                y1 = row * self.square_size
                color = light if (row + col) % 2 == 0 else dark
                self.canvas.create_rectangle(x1, y1, x1 + self.square_size, y1 + self.square_size, fill=color,
                                             outline=color)

        if self.last_move_squares:
            from_sq, to_sq = self.last_move_squares
            for sq in [from_sq, to_sq]:
                cr, cc = self.board_to_canvas(*sq)
                x1 = cc * self.square_size;
                y1 = cr * self.square_size
                self.canvas.create_rectangle(x1, y1, x1 + self.square_size, y1 + self.square_size,
                                             fill=HIGHLIGHT_LAST_MOVE, outline=HIGHLIGHT_LAST_MOVE,
                                             tags="last_move_highlight", stipple="gray50")

        for annotation in self.drawn_annotations:
            if len(annotation) == 1:
                r, c = annotation[0]
                cr, cc = self.board_to_canvas(r, c)
                x1 = cc * self.square_size;
                y1 = cr * self.square_size
                self.canvas.create_oval(x1 + 3, y1 + 3, x1 + self.square_size - 3, y1 + self.square_size - 3,
                                        outline=CIRCLE_COLOR, width=4)
            elif len(annotation) == 2:
                start_sq, end_sq = annotation
                x_s, y_s = self._sq_center_coords(*start_sq)
                x_e, y_e = self._sq_center_coords(*end_sq)
                self.canvas.create_line(x_s, y_s, x_e, y_e, arrow='last', arrowshape=(10, 15, 5), width=8,
                                        fill=ARROW_COLOR)

        for r in range(8):
            for c in range(8):
                piece = self.board.board[r][c]
                if piece:
                    cr, cc = self.board_to_canvas(r, c)
                    x = cc * self.square_size + self.square_size // 2
                    y = cr * self.square_size + self.square_size // 2
                    img = self.images.get(piece)
                    if img:
                        ChessApp.canvas_images.append(img)
                        self.canvas.create_image(x, y, image=img, tags="piece")

        if self.selected:
            cr, cc = self.board_to_canvas(*self.selected)
            x1 = cc * self.square_size;
            y1 = cr * self.square_size
            self.canvas.create_rectangle(x1, y1, x1 + self.square_size, y1 + self.square_size,
                                         outline=HIGHLIGHT_SELECTED, width=3)
            for (tr, tc) in self.legal_targets:
                cr, cc = self.board_to_canvas(tr, tc)
                cx = cc * self.square_size + self.square_size // 2
                cy = cr * self.square_size + self.square_size // 2
                self.canvas.create_oval(cx - 10, cy - 10, cx + 10, cy + 10, fill=HIGHLIGHT_TARGET, outline="")

        if self.board.king_in_check(self.board.turn):
            kp = self.board.find_king(self.board.turn)
            if kp:
                cr, cc = self.board_to_canvas(*kp)
                x1 = cc * self.square_size;
                y1 = cr * self.square_size
                self.canvas.create_rectangle(x1, y1, x1 + self.square_size, y1 + self.square_size, outline="red",
                                             width=4)

        offset = 5
        ranks_display = RANKS if self.is_flipped else RANKS[::-1]
        files_display = FILES[::-1] if self.is_flipped else FILES
        for i in range(8):
            self.canvas.create_text(offset, i * self.square_size + offset, anchor='nw', text=ranks_display[i],
                                    fill=coord_color, font=('Arial', 9))
            text_x = i * self.square_size + self.square_size - offset if self.is_flipped else (
                                                                                                          7 - i) * self.square_size + self.square_size - offset
            self.canvas.create_text(text_x, self.board_px - offset, anchor='se', text=files_display[i],
                                    fill=coord_color, font=('Arial', 9))

        st, winner = self.board.game_status()

        # Gestion du texte de statut et sauvegarde
        status_text = ""
        if st == 'checkmate':
            if not self.game_over:
                self.game_over = True
                self.start_button.config(text="Partie terminée")
                if not self.is_analyzing_saved_game: self.save_game(st)
                winner_str = 'Les Blancs' if winner == WHITE else 'Les Noirs'
                messagebox.showinfo("Fin", f"Échec et mat ! {winner_str} gagnent.")
            status_text = f"Mat ! {winner}"
        elif st in ('stalemate', 'draw'):
            if not self.game_over:
                self.game_over = True
                self.start_button.config(text="Partie terminée")
                if not self.is_analyzing_saved_game: self.save_game(st)
            status_text = "Nulle"
        else:
            if self.board.king_in_check(self.board.turn):
                status_text = "Echec !"
            else:
                status_text = f"Trait aux {'Blancs' if self.board.turn == WHITE else 'Noirs'}"

        if self.game_mode == 'lan':
            status_text += " (LAN)"

        self.status.config(text=status_text)

        self.refresh_captured_display()
        self.refresh_history()
        self.update_clock_labels()
        self.info_tab.refresh_info()
        self.canvas.tag_raise("piece")

    def on_click_move(self, event):
        if self.animating: return

        # En mode LAN, vérifier si c'est mon tour
        if self.game_mode == 'lan':
            if self.network_manager.is_host and self.board.turn == BLACK: return
            if not self.network_manager.is_host and self.board.turn == WHITE: return

        if len(self.board.history) != len(self.full_history_data) and len(self.full_history_data) > 0:
            self.restore_position(len(self.full_history_data) - 1, animate=False)

        if not self.started and self.board.game_status()[0] == 'ongoing':
            self.started = True
            # Quand on commence à jouer, on n'est plus en mode analyse d'une partie sauvegardée
            self.is_analyzing_saved_game = False

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
                move_copy = copy.deepcopy(chosen_move)
                self.full_history_data.append(move_copy)
                self.board.push_move(chosen_move)
                self.last_move_squares = (fr, fc), (br, bc)
                if chosen_move.captured:
                    c = WHITE if chosen_move.piece.isupper() else BLACK
                    if c == WHITE:
                        self.captured_by_white.append(chosen_move.captured)
                    else:
                        self.captured_by_black.append(chosen_move.captured)

                # Envoi Réseau
                if self.game_mode == 'lan':
                    self.network_manager.send_move(chosen_move.uci())

                self.drawn_annotations = []
                self.history_widget.deselect_all_cells()
                self.selected = None
                self.legal_targets = []
                self.draw_board()
            else:
                self.selected = None
                self.legal_targets = []
                self.draw_board()

    def on_right_click_clear(self, event):
        self.drawn_annotations = []
        self.draw_board()

    def on_ctrl_click_start(self, event):
        self.drawing_arrow = True
        self.arrow_start_sq = self._coords_to_square(event.x, event.y)
        if self.current_arrow_id: self.canvas.delete(self.current_arrow_id); self.current_arrow_id = None
        self.draw_board()

    def on_ctrl_click_drag(self, event):
        if not self.drawing_arrow or not self.arrow_start_sq: return
        if self.current_arrow_id: self.canvas.delete(self.current_arrow_id)
        x_s, y_s = self._sq_center_coords(*self.arrow_start_sq)
        self.current_arrow_id = self.canvas.create_line(x_s, y_s, event.x, event.y, arrow='last',
                                                        arrowshape=(10, 15, 5), width=8, fill=ARROW_COLOR,
                                                        tags="temp_arrow")
        self.canvas.tag_raise("piece")

    def on_ctrl_click_release(self, event):
        if not self.drawing_arrow or not self.arrow_start_sq: return
        if self.current_arrow_id: self.canvas.delete(self.current_arrow_id); self.current_arrow_id = None
        self.drawing_arrow = False
        end_sq = self._coords_to_square(event.x, event.y)
        if not end_sq: self.arrow_start_sq = None; self.draw_board(); return

        start_coords = self._sq_center_coords(*self.arrow_start_sq)
        if math.dist(start_coords, (event.x, event.y)) < 10 or self.arrow_start_sq == end_sq:
            new_circle = (self.arrow_start_sq,)
            if new_circle in self.drawn_annotations:
                self.drawn_annotations.remove(new_circle)
            else:
                self.drawn_annotations.append(new_circle)
        elif self.arrow_start_sq != end_sq:
            new_arrow = (self.arrow_start_sq, end_sq)
            if new_arrow in self.drawn_annotations:
                self.drawn_annotations.remove(new_arrow)
            else:
                self.drawn_annotations.append(new_arrow)
        self.arrow_start_sq = None
        self.draw_board()

    def save_game(self, status: str):
        if not self.full_history_data: return
        game_name = f"Partie {len(self.saved_games) + 1} ({status.capitalize()})"
        self.saved_games.append((game_name, copy.deepcopy(self.full_history_data)))
        self.games_tab.refresh_list()

    def on_undo(self):
        if not self.board.history: return
        if self.full_history_data: self.full_history_data.pop()
        if self.clock_history:
            w, b = self.clock_history.pop()
            self.time_left[WHITE] = w;
            self.time_left[BLACK] = b

        last = self.board.history[-1][0] if self.board.history else None
        if last and last.captured:
            c = WHITE if last.piece.isupper() else BLACK
            if c == WHITE:
                if self.captured_by_white: self.captured_by_white.pop()
            else:
                if self.captured_by_black: self.captured_by_black.pop()

        self.board.undo_move()
        self.last_move_squares = self._get_last_move_from_history()
        self.selected = None;
        self.legal_targets = [];
        self.game_over = False
        self.is_analyzing_saved_game = False
        self.start_button.config(text="Commencer la partie")
        self.history_widget.deselect_all_cells()
        self.draw_board()
        self.info_tab.refresh_info()

    def on_new(self):
        # FIX CRITIQUE DOUBLON : Ne pas sauvegarder si on analyse une partie déjà finie
        is_finished = self.board.game_status()[0] != 'ongoing'
        if self.full_history_data and not is_finished and not self.is_analyzing_saved_game:
            self.save_game("Abandon")

        self.board = Board()
        self.selected = None
        self.legal_targets = []
        self.animating = False
        self.game_over = False
        self.started = False
        self.is_analyzing_saved_game = False
        self.start_button.config(text="Commencer la partie")
        self.time_left = {WHITE: self.init_seconds, BLACK: self.init_seconds}
        self.clock_history = []
        self.captured_by_white = []
        self.captured_by_black = []
        self.drawn_annotations = []
        self.full_history_data = []
        self.last_move_squares = None
        self.draw_board()
        self.info_tab.refresh_info()
        self.games_tab.refresh_list()

    def compute_legal_targets(self, fr, fc):
        self.legal_targets = []
        for m in self.board.generate_moves(legal=True):
            if m.from_sq == (fr, fc): self.legal_targets.append(m.to_sq)

    def ask_promotion(self):
        top = tk.Toplevel(self, bg=UI_BG_PRIMARY);
        top.title("Promotion")
        res = {'val': None}

        def pick(v): res['val'] = v; top.destroy()

        tk.Label(top, text="Promotion:", bg=UI_BG_PRIMARY, fg=UI_FG).pack()
        f = tk.Frame(top, bg=UI_BG_PRIMARY);
        f.pack()
        for p in ['q', 'r', 'b', 'n']:
            ttk.Button(f, text=p.upper(), width=5, command=lambda x=p: pick(x), style='Dark.TButton').pack(side='left')
        self.wait_window(top)
        return res['val']

    def refresh_history(self):
        self.history_widget.clear()
        moves = self.full_history_data
        if not moves: return
        count = len(moves)
        n_rows = count // 2 + (count % 2)
        for i in range(n_rows):
            wm = move_to_readable(moves[i * 2]) if i * 2 < count else ""
            bm = move_to_readable(moves[i * 2 + 1]) if i * 2 + 1 < count else ""
            self.history_widget.add_row(i + 1, wm, bm)
        self.history_widget.tree.yview_moveto(1.0)

    def refresh_captured_display(self):
        for c in self.white_capture_frame.winfo_children(): c.destroy()
        for c in self.black_capture_frame.winfo_children(): c.destroy()

        def show(frame, lst, w):
            cnt = collections.Counter([p.upper() for p in lst])
            for p in GROUP_ORDER:
                for _ in range(cnt.get(p, 0)):
                    key = p.lower() if w else p
                    if self.small_images.get(key):
                        tk.Label(frame, image=self.small_images[key], bg=UI_BG_SECONDARY).pack(side='left', padx=1)

        show(self.white_capture_frame, self.captured_by_white, True)
        show(self.black_capture_frame, self.captured_by_black, False)

    def _set_time_dialog(self, parent):
        val = simpledialog.askinteger("Temps", "Minutes:", initialvalue=5, minvalue=1, parent=parent)
        if val:
            self.init_seconds = val * 60
            self.on_new()

    def update_clock_labels(self):
        self.time_label_white.config(text=self._fmt_time(self.time_left[WHITE]))
        self.time_label_black.config(text=self._fmt_time(self.time_left[BLACK]))
        # Couleurs actives/inactives
        if self.started and not self.game_over:
            if self.board.turn == WHITE:
                self.white_timer_bg.config(bg=UI_TIMER_ACTIVE)
                self.black_timer_bg.config(bg=UI_TIMER_INACTIVE)
            else:
                self.white_timer_bg.config(bg=UI_TIMER_INACTIVE)
                self.black_timer_bg.config(bg=UI_TIMER_ACTIVE)
        else:
            self.white_timer_bg.config(bg=UI_TIMER_INACTIVE)
            self.black_timer_bg.config(bg=UI_TIMER_INACTIVE)

    def _fmt_time(self, s):
        return f"{s // 60:02d}:{s % 60:02d}"

    def on_start(self):
        if not self.started: self.started = True; self.start_button.config(text="En cours")

    def _tick(self):
        if self.started and not self.animating and not self.game_over:
            self.time_left[self.board.turn] -= 1
            if self.time_left[self.board.turn] <= 0:
                self.game_over = True
                self.start_button.config(text="Temps écoulé")
                if not self.is_analyzing_saved_game: self.save_game("Temps")
                messagebox.showinfo("Fin", "Temps écoulé !")
            self.update_clock_labels()
        self.after(1000, self._tick)

    def toggle_theme(self, theme):
        self.current_theme = theme
        self.apply_theme_colors(theme)
        self.draw_board()

    # Pour garder compatibilité avec le bouton, on garde la méthode mais on l'inline dans l'init
    def apply_theme_colors(self, theme_name):
        global BOARD_LIGHT, BOARD_DARK, HIGHLIGHT_LAST_MOVE, HIGHLIGHT_SELECTED, HIGHLIGHT_TARGET
        if theme_name == 'dark':
            BOARD_LIGHT = DARK_BOARD_LIGHT
            BOARD_DARK = DARK_BOARD_DARK
            HIGHLIGHT_LAST_MOVE = DARK_HIGHLIGHT_LAST_MOVE
            HIGHLIGHT_SELECTED = DARK_HIGHLIGHT_SELECTED
            HIGHLIGHT_TARGET = DARK_HIGHLIGHT_TARGET
        else:
            BOARD_LIGHT = LIGHT_BOARD_LIGHT
            BOARD_DARK = LIGHT_BOARD_DARK
            HIGHLIGHT_LAST_MOVE = LIGHT_HIGHLIGHT_LAST_MOVE
            HIGHLIGHT_SELECTED = LIGHT_HIGHLIGHT_SELECTED
            HIGHLIGHT_TARGET = LIGHT_HIGHLIGHT_TARGET

        # Mise à jour timer
        for frame in [self.black_timer_frame, self.white_timer_frame]:
            frame.config(bg=UI_BG_SECONDARY)
            for widget in frame.winfo_children():
                if isinstance(widget, tk.Label): widget.config(bg=UI_BG_SECONDARY, fg=UI_FG)

    def flip_board(self):
        self.is_flipped = not self.is_flipped
        self.draw_board()

    def open_settings_window(self):
        top = tk.Toplevel(self, bg=UI_BG_PRIMARY)
        tk.Label(top, text="Paramètres", bg=UI_BG_PRIMARY, fg=UI_FG).pack(pady=10)
        ttk.Button(top, text="Sombre", command=lambda: self.toggle_theme('dark'), style='Dark.TButton').pack(pady=5)
        ttk.Button(top, text="Clair", command=lambda: self.toggle_theme('light'), style='Dark.TButton').pack(pady=5)
        ttk.Button(top, text="Retourner", command=self.flip_board, style='Dark.TButton').pack(pady=5)
        ttk.Button(top, text="Temps", command=lambda: self._set_time_dialog(top), style='Dark.TButton').pack(pady=5)


# ---------------- main ----------------
if __name__ == "__main__":
    menu = StartMenu()
    menu.mainloop()

    if menu.mode:
        app = ChessApp(mode=menu.mode, network_config=menu.network_config)
        app.mainloop()