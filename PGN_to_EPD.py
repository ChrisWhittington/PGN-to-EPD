#
#
import sys
import os
import asyncio
import chess
import time
import random
import numpy as np
import chess.pgn
import chess.engine
import argparse
import pathlib

from os import listdir
from os.path import isfile, join
#

# global paarameters
# ==================
# only use games by players both above elo limit
ELO_LIMIT = 2700
# short draws get aborted
SHORTDRAWLENGTH = 45
# short games get aborted
SHORTGAMELENGTH = 40
# we don't sample the first few epds after startpos
FIRSTMOVENUM = 5
# SF analysis time setting (ms)
GAME_OUTCOME_TIME_LIMIT = 100
POSITION_ANALYSIS_TIME_LIMIT = 25
# SF threads to use
THREADS = 1
# centipawn limits of what counts as WDL
WIN_LIMIT = 100
DRAW_LIMIT = 50
# engine to use
ANALYSIS_ENGINE = "sf11"

# stub name for pgn and epd files
STUB_FILENAME = "ccrl-40-40-june-2020-2700"

EPD_FILE_SIZE = 200000

# which core this instantiation is supposed to use (1-6 usually)
CORE_ID = 1
USEABLE_CORES = 6

#
# file batch ids for which PGN files to use
PGN_BATCH_START = 0
PGN_BATCH_END = 2

def normalise_uci_score_to_int(score):
    score = str(score)
    score = score.replace('+', '')
    if ('#' in score):        
        #print(score)
        score = score.replace('#', '')
        score = int(score)
        #print(score)
        if (score < 0):
            score = -(32000 + score)
        else:
            score = (32000 - score)
        #print(score)
        #assert(1==2), 'break'
    score = int(score)
    return score
#

#
def get_elo_difference(wins, draws, losses):
    points = wins + draws/2.0
    games = wins + draws + losses
    winrate = points / games
    if (games == wins):
        elo = 1000.0
    else:
        if (points == 0.0):
            elo = -1000.0
        else:
            elo = math.log10((games - points) / points)
            elo = -(elo*400)
    return winrate, elo
#

#
def is_file_exists(path):
    isExist = os.path.exists(path) 
    if not isExist:
        return False
    return True
#
#
def save_epd_batch(saved_epd_list, epd_batch_id, epd_save_filename):
    saved_epd_list = list(set(saved_epd_list))
    random.shuffle(saved_epd_list)

    savefilename = epd_save_filename  + "-" + str(epd_batch_id) + ".epd"
    print("Saving batch", epd_batch_id, "epds", len(saved_epd_list), savefilename)

    f = open(savefilename, "w", encoding = "utf-8")
    for epd in saved_epd_list:
        epd = epd.strip()
        f.write(epd + "\n")
    f.close()

    return
#

#
def get_move_type(board, move):
    type = ""
    if (board.is_capture(move)):
        type += "x" # move is capture
    if (move.promotion != None):
        type += "p"   # move is promotion
    if (board.is_check()):
        type += "e" # move is evasion
    if (board.gives_check(move)):
        type += "+"
    if (type == ""):
        type = "-"
    return type
#

#
def clean_raw_pgns():
    assert(1==2), 'break - why you doing this again?'
    pgn_dir = "e:/pgn-2020-june/"
    pgn_filename = "ccrl-40-40-june-2020-"
    #pgn_filename = "ccrl-blitz-june-2020-2800"
    filename = pgn_dir + pgn_filename + ".pgn"
    game_count = 0
    batch_id = 0
    clean_game_count = 0
    clean_pgns = []
    pgn_file = open(filename)
    while (True):
        # load next PGN
        # =============
        try:
            game = chess.pgn.read_game(pgn_file)
        except ValueError:
            print('Value Error')
            continue
        if (game == None):
            break
        game_count += 1

        if (len(game.errors) > 0):
            print("*******", game.errors)
            continue
        # pgn looks okay, save ..
        clean_game_count += 1
        clean_pgns.append(game)
        if ((game_count % 500) == 0):
            print(game_count, clean_game_count)

        if ((clean_game_count % 50000) == 0):           
            f = open(pgn_filename  + "-" + str(batch_id) + ".pgn", "w", encoding = "utf-8")
            for game in clean_pgns:
                f.write(str(game) + "\n\n")
            f.close()
            batch_id += 1
            clean_pgns = [] 

    pgn_file.close()

    f = open(pgn_filename + "-" + str(batch_id) + ".pgn", "w", encoding = "utf-8")
    for game in clean_pgns:
        f.write(str(game) + "\n\n")
    f.close()
    
    return
