import chess

from engine.evaluation.constants.piece_square_tables import PHASE_INC, OPENING_PST, ENDGAME_PST


class StockfishLikeEvaluator:
    """
    Bộ lượng giá theo phong cách Stockfish đơn giản hóa.

    Cốt lõi là tapered PST, sau đó cộng thêm các term phổ biến:
    - bishop pair
    - rook on open / semi-open file
    - passed pawn / candidate passer
    - pawn majority
    - mobility
    - king safety cơ bản
    """

    BISHOP_PAIR_BONUS = 30
    ROOK_OPEN_FILE_BONUS = 18
    ROOK_SEMI_OPEN_FILE_BONUS = 10
    ROOK_7TH_RANK_BONUS = 12
    PASSED_PAWN_BASE = 18
    MOBILITY_WEIGHT = {
        chess.KNIGHT: 4,
        chess.BISHOP: 4,
        chess.ROOK: 2,
        chess.QUEEN: 1,
    }
    KING_RING_BONUS = 3
    CASTLED_KING_BONUS = 18
    UNCASTLED_KING_PENALTY = 8
    PAWN_MAJORITY_BONUS = 6

    def evaluate(self, board: chess.Board) -> int:
        opening_score = 0
        endgame_score = 0
        phase = 0

        for piece_type in range(1, 7):
            phase_weight = PHASE_INC[piece_type]
            opening_table = OPENING_PST[piece_type]
            endgame_table = ENDGAME_PST[piece_type]

            for square in board.pieces(piece_type, chess.WHITE):
                opening_score += opening_table[square]
                endgame_score += endgame_table[square]
                phase += phase_weight

            for square in board.pieces(piece_type, chess.BLACK):
                flipped_square = square ^ 56
                opening_score -= opening_table[flipped_square]
                endgame_score -= endgame_table[flipped_square]
                phase += phase_weight

        opening_phase = min(phase, 24)
        endgame_phase = 24 - opening_phase
        score = (opening_score * opening_phase + endgame_score * endgame_phase) // 24

        score += self._bishop_pair_bonus(board)
        score += self._rook_file_bonus(board)
        score += self._passed_pawn_bonus(board)
        score += self._pawn_majority_bonus(board)
        score += self._mobility_bonus(board)
        score += self._king_safety_bonus(board, opening_phase, endgame_phase)

        if board.turn == chess.BLACK:
            return -score

        return score

    def _bishop_pair_bonus(self, board: chess.Board) -> int:
        score = 0
        if len(board.pieces(chess.BISHOP, chess.WHITE)) >= 2:
            score += self.BISHOP_PAIR_BONUS
        if len(board.pieces(chess.BISHOP, chess.BLACK)) >= 2:
            score -= self.BISHOP_PAIR_BONUS
        return score

    def _rook_file_bonus(self, board: chess.Board) -> int:
        score = 0
        white_pawns = board.pieces(chess.PAWN, chess.WHITE)
        black_pawns = board.pieces(chess.PAWN, chess.BLACK)

        for square in board.pieces(chess.ROOK, chess.WHITE):
            file_index = chess.square_file(square)
            friendly_on_file = any(chess.square_file(pawn_square) == file_index for pawn_square in white_pawns)
            enemy_on_file = any(chess.square_file(pawn_square) == file_index for pawn_square in black_pawns)

            if not friendly_on_file and not enemy_on_file:
                score += self.ROOK_OPEN_FILE_BONUS
            elif not friendly_on_file and enemy_on_file:
                score += self.ROOK_SEMI_OPEN_FILE_BONUS

            if chess.square_rank(square) == 6:
                score += self.ROOK_7TH_RANK_BONUS

        for square in board.pieces(chess.ROOK, chess.BLACK):
            file_index = chess.square_file(square)
            friendly_on_file = any(chess.square_file(pawn_square) == file_index for pawn_square in black_pawns)
            enemy_on_file = any(chess.square_file(pawn_square) == file_index for pawn_square in white_pawns)

            if not friendly_on_file and not enemy_on_file:
                score -= self.ROOK_OPEN_FILE_BONUS
            elif not friendly_on_file and enemy_on_file:
                score -= self.ROOK_SEMI_OPEN_FILE_BONUS

            if chess.square_rank(square) == 1:
                score -= self.ROOK_7TH_RANK_BONUS

        return score

    def _passed_pawn_bonus(self, board: chess.Board) -> int:
        score = 0

        for square in board.pieces(chess.PAWN, chess.WHITE):
            bonus = self._single_passed_pawn_bonus(board, square, chess.WHITE)
            score += bonus

        for square in board.pieces(chess.PAWN, chess.BLACK):
            bonus = self._single_passed_pawn_bonus(board, square, chess.BLACK)
            score -= bonus

        return score

    def _single_passed_pawn_bonus(self, board: chess.Board, square: chess.Square, color: chess.Color) -> int:
        if not self._is_passed_pawn(board, square, color):
            return 0

        rank = chess.square_rank(square)
        advance = rank if color == chess.WHITE else 7 - rank
        bonus = self.PASSED_PAWN_BASE + advance * 4

        forward_square = square + 8 if color == chess.WHITE else square - 8
        if 0 <= forward_square < 64 and board.piece_at(forward_square) is not None:
            bonus //= 2

        return bonus

    def _is_passed_pawn(self, board: chess.Board, square: chess.Square, color: chess.Color) -> bool:
        enemy_pawns = board.pieces(chess.PAWN, not color)
        file_index = chess.square_file(square)
        rank_index = chess.square_rank(square)

        for enemy_square in enemy_pawns:
            enemy_file = chess.square_file(enemy_square)
            if abs(enemy_file - file_index) > 1:
                continue

            enemy_rank = chess.square_rank(enemy_square)
            if color == chess.WHITE and enemy_rank > rank_index:
                return False
            if color == chess.BLACK and enemy_rank < rank_index:
                return False

        return True

    def _pawn_majority_bonus(self, board: chess.Board) -> int:
        score = 0
        white_files = self._pawn_files(board, chess.WHITE)
        black_files = self._pawn_files(board, chess.BLACK)

        white_queen_side = white_files[0] + white_files[1] + white_files[2] + white_files[3]
        white_king_side = white_files[4] + white_files[5] + white_files[6] + white_files[7]
        black_queen_side = black_files[0] + black_files[1] + black_files[2] + black_files[3]
        black_king_side = black_files[4] + black_files[5] + black_files[6] + black_files[7]

        score += self._wing_majority_score(white_queen_side, black_queen_side)
        score += self._wing_majority_score(white_king_side, black_king_side)

        return score

    def _pawn_files(self, board: chess.Board, color: chess.Color) -> list[int]:
        files = [0] * 8
        for square in board.pieces(chess.PAWN, color):
            files[chess.square_file(square)] += 1
        return files

    def _wing_majority_score(self, white_count: int, black_count: int) -> int:
        if white_count == black_count:
            return 0
        if white_count > black_count:
            return (white_count - black_count) * self.PAWN_MAJORITY_BONUS
        return -(black_count - white_count) * self.PAWN_MAJORITY_BONUS

    def _mobility_bonus(self, board: chess.Board) -> int:
        score = 0
        white_occupied = board.occupied_co[chess.WHITE]
        black_occupied = board.occupied_co[chess.BLACK]

        for piece_type, weight in self.MOBILITY_WEIGHT.items():
            for square in board.pieces(piece_type, chess.WHITE):
                mobility_squares = board.attacks(square) & ~white_occupied
                mobility = len(mobility_squares)
                score += mobility * weight

            for square in board.pieces(piece_type, chess.BLACK):
                mobility_squares = board.attacks(square) & ~black_occupied
                mobility = len(mobility_squares)
                score -= mobility * weight

        return score

    def _king_safety_bonus(self, board: chess.Board, opening_phase: int, endgame_phase: int) -> int:
        score = 0
        opening_scale = max(1, opening_phase)
        endgame_scale = max(1, endgame_phase)

        score += self._single_king_safety(board, chess.WHITE, opening_scale, endgame_scale)
        score -= self._single_king_safety(board, chess.BLACK, opening_scale, endgame_scale)

        return score

    def _single_king_safety(
        self,
        board: chess.Board,
        color: chess.Color,
        opening_scale: int,
        endgame_scale: int,
    ) -> int:
        king_square = board.king(color)
        if king_square is None:
            return 0

        rank = chess.square_rank(king_square)
        file_index = chess.square_file(king_square)

        score = 0
        if color == chess.WHITE:
            if king_square in (chess.G1, chess.C1):
                score += self.CASTLED_KING_BONUS * opening_scale // 24
            else:
                score -= self.UNCASTLED_KING_PENALTY * opening_scale // 24

            if rank >= 4 and 2 <= file_index <= 5:
                score += self.KING_RING_BONUS * endgame_scale // 24
        else:
            if king_square in (chess.G8, chess.C8):
                score += self.CASTLED_KING_BONUS * opening_scale // 24
            else:
                score -= self.UNCASTLED_KING_PENALTY * opening_scale // 24

            if rank <= 3 and 2 <= file_index <= 5:
                score += self.KING_RING_BONUS * endgame_scale // 24

        enemy_color = not color
        king_ring = chess.BB_KING_ATTACKS[king_square] | chess.BB_SQUARES[king_square]
        attack_count = 0
        for ring_square in chess.SquareSet(king_ring):
            attack_count += board.is_attacked_by(enemy_color, ring_square)

        if attack_count:
            score -= attack_count * 2

        return score