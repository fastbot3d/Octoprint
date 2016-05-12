# coding=utf-8
from __future__ import absolute_import
__author__ = "Gina Häußge <osd@foosel.net>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'


import time
import os
import re
import threading
import math
import Queue

#lkj from serial import SerialTimeoutException

from octoprint.settings import settings
from octoprint.plugin import plugin_manager
from octoprint.util import get_exception_string

from .pipeReadWrite import PipeReadWrite

class FastbotPrinter():
	command_regex = re.compile("[GM]\d+")
	sleep_regex = re.compile("sleep (\d+)")
	sleep_after_regex = re.compile("sleep_after ([GM]\d+) (\d+)")
	sleep_after_next_regex = re.compile("sleep_after_next ([GM]\d+) (\d+)")
	custom_action_regex = re.compile("action_custom ([a-zA-Z0-9_]+)(\s+.*)?")

	def __init__(self, read_timeout=5.0, write_timeout=10.0):
		import logging
		self._logger = logging.getLogger("octoprint.plugin.fastbot_printer.FastbotPrinter")
		
		self._read_timeout = read_timeout
		self._write_timeout = write_timeout
		self._pipe = PipeReadWrite(self._read_timeout, self._write_timeout)
				
		

	def __str__(self):
		return "Fastbot(read_timeout={read_timeout},write_timeout={write_timeout},options={options})"\
			.format(read_timeout=self._read_timeout, write_timeout=self._write_timeout, options=settings().get(["devel", "virtualPrinter"]))


		
	def writeEmerg(self, command):		
		try:
			self._pipe.writeEmerg(command)
		except:
			exceptionString = get_exception_string()
			print("Unexpected error while writeEmerg pipe port: %s" % exceptionString)
			self.close()
			raise IOError("Failed to write, remote close")	
			
	def write(self, command):
		#commandToSend = command + "\n"
		#commandToSend = command		
		try:
			self._pipe.write(command)
		except:
			exceptionString = get_exception_string()
			print("Unexpected error while writing pipe port: %s" % exceptionString)
			self.close()
			raise IOError("Failed to write, remote close")	

	def readline(self):
		if self._pipe is None:
			return None
		try:			
			line = self._pipe.readline()		
			#print("lkj readline: %s" % str(line))
		except:
			exceptionString = get_exception_string()
			print("lkj Unexpected error while reading pipe port: %s" % exceptionString)
			self.close()
			raise IOError("Failed to readline, remote close")	
			#return None
		return line

	def close(self):
		try:
			if self._pipe is not None:
				self._pipe.close()
		finally:
			self._pipe = None
			
