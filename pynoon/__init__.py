"""

Basic connectivity and control for Noon Home Room Director and Extension switches.

Note that this API is not supported by Noon, and is subject to change or withdrawal at any time.

"""

__author__ = "Alistair Galbraith"
__copyright__ = "Copyright 2018, Alistair Galbraith"

import logging
import requests
import websocket
import threading
import json
import datetime

from typing import Any, Callable, Dict, Type

from pynoon.const import (
    LOGIN_URL, RENEW_TOKEN_URL, DEX_URL
)

_LOGGER = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG, format='%(message)s')

NoonEventHandler = Callable[['NoonEntity', Any, 'NoonEvent', Dict], None]


class NoonException(Exception):

    pass


class NoonAuthenticationError(NoonException):

    pass


class NoonInvalidParametersError(NoonException):

    pass


class NoonInvalidJsonError(NoonException):

    pass


class NoonDuplicateIdError(NoonException):

    pass


class NoonUnknownError(NoonException):

    pass


class NoonEvent(object):

    pass


class NoonEntity(object):

    def __init__(self, noon, guid, name):
        """Initializes the base class with common, basic data."""
        self._noon = noon
        self._name = name
        self._guid = guid
        self._subscribers = []
        noon._registerEntity(self)

    @property 
    def name(self):
        """Returns the entity name (e.g. Pendant)."""
        return self._name

    @property 
    def guid(self):
        """Returns the entity unique ID (GUID from Noon)."""
        return self._guid

    def _dispatch_event(self, event: NoonEvent, params: Dict):
        """Dispatches the specified event to all the subscribers."""
        _LOGGER.debug("Sending notifications!")
        for handler, context in self._subscribers:
            _LOGGER.debug("...notification sent.")
            handler(self, context, event, params)

    def subscribe(self, handler: NoonEventHandler, context):
        """Subscribes to events from this entity.
        handler: A callable object that takes the following arguments (in order)
                obj: the LutrongEntity object that generated the event
                context: user-supplied (to subscribe()) context object
                event: the LutronEvent that was generated.
                params: a dict of event-specific parameters
        context: User-supplied, opaque object that will be passed to handler.
        """
        _LOGGER.debug("Added update subscriber for {}".format(self.name))
        self._subscribers.append((handler, context))
    
    def handle_update(self, args):
        """The handle_update callback is invoked when an event is received
        for the this entity.
        Returns:
        True - If event was valid and was handled.
        False - otherwise.
        """
        return False

    @classmethod
    def fromJsonObject(cls, noon, json):

        raise NoonInvalidJsonError
        return False

