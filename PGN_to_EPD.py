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

# how many postions per PGN to sample
SAMPLING_RATE = 5

# stub name for pgn and epd files
#ROOTDIR = "ccrl-40-40"
#STUB_FILENAME = ROOTDIR + "-june-2020-2700"
EPD_FILE_SIZE = 200000

# which core this instantiation is supposed to use (1-6 usually)
#CORE_ID = 1
#USEABLE_CORES = 6

#
# file batch ids for which PGN files to use
#PGN_BATCH_START = 0
#PGN_BATCH_END = 2

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
def invert_row(row):
    inv_row = ''
    for i in range(len(row)):
        x = row[i]
        if ((x >= '0') and (x <= '8')):
            y = x
        else:
            if (x > 'Z'):
                y = x.upper()
            else:
                y = x.lower()
        inv_row += y
    return inv_row
#

def invert_fen(fen):
    inv = ''
    x = fen.split('/')
    for i in range(8):
        f = x[7-i]
        f_inv = invert_row(f)
        inv = str(inv + str(f_inv))
        if (i < 7):
            inv += '/'
    return inv
#

def invert_colour(colour):
    if (colour == 'w'):
        return 'b'
    else:
        if (colour == 'b'):
            return 'w'
    assert(1==2), 'colour fail'
    return 0
#

def invert_castles(castles):
    return castles
    return x
#

# used originally for ep sqaure, but will work will all squares
def invert_square(ep):
    if (ep == '-'):
        return ep
    x = ep[0]
    y = int(ep[1])
    #print(x,y)
    y -= int('1')
    y ^= 7
    y += int('1')
    ep_str = '' + str(x) + str(y)
    
    #print(ep_str)
    #assert(1==2), 'break'
    return ep_str
#

def numerical_invert(x):
    if ('.' in x):
        return str(1.0 - float(x))
    x = -int(x)
    return str(x)
#

# retruns colour and eval and bm inverted
def invert_epd(epd):
    epd = epd.strip()
    x = epd.split(";")
    y = x[0].split(" ")

    fen = invert_fen(y[0])
    colour = invert_colour(y[1])
    castles = invert_castles(y[2])
    ep = invert_square(y[3])

    #print(epd)
    # put the fen back together again
    inverted_epd = fen + ' ' + colour + ' ' + castles + ' ' + ep + ' ' + y[4] + ' ' + y[5]
    #print(inverted_epd)

    for i in range(1, len(x)):
        str = '; '
        d = x[i]
        d = d.strip()
        
        y = d.split(' ')
        
        mv = y[0]
        s1 = mv[0:2]
        s2 = mv[2:4]
        
        str += invert_square(s1)
        str += invert_square(s2)
        if (len(mv) > 4):
            str += mv[-1]
        inverted_epd += str + ' ' + y[1] + ' '
        z = y[2].split('=')
        #print(z[0])
        #print(z[1])
        #print(numerical_invert(z[1]))
        #print(y[3])
        #inverted_epd += z[0] + '=' + numerical_invert(z[1])
        inverted_epd += z[0] + '=' + z[1]
        for j in range(3, len(y), 1):
            inverted_epd += ' ' + y[j]
    #print(epd)
    #print(inverted_epd)
    #if (len(mv) > 4):
    #    assert(1==2), 'break'
    return inverted_epd
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

