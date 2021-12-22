import asyncio
import socketio
import haversine as hs
import firebase_admin
from firebase_admin import credentials, auth, firestore
from chetchatgame import gamesession
from chetchatgame import partygamesession
from chetchatgame import onevsallgamesession
from chetchatgame import gamesessionnational
import collections
from chetchatgame import playerstates as state
from datetime import datetime, timezone, timedelta
from chetchatgame import gameoverrewarddetails as endreward
from google.cloud.firestore_v1.transforms import DELETE_FIELD
import calendar


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
        # v = self.get_membership("fuuY8wZyDQPSrbLVG5GxqDQm6an1")
        print(self.get_value_from_db('fuuY8wZyDQPSrbLVG5GxqDQm6an1', 'last_refill_time'))

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
            await self.send_one_vs_all_searching_count()
            print("MAIN MOMO: Number of Party Game searching Users: {}".format(len(self.searchinguserforonevsall)))

        if sid in self.offeredservices:
            self.offeredservices.pop(sid)

        if sid in self.connectedusers:
            if self.connectedusers[sid]['receivedrequest'] and not self.connectedusers[sid]['ingame']:
                print("MAIN MOMO: User: {} Disconnected while Game request".format(self.getusername(sid)))
                otherplayer = {}
                otherplayer['sid'] = self.connectedusers[sid]['otherplayersid']
                await self.on_request_rejected(sid, otherplayer)

            userinfo = self.connectedusers.pop(sid)
            print("MAIN MOMO: Removing User: {} from MOMO: {}".format(self.getusername(sid), sid))

            sessionid = userinfo['assignedsessionid']

            if sessionid in self.activegamesessions:
                gamesession = self.activegamesessions[sessionid]
                gamesession.userleft(sid)
                users = gamesession.getsessionusers()

                if gamesession.getgamemode() == state.GameState.local:
                    if gamesession.didallcompletesession() is False:
                        self.update_heart_on_disconnect(userinfo['userid'])
                    for user in users:
                        if user != sid and user in self.connectedusers:
                            print("MAIN MOMO: Calling session complete for User: {} because the other player left: {}"
                                  .format(self.getusername(user), self.getusername(sid)))
                            await self.request_rejected_in_current_session(user)
                            await self.on_session_complete(user, sessionid)
                            await self.opponent_disconnect_from_current_session(user)

                if gamesession.getgamemode() == state.GameState.national:
                    if gamesession.didallcompletesession() is False:
                        self.update_heart_on_disconnect(userinfo['userid'])
                    for user in users:
                        if user != sid and user in self.connectedusers:
                            print("MAIN MOMO: Calling session complete for User: {} because the other player left: {}"
                                  .format(self.getusername(user), self.getusername(sid)))
                            await self.on_session_complete(user, sessionid)

                if gamesession.getgamemode() == state.GameState.twovstwo:
                    if gamesession.didallcompletesession() is False:
                        self.update_heart_on_disconnect(userinfo['userid'])
                    for user in users:
                        if user != sid and user in self.connectedusers:
                            if gamesession.completedsession(user):
                                await self.on_session_complete(user, sessionid)
                            elif gamesession.getteamonecount() < 1 and gamesession.getteamtwocount() > 0:
                                print("MAIN MOMO:From:Calling session complete since"
                                      " All the players from Team One left the game")
                                gamesession.resetscore('teamone')
                                await self.on_session_complete(user, sessionid)
                            elif gamesession.getteamtwocount() < 1 and gamesession.getteamonecount() > 0:
                                print("MAIN MOMO:From:Calling session complete since "
                                      "All the players from Team Two left the game")
                                gamesession.resetscore('teamtwo')
                                await self.on_session_complete(user, sessionid)

                if gamesession.getgamemode() == state.GameState.onevsall:
                    if gamesession.didallcompletesession() is False:
                        self.update_heart_on_disconnect(userinfo['userid'])
                    for user in users:
                        if user != sid and user in self.connectedusers:
                            if gamesession.completedsession(user):
                                await self.on_session_complete(user, sessionid)
                            if gamesession.getsessionplayercount() < 2:
                                print("MAIN MOMO: Calling session complete for User: {} because the other players left"
                                      .format(self.getusername(user)))
                                await self.on_session_complete(user, sessionid)

    async def on_disconnect(self, sid):
        print(f'MAIN MOMO: Client {sid} DISCONNECTED!!!')
        self.update_loggout_time(sid)
        await self.removealluserdetailsfromMOMO(sid)

    async def on_signout(self, sid):
        print(f'MAIN MOMO: Client {sid} SIGNED OUT! BYE!')
        self.update_loggout_time(sid)
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
            userdict['localgamepage'] = False
            userdict['otherplayersid'] = ''
            userdict['maxlocaldistance'] = 1
            userdict['profileid'] = 0
            userdict['membership'] = 3
            userdict['gender'] = 0
            self.connectedusers[sid] = userdict
            print("MAIN MOMO: Added User to MOMO: {}".format(self.getusername(sid)))
        else:
            print("MAIN MOMO: User already in MOMO: {}".format(self.getusername(sid)))
        return userdict

    def getusername(self, sid):
        if sid in self.connectedusers:
            return self.connectedusers[sid]['name']
        return ""

    def getprofileid(self, sid):
        if sid in self.connectedusers:
            return self.connectedusers[sid]['profileid']
        return 0

    # GAME SERVER
    def update_heart_on_disconnect(self, userid):
        val = 1
        self.set_heart_value_in_db(userid, 'heart', val)


    async def on_update_membership(self, sid, info):
        value = info['membership']
        if sid in self.connectedusers:
            self.connectedusers[sid]['membership'] = value
        pass

    async def on_update_gender(self, sid, info):
        value = info['gender']
        if sid in self.connectedusers:
            self.connectedusers[sid]['gender'] = value
        pass

    async def on_set_profile_id(self, sid, data):
        profileid = data['profileid']
        if sid in self.connectedusers:
            self.connectedusers[sid]['profileid'] = profileid
            print('player pro id', self.connectedusers[sid]['profileid'])
        pass

    async def on_local_game_page_selected(self, sid, pagevalue):
        localgamepage = pagevalue['localgamepage']
        if sid in self.connectedusers:
            self.connectedusers[sid]['localgamepage'] = localgamepage
        pass

    async def on_max_local_distance(self, sid, findinfo):
        maxlocaldistance = findinfo['maxlocaldistance']
        if sid in self.connectedusers:
            self.connectedusers[sid]['maxlocaldistance'] = maxlocaldistance
        pass

    async def on_update_location(self, sid, findinfos):
        if sid in self.connectedusers:
            self.connectedusers[sid]['lat'] = findinfos['lat']
            self.connectedusers[sid]['lon'] = findinfos['lon']
        pass

    async def on_get_players(self, sid):
        if sid in self.connectedusers:
            # print('Getting Info')
            targetlatlon = (self.connectedusers[sid]['lat'], self.connectedusers[sid]['lon'])
            print('MOMOMAIN: User', self.connectedusers[sid]['name'])
            # print(self.connectedusers[sid]['lat'], self.connectedusers[sid]['lon'])
            maxlocaldistance = self.connectedusers[sid]['maxlocaldistance']
            sorteddict = {}
            returnusersdict = {}
            locationdict = {'sid': 0, 'name': 'new'}
            for user in self.connectedusers:
                if sid != user:
                    if self.useravailabletoplay(user):
                        otherlatlon = (self.connectedusers[user]['lat'], self.connectedusers[user]['lon'])
                        # if otherlatlon[0] != 0.0 and otherlatlon[1] != 0.0 and targetlatlon[0] != 0.0 and targetlatlon[
                        #     1] != 0.0:
                        if self.validdistance(otherlatlon, targetlatlon, maxlocaldistance):
                            locationdict['sid'] = user
                            locationdict['name'] = self.connectedusers[user]['name']
                            locationdict['profilepic'] = self.connectedusers[user]['profileid']
                            locationdict['gender'] = self.connectedusers[user]['gender']
                            locationdict['membership'] = self.connectedusers[user]['membership']
                            sorteddict[self.calculatedistancebetweenlocations(targetlatlon, otherlatlon)] = dict(
                                locationdict)
                            print("Added")
                            # print(sorteddict[self.calculatedistancebetweenlocations(targetlatlon, otherlatlon)])
            if sorteddict:
                i = 0
                sorteddict = collections.OrderedDict(sorted(sorteddict.items()))
                for k, v in sorteddict.items():
                    returnusersdict[i] = v
                    i = i + 1
            print('Return Dict', returnusersdict)
            await self.sio.emit('get_player_list', data=returnusersdict, room=sid)
        pass

    def useravailabletoplay(self, user):
        if not self.connectedusers[user]['localgamepage']:
            return False
        if self.connectedusers[user]['receivedrequest']:
            return False
        if self.connectedusers[user]['ingame']:
            return False
        return True

    def validdistance(self, otherlatlon, targetlatlon, maxdistance):
        if otherlatlon[0] == 0.0 and otherlatlon[1] == 0.0:
            return False
        if targetlatlon[0] == 0.0 and targetlatlon[1] == 0.0:
            return False
        distance = self.calculatedistancebetweenlocations(otherlatlon, targetlatlon)
        if distance > maxdistance:
            return False
        return True

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
                    returnusersdict['gender'] = self.connectedusers[sid]['gender']
                    returnusersdict['membership'] = self.connectedusers[sid]['membership']
                    returnusersdict['profileid'] = self.connectedusers[sid]['profileid']
                    await self.sio.emit('game_request_received', data=returnusersdict, room=otherplayersid)

                    selfplayerdict = {}
                    otherplayerdict = {}
                    selfplayerdict['enemyprofileid'] = self.connectedusers[otherplayersid]['profileid']
                    print('Other player pro id', self.connectedusers[otherplayersid]['profileid'])
                    otherplayerdict['enemyprofileid'] = self.connectedusers[sid]['profileid']
                    print('Self player pro id', self.connectedusers[sid]['profileid'])

                    await self.sio.emit('other_player_profile_id', data=otherplayerdict, room=otherplayersid)
                    await self.sio.emit('other_player_profile_id', data=selfplayerdict, room=sid)
        pass

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
        pass

    async def request_rejected_in_current_session(self, otherplayersid):
        if otherplayersid in self.connectedusers:
            print("adasdasddsdasdasdasa asdasdsadasdasdasd : ", self.connectedusers[otherplayersid]["name"])
            self.connectedusers[otherplayersid]['receivedrequest'] = False
            self.connectedusers[otherplayersid]['otherplayersid'] = ''
            await self.sio.emit('game_request_rejected', room=otherplayersid)
        pass

    async def on_start_game(self, sid, otherplayer):
        print('start Clicked')
        otherplayersid = otherplayer['sid']
        samesession = otherplayer['samesession']

        if sid in self.connectedusers and otherplayersid in self.connectedusers:
            if samesession == 'TRUE':
                currentsession = self.connectedusers[sid]['assignedsessionid']
                if self.activegamesessions[currentsession]:
                    self.activegamesessions.pop(currentsession)
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
        # users_finding_game = self.getappropriateuser(sid)
        # if users_finding_game is not None:
        if self.searchingusers[sid] is not None and len(self.searchingusers.keys()) > 1:
            users = []
            for user in self.searchingusers:
                if len(users) < 2:
                    users.append(user)

            for user in users:
                self.searchingusers.pop(user)

            # user1 = users_finding_game[0]
            # user2 = users_finding_game[1]
            sessioninfo = self.creategamesessionnational(users[0], users[1])
            sessionid = sessioninfo['sessionid']
            self.connectedusers[users[0]]['assignedsessionid'] = sessionid
            self.connectedusers[users[0]]['ingame'] = True
            self.connectedusers[users[1]]['assignedsessionid'] = sessionid
            self.connectedusers[users[1]]['ingame'] = True
            retvaluser1 = {}
            retvaluser2 = {}

            retvaluser1 = dict(sessioninfo)
            retvaluser2 = dict(sessioninfo)

            if users[0] in retvaluser1:
                retvaluser1.pop(users[0])

            if users[1] in retvaluser2:
                retvaluser2.pop(users[1])

            print(retvaluser1)
            print(users[0])
            print(retvaluser2)
            print(users[1])

            await self.sio.emit('game_found_national', data=retvaluser1, room=users[0])
            await self.sio.emit('game_found_national', data=retvaluser2, room=users[1])
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
                if len(users) < 4:
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
        await self.send_one_vs_all_searching_count()

        if self.searchinguserforonevsall is not None and len(self.searchinguserforonevsall.keys()) > 4:
            users = []
            for user in self.searchinguserforonevsall:
                if len(users) < 5:
                    users.append(user)

            for user in users:
                self.searchinguserforonevsall.pop(user)

            sessioninfo = self.createonevsallgamesession(users)
            sessionid = sessioninfo['sessionid']
            res = list(sessioninfo.keys())#.index(find_key)

            for user in users:
                self.connectedusers[user]['assignedsessionid'] = sessionid
                self.connectedusers[user]['ingame'] = True

            find_key = 'Germany'
            for user in users:
                retsessioninfo = dict(sessioninfo)
                retsessioninfo['coloridx'] = res.index(user)
                print(retsessioninfo)
                if user in retsessioninfo:
                    retsessioninfo.pop(user)
                await self.sio.emit('one_vs_all_game_found', data=retsessioninfo, room=user)
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
            await self.sio.emit('find_game_cancelled', room=sid)
            await self.send_one_vs_all_searching_count()
        else:
            print("MAIN MOMO: Not searching game for User: {}".format(self.getusername(sid)))

    def calculatedistancebetweenlocations(self, loc1, loc2):
        # print('Distance: ', hs.haversine(loc1, loc2))
        return hs.haversine(loc1, loc2)

    def getappropriateuser(self, sid):
        targetuserinfos = self.searchingusers[sid]
        targetmindistance = targetuserinfos['mindistance']
        targetlatlon = (targetuserinfos['lat'], targetuserinfos['lon'])
        for othersid in self.searchingusers:
            if othersid == sid:
                continue
            otherfindinfos = self.searchingusers[othersid]
            othermindistance = otherfindinfos['mindistance']
            otherlatlon = (otherfindinfos['lat'], otherfindinfos['lon'])
            if otherlatlon[0] != 0.0 and otherlatlon[1] != 0.0 and targetlatlon[0] != 0.0 and targetlatlon[1] != 0.0:
                distance = self.calculatedistancebetweenlocations(otherlatlon, targetlatlon)
                if distance > targetmindistance and distance > othermindistance:
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

    def creategamesessionnational(self, user1, user2):
        print("MAIN MOMO: Creating game session for Users: {} and {}".format(self.getusername(user1),
                                                                             self.getusername(user2)))
        sessionid = user1 + user2
        user1id = self.connectedusers[user1]['userid']
        user2id = self.connectedusers[user2]['userid']
        user1name = self.connectedusers[user1]['name']
        user2name = self.connectedusers[user2]['name']
        gamesessioninstance = gamesessionnational.GameSession(sessionID=sessionid, user1id=user1id, user2id=user2id,
                                                      user1sio=user1, user2sio=user2, user1name=user1name,
                                                      user2name=user2name)
        print("MAIN MOMO: Adding active session: {}".format(sessionid))

        # for user in users:
        #     print('MAIN MOMO:User: {}'.format(self.getusername(user)))
        #     print('user sid: ', user)
        #     print('user id: ', self.connectedusers[user]['userid'])
        #     print('user name: ', self.connectedusers[user]['name'])

        tempval = {'userid': '', 'username': '', 'gender': 0, 'membership': 3, 'profileid': 0}
        retval = {}

        tempval['userid'] = self.connectedusers[user1]['userid']
        tempval['username'] = self.connectedusers[user1]['name']
        tempval['gender'] = self.connectedusers[user1]['gender']
        tempval['membership'] = self.connectedusers[user1]['membership']
        tempval['profileid'] = self.connectedusers[user1]['profileid']

        retval[user1] = dict(tempval)

        tempval['userid'] = self.connectedusers[user2]['userid']
        tempval['username'] = self.connectedusers[user2]['name']
        tempval['gender'] = self.connectedusers[user2]['gender']
        tempval['membership'] = self.connectedusers[user2]['membership']
        tempval['profileid'] = self.connectedusers[user2]['profileid']

        retval[user2] = dict(tempval)

        self.activegamesessions[sessionid] = gamesessioninstance

        # retval['user1id'] = user1id
        # retval['user2id'] = user2id
        # retval['user1name'] = user1name
        # retval['user2name'] = user2name
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
            print('user id: ', self.connectedusers[user]['userid'])
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

        tempval = {'userid': '', 'username': '', 'gender': 0, 'membership': 3, 'profileid': 0}
        retval={}

        print('MAIN MOMO: Creating game session for Users:')
        for user in users:
            print('MAIN MOMO:User: {}'.format(self.getusername(user)))
            print('user sid: ', user)
            print('user id: ', self.connectedusers[user]['userid'])
            print('user name: ', self.connectedusers[user]['name'])

            tempval['userid'] = self.connectedusers[user]['userid']
            tempval['username'] = self.connectedusers[user]['name']
            tempval['gender'] = self.connectedusers[user]['gender']
            tempval['membership'] = self.connectedusers[user]['membership']
            tempval['profileid'] = self.connectedusers[user]['profileid']

            retval[user] = dict(tempval)

            userid.append(self.connectedusers[user]['userid'])
            username.append(self.connectedusers[user]['name'])

        gamesessioninstance = onevsallgamesession.OneVsAllGameSession(sessionID=sessionid, usersid=userid,
                                                                      userssio=users, usersname=username)
        print("MAIN MOMO: Adding active session: {}".format(sessionid))

        self.activegamesessions[sessionid] = gamesessioninstance

        # for user in range(len(users)):
            # retval[user] = {'userid': userid[user]}
            # retval[user] = {'username': username[user]}
            # retval[user]['gender'] = self.connectedusers[user]['gender']
            # retval[user]['membership'] = self.connectedusers[user]['membership']
            # retval[user]['profileid'] = self.connectedusers[user]['profileid']

        # retval['sessionid'] = sessionid
        # return retval

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

    async def on_send_session_timer(self, sid, gamesessionid):
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

            if gamesession.getgamemode() == state.GameState.national:
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
                    scoredict = gamesession.getscore(user)
                    await self.sio.emit('one_vs_all_score', data=scoredict, room=user)
        pass

    async def on_send_message(self, sid, sessionmessagedict):
        # sessionid = sessionmessagedict['SESSION_ID']
        sessionid = self.connectedusers[sid]['assignedsessionid']
        message = sessionmessagedict['MESSAGE']
        if sessionid in self.activegamesessions:
            gamesession = self.activegamesessions[sessionid]
            users = gamesession.getsessionusers()

            if gamesession.getgamemode() == state.GameState.local:
                for user in users:
                    if user != sid:
                        await self.sio.emit('opponent_message', data=sessionmessagedict, room=user)

            if gamesession.getgamemode() == state.GameState.national:
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

    async def on_game_started_timer(self, sid, info):
        print('Getting Game Timer')
        retObj = {"GAME_STARTED_TIME": 0, "MS": 0}
        sessionid = info["SESSION_ID"]
        startTime = info["GAME_STARTED_TIME"]
        latency = info["MS"]
        if sessionid in self.activegamesessions:
            gamesession = self.activegamesessions[sessionid]
            if sid in self.connectedusers:
                retVal = gamesession.getstarttime()
                retLatency = gamesession.getlatency()
                if retVal == 0:
                    gamesession.setstarttime(startTime)
                    retVal = startTime
                if retLatency == 0:
                    gamesession.setlatency(latency)
                    retLatency = latency
                retObj["GAME_STARTED_TIME"] = retVal
                retObj["MS"] = retLatency
                print('GameTimer::', retObj["GAME_STARTED_TIME"])
                await self.sio.emit('get_game_timer', data=retObj, room=sid)
        pass

    async def on_play_again(self, sid):
        print("MAIN MOMO: Sent Game Request")
        if sid in self.connectedusers:
            sessionid = self.connectedusers[sid]['assignedsessionid']
            if sessionid in self.activegamesessions:
                gamesession = self.activegamesessions[sessionid]
                otherplayersid = gamesession.getopponentsid(sid)
                print("MAIN MOMO: Sent Game Request To User: {}".format(self.getusername(otherplayersid)))
                if otherplayersid in self.connectedusers:
                    returnusersdict = {}
                    # returnusersdict['sid'] = sid
                    # returnusersdict['name'] = self.connectedusers[sid]['name']
                    returnusersdict['sid'] = sid
                    returnusersdict['name'] = self.connectedusers[sid]['name']
                    returnusersdict['gender'] = self.connectedusers[sid]['gender']
                    returnusersdict['membership'] = self.connectedusers[sid]['membership']
                    returnusersdict['profileid'] = self.connectedusers[sid]['profileid']
                    # await self.sio.emit('game_request_received_play_again', room=otherplayersid)
                    await self.sio.emit('game_request_received', data=returnusersdict, room=otherplayersid)

    async def turn_off_play_again(self, sid):
        if sid in self.connectedusers:
            print("MAIN MOMO: Turning Off Play Again For Active User: {}".format(self.getusername(sid)))
            await self.sio.emit('turn_off_play_again', room=sid)
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

            for user in sessioncompleteresult:
                if user in self.connectedusers:
                    self.connectedusers[user]['ingame'] = False
                    self.connectedusers[user]['receivedrequest'] = False

            sessionresult = gamesession.getsessionresult()

            if gamesession.getgamemode() == state.GameState.local:
                print("MAIN MOMO: The Winner is User: {}".format(self.getusername(sessionresult['winnersid'])))
                for user in sessioncompleteresult:
                    if user in self.connectedusers:
                        self.update_resource_after_match(user, sessionresult['winneruserid'], 'local_point')
                        await self.sio.emit('game_over', data=sessionresult, room=user)

            if gamesession.getgamemode() == state.GameState.national:
                print("MAIN MOMO: The Winner is User: {}".format(self.getusername(sessionresult['winnersid'])))
                self.remove_active_game_session(sessionid)
                for user in sessioncompleteresult:
                    if user in self.connectedusers:
                        self.update_resource_after_match(user, sessionresult['winneruserid'], 'national_point')
                        await self.sio.emit('game_over', data=sessionresult, room=user)

            if gamesession.getgamemode() == state.GameState.twovstwo:
                self.remove_active_game_session(sessionid)
                print("MAIN MOMO: The Winning Team is: {}".format(sessionresult['winningteam']))
                for user in sessioncompleteresult:
                    if user in self.connectedusers:
                        self.connectedusers[user]['assignedsessionid'] = ''
                        await self.sio.emit('game_over_two_vs_two', data=sessionresult, room=user)

            if gamesession.getgamemode() == state.GameState.onevsall:
                self.remove_active_game_session(sessionid)
                print("MAIN MOMO: The Winner is User: {}".format(self.getusername(sessionresult['winnersid'])))
                for user in sessioncompleteresult:
                    if user in self.connectedusers:
                        # opponentname = gamesession.getopponentname(user)
                        self.connectedusers[user]['assignedsessionid'] = ''
                        self.update_resource_after_match(user, sessionresult['winneruserid'], 'national_point')
                        # await self.sio.emit('one_vs_all_opponent_name', data=opponentname, room=user)
                        await self.sio.emit('game_over_one_vs_all', data=sessionresult, room=user)
        pass

    async def on_force_complete_session(self, sid, sessionid):
        print("MAIN MOMO: FORCE SESSION COMPLETE User: {} SessionID: {}".format(self.getusername(sid), sessionid))
        if sessionid not in self.activegamesessions:
            print("MAIN MOMO: FORCE SESSION NOT FOUND")
            if sid in self.connectedusers:
                await self.sio.emit('cancel_session_complete_check', room=sid)
            return
        gamesession = self.activegamesessions[sessionid]
        sessioncompleteresult = gamesession.forcecompletesession()

        if sessioncompleteresult is not None:
            print("MAIN MOMO: Removing active User: {} SessionID: {}".format(self.getusername(sid), sessionid))

            for user in sessioncompleteresult:
                if user in self.connectedusers:
                    self.connectedusers[user]['ingame'] = False
                    self.connectedusers[user]['receivedrequest'] = False

            sessionresult = gamesession.getsessionresult()

            if gamesession.getgamemode() == state.GameState.local:
                print("MAIN MOMO: The Winner is User: {}".format(self.getusername(sessionresult['winnersid'])))
                for user in sessioncompleteresult:
                    if user in self.connectedusers:
                        self.update_resource_after_match(user,sessionresult['winneruserid'],'local_point')
                        await self.sio.emit('game_over', data=sessionresult, room=user)

            if gamesession.getgamemode() == state.GameState.national:
                print("MAIN MOMO: The Winner is User: {}".format(self.getusername(sessionresult['winnersid'])))
                self.remove_active_game_session(sessionid)
                for user in sessioncompleteresult:
                    if user in self.connectedusers:
                        self.update_resource_after_match(user, sessionresult['winneruserid'], 'national_point')
                        await self.sio.emit('game_over', data=sessionresult, room=user)

            if gamesession.getgamemode() == state.GameState.twovstwo:
                self.remove_active_game_session(sessionid)
                print("MAIN MOMO: The Winning Team is: {}".format(sessionresult['winningteam']))
                for user in sessioncompleteresult:
                    if user in self.connectedusers:
                        self.connectedusers[user]['assignedsessionid'] = ''
                        await self.sio.emit('game_over_two_vs_two', data=sessionresult, room=user)

            if gamesession.getgamemode() == state.GameState.onevsall:
                self.remove_active_game_session(sessionid)
                print("MAIN MOMO: The Winner is User: {}".format(self.getusername(sessionresult['winnersid'])))
                for user in sessioncompleteresult:
                    if user in self.connectedusers:
                        # opponentname = gamesession.getopponentname(user)
                        self.connectedusers[user]['assignedsessionid'] = ''
                        self.update_resource_after_match(user, sessionresult['winneruserid'], 'national_point')
                        # await self.sio.emit('one_vs_all_opponent_name', data=opponentname, room=user)
                        await self.sio.emit('game_over_one_vs_all', data=sessionresult, room=user)
        pass

    async def on_post_latency(self, sid, info):
        latency = info["LATENCY"]
        ct = info["CurrentTime"]
        retVal = info["RetVal"]
        # print("MAIN MOMO: User: {} Start Time{}".format(self.getusername(sid), latency))
        # print("MAIN MOMO: User: {} Current Time{}".format(self.getusername(sid), ct))
        # print("MAIN MOMO: User: {} Start - Current{}".format(self.getusername(sid), retVal))
        pass

    async def on_debug_function(self, sid, info):
        retVal = info["Value"]
        print("MAIN MOMO: User: DEBUG TEXT: ", retVal)
        # print("MAIN MOMO: User: DEBUG TEXT: ".format(self.getusername(sid), retVal))
        pass

    def update_loggout_time(self, sid):
        if sid in self.connectedusers:
            print(self.connectedusers[sid]["userid"])
            database = firestore.client()
            collection = database.collection('players')

            now = datetime.now(timezone.utc)

            # mm/dd/YY H:M:S
            dt_string = now.strftime("%m/%d/%Y %H:%M:%S")
            str = ""

            for i in dt_string:
                if i != "/" and i != " " and i != ":":
                    str += i

            res = collection.document(self.connectedusers[sid]["userid"]).update \
                ({'logged_out_time': now})

            # res = collection.document(self.connectedusers[sid]["userid"]).update \
            #     ({'dateTimeYear': str})

    async def opponent_disconnect_from_current_session(self, sid):
        if sid in self.connectedusers:
            if self.connectedusers[sid]['assignedsessionid']:
                self.remove_active_game_session(self.connectedusers[sid]['assignedsessionid'])
                await self.turn_off_play_again(sid)
                self.connectedusers[sid]['assignedsessionid'] = ''
                print('USER DISCONNECTED FROM CURRENT SESSION', self.getusername(sid))
        pass

    async def on_disconnected_from_current_session(self, sid):
        if sid in self.connectedusers:
            if self.connectedusers[sid]['assignedsessionid']:
                gamesession = self.remove_active_game_session(self.connectedusers[sid]['assignedsessionid'])
                print(gamesession)
                if gamesession:
                    await self.turn_off_play_again(gamesession.getopponentsid(sid))
                self.connectedusers[sid]['assignedsessionid'] = ''
                print('USER DISCONNECTED FROM CURRENT SESSION', self.getusername(sid))
        pass

    async def on_get_last_logged_out_time(self, sid, info):
        loggedoutparms = info['lastloggedouttime']
        timedetails = {}
        if sid in self.connectedusers:
            print('Check For Daily Reward')
            timedetails = self.get_difference_between_loggout_time(self.connectedusers[sid]['userid'], loggedoutparms)
            await self.sio.emit('check_for_daily_rewards', data=timedetails, room=sid)
        pass

    async def on_update_heart_time(self, sid, info):
        lastrefillparams = info['lastrefill']
        timedetails = {}
        if sid in self.connectedusers:
            print('Check For Heart Timer')
            timedetails = self.get_difference_between_last_heart_claimed_time(self.connectedusers[sid]['userid'], 'last_refill_time')
            print(timedetails)
            await self.sio.emit('update_heart_count', data=timedetails, room=sid)
        pass

    def remove_active_game_session(self, sessionid):
        if sessionid in self.activegamesessions:
            print('MOMO: REMOVING ACTIVE GAME SESSION {}'.format(sessionid))
            return self.activegamesessions.pop(sessionid)
        return None

    def get_difference_between_loggout_time(self, userid, param):
        db = firestore.client()
        doc_ref = db.collection('players').document(userid)
        doc = doc_ref.get()
        ret = {'DAYS': 0}
        if doc.exists:
            ref = doc.to_dict()
            for d in ref:
                if (d == param):
                    userloggedouttime = ref[d]
                    currentutctime = datetime.utcnow()
                    parseduserloggouttime = userloggedouttime.strftime("%d/%m/%Y")
                    parsedcurrentutctime = currentutctime.strftime("%d/%m/%Y")
                    finaluserloggedouttime = datetime.strptime(parseduserloggouttime, "%d/%m/%Y")
                    finalutcnowtime = datetime.strptime(parsedcurrentutctime, "%d/%m/%Y")
                    dt_string = finalutcnowtime - finaluserloggedouttime
                    days, seconds = dt_string.days, dt_string.seconds
                    ret['DAYS'] = days
        return ret

    def get_difference_between_last_heart_claimed_time(self, userid, param):
        db = firestore.client()
        doc_ref = db.collection('players').document(userid)
        doc = doc_ref.get()
        ret = {'DAYS': 0, 'HOURS': 0, 'MINUTES': 0, 'SECONDS': 0,'MEMBERSHIP':0}
        if doc.exists:
            ref = doc.to_dict()
            for d in ref:
                if (d == param):
                    userloggedouttime = ref[d]
                    currentutctime = datetime.utcnow()
                    parseduserloggouttime = userloggedouttime.strftime("%d/%m/%Y %H:%M:%S")
                    parsedcurrentutctime = currentutctime.strftime("%d/%m/%Y %H:%M:%S")
                    print('last Refill Time: ', parseduserloggouttime)
                    finaluserloggedouttime = datetime.strptime(parseduserloggouttime, "%d/%m/%Y %H:%M:%S")
                    finalutcnowtime = datetime.strptime(parsedcurrentutctime, "%d/%m/%Y %H:%M:%S")
                    dt_string = finalutcnowtime - finaluserloggedouttime
                    days, seconds = dt_string.days, dt_string.seconds
                    hours = days * 24 + seconds // 3600
                    # minutes = (seconds % 3600) // 60
                    if hours == 0:
                        minutes = (seconds % 3600) // 60
                        print(minutes)
                    else:
                        minutes = (hours * 60) + (seconds % 3600) // 60
                        print(minutes)
                    seconds = seconds % 60
                    ret['DAYS'] = days
                    ret['HOURS'] = hours
                    ret['MINUTES'] = minutes
                    ret['SECONDS'] = seconds
                if d == 'membership':
                    ret['MEMBERSHIP'] = ref[d]
        return ret

    def set_heart_value_in_db(self, userid, param, value):
        db = firestore.client()
        doc_ref = db.collection('players').document(userid)
        doc = doc_ref.get()
        count = 0
        if doc.exists:
            ref = doc.to_dict()
            for d in ref:
                if d == param:
                    count = ref[d]
            if count > 0:
                count = count-value
                if count == 9:
                    doc_ref.update({
                        param: count,
                        'last_refill_time': datetime.utcnow(),
                        })
                else:
                    doc_ref.update({
                        param: count,
                    })

    def set_value_in_db_result(self, userid, param, value):
        db = firestore.client()
        doc_ref = db.collection('players').document(userid)
        doc = doc_ref.get()
        count = 0
        if doc.exists:
            ref = doc.to_dict()
            for d in ref:
                if d == param:
                    count = ref[d]
            count = count + value
            if count > 0:
                doc_ref.update({
                    param: count,
                    })
            else:
                doc_ref.update({
                    param: 0,
                })

    def update_resource_after_match(self, sid, winnerid, param):
        if sid in self.connectedusers:
            if self.connectedusers[sid]['userid'] == winnerid:
                self.set_value_in_db_result(self.connectedusers[sid]['userid'], 'coins',
                                            endreward.winningcoins(self.connectedusers[sid]['membership']))
                if param == 'local_point':
                    self.set_value_in_db_result(self.connectedusers[sid]['userid'], 'local_point',
                                                endreward.localwinningpoints(self.connectedusers[sid]['membership']))
                if param == 'national_point':
                    self.set_value_in_db_result(self.connectedusers[sid]['userid'], 'national_point',
                                                endreward.nationalwinningpoints(self.connectedusers[sid]['membership']))
            else:
                self.set_heart_value_in_db(self.connectedusers[sid]['userid'], 'heart', 1)
                self.set_value_in_db_result(self.connectedusers[sid]['userid'], 'coins',
                                            endreward.losingcoins(self.connectedusers[sid]['membership']))
                if param == 'local_point':
                    self.set_value_in_db_result(self.connectedusers[sid]['userid'], 'local_point',
                                                endreward.locallosingpoints(self.connectedusers[sid]['membership']))
                if param == 'national_point':
                    self.set_value_in_db_result(self.connectedusers[sid]['userid'], 'national_point',
                                                endreward.nationallosingpoints(self.connectedusers[sid]['membership']))

    def get_value_from_db(self, userid, param):
        db = firestore.client()
        doc_ref = db.collection('players').document(userid)
        doc = doc_ref.get()
        print(doc_ref)
        retval = ''

