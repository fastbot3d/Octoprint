# coding=utf-8
from octoprint.comm.protocol.repetier import RepetierTextualProtocol
from octoprint.comm.transport import Transport

__author__ = "Gina Häußge <osd@foosel.net>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

import time
import threading
import copy
import os
import re
import logging

import octoprint.util.comm as comm
import octoprint.util as util

from octoprint.settings import settings
from octoprint.events import eventManager, Events

from octoprint.filemanager.destinations import FileDestinations

from octoprint.comm.protocol import State as ProtocolState, Protocol
from octoprint.comm.protocol.reprap import RepRapProtocol
from octoprint.comm.transport.serialTransport import SerialTransport
from octoprint.comm.transport.pipeTransport import PipeTransport

from octoprint.plugin import plugin_manager, ProgressPlugin

def getConnectionOptions():
	"""
	 Retrieves the available ports, baudrates, prefered port and baudrate for connecting to the printer.
	"""
	return {
		"ports": comm.serialList(),
		"baudrates": comm.baudrateList(),
		"portPreference": settings().get(["serial", "port"]),
		"baudratePreference": settings().getInt(["serial", "baudrate"]),
		"autoconnect": settings().getBoolean(["serial", "autoconnect"])
	}

class Printer():
	def __init__(self, fileManager, analysisQueue, printerProfileManager):
		from collections import deque

		self._logger = logging.getLogger(__name__)
		#self._estimationLogger = logging.getLogger("ESTIMATIONS")
		#self._printTimeLogger = logging.getLogger("PRINT_TIME")

		self._analysisQueue = analysisQueue
		self._fileManager = fileManager
		self._printerProfileManager = printerProfileManager

		# state
		self._temps = deque([], 300)
		self._tempBacklog = []

		self._latestMessage = None
		self._messages = deque([], 300)
		self._messageBacklog = []

		self._latestLog = None
		self._log = deque([], 300)
		self._logBacklog = []

		self._state = None

		self._currentZ = None

		self._progress = None
		self._printTime = None
		self._printTimeLeft = None

		self._printAfterSelect = False

		# sd handling
		self._sdPrinting = False
		self._sdStreaming = False
		self._sdFilelistAvailable = threading.Event()
		self._streamingFinishedCallback = None

		self._selectedFile = None
		self._timeEstimationData = None

		# comm
		self._comm = None

		self._protocol = self._createProtocol()

		# callbacks
		self._callbacks = []
		
		#lkj
		self._cmdBeforePrint = []
		self._cmdAfterPrint = []
		
		# progress plugins
		self._lastProgressReport = None
		self._progressPlugins = plugin_manager().get_implementations(ProgressPlugin)

		self._stateMonitor = StateMonitor(
			ratelimit=0.5,
			updateCallback=self._sendCurrentDataCallbacks,
			addTemperatureCallback=self._sendAddTemperatureCallbacks,
			addLogCallback=self._sendAddLogCallbacks,
			addMessageCallback=self._sendAddMessageCallbacks
		)
		self._stateMonitor.reset(
			state={"text": self.getStateString(), "flags": self._getStateFlags()},
			jobData={
				"file": {
					"name": None,
					"size": None,
					"origin": None,
					"date": None
				},
				"estimatedPrintTime": None,
				"lastPrintTime": None,
				"filament": {
					"length": None,
					"volume": None
				}
			},
			progress={"completion": None, "filepos": None, "printTime": None, "printTimeLeft": None},
			currentZ=None
		)

		eventManager().subscribe(Events.METADATA_ANALYSIS_FINISHED, self.onMetadataAnalysisFinished)
		eventManager().subscribe(Events.METADATA_STATISTICS_UPDATED, self.onMetadataStatisticsUpdated)

	#lkj
	def setCmdBeforePrint(self, gcode_cmds):
		self._cmdBeforePrint = gcode_cmds[:]		
		pass

	def setCmdAfterPrint(self, gcode_cmds):
		self._cmdAfterPrint = gcode_cmds[:]		
		pass	
	
	def _getTransportFactory(self):
		transports = self._getSubclassAttributes(Transport, "__transportinfo__", validator=lambda x: not x[2])

		transportType = settings().get(["communication", "transport"])
		for t in transports:
			id, name, abstract, factory = t
			if transportType == id:
				return factory

		return SerialTransport

	def _createProtocol(self):
		transport = self._getTransportFactory()
		protocol_type = settings().get(["communication", "protocol"])

		protocols = self._getSubclassAttributes(Protocol, "__protocolinfo__", validator=lambda x: not x[2])

		protocol_factory = RepRapProtocol
		for p in protocols:
			id, name, abstract, factory = p
			if protocol_type == id:
				protocol_factory = factory
				break

		return protocol_factory(transport, protocol_listener=self)

	def _getSubclassAttributes(self, origin, attribute, converter=lambda o, v: v, validator=lambda x: True):
		result = []

		if hasattr(origin, attribute):
			value = getattr(origin, attribute)
			if validator(value):
				converted = list(converter(origin, value))
				converted.append(origin)
				result.append(converted)

		subclasses = origin.__subclasses__()
		if subclasses:
			for s in subclasses:
				result.extend(self._getSubclassAttributes(s, attribute, converter, validator))

		return result

	#~~ callback handling

	def registerCallback(self, callback):
		self._callbacks.append(callback)
		self._sendInitialStateUpdate(callback)

	def unregisterCallback(self, callback):
		if callback in self._callbacks:
			self._callbacks.remove(callback)

	def _sendAddTemperatureCallbacks(self, data):
		for callback in self._callbacks:
			try: callback.addTemperature(data)
			except: self._logger.exception("Exception while adding temperature data point")

	def _sendAddLogCallbacks(self, data):
		for callback in self._callbacks:
			try: callback.addLog(data)
			except: self._logger.exception("Exception while adding communication log entry")

	def _sendAddMessageCallbacks(self, data):
		for callback in self._callbacks:
			try: callback.addMessage(data)
			except: self._logger.exception("Exception while adding printer message")

	def _sendCurrentDataCallbacks(self, data):
		for callback in self._callbacks:
			try: callback.sendCurrentData(copy.deepcopy(data))
			except: self._logger.exception("Exception while pushing current data")

	def _sendTriggerUpdateCallbacks(self, type):
		for callback in self._callbacks:
			try: callback.sendEvent(type)
			except: self._logger.exception("Exception while pushing trigger update")
	#lkj		
	def sendEventUpdateCallbacks(self, type, playload):
		for callback in self._callbacks:
			try: callback.sendEvent('fastbot', playload)
			except: self._logger.exception("Exception while pushing trigger update")


	def _sendFeedbackCommandOutput(self, name, output):
		for callback in self._callbacks:
			try: callback.sendFeedbackCommandOutput(name, output)
			except: self._logger.exception("Exception while pushing feedback command output")

	#~~ callbacks from protocol

	def onStateChange(self, source, oldState, newState):
		if not source == self._protocol:
			return

		# forward relevant state changes to gcode manager
		if oldState == ProtocolState.PRINTING:
			self._analysisQueue.resume() # printing done, put those cpu cycles to good use
			if self._selectedFile is not None and newState == ProtocolState.OFFLINE or newState == ProtocolState.ERROR:
				# self._fileManager.log_print(FileDestinations.SDCARD if self._selectedFile["sd"] else FileDestinations.LOCAL, self._selectedFile["filename"], time.time(), self._protocol.get_print_time(), False)
				self._fileManager.log_print(self._selectedFile["origin"], self._selectedFile["filename"], time.time(), self._protocol.get_print_time(), False)
				
		elif newState == ProtocolState.PRINTING:
			self._analysisQueue.pause()  # do not analyse files while printing

		self._setState(newState)

	def onTemperatureUpdate(self, source, temperatureData):
		if not source == self._protocol:
			return

		self._addTemperatureData(temperatureData)

	def onProgress(self, source, progress):
		if not source == self._protocol:
			return

		self._setProgressData(progress["completion"], progress["filepos"], progress["printTime"])

	def onZChange(self, source, oldZ, newZ):
		if not source == self._protocol:
			return

		if newZ != oldZ:
			# we have to react to all z-changes, even those that might "go backward" due to a slicer's retraction or
			# anti-backlash-routines. Event subscribes should individually take care to filter out "wrong" z-changes
			eventManager().fire(Events.Z_CHANGE, {"new": newZ, "old": oldZ})

		self._setCurrentZ(newZ)

	def onFileSelected(self, source, filename, filesize, origin):
		if not source == self._protocol:
			return

		self._setJobData(filename, filesize, origin)
		self._stateMonitor.setState({"text": self.getStateString(), "flags": self._getStateFlags()})

		if self._printAfterSelect:
			self.startPrint()
		pass

	def onPrintjobDone(self, source):
		if not source == self._protocol:
			return
		if self._cmdAfterPrint is not None and self._cmdAfterPrint.count > 0:
			self.commands(self._cmdAfterPrint)
			print("lkj onPrintjobDone, send _cmdAfterPrint")
			
		self._setProgressData(100.0, self._selectedFile["filesize"], self._protocol.get_print_time())
		self._stateMonitor.setState({"text": self.getStateString(), "flags": self._getStateFlags()})

		if self._selectedFile is not None:
			# self._fileManager.log_print(FileDestinations.SDCARD if self._selectedFile["sd"] else FileDestinations.LOCAL, self._selectedFile["filename"], time.time(), self._protocol.get_print_time(), True, self._printerProfileManager.get_current_or_default()["id"])
			self._fileManager.log_print(self._selectedFile["origin"], self._selectedFile["filename"], time.time(), self._protocol.get_print_time(), True, self._printerProfileManager.get_current_or_default()["id"])
			

	def onPrintjobCancelled(self, source):
		if not source == self._protocol:
			return

		if self._selectedFile is not None:
			# self._fileManager.log_print(FileDestinations.SDCARD if self._selectedFile["sd"] else FileDestinations.LOCAL, self._selectedFile["filename"], time.time(), self._protocol.get_print_time(), False, self._printerProfileManager.get_current_or_default()["id"])
			self._fileManager.log_print(self._selectedFile["origin"], self._selectedFile["filename"], time.time(), self._protocol.get_print_time(), False, self._printerProfileManager.get_current_or_default()["id"])

	def onFileTransferStarted(self, source, filename, filesize):
		if not source == self._protocol:
			return

		self._sdStreaming = True

		self._setJobData(filename, filesize, FileDestinations.SDCARD)
		self._setProgressData(0.0, 0, 0)
		self._stateMonitor.setState({"text": self.getStateString(), "flags": self._getStateFlags()})

	def onFileTransferDone(self, source):
		if not source == self._protocol:
			return

		self._sdStreaming = False

		if self._streamingFinishedCallback is not None:
			self._streamingFinishedCallback(self._sdRemoteName, FileDestinations.SDCARD)

		self._sdRemoteName = None
		self._setCurrentZ(None)
		self._setJobData(None, None, None)
		self._setProgressData(None, None, None)
		self._stateMonitor.setState({"text": self.getStateString(), "flags": self._getStateFlags()})

	def onSdStateChange(self, source, sdAvailable):
		if not source == self._protocol:
			return

		self._stateMonitor.setState({"text": self.getStateString(), "flags": self._getStateFlags()})

	def onSdFiles(self, source, files):
		if not source == self._protocol:
			return

		eventManager().fire(Events.UPDATED_FILES, {"type": "gcode"})
		self._sdFilelistAvailable.set()

	def onLogTx(self, source, tx):
		if not source == self._protocol:
			return

		self._addLog("Send: %s" % tx)

	def onLogRx(self, source, rx):
		if not source == self._protocol:
			return

		self._addLog("Recv: %s" % rx)

	def onLogError(self, source, error):
		if not source == self._protocol:
			return

		self._addLog("ERROR: %s" % error)

	#~~ callback from metadata analysis event

	def onMetadataAnalysisFinished(self, event, data):
		if self._selectedFile:
			self._setJobData(self._selectedFile["filename"],
							 self._selectedFile["filesize"],
							 self._selectedFile["sd"])

	def onMetadataStatisticsUpdated(self, event, data):
		self._setJobData(self._selectedFile["filename"],
		                 self._selectedFile["filesize"],
		                 self._selectedFile["sd"])

	#~~ progress plugin reporting

	def _reportPrintProgressToPlugins(self, progress):
		if not progress or not self._selectedFile or not "sd" in self._selectedFile or not "filename" in self._selectedFile:
			return

		# storage = "sdcard" if self._selectedFile["sd"] else "local"
		storage = self._selectedFile["origin"]
		filename = self._selectedFile["filename"]

		def call_plugins(storage, filename, progress):
			for name, plugin in self._progressPlugins.items():
				try:
					plugin.on_print_progress(storage, filename, progress)
				except:
					self._logger.exception("Exception while sending print progress to plugin %s" % name)

		thread = threading.Thread(target=call_plugins, args=(storage, filename, progress))
		thread.daemon = False
		thread.start()

	#~~ printer commands

	def connect(self, protocol_option_overrides=None, transport_option_overrides=None, profile=None):
		"""
		 Connects to the printer. If port and/or baudrate is provided, uses these settings, otherwise autodetection
		 will be attempted.
		"""
		self._protocol.disconnect()

		protocol_options = settings().get(["communication", "protocolOptions"], merged=True)
		if protocol_option_overrides is not None and isinstance(protocol_option_overrides, dict):
			protocol_options = util.dict_merge(protocol_options, protocol_option_overrides)

		transport_options = settings().get(["communication", "transportOptions"], merged=True)
		if transport_option_overrides is not None and isinstance(transport_option_overrides, dict):
			transport_options = util.dict_merge(transport_options, transport_option_overrides)

		self._protocol.connect(protocol_options, transport_options)
		self._printerProfileManager.select(profile)

	def disconnect(self):
		"""
		 Closes the connection to the printer.
		"""
		self._protocol.disconnect()
		self._printerProfileManager.deselect()
		eventManager().fire(Events.DISCONNECTED)

	def getConnectionOptions(self):
		connection_options = self._protocol.get_connection_options()

		return {
		"ports": connection_options["port"],
		"baudrates": connection_options["baudrate"],
		"portPreference": settings().get(["serial", "port"]),
		"baudratePreference": settings().getInt(["serial", "baudrate"]),
		"autoconnect": settings().getBoolean(["serial", "autoconnect"])
		}
	def command(self, command):
		self._protocol.send_manually(command)

	def commands(self, commands):
		self.command(commands)

	def jog(self, axis, amount):
		if not axis or not amount:
			return

		printer_profile = self._printerProfileManager.get_current_or_default()
		axis = axis.lower()
		if axis in printer_profile["axes"]:
			speed = printer_profile["axes"][axis]["speed"]
			speed = float(speed)
			speed = int(speed) * 60
			print("lkj jog speed:%s" % str(speed))
			self._protocol.jog(axis, amount, speed)
	#lkj add		
	def jogSpeed(self, axis, amount, speed):
		if not axis or not amount or not speed:
			return
	
		printer_profile = self._printerProfileManager.get_current_or_default()
		axis = axis.lower()
		if axis in printer_profile["axes"]:			
			speed1 = float(speed)
			speed1 = int(speed1) * 60
			print("lkj jog speed:%s" % str(speed1))
			self._protocol.jog(axis, amount, speed1)
			
	def feedSpeed(self, speed):
		self._protocol.feedSpeed(speed)
		
	def fanControl(self, fanId, on):
		self._protocol.fanControl(fanId, on)
		
		
	def home(self, axes):
		self._protocol.home(axes)
	
		

	def extrude(self, amount):
		if not amount:
			return

		printer_profile = self._printerProfileManager.get_current_or_default()
		if "e" in printer_profile["axes"]:
			speed = printer_profile["axes"]["e"]["speed"]
			self._protocol.extrude(amount, speed)
	#lkj add
	def extrudeSpeed(self, amount, speed):
		if not amount:
			return
	
		printer_profile = self._printerProfileManager.get_current_or_default()
		if "e" in printer_profile["axes"]:
			speed1 = float(speed)
			speed1 = int(speed1) * 60
			print("lkj extrudeSpeed speed:%s" % str(speed1))
			self._protocol.extrude(amount, speed1)	

	def changeTool(self, tool):
		self._protocol.change_tool(tool)

	def setTemperature(self, type, value):
		self._protocol.set_temperature(type, value)

	def setTemperatureOffset(self, offsets):
		current_offsets = self._protocol.get_temperature_offsets()

		new_offsets = {}
		new_offsets.update(current_offsets)

		for key in offsets:
			if key == "bed" or re.match("tool\d+", key):
				new_offsets[key] = offsets[key]

		self._protocol.set_temperature_offsets(new_offsets)
		self._stateMonitor.setTempOffsets(new_offsets)

	def selectFile(self, filename, origin, printAfterSelect=False):
		self._printAfterSelect = printAfterSelect
		self._protocol.select_file(filename, origin)
		self._setProgressData(0, None, None)
		self._setCurrentZ(None)

	def unselectFile(self):
		self._protocol.deselect_file()
		self._setProgressData(0, None, None)
		self._setCurrentZ(None)

	def startPrint(self):
		"""
		 Starts the currently loaded print job.
		 Only starts if the printer is connected and operational, not currently printing and a printjob is loaded
		"""
		if not self._protocol.is_operational() or self._protocol.is_busy():
			return
		if self._selectedFile is None:
			return
		if self._cmdBeforePrint is not None and self._cmdBeforePrint.count > 0:
			self.commands(self._cmdBeforePrint)
			print("lkj startPrint, send cmdBeforePrint")
			

		self._timeEstimationData = TimeEstimationHelper()
		self._lastProgressReport = None
		self._setCurrentZ(None)
		self._protocol.start_print()

	def togglePausePrint(self):
		"""
		 Pause the current printjob.
		"""
		self._protocol.pause_print()

	def cancelPrint(self, disableMotorsAndHeater=True):
		"""
		 Cancel the current printjob.
		"""
		self._protocol.cancel_print()

		if disableMotorsAndHeater:
			printer_profile = self._printerProfileManager.get_current_or_default()
			extruder_count = printer_profile["extruder"]["count"]

			# disable motors, switch off hotends, bed and fan
			commands = ["M84 S1"]
			#commands = ["M105"]
			#commands.extend(["G92 X0 Y0 Z0 E0"])
			#commands.extend(["M84"])
			#commands.extend(map(lambda x: "M104 T%d S0" % x, range(extruder_count)))
			#commands.extend(["M140 S0", "M106 S0"])
			self.commands(commands)

		# reset progress, height, print time
		self._setCurrentZ(None)
		self._setProgressData(None, None, None)

		# mark print as failure
		if self._selectedFile is not None:
			#lkj self._fileManager.log_print(FileDestinations.SDCARD if self._selectedFile["sd"] else FileDestinations.LOCAL, self._selectedFile["filename"], time.time(), self._protocol.get_print_time(), False, self._printerProfileManager.get_current_or_default()["id"])
			self._fileManager.log_print(self._selectedFile["origin"], self._selectedFile["filename"], time.time(), self._protocol.get_print_time(), False, self._printerProfileManager.get_current_or_default()["id"])
			
			payload = {
				"file": self._selectedFile["filename"],
				"origin": FileDestinations.LOCAL
			}
			#lkj if self._selectedFile["sd"]:
			#lkj	payload["origin"] = FileDestinations.SDCARD
			payload["origin"] = self._selectedFile["origin"]
			eventManager().fire(Events.PRINT_FAILED, payload)

	#~~ state monitoring

	def _setCurrentZ(self, currentZ):
		self._currentZ = currentZ
		self._stateMonitor.setCurrentZ(self._currentZ)

	def _setState(self, state):
		self._state = state
		self._stateMonitor.setState({"text": self.getStateString(), "flags": self._getStateFlags()})

	def _addLog(self, log):
		self._log.append(log)
		self._stateMonitor.addLog(log)

	def _addMessage(self, message):
		self._messages.append(message)
		self._stateMonitor.addMessage(message)

	def _estimateTotalPrintTime(self, progress, printTime):
		if not progress or not printTime:
			#self._estimationLogger.info("{progress};{printTime};;;;".format(**locals()))
			return None

		else:
			newEstimate = printTime * 100 / progress
			self._timeEstimationData.update(newEstimate)

			result = None
			if self._timeEstimationData.is_stable():
				result = self._timeEstimationData.average_total_rolling

			#averageTotal = self._timeEstimationData.average_total
			#averageTotalRolling = self._timeEstimationData.average_total_rolling
			#averageDistance = self._timeEstimationData.average_distance

			#self._estimationLogger.info("{progress};{printTime};{newEstimate};{averageTotal};{averageTotalRolling};{averageDistance}".format(**locals()))

			return result

	def _setProgressData(self, progress, filepos, printTime):
		estimatedTotalPrintTime = self._estimateTotalPrintTime(progress, printTime)
		statisticalTotalPrintTime = None
		totalPrintTime = estimatedTotalPrintTime

		if self._selectedFile and "estimatedPrintTime" in self._selectedFile and self._selectedFile["estimatedPrintTime"]:
			statisticalTotalPrintTime = self._selectedFile["estimatedPrintTime"]
			if progress and printTime:
				if estimatedTotalPrintTime is None:
					totalPrintTime = statisticalTotalPrintTime
				else:
					if progress < 50:
						sub_progress = progress * 2 / 100
					else:
						sub_progress = 1.0
					totalPrintTime = (1 - sub_progress) * statisticalTotalPrintTime + sub_progress * estimatedTotalPrintTime

		#self._printTimeLogger.info("{progress};{printTime};{estimatedTotalPrintTime};{statisticalTotalPrintTime};{totalPrintTime}".format(**locals()))

		self._progress = progress
		self._printTime = printTime
		self._printTimeLeft = totalPrintTime - printTime if (totalPrintTime is not None and printTime is not None) else None

		self._stateMonitor.setProgress({
			"completion": self._progress,
			"filepos": filepos,
			"printTime": int(self._printTime) if self._printTime is not None else None,
			"printTimeLeft": int(self._printTimeLeft) if self._printTimeLeft is not None else None
		})

		if progress:
			progress_int = int(progress)
			if self._lastProgressReport != progress_int:
				self._lastProgressReport = progress_int
				self._reportPrintProgressToPlugins(progress_int)


	def _addTemperatureData(self, temperatureData):
		currentTimeUtc = int(time.time())

		data = {
			"time": currentTimeUtc
		}
		for tool in temperatureData.keys():
			data[tool] = {
				"actual": temperatureData[tool][0],
				"target": temperatureData[tool][1]
			}

		self._temps.append(data)

		self._stateMonitor.addTemperature(data)

	def _setJobData(self, filename, filesize, origin):
		sd = origin == FileDestinations.SDCARD
		if filename is not None:
			self._selectedFile = {
				"filename": filename,
				"filesize": filesize,
			        "origin": origin,   #lkj add
				"sd": sd,
				"estimatedPrintTime": None
			}
		else:
			self._selectedFile = None
			self._stateMonitor.setJobData({
				"file": {
					"name": None,
					"origin": None,
					"size": None,
					"date": None
				},
				"estimatedPrintTime": None,
				"averagePrintTime": None,
				"lastPrintTime": None,
				"filament": None,
			})
			return

		estimatedPrintTime = None
		lastPrintTime = None
		averagePrintTime = None
		date = None
		filament = None
		if filename:
			# Use a string for mtime because it could be float and the
			# javascript needs to exact match
			if not sd:
				date = int(os.stat(filename).st_ctime)

			try:
				#lkj fileData = self._fileManager.get_metadata(FileDestinations.SDCARD if sd else FileDestinations.LOCAL, filename)
				fileData = self._fileManager.get_metadata(self._selectedFile["origin"], filename)
				
			except:
				fileData = None
			if fileData is not None:
				if "analysis" in fileData:
					if estimatedPrintTime is None and "estimatedPrintTime" in fileData["analysis"]:
						estimatedPrintTime = fileData["analysis"]["estimatedPrintTime"]
					if "filament" in fileData["analysis"].keys():
						filament = fileData["analysis"]["filament"]
				if "statistics" in fileData:
					printer_profile = self._printerProfileManager.get_current_or_default()["id"]
					if "averagePrintTime" in fileData["statistics"] and printer_profile in fileData["statistics"]["averagePrintTime"]:
						averagePrintTime = fileData["statistics"]["averagePrintTime"][printer_profile]
					if "lastPrintTime" in fileData["statistics"] and printer_profile in fileData["statistics"]["lastPrintTime"]:
						lastPrintTime = fileData["statistics"]["lastPrintTime"][printer_profile]

				if averagePrintTime is not None:
					self._selectedFile["estimatedPrintTime"] = averagePrintTime
				elif estimatedPrintTime is not None:
					# TODO apply factor which first needs to be tracked!
					self._selectedFile["estimatedPrintTime"] = estimatedPrintTime

		self._stateMonitor.setJobData({
			"file": {
				"name": os.path.basename(filename) if filename is not None else None,
				"origin": origin,
				"size": filesize,
				"date": date
			},
			"estimatedPrintTime": estimatedPrintTime,
			"averagePrintTime": averagePrintTime,
			"lastPrintTime": lastPrintTime,
			"filament": filament,
		})

	def _sendInitialStateUpdate(self, callback):
		try:
			data = self._stateMonitor.getCurrentData()
			data.update({
				"temps": list(self._temps),
				"logs": list(self._log),
				"messages": list(self._messages)
			})
			callback.sendHistoryData(data)
		except Exception, err:
			import sys
			sys.stderr.write("ERROR: %s\n" % str(err))
			pass

	def _getStateFlags(self):
		return {
			"operational": self.isOperational(),
			"printing": self.isPrinting(),
			"closedOrError": self.isClosedOrError(),
			"error": self.isError(),
			"paused": self.isPaused(),
			"ready": self.isReady(),
			"sdReady": self.isSdReady()
		}

	#~~ callbacks triggered from self._comm

	def mcReceivedRegisteredMessage(self, command, output):
		self._sendFeedbackCommandOutput(command, output)

	def mcForceDisconnect(self):
		self.disconnect()

	#~~ sd file handling

	def getSdFiles(self):
		if not self._protocol.is_sd_ready():
			return []
		return self._protocol.get_sd_files()

	def addSdFile(self, filename, absolutePath, streamingFinishedCallback):
		if self._protocol.is_busy() or not self._protocol.is_sd_ready():
			logging.error("No connection to printer or printer is busy")
			return

		self._streamingFinishedCallback = streamingFinishedCallback

		self.refreshSdFiles(blocking=True)
		existingSdFiles = map(lambda x: x[0], self._protocol.get_sd_files())

		self._sdRemoteName = util.getDosFilename(filename, existingSdFiles)
		self._protocol.add_sd_file(absolutePath, filename, self._sdRemoteName)

		return self._sdRemoteName

	def deleteSdFile(self, filename):
		if not self._protocol.is_sd_ready():
			return
		self._protocol.remove_sd_file(filename)

	def initSdCard(self):
		self._protocol.init_sd()

	def releaseSdCard(self):
		if not self._protocol.is_sd_ready() or self._protocol.is_busy():
			return
		self._protocol.release_sd()

	def refreshSdFiles(self, blocking=False):
		"""
		Refreshs the list of file stored on the SD card attached to printer (if available and printer communication
		available). Optional blocking parameter allows making the method block (max 10s) until the file list has been
		received (and can be accessed via self._protocol.get_sd_files()). Defaults to a asynchronous operation.
		"""
		if not self._protocol.is_sd_ready():
			return
		self._sdFilelistAvailable.clear()
		self._protocol.refresh_sd_files()
		if blocking:
			self._sdFilelistAvailable.wait(10000)

	#~~ state reports

	def getStateString(self):
		"""
		 Returns a human readable string corresponding to the current communication state.
		"""
		return self._state

	def getCurrentData(self):
		return self._stateMonitor.getCurrentData()

	def getCurrentJob(self):
		currentData = self._stateMonitor.getCurrentData()
		return currentData["job"]

	def getCurrentTemperatures(self):
		temperatures = self._protocol.get_current_temperatures()
		offsets = self._protocol.get_temperature_offsets()

		result = {}
		result.update(temperatures)
		for key, tool in result:
			tool["offset"] = offsets[key] if key in offsets and offsets[key] is not None else 0

		return result

	def getTemperatureHistory(self):
		return self._temps

	def getCurrentConnection(self):
		opt = self._protocol.get_current_connection()
		if "port" in opt.keys() and "baudrate" in opt.keys():
			return self._protocol.get_state(), opt["port"], opt["baudrate"], self._printerProfileManager.get_current_or_default()
		return self._protocol.get_state(), None, None, None

	def isClosedOrError(self):
		return self._protocol.get_state() == ProtocolState.OFFLINE or self._protocol == ProtocolState.ERROR

	def isOperational(self):
		return not self.isClosedOrError()

	def isPrinting(self):
		return self._protocol.get_state() == ProtocolState.PRINTING

	def isPaused(self):
		return self._protocol.get_state() == ProtocolState.PAUSED

	def isError(self):
		return self._protocol.get_state() == ProtocolState.ERROR

	def isReady(self):
		return self.isOperational() and not self._protocol.is_streaming()

	def isSdReady(self):
		if not settings().getBoolean(["feature", "sdSupport"]):
			return False
		else:
			return self._protocol.is_sd_ready()

