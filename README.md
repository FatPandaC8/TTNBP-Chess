A modular, high-performance Python chess engine built with clean architecture principles. TTNBP-Chess combines advanced search algorithms, sophisticated position evaluation, and UCI protocol support for seamless integration with chess GUI applications.

---

## 🎯 Features

- **UCI Protocol Support**: Full UCI protocol implementation for compatibility with popular chess GUIs (Chess.com, Lichess, Arena, etc.)
- **Advanced Search Algorithms**:
  - Alpha-Beta Pruning with Move Ordering
  - Transposition Tables (TT) for caching positions
  - Lazy SMP (Shared Memory Parallel) for multi-core processing
  - Time Management and Depth Control
  
- **Sophisticated Evaluation**:
  - Tapered Evaluation (Opening/Endgame transition)
  - Piece-Square Tables (PST) for positional assessment
  - Material Value Calculation
  - Hanging Piece Detection and Penalties
  
- **Modular Architecture**: Clean separation of concerns makes it easy to extend and customize:
  - Board logic and move generation
  - Search algorithms and heuristics
  - Evaluation functions
  - Protocol handlers

- **Logging & Analysis**: Comprehensive game logging for move analysis, search statistics, and performance benchmarking

---

## 📋 Project Structure

```
src/engine/
├── agents/              # Agent interface and AI player implementations
├── board/               # Board representation and move utilities
├── cache/               # Transposition tables and caching mechanisms
├── evaluation/          # Position evaluation engines
│   ├── constants/       # Piece values, square tables, phase weights
│   └── eval.py          # Tapered evaluation with PST
├── game/                # Game runners and match orchestration
├── protocols/           # UCI and external protocol handlers
├── search/              # Search algorithms and enhancements
│   ├── algorithms/      # Core search implementations
│   │   ├── search.py    # Standard Alpha-Beta search
│   │   └── member_name/        # Each member has their own implementation of search
│   ├── heuristics/      # Search heuristics (hanging pieces, etc.)
│   └── interface.py     # Search algorithm base interface
├── utils/               # Shared utilities
│   ├── logger.py        # Async logging with JSON output
│   ├── config_loader.py # YAML configuration management
│   ├── decorators.py    # Performance timing utilities
│   └── tactics.py       # Tactical evaluation helpers
└── uci.py               # Main UCI entry point
```

---

## 🚀 Quick Start

### Prerequisites

- Python 3.8+
- Docker & Docker Compose (recommended)

### Installation

#### Using Docker (Recommended)

Build the Docker image:
```bash
make build
```

Run the engine:
```bash
make run
```

#### Local Installation

1. Clone the repository:
```bash
git clone https://github.com/FatPandaC8/TTNBP-Chess.git
cd TTNBP-Chess
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Run the UCI engine:
```bash
python -m src.engine.uci
```

---

## 📚 Usage

### UCI Protocol

Once running, the engine accepts standard UCI commands:

```
uci                          # Identify the engine
isready                      # Check if engine is ready
position startpos moves ...  # Set board position
go depth 20                  # Search to depth 20
go movetime 5000             # Search for 5 seconds
quit                         # Exit
```

### Programmatic Usage

```python
from engine.agents.interface import Agent
from engine.evaluation.eval import Evaluator
from engine.search.algorithms.search import Searcher
import chess

# Create evaluator and searcher
evaluator = Evaluator()
searcher = Searcher(evaluator=evaluator)

# Build agent with builder pattern
agent = Agent(id="my-engine", time_limit=5.0)
agent.with_search(searcher)
agent.with_depth(12)

# Get best move
board = chess.Board()
best_move = agent.get_move(board)
print(f"Best move: {best_move}")
```

---

## ⚙️ Configuration

Configuration files are stored in YAML format in the `config/` directory:

```
config/
├── evaluation/
│   └── config.yml
├── search/
│   └── config.yml
└── ...
```

Load configurations programmatically:

```python
from engine.utils.config_loader import load_config

config = load_config("evaluation/config.yml")
```

---

## 🧠 Core Components

### Evaluation Engine

The `Evaluator` class implements tapered evaluation:
- **Opening Score**: Optimized for active piece play and control
- **Endgame Score**: Emphasizes piece safety and king activity
- **Interpolation**: Smooth transition between phases using piece count

Features:
- Piece-square table lookup (64 squares × 6 piece types)
- Material value calculation
- Phase detection for opening/endgame

### Search Algorithms

#### Standard Alpha-Beta Search
- Depth-first minimax with alpha-beta pruning
- Move ordering optimizations
- Transposition table pruning

#### TT Warming (Shared Memory Parallel)
- Multi-threaded search on shared board state
- Distributed transposition table merging
- Configurable worker count

### Move Generation & Board Logic

Built on `python-chess` library:
- Legal move generation
- FEN/PGN support
- Board state utilities

---

## 🔧 Extending the Engine

### Adding Custom Evaluation Functions

1. Create a new file in `src/engine/evaluation/`:
```python
# src/engine/evaluation/my_eval.py
import chess

class MyEvaluator:
    def evaluate(self, board: chess.Board) -> int:
        # Your evaluation logic
        return score
```

2. Use it in your agent:
```python
from engine.evaluation.my_eval import MyEvaluator
agent.with_search(Searcher(evaluator=MyEvaluator()))
```

### Adding Search Heuristics

1. Add heuristics in `src/engine/search/heuristics/`:
```python
# src/engine/search/heuristics/my_heuristic.py
def my_heuristic(board, move):
    return heuristic_score
```

### Adding Move Ordering Techniques

1. Extend `src/engine/search/ordering/` with new strategies:
```python
def sort_moves_custom(board, moves):
    # Your custom move ordering
    return sorted_moves
```

---

## 📊 Performance & Benchmarking

### Running Benchmarks

```bash
# Benchmark evaluators at various depths
python scripts/benchmark_evals.py

# Mark and test engine performance
python scripts/mark1.py
```

### Logging & Analysis

The engine logs all moves, search statistics, and game results to `logs/engine_*.log`:

```json
{"type": "move", "move": "e2e4", "fen": "..."}
{"type": "search", "move": "e2e4", "score": 35, "depth": 12, "time": 0.234}
{"type": "match_result", "result": "1-0"}
```

---

## 🔍 Architecture Principles

- **Modularity**: Each component (board, search, evaluation) is independent
- **Extensibility**: Builder pattern and strategy pattern for flexible composition
- **Performance**: Optimized data structures (transposition tables, bitboards)
- **Clean Code**: Clear separation of concerns with documented interfaces
- **Async Logging**: Non-blocking logging with background worker threads

---

## 📝 Dependencies

- **python-chess** (3.1+): Chess move generation and validation
- **pyyaml**: Configuration file parsing

See `requirements.txt` for exact versions.

---