class NoonSpace(NoonEntity):

    class Event(NoonEvent):
        """Output events that can be generated.
        SCENE_CHANGED: The scene has changed.
            Params:
            scene: new scene guid (string)
        """
        SCENE_CHANGED = 1

        """
        LIGHTSON_CHANGED: The space lights have turned or off.
            Params:
            lightsOn: Lights are on (boolean)
        """
        LIGHTSON_CHANGED = 2

        
    @property
    def lightsOn(self):
        return self._lightsOn
    @lightsOn.setter
    def lightsOn(self, value):
        valueChanged = (self._lightsOn != value)
        self._lightsOn = value
        if valueChanged:
            self._dispatch_event(NoonSpace.Event.LIGHTSON_CHANGED, {'lightsOn': self._lightsOn})

    @property
    def activeSceneName(self):
        if self.activeScene is not None:
            scene = self._scenes.get(self.activeScene, None)
            if scene:
                return scene.name
            else:
                return "Unknown"
        else:
            return "Unknown"

    @property
    def activeScene(self):
        return self._activeScene
    @activeScene.setter
    def activeScene(self, value):

        """ This may be a dict object - {"guid": "some-guid-value-here"} """
        actualValue = value
        if isinstance(actualValue, Dict) and actualValue.get("guid", None) is not None:
            actualValue = actualValue.get("guid")

        """ Sanity check - we should have a scene for this """
        newScene = self._scenes.get(actualValue, None)
        if newScene is None:
            if actualValue is not None:
                _LOGGER.error("Space changed to new scene '{}', but this scene is unknown!".format(actualValue))
            return

        """ Debug """
        _LOGGER.info("Scene for space '{}' changed to '{}'".format(self.name, newScene.name))

        valueChanged = (self._activeScene != actualValue)
        self._activeScene = actualValue
        if valueChanged:
            self._dispatch_event(NoonSpace.Event.SCENE_CHANGED, {'sceneId': self._activeScene})

    def setSceneActive(self, active=None, sceneIdOrName=None):

        """ (Re)authenticate if needed """
        self._noon.authenticate()

        """ Replace variables """
        if active is None:
            active = self.lightsOn
        if sceneIdOrName is None:
            sceneIdOrName = self.activeScene

        """ Get the scene """
        targetScene = self._scenes.get(sceneIdOrName, None)
        if targetScene is None:
            for id, scene in self._scenes.items():
                if scene.name == sceneIdOrName:
                    targetScene = scene
        
        """ Sanity Check """
        if targetScene is None:
            _LOGGER.error("Did not find scene in space '{}' with name or ID {}".format(self.name, sceneIdOrName))
            raise NoonInvalidParametersError

        """ Send the command """
        _LOGGER.debug("Attempting to activate scene {} in space '{}', with active = {}".format(targetScene.name, self.name, active))
        actionUrl = "{}/api/action/space/scene".format(self._noon.endpoints["action"])
        result = self._noon.session.post(actionUrl, headers={"Authorization": "Token {}".format(self._noon.authToken)}, json={"space": self.guid, "activeScene": targetScene.guid, "on": active, "tid": 55555})
        _LOGGER.debug("Got activate scene result: {}".format(result))


    def activateScene(self):

        self.setSceneActive(active=True)

    def deactivateScene(self):

        self.setSceneActive(active=False)

    def __init__(self, noon, guid, name, activeScene=None, lightsOn=None, lines={}, scenes={}):
        
        """Initializes the Space."""
        self._activeScene = None
        self._lightsOn = None
        self._lines = lines
        self._scenes = scenes
        super(NoonSpace, self).__init__(noon, guid, name)

        """ Trigger any initial updates """
        self.activeScene = activeScene
        self.lightsOn = lightsOn

    def __str__(self):
        """Returns a pretty-printed string for this object."""
        return 'Space name: "%s" active scene ID: %s, lights on: "%s"' % (
            self._name, self._activeScene, self._lightsOn)

    def __repr__(self):
        """Returns a stringified representation of this object."""
        return str({'name': self._name, 'activeScene': self._activeScene,
                    'lightsOn': self._lightsOn, 'id': self._guid})

    @classmethod
    def fromJsonObject(cls, noon, json):

        """Sanity Check"""
        if not isinstance(noon, Noon):
            _LOGGER.error("Noon object not correctly passed as a parameter")
            raise NoonInvalidParametersError
        if not isinstance(json, Dict):
            _LOGGER.error("JSON object must be pre-parsed before loading")
            raise NoonInvalidParametersError

        """Basics"""
        guid = json.get("guid", None)
        name = json.get("name", None)

        if guid is None or name is None:
            _LOGGER.debug("Invalid JSON payload: {}".format(json))
            raise NoonInvalidJsonError
        newSpace = NoonSpace(noon, guid, name)

        """Scenes"""
        scenesMap = {}
        for scene in json.get("scenes", []):
            thisScene = NoonScene.fromJsonObject(noon, newSpace, scene)
            scenesMap[thisScene.guid] = thisScene
        newSpace._scenes = scenesMap

        """Lines"""
        linesMap = {}
        for line in json.get("lines", []):
            thisLine = NoonLine.fromJsonObject(noon, newSpace, line)
            linesMap[thisLine.guid] = thisLine
        newSpace._lines = linesMap

        """ Status """
        lightsOn = json.get("lightsOn", None)
        activeScene = json.get("activeScene", {}).get("guid", None)
        newSpace.lightsOn = lightsOn
        newSpace.activeScene = activeScene
        
        return newSpace


