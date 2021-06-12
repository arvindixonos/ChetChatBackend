from chetchatgame import playerstates as state

class GameSession:
    sessionID = None
    userInfos = None
    sessionComplete = False
    gamemode = ''

    def __init__(self, sessionID, user1sio, user2sio, user1id, user2id, user1name, user2name):
        self.userInfos = {  'user1id': {'claimed': False, 'complete': False, 'started': False, 'score': 0, 'bot': False},
                            'user2id': {'claimed': False, 'complete': False, 'started': False, 'score': 0, 'bot': False}}
        self.gamemode = state.GameState.local
        self.sessionComplete = False
        self.sessionID = sessionID
        self.userInfos[user1sio] = self.userInfos.pop('user1id')
        self.userInfos[user2sio] = self.userInfos.pop('user2id')
        self.userInfos[user1sio]['userid'] = user1id
        self.userInfos[user2sio]['userid'] = user2id
        self.userInfos[user1sio]['name'] = user1name
        self.userInfos[user2sio]['name'] = user2name

    def getgamemode(self):
        return self.gamemode

    def userleft(self, userid):
        print("MAIN MOMO: User: {} has active session, so ending the session: {}"
              .format(self.userInfos[userid]['name'], self.sessionID))
        self.sessioncomplete(userid)
        self.setscore(userid, -1)

    def didallclaimsession(self):
        keys = self.userInfos.keys()
        for key in keys:
            if self.userInfos[key]['claimed'] is False:
                return False
        return True

    def didallcompletesession(self):
        keys = self.userInfos.keys()
        for key in keys:
            if self.userInfos[key]['complete'] is False:
                return False
        return True

    def claimsession(self, userid):
        self.userInfos[userid]['claimed'] = True
        if self.didallclaimsession():
            return self.getsessionusers()
        return None

    def setscore(self, userid, score):
        print("MAIN MOMO: Setting score for User: {}, SCORE: {}".format(self.userInfos[userid]['name'], score))
        self.userInfos[userid]['score'] = score

    def sessioncomplete(self, userid):
        print("MAIN MOMO: Session complete for User: {}".format(self.userInfos[userid]['name']))
        self.userInfos[userid]['complete'] = True
        if self.didallcompletesession():
            return self.getsessionusers()
        return None

    def sessionstart(self, userid):
        self.userInfos[userid]['started'] = True

    def getsessionusers(self):
        return list(self.userInfos.keys())

    def getsessionresult(self):
        retdict = {}
        users = self.getsessionusers()
        if self.userInfos[users[0]]['score'] > self.userInfos[users[1]]['score']:
            retdict['winnersid'] = users[0]
            retdict['winnerscore'] = self.userInfos[users[0]]['score']
            retdict['winneruserid'] = self.userInfos[users[0]]['userid']
            retdict['winnername'] = self.userInfos[users[0]]['name']
        else:
            retdict['winnersid'] = users[1]
            retdict['winnerscore'] = self.userInfos[users[1]]['score']
            retdict['winneruserid'] = self.userInfos[users[1]]['userid']
            retdict['winnername'] = self.userInfos[users[1]]['name']
        return retdict