def build_opening_books():
    debug_count = 0
    game_count = 0
    pgn_count = 0
    pgns = []
    directories = ["rebel-mixed-cegt/pgn2800-",
                    "ccrl-40-40/pgns/ccrl-40-40-june-2020-2700-",
                    "ccrl-blitz/pgns/ccrl-blitz-june-2020-2800-"]
    for dir in directories:
        batch_id = 0
        while (True):
            filename = dir + str(batch_id) + ".pgn"
            batch_id += 1
            isExist = os.path.exists(filename) 
            if (isExist == False):
                break
            else:
                pgn_file = open(filename)
                print("Loading", filename)
                print()

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
                    
                    save_pgn_str = '[Event "?"]\n'
                    save_pgn_str += '[Site "?"]\n'
                    save_pgn_str += '[Date "????.??.??"]\n'
                    save_pgn_str += '[Round "?"]\n'
                    save_pgn_str += '[White "?"]\n'
                    save_pgn_str += '[Black "?"]\n'
                    save_pgn_str += '[Result "*"]\n\n'

                    halfmovenum = 0
                    board = game.board()
                    for move in game.mainline_moves():
                        
                        fullmovenum = board.fullmove_number
                        mv = board.san(move)
                        board.push(move)
                        if ((halfmovenum & 1) == 0):
                            save_pgn_str += str(fullmovenum) + '. ' + mv + ' '
                        else:
                            save_pgn_str += mv + ' '

                        halfmovenum += 1
                        if ((halfmovenum == 7) or (halfmovenum == 12) or (halfmovenum == 20)):
                            pgns.append(save_pgn_str + '*')
                            pgn_count += 1
                        if (halfmovenum == 20):
                            break;
                    if (1==2):
                        debug_count += 1
                        if (debug_count < 10):
                            print(pgns[game_count])
                        if (debug_count == 10):
                            assert(1==2), 'temp break'

                    game_count += 1
                    
                    if ((game_count % 1000) == 0):
                        pgns = list(set(pgns))
                        print(pgn_count, len(pgns))
                    # DEBUG TEMP, we could just look at all games
                    if (1==1):
                        if ((game_count % 10000) == 0):
                            break
    print("pgn count", len(pgns))
    pgns = list(set(pgns))
    print("unique pgns", len(pgns))
    random.shuffle(pgns)
    pgn_batch = int((len(pgns) / 6) - 2)
    batch_id = 0
    pgn_count = 0
    save_pgn_filename = "book-pgns/pgn-book-" + str(batch_id) + ".pgn"
    f = open(save_pgn_filename, "w", encoding = "utf-8")
    print("saving", pgn_batch, "pgns to", save_pgn_filename)
    for this_pgn in pgns:
        f.write(this_pgn + "\n\n")
        pgn_count += 1
        if ((pgn_count % pgn_batch) == 0):
            f.close()
            batch_id += 1
            if (batch_id > 5):
                break
            save_pgn_filename = "book-pgns/pgn-book-" + str(batch_id) + ".pgn"
            f = open(save_pgn_filename, "w", encoding = "utf-8")
            print("saving", pgn_batch, "pgns to", save_pgn_filename)
#
    print()
    print("saved", pgn_count, "pgns")
    assert(1==2), 'break - done'
    return
#

#
def process_epds():
    # load all epds
    # =============
    mypath = "temp-epds/"
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

    # split into 100K long files
    x9 = len(epd_list)
    filecount = int(len(epd_list) / 100000) + 1
    x1 = int(x9 / filecount)   # batch size
    epd_save_filename = "epds/eval-results"
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
    #await engine.configure({'Threads': THREADS})
    #assert(1==2), 'break'

    start_t = time.time()
    saved_epd_list = []
    epd_batch_id = 0
    n_epds = 0
    epd_count = 0
    game_count = 0
    game_good_count = 0

    mypath = "pgns/"
    epd_save_filename = "temp-epds/temp-epd"
    pgn_data_files = []
    onlyfiles = [f for f in listdir(mypath) if isfile(join(mypath, f))]
    for f in onlyfiles:
        if '.pgn' in f:
            print("found", mypath + f)
            pgn_data_files.append(mypath + f)

    for pgn_filename in pgn_data_files:
        print('Loading', pgn_filename)
        
        pgn_file = open(pgn_filename)
        while (True):
            # load next PGN
            # =============
            game_count += 1

            # report progress
            if ((game_count % 100) == 0):
                #n_epds = len(saved_epd_list)
                localtime = time.asctime(time.localtime(time.time()))
                used_t = time.time() - start_t
                print(localtime + " pgns=" + str(game_count) + " useable pgns=" + str(game_good_count) +
                      " epds=" + str(epd_count) + " epds/sec=" + str(round(epd_count/used_t, 1)) +
                      " sampled epds=" + str(n_epds) + " sampled epds/sec=" + str(round(n_epds/used_t, 1)) +
                      " sampling rate=" + str(round(n_epds/epd_count,2)))

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
                        
            #print(halfmovenum, len(game_epd_list))
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
            for i in range(int(len(game_epd_list) / SAMPLING_RATE)):            
                r = random.randint(FIRSTMOVENUM, len(game_epd_list) - 1)
                epd = game_epd_list[r]
                # add game length
                epd += (" len=" + str(halfmovenum))

                #if ((r > ((halfmovenum/2) + 1)) and (halfmovenum > 200)):
                #    print(epd)
                #    print(r, halfmovenum, len(game_epd_list))
                #    assert(1==2), 'break'
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

    if (1==2):
        # dumb, when parallel, don't do process here
        # concatenate all epds, shuffle and split into N sub-files
        # ========================================================
        # process_epds()
        # specially for ED
        process_epds()
        #
        # username affects base path of where epds are to be found
        invert_texel_epds("Ed")

    return