#SUBRACT DATES
        # a_date = datetime.utcnow()
        # dd = timedelta(days=90)
        #
        # v =a_date - dd
        # print(a_date - dd)

#TO DELETE A FIELD FROM FIREBASE FIRESTORE
        # doc_ref.update({
        #             'date_time_Now': DELETE_FIELD,
        #     })
        # keys = ['coins','crystals','daily_login_count','daily_reward_available','gender','heart','highscore','is_new_player','last_refill_time','local_point','logged_out_time','mana'
        #         ,'membership','name','national_point','onetime_mb_bronze','onetime_mb_gold','onetime_mb_silver','onetime_mb_normal','profileimageID','playerID']
        #
        # print(keys)
        # print(len(keys))
        print(self.get_difference_between_loggout_time(userid, 'logged_out_time'))
        # r = db.collection('players').document(userid)
        # r.update({
        #         'power_cracker': 1,
        #         'power_rocket': 2,
        #         'power_duck': 3,
        #         'power_ufo': 4,
        #         'power_cracker_idx': 5,
        #         'power_balloon': 6,
        #         'power_sweep': 7,
        #         'power_pick_sweep': 8,
        #         'power_mastermind': 9,
        #         'power_dragon': 10,
        #         'power_voltage': 11,
        #         'power_cobra': 12,
        #         'power_wolly': 13,
        #         'power_doc_color': 14,
        #          })
