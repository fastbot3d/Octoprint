# coding=utf-8
from __future__ import absolute_import

__author__ = "Gina Häußge <osd@foosel.net>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'
__copyright__ = "Copyright (C) 2014 The OctoPrint Project - Released under terms of the AGPLv3 License"

from flask import request, jsonify, make_response, url_for

import octoprint.util as util
from octoprint.filemanager.destinations import FileDestinations
from octoprint.settings import settings, valid_boolean_trues
from octoprint.server import printer, fileManager, slicingManager, eventManager, NO_CONTENT
from octoprint.server.util.flask import restricted_access
from octoprint.server.api import api
from octoprint.events import Events
import octoprint.filemanager


#lkj add 
@api.route("/downloadSDxx", methods=["post"])
def downloadSDGcodeFiles():
	data = request.json
	
	fileName = None
	if "filename" in data:
		print("lkj downloadSDGcodeFiles 3.4")
		fileName = data["filename"]
		
	if "origin" in data:
		print("lkj downloadSDGcodeFiles 3.4")
		origin = data["origin"]	
		
	print("lkj downloadSDGcodeFiles request.values:%s" % str(request.values) )
	print("lkj downloadSDGcodeFiles data:%s" % str(data) )
	
	if origin not in [FileDestinations.LOCAL, FileDestinations.SDCARD, FileDestinations.FastbotSDCARD]:
		return make_response("Unknown origin: %s" % origin, 404)
	print("lkj downloadSDGcodeFiles 1")
	#selectAfterUpload = "select" in request.values.keys() and request.values["select"] in valid_boolean_trues
	#printAfterSelect = "print" in request.values.keys() and request.values["print"] in valid_boolean_trues

	if origin == FileDestinations.FastbotSDCARD  and  not printer.isSdReady():
		return jsonify("")
	print("lkj downloadSDGcodeFiles 2")
	
		
	
	baseFolder = fileManager._storage(origin).get_basefolder()
	print("lkj downloadSDGcodeFiles 3.31 " )
		
	
	print("lkj downloadSDGcodeFiles 4")
	fileFullName = baseFolder + "/" + fileName
	print("lkj downloadSDGcodeFiles 5")
	buf_size = 4096
	print("download file handler:%s" % fileFullName)
	response = make_response(view_function())
	response.headers['Content-Type'] = 'application/octet-stream'
	response.headers['Content-Disposition'] = 'attachment; filename='+fileName
	response.write
	return response
	'''
	self.set_header('Content-Type', 'application/octet-stream')
	self.set_header('Content-Disposition', 'attachment; filename='+fileName)
	with open(fileFullName, 'rb') as f:
		while True:
			data = f.read(buf_size)
			if not data:
				break
			self.write(data)
	self.finish()
	'''

@api.route("/files", methods=["GET"])
def readGcodeFiles():
	filter = None
	if "filter" in request.values:
		filter = request.values["filter"]
	if filter is not None:
		print("lkj readGcodeFiles filter:%s" % repr(filter) )
	print("lkj readGcodeFiles request.values:%s" % str(request.values) )
	
	files = _getFileList(FileDestinations.LOCAL, filter=filter)
	print("lkj 1 readGcodeFiles files:%s" % str(files) )
	#lkj files.extend(_getFileList(FileDestinations.SDCARD))
	sdFree = 0
	if printer.isSdReady():
		files.extend(_getFileList(FileDestinations.FastbotSDCARD))
		sdFree = util.getFreeBytes(fileManager._storage(FileDestinations.FastbotSDCARD).get_basefolder())
		print("lkj 2 readGcodeFiles files:%s, sdFree:%s" % (str(files), str(sdFree)) )
		
	return jsonify(files=files, free=util.getFreeBytes(settings().getBaseFolder("uploads")), sdFree=sdFree)


@api.route("/files/<string:origin>", methods=["GET"])
def readGcodeFilesForOrigin(origin):
	if origin not in [FileDestinations.LOCAL, FileDestinations.SDCARD, FileDestinations.FastbotSDCARD]:
		return make_response("Unknown origin: %s" % origin, 404)

	files = _getFileList(origin)
	print("lkj readGcodeFilesForOrigin origin:%s" % origin )
	print("lkj readGcodeFilesForOrigin files:%s" % str(files) )
	if origin == FileDestinations.LOCAL:
		return jsonify(files=files, free=util.getFreeBytes(settings().getBaseFolder("uploads")))
	elif origin == FileDestinations.FastbotSDCARD:
		return jsonify(files=files, sdFree=util.getFreeBytes(fileManager._storage(origin).get_basefolder()))
	else:
		return jsonify(files=files)


