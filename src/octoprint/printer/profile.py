# coding=utf-8
from __future__ import absolute_import

__author__ = "Gina Häußge <osd@foosel.net>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'
__copyright__ = "Copyright (C) 2014 The OctoPrint Project - Released under terms of the AGPLv3 License"


import os
import copy
import re

from octoprint.settings import settings
from octoprint.util import dict_merge, dict_clean

#lkj
from octoprint.comm.protocol.reprap.util import GcodeCommand





class SaveError(Exception):
	pass

class MachineType(object):
	XYZ = "XYZ"
	Delta = "Delta"
	CoreXY = "CoreXY"
	
class BedTypes(object):
	RECTANGULAR = "rectangular"
	CIRCULAR = "circular"

class PrinterProfileManager(object):
	#lkj
	COMMAND_Finish_sending_M910 = GcodeCommand("M910")
	COMMAND_Has_bed_M908 = staticmethod(lambda s: GcodeCommand("M908", s=s))	
	COMMAND_Steps_per_unit_M92 = staticmethod(lambda x, y, z, e: GcodeCommand("M92", x=x if x else None, y=y if y else None, z=z if z else None, e=e if e else None))
	COMMAND_Maximum_area_unit_M520 = staticmethod(lambda x, y, z: GcodeCommand("M520", x=x if x else None, y=y if y else None, z=z if z else None))
	COMMAND_Homing_direction_M525 = staticmethod(lambda x, y, z: GcodeCommand("M525", x=x, y=y, z=z))
	COMMAND_Home_offset_M206_T0 = staticmethod(lambda s, t, x, y, z: GcodeCommand("M206", s=s, t=t, x=x, y=y, z=z))
	#COMMAND_Home_offset_M206_T1 = staticmethod(lambda x, y, z: GcodeCommand("M206", x=x if x else None, y=y if y else None, z=z if z else None))
	
	COMMAND_Axis_invert_M510 = staticmethod(lambda x, y, z, e: GcodeCommand("M510", x=x, y=y, z=z, e=e))
	COMMAND_Stepper_current_M906 = staticmethod(lambda x, y, z, e, b: GcodeCommand("M906", x=x if x else None, y=y if y else None, z=z if z else None, e=e if e else None, b=b if b else None))
	COMMAND_Stepper_mircostep_M909 = staticmethod(lambda x, y, z, e, b: GcodeCommand("M909", x=x if x else None, y=y if y else None, z=z if z else None, e=e if e else None, b=b if b else None))
	COMMAND_Endstop_invert_M526 = staticmethod(lambda x, y, z: GcodeCommand("M526", x=x, y=y, z=z))
	COMMAND_Minimum_endstop_input_M523 = staticmethod(lambda x, y, z: GcodeCommand("M523", x=x , y=y , z=z))
	COMMAND_Maximum_endstop_input_M524 = staticmethod(lambda x, y, z: GcodeCommand("M524", x=x, y=y, z=z))
	COMMAND_Use_software_endstop_M522 = staticmethod(lambda i, a: GcodeCommand("M522", i=i, a=a))
	COMMAND_Retract_length_M207 = staticmethod(lambda s, f, z: GcodeCommand("M207", s=s if s else None, f=f if f else None, z=z if z else None))
	COMMAND_Retract_recover_length_M208 = staticmethod(lambda s, f: GcodeCommand("M208", s=s if s else None, f=f if f else None))
	COMMAND_Maximum_feedrates_M203 = staticmethod(lambda x, y, z, e: GcodeCommand("M203", x=x if x else None, y=y if y else None, z=z if z else None, e=e if e else None))
	COMMAND_Homing_feedrate_M210 = staticmethod(lambda x, y, z, e: GcodeCommand("M210", x=x if x else None, y=y if y else None, z=z if z else None, e=e if e else None))
	COMMAND_Maximum_acceleration_M201 = staticmethod(lambda x, y, z, e: GcodeCommand("M201", x=x if x else None, y=y if y else None, z=z if z else None, e=e if e else None))
	COMMAND_Acceleration_M204 = staticmethod(lambda s, t: GcodeCommand("M204", s=s if s else None, t=t if t else None))
	COMMAND_Advanced_variables_M205 = staticmethod(lambda s, t, x, z, e: GcodeCommand("M205", s=s if s else None, t=t if t else None, x=x if x else None, z=z if z else None, e=e if e else None))
	COMMAND_TEMPETURE_PID_M301 = staticmethod(lambda t, p, i, d, s, b, w: GcodeCommand("M301", t=t, p=p, i=i, d=d, s=s, b=b, w=w))
	COMMAND_DELTA_ARGS_M665 = staticmethod(lambda l, r, s, z: GcodeCommand("M665", l=l, r=r, s=s, z=z))
	COMMAND_MACHINE_TYPE_M913 = staticmethod(lambda s: GcodeCommand("M913", s=s))
	COMMAND_DYNAMIC_CURRENT_M911 = staticmethod(lambda s: GcodeCommand("M911", s=s))
	COMMAND_BBP1_EXTENT_INTERFACE_M916 = staticmethod(lambda s,t: GcodeCommand("M916", s=s, t=t))
	
	
	default = dict(
		id = "_default",
		name = "Default",
		model = "Generic RepRap Printer",
		color = "default",
		volume=dict(
			width = 200,
			depth = 200,
			height = 200,
			formFactor = BedTypes.RECTANGULAR,
		),
		heatedBed = True,
	        dynamicCurrent = False,
	        machineType = MachineType.XYZ,
	        pids = dict(
	                t0  = dict(p=10.0, i=0.5, d=0.0, limit=10.0, factor=0.033, offset=40.0),
	                t1  = dict(p=10.0, i=0.5, d=0.0, limit=10.0, factor=0.033, offset=40.0),
	                bed = dict(p=10.0, i=0.5, d=0.0, limit=10.0, factor=0.033, offset=40.0),
	                ),
	        delta_args = dict(
	                diagonal_rod = 250.0,  
	                print_radius = 175.0,
	                z_home_pos  = 33.0,
	                segments_per_second = 18.0,                
	                ),
	        extendInterface = 1, 
	        thermocouple = 3,	        
		extruder=dict(
			count = 1,
			offsets = [
				dict(x=0.0, y=0.0,z=0.0)
				#(0, 0, 0)
			],
			nozzleDiameter = 0.4
		),
		axes=dict(
			x = dict(speed=500, inverted=True),
			y = dict(speed=500, inverted=False),
			z = dict(speed=5, inverted=True),
			e = dict(speed=25, inverted=False)
		),
	        #lkj
	        cmdPrintStart=[
	            dict(cmd="M80"),	                
	            dict(cmd="G28 X0 Y0"),
	            dict(cmd="G28 Z0"),
	            dict(cmd="G1 Z15.0 F6000"),
	            dict(cmd="M140 S60.0"),
	            dict(cmd="M104 T0 S200.0"),
	            dict(cmd="M109 T0 S200.0"),
	            dict(cmd="M190 S60.0")
	          #  dict(cmd="G92 E0"),
	          #  dict(cmd="G1 F600 E64"),
	          #  dict(cmd="G92 E0")
	        ],
	        cmdPrintStop=[
	            #dict(cmd="G28 X0 Y0"),
	            dict(cmd="M84 S1")	            
	        ],
	        stepsPerUnit = dict(
	                x = 157.4804,
	                y = 157.4804,
	                z = 2133.33,
	                e = 304
	        ),	
	        homingDirection=dict(
	                x = False,
	                y = False,
	                z = False,
                ),	        
	        stepperCurrent = dict(    
	                x = 800,
	                y = 800,
	                z = 450,
	                t0 = 450,
	                t1 = 450,
	        ),
	        stepperMircostep = dict(
	                x = 32,
                        y = 32,
                        z = 32,
                        t0 = 32,
                        t1 = 32,	                        
	        ),
	        endstopInvert = dict(
	                x = False,
	                y = False,
	                z = False
	        ),
	        endstopMinimumInput = dict(
	                x = True,
	                y = True,
	                z = True,
	        ),
	        endstopMaxmumInput = dict(
	                x = True,
	                y = True,
	                z = True,	                        
	        ),
	        endstopUseSoftware  = dict(
	                minVal = False,
	                maxVal = True,
	        ),
	        retractLength = dict(
	                 length = 3,
	                 feedrate = 25,
	                 zlift = 0,
	        ),
	        retractRecoverLength = dict(
	                length = 2,
                        feedrate = 20,	                        
                ),	        
	        homingFeedrates = dict(
	                x = 3000,
	                y = 3000,
	                z = 120,
	                e = 0,
	        ),
	        accelerationMaximum = dict(
	                x = 9000,
	                y = 9000,
	                z = 100,
	                e = 10000,	                        
	        ),
	        accelerationMoveRetract = dict(
	                move = 4000,
	                retract= 3000,
	        ),
	        advancedVariables = dict(
	                minimumfeedrate = 0,
	                mintravelfeedrate = 0,
	                maxXYJerk = 100,
	                maxZJerk = 0.4,
	                maxEJerk = 5.0,
	        )	        
	)

	def __init__(self):
		self._current = None

		self._folder = settings().getBaseFolder("printerProfiles")

	def select(self, identifier):
		#lkj
		ret_select=False
		if identifier is None or not self.exists(identifier):
			self._current = self.get_default()
			#return False
			ret_select = False
		else:
			self._current = self.get(identifier)
			#return True
			ret_select = True
		print("lkj, select a profile !!!!")	
		self.sendPreferenctParameter(self._current)	
		self.getBeforeAndAfterPrintParameter(self._current)
		return ret_select
	

	def deselect(self):
		self._current = None

	def get_all(self):
		return self._load_all()

	def get(self, identifier):
		if identifier == "_default":
			return self._load_default()
		elif self.exists(identifier):
			return self._load_from_path(self._get_profile_path(identifier))
		else:
			return None

	def remove(self, identifier):
		if identifier == "_default":
			return False
		if self._current is not None and self._current["id"] == identifier:
			return False
		return self._remove_from_path(self._get_profile_path(identifier))


	def __send_all_update_epprom(self, profile):
		#print("__send_all_update_epprom, profile=%s" % repr(profile))
		cmds = []
		if "heatedBed" in profile:
			hasBed = 1
			hasBed = profile["heatedBed"]
			cmds.append(self.__class__.COMMAND_Has_bed_M908(hasBed))		
		if "stepsPerUnit" in profile:
			x = profile["stepsPerUnit"]["x"]
			y = profile["stepsPerUnit"]["y"]
			z = profile["stepsPerUnit"]["z"]
			e = profile["stepsPerUnit"]["e"]
			cmds.append(self.__class__.COMMAND_Steps_per_unit_M92(x,y,z,e))			
		if "volume" in profile:
			x = profile["volume"]["width"]
			y = profile["volume"]["depth"]
			z = profile["volume"]["height"]
			cmds.append(self.__class__.COMMAND_Maximum_area_unit_M520(x,y,z))
		'''
		if "homingDirection" in profile:
			x = profile["homingDirection"]["x"]
			y = profile["homingDirection"]["y"]
			z = profile["homingDirection"]["z"]
			cmds.append(self.__class__.COMMAND_Homing_direction_M525(x,y,z))
		'''
		
		if "extruder" in profile:
			offsets = profile["extruder"]["offsets"]
			#print("lkj offsets:%s" %(str(offsets)))			
			s = profile["extruder"]["count"]			
			t = 0
			#x,y,z = 0.0,0.0,0.0
			for index in range(s):
				x = offsets[index]["x"]
				y = offsets[index]["y"]
				z = offsets[index]["z"]
				#print("lkj x:%s, y:%s, z:%s" %(str(x),str(y),str(z)))
				cmds.append(self.__class__.COMMAND_Home_offset_M206_T0(s,t,x,y,z))
				t += 1				
			'''
			for offset in offsets:
				if "x" in offset and offset["x"] is not None:
					x = offset["x"]
					y = offset["y"]
					z = offset["z"]
					#print("lkj x:%s, y:%s, z:%s" %(str(x),str(y),str(z)))
					cmds.append(self.__class__.COMMAND_Home_offset_M206_T0(s,t,x,y,z))
					t += 1
			'''
			
		if "axes" in profile:
			x = profile["axes"]["x"]["inverted"]
			y = profile["axes"]["y"]["inverted"]
			z = profile["axes"]["z"]["inverted"]
			e = profile["axes"]["e"]["inverted"]
			cmds.append(self.__class__.COMMAND_Axis_invert_M510(x,y,z,e))	
			
			speed_x = profile["axes"]["x"]["speed"]
			speed_y = profile["axes"]["y"]["speed"]
			speed_z = profile["axes"]["z"]["speed"]
			speed_e = profile["axes"]["e"]["speed"]
			cmds.append(self.__class__.COMMAND_Maximum_feedrates_M203(speed_x,speed_y,speed_z,speed_e))			
		if "stepperCurrent" in profile:
			x = profile["stepperCurrent"]["x"]
			y = profile["stepperCurrent"]["y"]
			z = profile["stepperCurrent"]["z"]
			t0 = profile["stepperCurrent"]["t0"]
			t1 = profile["stepperCurrent"]["t1"]
			cmds.append(self.__class__.COMMAND_Stepper_current_M906(x,y,z,t0,t1))
		if "stepperMircostep" in profile:
			x = profile["stepperMircostep"]["x"]
			y = profile["stepperMircostep"]["y"]
			z = profile["stepperMircostep"]["z"]
			t0 = profile["stepperMircostep"]["t0"]
			t1 = profile["stepperMircostep"]["t1"]
			cmds.append(self.__class__.COMMAND_Stepper_mircostep_M909(x,y,z,t0,t1))
		'''
		if "endstopInvert" in profile:
			x = profile["endstopInvert"]["x"]
			y = profile["endstopInvert"]["y"]
			z = profile["endstopInvert"]["z"]
			cmds.append(self.__class__.COMMAND_Endstop_invert_M526(x,y,z))				
		if "endstopMinimumInput" in profile:
			x = profile["endstopMinimumInput"]["x"]
			y = profile["endstopMinimumInput"]["y"]
			z = profile["endstopMinimumInput"]["z"]
			cmds.append(self.__class__.COMMAND_Minimum_endstop_input_M523(x,y,z))			
		if "endstopMaxmumInput" in profile:
			x = profile["endstopMaxmumInput"]["x"]
			y = profile["endstopMaxmumInput"]["y"]
			z = profile["endstopMaxmumInput"]["z"]
			cmds.append(self.__class__.COMMAND_Maximum_endstop_input_M524(x,y,z))
		'''	
		if "endstopUseSoftware" in profile:
			minVal = profile["endstopUseSoftware"]["minVal"]
			maxVal = profile["endstopUseSoftware"]["maxVal"]
			cmds.append(self.__class__.COMMAND_Use_software_endstop_M522(minVal,maxVal))
		if "retractLength" in profile:
			length = profile["retractLength"]["length"]
			feedrate = profile["retractLength"]["feedrate"]
			zlift = profile["retractLength"]["zlift"]
			cmds.append(self.__class__.COMMAND_Retract_length_M207(length,feedrate,zlift))
		if "retractRecoverLength" in profile:
			length = profile["retractRecoverLength"]["length"]
			feedrate = profile["retractRecoverLength"]["feedrate"]
			cmds.append(self.__class__.COMMAND_Retract_recover_length_M208(length,feedrate))			
		if "homingFeedrates" in profile:
			x = profile["homingFeedrates"]["x"]
			y = profile["homingFeedrates"]["y"]
			z = profile["homingFeedrates"]["z"]
			e = profile["homingFeedrates"]["e"]
			cmds.append(self.__class__.COMMAND_Homing_feedrate_M210(x,y,z,e))
		if "accelerationMaximum" in profile:
			x = profile["accelerationMaximum"]["x"]
			y = profile["accelerationMaximum"]["y"]
			z = profile["accelerationMaximum"]["z"]
			e = profile["accelerationMaximum"]["e"]
			cmds.append(self.__class__.COMMAND_Maximum_acceleration_M201(x,y,z,e))
		if "accelerationMoveRetract" in profile:
			move = profile["accelerationMoveRetract"]["move"]
			retract = profile["accelerationMoveRetract"]["retract"]
			cmds.append(self.__class__.COMMAND_Acceleration_M204(move,retract))
		if "advancedVariables" in profile:
			minimumfeedrate = profile["advancedVariables"]["minimumfeedrate"]
			mintravelfeedrate = profile["advancedVariables"]["mintravelfeedrate"]
			maxXYJerk = profile["advancedVariables"]["maxXYJerk"]
			maxZJerk = profile["advancedVariables"]["maxZJerk"]
			maxEJerk = profile["advancedVariables"]["maxEJerk"]
			cmds.append(self.__class__.COMMAND_Advanced_variables_M205(minimumfeedrate, mintravelfeedrate,maxXYJerk,maxZJerk,maxEJerk))						

		if "dynamicCurrent" in profile:				
			dynamicCurrent = profile["dynamicCurrent"]
			cmds.append(self.__class__.COMMAND_DYNAMIC_CURRENT_M911(dynamicCurrent))	
			
		if "extendInterface" in profile:				
			extendInterface = profile["extendInterface"]
			thermocouple = profile["thermocouple"]
			
			cmds.append(self.__class__.COMMAND_BBP1_EXTENT_INTERFACE_M916(extendInterface, thermocouple))	
			
		if "machineType" in profile:
			machineType = profile["machineType"]
			m_type_val={"XYZ":0, "Delta":1, "CoreXY":2}
			print("machine Type:%d" % m_type_val[machineType])
			cmds.append(self.__class__.COMMAND_MACHINE_TYPE_M913(m_type_val[machineType]))
	
		if "delta_args" in profile:
			diagonal_rod = profile["delta_args"]["diagonal_rod"]
			print_radius = profile["delta_args"]["print_radius"]
			segments_per_second = profile["delta_args"]["segments_per_second"]
			z_home_pos = profile["delta_args"]["z_home_pos"]
			cmds.append(self.__class__.COMMAND_DELTA_ARGS_M665(diagonal_rod, print_radius, segments_per_second, z_home_pos))						

		if "pids" in profile:
			pids = []
			pid0 = profile["pids"]["t0"]
			pid1 = profile["pids"]["t1"]
			pidbed = profile["pids"]["bed"]
			pids.append(pid0)
			pids.append(pid1)
			pids.append(pidbed)
			print("pidbed:%s" %(str(pids)))
			t = 0
			for pid in pids:
				p,i,d,factor,offset,limit = pid["p"],pid["i"],pid["d"],pid["factor"],pid["offset"],pid["limit"]
				cmds.append(self.__class__.COMMAND_TEMPETURE_PID_M301(t,p,i,d,factor,offset,limit))
				t += 1

		cmds.append(self.__class__.COMMAND_Finish_sending_M910)
		
		#for cmd in cmds:
		#	print("cmd:%s" % str(cmd))
		return cmds
		
	
	def save(self, profile, allow_overwrite=False, make_default=False):		
		if "id" in profile:
			identifier = profile["id"]
		elif "name" in profile:
			identifier = profile["name"]
		else:
			raise ValueError("profile must contain either id or name")

		identifier = self._sanitize(identifier)
		profile["id"] = identifier
		profile = dict_clean(profile, self.__class__.default)
		print("lkj save identifier:%s" % str(identifier))
		#lkj 
		'''from octoprint.server import printer
		if printer.isOperational():
			cmds = self.__send_all_update_epprom(profile)
			printer.commands(cmds)
			cmd_eeprom = GcodeCommand("M500")
			printer.command(cmd_eeprom)			
			pass
		print("lkj save 2")
		'''
		self.sendPreferenctParameter(profile)
		self.saveToEEPROM()
		self.getBeforeAndAfterPrintParameter(profile)
		
		if identifier == "_default":
			default_profile = dict_merge(self._load_default(), profile)
			settings().set(["printerProfiles", "defaultProfile"], default_profile, defaults=dict(printerProfiles=dict(defaultProfile=self.__class__.default)))
			settings().save()
		else:
			self._save_to_path(self._get_profile_path(identifier), profile, allow_overwrite=allow_overwrite)

			if make_default:
				settings().set(["printerProfiles", "default"], identifier)
		
		if self._current is not None and self._current["id"] == identifier:
			self.select(identifier)
		return self.get(identifier)
	
	#lkj 
	def sendPreferenctParameter(self, inProfile):		
		from octoprint.server import printer
		if printer.isOperational():
			cmds = self.__send_all_update_epprom(inProfile)
			printer.commands(cmds)
			#cmd_eeprom = GcodeCommand("M500")
			#printer.command(cmd_eeprom)				
		print("lkj sendPreferenctParameter")	
		''''''
		return
	
	def saveToEEPROM(self):		
		from octoprint.server import printer
		if printer.isOperational():
			cmd_eeprom = GcodeCommand("M500")
			printer.command(cmd_eeprom)				
		
	def getBeforeAndAfterPrintParameter(self, inProfile):		
		from octoprint.server import printer
		if "cmdPrintStart" in inProfile:
			cmds = inProfile["cmdPrintStart"]
			gcode_cmds = []
			print("lkj cmdPrintStart cmds:%s" %(str(cmds)))
			for cmd in cmds:
				str_cmd = cmd["cmd"]
				gcode_cmd = GcodeCommand.from_line(str_cmd)
				print("lkj cmdPrintStart gcode_cmd:%s" %(str(gcode_cmd)))
				gcode_cmds.append(gcode_cmd)	
			printer.setCmdBeforePrint(gcode_cmds)
		if "cmdPrintStop" in inProfile:
			cmds = inProfile["cmdPrintStop"]
			gcode_cmds = []
			print("lkj cmdPrintStop cmds:%s" %(str(cmds)))
			for cmd in cmds:
				str_cmd = cmd["cmd"]
				gcode_cmd = GcodeCommand.from_line(str_cmd)
				print("lkj cmdPrintStop gcode_cmd:%s" %(str(gcode_cmd)))
				gcode_cmds.append(gcode_cmd)	
			printer.setCmdAfterPrint(gcode_cmds)
		
		print("lkj getBeforeAndAfterPrintParameter")	
			
	def get_default(self):
		default = settings().get(["printerProfiles", "default"])
		if default is not None and self.exists(default):
			profile = self.get(default)
			if profile is not None:
				return profile

		return self._load_default()

	def set_default(self, identifier):
		all_identifiers = self._load_all_identifiers().keys()
		if identifier is not None and not identifier in all_identifiers:
			return

		settings().set(["printerProfile", "default"], identifier)
		settings().save()

	def get_current_or_default(self):
		if self._current is not None:
			return self._current
		else:
			return self.get_default()

	def get_current(self):
		return self._current

	def exists(self, identifier):
		if identifier is None:
			return False
		elif identifier == "_default":
			return True
		else:
			path = self._get_profile_path(identifier)
			return os.path.exists(path) and os.path.isfile(path)

	def _load_all(self):
		all_identifiers = self._load_all_identifiers()
		results = dict()
		for identifier, path in all_identifiers.items():
			if identifier == "_default":
				profile = self._load_default()
			else:
				profile = self._load_from_path(path)

			if profile is None:
				continue

			results[identifier] = dict_merge(self._load_default(), profile)
		return results

	def _load_all_identifiers(self):
		results = dict(_default=None)
		for entry in os.listdir(self._folder):
			if entry.startswith(".") or not entry.endswith(".profile") or entry == "_default.profile":
				continue

			path = os.path.join(self._folder, entry)
			if not os.path.isfile(path):
				continue

			identifier = entry[:-len(".profile")]
			results[identifier] = path
		return results

	def _load_from_path(self, path):
		if not os.path.exists(path) or not os.path.isfile(path):
			return None

		import yaml
		with open(path) as f:
			profile = yaml.safe_load(f)
		return profile

	def _save_to_path(self, path, profile, allow_overwrite=False):
		if os.path.exists(path) and not allow_overwrite:
			raise SaveError("Profile %s already exists and not allowed to overwrite" % profile["id"])

		import yaml
		with open(path, "wb") as f:
			try:
				yaml.safe_dump(profile, f, default_flow_style=False, indent="  ", allow_unicode=True)
			except Exception as e:
				raise SaveError("Cannot save profile %s: %s" % (profile["id"], e.message))

	def _remove_from_path(self, path):
		try:
			os.remove(path)
			return True
		except:
			return False

	def _load_default(self):
		default_profile = settings().get(["printerProfiles", "defaultProfile"])
		return dict_merge(copy.deepcopy(self.__class__.default), default_profile)

	def _get_profile_path(self, identifier):
		return os.path.join(self._folder, "%s.profile" % identifier)

	def _sanitize(self, name):
		if name is None:
			return None

		if "/" in name or "\\" in name:
			raise ValueError("name must not contain / or \\")

		import string
		valid_chars = "-_.() {ascii}{digits}".format(ascii=string.ascii_letters, digits=string.digits)
		sanitized_name = ''.join(c for c in name if c in valid_chars)
		sanitized_name = sanitized_name.replace(" ", "_")
		return sanitized_name

