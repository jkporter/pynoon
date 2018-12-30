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

from typing import Any, Callable, Dict, Type

from pynoon.const import (
    LOGIN_URL, DEX_URL
)

_LOGGER = logging.getLogger(__name__)

# Enable debug logging
_LOGGER.setLevel(10)

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
		for handler, context in self._subscribers:
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
	def activeScene(self):
		return self._activeScene
	@activeScene.setter
	def activeScene(self, value):
		valueChanged = (self._activeScene != value)
		self._activeScene = value
		if valueChanged:
			self._dispatch_event(NoonSpace.Event.SCENE_CHANGED, {'sceneId': self._activeScene})

	def __init__(self, noon, guid, name, activeScene=None, lightsOn=None, lines=[], scenes=[]):
		
		"""Initializes the Space."""
		self._activeScene = None
		self._lightsOn = None
		self._lines = lines
		self._scenes = scenes
		super(NoonSpace, self).__init__(noon, guid, name)

		""" Trigger any initial updates """
		self.activeScene = activeScene
		self.lightsOn = lightsOn


		# TODO: Commented out
		#self._lutron.register_id(Output._CMD_TYPE, self)

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
		for scene in json.get("scenes", []):
			thisScene = NoonScene.fromJsonObject(noon, scene)
			newSpace._scenes.append(thisScene)

		"""Lines"""
		for device in json.get("devices", []):
			thisLine = NoonLine.fromJsonObject(noon, device.get("line", None))
			newSpace._lines.append(thisLine)

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
		LIGHTS_ON_CHANGED: The line lights have turned or off.
			Params:
			lightsOn: Lights are on (boolean)
		"""
		LIGHTS_ON_CHANGED = 2

	@property
	def lightsOn(self):
		return self._lightsOn
	@lightsOn.setter
	def lightsOn(self, value):

		""" Map the value back to a boolean """
		actualValue = value
		if actualValue == "on":
			actualValue = True
		elif actualValue == "off":
			actualValue = False

		valueChanged = (self._lightsOn != actualValue)
		self._lightsOn = actualValue
		if valueChanged:
			self._dispatch_event(NoonLine.Event.LIGHTS_ON_CHANGED, {'lightsOn': self._lightsOn})

	@property
	def dimmingLevel(self):
		return self._dimmingLevel
	@dimmingLevel.setter
	def dimmingLevel(self, value):
		valueChanged = (self._dimmingLevel != value)
		self._dimmingLevel = value
		if valueChanged:
			self._dispatch_event(NoonLine.Event.DIM_LEVEL_CHANGED, {'dimLevel': self._dimmingLevel})

	def __init__(self, noon, guid, name, dimmingLevel=None, lightsOn=None):
		
		"""Initializes the Space."""
		self._lightsOn = None
		self._dimmingLevel = None
		super(NoonLine, self).__init__(noon, guid, name)

		""" Trigger any initial updates """
		self.lightsOn = lightsOn
		self.dimmingLevel = dimmingLevel

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
		name = json.get("displayName", None)

		if guid is None or name is None:
			_LOGGER.debug("Invalid JSON payload: {}".format(json))
			raise NoonInvalidJsonError
		newLine = NoonLine(noon, guid, name)

		""" Status """
		lightsOn = json.get("lineState", None)
		dimmingLevel = json.get("dimmingLevel", None)
		newLine.lightsOn = lightsOn
		newLine.dimmingLevel = dimmingLevel

	def __str__(self):
		"""Returns a pretty-printed string for this object."""
		return 'Line name: "%s" lights on: %s, dim level: "%s"' % (
			self._name, self._lightsOn, self._dimmingLevel)

	def __repr__(self):
		"""Returns a stringified representation of this object."""
		return str({'name': self._name, 'dimmingLevel': self._dimmingLevel,
					'lightsOn': self._lightsOn, 'id': self._guid})

class NoonScene(NoonEntity):

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
		newScene = NoonScene(noon, guid, name)

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
		self.__token = None
		self.__session = requests.Session()
		self.__subscribed = False

		# Store credentials
		self.__username = username
		self.__password = password
		self.__endpoints = {}

		# External Properties
		self.__spaces = {}
		self.__lines = {}
		self.__scenes = {}
		

	def authenticate(self):

		""" Authenticate user, and get tokens """
		_LOGGER.debug("Authenticating...")
		result = self.__session.post(LOGIN_URL, json={"email": self.__username, "password": self.__password}).json()
		if isinstance(result, dict) and result.get("token") is not None:
			_LOGGER.debug("Authenticated successfully with Noon")
			self.authenticated = True
			self.__token = result.get("token")
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

		""" Get the device details for this account """
		_LOGGER.debug("Refreshing devices...")
		queryUrl = "{}/api/query".format(self.__endpoints["query"])
		result = self.__session.post(queryUrl, headers={"Authorization": "Token {}".format(self.__token), "Content-Type":"application/graphql"}, data="{spaces {guid name lightsOn activeScene{guid name} devices{serial name isOnline line{guid lineState displayName dimmingLevel}} scenes{name guid}}}").json()
		if isinstance(result, dict) and isinstance(result.get("spaces"), list):
			for space in result.get("spaces"):

				# Create the space
				thisSpace = NoonSpace.fromJsonObject(self, space)

				# Debug
				_LOGGER.error("Discovered space '{}'".format(thisSpace.name))
				

		else:
			_LOGGER.error("Invalid device discovery response from Noon")
			_LOGGER.warn("Response: {}".format(result))


	def connect(self):

		if not self.__subscribed:
			self.__subscribed = True
			#self.__event_handle = threading.Event()
			#event_thread = threading.Thread(target=self._thread_event_function)
			#event_thread.start()
			self._thread_event_function()
		else:
			_LOGGER.error("Already attached to event stream!")


	def _thread_event_function(self):
		self.__subscribed = True
		websocket.enableTrace(True)
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
		self.__websocket.run_forever()

		#eventStreamUrl = "{}/api/notifications".format(self.__endpoints["notification-ws"])
		

		return True


def _on_websocket_message(ws, message): 

		_LOGGER.error("Websocket: Got message - {}".format(message))

def _on_websocket_error(ws, error): 

		_LOGGER.error("Websocket: Error - {}".format(error))

def _on_websocket_close(ws): 

		_LOGGER.error("Websocket: Closed")

def _on_websocket_open(ws): 

		_LOGGER.error("Websocket: Opened")