class StateMonitor(object):
	def __init__(self, ratelimit, updateCallback, addTemperatureCallback, addLogCallback, addMessageCallback):
		self._ratelimit = ratelimit
		self._updateCallback = updateCallback
		self._addTemperatureCallback = addTemperatureCallback
		self._addLogCallback = addLogCallback
		self._addMessageCallback = addMessageCallback

		self._state = None
		self._jobData = None
		self._gcodeData = None
		self._sdUploadData = None
		self._currentZ = None
		self._progress = None

		self._offsets = {}

		self._changeEvent = threading.Event()
		self._stateMutex = threading.Lock()

		self._lastUpdate = time.time()
		self._worker = threading.Thread(target=self._work)
		self._worker.daemon = True
		self._worker.start()

	def reset(self, state=None, jobData=None, progress=None, currentZ=None):
		self.setState(state)
		self.setJobData(jobData)
		self.setProgress(progress)
		self.setCurrentZ(currentZ)

	def addTemperature(self, temperature):
		self._addTemperatureCallback(temperature)
		self._changeEvent.set()

	def addLog(self, log):
		self._addLogCallback(log)
		self._changeEvent.set()

	def addMessage(self, message):
		self._addMessageCallback(message)
		self._changeEvent.set()

	def setCurrentZ(self, currentZ):
		self._currentZ = currentZ
		self._changeEvent.set()

	def setState(self, state):
		with self._stateMutex:
			self._state = state
			self._changeEvent.set()

	def setJobData(self, jobData):
		self._jobData = jobData
		self._changeEvent.set()

	def setProgress(self, progress):
		self._progress = progress
		self._changeEvent.set()

	def setTempOffsets(self, offsets):
		self._offsets = offsets
		self._changeEvent.set()

	def _work(self):
		while True:
			self._changeEvent.wait()

			with self._stateMutex:
				now = time.time()
				delta = now - self._lastUpdate
				additionalWaitTime = self._ratelimit - delta
				if additionalWaitTime > 0:
					time.sleep(additionalWaitTime)

				data = self.getCurrentData()
				self._updateCallback(data)
				self._lastUpdate = time.time()
				self._changeEvent.clear()

	def getCurrentData(self):
		return {
			"state": self._state,
			"job": self._jobData,
			"currentZ": self._currentZ,
			"progress": self._progress,
			"offsets": self._offsets
		}


