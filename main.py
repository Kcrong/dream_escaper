# -*-coding: utf-8 -*-
from socket import *
import errno
from collections import defaultdict

import sys
import time
import thread

if len(sys.argv) < 3:
    print "Argv Error!"
    print "python %s [HOST] [PORT]" % sys.argv[0]
    exit()

else:
    print "%s: %s Listen" % (sys.argv[1], sys.argv[2])

RANDOM_VS = None


class GameClient:
    # 닉네임 리스트
    nick_index = defaultdict(list)

    def __init__(self, sock, addr, nick=None):
        # 자신의 소켓
        self.sock = sock
        self.nick = nick

        # 현재 대전 중인 상대
        self.vs = None

        GameClient.nick_index[nick].append(self)

    def __repr__(self):
        return "<Client %s>" % self.nick

    def start_battle(self, vs):
        # vs 는 파트너의 GameClient 객체
        self.vs = vs

    def finish_battle(self):
        self.vs = None

    @classmethod
    def find_client(cls, nick):
        try:
            return GameClient.nick_index[nick][0]
        except IndexError:
            return None

    @classmethod
    def remove_client(cls, nick):
        try:
            del GameClient.nick_index[nick]
        except KeyError:
            pass


def find_client(name):
    """
        # class 내부에서 Pre-index 해주는 방법으로 함. 가장 빠른 듯

        # 두 번째로 느림..
        # return [x for x in USER_LIST if x.name == 'as'][0]

        # 가장 느림..
        # return filter(lambda x: x.nick == name, USER_LIST)[0]
    """

    return GameClient.find_client(name)


def create_listen_socket():
    s = socket(AF_INET, SOCK_STREAM)
    s.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
    s.bind((sys.argv[1], int(sys.argv[2])))
    s.listen(5)

    return s


def add_client(client, addr, nick):
    """
    :param client: 클라이언트 소켓
    :param addr: 클라이언트 주소
    :param nick: 클라이언트 닉네임
    :return:
        중복되는 닉네임이 없을 경우: Client 객체 반환
        중복되는 닉네임이 있을 경우: None 반환
    """
    if GameClient.find_client(nick) is None:
        c = GameClient(client, addr, nick)
        client.send('t')
        print "%s 님이 입장하였습니다." % c.nick
        return c

    else:
        return None


def match_random(client, data):
    print "%s 님이 랜덤큐로 입장하였습니다." % client.nick
    global RANDOM_VS

    if RANDOM_VS is None:
        RANDOM_VS = client
    else:
        print "%s 님과 %s 님이 게임을 시작하였습니다." % (client.nick, RANDOM_VS.nick)
        RANDOM_VS.start_battle(client)
        RANDOM_VS.sock.send(client.nick)
        client.start_battle(RANDOM_VS)
        client.sock.send(RANDOM_VS.nick)
        RANDOM_VS = None


def match_client(client, nick):
    partner = None

    print "%s 님이 %s 에게 게임을 신청하였습니다." % (client.nick, nick)

    while partner is None:
        print "%s 을 찾는 중입니다." % nick
        partner = GameClient.find_client(nick)
        time.sleep(5)

    print "%s 님을 찾았습니다." % partner.nick

    client.start_battle(partner)

    print "%s 님을 대기중입니다." % partner.nick

    while True:
        if partner.vs == client:
            print "%s 님과 %s 님의 게임이 시작되었습니다." % (client.nick, partner.nick)
            client.sock.send('t')
            break
        else:
            time.sleep(5)


def send_info(client, data):
    print "%s 님이 %s 님에게: %s" % (client.nick, client.vs.nick, data)
    client.vs.sock.send(data)


def exit_user(client):
    print "%s 님이 퇴장하셨습니다." % client.nick

    try:
        client.vs.sock.send('X')
    except AttributeError:
        # 만약 client.vs.sock 이 None 이라면 (상대가 없는 상태라면)
        pass

    client.remove_client()
    return


command_dict = {
    'R': match_random,
    'F': match_client,
    'S': send_info,
}


# 위 방법으로 Switch Case 을 구현했으나, 함수별로 인자값 관리가 되질 않아 쓸데없는 비용이 발생한다.
# --> **args 사용

def get_client(client_sock, addr):
    client = None

    def how_to():
        return \
            """
            (Only First time.)
            [nick]: Add user
            - Success t
            - Fail f

            R: Find Random Partner
            - return Partner's Nick

            F[nick]: start game with [nick]
            - Success t
            - Fail f

            S: Send Packet to Partner
            - Success t
            - Fail f
            """

    # 클라이언트 닉네임 등록
    while client is None:
        data = client_sock.recv(1024)
        if len(data) == 0:
            break

        client = add_client(client_sock, addr, data)

    # 클라이언트 게임 이용 중
    while client is not None:
        try:
            tmp = client.sock.recv(1024)
            command = tmp[0]
            data = tmp[1:]

        except IndexError:
            break

        except error as e:
            # 난 reset by peer 에러만 본다.
            if e.errno != errno.ECONNRESET:
                raise

            exit_user(client)
            break

        try:
            command_dict[command](client, data)
        except KeyError:
            client.sock.send(how_to())
            # escape loop
            exit_user(client)
            break

    print "%s is Quit." % addr


if __name__ == '__main__':
    s = create_listen_socket()
    print "GameServer Start"
    while True:
        client, addr = s.accept()
        thread.start_new_thread(get_client, (client, addr[0],))