def _getFileDetails(origin, filename):
	files = _getFileList(origin)
	for file in files:
		if file["name"] == filename:
			return file
	return None


def _getFileList(origin, filter=None):
	if origin == FileDestinations.SDCARD:
		sdFileList = printer.getSdFiles()

		files = []
		if sdFileList is not None:
			for sdFile, sdSize in sdFileList:
				file = {
					"type": "machinecode",
					"name": sdFile,
					"origin": FileDestinations.SDCARD,
					"refs": {
						"resource": url_for(".readGcodeFile", target=FileDestinations.SDCARD, filename=sdFile, _external=True)
					}
				}
				if sdSize is not None:
					file.update({"size": sdSize})
				files.append(file)
	else:
		filter_func = None
		if filter:
			filter_func = lambda entry, entry_data: octoprint.filemanager.valid_file_type(entry, type=filter)
		files = fileManager.list_files(origin, filter=filter_func, recursive=False)[origin].values()
		
		#lkj
		new_files = []
		for file in files:
			if "name" in file and octoprint.filemanager.valid_file_type(file["name"], type="fbot"):
				print("lkj delete 2 file name:%s" % file["name"])
			else:
				new_files.append(file)
		
		files = new_files[0:len(new_files)]	
		
		print("files:%s" % (str(files)))		
		for file in files:
			file["origin"] = origin		

			if "analysis" in file and octoprint.filemanager.valid_file_type(file["name"], type="gcode"):
				file["gcodeAnalysis"] = file["analysis"]
				del file["analysis"]

			if "history" in file and octoprint.filemanager.valid_file_type(file["name"], type="gcode"):
				# convert print log
				history = file["history"]
				del file["history"]
				success = 0
				failure = 0
				last = None
				for entry in history:
					success += 1 if "success" in entry and entry["success"] else 0
					failure += 1 if "success" in entry and not entry["success"] else 0
					if not last or ("timestamp" in entry and "timestamp" in last and entry["timestamp"] > last["timestamp"]):
						last = entry
				if last:
					prints = dict(
						success=success,
						failure=failure,
						last=dict(
							success=last["success"],
							date=last["timestamp"]
						)
					)
					if "printTime" in last:
						prints["last"]["printTime"] = last["printTime"]
					file["prints"] = prints

			file.update({
				"refs": {
			                "resource": url_for(".readGcodeFile", target=origin, filename=file["name"], _external=True),
			                "download": url_for("index", _external=True) + "downloads/files/" + origin + "/" + file["name"]
			                #lkj
			                # "resource": url_for(".readGcodeFile", target=FileDestinations.LOCAL, filename=file["name"], _external=True),
			                # "download": url_for("index", _external=True) + "downloads/files/" + FileDestinations.LOCAL + "/" + file["name"]
			                
				}
			                
			})
	return files


def _verifyFileExists(origin, filename):
	if origin == FileDestinations.SDCARD:
		return filename in map(lambda x: x[0], printer.getSdFiles())
	else:
		return fileManager.file_exists(origin, filename)