#
#
def process_epds():
    # load all epds
    # =============
    mypath = "result-eval-epds/"
    epd_files = []
    onlyfiles = [f for f in listdir(mypath) if isfile(join(mypath, f))]
    epd_list = []
    for f in onlyfiles:
        if '.epd' in f:
            print(f)
            epd_files.append(mypath + f)

    for filename in epd_files:
        with open(filename, 'r') as f9:
            while (True):
                line = f9.readline()
                line = line.strip()
                if not line:
                    break
                epd_list.append(line)

    # remove duplicates and shuffle
    # =============================
    x9 = len(epd_list)
    epd_list = list(set(epd_list))
    print("epds", x9, "unique epds", len(epd_list))
    random.shuffle(epd_list)

    # split into 80 files (for 10 cores to process 8 files each)
    # ==========================================================
    filecount = 80
    x9 = len(epd_list)
    x1 = int(x9 / filecount)   # batch size
    epd_save_filename = "temp-eval-epds/temp-eval-results"
    for batch_id in range(filecount):
        start_ix = batch_id * x1
        end_ix = (batch_id + 1) * x1
        if (batch_id == (filecount-1)):
            end_ix = len(epd_list)
        saved_epd_list = epd_list[start_ix : end_ix]
        #print("batch id", batch_id, "batch size", len(saved_epd_list), "start", start_ix, "end", end_ix)
        save_epd_batch(saved_epd_list, batch_id, epd_save_filename)
    return
#