# TO CHANGE VALUES IN FIREBASE
        param ='profileimageID'
        # database_2 = firestore.client()
        # all_users_ref_2 = database_2.collection(u'players').stream()
        # for users in all_users_ref_2:
            # print(u'{} => {}'.format(users.id, users.to_dict()))
            #print(users.id)
            # r = db.collection('players').document(users.id)
            # r.update({
            #     'power_cracker': 0,
            #     'power_rocket': 0,
            #     'power_duck': 0,
            #     'power_ufo': 0,
            #     'power_cracker_idx': 0,
            #     'power_balloon': 0,
            #     'power_sweep': 0,
            #     'power_pick_sweep': 0,
            #     'power_mastermind': 0,
            #     'power_dragon': 0,
            #     'power_voltage': 0,
            #     'power_cobra': 0,
            #     'power_wolly': 0,
            #     'power_doc_color': 0,
            # })
            # print('Updated')
            # doc = r.get()
            # if doc.exists:
            #     ref = doc.to_dict()
            #     for d in ref:
            #         if (d == 'logged_out_time'):
            #             userloggedouttime = ref[d]
            #             currentutctime = datetime.utcnow()
            #
            #             parseduserloggouttime = userloggedouttime.strftime("%d/%m/%Y")
            #             parsedcurrentutctime = currentutctime.strftime("%d/%m/%Y")
            #
            #             if parseduserloggouttime == parsedcurrentutctime:
            #                 print(ref['name'])
            #                 print(ref['playerID'])