#lkj, bug , only upload little size file less than 200k.
#@api.route("/filesFirmware/<string:target>", methods=["POST"])
#@restricted_access
def uploadFirmwareFile(target):
	print("lkj uploadFirmwareFile target:%s" % str(target))
	target = FileDestinations.LOCAL
	if not target in [FileDestinations.LOCAL, FileDestinations.SDCARD]:
		return make_response("Unknown target: %s" % target, 404)
	
	print("lkj post target:%s" % str(target))
	print("lkj post request.values:%s" % str(request.values))
	print("lkj post request.files:%s" % str(request.files))
	
	input_name = "file"
	input_upload_name = input_name + "." + settings().get(["server", "uploads", "nameSuffix"])
	input_upload_path = input_name + "." + settings().get(["server", "uploads", "pathSuffix"])
	if input_upload_name in request.values and input_upload_path in request.values:
		print("lkj here 1")
		import shutil
		upload = util.Object()
		upload.filename = request.values[input_upload_name]
		upload.save = lambda new_path: shutil.move(request.values[input_upload_path], new_path)
	elif input_name in request.files:
		print("lkj here 2")
		upload = request.files[input_name]
	else:
		return make_response("No file included", 400)
	print("lkj post 2")
	# determine future filename of file to be uploaded, abort if it can't be uploaded
	try:
		futureFilename = fileManager.sanitize_name(FileDestinations.LOCAL, upload.filename)
	except:
		futureFilename = None
		
	print("lkj futureFilename:%s" % futureFilename)
	
	try :
		added_file = fileManager.add_firmware_file(FileDestinations.LOCAL, upload.filename, upload, allow_overwrite=True)
	except :
		added_file = None
	if added_file is None:
		print("lkj post added_file is None")
		return make_response("Could not upload the file %s" % upload.filename, 500)
	print("lkj added_file: %s" % added_file)
	
	files = {}
	done = True
	files.update({
		FileDestinations.LOCAL: {
			"name": added_file,
			"origin": FileDestinations.LOCAL		
		}
	})
	r = make_response(jsonify(files=files, done=done), 201)
	#lkj 
	from octoprint.server import printer
	if printer.isOperational():
		#cmd = ("M205", param=added_file)
		#printer.command()
		pass
			
	#r.headers["Location"] = added_file
	return r


def upload_temp_curve_firmware(target):
	print("lkj upload_temp_curve_firmware target:%s" % str(target))

	print("lkj post request.values:%s" % str(request.values))
	print("lkj post request.files:%s" % str(request.files))
	
	input_name = "file"
	input_upload_name = input_name + "." + settings().get(["server", "uploads", "nameSuffix"])
	input_upload_path = input_name + "." + settings().get(["server", "uploads", "pathSuffix"])
	if input_upload_name in request.values and input_upload_path in request.values:
		print("lkj here 1")
		import shutil
		upload = util.Object()
		upload.filename = request.values[input_upload_name]
		upload.save = lambda new_path: shutil.move(request.values[input_upload_path], new_path)
	elif input_name in request.files:
		print("lkj here 2")
		upload = request.files[input_name]
	else:
		return make_response("No file included", 400)
	print("lkj post 2")
	# determine future filename of file to be uploaded, abort if it can't be uploaded
	try:
		futureFilename = fileManager.sanitize_name(FileDestinations.LOCAL, upload.filename)
	except:
		futureFilename = None
		
	print("lkj futureFilename:%s" % futureFilename)
	
	try :
		added_file = fileManager.add_temp_curve_file(FileDestinations.LOCAL, upload.filename, upload, allow_overwrite=True, target=target)
	except :
		added_file = None
	if added_file is None:
		print("lkj post added_file is None")
		return make_response("Could not upload the file %s" % upload.filename, 500)
	print("lkj added_file: %s" % added_file)
	
	files = {}
	done = True
	files.update({
		FileDestinations.LOCAL: {
			"name": added_file,
			"origin": FileDestinations.LOCAL		
		}
	})
	r = make_response(jsonify(files=files, done=done), 201)	
	return r



