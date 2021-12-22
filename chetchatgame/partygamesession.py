from chetchatgame import playerstates as state

class PartyGameSession:
    sessionID = None
    userinfos = None
    sessionComplete = False
    teamonescore = 0
    teamtwoscore = 0
    gamemode = None
    teamonekeys = []
    teamtwokeys = []
    starttime = 0
    latency = 0

    def __init__(self, sessionID, usersid, userssio, usersname):
        self.userinfos = {0: {'claimed': False, 'complete': False, 'started': False,
                              'score': 0, 'bot': False, 'team': 'teamone'},
                          1: {'claimed': False, 'complete': False, 'started': False,
                              'score': 0, 'bot': False, 'team': 'teamone'},
                          2: {'claimed': False, 'complete': False, 'started': False,
                              'score': 0, 'bot': False, 'team': 'teamtwo'},
                          3: {'claimed': False, 'complete': False, 'started': False,
                              'score': 0, 'bot': False, 'team': 'teamtwo'}
                          }
        self.sessionComplete = False
        self.sessionID = sessionID
        self.gamemode = state.GameState.twovstwo

        for idx in range(len(userssio)):
            self.userinfos[userssio[idx]] = self.userinfos.pop(idx)
            self.userinfos[userssio[idx]]['userid'] = usersid[idx]
            self.userinfos[userssio[idx]]['name'] = usersname[idx]
            print("Start Claimed: ", self.userinfos[userssio[idx]]['claimed'])

        self.fillteamlist()

    def fillteamlist(self):
        users = self.getsessionusers()
        self.teamonekeys.clear()
        self.teamtwokeys.clear()
        for user in users:
            if self.userinfos[user]['team'] == 'teamone':
                self.teamonekeys.append(user)
            if self.userinfos[user]['team'] == 'teamtwo':
                self.teamtwokeys.append(user)

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

    def userleft(self, userid):
        print("MAIN MOMO:From: {} player: {} left the game".format(
            self.userinfos[userid]['team'], self.userinfos[userid]['name']))
        self.setscore(userid, -1)
        self.sessioncomplete(userid)
        self.resetteamname(userid)

    def completedsession(self, key):
        return self.userinfos[key]['complete']

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
        print('MAIN MOMO: Setting score for {}'.format(self.userinfos[userid]['team']))
        print("MAIN MOMO: Setting score for User: {}, SCORE: {}".format(self.userinfos[userid]['name'], score))
        self.userinfos[userid]['score'] = score

    def getscore(self, userid):
        self.teamonescore = self.userinfos[self.teamonekeys[0]]['score'] + self.userinfos[self.teamonekeys[1]]['score']
        self.teamtwoscore = self.userinfos[self.teamtwokeys[0]]['score'] + self.userinfos[self.teamtwokeys[1]]['score']
        teamname = self.getteamname(userid)
        ret = {}
        if teamname == 'teamone':
            ret['teamscore'] = self.teamonescore
            ret['opponentscore'] = self.teamtwoscore
        else:
            ret['teamscore'] = self.teamtwoscore
            ret['opponentscore'] = self.teamonescore
        return ret

    def resetscore(self, team):
        if team == 'teamone':
            self.teamonescore = -1
        else:
            self.teamtwoscore = -1


    def resetteamname(self, userid):
        self.userinfos[userid]['team'] = ''

    def getteamname(self, userid):
        return self.userinfos[userid]['team']

    def getteamonecount(self):
        teamcount = 0
        users = self.getsessionusers()
        for user in users:
            if self.userinfos[user]['team'] == 'teamone':
                teamcount += 1
        return teamcount

    def getteamtwocount(self):
        teamcount = 0
        users = self.getsessionusers()
        for user in users:
            if self.userinfos[user]['team'] == 'teamtwo':
                teamcount += 1
        return teamcount

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
