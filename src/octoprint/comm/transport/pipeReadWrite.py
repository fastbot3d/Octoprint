# coding=utf-8
__author__ = "luokj"
__license__ = "GNU Affero General Public License http://www.gnu.org/licenses/agpl.html"
__copyright__ = "Copyright (C) 2014 luokj - Released under terms of the AGPLv3 License"

import os, time
import glob
import threading

from octoprint.util import getExceptionString
import logging
import socket

"""
close()
write(xx)
xx readline()
(readTimeout, writeTimeout)
"""

class PipeReadWrite():

	_fifo_read_name = "/tmp/fifo_py_rd_c_wr"
	_fifo_write_name = "/tmp/fifo_py_wr_c_rd"

	def __init__(self, readTimeout, writeTimeout):
		self._HOST='127.0.0.1'
		self._ReadPORT= 50012
		self._WritePORT=50002
		self._logger = logging.getLogger("lkj-PipeReadWrite")
		print(" in PipeReadWrite 0 ")
		self._socketRead = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
		#print(" in PipeReadWrite 1 ")
		self._socketWrite = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
		print(" in PipeReadWrite 2 ")
		self._connectionTimeout = 3   #3 s
		self._readTimeout = readTimeout
		self._writeTimeout = writeTimeout
		self._logger.info("PipeReadWrite init")

		self._socketRead.setblocking(1)
		self._socketRead.connect((self._HOST,self._ReadPORT))
		self._socketWrite.connect((self._HOST,self._WritePORT))
		self._readBuffer = []
		self._finishreadBuffer = True
		self._stateMutex = threading.Lock()

	def close(self):
		#import traceback
		#lkj traceback.print_stack()
		if self._socketWrite is not None:
			self._socketWrite.send("exit")
			self._socketWrite.close()
			self._socketWrite = None


		if self._socketRead is not None:
			self._socketRead.close()
			self._socketRead = None

		'''
		try:
			if self._pipeRead  is not  None :
				self._pipeRead.close()
			if self._pipeWrite is not  None :
				self._pipeWrite.close()
		except:
			exceptionString = getExceptionString()
			self._logger.error("Unexpected error while close pipe: %s" % exceptionString)

		self._pipeRead = None
		self._pipeWrite = None
		'''

		self._connectionTimeout = 0
		self._readTimeout = 0
		self._writeTimeout = 0

		self._logger.info("PipeReadWrite close")

	def readline(self):
		#print("lkj start read")

		while len(self._readBuffer) >= 1 :
			ret = self._readBuffer.pop()
			#print("return ret=%s" % ret)
			#self._logger.info("PipeReadWrite readline:%s" % ret)
			self._finishreadBuffer = False
			return ret


		if len(self._readBuffer) == 0 :
			self._finishreadBuffer = True

		if self._finishreadBuffer :
			a = self._socketRead.recv(256)
			if a is not None:
				#str2 = self._readBuffer.pop() + a
				self._readBuffer = a.split('\n')
				self._readBuffer.reverse()
				ret = self._readBuffer.pop()
				#self._logger.info("PipeReadWrite readline:%s" % ret)
				return ret

		print("lkj end read, cann't stand here!!!!")
		return a

	def write(self, value):
		if self._socketWrite is not None:
			#self._logger.info("PipeReadWrite write:%s" % value)

			with self._stateMutex :
				try:
					self._socketWrite.send(value)
					#self._socketWrite.flush()
				except:
					exceptionString = getExceptionString()
					self._logger.error("Unexpected error while writing pipe port: %s" % exceptionString)


# for test
def main():
	print(" in test main ")
	_HOST='127.0.0.1'
	_ReadPORT= 50012
	_WritePORT=50002
	print(" in PipeReadWrite 0 ")
	_socketRead = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
	#print(" in PipeReadWrite 1 ")
	_socketWrite = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
	print(" in PipeReadWrite 2 ")

	_socketRead.connect((_HOST,_ReadPORT))
	_socketWrite.connect((_HOST,_WritePORT))
	time.sleep(0.1)

	_socketWrite.send("M109\n")
	readstr = _socketRead.recv(256)
	print("read \"%s\" from pipe" % readstr)


if __name__ == '__main__' :
	main()