class TimeEstimationHelper(object):

	STABLE_THRESHOLD = 0.1
	STABLE_COUNTDOWN = 250
	STABLE_ROLLING_WINDOW = 250

	def __init__(self):
		import collections
		self._distances = collections.deque([], self.__class__.STABLE_ROLLING_WINDOW)
		self._totals = collections.deque([], self.__class__.STABLE_ROLLING_WINDOW)
		self._sum_total = 0
		self._count = 0
		self._stable_counter = None

	def is_stable(self):
		return self._stable_counter is not None and self._stable_counter >= self.__class__.STABLE_COUNTDOWN

	def update(self, newEstimate):
			old_average_total = self.average_total

			self._sum_total += newEstimate
			self._totals.append(newEstimate)
			self._count += 1

			if old_average_total:
				self._distances.append(abs(self.average_total - old_average_total))

			if -1.0 * self.__class__.STABLE_THRESHOLD < self.average_distance < self.__class__.STABLE_THRESHOLD:
				if self._stable_counter is None:
					self._stable_counter = 0
				else:
					self._stable_counter += 1
			else:
				self._stable_counter = None

	@property
	def average_total(self):
		if not self._count:
			return None
		else:
			return self._sum_total / self._count

	@property
	def average_total_rolling(self):
		if not self._count or self._count < self.__class__.STABLE_ROLLING_WINDOW:
			return None
		else:
			return sum(self._totals) / len(self._totals)

	@property
	def average_distance(self):
		if not self._count or self._count < self.__class__.STABLE_ROLLING_WINDOW + 1:
			return None
		else:
			return sum(self._distances) / len(self._distances)