class NoonLine(NoonEntity):

    class Event(NoonEvent):
        """Output events that can be generated.
        DIM_LEVEL_CHANGED: The dim level of this line has changed.
            Params:
            dimLevel: New dim level percent (integer)
        """
        DIM_LEVEL_CHANGED = 1

        """
        LINE_STATE_CHANGED: The line lights have turned or off.
            Params:
            lineState: Line State (string - 'on' or 'off')
        """
        LINE_STATE_CHANGED = 2

    @property
    def lineState(self):
        return self._lineState
    @lineState.setter
    def lineState(self, value):

        valueChanged = (self._lineState != value)
        self._lineState = value
        if valueChanged:
            self._dispatch_event(NoonLine.Event.LINE_STATE_CHANGED, {'lineState': self._lineState})

    @property
    def parentSpace(self):
        return self._parentSpace

    @property
    def dimmingLevel(self):
        return self._dimmingLevel
    @dimmingLevel.setter
    def dimmingLevel(self, value):
        valueChanged = (self._dimmingLevel != value)
        self._dimmingLevel = value
        if valueChanged:
            self._dispatch_event(NoonLine.Event.DIM_LEVEL_CHANGED, {'dimLevel': self._dimmingLevel})

    def set_brightness(self, brightnessLevel):

        """ (Re)authenticate if needed """
        self._noon.authenticate()

        """ Send the command """
        actionUrl = "{}/api/action/line/lightLevel".format(self._noon.endpoints["action"])
        result = self._noon.session.post(actionUrl, headers={"Authorization": "Token {}".format(self._noon.authToken)}, json={"line": self.guid, "lightLevel": brightnessLevel, "tid": 55555})
        _LOGGER.debug("Got set_brightness result: {}".format(result))
    

    def turn_on(self):
        
        self.set_brightness(100)

    def turn_off(self):
        
        self.set_brightness(0)

    def __init__(self, noon, space, guid, name, dimmingLevel=None, lineState=None):
        
        """Initializes the Space."""
        self._lineState = None
        self._dimmingLevel = None
        self._parentSpace = space
        super(NoonLine, self).__init__(noon, guid, name)

        """ Trigger any initial updates """
        self.lineState = lineState
        self.dimmingLevel = dimmingLevel

    @classmethod
    def fromJsonObject(cls, noon, space, json):

        """Sanity Check"""
        if not isinstance(noon, Noon):
            _LOGGER.error("Noon object not correctly passed as a parameter")
            raise NoonInvalidParametersError
        if not isinstance(json, Dict):
            _LOGGER.error("JSON object must be pre-parsed before loading")
            raise NoonInvalidParametersError

        """Basics"""
        guid = json.get("guid", None)
        name = json.get("displayName", None)

        if guid is None or name is None:
            _LOGGER.debug("Invalid JSON payload: {}".format(json))
            raise NoonInvalidJsonError
        newLine = NoonLine(noon, space, guid, name)

        """ Status """
        lineState = json.get("lineState", None)
        dimmingLevel = json.get("dimmingLevel", None)
        newLine.lineState = lineState
        newLine.dimmingLevel = dimmingLevel

        return newLine

    def __str__(self):
        """Returns a pretty-printed string for this object."""
        return 'Line name: "%s" lights on: %s, dim level: "%s"' % (
            self._name, self._lineState, self._dimmingLevel)

    def __repr__(self):
        """Returns a stringified representation of this object."""
        return str({'name': self._name, 'dimmingLevel': self._dimmingLevel,
                    'lightsOn': self._lineState, 'id': self._guid})

class NoonScene(NoonEntity):

    def __init__(self, noon, space, guid, name):
        
        """Initializes the Space."""
        self._parentSpace = space
        super(NoonScene, self).__init__(noon, guid, name)

    @classmethod
    def fromJsonObject(cls, noon, space, json):

        """Sanity Check"""
        if not isinstance(noon, Noon):
            _LOGGER.error("Noon object not correctly passed as a parameter")
            raise NoonInvalidParametersError
        if not isinstance(json, Dict):
            _LOGGER.error("JSON object must be pre-parsed before loading")
            raise NoonInvalidParametersError

        """Basics"""
        guid = json.get("guid", None)
        name = json.get("name", None)

        if guid is None or name is None:
            _LOGGER.debug("Invalid JSON payload: {}".format(json))
            raise NoonInvalidJsonError
        newScene = NoonScene(noon, space, guid, name)

        return newScene

    def __str__(self):
        """Returns a pretty-printed string for this object."""
        return 'Scene name: "%s" id: "%s"' % (
            self._name, self._guid)

    def __repr__(self):
        """Returns a stringified representation of this object."""
        return str({'name': self._name, 'id': self._guid})


