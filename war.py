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

def kill_game(game):
    """
    TODO: If either client sends a bad message, immediately nuke the game.
    """
    pass

def compare_cards(card1, card2):
    """
    TODO: Given an integer card representation, return -1 for card1 < card2,
    0 for card1 = card2, and 1 for card1 > card2

    What is a good way to approach this?

    I'll be given a card1 from player1 and card2 from player2.

    Map the values inside the card variabless to represent the actual card value (0 = 2, 1 = 3...11 (K) = 13)
    Once I have the actual value of the cards, then I can just compare them directly

    return -1, 0, 1 based on value comparison
    """
    pass

def deal_cards():
    """
    TODO: Randomize a deck of cards (list of ints 0..51), and return two
    26 card "hands."
    create a deck (list???)
    randomize the deck
    populate player's corresponding attributes to it's Game namedtuple with half the deck --?
    """
    pass

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
    """ I have two clients now, player1 & player2:
    I want to get their requests for a game, first.
    To do this, I must first begin by calling readexactly twice, and save their requests into variable
    ****Can I hardcode '2' as the number of bytes I want to receieve exactly?

    Next I will have 2 requests from 2 different clients. 
    1st request I receive from both should be: ??????????????????????????????????????
        b'00'   --> to indicate they both want the game
      I will respond with:
        b'1<1-...-26>'  --> to indicate the game has started, and your hand 
    2nd request I receive from both should then b:
        b'2<1byte>      --> to indicate the card the player wants to use in this round
      I will:
        1. Check that this card is in the corresponding player's hand
            -Card is not a duplicate
            -Card is not empty
            -Card is not something you didn't originally have
        2. Compare the card to the other player's card
            -Go to my scoring map 
        3. respond with:
            b'3"W"/"L"/"D"' - to each player -----am I keeping track of score as well?
    All subsequent requests and responses are like the 2nd, until the player's hands are empty
    ...
    Client/Player sends last card, receives last result, disconnects from socket
    Server sends the last response containing last round's result, disconnect from socket
    """
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