#
async def make_epds():
    break_count = 0 # temp debug
    # load analysis engine
    print("trying to open " + ANALYSIS_ENGINE + ".exe")
    try:
        transport, engine = await chess.engine.popen_uci(ANALYSIS_ENGINE)
    except OSError:
        print("engine open fail, " + ANALYSIS_ENGINE + ".exe should be in working directory")
        assert(1==2), 'break'
    engine_name = engine.id.get("name")
    print("Found", engine_name)
    # print(engine.options['Threads'])
    await engine.configure({'Threads': THREADS})
    #assert(1==2), 'break'

    start_t = time.time()
    saved_epd_list = []
    epd_batch_id = 0
    n_epds = 0
    epd_count = 0
    game_count = 0
    game_good_count = 0

    start_batch = PGN_BATCH_START
    end_batch = PGN_BATCH_END
    pgn_root = STUB_FILENAME
    epd_save_filename = "result-eval-epds/epds-from-" + pgn_root + "-" + str(start_batch) + "-" + str(end_batch)
    for pgn_batch_id in range(start_batch, end_batch+1, 1):
        pgn_filename = "pgns/" + pgn_root + "-" + str(pgn_batch_id) + ".pgn"
        print('Loading', pgn_filename, pgn_batch_id, start_batch, end_batch)
        file = pathlib.Path(pgn_filename)
        if not file.exists():
            assert (1==2), 'file not found error'

        pgn_file = open(pgn_filename)
        while (True):
            # load next PGN
            # =============
            game_count += 1
            try:
                game = chess.pgn.read_game(pgn_file)
            except ValueError:
                print('Value Error')
                continue
            if (game == None):
                break
        
            if (len(game.errors) > 0):
                print("*******", game.errors)
                continue
        
            # get result, and abort game if not valid
            # =======================================
            result = game.headers["Result"]
            if (result == '1-0'):
                v_pgn = 1.0
            else:
                if (result == '0-1'):
                    v_pgn = 0.0
                else:
                    if (result == '1/2-1/2'):
                        v_pgn = 0.5
                    else:
                        continue
            if (ELO_LIMIT > 0):
                try:
                    elo_w = game.headers["WhiteElo"]
                except KeyError:
                    continue
                try:
                    elo_b = game.headers["BlackElo"]
                except KeyError:
                    continue
                try:
                   elo_w = int(elo_w)
                except ValueError:
                    continue
                try:
                   elo_b = int(elo_b)
                except ValueError:
                    continue
                if (elo_w < ELO_LIMIT):
                    continue
                if (elo_b < ELO_LIMIT):
                    continue

            # go through game
            # ===============
            game_epd_list = []
            board = game.board()
            halfmovenum = 0
            for move in game.mainline_moves():
                type = get_move_type(board, move)
                mv = move.uci()
                epd = board.fen() + '; ' + mv + " " + type + ' pgn=' + str(v_pgn)
                game_epd_list.append(epd)
                #print(epd)
                board.push(move)
                halfmovenum += 1
                v_pgn = 1.0 - v_pgn
                        
            #assert(1==2), 'break'

            # abandon short draws
            # ===================
            if ((v_pgn == 0.5) and (halfmovenum < SHORTDRAWLENGTH)):
                continue
            # abandon short games
            # ===================
            if (halfmovenum < SHORTGAMELENGTH):
                continue

            # strip final two epds
            # ====================
            game_epd_list = game_epd_list[:-2]
        
            # use engine to confirm PGN stated result for this epd
            # ====================================================
            epd = game_epd_list[-1]
            x = epd.split(';')
            fen = x[0]
            y = x[1].split('pgn=')
            v_final_pgn_move = float(y[1])
            #print(fen)

            board = chess.Board(fen)
            limit = chess.engine.Limit(time = GAME_OUTCOME_TIME_LIMIT / 1000)
            info = await engine.analyse(board, limit)
            #print(info)
            #assert(1==2), 'break'
            depth = info['depth']
            nodes = info['nodes']
            score = info['score']
            # convert score to integer
            # ========================
            v_sf = normalise_uci_score_to_int(score)

            pv = info['pv']
            move = pv[0]            
            mv = move.uci()

            # abandon game results where SF search doesn't agree
            # ==================================================
            flag = False
            if ((v_sf > WIN_LIMIT) and (v_final_pgn_move == 1.0)):
                flag = True
            if ((v_sf < -WIN_LIMIT) and (v_final_pgn_move == 0.0)):
                flag = True
            if ((v_sf < DRAW_LIMIT) and (v_sf > -DRAW_LIMIT) and (v_final_pgn_move == 0.5)):
                flag = True
            if (flag == False):
                #print(game)
                #epd = epd + '; ' + mv + ' sf10=' + str(v_sf)
                #print(epd)
                continue

            #assert(1==2), 'break'
            # ??????

            # found an ok game to use
            game_good_count += 1
            epd_count += (len(game_epd_list) - FIRSTMOVENUM)
            # randomly sample a few epds
            # ==========================
            temp_epd_list = []
            for i in range(int(len(game_epd_list) / 5)):            
                r = random.randint(FIRSTMOVENUM, len(game_epd_list) - 1)
                epd = game_epd_list[r]
                #while (r < len(game_epd_list)):                    
                #    # move on from non-quiet positions (move is capture or promo)
                #    x = epd.split(';')
                #    fen = x[0]
                #    board = chess.Board(fen)
                #    y = x[1].split('pgn=')
                #    mv = y[0].strip()
                #    move = chess.Move.from_uci(mv)
                #    if not (board.is_capture(move) or (move.promotion != None)):
                #        break
                #    r += 1
                    #print(epd, mv)

                # add SF11 analysis here
                # ======================
                # nope, do that in next batch program process
                temp_epd_list.append(epd)
                #break_count += 1
                #print(epd)
                #if (break_count > 500):
                #    assert(1==2), 'break'

            # throw out any duplicates and add to saved_epd_list ...
            # ======================================================
            saved_epd_list += list(set(temp_epd_list))
            n_epds += len(temp_epd_list)

            # consider saving a batch of epds ...
            # ===================================
            if (len(saved_epd_list) > EPD_FILE_SIZE):
                save_epd_batch(saved_epd_list, epd_batch_id, epd_save_filename)
                # reset the epd list count etc.
                saved_epd_list = []
                epd_batch_id += 1
                # assert(epd_batch_id < 4), 'temp break'

            if ((game_count % 100) == 0):
                #n_epds = len(saved_epd_list)
                localtime = time.asctime(time.localtime(time.time()))
                used_t = time.time() - start_t
                print(localtime + " pgns=" + str(game_count) + " useable pgns=" + str(game_good_count) +
                      " epds=" + str(epd_count) + " epds/sec=" + str(round(epd_count/used_t, 1)) +
                      " sampled epds=" + str(n_epds) + " sampled epds/sec=" + str(round(n_epds/used_t, 1)) +
                      " sampling rate=" + str(round(n_epds/epd_count,2)))
                #assert(1==2), 'break'

            # loop back, next game
            # ====================

        # finished with this pgn file
        pgn_file.close()
        # loop back, get next pgn file

    # save final epd batch
    if (len(saved_epd_list) > 0):
        save_epd_batch(saved_epd_list, epd_batch_id, epd_save_filename)
    #assert(1==2), 'break'
    await engine.quit()
    # concatenate all epds, shuffle and split into N sub-files
    # ========================================================
    process_epds()
    return
