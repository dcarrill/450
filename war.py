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
import threading
import sys

"""
Namedtuples work like classes, but are much more lightweight so they end
up being faster. It would be a good idea to keep objects in each of these
for each game which contain the game's state, for instance things like the
socket, the cards given, the cards still available, etc.
"""
Game = namedtuple("Game", ['p1', 'p2'])
Players = namedtuple("players", ['hand1', 'hand2'])
PLAYERS = asyncio.Queue()
PL_LIST = []

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

def kill_game(player_list):
    """
    Closes the player's connections upon error.
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
    Create a deck of 0 - 51 ints (each rep. a card/suit combo)
    Shuffle the deck
    Split the deck into halfs (one for each player)
    Create a list of the lists of cards
    """
    deck = list(range(0, 52))
    random.shuffle(deck)
    first_half = deck[0:26]
    second_half = deck[26:52]
    player_hands = []
    player_hands.append(bytes(first_half))
    player_hands.append(bytes(second_half))
    return player_hands

def serve_game(reader, writer):
    """Create a player list so that we can enummerate two at a time
    Once we have two players, populate a Game-tuple for the pair
        Create a Task, which calls game_play function with the Game-tuple info
        Prints to ensure that round between those players is over.
    """
    PL_LIST.append((reader, writer))

    if len(PL_LIST) >= 2:
        gameround = Game([PL_LIST.pop()], [PL_LIST.pop()])
        single_game = asyncio.Task(game_play(gameround))
        try:
            PLAYERS.put_nowait(gameround)
        except asyncio.QueueFull:
            logging.error("Queue is full...")
        def task_done(task):
            """Simply prints that the task is done """
            print("Task{0} is complete".format(task))
        single_game.add_done_callback(task_done)


async def game_play(gameround):
    """ This is where the actual game play takes place
    """
    #Get the players hands
    player1 = gameround.p1
    p1_reader = player1[0][0]
    p1_writer = player1[0][1]
    player2 = gameround.p2
    p2_reader = player2[0][0]
    p2_writer = player2[0][1]

    #Get the player's initial responses
    p1_res = await p1_reader.readexactly(2)
    p2_res = await p2_reader.readexactly(2)

    #Make sure first request from players is 'want game'
    if p1_res != b'\0\0' or p2_res != b'\0\0':
        logging.debug("Didn't really want to play the game, huh?")
        kill_game([p1_writer, p2_writer])
        return
    #Otherwise the players sent a valid intial responses
    #Deal player hands
    player_hands = deal_cards()
    p_cards = Players(player_hands[0], player_hands[1])
    p_hand1 = p_cards[0]
    p_hand2 = p_cards[1]

    #Check for server errors
    numhands = len(player_hands)
    numcards1 = len(p_hand1)
    numcards2 = len(p_hand2)
    #Server did not give them the correct number of cards
    if numhands != 2 or numcards1 != 26 or numcards2 != 26:
        logging.debug("Server's Mistake in dealing!")
        kill_game([p1_writer, p2_writer])
        return
    #Dealing hand to each - start of game
    p1_writer.write(b'\1' + p_hand1)
    p2_writer.write(b'\1' + p_hand2)

    #Card comparisons
    game_round = 0
    while game_round < 26:
        play1res = await p1_reader.readexactly(2)
        play2res = await p2_reader.readexactly(2)

        #Make sure their request is 'play card'
        if play1res[0] != 2 or play2res[0] != 2:
            logging.debug("Player did not send 'Play Card' command")
            kill_game([p1_writer, p2_writer])
            return
        p1_card = play1res[1]
        p2_card = play2res[1]

        #card is NOT in their hands
        b_card1 = bytes([p1_card])
        b_card2 = bytes([p2_card])

        if p_hand1.find(b_card1) == -1 or p_hand2.find(b_card2) == -1:
            logging.debug("Played a card not in your hand")
            kill_game([p1_writer, p2_writer])
            return

        #not really performing this, but oh well
        p_hand1.replace(b_card1, b'--')
        p_hand2.replace(b_card2, b'--')

        result = compare_cards(p1_card, p2_card)
        if result == 0:
            p1_writer.write(b'\3\1')
            p2_writer.write(b'\3\1')
        elif result == -1: #player 1 loses
            p1_writer.write(b'\3\2')
            p2_writer.write(b'\3\0')
        elif result == 1: #player 2 loses
            p1_writer.write(b'\3\0')
            p2_writer.write(b'\3\2')
        else:
            logging.debug("Game result error, got: %d", result)
            kill_game([player1, player2])
            return
        game_round += 1
    kill_game([p1_writer, p2_writer])
    return

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
        logging.debug("Game complete,  I %s", result)
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
    loop = asyncio.get_event_loop()
    if args[0] == "server":
        coroutine = asyncio.start_server(serve_game, host=host, port=port, loop=loop)
        server = loop.run_until_complete(coroutine)
        try:
            loop.run_forever()
            # your server should serve clients until the user presses ctrl+c
            #serve_game(host, port)
        except KeyboardInterrupt:
            server.close()
            loop.run_until_complete(server.wait_closed())
            pass
        return
    #else:
        #loop = asyncio.get_event_loop()

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
