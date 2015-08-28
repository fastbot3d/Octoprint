# coding=utf-8

__author__ = "luokj"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

import os
import sys
import stat  
import struct
import subprocess
import threading
 
class FirmwareFastbot:
    
    def __init__(self):
    #def __init__(self, ver, fileinfos):
        '''__header={
            magic: "XXX114113112",
            version:"0.9",
            file_num:1,
            firmware_files:[
                {file_name:"pru", file_len:100}
            ]
        }
	.fbot
	n个
	magic  "XXX114113112"  12
	version   12byte
	file_num  4 byte  
	file1_name 12byte   
	file1_len  4byte
	file2_name 
	file2_len  
	
	file1
	file2
	file3
	file4
	file5
	'''
    	self._firmwareMagic = "XXX114113112"
        #self._fastbotVersion = ver 
        self._fileInfo = [] # = fileinfos[:] #fileName, size 
        self._fileNum = 0 # = len(self._fileInfo)
	
        self._unicornCopyPath = "/usr/bin/unicorn"
	self._pruCopyPath = "/.octoprint/pru.bin"
        
        pass
    
    def rebootSystem(self,delay):
	print("rebootSystem 0")
	def rebootDelay():
	    print("rebootSystem 4")
	    self._executeSystemCommand("reboot")
	
	print("rebootSystem 1")
	t=threading.Timer(delay, rebootDelay)
	print("rebootSystem 2")
	t.start()	
	print("rebootSystem 3")

    def _executeSystemCommand(self, command):
	def commandExecutioner(command):
	    print("Executing system command: %s" % command)
	    subprocess.Popen(command, shell=True)
    
	try:
	    if isinstance(command, (list, tuple, set)):
		for c in command:
		    commandExecutioner(c)
	    else:
		commandExecutioner(command)
	except subprocess.CalledProcessError, e:
	    print("Command failed with return code %i: %s" % (e.returncode, e.message))
	except Exception, ex: 
	    print("Command failed")
    
    
    def _getHeaderInfo(self, f, destinationDirectory):
        self._fastbotVersion, self._fileNum = struct.unpack('12sI', f.read(16))
	self._fastbotVersion.strip('\x00')
	print("get version:%s, fileNum:%d"% (self._fastbotVersion, self._fileNum))
	
        count = 0        
        while count < self._fileNum:
            fileName,fileSzie = struct.unpack('12sI', f.read(16))
            print("get fileName:%s, fileSize:%d"% (fileName, fileSzie))
	    fullPath = destinationDirectory + fileName
	    print("full Path:%s" % (fullPath))   
            self._fileInfo.append((fullPath.strip('\x00'), fileSzie)) 
            count += 1
               
    
    def _setHeaderInfo():
        pass
    

        
    def _copyFiles(self):
	for (fileName,fileSzie) in self._fileInfo:
	    print("_copyFiles fileName:%s, fileSize:%d"% (fileName, fileSzie))	    	    
	    if "update" in fileName:	
		cmd = "chmod 777  " + fileName		
		self._executeSystemCommand(cmd)
		cmd = fileName
		self._executeSystemCommand(cmd)		
		continue	    
	'''
	for (fileName,fileSzie) in self._fileInfo:
	    print("_copyFiles fileName:%s, fileSize:%d"% (fileName, fileSzie))	    
	    
	    if "pru" in fileName:		
		cmd = "cp -f " + fileName + " " + self._pruCopyPath
		self._executeSystemCommand(cmd)		
		continue
	    if "unicorn" in fileName:	
		cmd = "cp -f " + fileName + " " + self._unicornCopyPath
		self._executeSystemCommand(cmd)
		cmd = "chmod 777  " + self._unicornCopyPath
		self._executeSystemCommand(cmd)		
		continue
	'''
	pass
	
    def _splitFile(self, fd):
        for (fileName,fileSzie) in self._fileInfo:
            print("split fileName:%s, fileSize:%d"% (fileName, fileSzie))
            write_fd = open(fileName, 'wb')
            write_fd.write(fd.read(fileSzie))
            write_fd.flush()
            write_fd.close()
        pass    
    
    def loadFirmware(self, filePath, destination):
        f = open(filePath, "rb")
        if f.read(12).upper() == self._firmwareMagic:
            self._getHeaderInfo(f, destination)           
            self._splitFile(f)
        else:
            print("error, ilegal firmware!!!!!!!!")
        f.close() 
	
	self._copyFiles()	
        print("loadFirmware is end")
	
	return self._fastbotVersion            
    
    def saveFirmware(self, ver, filePaths, destinationFirmwareName):
        self._fastbotVersion = ver         
        self._fileNum = len(filePaths)        
        head_part1 = struct.pack('12s12sI', self._firmwareMagic, self._fastbotVersion, self._fileNum)
        
        fullPath = destinationFirmwareName        
        firmwareFd = open(fullPath, mode='wb')
        firmwareFd.write(head_part1);
        
        
        count = 0
        while count < self._fileNum:
            fileStats = os.stat(filePaths[count]) 
            size = fileStats[stat.ST_SIZE]
            print("fileName:%s, size:%d" % (filePaths[count], size))
	    fileName=os.path.basename(filePaths[count])
            head_part2 = struct.pack('12sI', fileName, size)
            firmwareFd.write(head_part2);
            count += 1
            
        for fileName in filePaths:
            fd = open(fileName, "rb")
            firmwareFd.write(fd.read());
            fd.close()
            
        firmwareFd.flush()
        firmwareFd.close()
        print("firmware %s is ready" % (fullPath))