#

#
# currently adds SF11 analysis, junking any capture/promos
async def analyse_epds(core_id, total_cores):
    # load analysis engine
    print("trying to open " + ANALYSIS_ENGINE + ".exe")
    try:
        transport, engine = await chess.engine.popen_uci(ANALYSIS_ENGINE)
    except OSError:
        print("engine open fail, " + ANALYSIS_ENGINE + ".exe should be in working directory")
        assert(1==2), 'break'
    engine_name = engine.id.get("name")
    print("Found", engine_name)
    # print(engine.options['Threads'])
    # await engine.configure({'Threads': THREADS})
    #assert(1==2), 'break'
    loadpath = "temp-eval-epds/temp-eval-results-"
    savepath = "result-plus-sf-eval-epds/sf-eval"
    # we should have 80 files, we're using total-cores(10) and this core is core_id
    n_batches = int(80 / total_cores)
    start_batch = (core_id-1) * n_batches
    end_batch = core_id * n_batches
    for batch_id in range(start_batch, end_batch, 1):
        filename = loadpath + str(batch_id) + ".epd"
        print("Loading", filename, "batch", batch_id, "from", start_batch, "to", end_batch)
        epd_list = []
        with open(filename, 'r') as f9:
            while (True):
                line = f9.readline()
                line = line.strip()
                if not line:
                    break
                epd_list.append(line)

        new_epd_list = []
        for epd in epd_list:
            epd = epd.strip()
            if (epd == ""):
                assert(1==2), 'epd fail'
            fen = epd.split(";")[0]
            board = chess.Board(fen)
            limit = chess.engine.Limit(time = POSITION_ANALYSIS_TIME_LIMIT / 1000)
            info = await engine.analyse(board, limit)
            #print(info)
            #assert(1==2), 'break'
            depth = info['depth']
            nodes = info['nodes']
            score = info['score']
            # convert score to integer
            # ========================
            v_sf = normalise_uci_score_to_int(score)

            pv = info['pv']
            move = pv[0]

            type = get_move_type(board, move)
            mv = move.uci()

            epd += "; " + str(mv) + " " + type + " " + ANALYSIS_ENGINE + "=" + str(v_sf) + " t=" + str(POSITION_ANALYSIS_TIME_LIMIT)
            new_epd_list.append(epd)
            # debug
            #print(epd)
            #if (len(new_epd_list) > 25):
            #    break
        # save epd batch
        save_epd_batch(new_epd_list, batch_id, savepath)

    #assert(1==2), 'break'
    return
#


