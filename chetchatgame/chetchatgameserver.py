import socketio
import haversine as hs
import firebase_admin
from firebase_admin import credentials, auth
from chetchatgame import gamesession


class ChetChatGameServer(socketio.AsyncNamespace):
    sio = None
    connectedusers = {}
    offeredservices = {}
    searchingusers = {}
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
        if sid in self.offeredservices:
            self.offeredservices.pop(sid)
        if sid in self.connectedusers:
            print("MAIN MOMO: Removing User: {} from MOMO: {}".format(self.getusername(sid), sid))
            userinfo = self.connectedusers.pop(sid)
            sessionid = userinfo['assignedsessionid']
            if sessionid in self.activegamesessions:
                print("MAIN MOMO: User: {} has active session, so ending the session: {}".format(self.getusername(sid),
                                                                                                 sessionid))
                gamesession = self.activegamesessions[sessionid]
                gamesession.userleft(sid)
                users = gamesession.getsessionusers()
                for user in users:
                    if user != sid:
                        print(
                            "MAIN MOMO: Calling session complete for User: {} because the other player left: {}".format(
                                self.getusername(user), self.getusername(sid)))
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
            self.connectedusers[sid] = userdict
            print("MAIN MOMO: Added User to MOMO: {}".format(self.getusername(sid)))
        else:
            print("MAIN MOMO: User already in MOMO: {}".format(self.getusername(sid)))

        return userdict

    def getusername(self, sid):
        if sid in self.connectedusers:
            return self.connectedusers[sid]['name']
        return ""

    async def on_set_location(self, sid, location):
        if sid in self.connectedusers:
            self.connectedusers[sid]['lat']= location['lat']
            self.connectedusers[sid]['lon'] = location['lon']
            print("MAIN MOMO: User:{}".format(self.connectedusers[sid]['name']))
            print("MAIN MOMO: lat:{} ".format(self.connectedusers[sid]['lat']))
            print("MAIN MOMO: lon:{} ".format(self.connectedusers[sid]['lon']))

        if len(self.searchingusers) >= 1:
            returnusersdict = {}
            locationdict = {'lat': 0, 'lon': 0}
            for user in self.searchingusers:
                if user in self.connectedusers:
                    if sid != user:
                        print(user)
                        locationdict['lat'] = self.connectedusers[user]['lat']
                        locationdict['lon'] = self.connectedusers[user]['lon']
                        returnusersdict[user] = locationdict
                        print("Addded")
                        print(returnusersdict[user])
            await self.sio.emit('get_location', data=returnusersdict)

    # GAME SERVER
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
            self.connectedusers[user2]['assignedsessionid'] = sessionid
            await self.sio.emit('game_found', data=sessioninfo, room=users_finding_game[0])
            await self.sio.emit('game_found', data=sessioninfo, room=users_finding_game[1])
        pass

    async def on_cancel_find_game(self, sid):
        if sid in self.searchingusers:
            print("MAIN MOMO: Cancelled Find Game for User: {}".format(self.getusername(sid)))
            self.searchingusers.pop(sid)
            await self.sio.emit('find_game_cancelled', room=sid)
        else:
            print("MAIN MOMO: Not searching game for User: {}".format(self.getusername(sid)))

    def calculatedistancebetweenlocations(self, loc1, loc2):
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

    async def on_claim_game_session(self, sid, gamesessionid):
        print("MAIN MOMO: Claiming game session for User: {}".format(self.getusername(sid)))
        gamesession = self.activegamesessions[gamesessionid]
        claimresult = gamesession.claimsession(sid)
        if claimresult is not None:
            user1 = claimresult[0]
            user2 = claimresult[1]
            await self.sio.emit('start_session', room=user1)
            await self.sio.emit('start_session', room=user2)

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
            if users[0] != sid:
                await self.sio.emit('opponent_score', data=sessionscoredict, room=users[0])
            if users[1] != sid:
                await self.sio.emit('opponent_score', data=sessionscoredict, room=users[1])
        pass

    async def on_send_message(self, sid, sessionmessagedict):
        sessionid = sessionmessagedict['SESSION_ID']
        message = sessionmessagedict['MESSAGE']
        if sessionid in self.activegamesessions:
            gamesession = self.activegamesessions[sessionid]
            users = gamesession.getsessionusers()
            if users[0] != sid:
                await self.sio.emit('opponent_message', data=sessionmessagedict, room=users[0])
            if users[1] != sid:
                await self.sio.emit('opponent_message', data=sessionmessagedict, room=users[1])
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
            user1 = sessioncompleteresult[0]
            user2 = sessioncompleteresult[1]

            if user1 in self.connectedusers:
                self.connectedusers[user1]['assignedsessionid'] = ''

            if user2 in self.connectedusers:
                self.connectedusers[user2]['assignedsessionid'] = ''

            sessionresult = gamesession.getsessionresult()
            print("MAIN MOMO: The Winner is User: {}".format(self.getusername(sessionresult['winnersid'])))
            await self.sio.emit('game_over', data=sessionresult, room=user1)
            await self.sio.emit('game_over', data=sessionresult, room=user2)
        pass
