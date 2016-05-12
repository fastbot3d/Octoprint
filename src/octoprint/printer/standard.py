# coding=utf-8
"""
This module holds the standard implementation of the :class:`PrinterInterface` and it helpers.
"""

from __future__ import absolute_import

__author__ = "Gina Häußge <osd@foosel.net>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'
__copyright__ = "Copyright (C) 2014 The OctoPrint Project - Released under terms of the AGPLv3 License"

import copy
import logging
import os
import threading
import time

import flask
import math

from octoprint import util as util
from octoprint.events import eventManager, Events
from octoprint.filemanager import FileDestinations
from octoprint.plugin import plugin_manager, ProgressPlugin
from octoprint.printer import PrinterInterface, PrinterCallback, UnknownScript
from octoprint.printer.estimation import TimeEstimationHelper
from octoprint.settings import settings
from octoprint.util import comm as comm
from octoprint.util import InvariantContainer


class Printer(PrinterInterface, comm.MachineComPrintCallback):
	"""
	Default implementation of the :class:`PrinterInterface`. Manages the communication layer object and registers
	itself with it as a callback to react to changes on the communication layer.
	"""

	def __init__(self, fileManager, analysisQueue, printerProfileManager):
		from collections import deque

		self._logger = logging.getLogger(__name__)

		self._analysisQueue = analysisQueue
		self._fileManager = fileManager
		self._printerProfileManager = printerProfileManager

		# state
		# TODO do we really need to hold the temperature here?
		self._temp = None
		self._bedTemp = None
		self._targetTemp = None
		self._targetBedTemp = None
		self._temps = TemperatureHistory(cutoff=settings().getInt(["temperature", "cutoff"])*60)
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
		
		#lkj 
		self._progress_update_interval = 3			
		self._progress_update_last = time.time()	
		
		self._temp_update_interval = 2	
		self._temp_update_last = time.time()	
		self._last_read_temp_time =  0
		timeoutThread = threading.Thread(target=self._timeoutWorker)
		timeoutThread.daemon = True
		timeoutThread.start()		
		self._last_connect_time = time.time()

		# comm
		self._comm = None

		# callbacks
		self._callbacks = []

		# progress plugins
		self._lastProgressReport = None
		self._progressPlugins = plugin_manager().get_implementations(ProgressPlugin)

		self._stateMonitor = StateMonitor(
			interval=1,
			on_update=self._sendCurrentDataCallbacks,
			on_add_temperature=self._sendAddTemperatureCallbacks,
			on_add_log=self._sendAddLogCallbacks,
			on_add_message=self._sendAddMessageCallbacks
		)
		self._stateMonitor.reset(
			state={"text": self.get_state_string(), "flags": self._getStateFlags()},
			job_data={
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
			current_z=None
		)

		eventManager().subscribe(Events.METADATA_ANALYSIS_FINISHED, self._on_event_MetadataAnalysisFinished)
		eventManager().subscribe(Events.METADATA_STATISTICS_UPDATED, self._on_event_MetadataStatisticsUpdated)

	#lkj 
	def _timeoutWorker(self, timeout=9):
		while True :
			now = time.time()
			delta = now - self._last_read_temp_time
			diff = delta - timeout
			
			if self._last_read_temp_time == 0:
				time.sleep(3)
				continue
			#print("lkj read delta:%s, diff:%s" % (str(delta), str(diff)))
			if diff > 0 and diff < 300 and (self._comm is not None and self._comm.isOperational()):
				self.disconnect()
				print("lkj timeout, disconnect!!!!")	
			else :
				time.sleep(3)
				
	#~~ handling of PrinterCallbacks	

	def register_callback(self, callback):
		if not isinstance(callback, PrinterCallback):
			self._logger.warn("Registering an object as printer callback which doesn't implement the PrinterCallback interface")

		self._callbacks.append(callback)
		self._sendInitialStateUpdate(callback)

	def unregister_callback(self, callback):
		if callback in self._callbacks:
			self._callbacks.remove(callback)

	def _sendAddTemperatureCallbacks(self, data):
		for callback in self._callbacks:
			try: callback.on_printer_add_temperature(data)
			except: self._logger.exception("Exception while adding temperature data point")

	def _sendAddLogCallbacks(self, data):
		for callback in self._callbacks:
			try: callback.on_printer_add_log(data)
			except: self._logger.exception("Exception while adding communication log entry")

	def _sendAddMessageCallbacks(self, data):
		for callback in self._callbacks:
			try: callback.on_printer_add_message(data)
			except: self._logger.exception("Exception while adding printer message")

	def _sendCurrentDataCallbacks(self, data):
		for callback in self._callbacks:
			try: callback.on_printer_send_current_data(copy.deepcopy(data))
			except: self._logger.exception("Exception while pushing current data")

	#~~ callback from metadata analysis event

	def _on_event_MetadataAnalysisFinished(self, event, data):
		if self._selectedFile:
			self._setJobData(self._selectedFile["filename"],
							 self._selectedFile["filesize"],
			                                  self._selectedFile["origin"])
							 #lkj self._selectedFile["sd"])

	def _on_event_MetadataStatisticsUpdated(self, event, data):
		self._setJobData(self._selectedFile["filename"],
		                 self._selectedFile["filesize"],
		                 self._selectedFile["origin"])
				#lkj self._selectedFile["sd"])

	#~~ progress plugin reporting

	def _reportPrintProgressToPlugins(self, progress):
		if not progress or not self._selectedFile or not "sd" in self._selectedFile or not "filename" in self._selectedFile:
			return

		storage = "sdcard" if self._selectedFile["sd"] else "local"
		filename = self._selectedFile["filename"]

		def call_plugins(storage, filename, progress):
			for plugin in self._progressPlugins:
				try:
					plugin.on_print_progress(storage, filename, progress)
				except:
					self._logger.exception("Exception while sending print progress to plugin %s" % plugin._identifier)

		thread = threading.Thread(target=call_plugins, args=(storage, filename, progress))
		thread.daemon = False
		thread.start()

	#~~ PrinterInterface implementation

	def connect(self, port=None, baudrate=None, profile=None):
		"""
		 Connects to the printer. If port and/or baudrate is provided, uses these settings, otherwise autodetection
		 will be attempted.
		"""
		
		now = time.time()
		print("lkj now=%s last=%s" %(str(now), str(self._last_connect_time)))
		if now - self._last_connect_time < 5:
			self._last_connect_time = time.time()
			return;
		if self._comm is not None:				
			self._comm.close()			
		self._printerProfileManager.select(profile)
		self._comm = comm.MachineCom(port, baudrate, callbackObject=self, printerProfileManager=self._printerProfileManager)
		self._last_connect_time = now

	def disconnect(self):
		"""
		 Closes the connection to the printer.
		"""
		if self._comm is not None:
			self._comm.close()
		self._comm = None
		self._printerProfileManager.deselect()
		eventManager().fire(Events.DISCONNECTED)
		self._last_read_temp_time = 0
		
	def get_transport(self):

		if self._comm is None:
			return None

		return self._comm.getTransport()
	getTransport = util.deprecated("getTransport has been renamed to get_transport", since="1.2.0-dev-590", includedoc="Replaced by :func:`get_transport`")

	def fake_ack(self):
		if self._comm is None:
			return

		self._comm.fakeOk()
		
	def shellcommand(self, cmd): #lkj
		def _shellThread(cmd=None, a=0):
			print("cmd:%s thread start" % str(cmd))
			if cmd is None:
				return 
			
			self._stateMonitor.add_log("output:-------start to excute " + str(cmd) + "-------")
			import sarge
			#cmd = ['/bin/ls', '-la', '/']			
			p = sarge.run(cmd,  async=True, stdout=sarge.Capture(), stderr=sarge.Capture())
			p.wait_events()			
			try:
				while p.returncodes[0] is None:
					#print("return code:%s" % str(p.returncodes))
					line = p.stdout.readline(timeout=1)
					if not line:
						line = p.stderr.readline(timeout=1)
						if not line:
							p.commands[0].poll()
							continue	
						else :
							line = line[0:len(line)-1]  #remove \n
							self._stateMonitor.add_log("output:" + str(line))							
						#p.commands[0].poll()
						#continue		
					else :
						line = line[0:len(line)-1]  #remove \n
						self._stateMonitor.add_log("output:" + str(line))
						#print("output:%s" % str(line))					
			finally:
				p.close()
				self._stateMonitor.add_log("output:------- exit" + str(cmd) + "-------")
			print("cmd:%s thread exit" % str(cmd))
		cmd = str(cmd)
		print("cmd:%s" % cmd)
		shellThread = threading.Thread(target=_shellThread, args=(cmd, 1))
		shellThread.start()			
		pass

	def commands(self, commands):
		"""
		Sends one or more gcode commands to the printer.
		"""
		if self._comm is None:
			return

		if not isinstance(commands, (list, tuple)):
			commands = [commands]

		for command in commands:
			#lkj M602 for filament
			if "M602" in command or "M106" in command \
			   or "M176" in command or "M150" in command :
				self._comm._doSendEmergency(command)
			else :				
				self._comm.sendCommand(command)

	def script(self, name, context=None):
		if self._comm is None:
			return

		if name is None or not name:
			raise ValueError("name must be set")

		result = self._comm.sendGcodeScript(name, replacements=context)
		if not result:
			raise UnknownScript(name)

	def jog(self, axis, amount):
		if not isinstance(axis, (str, unicode)):
			raise ValueError("axis must be a string: {axis}".format(axis=axis))

		axis = axis.lower()
		if not axis in PrinterInterface.valid_axes:
			raise ValueError("axis must be any of {axes}: {axis}".format(axes=", ".join(PrinterInterface.valid_axes), axis=axis))
		if not isinstance(amount, (int, long, float)):
			raise ValueError("amount must be a valid number: {amount}".format(amount=amount))

		printer_profile = self._printerProfileManager.get_current_or_default()
		movement_speed = printer_profile["axes"][axis]["speed"]
		self.commands(["G91", "G1 %s%.4f F%d" % (axis.upper(), amount, movement_speed), "G90"])
	#lkj
	def jogSpeed(self, axis, amount, speed):
		if not isinstance(axis, (str, unicode)):
			raise ValueError("axis must be a string: {axis}".format(axis=axis))

		axis = axis.lower()
		if not axis in PrinterInterface.valid_axes:
			raise ValueError("axis must be any of {axes}: {axis}".format(axes=", ".join(PrinterInterface.valid_axes), axis=axis))
		if not isinstance(amount, (int, long, float)):
			raise ValueError("amount must be a valid number: {amount}".format(amount=amount))
		
		speed1 = float(speed)
		speed1 = int(speed1) * 60
		print("lkj jog speed:%s" % str(speed1))		
		movement_speed = speed1
		self.commands(["G91", "G1 %s%.4f F%d" % (axis.upper(), amount, movement_speed), "G90"])

	def fanControl(self, fanId, onOff):
		#cmd = []
		cmd = ""
		on = str(onOff * 255)
		if fanId == 1 :
			#cmd.append("M106 S" + on)
			cmd="M106 S" + on
		if fanId == 2 :
			#cmd.append("M106 N2 S" + on)		
			cmd = "M106 N2 S" + on
		if fanId == 3:
			#cmd.append("M176 S" + on)
			cmd = "M176 S" + on
			'''  old code
			if on == "255":
				cmd.append("M176 S255")
			else :
				cmd.append("M177")				
			'''
		if fanId == 4:
			#cmd.append("M150 R" + on)
			cmd ="M150 R" + on
		if fanId == 5:
			#cmd.append("M150 G" + on)
			cmd ="M150 G" + on
		if fanId == 6:
			#cmd.append("M150 B" + on)
			cmd = "M150 B" + on
			
		self._comm._doSendEmergency(cmd)
		#self.commands(cmd)

	def home(self, axes):
		if not isinstance(axes, (list, tuple)):
			if isinstance(axes, (str, unicode)):
				axes = [axes]
			else:
				raise ValueError("axes is neither a list nor a string: {axes}".format(axes=axes))

		validated_axes = filter(lambda x: x in PrinterInterface.valid_axes, map(lambda x: x.lower(), axes))
		if len(axes) != len(validated_axes):
			raise ValueError("axes contains invalid axes: {axes}".format(axes=axes))

		self.commands(["G91", "G28 %s" % " ".join(map(lambda x: "%s0" % x.upper(), validated_axes)), "G90"])

	def extrude(self, amount):
		if not isinstance(amount, (int, long, float)):
			raise ValueError("amount must be a valid number: {amount}".format(amount=amount))

		printer_profile = self._printerProfileManager.get_current_or_default()
		extrusion_speed = printer_profile["axes"]["e"]["speed"]
		self.commands(["G91", "G1 E%s F%d" % (amount, extrusion_speed), "G90"])
		
	def extrudeSpeed(self, amount, speed):
		if not isinstance(amount, (int, long, float)):
			raise ValueError("amount must be a valid number: {amount}".format(amount=amount))
		
		speed1 = float(speed)
		speed1 = int(speed1) * 60
		extrusion_speed = speed1
		print("lkj extrudeSpeed speed:%s" % str(speed1))		
		self.commands(["G91", "G1 E%s F%d" % (amount, extrusion_speed), "G90"])

	def change_tool(self, tool):
		if not PrinterInterface.valid_tool_regex.match(tool):
			raise ValueError("tool must match \"tool[0-9]+\": {tool}".format(tool=tool))

		tool_num = int(tool[len("tool"):])
		self.commands("T%d" % tool_num)

	def set_temperature(self, heater, value):
		if not PrinterInterface.valid_heater_regex.match(heater):
			raise ValueError("heater must match \"tool[0-9]+\" or \"bed\": {heater}".format(type=heater))

		if not isinstance(value, (int, long, float)) or value < 0:
			raise ValueError("value must be a valid number >= 0: {value}".format(value=value))

		if heater.startswith("tool"):
			printer_profile = self._printerProfileManager.get_current_or_default()
			extruder_count = printer_profile["extruder"]["count"]
			if extruder_count > 1:
				toolNum = int(heater[len("tool"):])
				#lkj self.commands("M104 T%d S%f" % (toolNum, value))
				self._comm._doSendEmergency("M104 T%d S%f" % (toolNum, value))
			else:
				#lkj self.commands("M104 S%f" % value)
				self._comm._doSendEmergency("M104 S%f" % value)

		elif heater == "bed":
			#self.commands("M140 S%f" % value)
			self._comm._doSendEmergency("M140 S%f" % value)

	def set_temperature_offset(self, offsets=None):
		if offsets is None:
			offsets = dict()

		if not isinstance(offsets, dict):
			raise ValueError("offsets must be a dict")

		validated_keys = filter(lambda x: PrinterInterface.valid_heater_regex.match(x), offsets.keys())
		validated_values = filter(lambda x: isinstance(x, (int, long, float)), offsets.values())

		if len(validated_keys) != len(offsets):
			raise ValueError("offsets contains invalid keys: {offsets}".format(offsets=offsets))
		if len(validated_values) != len(offsets):
			raise ValueError("offsets contains invalid values: {offsets}".format(offsets=offsets))

		if self._comm is None:
			return

		self._comm.setTemperatureOffset(offsets)
		self._stateMonitor.set_temp_offsets(offsets)

	def _convert_rate_value(self, factor, min=0, max=200):
		if not isinstance(factor, (int, float, long)):
			raise ValueError("factor is not a number")

		if isinstance(factor, float):
			factor = int(factor * 100.0)

		if factor < min or factor > max:
			raise ValueError("factor must be a value between %f and %f" % (min, max))

		return factor

	def feed_rate(self, factor):
		factor = self._convert_rate_value(factor, min=50, max=200)
		self.commands("M220 S%d" % factor)

	def flow_rate(self, factor):
		factor = self._convert_rate_value(factor, min=75, max=125)
		self.commands("M221 S%d" % factor)

	#lkj def select_file(self, path, sd, printAfterSelect=False):
	def select_file(self, path, origin, printAfterSelect=False):
		if self._comm is None or (self._comm.isBusy() or self._comm.isStreaming()):
			self._logger.info("Cannot load file: printer not connected or currently busy")
			return
		print("lkj standard.py select file")		
		sd = origin == FileDestinations.SDCARD #lkj
		self._printAfterSelect = printAfterSelect
		#lkj self._comm.selectFile("/" + path if sd else path, sd)
		self._comm.selectFile("/" + path if sd else path, origin)
		self._setProgressData(0, None, None, None)
		self._setCurrentZ(None)
		print("lkj standard.py select file end")

	def unselect_file(self):
		if self._comm is not None and (self._comm.isBusy() or self._comm.isStreaming()):
			return

		self._comm.unselectFile()
		self._setProgressData(0, None, None, None)
		self._setCurrentZ(None)

	def start_print(self):
		"""
		 Starts the currently loaded print job.
		 Only starts if the printer is connected and operational, not currently printing and a printjob is loaded
		"""
		if self._comm is None or not self._comm.isOperational() or self._comm.isPrinting():
			return
		if self._selectedFile is None:
			return

		rolling_window = None
		threshold = None
		countdown = None
		if self._selectedFile["sd"]:
			# we are interesting in a rolling window of roughly the last 15s, so the number of entries has to be derived
			# by that divided by the sd status polling interval
			rolling_window = 15 / settings().get(["serial", "timeout", "sdStatus"])

			# we are happy if the average of the estimates stays within 60s of the prior one
			threshold = 60

			# we are happy when one rolling window has been stable
			countdown = rolling_window
		self._timeEstimationData = TimeEstimationHelper(rolling_window=rolling_window, threshold=threshold, countdown=countdown)

		self._lastProgressReport = None
		self._setProgressData(0, None, None, None)
		self._setCurrentZ(None)
		self._comm.startPrint()

	def toggle_pause_print(self):
		"""
		 Pause the current printjob.
		"""
		if self._comm is None:
			return

		self._comm.setPause(not self._comm.isPaused())

	def cancel_print(self):
		"""
		 Cancel the current printjob.
		"""
		if self._comm is None:
			return

		self._comm.cancelPrint()

		# reset progress, height, print time
		self._setCurrentZ(None)
		self._setProgressData(None, None, None, None)

		# mark print as failure
		if self._selectedFile is not None:
			#lkj self._fileManager.log_print(FileDestinations.SDCARD if self._selectedFile["sd"] else FileDestinations.LOCAL, self._selectedFile["filename"], time.time(), self._comm.getPrintTime(), False, self._printerProfileManager.get_current_or_default()["id"])
			self._fileManager.log_print(self._selectedFile["origin"], self._selectedFile["filename"], time.time(), self._comm.getPrintTime(), False, self._printerProfileManager.get_current_or_default()["id"])
			
			payload = {
				"file": self._selectedFile["filename"],
				"origin": self._selectedFile["origin"]
			        #lkj "origin": FileDestinations.LOCAL
			}
			if self._selectedFile["sd"]:
				payload["origin"] = FileDestinations.SDCARD
			eventManager().fire(Events.PRINT_FAILED, payload)

	def get_state_string(self):
		"""
		 Returns a human readable string corresponding to the current communication state.
		"""
		if self._comm is None:
			return "Offline"
		else:
			return self._comm.getStateString()

	def get_current_data(self):
		return self._stateMonitor.get_current_data()

	def get_current_job(self):
		currentData = self._stateMonitor.get_current_data()
		return currentData["job"]

	def get_current_temperatures(self):
		if self._comm is not None:
			offsets = self._comm.getOffsets()
		else:
			offsets = dict()

		result = {}
		if self._temp is not None:
			for tool in self._temp.keys():
				result["tool%d" % tool] = {
					"actual": self._temp[tool][0],
					"target": self._temp[tool][1],
					"offset": offsets[tool] if tool in offsets and offsets[tool] is not None else 0
				}
		if self._bedTemp is not None:
			result["bed"] = {
				"actual": self._bedTemp[0],
				"target": self._bedTemp[1],
				"offset": offsets["bed"] if "bed" in offsets and offsets["bed"] is not None else 0
			}

		return result

	def get_temperature_history(self):
		return self._temps

	def get_current_connection(self):
		if self._comm is None:
			return "Closed", None, None, None

		port, baudrate = self._comm.getConnection()
		printer_profile = self._printerProfileManager.get_current_or_default()
		return self._comm.getStateString(), port, baudrate, printer_profile

	def is_closed_or_error(self):
		return self._comm is None or self._comm.isClosedOrError()

	def is_operational(self):
		return self._comm is not None and self._comm.isOperational()

	def is_printing(self):
		return self._comm is not None and self._comm.isPrinting()

	def is_paused(self):
		return self._comm is not None and self._comm.isPaused()

	def is_error(self):
		return self._comm is not None and self._comm.isError()

	def is_ready(self):
		return self.is_operational() and not self._comm.isStreaming()

	def is_sd_ready(self):
		if not settings().getBoolean(["feature", "sdSupport"]) or self._comm is None:
			return False
		else:
			return self._comm.isSdReady()

	#~~ sd file handling

	def get_sd_files(self):
		if self._comm is None or not self._comm.isSdReady():
			return []
		return map(lambda x: (x[0][1:], x[1]), self._comm.getSdFiles())

	def add_sd_file(self, filename, absolutePath, streamingFinishedCallback):
		if not self._comm or self._comm.isBusy() or not self._comm.isSdReady():
			self._logger.error("No connection to printer or printer is busy")
			return

		self._streamingFinishedCallback = streamingFinishedCallback

		self.refresh_sd_files(blocking=True)
		existingSdFiles = map(lambda x: x[0], self._comm.getSdFiles())

		remoteName = util.get_dos_filename(filename, existing_filenames=existingSdFiles, extension="gco")
		self._timeEstimationData = TimeEstimationHelper()
		self._comm.startFileTransfer(absolutePath, filename, "/" + remoteName)

		return remoteName

	def delete_sd_file(self, filename):
		if not self._comm or not self._comm.isSdReady():
			return
		self._comm.deleteSdFile("/" + filename)

	def init_sd_card(self):
		if not self._comm or self._comm.isSdReady():
			return
		self._comm.initSdCard()

	def release_sd_card(self):
		if not self._comm or not self._comm.isSdReady():
			return
		self._comm.releaseSdCard()

	def refresh_sd_files(self, blocking=False):
		"""
		Refreshs the list of file stored on the SD card attached to printer (if available and printer communication
		available). Optional blocking parameter allows making the method block (max 10s) until the file list has been
		received (and can be accessed via self._comm.getSdFiles()). Defaults to an asynchronous operation.
		"""
		if not self._comm or not self._comm.isSdReady():
			return
		self._sdFilelistAvailable.clear()
		self._comm.refreshSdFiles()
		if blocking:
			self._sdFilelistAvailable.wait(10000)

	#~~ state monitoring

	def _setCurrentZ(self, currentZ):
		self._currentZ = currentZ
		self._stateMonitor.set_current_z(self._currentZ)

	def _setState(self, state):
		self._state = state
		self._stateMonitor.set_state({"text": self.get_state_string(), "flags": self._getStateFlags()})

	def _addLog(self, log):
		self._log.append(log)
		self._stateMonitor.add_log(log)

	def _addMessage(self, message):
		self._messages.append(message)
		self._stateMonitor.add_message(message)

	def _estimateTotalPrintTime(self, progress, printTime):
		if not progress or not printTime or not self._timeEstimationData:
			return None

		else:
			newEstimate = printTime / progress
			self._timeEstimationData.update(newEstimate)

			result = None
			if self._timeEstimationData.is_stable():
				result = self._timeEstimationData.average_total_rolling

			return result

	def _setProgressData(self, progress, filepos, printTime, cleanedPrintTime):
		estimatedTotalPrintTime = self._estimateTotalPrintTime(progress, cleanedPrintTime)
		totalPrintTime = estimatedTotalPrintTime

		if self._selectedFile and "estimatedPrintTime" in self._selectedFile and self._selectedFile["estimatedPrintTime"]:
			statisticalTotalPrintTime = self._selectedFile["estimatedPrintTime"]
			if progress and cleanedPrintTime:
				if estimatedTotalPrintTime is None:
					totalPrintTime = statisticalTotalPrintTime
				else:
					if progress < 0.5:
						sub_progress = progress * 2
					else:
						sub_progress = 1.0
					totalPrintTime = (1 - sub_progress) * statisticalTotalPrintTime + sub_progress * estimatedTotalPrintTime

		self._progress = progress
		self._printTime = printTime
		self._printTimeLeft = totalPrintTime - cleanedPrintTime if (totalPrintTime is not None and cleanedPrintTime is not None) else None

		self._stateMonitor.set_progress({
			"completion": self._progress * 100 if self._progress is not None else None,
			"filepos": filepos,
			"printTime": int(self._printTime) if self._printTime is not None else None,
			"printTimeLeft": int(self._printTimeLeft) if self._printTimeLeft is not None else None
		})

		if progress:
			progress_int = int(progress * 100)
			if self._lastProgressReport != progress_int:
				self._lastProgressReport = progress_int
				self._reportPrintProgressToPlugins(progress_int)


	def _addTemperatureData(self, temp, bedTemp):
		currentTimeUtc = int(time.time())

		data = {
			"time": currentTimeUtc
		}
		for tool in temp.keys():
			data["tool%d" % tool] = {
				"actual": temp[tool][0],
				"target": temp[tool][1]
			}
		if bedTemp is not None and isinstance(bedTemp, tuple):
			data["bed"] = {
				"actual": bedTemp[0],
				"target": bedTemp[1]
			}

		self._temps.append(data)

		self._temp = temp
		self._bedTemp = bedTemp

		self._stateMonitor.add_temperature(data)

	#lkj def _setJobData(self, filename, filesize, sd):
	def _setJobData(self, filename, filesize, origin):		
		if filename is not None:
			print("_setJobData %s" % str(origin))
			sd = origin == FileDestinations.SDCARD
			if sd:
				path_in_storage = filename
				if path_in_storage.startswith("/"):
					path_in_storage = path_in_storage[1:]
				path_on_disk = None
			else:
				#lkj path_in_storage = self._fileManager.path_in_storage(FileDestinations.LOCAL, filename)
				#lkj path_on_disk = self._fileManager.path_on_disk(FileDestinations.LOCAL, filename)
				path_in_storage = self._fileManager.path_in_storage(origin, filename)
				path_on_disk = self._fileManager.path_on_disk(origin, filename)				
			self._selectedFile = {
				"filename": path_in_storage,
				"filesize": filesize,
				"sd": sd,
			        "origin": origin,   #lkj add
				"estimatedPrintTime": None
			}
		else:
			self._selectedFile = None
			self._stateMonitor.set_job_data({
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
		if path_on_disk:
			# Use a string for mtime because it could be float and the
			# javascript needs to exact match
			if not sd:
				date = int(os.stat(path_on_disk).st_mtime)

			try:
				#lkj fileData = self._fileManager.get_metadata(FileDestinations.SDCARD if sd else FileDestinations.LOCAL, path_on_disk)
				fileData = self._fileManager.get_metadata(self._selectedFile["origin"], path_on_disk)
				
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

		self._stateMonitor.set_job_data({
			"file": {
				"name": path_in_storage,
				"origin": origin,
				#lkj "origin": FileDestinations.SDCARD if sd else FileDestinations.LOCAL,		                
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
			data = self._stateMonitor.get_current_data()
			data.update({
				"temps": list(self._temps),
				"logs": list(self._log),
				"messages": list(self._messages)
			})
			callback.on_printer_send_initial_data(data)
		except Exception, err:
			import sys
			sys.stderr.write("ERROR: %s\n" % str(err))
			pass

	def _getStateFlags(self):
		return {
			"operational": self.is_operational(),
			"printing": self.is_printing(),
			"closedOrError": self.is_closed_or_error(),
			"error": self.is_error(),
			"paused": self.is_paused(),
			"ready": self.is_ready(),
			"sdReady": self.is_sd_ready()
		}

	#~~ comm.MachineComPrintCallback implementation

	def on_comm_log(self, message):
		print("lkj on_comm_log %s" % str(message))
		"""
		 Callback method for the comm object, called upon log output.
		"""
		self._addLog(message)

	def on_comm_temperature_update(self, temp, bedTemp):
		#print("lkj on_comm_temperature_update")
		self._last_read_temp_time = time.time()
		#lkj self._addTemperatureData(temp, bedTemp)		
		
		delta = time.time() - self._temp_update_last			
		if self.is_printing() and self._temp_update_interval - delta <= 0:
			print("lkj on_comm_temperature_update 6")
			self._addTemperatureData(temp, bedTemp)
			self._temp_update_last = time.time()	
		elif not self.is_printing():
			self._addTemperatureData(temp, bedTemp)
			self._temp_update_last = time.time()			
			

	def on_comm_state_change(self, state):
		print("lkj on_comm_state_change")
		"""
		 Callback method for the comm object, called if the connection state changes.
		"""
		oldState = self._state
		#lkj 
		#self._last_read_temp_time = time.time()
		
		# forward relevant state changes to gcode manager
		if oldState == comm.MachineCom.STATE_PRINTING:
			if self._selectedFile is not None:
				if state == comm.MachineCom.STATE_CLOSED or state == comm.MachineCom.STATE_ERROR or state == comm.MachineCom.STATE_CLOSED_WITH_ERROR:
					#lkj self._fileManager.log_print(FileDestinations.SDCARD if self._selectedFile["sd"] else FileDestinations.LOCAL, self._selectedFile["filename"], time.time(), self._comm.getPrintTime(), False, self._printerProfileManager.get_current_or_default()["id"])
					self._fileManager.log_print(self._selectedFile["origin"], self._selectedFile["filename"], time.time(), self._comm.getPrintTime(), False, self._printerProfileManager.get_current_or_default()["id"])
			self._analysisQueue.resume() # printing done, put those cpu cycles to good use
		elif state == comm.MachineCom.STATE_PRINTING:
			self._analysisQueue.pause() # do not analyse files while printing
		elif state == comm.MachineCom.STATE_CLOSED or state == comm.MachineCom.STATE_CLOSED_WITH_ERROR:
			if self._comm is not None:
				self._comm = None

			self._setProgressData(0, None, None, None)
			self._setCurrentZ(None)
			self._setJobData(None, None, None)

		self._setState(state)

	def on_comm_message(self, message):
		print("lkj on_comm_message %s " % message)
		"""
		 Callback method for the comm object, called upon message exchanges via serial.
		 Stores the message in the message buffer, truncates buffer to the last 300 lines.
		"""
		self._addMessage(message)
		
	def on_comm_progress(self):
		#print("lkj on_comm_progress")
		"""
		 Callback method for the comm object, called upon any change in progress of the printjob.
		 Triggers storage of new values for printTime, printTimeLeft and the current progress.
		"""
		#lkj start
		progress = self._comm.getPrintProgress()
		if progress > 0.98:
			print("lkj on_comm_progress 2")
			self._setProgressData(self._comm.getPrintProgress(), self._comm.getPrintFilepos(), self._comm.getPrintTime(), self._comm.getCleanedPrintTime())	
		else:				
			delta = time.time() - self._progress_update_last			
			if self._progress_update_interval <= delta :
				print("lkj on_comm_progress 6")
				self._setProgressData(self._comm.getPrintProgress(), self._comm.getPrintFilepos(), self._comm.getPrintTime(), self._comm.getCleanedPrintTime())
				self._progress_update_last = time.time()			 
		#lkj end 
		#self._setProgressData(self._comm.getPrintProgress(), self._comm.getPrintFilepos(), self._comm.getPrintTime(), self._comm.getCleanedPrintTime())

	def on_comm_z_change(self, newZ):
		print("lkj on_comm_z_change")
		"""
		 Callback method for the comm object, called upon change of the z-layer.
		"""
		oldZ = self._currentZ
		if newZ != oldZ:
			# we have to react to all z-changes, even those that might "go backward" due to a slicer's retraction or
			# anti-backlash-routines. Event subscribes should individually take care to filter out "wrong" z-changes
			eventManager().fire(Events.Z_CHANGE, {"new": newZ, "old": oldZ})

		self._setCurrentZ(newZ)

	def on_comm_sd_state_change(self, sdReady):
		print("lkj on_comm_sd_state_change")
		self._stateMonitor.set_state({"text": self.get_state_string(), "flags": self._getStateFlags()})

	def on_comm_sd_files(self, files):
		print("lkj on_comm_sd_files")
		eventManager().fire(Events.UPDATED_FILES, {"type": "gcode"})
		self._sdFilelistAvailable.set()

	#lkj def on_comm_file_selected(self, filename, filesize, sd):
	def on_comm_file_selected(self, filename, filesize, origin):		
		print("lkj on_comm_file_selected %s" % str(origin))
		self._setJobData(filename, filesize, origin)
		self._stateMonitor.set_state({"text": self.get_state_string(), "flags": self._getStateFlags()})

		if self._printAfterSelect:
			self.start_print()

	def on_comm_print_job_done(self):
		print("lkj on_comm_print_job_done")
		#lkj self._fileManager.log_print(FileDestinations.SDCARD if self._selectedFile["sd"] else FileDestinations.LOCAL, self._selectedFile["filename"], time.time(), self._comm.getPrintTime(), True, self._printerProfileManager.get_current_or_default()["id"])
		self._fileManager.log_print(self._selectedFile["origin"], self._selectedFile["filename"], time.time(), self._comm.getPrintTime(), True, self._printerProfileManager.get_current_or_default()["id"])
		self._setProgressData(1.0, self._selectedFile["filesize"], self._comm.getPrintTime(), 0)
		self._stateMonitor.set_state({"text": self.get_state_string(), "flags": self._getStateFlags()})

	def on_comm_file_transfer_started(self, filename, filesize):
		print("lkj on_comm_file_transfer_started")
		self._sdStreaming = True

		#lkj self._setJobData(filename, filesize, True)
		self._setJobData(filename, filesize, FileDestinations.SDCARD)		
		self._setProgressData(0.0, 0, 0, None)
		self._stateMonitor.set_state({"text": self.get_state_string(), "flags": self._getStateFlags()})

	def on_comm_file_transfer_done(self, filename):
		print("lkj on_comm_file_transfer_done")
		self._sdStreaming = False

		if self._streamingFinishedCallback is not None:
			# in case of SD files, both filename and absolutePath are the same, so we set the (remote) filename for
			# both parameters
			self._streamingFinishedCallback(filename, filename, FileDestinations.SDCARD)

		self._setCurrentZ(None)
		self._setJobData(None, None, None)
		self._setProgressData(None, None, None, None)
		self._stateMonitor.set_state({"text": self.get_state_string(), "flags": self._getStateFlags()})

	def on_comm_force_disconnect(self):
		print("lkj on_comm_force_disconnect")
		self.disconnect()


class StateMonitor(object):
	def __init__(self, interval=0.5, on_update=None, on_add_temperature=None, on_add_log=None, on_add_message=None):
		self._interval = interval
		self._update_callback = on_update
		self._on_add_temperature = on_add_temperature
		self._on_add_log = on_add_log
		self._on_add_message = on_add_message

		self._state = None
		self._job_data = None
		self._gcode_data = None
		self._sd_upload_data = None
		self._current_z = None
		self._progress = None

		self._offsets = {}

		self._change_event = threading.Event()
		self._state_lock = threading.Lock()

		self._last_update = time.time()
		self._worker = threading.Thread(target=self._work)
		self._worker.daemon = True
		self._worker.start()

	def reset(self, state=None, job_data=None, progress=None, current_z=None):
		self.set_state(state)
		self.set_job_data(job_data)
		self.set_progress(progress)
		self.set_current_z(current_z)

	def add_temperature(self, temperature):
		self._on_add_temperature(temperature)
		self._change_event.set()

	def add_log(self, log):
		self._on_add_log(log)
		self._change_event.set()

	def add_message(self, message):
		self._on_add_message(message)
		self._change_event.set()

	def set_current_z(self, current_z):
		self._current_z = current_z
		self._change_event.set()

	def set_state(self, state):
		with self._state_lock:
			self._state = state
			self._change_event.set()

	def set_job_data(self, job_data):
		self._job_data = job_data
		self._change_event.set()

	def set_progress(self, progress):
		self._progress = progress
		self._change_event.set()

	def set_temp_offsets(self, offsets):
		self._offsets = offsets
		self._change_event.set()

	def _work(self):
		while True:
			self._change_event.wait()

			with self._state_lock:
				now = time.time()
				delta = now - self._last_update
				additional_wait_time = self._interval - delta
				if additional_wait_time > 0:
					time.sleep(additional_wait_time)

				data = self.get_current_data()
				self._update_callback(data)
				self._last_update = time.time()
				self._change_event.clear()

	def get_current_data(self):
		return {
			"state": self._state,
			"job": self._job_data,
			"currentZ": self._current_z,
			"progress": self._progress,
			"offsets": self._offsets
		}


class TemperatureHistory(InvariantContainer):
	def __init__(self, cutoff=30 * 60):

		def temperature_invariant(data):
			data.sort(key=lambda x: x["time"])
			now = int(time.time())
			return [item for item in data if item["time"] >= now - cutoff]

		InvariantContainer.__init__(self, guarantee_invariant=temperature_invariant)