def uploadFastBotSDCARD(target):
	print("lkj uploadFastBotSDCARD target:%s" % str(target))
	#target = FileDestinations.FastbotSDCARD
	
	print("lkj post request.values:%s" % str(request.values))
	print("lkj post request.files:%s" % str(request.files))


	input_name = "file"
	input_upload_name = input_name + "." + settings().get(["server", "uploads", "nameSuffix"])
	input_upload_path = input_name + "." + settings().get(["server", "uploads", "pathSuffix"])
	if input_upload_name in request.values and input_upload_path in request.values:
		import shutil
		upload = util.Object()
		upload.filename = request.values[input_upload_name]
		upload.save = lambda new_path: shutil.move(request.values[input_upload_path], new_path)
	elif input_name in request.files:
		upload = request.files[input_name]
	else:
		return make_response("No file included", 400)
	
	print("lkj post upload:%s" % str(upload))
	
	if target == FileDestinations.FastbotSDCARD and not settings().getBoolean(["feature", "sdSupport"]):
		return make_response("SD card support is disabled", 404)
	print("lkj uploadGcodeFile 2")
	sd = target == FileDestinations.FastbotSDCARD
	selectAfterUpload = "select" in request.values.keys() and request.values["select"] in valid_boolean_trues
	printAfterSelect = "print" in request.values.keys() and request.values["print"] in valid_boolean_trues

	print("lkj uploadGcodeFile 3")	
	# determine current job
	currentFilename = None
	currentOrigin = None
	currentJob = printer.getCurrentJob()
	if currentJob is not None and "file" in currentJob.keys():
		currentJobFile = currentJob["file"]
		if "name" in currentJobFile.keys() and "origin" in currentJobFile.keys():
			currentFilename = currentJobFile["name"]
			currentOrigin = currentJobFile["origin"]

	# determine future filename of file to be uploaded, abort if it can't be uploaded
	try:
		futureFilename = fileManager.sanitize_name(FileDestinations.FastbotSDCARD, upload.filename)
	except:
		futureFilename = None
	if futureFilename is None or not (slicingManager.slicing_enabled or octoprint.filemanager.valid_file_type(futureFilename, type="gcode")):
		return make_response("Can not upload file %s, wrong format?" % upload.filename, 415)
	print("lkj uploadGcodeFile 4")
	# prohibit overwriting currently selected file while it's being printed
	if futureFilename == currentFilename and target == currentOrigin and printer.isPrinting() or printer.isPaused():
		return make_response("Trying to overwrite file that is currently being printed: %s" % currentFilename, 409)
	print("lkj uploadGcodeFile 5")
	def fileProcessingFinished(filename, absFilename, destination):
		"""
		Callback for when the file processing (upload, optional slicing, addition to analysis queue) has
		finished.

		Depending on the file's destination triggers either streaming to SD card or directly calls selectAndOrPrint.
		"""
		selectAndOrPrint(filename, absFilename, destination)
		return filename

	def selectAndOrPrint(filename, absFilename, destination):
		"""
		Callback for when the file is ready to be selected and optionally printed. For SD file uploads this is only
		the case after they have finished streaming to the printer, which is why this callback is also used
		for the corresponding call to addSdFile.

		Selects the just uploaded file if either selectAfterUpload or printAfterSelect are True, or if the
		exact file is already selected, such reloading it.
		"""
		if octoprint.filemanager.valid_file_type(added_file, "gcode") and (selectAfterUpload or printAfterSelect or (currentFilename == filename and currentOrigin == destination)):
			printer.selectFile(absFilename, destination == FileDestinations.FastbotSDCARD, printAfterSelect)
	print("lkj uploadGcodeFile 6")		
	added_file = fileManager.add_file(FileDestinations.FastbotSDCARD, upload.filename, upload, allow_overwrite=True)
	if added_file is None:
		return make_response("Could not upload the file %s" % upload.filename, 500)
	
	print("lkj uploadGcodeFile 6.0, added_file:%s" % str(added_file))
	if octoprint.filemanager.valid_file_type(added_file, "stl"):
		filename = added_file
		done = True
		print("lkj uploadGcodeFile 6.1")
	else:
		filename = fileProcessingFinished(added_file, fileManager.get_absolute_path(FileDestinations.FastbotSDCARD, added_file), target)
		done = True

	sdFilename = filename

	eventManager.fire(Events.UPLOAD, {"file": filename, "target": target})

	files = {}
	'''
	location = url_for(".readGcodeFile", target=FileDestinations.LOCAL, filename=filename, _external=True)
	files.update({
                FileDestinations.LOCAL: {
                        "name": filename,
                        "origin": FileDestinations.LOCAL,
                        "refs": {
                                "resource": location,
                                "download": url_for("index", _external=True) + "downloads/files/" + FileDestinations.LOCAL + "/" + filename
                        }
                }
        })
	'''
	print("lkj uploadGcodeFile 7 sdFilename:%s" % sdFilename)
	if sd and sdFilename:
		print("lkj uploadGcodeFile 7.1")
		location = url_for(".readGcodeFile", target=FileDestinations.FastbotSDCARD, filename=sdFilename, _external=True)
		files.update({
	                FileDestinations.FastbotSDCARD: {
	                        "name": sdFilename,
	                        "origin": FileDestinations.FastbotSDCARD,
	                        "refs": {
	                                "resource": location
	                        }
	                }
	        })
	print("lkj uploadFastBotSDCARD 8")	
	r = make_response(jsonify(files=files, done=done), 201)
	r.headers["Location"] = location
	return r	


