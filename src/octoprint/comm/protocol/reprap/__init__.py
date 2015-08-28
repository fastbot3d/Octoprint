# coding=utf-8
import Queue
from collections import deque
from octoprint.events import eventManager, Events
from octoprint.util import filterNonAscii

__author__ = "Gina Häußge <osd@foosel.net>"
__license__ = "GNU Affero General Public License http://www.gnu.org/licenses/agpl.html"
__copyright__ = "Copyright (C) 2014 Gina Häußge - Released under terms of the AGPLv3 License"

import re
import threading
import time
from octoprint.comm.protocol import State, Protocol, PrintingSdFileInformation
from octoprint.comm.protocol.reprap.util import GcodeCommand, CommandQueue, CommandQueueEntry, PrintingGcodeFileInformation, \
	StreamingGcodeFileInformation, TypeAlreadyInQueue, SpecialCommandQueueEntry
from octoprint.comm.transport import SendTimeout
from octoprint.filemanager import valid_file_type
from octoprint.filemanager.destinations import FileDestinations
from octoprint.settings import settings
from octoprint.util import CountedEvent
import octoprint.plugin


class RepRapProtocol(Protocol):

	__protocolinfo__ = ("reprap", "RepRap", False)

	## Firmware messages
	MESSAGE_OK = staticmethod(lambda line: line.lower().startswith("ok"))
	MESSAGE_START = staticmethod(lambda line: line.startswith("start"))
	MESSAGE_WAIT = staticmethod(lambda line: line.startswith("wait"))
	MESSAGE_RESEND = staticmethod(lambda line: line.lower().startswith("resend") or line.lower().startswith("rs"))

	MESSAGE_TEMPERATURE = staticmethod(lambda line: "T:" in line or line.startswith("T:") or "T0:" in line or line.startswith("T0:"))

	MESSAGE_SD_INIT_OK = staticmethod(lambda line: line.lower().startswith("sd card ok"))
	#MESSAGE_SD_INIT_OK = staticmethod(lambda line: line.lower() == "sd card ok")
	MESSAGE_SD_INIT_FAIL = staticmethod(lambda line: "sd init fail" in line.lower() or "volume.init failed" in line.lower() or "openroot failed" in line.lower())
	MESSAGE_SD_FILE_OPENED = staticmethod(lambda line: line.lower().startswith("file opened"))
	MESSAGE_SD_FILE_SELECTED = staticmethod(lambda line: line.lower().startswith("file selected"))
	MESSAGE_SD_BEGIN_FILE_LIST = staticmethod(lambda line: line.lower().startswith("begin file list"))
	MESSAGE_SD_END_FILE_LIST = staticmethod(lambda line: line.lower().startswith("end file list"))
	MESSAGE_SD_PRINTING_BYTE = staticmethod(lambda line: "sd printing byte" in line.lower())
	MESSAGE_SD_NOT_PRINTING = staticmethod(lambda line: "not sd printing" in line.lower())
	MESSAGE_SD_DONE_PRINTING = staticmethod(lambda line: "done printing file" in line.lower())
	MESSAGE_SD_BEGIN_WRITING = staticmethod(lambda line: "writing to file" in line.lower())
	MESSAGE_SD_END_WRITING = staticmethod(lambda line: "done saving file" in line.lower())

	MESSAGE_ERROR = staticmethod(lambda line: line.startswith("Error:") or line.startswith("!!"))
	MESSAGE_ERROR_MULTILINE = staticmethod(lambda line: RepRapProtocol.REGEX_ERROR_MULTILINE.match(line))
	MESSAGE_ERROR_COMMUNICATION = staticmethod(lambda line: 'checksum mismatch' in line.lower()
															or 'wrong checksum' in line.lower()
															or 'line number is not last line number' in line.lower()
															or 'expected line' in line.lower()
															or 'no line number with checksum' in line.lower()
															or 'no checksum with line number' in line.lower()
															or 'missing checksum' in line.lower())
	MESSAGE_ERROR_COMMUNICATION_LINENUMBER = staticmethod(lambda line: 'line number is not line number' in line.lower()
															or 'expected line' in line.lower())

	TRANSFORM_ERROR = staticmethod(lambda line: line[6:] if line.startswith("Error:") else line[2:])

	## Commands
	COMMAND_GET_TEMP = staticmethod(lambda: GcodeCommand("M105"))
	COMMAND_SET_EXTRUDER_TEMP = staticmethod(lambda s, t, w: GcodeCommand("M109", s=s, t=t) if w else GcodeCommand("M104", s=s, t=t))
	COMMAND_SET_LINE = staticmethod(lambda n: GcodeCommand("M110 N%d" % n))
	COMMAND_SET_BED_TEMP = staticmethod(lambda s, w: GcodeCommand("M190", s=s) if w else GcodeCommand("M140", s=s))
	COMMAND_SET_RELATIVE_POSITIONING = staticmethod(lambda: GcodeCommand("G91"))
	COMMAND_SET_ABSOLUTE_POSITIONING = staticmethod(lambda: GcodeCommand("G90"))
	COMMAND_SET_RELATIVE_EXTRUDER = staticmethod(lambda: GcodeCommand("M83"))
	COMMAND_SET_ABSOLUTE_EXTRUDER = staticmethod(lambda: GcodeCommand("M82"))
	COMMAND_MOVE_AXIS = staticmethod(lambda axis, amount, speed: GcodeCommand("G1", x=amount if axis=='x' else None, y=amount if axis=='y' else None, z=amount if axis=='z' else None, f=speed))
	COMMAND_MOVE = staticmethod(lambda x, y, z, speed: GcodeCommand("G1", x=x if x is not None else None, y=y if y is not None else None, z=z if z is not None else None, f=speed))
	COMMAND_EXTRUDE = staticmethod(lambda amount, speed: GcodeCommand("G1", e=amount, f=speed))
	COMMAND_HOME_AXIS = staticmethod(lambda x, y, z: GcodeCommand("G28", x=0 if x else None, y=0 if y else None, z=0 if z else None))
	COMMAND_SET_TOOL = staticmethod(lambda t: GcodeCommand("T%d" % t))
	COMMAND_SET_POSITION = staticmethod(lambda x, y, z, e: GcodeCommand("G92", x=x if x is not None else None, y=y if y is not None else None, z=z if z is not None else None, e=e if e is not None else None))
	COMMAND_GET_POSITION = staticmethod(lambda: GcodeCommand("M114"))
	COMMAND_SD_REFRESH = staticmethod(lambda: GcodeCommand("M20"))
	COMMAND_SD_INIT = staticmethod(lambda: GcodeCommand("M21"))
	COMMAND_SD_RELEASE = staticmethod(lambda: GcodeCommand("M22"))
	COMMAND_SD_SELECT_FILE = staticmethod(lambda name: GcodeCommand("M23", param=name))
	COMMAND_SD_START = staticmethod(lambda: GcodeCommand("M24"))
	COMMAND_SD_PAUSE = staticmethod(lambda: GcodeCommand("M25"))
	COMMAND_SD_SET_POS = staticmethod(lambda pos: GcodeCommand("M26", s=pos))
	COMMAND_SD_STATUS = staticmethod(lambda: GcodeCommand("M27"))
	COMMAND_SD_BEGIN_WRITE = staticmethod(lambda name: GcodeCommand("M28", param=name))
	COMMAND_SD_END_WRITE = staticmethod(lambda name: GcodeCommand("M29", param=name))
	COMMAND_SD_DELETE = staticmethod(lambda name: GcodeCommand("M30", param=name))

	COMMAND_PRINT_PAUSE = staticmethod(lambda: GcodeCommand("M600"))
	COMMAND_PRINT_RESUME = staticmethod(lambda: GcodeCommand("M601"))

	## Command types
	COMMAND_TYPE_TEMPERATURE = "temperature"
	COMMAND_TYPE_SD_PROGRESS = "sd_progress"

	# Regex matching temperature entries in line. Groups will be as follows:
	# - 1: whole tool designator incl. optional toolNumber ("T", "Tn", "B")
	# - 2: toolNumber, if given ("", "n", "")
	# - 3: actual temperature
	# - 4: whole target substring, if given (e.g. " / 22.0")
	# - 5: target temperature
	REGEX_TEMPERATURE = re.compile("(B|T(\d*)):\s*([-+]?\d*\.?\d+)(\s*\/?\s*([-+]?\d*\.?\d+))?")

	# Regex matching "File opened" message. Groups will be as follows:
	# - 1: name of the file that got opened (e.g. "file.gco")
	# - 2: size of the file that got opened, in bytes, parseable to integer (e.g. "2392010")
	REGEX_FILE_OPENED = re.compile("File opened:\s*(.*?)\s+Size:\s*([0-9]*)")

	# Regex matching printing byte message. Groups will be as follows:
	# - 1: current file position
	# - 2: file size
	REGEX_SD_PRINTING_BYTE = re.compile("([0-9]*)/([0-9]*)")

	# Regex matching multi line errors
	#
	# Marlin reports MAXTEMP issues on extruders in the format
	#
	#   Error:{int}
	#   Extruder switched off. {MIN|MAX}TEMP triggered !
	#
	# This regex matches the line initiating those multiline errors. If it is encountered, the next line has
	# to be fetched from the transport layer in order to fully handle the error at hand.
	REGEX_ERROR_MULTILINE = re.compile("Error:[0-9]\n")

	# Regex matching M114 output: "X:<x>Y:<y>Z:<z>E:<e> ..."
	# - 1: current X
	# - 2: current Y
	# - 3: current Z
	# - 4: current E
	REGEX_POSITION = re.compile("X:([-+]?\d*\.?\d+)\s*Y:([-+]?\d*\.?\d+)\s*Z:([-+]?\d*\.?\d+)\s*E:([-+]?\d*\.?\d+)")

	BLOCKING_COMMANDS = (
		"M109", "M190",                                             # set and wait for temperature (hotend & bed)
		"G28",                                                      # home
		"G29", "G30", "G31", "G32"                                  # bed probing
	)

	def __init__(self, transport_factory, protocol_listener=None):
		Protocol.__init__(self, transport_factory, protocol_listener)

		self._lastTemperatureUpdate = time.time()
		self._lastSdProgressUpdate = time.time()

		self._startSeen = False
		self._receivingSdFileList = False

		self._send_queue = CommandQueue()
		#lkj
		self._send_queue_backup = CommandQueue()
		
		self._clear_for_send = CountedEvent(max=10)

		self._force_checksum = True
		self._wait_for_start = False
		self._sd_always_available = False
		self._rx_cache_size = 0

		self._blocking_command_active = False

		self._temperature_interval = 5.0
		self._sdstatus_interval = 5.0
		

		self._sent_lines = deque([])
		self._send_lock = threading.RLock()

		self._previous_resend = False
		self._last_comm_error = None
		self._last_resend_number = None
		self._current_resend_count = 0
		self._sent_before_resend = 0
		#lkj
		self._heatupOK = False
		
		self._send_queue_processing = True
		self._thread = threading.Thread(target=self._handle_send_queue, name="SendQueueHandler")
		self._thread.daemon = True
		self._thread.start()

		self._last_queried_position = None
		self._last_seen_f = None

		self._output = []

		self._fill_queue_semaphore = threading.BoundedSemaphore(10)
		self._fill_queue_state_signal = threading.Event()
		self._fill_queue_mutex = threading.Lock()
		self._fill_queue_processing = True
		self._fill_thread = threading.Thread(target=self._fill_send_queue, name="FillQueueHandler")
		self._fill_thread.daemon = True
		self._fill_thread.start()

		self._current_line = 1
		self._current_extruder = 0
		self._state = State.OFFLINE

		self._pluginManager = octoprint.plugin.plugin_manager()
		self._gcode_hooks = dict(
			queued=self._pluginManager.get_hooks("octoprint.comm.protocol.gcode.queued").values(),
			sending=self._pluginManager.get_hooks("octoprint.comm.protocol.gcode.sending").values(),
			sent=self._pluginManager.get_hooks("octoprint.comm.protocol.gcode.sent").values(),
			acknowledged=self._pluginManager.get_hooks("octoprint.comm.protocol.gcode.acknowledged").values()
		)

		self._preprocessors = dict()
		self._setup_preprocessors()

		self._reset()

	def _setup_preprocessors(self):
		self._preprocessors.clear()

		for attr in dir(self):
			if attr.startswith("_gcode") and (attr.endswith("_queued") or attr.endswith("_sending") or attr.endswith("_sent") or attr.endswith("_acknowledged")):
				split_attr = attr.split("_")
				if not len(split_attr) == 4:
					continue

				prefix, code, postfix = split_attr[1:]
				if not postfix in self._preprocessors:
					self._preprocessors[postfix] = dict()
				self._preprocessors[postfix][code] = getattr(self, attr)

	def _reset(self, from_start=False):
		with self._send_lock:
			self._lastTemperatureUpdate = time.time()
			self._lastSdProgressUpdate = time.time()

			self._blocking_command_active = False

			if self._wait_for_start:
				self._startSeen = from_start
			else:
				self._startSeen = True

			if not self._startSeen:
				self._clear_for_send.clear(completely=True)
			else:
				if self._clear_for_send.blocked():
					self._clear_for_send.set()

			self._receivingSdFileList = False

			self._heatupOK = False
			
			# clear the the send queue
			self._send_queue.clear()

			self._sent_lines.clear()
			self._current_line = 1
			self._current_extruder = 0

			self._previous_resend = False
			self._last_comm_error = None
			self._last_resend_number = None
			self._current_resend_count = 0
			self._sent_before_resend = 0

			self._output = []
			self._last_queried_position = None
			self._last_seen_f = None

	def connect(self, protocol_options, transport_options):
		self._wait_for_start = protocol_options["waitForStart"] if "waitForStart" in protocol_options else False
		self._force_checksum = protocol_options["checksum"] if "checksum" in protocol_options else True
		self._sd_always_available = protocol_options["sdAlwaysAvailable"] if "sdAlwaysAvailable" in protocol_options else False
		self._rx_cache_size = protocol_options["buffer"] if "buffer" in protocol_options else 0
		self._temperature_interval = protocol_options["timeout"]["temperature"] if "timeout" in protocol_options and "temperature" in protocol_options["timeout"] else 5.0
		self._sdstatus_interval = protocol_options["timeout"]["sdstatus"] if "timeout" in protocol_options and "sdstatus" in protocol_options["timeout"] else 5.0

		self._reset()

		# connect
		Protocol.connect(self, protocol_options, transport_options)

		# we'll send an M110 first to reset line numbers to 0
		self._send(self.__class__.COMMAND_SET_LINE(0), high_priority=True)

		# enqueue our first temperature query so it gets sent right on establishment of the connection
		self._send_temperature_query(with_type=True)

	def disconnect(self, on_error=False):
		self._clear_for_send.clear(completely=True)
		# disconnect
		Protocol.disconnect(self, on_error=on_error)

	def select_file(self, filename, origin):
		if origin == FileDestinations.SDCARD:
			if not self._sd_available:
				return
			self._send(self.__class__.COMMAND_SD_SELECT_FILE(filename), high_priority=True)
		else:
			self._selectFile(PrintingGcodeFileInformation(filename, self.get_temperature_offsets, origin))
			

	def start_print(self):
		wasPaused = self._state == State.PAUSED
		self._heatupOK = False
		Protocol.start_print(self)
		if isinstance(self._current_file, PrintingSdFileInformation):
			if wasPaused:
				self._send(self.__class__.COMMAND_SD_SET_POS(0))
				self._current_file.setFilepos(0)
			self._send(self.__class__.COMMAND_SD_START())

	def cancel_print(self):
		if isinstance(self._current_file, PrintingSdFileInformation):
			self._send(self.__class__.COMMAND_SD_PAUSE)
			self._send(self.__class__.COMMAND_SD_SET_POS(0))

		Protocol.cancel_print(self)
		self._heatupOK = False
		print("cancel_print 2")

	def _print_cancelled(self):
		with self._fill_queue_mutex:
			cleared = self._send_queue.clear(matcher=lambda entry: entry is not None and entry.command is not None and hasattr(entry.command, "progress") and entry.command.progress is not None and (not hasattr(entry, "prepared") or entry.prepared is None))
			self._logger.debug("Cleared %d job entries from the send queue: %r" % (len(cleared), cleared))

	def pause_print(self, only_pause=None, only_resume=None):
		wasPaused = self._state == State.PAUSED
	
		#lkj add
		if self._state == State.PAUSED and not only_pause:	
			print("lkj resume M601");
			self._send(self.__class__.COMMAND_PRINT_RESUME(), high_priority=CommandQueueEntry.PRIORITY_HIGH )	
		
			 	
			with self._send_lock:
				with self._send_queue.clearlock:						
					while self._send_queue_backup.qsize() != 0 :
						item, entry = self._send_queue_backup.peek()
						if item is not None :
							self._send_queue.put(item)
							self._send_queue_backup.remove(entry)
							print("lkj remove backup entry %s" % repr(item))
						if self._send_queue_backup.qsize() == 0:	
							break					
			''' 
			'''
			
		with self._fill_queue_mutex:
			Protocol.pause_print(self, only_pause=only_pause, only_resume=only_resume)
		isPaused = self._state == State.PAUSED

		if wasPaused == isPaused:
			# nothing changed, either we are still printing or we are still paused
			return
		
		
		if not wasPaused:
			'''
			while self._send_queue_processing:
				if self._send_queue.qsize() == 0:	
					break
				else:
					print("lkj wait until queue is null ");
					time.sleep(0.1)
			
			'''
			with self._send_lock:
				with self._send_queue.clearlock:
					self._send_queue_backup.clear()
					while self._send_queue.qsize() != 0 :
						item, entry = self._send_queue.peek()
						if item is not None :
							self._send_queue_backup.put(item)
							self._send_queue.remove(entry)
							print("lkj remove entry %s" % repr(item))
						if self._send_queue.qsize() == 0:	
							break		
			self._send(self.__class__.COMMAND_PRINT_PAUSE(), high_priority=CommandQueueEntry.PRIORITY_HIGH)		
		
		
		'''
		
		
		
		if not wasPaused:
			# printer was printing, now paused
			def positionCallback(command):
				print("### command: %s" % command.command)
				print("### output: %r" % command.output)
				if command.output is None:
					return

				for line in command.output:
					match = self.__class__.REGEX_POSITION.search(line)
					if match is None:
						continue

					try:
						x = float(match.group(1))
						y = float(match.group(2))
						z = float(match.group(3))
						e = float(match.group(4))
						self._last_queried_position = (x, y, z, e)
						print("### set last_queried_position: %r" % (self._last_queried_position,))
					except ValueError:
						self._last_queried_position = None
						print("### set last_queried_position: %r" % (self._last_queried_position,))
					else:
						self._send(self.__class__.COMMAND_SET_RELATIVE_EXTRUDER())      # relative extruder
						self._send(self.__class__.COMMAND_EXTRUDE(-4.5, 6000))          # retract
						self._send(self.__class__.COMMAND_SET_RELATIVE_POSITIONING())   # relative positioning
						self._send(self.__class__.COMMAND_MOVE_AXIS("z", 15, 7800))     # move z up a bit
						self._send(self.__class__.COMMAND_HOME_AXIS(True, True, False)) # home x/y
						self._send(self.__class__.COMMAND_SET_ABSOLUTE_POSITIONING())   # absolute positioning
						self._send(self.__class__.COMMAND_SET_ABSOLUTE_EXTRUDER())      # absolute extruder

			# fetch the current position, once we have that we can continue
			#lkj positionCommand = self.__class__.COMMAND_GET_POSITION()
			#lkj positionCommand.callback = positionCallback
			print("lkj pause M600");
			self._send(self.__class__.COMMAND_PRINT_PAUSE(), high_priority=CommandQueueEntry.PRIORITY_HIGH)
			
		else:
			print("lkj resume M601");
			self._send(self.__class__.COMMAND_PRINT_RESUME(), high_priority=CommandQueueEntry.PRIORITY_HIGH )	
				lkj
			# printer was paused, now resuming
			#print("### get last_queried_position: %r" % (self._last_queried_position,))
			#if self._last_queried_position is not None:
			#	x, y, z, e = self._last_queried_position
			#	f = self._last_seen_f if self._last_seen_f else 7800
			#	self._send(self.__class__.COMMAND_SET_RELATIVE_EXTRUDER())              # relative extruder
			#	self._send(self.__class__.COMMAND_EXTRUDE(4.5, 6000))                   # prime the nozzle
			#	self._send(self.__class__.COMMAND_EXTRUDE(-4.5, 6000))                  # prime the nozzle
			#	self._send(self.__class__.COMMAND_MOVE(x, y, z, f))                     # move back to former x, y, z
			#	self._send(self.__class__.COMMAND_EXTRUDE(4.5, 300))                    # extrude a bit of material
			#	self._send(self.__class__.COMMAND_SET_ABSOLUTE_EXTRUDER())              # absolute extruder
			#	self._send(self.__class__.COMMAND_SET_POSITION(None, None, None, e))    # define current as old e
			#	self._send(self.__class__.COMMAND_MOVE(None, None, None, f))            # set speed
			#
		'''
			
	def init_sd(self):
		Protocol.init_sd(self)
		self._send(self.__class__.COMMAND_SD_INIT())
		if self._sd_always_available:
			self._changeSdState(True)

	def release_sd(self):
		Protocol.release_sd(self)
		self._send(self.__class__.COMMAND_SD_RELEASE())
		if self._sd_always_available:
			self._changeSdState(False)

	def refresh_sd_files(self):
		if not self._sd_available:
			return

		Protocol.refresh_sd_files(self)
		self._send(self.__class__.COMMAND_SD_REFRESH())

	def add_sd_file(self, path, local, remote):
		Protocol.add_sd_file(self, path, local, remote)
		if not self.is_operational() or self.is_busy():
			return

		self.send_manually(self.__class__.COMMAND_SD_BEGIN_WRITE(remote))

		self._current_file = StreamingGcodeFileInformation(path, local, remote)

		self._current_file.start()

		eventManager().fire(Events.TRANSFER_STARTED, {"local": local, "remote": remote})

		self._startFileTransfer(remote, self._current_file.getFilesize())
		self._changeState(State.STREAMING)

	def remove_sd_file(self, filename):
		Protocol.remove_sd_file(self, filename)
		if not self.is_operational() or \
				(self.is_busy() and isinstance(self._current_file, PrintingSdFileInformation) and
						 self._current_file.getFilename() == filename):
			return

		self.send_manually(self.__class__.COMMAND_SD_DELETE(filename))
		self.refresh_sd_files()

	def set_temperature(self, type, value):
		if type.startswith("tool"):
			from octoprint.printer.profile import PrinterProfileManager
			printerProfileManager = PrinterProfileManager()
			printer_profile = printerProfileManager.get_current_or_default()
			
			toolnum1 = 0;
			if "count" in printer_profile["extruder"]:
				toolnum1 = printer_profile["extruder"]["count"]
			
			if settings().getInt(["printerParameters", "numExtruders"]) > 1 or \
			        toolnum1 > 1:
				try:
					tool_num = int(type[len("tool"):])
					self.send_manually(self.__class__.COMMAND_SET_EXTRUDER_TEMP(value, tool_num, False))
				except ValueError:
					pass
			else:
				# set temperature without tool number
				self.send_manually(self.__class__.COMMAND_SET_EXTRUDER_TEMP(value, None, False))
		elif type == "bed":
			self.send_manually(self.__class__.COMMAND_SET_BED_TEMP(value, False))

	def jog(self, axis, amount, speed):
		commands = (
			self.__class__.COMMAND_SET_RELATIVE_POSITIONING(),
			self.__class__.COMMAND_MOVE_AXIS(axis, amount, speed),
			self.__class__.COMMAND_SET_ABSOLUTE_POSITIONING()
		)
		self.send_manually(commands)
		
	def feedSpeed(self, speed):
		speed_cmd = GcodeCommand("M220 S" + speed)
		self.send_manually(speed_cmd,high_priority=True)	
		
	def fanControl(self, fanId, onOff):
		on = str(onOff * 255)
		if fanId == 1 or fanId == 2 :
			cmd = "M106 S" + on
		if fanId == 3:
			if on == "255":
				cmd = "M176 S255"
			else :
				cmd = "M177"				
		if fanId == 4:
			cmd = "M150 R" + on
		if fanId == 5:
			cmd = "M150 G" + on
		if fanId == 6:
			cmd = "M150 B" + on
		self.send_manually(cmd)	

	def home(self, axes):

		commands = (
			self.__class__.COMMAND_SET_RELATIVE_POSITIONING(),
			self.__class__.COMMAND_HOME_AXIS('x' in axes, 'y' in axes, 'z' in axes),
			self.__class__.COMMAND_SET_ABSOLUTE_POSITIONING()
		)
		self.send_manually(commands)

	def extrude(self, amount, speed):
		commands = (
			self.__class__.COMMAND_SET_RELATIVE_POSITIONING(),
			self.__class__.COMMAND_EXTRUDE(amount, speed),
			self.__class__.COMMAND_SET_ABSOLUTE_POSITIONING()
		)
		self.send_manually(commands)

	def change_tool(self, tool):
		try:
			tool_num = int(tool[len("tool"):])
			self.send_manually(self.__class__.COMMAND_SET_TOOL(tool_num))
		except ValueError:
			pass

	def send_manually(self, command, high_priority=False):
		if self.is_streaming():
			return
		if isinstance(command, (tuple, list)):
			for c in command:
				self._send(c, high_priority=high_priority)
		else:
			self._send(command, high_priority=high_priority)

	def _fileTransferFinished(self, current_file):
		if isinstance(current_file, StreamingGcodeFileInformation):
			self.send_manually(self.__class__.COMMAND_SD_END_WRITE(current_file.getRemoteFilename()))
			eventManager().fire(Events.TRANSFER_DONE, {
				"local": current_file.getLocalFilename(),
				"remote": current_file.getRemoteFilename(),
				"time": self.get_print_time()
			})
		else:
			self._logger.warn("Finished file transfer to printer's SD card, but could not determine remote filename, assuming 'unknown.gco' for end-write-command")
			self.send_manually(self.__class__.COMMAND_SD_END_WRITE("unknown.gco"))
		self.refresh_sd_files()

	##~~ callback methods

	def onMessageReceived(self, source, message):
		if self._transport != source:
			return

		message = self._handle_errors(message.strip())
		if message == "" :
			return
		
		# temperature updates_handle_errors
		if self.__class__.MESSAGE_TEMPERATURE(message):
			self._process_temperatures(message)
			if not self.__class__.MESSAGE_OK(message) and not self.is_heating_up():
				self._heatupDetected()
				#self._heatupOK = False
				#print("lkj debug: 1")
				#self._logger.info("lkj debug: 1")
			elif self.__class__.MESSAGE_OK(message) and self.is_heating_up():   #lkj
				self._heatupDone()
				self._heatupOK = True
				self._stateChanged(State.PRINTING)
				#print("lkj debug: 2")
				#self._logger.info("lkj debug: 2")
				#return
			
			
			if self.__class__.MESSAGE_OK(message):
				#lkj self.extrude(64, 600)
				self._heatupOK = True
				#print("lkj debug: 3")
				#self._logger.info("lkj debug: 3")
				return				
			'''
			else:
				if self._heatupOK is True:
					stable_temp = True
					temperatures = self.get_current_temperatures()
									
					for temp_key in temperatures.keys():						
						(cur, target) = temperatures[temp_key];
						if cur is None or target is None:
							continue
						diff = cur - target
						
						self._logger.info("temperature diff is %s, self._heatupOK:%s" % (str(diff), str(self._heatupOK)))
						
						print("temperatur diff is %s" % str(diff))
						if diff > 30 or diff < -30 :
							stable_temp = False
							break
								
					if  stable_temp is True :
						self._heatupOK = True
					else : 	
						self._heatupOK = False
				else:
					self._heatupOK = False
					self._logger.info("lkj debug: 4")
					print("lkj debug: 4")
				
				self._logger.info("self._heatupOK:%s" % (str(self._heatupOK)))
				return
			'''
			return
		if message:
			self._output.append(message)
			#print("--- output: %r" % self._output)

		##~~ Control message processing: ok, resend, start, wait

		if self.__class__.MESSAGE_OK(message):
			if self._state == State.CONNECTED and self._startSeen:
				# if we are currently connected, have seen start and just gotten an "ok" we are now operational
				self._changeState(State.OPERATIONAL)
			

			if not self._previous_resend:
				# our most left line from the sent_lines just got acknowledged
				self._process_acknowledgement()
			else:
				self._previous_resend = False
			self._clear_for_send.set()

		elif self.__class__.MESSAGE_START(message):
			# initial handshake with the firmware
			if self._state != State.CONNECTED:
				# we received a "start" while running, this means the printer has unexpectedly reset
				self._changeState(State.CONNECTED)
			self._reset(from_start=True)
			return

		elif self.__class__.MESSAGE_RESEND(message):
			self._previous_resend = True
			self._handle_resend_request(message)
			return

		elif self.__class__.MESSAGE_WAIT(message):
			#self._clear_for_send.set()
			# TODO really?
			return

		# SD file list
		if self._receivingSdFileList and not self.__class__.MESSAGE_SD_END_FILE_LIST(message):
			fileinfo = message.strip().split(None, 2)
			if len(fileinfo) > 1:
				filename, size = fileinfo
				filename = filename.lower()
				try:
					size = int(size)
				except ValueError:
					# whatever that was, it was not an integer, so we'll ignore it and set size to None
					size = None
			else:
				filename = fileinfo[0].lower()
				size = None

			if valid_file_type(filename, "gcode"):
				if filterNonAscii(filename):
					self._logger.warn("Got a file from printer's SD that has a non-ascii filename (%s), that shouldn't happen according to the protocol" % filename)
				else:
					self._addSdFile(filename, size)
				return

		##~~ regular message processing

						

		# sd state
		elif self.__class__.MESSAGE_SD_INIT_OK(message):
			self._changeSdState(True)			
			init_ok, baseFolder = message.strip().split(":", 2)
			
			from octoprint.server import fileManager
			storage_managers_FastbotSDCARD = octoprint.filemanager.storage.LocalFileStorage(baseFolder)					
			fileManager.add_storage(octoprint.filemanager.FileDestinations.FastbotSDCARD, storage_managers_FastbotSDCARD)
			
		elif self.__class__.MESSAGE_SD_INIT_FAIL(message):
			self._changeSdState(False)
			from octoprint.server import fileManager
			fileManager.remove_storage(octoprint.filemanager.FileDestinations.FastbotSDCARD)

		# sd progress
		elif self.__class__.MESSAGE_SD_PRINTING_BYTE(message):
			match = self.__class__.REGEX_SD_PRINTING_BYTE.search(message)
			if isinstance(self._current_file, PrintingSdFileInformation):
				self._current_file.setFilepos(int(match.group(1)))
			self._reportProgress()
		elif self.__class__.MESSAGE_SD_DONE_PRINTING(message):
			if isinstance(self._current_file, PrintingSdFileInformation):
				self._current_file.setFilepos(0)
			self._changeState(State.OPERATIONAL)
			self._finishPrintjob()

		# sd file list
		elif self.__class__.MESSAGE_SD_BEGIN_FILE_LIST(message):
			self._resetSdFiles()
			self._receivingSdFileList = True
		elif self.__class__.MESSAGE_SD_END_FILE_LIST(message):
			self._receivingSdFileList = False
			self._sendSdFiles()

		# sd file selection
		elif self.__class__.MESSAGE_SD_FILE_OPENED(message):
			match = self.__class__.REGEX_FILE_OPENED.search(message)
			self._selectFile(PrintingSdFileInformation(match.group(1), int(match.group(2))))

		# sd file streaming
		elif self.__class__.MESSAGE_SD_BEGIN_WRITING(message):
			self._changeState(State.STREAMING)
		elif self.__class__.MESSAGE_SD_END_WRITING(message):
			self.refresh_sd_files()

		# firmware specific messages
		if not self._evaluate_firmware_specific_messages(source, message):
			return

		if not self.is_streaming():
			if time.time() > self._lastTemperatureUpdate + self._temperature_interval:
				self._send_temperature_query(with_type=True)
			elif self.is_sd_printing() and time.time() > self._lastSdProgressUpdate + self._sdstatus_interval:
				self._send_sd_progress_query(with_type=True)

	def onTimeoutReceived(self, source):
		if self._transport != source:
			return
		# allow sending to restart communication
		if self._state != State.OFFLINE:
			if self._clear_for_send.blocked():
				self._clear_for_send.set()

	def _stateChanged(self, newState):
		if ((self._state == State.PRINTING and not isinstance(self._current_file, PrintingSdFileInformation))
			or self._state == State.STREAMING):
			#lkj
			#print("lkj self._heatupOK:%s" % str(self._heatupOK))
			#if self._heatupOK is True:
			self._fill_queue_state_signal.set()
		else:
			self._fill_queue_state_signal.clear()

	##~~ private

	def _process_acknowledgement(self):
		output = self._output
		self._output = []

		with self._send_lock:
			if len(self._sent_lines) > 0:
				entry = self._sent_lines.popleft()

				if entry.command is not None:
					entry.command.output = output
					print("!!! Adding output to command %s: %r (entry: %r)" % (entry.command.command, entry.command.output, entry))

				# process command as acknowledged
				self._process_command(entry.command, "acknowledged", with_line_number=entry.line_number)

				if entry.command is not None:
					if entry.command.progress is not None:
						# if we got a progress, report it
						self._reportProgress(**entry.command.progress)

					if entry.command.callback is not None:
						# if we got a callback, call it
						entry.command.callback(entry.command)

				if len(self._sent_lines) > 0:
					# let's take a look at the next item in the nack queue, it might be a special entry demanding some action
					# from us now
					following_entry = self._sent_lines[0]
					if isinstance(following_entry, SpecialCommandQueueEntry):
						if following_entry.type == SpecialCommandQueueEntry.TYPE_JOBDONE:
							# we got a special queue item that marks that we just acknowledged the last command of
							# an ongoing print job, so let's signal that now
							if self.is_streaming():
								self._finishFileTransfer()
							else:
								self._finishPrintjob()

						# let's remove the special command, we should have processed it now...
						self._sent_lines.popleft()

			else:
				self._logger.warn("Ooops, got an ok but had no unacknowledged command O.o")

			# since we just got an acknowledgement, no more resends are pending
			self._last_resend_number = None
			self._current_resend_count = 0
			self._sent_before_resend = 0

	def _evaluate_firmware_specific_messages(self, source, message):
		return True

	def _send(self, command, high_priority=False, command_type=None, with_progress=None):
		if command is None:
			return

		if isinstance(command, CommandQueueEntry):
			entry = command
			if entry.command is not None:
				entry.command.progress = with_progress
		else:
			if not isinstance(command, GcodeCommand):
				command = GcodeCommand.from_line(command)
			command.progress = with_progress
			command, with_line_number = self._process_command(command, "queued")
			if command is None:
				return

			entry = CommandQueueEntry(
				CommandQueueEntry.PRIORITY_HIGH if high_priority else CommandQueueEntry.PRIORITY_NORMAL,
				command,
				line_number=with_line_number,
				command_type=command_type
			)

		try:
			self._send_queue.put(entry)
		except TypeAlreadyInQueue:
			pass

	# Called only from worker thread, not thread safe
	def _send_next(self):
		try:
			command = self._current_file.getNext()
		except ValueError:
			print("lkj _send_next ValueError")
			# TODO _current_file might already be closed since the print ended asynchronously between our callee and here, causing a ValueError => find some nicer way to handle this
			return None

		if command is None:
			command = SpecialCommandQueueEntry(SpecialCommandQueueEntry.TYPE_JOBDONE)

		self._send(command, with_progress=dict(completion=self._getPrintCompletion(), filepos=self._getPrintFilepos()))

	def _send_temperature_query(self, with_high_priority=False, with_type=False):
		self._send(self.__class__.COMMAND_GET_TEMP(), high_priority=with_high_priority, command_type=self.__class__.COMMAND_TYPE_TEMPERATURE if with_type else None)
		self._lastTemperatureUpdate = time.time()

	def _send_sd_progress_query(self, with_high_priority=False, with_type=False):
		self._send(self.__class__.COMMAND_SD_STATUS(), high_priority=with_high_priority, command_type=self.__class__.COMMAND_TYPE_SD_PROGRESS if with_type else None)
		self._lastSdProgressUpdate = time.time()

	def _handle_errors(self, line):
		if self.__class__.MESSAGE_ERROR(line):
			if self.__class__.MESSAGE_ERROR_MULTILINE(line):
				error = self._transport.receive()
			else:
				error = self.__class__.TRANSFORM_ERROR(line)

			# skip the communication errors as those get corrected via resend requests
			if self.__class__.MESSAGE_ERROR_COMMUNICATION(error):
				self._last_comm_error = error
				pass
			# handle the error
			elif not self._state == State.ERROR:
				self.onError(error)
		return line

	def _parse_temperatures(self, line):
		result = {}
		maxToolNum = 0
		for match in re.finditer(self.__class__.REGEX_TEMPERATURE, line):
			tool = match.group(1)
			toolNumber = int(match.group(2)) if match.group(2) and len(match.group(2)) > 0 else None
			if toolNumber > maxToolNum:
				maxToolNum = toolNumber

			try:
				actual = float(match.group(3))
				target = None
				if match.group(4) and match.group(5):
					target = float(match.group(5))

				result[tool] = (toolNumber, actual, target)
			except ValueError:
				# catch conversion issues, we'll rather just not get the temperature update instead of killing the connection
				pass

		if "T0" in result.keys() and "T" in result.keys():
			del result["T"]

		return maxToolNum, result

	def _process_temperatures(self, line):
		maxToolNum, parsedTemps = self._parse_temperatures(line)

		import copy
		result = copy.deepcopy(self._current_temperature)

		# extruder temperatures
		if not "T0" in parsedTemps.keys() and not "T1" in parsedTemps.keys() and "T" in parsedTemps.keys():
			# no T1 so only single reporting, "T" is our one and only extruder temperature
			toolNum, actual, target = parsedTemps["T"]

			if target is not None:
				result["tool0"] = (actual, target)
			elif "tool0" in result and result["tool0"] is not None and isinstance(result["tool0"], tuple):
				(oldActual, oldTarget) = result["tool0"]
				result["tool0"] = (actual, oldTarget)
			else:
				result["tool0"] = (actual, None)

		elif not "T0" in parsedTemps.keys() and "T" in parsedTemps.keys():
			# Smoothieware sends multi extruder temperature data this way: "T:<first extruder> T1:<second extruder> ..." and therefore needs some special treatment...
			# TODO: Move to Smoothieware sub class?
			_, actual, target = parsedTemps["T"]
			del parsedTemps["T"]
			parsedTemps["T0"] = (0, actual, target)

		if "T0" in parsedTemps.keys():
			for n in range(maxToolNum + 1):
				tool = "T%d" % n
				if not tool in parsedTemps.keys():
					continue

				toolNum, actual, target = parsedTemps[tool]
				key = "tool%d" % toolNum
				if target is not None:
					result[key] = (actual, target)
				elif key in result and result[key] is not None and isinstance(result[key], tuple):
					(oldActual, oldTarget) = result[key]
					result[key] = (actual, oldTarget)
				else:
					result[key] = (actual, None)

		# bed temperature
		if "B" in parsedTemps.keys():
			toolNum, actual, target = parsedTemps["B"]
			if target is not None:
				result["bed"] = (actual, target)
			elif "bed" in result and result["bed"] is not None and isinstance(result["bed"], tuple):
				(oldActual, oldTarget) = result["bed"]
				result["bed"] = (actual, oldTarget)
			else:
				result["bed"] = (actual, None)

		self._updateTemperature(result)

	def _handle_resend_request(self, message):
		line_to_resend = None
		try:
			line_to_resend = int(message.replace("N:", " ").replace("N", " ").replace(":", " ").split()[-1])
		except:
			if "rs" in message:
				line_to_resend = int(message.split()[1])

		last_comm_error = self._last_comm_error
		self._last_comm_error = None

		if line_to_resend is not None:
			with self._send_lock:
				if len(self._sent_lines) > 0:
					nack_entry = self._sent_lines[0]

					if last_comm_error is not None and \
							self.__class__.MESSAGE_ERROR_COMMUNICATION_LINENUMBER(last_comm_error) \
							and line_to_resend == self._last_resend_number \
							and self._current_resend_count < self._sent_before_resend:
						# this resend is a complaint about the wrong line_number, we already resent the requested
						# one and didn't see more resend requests for those yet than we had additional lines in the sent
						# buffer back then, so this is probably caused by leftovers in the printer's receive buffer
						# (that got sent after the firmware cleared the receive buffer but before we'd fully processed
						# the old resend request), we'll therefore just increment our counter and ignore this
						self._current_resend_count += 1
						return
					else:
						# this is either a resend request for a new line_number, or a resend request not caused by a
						# line number mismatch, or we now saw more consecutive requests for that line number than there
						# were additional lines in the nack buffer when we saw the first one, so we'll have to handle it
						self._last_resend_number = line_to_resend
						self._current_resend_count = 0
						self._sent_before_resend = len(self._sent_lines) - 1

					if nack_entry.line_number is not None and nack_entry.line_number == line_to_resend:
						try:
							while True:
								entry = self._sent_lines.popleft()
								entry.priority = CommandQueueEntry.PRIORITY_RESEND
								try:
									self._send_queue.put(entry)
								except TypeAlreadyInQueue:
									pass
						except IndexError:
							# that's ok, the nack lines are just empty
							pass

						return

					elif line_to_resend < nack_entry.line_number:
						# we'll ignore that resend request since that line was already acknowledged in the past
						return

				# if we've reached this point, we could not resend the requested line
				error = "Printer requested line %d but no sufficient history is available, can't resend" % line_to_resend
				self._logger.warn(error)
				if self.is_printing():
					# abort the print, there's nothing we can do to rescue it now
					self.onError(error)

				# reset line number local and remote
				self._current_line = 1
				self._sent_lines.clear()
				self._send(self.__class__.COMMAND_SET_LINE(0))

	##~~ handle queue filling in this thread when printing or streaming

	def _fill_send_queue(self):
		while self._fill_queue_processing:
			self._fill_queue_state_signal.wait(0.1)				
			if self._heatupOK is not True:
				time.sleep(0.5)
				continue
				
			
			#print("lkj try to get _fill_queue_mutex!!!!!!!!!!!!!!")
			with self._fill_queue_mutex:	
				#print("lkj get _fill_queue_mutex   ok!!!!!!!!!!!!!!")
				
				#print("lkj in _fill_send_queue, wait timeout _fill_queue_state_signal")
				if not ((self._state == State.PRINTING and not isinstance(self._current_file, PrintingSdFileInformation))
			                or self._state == State.STREAMING):
					continue					
				
				#print("lkj in _fill_send_queue, wait acquire _fill_queue_semaphore")
				#print("_fill_queue_semaphore value: %r" % self._fill_queue_semaphore._Semaphore__value)
				if self._fill_queue_semaphore.acquire(0.5):
					self._send_next()
					#print("/// sent next line from file: %r" % self._fill_queue_semaphore._Semaphore__value)
				#print("lkj fill send queue \n")
			#print("lkj release _fill_queue_mutex!!!!!!!!!!!!!!")	

	##~~ the actual send queue handling starts here

	def _handle_send_queue(self):
		while self._send_queue_processing:
			if self._send_queue.qsize() == 0:
				# queue is empty, wait a bit before checking again
				if ((self._state == State.PRINTING and not isinstance(self._current_file, PrintingSdFileInformation))
				    or self._state == State.STREAMING):
					pass
					#lkj self._logger.warn("_handle_send_queue, Buffer under run while printing!")
				time.sleep(0.1)
				continue

			if self._blocking_command_active:
				# blocking command is active, no use to send anything to the printer right now
				time.sleep(0.1)
				continue

			try:
				with self._send_lock:
					with self._send_queue.clearlock:
						sent = self._send_from_queue()
			except SendTimeout:
				# we just got a send timeout, so we'll just try again on the next loop iteration
				continue

			if not sent or self._rx_cache_size <= 0:
				# decrease the clear_for_send counter
				self._clear_for_send.clear()
				self._clear_for_send.wait()

	def _send_from_queue(self):
		item, entry = self._send_queue.peek()
		if item is None:
			if ((self._state == State.PRINTING and not isinstance(self._current_file, PrintingSdFileInformation))
			    or self._state == State.STREAMING):
				pass 
				#lkj self._logger.warn("_send_from_queue, Buffer under run while printing!")
			return False

		if not self._startSeen:
			return False
		if isinstance(item, SpecialCommandQueueEntry):
			self._sent_lines.append(item)
		else:
			if item.prepared is None:
				prepared, line_number = self._prepare_for_sending(item.command, with_line_number=item.line_number)

				item.prepared = prepared
				item.line_number = line_number

			if item.prepared is not None:
				# only actually send the command if it wasn't filtered out by preprocessing

				current_size = sum(self._sent_lines)
				new_size = current_size + item.size
				if new_size > self._rx_cache_size > 0 and not (current_size == 0):
					# Do not send if the left over space in the buffer is too small for this line. Exception: the buffer is empty
					# and the line still doesn't fit
					return False

				# send the command - we might get a SendTimeout here which is supposed to bubble up since it's caught in the
				# actual send loop
				print("+++ sent: %r" % item)
				try:
					self._transport.send(item.prepared)
				except:
					# remove from send queue
					try:
						print("get except")
						self._fill_queue_semaphore.release()
					except :
						pass	
					self._send_queue.remove(entry)
					return False
				# add the queue item into the deque of commands not yet acknowledged
				self._sent_lines.append(item)

				self._process_command(item.command, "sent", with_line_number=item.line_number)
			else:
				self._logger.debug("Dropping command which was disabled through preprocessing: %s" % item.command)

		# remove from send queue
		try:
			self._fill_queue_semaphore.release()
		except ValueError:
			# that's ok, the bounded semaphore complains that we just released more often than we acquired, but
			# we do this explicitly an just use the bounded semaphore to guarantee an upper bound on the
			# items added to the send queue by the fill thread
			pass
		self._send_queue.remove(entry)

		return True

	##~~ preprocessing of command in the three phases "queued", "sent" and "acknowledged"

	def _process_command(self, command, phase, with_line_number=None):
		if command is None:
			return None, None, None

		if not phase in ("queued", "sending", "sent", "acknowledged"):
			return None

		#handle our hooks, if any
		for hook in self._gcode_hooks[phase]:
			command, with_line_number = hook(self, command, with_line_number)

		if phase in self._preprocessors and command is not None and command.command in self._preprocessors[phase]:
			command, with_line_number = self._preprocessors[phase][command.command](command, with_line_number)

		# blocking command?
		if command is not None and command.command in self.__class__.BLOCKING_COMMANDS:
			if phase == "sent":
				self._logger.info("Waiting for a blocking command to finish: %s" % command.command)
				self._blocking_command_active = True
			elif phase == "acknowledged":
				self._logger.info("Blocking command finished: %s" % command.command)
				self._blocking_command_active = False

		return command, with_line_number

	def _prepare_for_sending(self, command, with_line_number=None):
		command, with_line_number = self._process_command(command, "sending", with_line_number=with_line_number)
		if command is None or command.unknown:
			return None, None

		if self._force_checksum:
			if with_line_number is not None:
				line_number = with_line_number
			else:
				line_number = self._current_line
			command_to_send = "N%d %s" % (line_number, str(command))

			checksum = reduce(lambda x, y: x ^ y, map(ord, command_to_send))

			if with_line_number is None:
				self._current_line += 1

			return "%s*%d" % (command_to_send, checksum), line_number
		else:
			return str(command), None

	##~~ specific command actions

	def _gcode_T_acknowledged(self, command, with_line_number):
		self._current_extruder = command.tool
		return command, with_line_number

	def _gcode_G0_acknowledged(self, command, with_line_number):
		if command.z is not None:
			self._reportZChange(command.z)
		if command.f is not None:
			self._last_seen_f = command.f
		return command, with_line_number
	_gcode_G1_acknowledged = _gcode_G0_acknowledged

	def _gcode_M0_queued(self, command, with_line_number):
		self.pause_print()
		# Don't send the M0 or M1 to the machine, as M0 and M1 are handled as an LCD menu pause.
		return None, with_line_number
	_gcode_M1_queued = _gcode_M0_queued

	def _gcode_M104_sent(self, command, with_line_number):
		key = "tool%d" % command.t if command.t is not None else self._current_extruder
		self._handle_temperature_code(command, key)
		return command, with_line_number
	_gcode_M109_sent = _gcode_M104_sent

	def _gcode_M140_sent(self, command, with_line_number):
		key = "bed"
		self._handle_temperature_code(command, key)
		return command, with_line_number
	_gcode_M190_sent = _gcode_M140_sent

	def _handle_temperature_code(self, command, key):
		if command.s is not None:
			target = command.s
			if key in self._current_temperature and self._current_temperature[key] is not None and isinstance(self._current_temperature[key], tuple):
				actual, old_target = self._current_temperature[key]
				self._current_temperature[key] = (actual, target)
			else:
				self._current_temperature[key] = (None, target)

	def _gcode_M110_sending(self, command, with_line_number):
		if command.n is not None:
			new_line_number = command.n
		else:
			new_line_number = 0

		self._current_line = new_line_number + 1

		# send M110 command with new line number
		return command, new_line_number

	def _gcode_M112_queued(self, command, with_line_number): # It's an emergency what todo? Canceling the print should be the minimum
		self.cancel_print()
		return command, with_line_number