#
def main(argv):
    global ELO_LIMIT, SHORTDRAWLENGTH, SHORTGAMELENGTH, FIRSTMOVENUM
    global GAME_OUTCOME_TIME_LIMIT, POSITION_ANALYSIS_TIME_LIMIT
    global THREADS, WIN_LIMIT, DRAW_LIMIT, ANALYSIS_ENGINE, STUB_FILENAME
    global PGN_BATCH_START, PGN_BATCH_END, CORE_ID, USEABLE_CORES

    parser = argparse.ArgumentParser()
    parser.add_argument('--elo', dest='elo', required=False, type=int, default=ELO_LIMIT, help='minimum player Elo')
    parser.add_argument('--drawlen', dest='drawlen', required=False, type=int, default=SHORTDRAWLENGTH, help='minimum length drawn games')
    parser.add_argument('--gamelen', dest='gamelen', required=False, type=int, default=SHORTGAMELENGTH, help='minimum length all games')
    parser.add_argument('--firstmove', dest='firstmove', required=False, type=int, default=FIRSTMOVENUM, help='start halfmove lower limit')
    parser.add_argument('--outcometime', dest='outcometime', required=False, type=int, default=GAME_OUTCOME_TIME_LIMIT, help='movetime(ms) to decide game outcome')
    parser.add_argument('--analysistime', dest='analysistime', required=False, type=int, default=POSITION_ANALYSIS_TIME_LIMIT, help='movetime(ms) to evaluate each epd')
    parser.add_argument('--winlimit', dest='winlimit', required=False, type=int, default=WIN_LIMIT, help='centipawn win window limit')
    parser.add_argument('--drawlimit', dest='drawlimit', required=False, type=int, default=DRAW_LIMIT, help='centipawn draw window limit')
    parser.add_argument('--pgnstart', dest='pgnstart', required=False, type=int, default=PGN_BATCH_START, help='starting pgn filenum id')
    parser.add_argument('--pgnend', dest='pgnend', required=False, type=int, default=PGN_BATCH_END, help='ending pgn filenum id')
    parser.add_argument('--coreid', dest='coreid', required=False, type=int, default=CORE_ID, help='which core id to use')
    parser.add_argument('--cores', dest='cores', required=False, type=int, default=USEABLE_CORES, help='how many cores to use')

    parser.add_argument('--stubfilename', dest='stubfilename', required=False, default=STUB_FILENAME, help='stub of epd/pgn data file names')
    parser.add_argument('--action', dest='action', required=False, default="null", help='operation: make/process/analyse')

    args = parser.parse_args()

    ELO_LIMIT = args.elo
    SHORTDRAWLENGTH = args.drawlen
    SHORTGAMELENGTH = args.gamelen
    FIRSTMOVENUM = args.firstmove
    GAME_OUTCOME_TIME_LIMIT = args.outcometime
    POSITION_ANALYSIS_TIME_LIMIT = args.analysistime
    WIN_LIMIT = args.winlimit
    DRAW_LIMIT = args.drawlimit
    PGN_BATCH_START = args.pgnstart
    PGN_BATCH_END = args.pgnend
    STUB_FILENAME = args.stubfilename

    action = args.action
    core_id = args.coreid
    total_cores = args.cores

    if (1==2):
        # manual override ...
        action = "analyse"
        core_id = 2
        total_cores = 10

        action = "make"
        PGN_BATCH_START = 0
        PGN_BATCH_END = 22

    localtime = time.asctime(time.localtime(time.time()))
    print(localtime)
    print()
    #
    print("Elo limit", ELO_LIMIT)
    print("Abort draw length", SHORTDRAWLENGTH)
    print("Abort game length", SHORTGAMELENGTH)
    print("Discount before move", FIRSTMOVENUM)
    print("Game outcome movetime ms", GAME_OUTCOME_TIME_LIMIT)
    print("EPD eval movetime ms", POSITION_ANALYSIS_TIME_LIMIT)
    print("Threads", THREADS)
    print("Win window centipawns", WIN_LIMIT)
    print("Draw window centipawns", DRAW_LIMIT)
    print("Analysis engine", ANALYSIS_ENGINE)
    print("PGN start batch", PGN_BATCH_START)
    print("PGN start end", PGN_BATCH_END)
    print("Program operation", action)
    print()

    if (action == "null"):
        print("null program action defined, aborting ...")
        return
    if ((action != "make") and (action != "process") and (action != "analyse")):
        print(action, "not understood, aborting ...")
        return

    # make/process/analyse
    # clean now done, no need to repeat
    # =================================
    if (1==2):
        clean_raw_pgns()
    #
    # done as part of make_epds()
    # no need to repeat, except first time round when I forgot it
    if (action == "process"):
        process_epds()
    #

    #
    # from cleaned PGN data, sample subset EPDs and save
    if (action == "make"):
        # until I upgrade to Python 3.7
        asyncio.set_event_loop_policy(chess.engine.EventLoopPolicy())
        loop = asyncio.get_event_loop()
        loop.run_until_complete(make_epds())
        loop.close()
        process_epds()
    #else:
    #    # works with Python 3.7 allegedly
    #    asyncio.set_event_loop_policy(chess.engine.EventLoopPolicy())
    #    asyncio.run(make_epds())

    if (action == "analyse"):
        asyncio.set_event_loop_policy(chess.engine.EventLoopPolicy())
        loop = asyncio.get_event_loop()
        loop.run_until_complete(analyse_epds(core_id, total_cores))
        loop.close()
    # assert(1==2), 'break, finished main()'
    return
#

#
if __name__ == "__main__":
    main(sys.argv[1:])
#
#