@api.route("/files/<string:target>", methods=["POST"])
@restricted_access
def uploadGcodeFile(target):
	print("lkj uploadGcodeFile target:%s" % str(target))
	if target in ["extruder1", "extruder2", "bed"] :
		return upload_temp_curve_firmware(target)
	
	if target == "firmware" :
		return uploadFirmwareFile(target)	
	
	if target == FileDestinations.FastbotSDCARD :		
		return uploadFastBotSDCARD(target)	
		
	if not target in [FileDestinations.LOCAL, FileDestinations.SDCARD]:
		return make_response("Unknown target: %s" % target, 404)

	input_name = "file"
	input_upload_name = input_name + "." + settings().get(["server", "uploads", "nameSuffix"])
	input_upload_path = input_name + "." + settings().get(["server", "uploads", "pathSuffix"])
	if input_upload_name in request.values and input_upload_path in request.values:
		import shutil
		upload = util.Object()
		upload.filename = request.values[input_upload_name]
		upload.save = lambda new_path: shutil.move(request.values[input_upload_path], new_path)
	elif input_name in request.files:
		upload = request.files[input_name]
	else:
		return make_response("No file included", 400)

	if target == FileDestinations.SDCARD and not settings().getBoolean(["feature", "sdSupport"]):
		return make_response("SD card support is disabled", 404)

	sd = target == FileDestinations.SDCARD
	selectAfterUpload = "select" in request.values.keys() and request.values["select"] in valid_boolean_trues
	printAfterSelect = "print" in request.values.keys() and request.values["print"] in valid_boolean_trues

	if sd:
		# validate that all preconditions for SD upload are met before attempting it
		if not (printer.isOperational() and not (printer.isPrinting() or printer.isPaused())):
			return make_response("Can not upload to SD card, printer is either not operational or already busy", 409)
		if not printer.isSdReady():
			return make_response("Can not upload to SD card, not yet initialized", 409)

	# determine current job
	currentFilename = None
	currentOrigin = None
	currentJob = printer.getCurrentJob()
	if currentJob is not None and "file" in currentJob.keys():
		currentJobFile = currentJob["file"]
		if "name" in currentJobFile.keys() and "origin" in currentJobFile.keys():
			currentFilename = currentJobFile["name"]
			currentOrigin = currentJobFile["origin"]

	# determine future filename of file to be uploaded, abort if it can't be uploaded
	try:
		futureFilename = fileManager.sanitize_name(FileDestinations.LOCAL, upload.filename)
	except:
		futureFilename = None
	if futureFilename is None or not (slicingManager.slicing_enabled or octoprint.filemanager.valid_file_type(futureFilename, type="gcode")):
		return make_response("Can not upload file %s, wrong format?" % upload.filename, 415)

	# prohibit overwriting currently selected file while it's being printed
	if futureFilename == currentFilename and target == currentOrigin and printer.isPrinting() or printer.isPaused():
		return make_response("Trying to overwrite file that is currently being printed: %s" % currentFilename, 409)

	def fileProcessingFinished(filename, absFilename, destination):
		"""
		Callback for when the file processing (upload, optional slicing, addition to analysis queue) has
		finished.

		Depending on the file's destination triggers either streaming to SD card or directly calls selectAndOrPrint.
		"""

		if destination == FileDestinations.SDCARD and octoprint.filemanager.valid_file_type(filename, "gcode"):
			return filename, printer.addSdFile(filename, absFilename, selectAndOrPrint)
		else:
			selectAndOrPrint(filename, absFilename, destination)
			return filename

	def selectAndOrPrint(filename, absFilename, destination):
		"""
		Callback for when the file is ready to be selected and optionally printed. For SD file uploads this is only
		the case after they have finished streaming to the printer, which is why this callback is also used
		for the corresponding call to addSdFile.

		Selects the just uploaded file if either selectAfterUpload or printAfterSelect are True, or if the
		exact file is already selected, such reloading it.
		"""
		if octoprint.filemanager.valid_file_type(added_file, "gcode") and (selectAfterUpload or printAfterSelect or (currentFilename == filename and currentOrigin == destination)):
			printer.selectFile(absFilename, destination == FileDestinations.SDCARD, printAfterSelect)

	added_file = fileManager.add_file(FileDestinations.LOCAL, upload.filename, upload, allow_overwrite=True)
	if added_file is None:
		return make_response("Could not upload the file %s" % upload.filename, 500)
	if octoprint.filemanager.valid_file_type(added_file, "stl"):
		filename = added_file
		done = True
	else:
		filename = fileProcessingFinished(added_file, fileManager.get_absolute_path(FileDestinations.LOCAL, added_file), target)
		done = True

	sdFilename = None
	if isinstance(filename, tuple):
		filename, sdFilename = filename

	eventManager.fire(Events.UPLOAD, {"file": filename, "target": target})

	files = {}
	location = url_for(".readGcodeFile", target=FileDestinations.LOCAL, filename=filename, _external=True)
	files.update({
		FileDestinations.LOCAL: {
			"name": filename,
			"origin": FileDestinations.LOCAL,
			"refs": {
				"resource": location,
				"download": url_for("index", _external=True) + "downloads/files/" + FileDestinations.LOCAL + "/" + filename
			}
		}
	})

	if sd and sdFilename:
		location = url_for(".readGcodeFile", target=FileDestinations.SDCARD, filename=sdFilename, _external=True)
		files.update({
			FileDestinations.SDCARD: {
				"name": sdFilename,
				"origin": FileDestinations.SDCARD,
				"refs": {
					"resource": location
				}
			}
		})

	r = make_response(jsonify(files=files, done=done), 201)
	r.headers["Location"] = location
	return r


