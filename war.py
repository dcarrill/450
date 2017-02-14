"""
war card game client and server
"""
import asyncio
from collections import namedtuple
from enum import Enum
import logging
import random
import socket
import socketserver
import thread
import sys

"""
Namedtuples work like classes, but are much more lightweight so they end
up being faster. It would be a good idea to keep objects in each of these
for each game which contain the game's state, for instance things like the
socket, the cards given, the cards still available, etc.
"""
Game = namedtuple("Game", ["p1", "p2"])
""" Contemplating how these namedtuple works exactly...
    Say this 'Game' namedtuple is basically like a default - no meaningful values
    Game - the name, how we will access the members, etc
    p1 & p2 are the attribute members - where we store info about these members


    Also wondering how to use the classes below
    *rubs chin and stares off into distance* hmmmm....

"""

class Command(Enum):
    """
    The byte values sent as the first byte of any message in the war protocol.
    """
    WANTGAME = 0
    GAMESTART = 1
    PLAYCARD = 2
    PLAYRESULT = 3


class Result(Enum):
    """
    The byte values sent as the payload byte of a PLAYRESULT message.
    """
    WIN = 0
    DRAW = 1
    LOSE = 2

def readexactly(sock, numbytes):
    """
    Accumulate exactly `numbytes` from `sock` and return those. If EOF is found
    before numbytes have been received, be sure to account for that here or in
    the caller.


    Have yet to account for EOF error
    """
    bytes_recv = b''
    while numbytes != len(bytes_recv):
        bytes_recv += sock.recv(numbytes - len(bytes_recv))
    return bytes_recv

#changed the arguments here________________
def kill_game(player_list):
    """
    TODO: If either client sends a bad message, immediately nuke the game.
    """
    player_list[0].close()
    player_list[1].close()

def compare_cards(card1, card2):
    """
    TODO: Given an integer card representation, return -1 for card1 < card2,
    0 for card1 = card2, and 1 for card1 > card2
    card1 = player1's card
    card2 = player2's card
    """
    p1_result = card1 % 13
    p2_result = card2 % 13

    if p1_result < p2_result:
        return -1
    elif p1_result > p2_result:
        return 1
    else:
        return 0

def deal_cards():
    """
    TODO:
    1. create a deck of 0 - 51 cards - list of bytes?
    2. randomize the deck
    3. split the deck in half
    4. return a single list of two lists
    """
    deck = list(range(0, 52))
    random.shuffle(deck)
    first_half = deck[0:26]
    second_half = deck[26:52]
    player_hands = []
    player_hands.append(bytes(first_half))
    player_hands.append(bytes(second_half))
    return player_hands

def serve_game(host, port):
    """
    TODO: Open a socket for listening for new connections on host:port, and
    perform the war protocol to serve a game of war between each client.
    This function should run forever, continually serving clients.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, port))
        sock.listen(2)
        #"playerX" is the name of the socket where I will send/recv bytes to
        player1, addr = sock.accept()
        player2, addr2 = sock.accept()
        play1res = readexactly(player1, 2)
        play2res = readexactly(player2, 2)
        
        #Make sure first request from players is 'want game'
        if play1res != b'\0\0' or play2res != b'\0\0':
            kill_game([player1, player2])
            return
        #Players want games, deal their hands
        player_hands = deal_cards()
        player1.send(b'\1' + player_hands[0])
        player2.send(b'\1' + player_hands[1])

        #Get their second request
        play1res = readexactly(player1, 2)
        play2res = readexactly(player2, 2)
        #Make sure their request is 'play card'
        if play1res[0:1] != b'\2' or play2res[0:1] != b'\2':
            kill_game([player1, player2])

        #extract the card they played
        p1_card = play1res[1]
        p2_card = play2res[1]
        #error checking - make sure the card is in their hand
        result = compare_cards(p1_card, p2_card)
        #remove the card from their hands -- does the client do this?

        if result == 0:
            player1.send(Result.DRAW)
            player2.send(Result.DRAW)
        elif result == -1: #player 1 loses
            player1.send(Result.LOSE)
            player2.send(Result.WIN)
        elif result == 1: #player 2 loses
            player1.send(Result.WIN)
            player2.send(Result.LOSE)
        else:
            #something else happened
            print("Error-didn't get a -1,0,1 comparison")
        #now we have 1 comparison
        #keep comparing until their hands are empty - while loop
        #once while-loop is over, we can close connections
    pass

async def limit_client(host, port, loop, sem):
    """
    Limit the number of clients currently executing.
    You do not need to change this function.
    """
    async with sem:
        return await client(host, port, loop)

async def client(host, port, loop):
    """
    Run an individual client on a given event loop.
    You do not need to change this function.
    """
    try:
        reader, writer = await asyncio.open_connection(host, port, loop=loop)
        # send want game
        writer.write(b"\0\0")
        card_msg = await reader.readexactly(27)
        myscore = 0
        for card in card_msg[1:]:
            writer.write(bytes([Command.PLAYCARD.value, card]))
            result = await reader.readexactly(2)
            if result[1] == Result.WIN.value:
                myscore += 1
            elif result[1] == Result.LOSE.value:
                myscore -= 1
        if myscore > 0:
            result = "won"
        elif myscore < 0:
            result = "lost"
        else:
            result = "drew"
        logging.debug("Game complete, I %s", result)
        writer.close()
        return 1
    except ConnectionResetError:
        logging.error("ConnectionResetError")
        return 0
    except asyncio.streams.IncompleteReadError:
        logging.error("asyncio.streams.IncompleteReadError")
        return 0
    except OSError:
        logging.error("OSError")
        return 0

def main(args):
    """
    launch a client/server
    """
    host = args[1]
    port = int(args[2])
    if args[0] == "server":
        try:
            # your server should serve clients until the user presses ctrl+c
            serve_game(host, port)
        except KeyboardInterrupt:
            pass
        return
    else:
        loop = asyncio.get_event_loop()

    if args[0] == "client":
        loop.run_until_complete(client(host, port, loop))
    elif args[0] == "clients":
        sem = asyncio.Semaphore(1000)
        num_clients = int(args[3])
        clients = [limit_client(host, port, loop, sem)
                   for x in range(num_clients)]
        async def run_all_clients():
            """
            use `as_completed` to spawn all clients simultaneously
            and collect their results in arbitrary order.
            """
            completed_clients = 0
            for client_result in asyncio.as_completed(clients):
                completed_clients += await client_result
            return completed_clients
        res = loop.run_until_complete(
            asyncio.Task(run_all_clients(), loop=loop))
        logging.info("%d completed clients", res)

    loop.close()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main(sys.argv[1:])
