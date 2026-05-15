#!/bin/bash

ENGINE="./bin/uci"
SF="./bin/stockfish"

./bin/cutechess-cli \
-engine name=MyEngine cmd=$ENGINE proto=uci \
-engine name=SF_Elo1320_Skill1 cmd=$SF proto=uci \
  option.UCI_LimitStrength=true \
  option.UCI_Elo=1320 \
  option.Skill\ Level=1 \
-each tc=100+1 \
-games 5 \
-repeat \
-concurrency 2 \
-pgnout logs/pgn/result.pgn