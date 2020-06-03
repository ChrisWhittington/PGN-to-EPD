# PGN-to-EPD
Converts PGN files into EPDs with a few extras

"make" mode - prepares EPDs from PGN
Tests PGNs for integrity, 
samples about 1 position in 3, 
adds move played in games, 
codes move with string "xpe+" where x=capture, p=promo, e=evasion, +=check
adds game result 0.0, 0.5 or 1.0
Junks PGNs where game result is out of line with SF11 evaluation

SF11.exe is (C) Stockfish Authors and subject to their GPL licence. 
Source code, licence etc avaialble at:
https://github.com/official-stockfish/Stockfish/blob/master/Copying.txt

"analyse" mode - adds SF11 evaluation.

Requirements
Directory containing:
pgn-to-epd batch file 
sf11.exe
wait.exe (or your equivalent, see batch file)
pgn_to_epd.exe (generate from pyinstaller from pgn_to_exe.py)
Subdirectories:
pgn - containing sequentially labelled clean PGN files for processing
temp epds - empty working directory
temp-eval-epds - empty working directory
result-eval-epds - will contain epd files
result-plus-sf-eval-epds - will contain epd files plus SF11 evaluation
