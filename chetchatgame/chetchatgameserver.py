import socketio
import haversine as hs
import firebase_admin
from firebase_admin import credentials, auth
from chetchatgame import gamesession
from chetchatgame import partygamesession
from chetchatgame import onevsallgamesession
import collections
from chetchatgame import playerstates as state

class ChetChatGameServer(socketio.AsyncNamespace):
    sio = None
    connectedusers = {}
    offeredservices = {}
    searchingusers = {}
    searchingusersfortwovstwo = {}
    searchinguserforonevsall = {}
    activegamesessions = {}

    cred = None

    def __init__(self, namespace):
        socketio.AsyncNamespace.__init__(self, namespace=namespace)
        self.cred = credentials.Certificate("serviceaccountkey.json")
        firebase_admin.initialize_app(self.cred)

    @classmethod
    def configure(cls, sio: socketio.Server):
        cls.sio = sio
        # server_methods = [m[0] for m in inspect.getmembers(cls, predicate=inspect.isfunction) if m[0].startswith('on_')]
        # for method in inspect.getmembers(cls.game_class, predicate=inspect.ismethod):
        #     if method[0] in server_methods:
        #         raise NameError(f'A event handler for {method[0]} already exists in the server interface.')
        #     if method[0].startswith('on_'):
        #         cls.sio.on(method[0][3:], handler=method[1])

    async def on_connect(self, sid, environ):
        print(f'MAIN MOMO: Client {sid} connected')
        if sid not in self.offeredservices:
            self.offeredservices[sid] = {}
            self.offeredservices[sid]["offeredservices"] = []
        await self.sio.send(f'Connected to MOMO server', room=sid)

    async def removealluserdetailsfromMOMO(self, sid):
        if sid in self.searchingusers:
            print("MAIN MOMO: Removing User: {} from searching queue: {}".format(self.getusername(sid), sid))
            self.searchingusers.pop(sid)
            print("MAIN MOMO: Number of searching Users: {}".format(len(self.searchingusers)))

        if sid in self.searchingusersfortwovstwo:
            print("MAIN MOMO: Removing User: {} from Party searching queue: {}".format(self.getusername(sid), sid))
            self.searchingusersfortwovstwo.pop(sid)
            await self.send_two_vs_two_searching_count()
            print("MAIN MOMO: Number of Party Game searching Users: {}".format(len(self.searchingusersfortwovstwo)))

        if sid in self.searchinguserforonevsall:
            print("MAIN MOMO: Removing User: {} from Party searching queue: {}".format(self.getusername(sid), sid))
            self.searchinguserforonevsall.pop(sid)
            await  self.send_one_vs_all_searching_count()
            print("MAIN MOMO: Number of Party Game searching Users: {}".format(len(self.searchinguserforonevsall)))

        if sid in self.offeredservices:
            self.offeredservices.pop(sid)

        if sid in self.connectedusers:
            print("MAIN MOMO: Removing User: {} from MOMO: {}".format(self.getusername(sid), sid))

            if self.connectedusers[sid]['receivedrequest'] and not self.connectedusers[sid]['ingame']:
                print("MAIN MOMO: User: {} Disconnected while Game request".format(self.getusername(sid)))
                otherplayer = {}
                otherplayer['sid'] = self.connectedusers[sid]['otherplayersid']
                await self.on_request_rejected(sid, otherplayer)

            userinfo = self.connectedusers.pop(sid)
            sessionid = userinfo['assignedsessionid']

            if sessionid in self.activegamesessions:
                gamesession = self.activegamesessions[sessionid]
                gamesession.userleft(sid)
                users = gamesession.getsessionusers()

                if gamesession.getgamemode() == state.GameState.local:
                    for user in users:
                        if user != sid and user in self.connectedusers:
                            print("MAIN MOMO: Calling session complete for User: {} because the other player left: {}"
                                  .format(self.getusername(user), self.getusername(sid)))
                            await self.on_session_complete(user, sessionid)

                if gamesession.getgamemode() == state.GameState.twovstwo:
                    for user in users:
                        if user != sid and user in self.connectedusers:
                            if gamesession.completedsession(user):
                                await self.on_session_complete(user, sessionid)
                            elif gamesession.getteamonecount() < 1 and gamesession.getteamtwocount() > 0:
                                print("MAIN MOMO:From:Calling session complete since"
                                      " All the players from Team One left the game")
                                await self.on_session_complete(user, sessionid)
                            elif gamesession.getteamtwocount() < 1 and gamesession.getteamonecount() > 0:
                                print("MAIN MOMO:From:Calling session complete since "
                                      "All the players from Team Two left the game")
                                await self.on_session_complete(user, sessionid)

                if gamesession.getgamemode() == state.GameState.onevsall:
                    for user in users:
                        if user != sid and user in self.connectedusers:
                            if gamesession.getsessionplayercount() < 2:
                                print("MAIN MOMO: Calling session complete for User: {} because the other players left"
                                      .format(self.getusername(user)))
                                await self.on_session_complete(user, sessionid)

    async def on_disconnect(self, sid):
        print(f'MAIN MOMO: Client {sid} DISCONNECTED!!!')
        await self.removealluserdetailsfromMOMO(sid)

    async def on_signout(self, sid):
        print(f'MAIN MOMO: Client {sid} SIGNED OUT! BYE!')
        await self.removealluserdetailsfromMOMO(sid)

    async def on_message(self, sid, message):
        print("MAIN MOMO: Recieved Message: {}".format(message))
        await self.sio.emit('message', data="HEY BRO PRPO", room=sid)
        pass

    # PROFILE SYSTEM
    async def on_authenticateuser(self, sid, userinfos):
        print("MAIN MOMO: Authenticate for User: {}".format(sid))
        token = userinfos['token']
        decoded_token = auth.verify_id_token(token)
        userdict = {}

        if sid not in self.connectedusers:
            userdict['userid'] = decoded_token['uid']
            userdict['name'] = userinfos['name']
            userdict['assignedsessionid'] = ''
            userdict['lat'] = 0
            userdict['lon'] = 0
            userdict['receivedrequest'] = False
            userdict['ingame'] = False
            userdict['otherplayersid'] = ''
            self.connectedusers[sid] = userdict
            print("MAIN MOMO: Added User to MOMO: {}".format(self.getusername(sid)))
        else:
            print("MAIN MOMO: User already in MOMO: {}".format(self.getusername(sid)))
        return userdict

    def getusername(self, sid):
        if sid in self.connectedusers:
            return self.connectedusers[sid]['name']
        return ""

    # GAME SERVER

    async def on_update_location(self, sid, findinfos):
        if sid in self.connectedusers:
            self.connectedusers[sid]['lat'] = findinfos['lat']
            self.connectedusers[sid]['lon'] = findinfos['lon']

    async def on_get_players(self, sid):
        if sid in self.connectedusers:
            print('Getting Info')
            targetlatlon = (self.connectedusers[sid]['lat'], self.connectedusers[sid]['lon'])
            sorteddict = {}
            returnusersdict = {}
            locationdict = {'sid': 0, 'name': 'new'}
            for user in self.connectedusers:
                if not self.connectedusers[user]['receivedrequest']:
                    if sid != user:
                        print(user)
                        otherlatlon = (self.connectedusers[user]['lat'], self.connectedusers[user]['lon'])
                        if otherlatlon[0] != 0.0 and otherlatlon[1] != 0.0 and targetlatlon[0] != 0.0 and targetlatlon[
                            1] != 0.0:
                            locationdict['sid'] = user
                            locationdict['name'] = self.connectedusers[user]['name']
                            sorteddict[self.calculatedistancebetweenlocations(targetlatlon, otherlatlon)] = dict(
                                locationdict)
                            print("Added")
                            print(sorteddict[self.calculatedistancebetweenlocations(targetlatlon, otherlatlon)])
            if sorteddict:
                i = 0
                sorteddict = collections.OrderedDict(sorted(sorteddict.items()))
                for k, v in sorteddict.items():
                    returnusersdict[i] = v
                    i = i + 1
            print('Return Dict', returnusersdict)
            await self.sio.emit('get_player_list', data=returnusersdict, room=sid)

    async def on_send_game_request(self, sid, otherplayerdict):
        if sid in self.connectedusers:
            otherplayersid = otherplayerdict['sid']
            self.connectedusers[sid]['receivedrequest'] = True
            self.connectedusers[sid]['otherplayersid'] = otherplayersid
            print("MAIN MOMO: Sent Game Request To User: {}".format(self.getusername(otherplayersid)))
            if otherplayersid in self.connectedusers:
                if not self.connectedusers[otherplayersid]['receivedrequest']:
                    print("MAIN MOMO: Recived Game Request From User: {}".format(self.getusername(sid)))
                    self.connectedusers[otherplayersid]['receivedrequest'] = True
                    self.connectedusers[otherplayersid]['otherplayersid'] = sid
                    print('Self Player: ', self.connectedusers[otherplayersid]['otherplayersid'])
                    returnusersdict = {}
                    returnusersdict['sid'] = sid
                    returnusersdict['name'] = self.connectedusers[sid]['name']
                    await self.sio.emit('game_request_received', data=returnusersdict, room=otherplayersid)

    async def on_request_rejected(self, sid, otherplayerdict):
        if sid in self.connectedusers:
            otherplayersid = otherplayerdict['sid']
            self.connectedusers[sid]['receivedrequest'] = False
            self.connectedusers[sid]['otherplayersid'] = ''
            print("MAIN MOMO: User: {} Rejected Game Request ".format(self.getusername(sid)))

            if otherplayersid in self.connectedusers:
                self.connectedusers[otherplayersid]['receivedrequest'] = False
                self.connectedusers[otherplayersid]['otherplayersid'] = ''
                returnusersdict = {}
                returnusersdict['sid'] = sid
                returnusersdict['name'] = self.connectedusers[sid]['name']
                await self.sio.emit('game_request_rejected', room=otherplayersid)

    async def on_start_game(self, sid, otherplayer):
        print('start Clicked')
        otherplayersid = otherplayer['sid']
        if sid in self.connectedusers and otherplayersid in self.connectedusers:
            user1 = sid
            user2 = otherplayersid
            print('user1 ', user1)
            print('user2 ', user2)
            sessioninfo = self.creategamesession(user1, user2)
            sessionid = sessioninfo['sessionid']
            self.connectedusers[user1]['assignedsessionid'] = sessionid
            self.connectedusers[user1]['ingame'] = True
            self.connectedusers[user1]['otherplayersid'] = ''
            self.connectedusers[user2]['assignedsessionid'] = sessionid
            self.connectedusers[user2]['ingame'] = True
            self.connectedusers[user2]['otherplayersid'] = ''
            await self.sio.emit('game_found', data=sessioninfo, room=user1)
            await self.sio.emit('game_found', data=sessioninfo, room=user2)
        pass

    async def on_find_game(self, sid, findinfos):
        print("MAIN MOMO: Find Game for User: {}".format(self.getusername(sid)))
        print("MAIN MOMO: Adding User: {} to searching queue".format(self.getusername(sid)))
        print("MAIN MOMO: Number of searching Users: {}".format(len(self.searchingusers)))
        self.searchingusers[sid] = findinfos
        users_finding_game = self.getappropriateuser(sid)
        if users_finding_game is not None:
            user1 = users_finding_game[0]
            user2 = users_finding_game[1]
            sessioninfo = self.creategamesession(user1, user2)
            sessionid = sessioninfo['sessionid']
            self.connectedusers[user1]['assignedsessionid'] = sessionid
            self.connectedusers[user1]['ingame'] = True
            self.connectedusers[user2]['assignedsessionid'] = sessionid
            self.connectedusers[user2]['ingame'] = True
            await self.sio.emit('game_found', data=sessioninfo, room=users_finding_game[0])
            await self.sio.emit('game_found', data=sessioninfo, room=users_finding_game[1])
        pass

    async def on_find_game_two_vs_two(self, sid, findinfos):
        print("MAIN MOMO: Find Game for User: {}".format(self.getusername(sid)))
        print("MAIN MOMO: Adding User: {} to searching queue".format(self.getusername(sid)))
        print("MAIN MOMO: Number of searching Users: {}".format(len(self.searchingusersfortwovstwo)))

        self.searchingusersfortwovstwo[sid] = findinfos
        await self.send_two_vs_two_searching_count()

        if self.searchingusersfortwovstwo is not None and len(self.searchingusersfortwovstwo.keys()) > 3:
            users = []
            for user in self.searchingusersfortwovstwo:
                users.append(user)

            for user in users:
                self.searchingusersfortwovstwo.pop(user)

            sessioninfo = self.create2vs2gamesession(users)
            sessionid = sessioninfo['sessionid']

            for user in users:
                self.connectedusers[user]['assignedsessionid'] = sessionid
                self.connectedusers[user]['ingame'] = True

            for user in users:
                await self.sio.emit('two_vs_two_game_found', data=sessioninfo, room=user)
        pass

    async def on_find_game_one_vs_all(self, sid, findinfos):
        print("MAIN MOMO: Find Game for User: {}".format(self.getusername(sid)))
        print("MAIN MOMO: Adding User: {} to searching queue".format(self.getusername(sid)))
        print("MAIN MOMO: Number of searching Users: {}".format(len(self.searchinguserforonevsall)))

        self.searchinguserforonevsall[sid] = findinfos
        if self.searchinguserforonevsall is not None and len(self.searchinguserforonevsall.keys()) > 4:
            users = []
            for user in self.searchinguserforonevsall:
                users.append(user)

            for user in users:
                self.searchinguserforonevsall.pop(user)

            sessioninfo = self.createonevsallgamesession(users)
            sessionid = sessioninfo['sessionid']

            for user in users:
                self.connectedusers[user]['assignedsessionid'] = sessionid
                self.connectedusers[user]['ingame'] = True

            for user in users:
                await self.sio.emit('one_vs_all_game_found', data=sessioninfo, room=user)
        pass

    async def send_two_vs_two_searching_count(self):
        ret = {'searchingusers': len(self.searchingusersfortwovstwo)}
        for user in self.searchingusersfortwovstwo:
            if user in self.connectedusers:
                await self.sio.emit('two_vs_two_player_count', data=ret, room=user)
        pass

    async def send_one_vs_all_searching_count(self):
        ret = {'searchingusers': len(self.searchinguserforonevsall)}
        for user in self.searchinguserforonevsall:
            if user in self.connectedusers:
                await self.sio.emit('one_vs_all_player_count', data=ret, room=user)
        pass

    async def on_cancel_find_game(self, sid):
        if sid in self.searchingusers:
            print("MAIN MOMO: Cancelled Find Game for User: {}".format(self.getusername(sid)))
            self.searchingusers.pop(sid)
            await self.sio.emit('find_game_cancelled', room=sid)
        elif sid in self.searchingusersfortwovstwo:
            print("MAIN MOMO: Cancelled Find Game for User: {}".format(self.getusername(sid)))
            self.searchingusersfortwovstwo.pop(sid)
            await self.send_two_vs_two_searching_count()
            await self.sio.emit('find_game_cancelled', room=sid)
        elif sid in self.searchinguserforonevsall:
            print("MAIN MOMO: Cancelled Find Game for User: {}".format(self.getusername(sid)))
            self.searchinguserforonevsall.pop(sid)
            await  self.send_one_vs_all_searching_count()
            await self.sio.emit('find_game_cancelled', room=sid)
        else:
            print("MAIN MOMO: Not searching game for User: {}".format(self.getusername(sid)))

    def calculatedistancebetweenlocations(self, loc1, loc2):
        # print('Distance: ', hs.haversine(loc1, loc2))
        return hs.haversine(loc1, loc2)

    def getappropriateuser(self, sid):
        targetuserinfos = self.searchingusers[sid]
        targetmaxdistance = targetuserinfos['maxdistance']
        targetlatlon = (targetuserinfos['lat'], targetuserinfos['lon'])
        for othersid in self.searchingusers:
            if othersid == sid:
                continue

            otherfindinfos = self.searchingusers[othersid]
            othermaxdistance = otherfindinfos['maxdistance']
            otherlatlon = (otherfindinfos['lat'], otherfindinfos['lon'])
            if otherlatlon[0] != 0.0 and otherlatlon[1] != 0.0 and targetlatlon[0] != 0.0 and targetlatlon[1] != 0.0:
                distance = self.calculatedistancebetweenlocations(otherlatlon, targetlatlon)
                if distance < targetmaxdistance and distance < othermaxdistance:
                    self.searchingusers.pop(sid)
                    print("Removed User: {} from search queue".format(self.getusername(sid)))
                    self.searchingusers.pop(othersid)
                    print("Removed User: {} from search queue".format(self.getusername(othersid)))
                    return (othersid, sid)
        return None

    def creategamesession(self, user1, user2):
        print("MAIN MOMO: Creating game session for Users: {} and {}".format(self.getusername(user1),
                                                                             self.getusername(user2)))
        sessionid = user1 + user2
        user1id = self.connectedusers[user1]['userid']
        user2id = self.connectedusers[user2]['userid']
        user1name = self.connectedusers[user1]['name']
        user2name = self.connectedusers[user2]['name']
        gamesessioninstance = gamesession.GameSession(sessionID=sessionid, user1id=user1id, user2id=user2id,
                                                      user1sio=user1, user2sio=user2, user1name=user1name,
                                                      user2name=user2name)
        print("MAIN MOMO: Adding active session: {}".format(sessionid))

        self.activegamesessions[sessionid] = gamesessioninstance
        retval = {}
        retval['user1id'] = user1id
        retval['user2id'] = user2id
        retval['user1name'] = user1name
        retval['user2name'] = user2name
        retval['sessionid'] = sessionid
        return retval

    def create2vs2gamesession(self, users):
        sessionid = users[0] + users[1]
        userid = []
        username = []
        print('MAIN MOMO: Creating game session for Users:')
        for user in users:
            print('MAIN MOMO:User: {}'.format(self.getusername(user)))
            print('user sid: ', user)
            print('user id: ',self.connectedusers[user]['userid'])
            print('user name: ', self.connectedusers[user]['name'])
            userid.append(self.connectedusers[user]['userid'])
            username.append(self.connectedusers[user]['name'])

        gamesessioninstance = partygamesession.PartyGameSession(sessionID=sessionid, usersid=userid,
                                                                userssio=users, usersname=username)
        print("MAIN MOMO: Adding active session: {}".format(sessionid))

        self.activegamesessions[sessionid] = gamesessioninstance

        retval = {}
        for user in range(len(users)):
            retval[user] = {'userid': userid[user]}
            retval[user] = {'username': username[user]}

        retval['sessionid'] = sessionid
        return retval

    def createonevsallgamesession(self, users):
        sessionid = users[0] + users[1]
        userid = []
        username = []
        print('MAIN MOMO: Creating game session for Users:')
        for user in users:
            print('MAIN MOMO:User: {}'.format(self.getusername(user)))
            print('user sid: ', user)
            print('user id: ', self.connectedusers[user]['userid'])
            print('user name: ', self.connectedusers[user]['name'])
            userid.append(self.connectedusers[user]['userid'])
            username.append(self.connectedusers[user]['name'])

        gamesessioninstance = onevsallgamesession.OneVsAllGameSession(sessionID=sessionid, usersid=userid,
                                                                userssio=users, usersname=username)
        print("MAIN MOMO: Adding active session: {}".format(sessionid))

        self.activegamesessions[sessionid] = gamesessioninstance

        retval = {}
        for user in range(len(users)):
            retval[user] = {'userid': userid[user]}
            retval[user] = {'username': username[user]}

        retval['sessionid'] = sessionid
        return retval

    async def on_claim_game_session(self, sid, gamesessionid):
        print("MAIN MOMO: Claiming game session for User: {}".format(self.getusername(sid)))
        gamesession = self.activegamesessions[gamesessionid]
        claimresult = gamesession.claimsession(sid)
        if claimresult is not None:
            for user in claimresult:
                print('Starting session', user)
                await self.sio.emit('start_session', room=user)

    async def on_claim_2vs2_game_session(self, sid, gamesessionid):
        print("MAIN MOMO: Claiming game session for User: {}".format(self.getusername(sid)))
        gamesession = self.activegamesessions[gamesessionid]
        claimresult = gamesession.claimsession(sid)
        teamname = {}
        if claimresult is not None:
            for user in claimresult:
                print('Starting session', user)
                teamname['teamname'] = gamesession.getteamname(user)
                await self.sio.emit('start_session_two_vs_two', data=teamname, room=user)

    async def on_claim_one_vs_all_game_session(self, sid, gamesessionid):
        print("MAIN MOMO: Claiming game session for User: {}".format(self.getusername(sid)))
        gamesession = self.activegamesessions[gamesessionid]
        claimresult = gamesession.claimsession(sid)
        if claimresult is not None:
            for user in claimresult:
                print('Starting session', user)
                await self.sio.emit('start_session_one_vs_all', room=user)

    async def on_starting_session(self, sid, sessionid):
        if sessionid in self.activegamesessions:
            print("MAIN MOMO: Starting game session for User: {}".format(self.getusername(sid)))
            gamesession = self.activegamesessions[sessionid]
            gamesession.sessionstart(sid)
        else:
            print("MAIN MOMO: Unable to start game session for User: {}".format(self.getusername(sid)))

    async def on_session_score(self, sid, sessionscoredict):
        sessionid = sessionscoredict['SESSION_ID']
        score = sessionscoredict['SCORE']
        if sessionid in self.activegamesessions:
            gamesession = self.activegamesessions[sessionid]
            gamesession.setscore(sid, score)
            users = gamesession.getsessionusers()
            if gamesession.getgamemode() == state.GameState.local:
                if users[0] != sid:
                    await self.sio.emit('opponent_score', data=sessionscoredict, room=users[0])
                if users[1] != sid:
                    await self.sio.emit('opponent_score', data=sessionscoredict, room=users[1])

            if gamesession.getgamemode() == state.GameState.twovstwo:
                for user in users:
                    scoredict = gamesession.getscore(user)
                    await self.sio.emit('party_score', data=scoredict, room=user)

            if gamesession.getgamemode() == state.GameState.onevsall:
                print("one vs all")
                for user in users:
                    print(user)
                    scoredict = gamesession.getscore(user)
                    await self.sio.emit('one_vs_all_score', data=scoredict, room=user)
        pass

    async def on_send_message(self, sid, sessionmessagedict):
        sessionid = sessionmessagedict['SESSION_ID']
        message = sessionmessagedict['MESSAGE']
        if sessionid in self.activegamesessions:
            gamesession = self.activegamesessions[sessionid]
            users = gamesession.getsessionusers()

            if gamesession.getgamemode() == state.GameState.local:
                for user in users:
                    if user != sid:
                        await self.sio.emit('opponent_message', data=sessionmessagedict, room=user)

            if gamesession.getgamemode() == state.GameState.twovstwo:
                for user in users:
                    if user != sid:
                        if gamesession.getteamname(user) == 'teamone' and gamesession.getteamname(sid) == 'teamone':
                            await self.sio.emit('opponent_message', data=sessionmessagedict, room=user)
                        if gamesession.getteamname(user) == 'teamtwo' and gamesession.getteamname(sid) == 'teamtwo':
                            await self.sio.emit('opponent_message', data=sessionmessagedict, room=user)

            if gamesession.getgamemode() == state.GameState.onevsall:
                for user in users:
                    if user != sid:
                        await self.sio.emit('opponent_message', data=sessionmessagedict, room=user)
        pass

    async def on_play_now(self, sid, sessionid):
        if sessionid in self.activegamesessions:
            gamesession = self.activegamesessions[sessionid]
            users = gamesession.getsessionusers()
            for user in users:
                if user != sid:
                    await self.sio.emit('play_now_clicked', room=user)
        pass

    async def on_session_complete(self, sid, sessionid):
        print("MAIN MOMO: SESSION COMPLETE User: {} SessionID: {}".format(self.getusername(sid), sessionid))
        if sessionid not in self.activegamesessions:
            print("MAIN MOMO: SESSION NOT FOUND")
            return
        gamesession = self.activegamesessions[sessionid]
        sessioncompleteresult = gamesession.sessioncomplete(sid)
        if sessioncompleteresult is not None:
            print("MAIN MOMO: Removing active User: {} SessionID: {}".format(self.getusername(sid), sessionid))
            self.activegamesessions.pop(sessionid)

            for user in sessioncompleteresult:
                if user in self.connectedusers:
                    self.connectedusers[user]['assignedsessionid'] = ''
                    self.connectedusers[user]['ingame'] = False
                    self.connectedusers[user]['receivedrequest'] = False

            sessionresult = gamesession.getsessionresult()
            if gamesession.getgamemode() == state.GameState.local:
                print("MAIN MOMO: The Winner is User: {}".format(self.getusername(sessionresult['winnersid'])))
                for user in sessioncompleteresult:
                    await self.sio.emit('game_over', data=sessionresult, room=user)

            if gamesession.getgamemode() == state.GameState.twovstwo:
                print("MAIN MOMO: The Winning Team is: {}".format(sessionresult['winningteam']))
                for user in sessioncompleteresult:
                    await self.sio.emit('game_over_two_vs_two', data=sessionresult, room=user)

            if gamesession.getgamemode() == state.GameState.onevsall:
                print("MAIN MOMO: The Winner is User: {}".format(self.getusername(sessionresult['winnersid'])))
                for user in sessioncompleteresult:
                    await self.sio.emit('game_over_one_vs_all', data=sessionresult, room=user)
        pass