@api.route("/files/<string:target>/<path:filename>", methods=["GET"])
def readGcodeFile(target, filename):
	if not target in [FileDestinations.LOCAL, FileDestinations.SDCARD]:
		return make_response("Unknown target: %s" % target, 404)

	file = _getFileDetails(target, filename)
	if not file:
		return make_response("File not found on '%s': %s" % (target, filename), 404)

	return jsonify(file)


@api.route("/files/<string:target>/<path:filename>", methods=["POST"])
@restricted_access
def gcodeFileCommand(filename, target):
	
	if not target in [FileDestinations.LOCAL, FileDestinations.SDCARD, FileDestinations.FastbotSDCARD]:
		return make_response("Unknown target: %s" % target, 404)

	if not _verifyFileExists(target, filename):
		return make_response("File not found on '%s': %s" % (target, filename), 404)

	# valid file commands, dict mapping command name to mandatory parameters
	valid_commands = {
		"select": [],
		"slice": []
	}

	command, data, response = util.getJsonCommandFromRequest(request, valid_commands)
	if response is not None:
		return response

	if command == "select":
		# selects/loads a file
		printAfterLoading = False
		if "print" in data.keys() and data["print"] in valid_boolean_trues:
			if not printer.isOperational():
				return make_response("Printer is not operational, cannot directly start printing", 409)
			printAfterLoading = True

		if target == FileDestinations.SDCARD:
			filenameToSelect = filename
		else:
			filenameToSelect = fileManager.get_absolute_path(target, filename)
		printer.selectFile(filenameToSelect, target, printAfterLoading)

	elif command == "slice":
		if "slicer" in data.keys():
			slicer = data["slicer"]
			del data["slicer"]
			if not slicer in slicingManager.registered_slicers:
				return make_response("Slicer {slicer} is not available".format(**locals()), 400)
			slicer_instance = slicingManager.get_slicer(slicer)
		elif "cura" in slicingManager.registered_slicers:
			slicer = "cura"
			slicer_instance = slicingManager.get_slicer("cura")
		else:
			return make_response("Cannot slice {filename}, no slicer available".format(**locals()), 415)

		if not octoprint.filemanager.valid_file_type(filename, type="stl"):
			return make_response("Cannot slice {filename}, not an STL file".format(**locals()), 415)

		if slicer_instance.get_slicer_properties()["same_device"] and (printer.isPrinting() or printer.isPaused()):
			# slicer runs on same device as OctoPrint, slicing while printing is hence disabled
			return make_response("Cannot slice on {slicer} while printing due to performance reasons".format(**locals()), 409)

		if "gcode" in data.keys() and data["gcode"]:
			gcode_name = data["gcode"]
			del data["gcode"]
		else:
			import os
			name, _ = os.path.splitext(filename)
			gcode_name = name + ".gco"

		# prohibit overwriting the file that is currently being printed
		currentOrigin, currentFilename = _getCurrentFile()
		if currentFilename == gcode_name and currentOrigin == target and (printer.isPrinting() or printer.isPaused()):
			make_response("Trying to slice into file that is currently being printed: %s" % gcode_name, 409)

		if "profile" in data.keys() and data["profile"]:
			profile = data["profile"]
			del data["profile"]
		else:
			profile = None

		if "printerProfile" in data.keys() and data["printerProfile"]:
			printerProfile = data["printerProfile"]
			del data["printerProfile"]
		else:
			printerProfile = None

		if "position" in data.keys() and data["position"] and isinstance(data["position"], dict) and "x" in data["position"] and "y" in data["position"]:
			position = data["position"]
			del data["position"]
		else:
			position = None

		select_after_slicing = False
		if "select" in data.keys() and data["select"] in valid_boolean_trues:
			if not printer.isOperational():
				return make_response("Printer is not operational, cannot directly select for printing", 409)
			select_after_slicing = True

		print_after_slicing = False
		if "print" in data.keys() and data["print"] in valid_boolean_trues:
			if not printer.isOperational():
				return make_response("Printer is not operational, cannot directly start printing", 409)
			select_after_slicing = print_after_slicing = True

		override_keys = [k for k in data if k.startswith("profile.") and data[k] is not None]
		overrides = dict()
		for key in override_keys:
			overrides[key[len("profile."):]] = data[key]

		def slicing_done(target, gcode_name, select_after_slicing, print_after_slicing):
			if select_after_slicing or print_after_slicing:
				sd = False
				if target == FileDestinations.SDCARD:
					filenameToSelect = gcode_name
					sd = True
				else:
					filenameToSelect = fileManager.get_absolute_path(target, gcode_name)
				printer.selectFile(filenameToSelect, sd, print_after_slicing)

		ok, result = fileManager.slice(slicer, target, filename, target, gcode_name,
		                               profile=profile,
		                               printer_profile_id=printerProfile,
		                               position=position,
		                               overrides=overrides,
		                               callback=slicing_done,
		                               callback_args=(target, gcode_name, select_after_slicing, print_after_slicing))

		if ok:
			files = {}
			location = url_for(".readGcodeFile", target=target, filename=gcode_name, _external=True)
			result = {
				"name": gcode_name,
				"origin": FileDestinations.LOCAL,
				"refs": {
					"resource": location,
					"download": url_for("index", _external=True) + "downloads/files/" + target + "/" + gcode_name
				}
			}

			r = make_response(jsonify(result), 202)
			r.headers["Location"] = location
			return r
		else:
			return make_response("Could not slice: {result}".format(result=result), 500)

	return NO_CONTENT