#

#
# currently adds SF11 analysis, junking any capture/promos
async def analyse_epds(core_id, total_cores):
    debug_counter = 0
    # load analysis engine
    if ((ANALYSIS_ENGINE == "sf11") or (ANALYSIS_ENGINE == "lc0")):
        print("trying to open " + ANALYSIS_ENGINE + ".exe")
        if (ANALYSIS_ENGINE == "sf11"):
            try:
                transport, engine = await chess.engine.popen_uci(ANALYSIS_ENGINE)
            except OSError:
                print("engine open fail, " + ANALYSIS_ENGINE + ".exe should be in working directory")
                assert(1==2), 'break'
        else:
            try:
                transport, engine = await chess.engine.popen_uci("lc0-v0.25.1/" + ANALYSIS_ENGINE)
            except OSError:
                print("engine open fail, lc0-v0.25.1/" + ANALYSIS_ENGINE + ".exe should be in working directory")
                assert(1==2), 'break'

        engine_name = engine.id.get("name")
        print("Found", engine_name)
        # print(engine.options['Threads'])
        # await engine.configure({'Threads': THREADS})
        #assert(1==2), 'break'
        # we're assuming here that we do sf11 evals before lc0 evals
        if (ANALYSIS_ENGINE == "sf11"):
            loadpath = ROOTDIR + "temp-eval-epds/temp-eval-results-"
            savepath = ROOTDIR + "result-plus-sf-eval-epds/sf-eval"
        else:
            loadpath = ROOTDIR + "result-plus-sf-eval-epds/sf-eval-"
            savepath = ROOTDIR + "result-plus-sf-and-lc0-eval-epds/sf_lc0_eval"
    else:
        print("unknown engine")
        assert(1==2), 'break'

    # we should have 80 files, we're using total-cores(10) and this core is core_id
    n_batches = int(80 / total_cores)
    start_batch = (core_id-1) * n_batches
    end_batch = core_id * n_batches
    for batch_id in range(start_batch, end_batch, 1):
        filename = loadpath + str(batch_id) + ".epd"
        print("Loading", filename, "batch", batch_id, "from", start_batch, "to", end_batch-1)
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
            time_used = int(info['time'] * 1000) # we want time in ms
            # convert score to integer
            # ========================
            if (ANALYSIS_ENGINE == "sf11"):
                v_sf = normalise_uci_score_to_int(score)
            else:
                # later lc0 report score in centipawns
                v_sf = normalise_uci_score_to_int(score)

            pv = info['pv']
            move = pv[0]

            type = get_move_type(board, move)
            mv = move.uci()

            epd += "; " + str(mv) + " " + type + " " + ANALYSIS_ENGINE + "=" + str(v_sf) + " t=" + str(time_used) + " nodes=" + str(nodes)
            new_epd_list.append(epd)
            # debug
            #if (debug_counter < 250):
            #    debug_counter += 1
            #    print(epd)
            #else:
            #    assert(1==2), 'break'

        # save epd batch
        save_epd_batch(new_epd_list, batch_id, savepath)

    #assert(1==2), 'break'
    return
#

#
def stats_on_texel_epds(username):
    # load all epds
    # =============
    
    if (username == 'Ed'):
        mypaths = ["normalised-epds/eval-normalised-results"]
    else:
        mypaths = ["texel-epds/epds-sf-lc0-ccrl-40-40/",
                   "texel-epds/epds-sf-lc0-ccrl-blitz/"]

    for mypath in mypaths:
        epd_files = []
        onlyfiles = [f for f in listdir(mypath) if isfile(join(mypath, f))]

        for f in onlyfiles:
            if '.epd' in f:
                #print(f)
                epd_files.append(mypath + f)

        n_epds = 0
        n_white_wins = 0
        n_black_wins = 0
        n_draws = 0
        for filename in epd_files:
            with open(filename, 'r') as f9:
                while (True):
                    line = f9.readline()
                    line = line.strip()
                    if not line:
                        break
                    n_epds += 1
                    x = line.split(" ")
                    res = x[8]
                    if ("0.0" in res):
                        n_draws += 1
                    else:
                        if ("1.0" in res):
                            if (x[1] == "w"):
                                n_white_wins += 1
                            else:
                                n_black_wins += 1
                        else:
                            if (x[1] == "b"):
                                n_white_wins += 1
                            else:
                                n_black_wins += 1
        assert(n_epds == (n_white_wins + n_black_wins + n_draws)), 'epd count fail'
        print(mypath, n_epds, n_white_wins, n_black_wins, n_draws, n_draws/n_epds, n_white_wins/n_epds, n_black_wins/n_white_wins)
    return
