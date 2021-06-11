class OneVsAllGameSession:
    sessionID = None
    userinfos = None
    sessionComplete = False
    gamemode = None

    def __init__(self, sessionID, usersid, userssio, usersname):
        self.userinfos = {0: {'claimed': False, 'complete': False, 'started': False,
                              'score': 0, 'bot': False},
                          1: {'claimed': False, 'complete': False, 'started': False,
                              'score': 0, 'bot': False},
                          2: {'claimed': False, 'complete': False, 'started': False,
                              'score': 0, 'bot': False}
                          }
        self.sessionComplete = False
        self.sessionID = sessionID
        self.gamemode = 'onevsall'

        for idx in range(len(userssio)):
            self.userinfos[userssio[idx]] = self.userinfos.pop(idx)
            self.userinfos[userssio[idx]]['userid'] = usersid[idx]
            self.userinfos[userssio[idx]]['name'] = usersname[idx]
            print("Start Claimed: ", self.userinfos[userssio[idx]]['claimed'])

    def setgamemode(self, gamemode):
        self.gamemode = gamemode

    def getgamemode(self):
        return self.gamemode

    def userleft(self, userid):
        print("MAIN MOMO:From: {} player: {} left the game".format(
            self.userinfos[userid]['team'], self.userinfos[userid]['name']))
        self.sessioncomplete(userid)
        self.setscore(userid, -1)

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

    def claimsession(self, userid):
        self.userinfos[userid]['claimed'] = True
        if self.didallclaimsession():
            return self.getsessionusers()
        return None

    def setscore(self, userid, score):
        print('MAIN MOMO: Setting score for {}'.format(self.userinfos[userid]['team']))
        print("MAIN MOMO: Setting score for User: {}, SCORE: {}".format(self.userinfos[userid]['name'], score))
        self.userinfos[userid]['score'] = score

    def getscore(self, userid):
        users = self.getsessionusers()
        ret = {}
        for user in users:
            if userid != user:
                ret[user] = self.userinfos[user]['score']
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
        retdict = {}
        print('more: ', self.teamonescore > self.teamtwoscore)
        if self.teamonescore > self.teamtwoscore:
            retdict['winningteam'] = 'teamone'
            retdict['winnerscore'] = self.teamonescore
        else:
            retdict['winningteam'] = 'teamtwo'
            retdict['winnerscore'] = self.teamtwoscore
        return retdict