@api.route("/files/<string:target>/<path:filename>", methods=["DELETE"])
@restricted_access
def deleteGcodeFile(filename, target):
	if not target in [FileDestinations.LOCAL, FileDestinations.SDCARD, FileDestinations.FastbotSDCARD]:
		return make_response("Unknown target: %s" % target, 404)

	if not _verifyFileExists(target, filename):
		return make_response("File not found on '%s': %s" % (target, filename), 404)

	# prohibit deleting files that are currently in use
	currentOrigin, currentFilename = _getCurrentFile()
	if currentFilename == filename and currentOrigin == target and (printer.isPrinting() or printer.isPaused()):
		make_response("Trying to delete file that is currently being printed: %s" % filename, 409)

	if (target, filename) in fileManager.get_busy_files():
		make_response("Trying to delete a file that is currently in use: %s" % filename, 409)

	# deselect the file if it's currently selected
	if currentFilename is not None and filename == currentFilename:
		printer.unselectFile()

	# delete it
	if target == FileDestinations.SDCARD:
		printer.deleteSdFile(filename)
	else:
		fileManager.remove_file(target, filename)

	return NO_CONTENT

def _getCurrentFile():
	currentJob = printer.getCurrentJob()
	if currentJob is not None and "file" in currentJob.keys() and "name" in currentJob["file"] and "origin" in currentJob["file"]:
		return currentJob["file"]["origin"], currentJob["file"]["name"]
	else:
		return None, None

