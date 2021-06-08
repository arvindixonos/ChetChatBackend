
class PartyGameSession:
    sessionID = None
    userInfos = None
    sessionComplete = False

    def __init__(self, sessionID, usersid, userssio, usersname):
        self.userInfos = {0: {'claimed': False, 'complete': False, 'started': False, 'score': 0, 'bot': False},
                          1: {'claimed': False, 'complete': False, 'started': False, 'score': 0, 'bot': False},
                          # 2: {'claimed': False, 'complete': False, 'started': False, 'score': 0, 'bot': False},
                          # 3: {'claimed': False, 'complete': False, 'started': False, 'score': 0, 'bot': False}}
                          }
        self.sessionComplete = False
        self.sessionID = sessionID
        i = 0
        for user in userssio:
            self.userInfos[user] = self.userInfos.pop(i)
            self.userInfos[user]['userid'] = usersid[i]
            self.userInfos[user]['name'] = usersname[i]
            print("Start Claimed: ", self.userInfos[user]['claimed'])
            i = i+1

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