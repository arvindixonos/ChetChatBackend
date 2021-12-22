from chetchatgame import playerstates as state

class GameSession:
    sessionID = None
    userinfos = None
    sessionComplete = False
    gamemode = ''
    starttime = 0
    latency = 0

    def __init__(self, sessionID, user1sio, user2sio, user1id, user2id, user1name, user2name):
        self.userinfos = {'user1id': {'claimed': False, 'complete': False, 'started': False, 'score': 0, 'bot': False},
                          'user2id': {'claimed': False, 'complete': False, 'started': False, 'score': 0, 'bot': False}}
        self.gamemode = state.GameState.national
        self.sessionComplete = False
        self.sessionID = sessionID
        self.userinfos[user1sio] = self.userinfos.pop('user1id')
        self.userinfos[user2sio] = self.userinfos.pop('user2id')
        self.userinfos[user1sio]['userid'] = user1id
        self.userinfos[user2sio]['userid'] = user2id
        self.userinfos[user1sio]['name'] = user1name
        self.userinfos[user2sio]['name'] = user2name

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

    def getgamemode(self):
        return self.gamemode

    def userleft(self, userid):
        print("MAIN MOMO: User: {} has active session, so ending the session: {}"
              .format(self.userinfos[userid]['name'], self.sessionID))
        self.sessioncomplete(userid)
        self.setscore(userid, -1)

    def didallclaimsession(self):
        keys = self.userinfos.keys()
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

    def getopponentsid(self, sid):
        users = self.getsessionusers()
        if users[0] == sid:
            return users[1]
        else:
            return users[0]


    def getsessionresult(self):
        retdict = {}
        users = self.getsessionusers()
        if self.userinfos[users[0]]['score'] > self.userinfos[users[1]]['score']:
            retdict['winnersid'] = users[0]
            retdict['winnerscore'] = self.userinfos[users[0]]['score']
            retdict['winneruserid'] = self.userinfos[users[0]]['userid']
            retdict['winnername'] = self.userinfos[users[0]]['name']
        else:
            retdict['winnersid'] = users[1]
            retdict['winnerscore'] = self.userinfos[users[1]]['score']
            retdict['winneruserid'] = self.userinfos[users[1]]['userid']
            retdict['winnername'] = self.userinfos[users[1]]['name']
        return retdict