def main():
    firmware = FirmwareFastbot()
    #filePaths=["/disk1/bbb/test/hostapd", "/disk1/bbb/test/unicorn"]
    #firmware.saveFirmware("0.91", filePaths, "/tmp/fireware.fbot")

    #firmware.loadFirmware("/tmp/fireware.fbot", "/tmp/")
    
    '''
    import argparse
    parser = argparse.ArgumentParser(prog="run")

    parser.add_argument("-p", "--pack", action="store", type=str, dest="pack",
                        help="pack file")
    parser.add_argument("-u", "--unpack", action="store", type=str, dest="unpack",
                        help="unpack firmware")

    parser.add_argument("-v", action="store_true", dest="version",
                        help="set firmware version")
    parser.add_argument("-b", "--basedir", action="store", dest="basedir",
                        help="Specify the basedir to use for uploads, timelapses etc. OctoPrint needs to have write access. Defaults to ~/.octoprint")
    parser.add_argument("--logging", action="store", dest="logConf",
                        help="Specify the config file to use for configuring logging. Defaults to ~/.octoprint/logging.yaml")

    parser.add_argument("--daemon", action="store", type=str, choices=["start", "stop", "restart"],
                        help="Daemonize/control daemonized OctoPrint instance (only supported under Linux right now)")
    parser.add_argument("--pid", action="store", type=str, dest="pidfile", default="/tmp/octoprint.pid",
                        help="Pidfile to use for daemonizing, defaults to /tmp/octoprint.pid")

    parser.add_argument("--iknowwhatimdoing", action="store_true", dest="allowRoot",
                        help="Allow OctoPrint to run as user root")

    args = parser.parse_args()

    if args.version:
        print "OctoPrint version %s" % __version__
        sys.exit(0)

    if args.daemon:
        if sys.platform == "darwin" or sys.platform == "win32":
            print >> sys.stderr, "Sorry, daemon mode is only supported under Linux right now"
            sys.exit(2)

        daemon = Main(args.pidfile, args.config, args.basedir, args.host, args.port, args.debug, args.allowRoot, args.logConf)
        if "start" == args.daemon:
            daemon.start()
        elif "stop" == args.daemon:
            daemon.stop()
        elif "restart" == args.daemon:
            daemon.restart()
    else:
        octoprint = Server(args.config, args.basedir, args.host, args.port, args.debug, args.allowRoot, args.logConf)
        octoprint.run()
    '''
    
    
if __name__ == "__main__":
    main()
