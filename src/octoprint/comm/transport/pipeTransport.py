# coding=utf-8
__author__ = "Gina Häußge <osd@foosel.net>"
__license__ = "GNU Affero General Public License http://www.gnu.org/licenses/agpl.html"
__copyright__ = "Copyright (C) 2014 Gina Häußge - Released under terms of the AGPLv3 License"

import os
import glob
import threading
#lkj import serial

try:
	import _winreg
except:
	pass

from . import Transport, TransportProperties, State, SendTimeout, TransportError
from octoprint.comm.transport.pipeReadWrite import PipeReadWrite
from octoprint.util import getExceptionString
from octoprint.util.virtual import VirtualPrinter
from octoprint.settings import settings
from octoprint.events import eventManager, Events

class PipeTransport(Transport):

	__transportinfo__ = ("pipe", "Pipe", False)

	def __init__(self, messageReceiver, stateReceiver, logReceiver):
		Transport.__init__(self, messageReceiver, stateReceiver, logReceiver)

		self._pipe = None
		self._port = None
		self._baudrate = None
		self._connectionTimeout = None
		self._writeTimeout = None
		self._readTimeout = None

		self._timeoutCounter = 0
		self._maxTimeouts = 20

		self._thread = None

	def get_properties(self):
		return {
			TransportProperties.FLOWCONTROL: False
		}

	def get_connection_options(self):
		print("in pipeTransport.py, call get_connection_options")
		return {
			"port": 'PIPE',
			"baudrate": 115200
		}
		"""lkj	"port": self.__getPipeList(),
			"baudrate": self.__getBaudrateList()
		"""

	def connect(self, opt):
		Transport.connect(self, opt)

		#lkj self._port = opt["port"] if "port" in opt else None
		#lkj self._baudrate = opt["baudrate"] if "baudrate" in opt else None

		self._readTimeout = opt["timeout"]["read"] if "timeout" in opt and "read" in opt["timeout"] else 5.0
		self._writeTimeout = opt["timeout"]["write"] if "timeout" in opt and "write" in opt["timeout"] else 0.5

		if self._connect():
			self._thread = threading.Thread(target=self._monitor, name="PipeTransportMonitor")
			self._thread.daemon = True
			self._thread.start()

	def disconnect(self, onError=False):
		try:
			if self._pipe is not None:
				self._pipe.close()
		finally:
			self._pipe = None
		self._thread = None
		Transport.disconnect(self, onError)

	def send(self, command):
		commandToSend = command + "\n"
		try:
			self._pipe.write(commandToSend)
			self._transport_logger.info("Send: %s" % command)
			self.logTx(command)
#lkj		except serial.SerialTimeoutException:
#			self._transport_logger.warn("Timeout while sending: %s" % command)
#			self.logError("Pipe timeout while writing to pipe port, try again later.")
#			raise SendTimeout()
		except:
			exceptionString = getExceptionString()
			self.logError("Unexpected error while writing pipe port: %s" % exceptionString)
			self.onError(exceptionString)
			self.disconnect(True)
			raise TransportError()

	def receive(self):
		return self._readline()

	def _monitor(self):
		error = None
		while True:
			line = self._readline()
			if line is None:
				error = "Pipe connection closed unexpectedly"
				break
			if line == "":
				self._timeoutCounter += 1
				self.onTimeout()
				if self._maxTimeouts and self._timeoutCounter > self._maxTimeouts:
					error = "Printer did not respond at all over %d retries, considering it dead" % self._maxTimeouts
					break
			else:
				self._timeoutCounter = 0
			self.onMessageReceived(line.strip())

		if error is not None:
			self._transport_logger.error(error)
			self.logError(error)
			self.onError(error)
			# TODO further error handling

	def _connect(self):
		self.changeState(State.OPENING_CONNECTION)
		
		self._pipe = PipeReadWrite(self._readTimeout, self._writeTimeout)
		self.changeState(State.CONNECTED)
		self._transport_logger.debug("Connected to %s" % self._pipe)
		#eventManager().fire(Events.CONNECTED, {"port": self._port, "baudrate": self._baudrate})
		eventManager().fire(Events.CONNECTED, {"port": "pipe", "baudrate": "115200"})
		return True

	def _readline(self):
		if self._pipe is None:
			return None

		try:
			line = self._pipe.readline()
		except:
			exceptionString = getExceptionString()
			print("lkj Unexpected error while reading pipe port: %s" % exceptionString)
			self.logError("Unexpected error while reading pipe port: %s" % exceptionString)
			self.onError(exceptionString)
			self.disconnect()
			return None

		if line != "":
			loggable_line = unicode(line, "ascii", "replace").encode("ascii", "replace").rstrip()
			self._transport_logger.debug("Recv: %s" % loggable_line)
			self.logRx(loggable_line)
		return line

	def __getPipeList(self):
		baselist=[]
		if os.name == "nt":
			try:
				key=_winreg.OpenKey(_winreg.HKEY_LOCAL_MACHINE,"HARDWARE\\DEVICEMAP\\SERIALCOMM")
				i=0
				while(1):
					baselist+=[_winreg.EnumValue(key,i)[1]]
					i+=1
			except:
				pass
		baselist = baselist \
				   + glob.glob("/dev/ttyUSB*") \
				   + glob.glob("/dev/ttyACM*") \
				   + glob.glob("/dev/ttyAMA*") \
				   + glob.glob("/dev/tty.usb*") \
				   + glob.glob("/dev/cu.*") \
				   + glob.glob("/dev/rfcomm*")

		additionalPorts = settings().get(["serial", "additionalPorts"])
		for additional in additionalPorts:
			baselist += glob.glob(additional)

		prev = settings().get(["serial", "port"])
		if prev in baselist:
			baselist.remove(prev)
			baselist.insert(0, prev)
		if settings().getBoolean(["devel", "virtualPrinter", "enabled"]):
			baselist.append("VIRTUAL")
		return baselist

	def __getBaudrateList(self):
		ret = [250000, 230400, 115200, 57600, 38400, 19200, 9600]
		prev = settings().getInt(["serial", "baudrate"])
		if prev in ret:
			ret.remove(prev)
			ret.insert(0, prev)
		return ret