#

def invert_texel_epds(username):
    # load all epds
    # =============
    if (username == 'Ed'):
        mypaths = ["epds/"]
    else:
        mypaths = ["texel-epds/epds-sf-lc0-ccrl-40-40/",
                   "texel-epds/epds-sf-lc0-ccrl-blitz/"]
    n_epds = 0
    n_inverts = 0
    n_white_wins = 0
    n_black_wins = 0
    n_draws = 0
    epd_list = []

    for mypath in mypaths:
        epd_files = []
        onlyfiles = [f for f in listdir(mypath) if isfile(join(mypath, f))]

        for f in onlyfiles:
            if '.epd' in f:
                print(f)
                epd_files.append(mypath + f)

        for filename in epd_files:
            with open(filename, 'r') as f9:
                while (True):
                    line = f9.readline()
                    epd = line.strip()
                    if not epd:
                        break

                    r = random.randint(1, 1000)
                    if (r > 500):
                        # invert board and colour, evals remain the same
                        n_inverts += 1
                        epd = invert_epd(epd)
                    #assert(1==2), 'break'
                    epd_list.append(epd)
                    n_epds += 1
                    x = epd.split(" ")
                    res = x[8]
                    if ("0.0" in res):
                        n_draws += 1
                    else:
                        if ("1.0" in res):
                            if (x[1] == "w"):
                                n_white_wins += 1
                            else:
                                n_black_wins += 1
                        else:
                            if (x[1] == "b"):
                                n_white_wins += 1
                            else:
                                n_black_wins += 1
                    if ((n_epds % 100000) == 0):
                        assert(n_epds == (n_white_wins + n_black_wins + n_draws)), 'epd count fail'
                        print(filename, n_inverts, n_epds, n_white_wins, n_black_wins, n_draws, n_draws/n_epds, n_white_wins/n_epds, n_black_wins/n_white_wins)

    assert(n_epds == (n_white_wins + n_black_wins + n_draws)), 'epd count fail'
    print(filename, n_inverts, n_epds, n_white_wins, n_black_wins, n_draws, n_draws/n_epds, n_white_wins/n_epds, n_black_wins/n_white_wins)

    # remove duplicates and shuffle
    # =============================
    x9 = len(epd_list)
    epd_list = list(set(epd_list))
    print("epds", x9, "unique epds", len(epd_list))
    # don't shuffle, maintains ccrl-40-40 and ccrl-blitz order of files, first 9mn are 40-40
    # random.shuffle(epd_list)

    # split into 100K long files
    x9 = len(epd_list)
    filecount = int(len(epd_list) / 100000) + 1
    x1 = int(x9 / filecount)   # batch size
    epd_save_filename = "normalised-epds/eval-normalised-results"
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
def main(argv):
    global ELO_LIMIT, SHORTDRAWLENGTH, SHORTGAMELENGTH, FIRSTMOVENUM
    global GAME_OUTCOME_TIME_LIMIT, POSITION_ANALYSIS_TIME_LIMIT
    global THREADS, WIN_LIMIT, DRAW_LIMIT, ANALYSIS_ENGINE, STUB_FILENAME
    global PGN_BATCH_START, PGN_BATCH_END, CORE_ID, USEABLE_CORES, ANALYSIS_ENGINE
    global ROOTDIR, SAMPLING_RATE

    parser = argparse.ArgumentParser()
    parser.add_argument('--elo', dest='elo', required=False, type=int, default=ELO_LIMIT, help='minimum player Elo')
    parser.add_argument('--drawlen', dest='drawlen', required=False, type=int, default=SHORTDRAWLENGTH, help='minimum length drawn games')
    parser.add_argument('--gamelen', dest='gamelen', required=False, type=int, default=SHORTGAMELENGTH, help='minimum length all games')
    parser.add_argument('--firstmove', dest='firstmove', required=False, type=int, default=FIRSTMOVENUM, help='start halfmove lower limit')
    parser.add_argument('--outcometime', dest='outcometime', required=False, type=int, default=GAME_OUTCOME_TIME_LIMIT, help='movetime(ms) to decide game outcome')
    parser.add_argument('--analysistime', dest='analysistime', required=False, type=int, default=POSITION_ANALYSIS_TIME_LIMIT, help='movetime(ms) to evaluate each epd')
    parser.add_argument('--winlimit', dest='winlimit', required=False, type=int, default=WIN_LIMIT, help='centipawn win window limit')
    parser.add_argument('--drawlimit', dest='drawlimit', required=False, type=int, default=DRAW_LIMIT, help='centipawn draw window limit')
    #parser.add_argument('--pgnstart', dest='pgnstart', required=False, type=int, default=PGN_BATCH_START, help='starting pgn filenum id')
    #parser.add_argument('--pgnend', dest='pgnend', required=False, type=int, default=PGN_BATCH_END, help='ending pgn filenum id')
    #parser.add_argument('--coreid', dest='coreid', required=False, type=int, default=CORE_ID, help='which core id to use')
    #parser.add_argument('--cores', dest='cores', required=False, type=int, default=USEABLE_CORES, help='how many cores to use')
    parser.add_argument('--samplingrate', dest='samplingrate', required=False, type=int, default=SAMPLING_RATE, help='sample N positions per PGN')
    # parser.add_argument('--stubfilename', dest='stubfilename', required=False, default=STUB_FILENAME, help='stub of epd/pgn data file names')
    parser.add_argument('--action', dest='action', required=False, default="null", help='operation: make/process/analyse/normalise')
    parser.add_argument('--analysisengine', dest='analysisengine', required=False, default="sf11", help='either lc0 or sf11')
    #parser.add_argument('--rootdir', dest='rootdir', required=False, default="ccrl-40-40", help='ccrl-40-40 or ccrl-blitz')

    args = parser.parse_args()

    ELO_LIMIT = args.elo
    SHORTDRAWLENGTH = args.drawlen
    SHORTGAMELENGTH = args.gamelen
    FIRSTMOVENUM = args.firstmove
    GAME_OUTCOME_TIME_LIMIT = args.outcometime
    POSITION_ANALYSIS_TIME_LIMIT = args.analysistime
    WIN_LIMIT = args.winlimit
    DRAW_LIMIT = args.drawlimit
    #PGN_BATCH_START = args.pgnstart
    #PGN_BATCH_END = args.pgnend
    #STUB_FILENAME = args.stubfilename
    ANALYSIS_ENGINE = args.analysisengine
    #ROOTDIR = args.rootdir

    SAMPLING_RATE = args.samplingrate

    action = args.action
    #core_id = args.coreid
    #total_cores = args.cores


    if (1==2):
        stats_on_texel_epds('chris')
        assert(1==2), 'done epd stats'

    if (1==1):
        invert_texel_epds("chris")
        assert(1==2), 'done inverts'

    if (1==2):
        build_opening_books()
        assert(1==2), 'done making opening books'

    if (1==2):
        clean_raw_pgns()

    if (1==2):
        # manual override ...
        action = "analyse"
        #ANALYSIS_ENGINE = "lc0"
        #POSITION_ANALYSIS_TIME_LIMIT = 250
        #core_id = 2
        #total_cores = 10

        action = "make"
        #PGN_BATCH_START = 0
        #PGN_BATCH_END = 45
        #ROOTDIR = "ccrl-blitz"

        #action = "process"

    localtime = time.asctime(time.localtime(time.time()))
    print(localtime)
    print()
    #
    print("PGN-to-EPD converter")
    print("Chris Whittington 2020")
    print("======================\n")
    print("Program operation", action)
    print("Elo limit", ELO_LIMIT)
    print("Abort draw length", SHORTDRAWLENGTH)
    print("Abort game length", SHORTGAMELENGTH)
    print("Discount before move", FIRSTMOVENUM)
    print("Game outcome movetime ms", GAME_OUTCOME_TIME_LIMIT)
    print("EPD eval movetime ms", POSITION_ANALYSIS_TIME_LIMIT)
    #print("Threads", THREADS)
    print("Win window centipawns", WIN_LIMIT)
    print("Draw window centipawns", DRAW_LIMIT)
    print("Analysis engine", ANALYSIS_ENGINE)
    print("PGN sample rate 1 in " + str(SAMPLING_RATE) + " positions")
    #print("PGN start end", PGN_BATCH_END)
    
    #print("Directory", ROOTDIR)
    print()


    if (action == "null"):
        print("null program action defined, aborting ...")
        return
    if ((action != "make") and (action != "process") and (action != "analyse") and (action != "normalise")):
        print(action, "not understood, aborting ...")
        return

    # make/process/analyse
    # clean now done, no need to ever repeat
    # ======================================
    if (1==2):
        clean_raw_pgns()
    #
    # after producing epds from pgns, concatenate
    # shuffle and save in sequential batches
    if (action == "process"):
        process_epds()
    #

    # username affects base path of where epds are to be found
    if (action == "normalise"):
        invert_texel_epds("Ed")

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

