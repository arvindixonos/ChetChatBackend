import operator
import collections
from chetchatgame import playerstates as state

class OneVsAllGameSession:
    sessionID = None
    userinfos = None
    sessionComplete = False
    gamemode = None
    sessionplayercount = 0
    starttime = 0
    latency = 0

    def __init__(self, sessionID, usersid, userssio, usersname):
        self.userinfos = {0: {'claimed': False, 'complete': False, 'started': False,
                              'score': 0, 'bot': False},
                          1: {'claimed': False, 'complete': False, 'started': False,
                              'score': 0, 'bot': False},
                          2: {'claimed': False, 'complete': False, 'started': False,
                              'score': 0, 'bot': False},
                          # 3: {'claimed': False, 'complete': False, 'started': False,
                          #     'score': 0, 'bot': False},
                          # 4: {'claimed': False, 'complete': False, 'started': False,
                          #     'score': 0, 'bot': False}
                          }

        self.sessionComplete = False
        self.sessionID = sessionID
        self.gamemode = state.GameState.onevsall
        self.sessionplayercount = len(userssio)

        for idx in range(len(userssio)):
            self.userinfos[userssio[idx]] = self.userinfos.pop(idx)
            self.userinfos[userssio[idx]]['userid'] = usersid[idx]
            self.userinfos[userssio[idx]]['name'] = usersname[idx]
            print("Start Claimed: ", self.userinfos[userssio[idx]]['claimed'])

    def getlatency(self):
        return self.latency

    def setlatency(self, t):
        if self.latency == 0:
            self.latency = t

    def getstarttime(self):
        return self.starttime

    def setstarttime(self, t):
        if self.starttime == 0:
            self.starttime = t

    def setgamemode(self, gamemode):
        self.gamemode = gamemode

    def getgamemode(self):
        return self.gamemode

    def reduceplayercount(self):
        self.sessionplayercount -= 1

    def getsessionplayercount(self):
        return self.sessionplayercount

    def completedsession(self, key):
        return self.userinfos[key]['complete']

    def userleft(self, userid):
        print("MAIN MOMO:From:Player: {} left the game".format(self.userinfos[userid]['name']))
        self.sessioncomplete(userid)
        self.setscore(userid, -1)
        self.reduceplayercount()

    def didallclaimsession(self):
        keys = self.userinfos.keys()
        print("All users: ", keys)
        for key in keys:
            if self.userinfos[key]['claimed'] is False:
                return False
        return True

    def didallcompletesession(self):
        keys = self.userinfos.keys()
        for key in keys:
            if self.userinfos[key]['complete'] is False:
                return False
        return True

    def forcecompletesession(self):
        keys = self.userinfos.keys()
        for key in keys:
            if self.userinfos[key]['complete'] is False:
                self.userinfos[key]['complete'] = True
        return self.getsessionusers()

    def claimsession(self, userid):
        self.userinfos[userid]['claimed'] = True
        if self.didallclaimsession():
            return self.getsessionusers()
        return None

    def setscore(self, userid, score):
        print("MAIN MOMO: Setting score for User: {}, SCORE: {}".format(self.userinfos[userid]['name'], score))
        self.userinfos[userid]['score'] = score

    def getscore(self, userid):
        users = self.getsessionusers()
        ret = {}
        for user in users:
            if userid != user:
                ret[user] = self.userinfos[user]['score']
        return ret

    def getopponentname(self, userid):
        users = self.getsessionusers()
        ret = {}
        for user in users:
            if userid != user:
                ret[user] = self.userinfos[user]['name']
        return ret

    def sessioncomplete(self, userid):
        print("MAIN MOMO: Session complete for User: {}".format(self.userinfos[userid]['name']))
        self.userinfos[userid]['complete'] = True
        if self.didallcompletesession():
            return self.getsessionusers()
        return None

    def sessionstart(self, userid):
        self.userinfos[userid]['started'] = True

    def getsessionusers(self):
        return list(self.userinfos.keys())

    def getsessionresult(self):
        score = {}
        retdict = {}

        users = self.getsessionusers()
        for user in users:
            print('user name: {} score: {}'.format(self.userinfos[user]['name'], self.userinfos[user]['score']))
            score[user] = self.userinfos[user]['score']

        sorted_x = sorted(score.items(), key=operator.itemgetter(1))
        sorted_dict = collections.OrderedDict(sorted_x)

        winnerlist = list(sorted_dict.keys())
        winnerid = winnerlist[len(winnerlist)-1]

        retdict['winnersid'] = winnerid
        retdict['winnerscore'] = self.userinfos[winnerid]['score']
        retdict['winneruserid'] = self.userinfos[winnerid]['userid']
        retdict['winnername'] = self.userinfos[winnerid]['name']
        return retdict