class Noon(object):
    """ Base object for Noon Home """

    @property
    def spaces(self):
        return self.__spaces

    @property
    def lines(self):
        return self.__lines

    def __init__(self, username=None, password=None):

        """ Create a PyNoon object

        :param username: Noon username
        :param password: Noon password

        :returns PyNoon base object

        """

        # Key internal flags
        self.__authenticated = False
        self.__loginResponse = None
        self.__token = None
        self.__tokenValidUntil = datetime.datetime.now()
        self.__tokenRenewValidUntil = datetime.datetime.now()
        self.__session = requests.Session()
        self.__subscribed = False

        # Store credentials
        self.__username = username
        self.__password = password
        self.__endpoints = {}

        # Flag for tracking errors
        self.__errorCount = 0
        self.__lastConnectAttempt = 0

        # External Properties
        self.__spaces = {}
        self.__lines = {}
        self.__scenes = {}
        self.__allEntities = {}
        

    @property
    def endpoints(self):
        return self.__endpoints

    @property
    def session(self):
        return self.__session

    @property
    def authToken(self):
        return self.__token

    def authenticate(self):

        """ Do we already have valid tokens? """
        if self.__token is not None and self.__tokenValidUntil > datetime.datetime.now():
            _LOGGER.debug("Using cached token, which should still be valid")
            return

        """ Authenticate user, and get tokens """
        _LOGGER.debug("No valid token or token expired. Authenticating...")
        if(self.__tokenRenewValidUntil > datetime.datetime.now()):
            url = RENEW_TOKEN_URL
            json = self.__loginResponse
        else:
            url = LOGIN_URL
            json = {"email": self.__username, "password": self.__password}

        result = self.__session.post(url, json=json).json()
        if isinstance(result, dict) and result.get("token") is not None:

            """ Debug """
            _LOGGER.debug("Authenticated successfully with Noon")

            """ Store the token and expiry time """
            self.authenticated = True
            self.__loginResponse = result
            self.__token = result.get("token")
            self.__tokenValidUntil = datetime.datetime.now() + datetime.timedelta(seconds = (result.get("lifetime",0)-30))
            self.__tokenRenewValidUntil = datetime.datetime.now() + datetime.timedelta(seconds = (result.get("renewLifetime",0)-30))
            _LOGGER.debug("Authenticated. Token expires at {:%H:%M:%S}.".format(self.__tokenValidUntil))
            
            """ Get endpoints if needed """
            if len(self.__endpoints) == 0:
                self._refreshEndpoints

            self._refreshEndpoints()
        else:
            _LOGGER.debug("Response: {}".format(result))
            raise NoonAuthenticationError

    def _refreshEndpoints(self):

        """ Update the noon endpoints for this account """
        _LOGGER.debug("Refreshing endpoints...")
        result = self.__session.get(DEX_URL, headers={"Authorization": "Token {}".format(self.__token)}).json()
        if isinstance(result, dict) and isinstance(result.get("endpoints"), dict):
            self.__endpoints = result.get("endpoints")
        else:
            _LOGGER.debug("Response: {}".format(result))
            raise NoonAuthenticationError

    def _registerEntity(self, entity: NoonEntity):

        """ EVERYTHING """
        self.__allEntities[entity.guid] = entity

        """ SPACE """
        if isinstance(entity, NoonSpace):
            existingEntity = self.__spaces.get(entity.guid, None)
            if existingEntity is not None:
                if entity.name != existingEntity.name and False:
                    _LOGGER.error("New space '{}' has same ID as existing space '{}'".format(entity.name, existingEntity.name))
                    raise NoonDuplicateIdError
                else:
                    return
            else:
                self.__spaces[entity.guid] = entity	

        """ LINE """
        if isinstance(entity, NoonLine):
            existingEntity = self.__lines.get(entity.guid, None)
            if existingEntity is not None:
                if entity.name != existingEntity.name and False:
                    _LOGGER.error("New line '{}' has same ID as existing line '{}'".format(entity.name, existingEntity.name))
                    raise NoonDuplicateIdError
                else:
                    return
            else:
                self.__lines[entity.guid] = entity	

        """ SCENE """
        if isinstance(entity, NoonScene):
            existingEntity = self.__scenes.get(entity.guid, None)
            if existingEntity is not None:
                if entity.name != existingEntity.name and False:
                    _LOGGER.error("New scene '{}' has same ID as existing scene '{}'".format(entity.name, existingEntity.name))
                    raise NoonDuplicateIdError
                else:
                    return
            else:
                self.__scenes[entity.guid] = entity			

        
    
    def discoverDevices(self):

        """ (Re)authenticate if needed """
        self.authenticate()

        """ Get the device details for this account """
        _LOGGER.debug("Refreshing devices...")
        queryUrl = "{}/api/query".format(self.__endpoints["query"])
        result = self.__session.post(queryUrl, headers={"Authorization": "Token {}".format(self.__token), "Content-Type":"application/graphql"}, data="{spaces {guid name lightsOn activeScene{guid name} lines{guid lineState displayName dimmingLevel multiwayMaster { guid }} scenes{name guid}}}").json()
        if isinstance(result, dict) and isinstance(result.get("spaces"), list):
            for space in result.get("spaces"):

                # Create the space
                thisSpace = NoonSpace.fromJsonObject(self, space)

                # Debug
                _LOGGER.debug("Discovered space '{}'".format(thisSpace.name))
                

        else:
            _LOGGER.error("Invalid device discovery response from Noon")
            _LOGGER.warn("Response: {}".format(result))


    def connect(self):

        """ (Re)authenticate if needed """
        self.authenticate()

        """ Connect on a separate thread """
        if not self.__subscribed:
            self.__subscribed = True
            self.__event_handle = threading.Event()
            event_thread = threading.Thread(target=self._thread_event_function)
            event_thread.start()
        else:
            _LOGGER.error("Already attached to event stream!")


    def _thread_event_function(self):
        self.__subscribed = True
        self.__lastConnectAttempt = datetime.datetime.now()
        websocket.enableTrace(False)
        eventStreamUrl = "{}/api/notifications".format(self.__endpoints["notification-ws"])
        self.__websocket = websocket.WebSocketApp(eventStreamUrl, 
                header = {
                    "Authorization": "Token {}".format(self.__token)
                },
                on_message = _on_websocket_message, 
                on_error = _on_websocket_error, 
                on_close = _on_websocket_close)
        self.__websocket.on_open = _on_websocket_open
        self.__websocket.parent = self
        self.__websocket.run_forever(ping_interval=30)

        return True

    def _handle_change(self, changeSummary):

        guid = changeSummary.get("guid", None)
        if guid is None:
            _LOGGER.error("Cannot process change - no GUID in {}".format(changeSummary))
            return

        affectedEntity = self.__allEntities.get(guid, None)
        if affectedEntity is None:
            _LOGGER.debug("UNEXPECTED: Got change notification for {}, but not an expected entity! ({}".format(guid, changeSummary))
            return

        _LOGGER.debug("Got change notification for '{}' - {}".format(affectedEntity.name, changeSummary))
        changedFields = changeSummary.get("fields", [])
        writeableFields = [attr for attr, value in vars(affectedEntity.__class__).items()
                 if isinstance(value, property) and value.fset is not None]
        _LOGGER.debug("Settable fields for this entity - {}".format(writeableFields))
        for changedField in changedFields:
            key = changedField.get("name")
            value = changedField.get("value")
            if key in writeableFields:
                _LOGGER.debug("...setting {} = {}".format(key, value))
                setattr(affectedEntity, key, value)
            else:
                _LOGGER.debug("...ignoring {} = {}".format(key, value))
            

    def _websocket_connected(self):

        _LOGGER.debug("Successful connection. Resetting error timers.")
        self.__errorCount = 0


    def _websocket_disconnected(self):

        """ Flag disconnected """
        self.__subscribed = False

        """ Look at our failure time. If it's within the last 30 seconds, we'll abort rather than spam Noon's servers """
        if self.__lastConnectAttempt < (datetime.datetime.now() - datetime.timedelta(seconds = 30)):
            _LOGGER.error("Failed to open websocket connection on first attempt. Giving up.")
            raise NoonException
        else:
            self.connect()

    def _websocket_message(self, message):
        
        """ Ignore empty messages """
        if message is None or len(message) < 5:
            return

        """ Attempt to parse the message """
        try:
            jsonMessage = json.loads(message)
        except:
            _LOGGER.debug("Failed to parse message: {}".format(message))
            return

        """ What sort of message is this? """
        if isinstance(jsonMessage, Dict):

            """ State change notification """
            if jsonMessage.get("event", None) == "notification" and isinstance(jsonMessage.get("data"), Dict):
                data = jsonMessage.get("data")
                changes = data.get("changes", [])
                for change in changes:
                    self._handle_change(change)
                    
            else:
                _LOGGER.error("Unexpected notifiction - {}".format(jsonMessage))

        else:

            _LOGGER.error("Invalid notifiction - {}".format(jsonMessage))




def _on_websocket_message(ws, message): 

        ws.parent._websocket_message(message)

def _on_websocket_error(ws, error): 

        _LOGGER.error("Websocket: Error - {}".format(error))

def _on_websocket_close(ws): 

        _LOGGER.error("Websocket: Closed")
        ws.parent._websocket_disconnected()

def _on_websocket_open(ws): 

        _LOGGER.debug("Websocket: Opened")
        ws.parent._websocket_connected()