#             print(users.to_dict())
#             for i in keys:
#                 if i not in doc.to_dict():
#                     # print(i)
#                     # r.update({
#                     #         'is_new_player': 'No',
#                     #             })
#                     print('Need Update: ', users.id)
#                 #     print('yes')
# #                 # else:
# #                 #
# #                 #     # r.update({
# #                 #     #             param: 0,
# #                 #     #     })



#TO GET LOGGED VALUE IN DESIRED FORMAT
        # ret = {'DAYS': 0, 'HOURS': 0, 'MINUTES': 0, 'SECONDS': 0}
        # if doc.exists:
        #     ref = doc.to_dict()
        #     for d in ref:
        #         if (d == param):
        #             userloggedouttime = ref[d]
        #             currentutctime = datetime.utcnow()
        #

                    # parseduserloggouttime = userloggedouttime.strftime("%d/%m/%Y %H:%M:%S")
                    # parsedcurrentutctime = currentutctime.strftime("%d/%m/%Y %H:%M:%S")
        #
        #             finaluserloggedouttime = datetime.strptime(parseduserloggouttime, "%d/%m/%Y %H:%M:%S")
        #             finalutcnowtime = datetime.strptime(parsedcurrentutctime, "%d/%m/%Y %H:%M:%S")
        #             dt_string = finalutcnowtime - finaluserloggedouttime
        #
        #             days, seconds = dt_string.days, dt_string.seconds
        #             hours = days * 24 + seconds // 3600
        #             if hours == 0:
        #                 minutes = (seconds % 3600) // 60
        #                 print(minutes)
        #             else:
        #                 minutes = (hours * 60) + (seconds % 3600) // 60
        #                 print(minutes)
        #             seconds = seconds % 60
        #             ret['DAYS'] = days
        #             ret['HOURS'] = hours
        #             ret['MINUTES'] = minutes
        #             ret['SECONDS'] = seconds
        # return ret

# async def on_what_day(self, sid, info):
    #     if sid in self.connectedusers:
    #         print(self.connectedusers[sid]["userid"])
    #         my_date = date.today()
    #         calendar.day_name[my_date.weekday()]
