import chess
from engine.evaluation.constants.piece_values import PIECE_VALUES

def material(board):
    score = 0

    for piece_type, value in PIECE_VALUES.items():
        score += len(board.pieces(piece_type, chess.WHITE)) * value 
        score -= len(board.pieces(piece_type, chess.BLACK)) * value 
    
    return score