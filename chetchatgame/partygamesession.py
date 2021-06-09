
class PartyGameSession:
    sessionID = None
    userInfos = None
    sessionComplete = False
    teamonescore = 0
    teamtwoscore = 0
    gamemode = None

    def __init__(self, sessionID, usersid, userssio, usersname, gamemode):
        self.userInfos = {0: {'claimed': False, 'complete': False, 'started': False,
                              'score': 0, 'bot': False, 'team': 'teamone'},
                          1: {'claimed': False, 'complete': False, 'started': False,
                              'score': 0, 'bot': False, 'team' : 'teamone'},
                          2: {'claimed': False, 'complete': False, 'started': False,
                              'score': 0, 'bot': False, 'team': 'teamtwo'},
                          3: {'claimed': False, 'complete': False, 'started': False,
                              'score': 0, 'bot': False, 'team': 'teamtwo'}
                          }
        self.sessionComplete = False
        self.sessionID = sessionID
        self.gamemode = gamemode

        for idx in range(len(userssio)):
            self.userInfos[userssio[idx]] = self.userInfos.pop(idx)
            self.userInfos[userssio[idx]]['userid'] = usersid[idx]
            self.userInfos[userssio[idx]]['name'] = usersname[idx]
            print("Start Claimed: ", self.userInfos[userssio[idx]]['claimed'])

    def setgamemode(self, gamemode):
        self.gamemode = gamemode

    def getgamemode(self):
        return self.gamemode

    def userleft(self, userid):
        self.sessioncomplete(userid)
        self.setscore(userid, -1)

    def didallclaimsession(self):
        keys = self.userInfos.keys()
        print("All users: ", keys)
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
        #print("MAIN MOMO: Setting score for User: {}, SCORE: {}".format(self.userInfos[userid]['name'], score))
        self.userInfos[userid]['score'] = score
        users = self.getsessionusers()
        print('team name: ', self.userInfos[userid]['team'])
        if self.userInfos[userid]['team'] == 'teamone':
            self.teamonescore += score
            print('score: ', self.teamonescore)
        if self.userInfos[userid]['team'] == 'teamtwo':
            self.teamtwoscore += score

    def getscore(self, userid):
        teamname = self.getteamname(userid)
        ret = {}
        if teamname == 'teamone':
            ret['teamscore'] = self.teamonescore
            ret['opponentscore'] = self.teamtwoscore
        else:
            ret['teamscore'] = self.teamtwoscore
            ret['opponentscore'] = self.teamonescore
        return ret

    def getteamname(self, userid):
        return self.userInfos[userid]['team']

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
        if self.teamonescore > self.teamtwoscore:
            retdict['winningteam'] = 'teamone'
            retdict['winnerscore'] = self.teamonescore
        else:
            retdict['winningteam'] = 'teamtwo'
            retdict['winnerscore'] = self.teamtwoscore
        return retdict