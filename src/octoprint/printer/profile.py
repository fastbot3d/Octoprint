# coding=utf-8
from __future__ import absolute_import

__author__ = "Gina Häußge <osd@foosel.net>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'
__copyright__ = "Copyright (C) 2014 The OctoPrint Project - Released under terms of the AGPLv3 License"


import os
import copy
import re
import logging

from octoprint.settings import settings
from octoprint.util import dict_merge, dict_sanitize, dict_contains_keys, is_hidden_path

class SaveError(Exception):
	pass

class CouldNotOverwriteError(SaveError):
	pass

class InvalidProfileError(Exception):
	pass

class BedTypes(object):
	RECTANGULAR = "rectangular"
	CIRCULAR = "circular"

	@classmethod
	def values(cls):
		return [getattr(cls, name) for name in cls.__dict__ if not name.startswith("__")]

class BedOrigin(object):
	LOWERLEFT = "lowerleft"
	CENTER = "center"

	@classmethod
	def values(cls):
		return [getattr(cls, name) for name in cls.__dict__ if not name.startswith("__")]

class MachineType(object):
	XYZ = "XYZ"
	Delta = "Delta"
	CoreXY = "CoreXY"
	
class PrinterProfileManager(object):
	"""
	Manager for printer profiles. Offers methods to select the globally used printer profile and to list, add, remove,
	load and save printer profiles.

	A printer profile is a ``dict`` of the following structure:

	.. list-table::
	   :widths: 15 5 10 30
	   :header-rows: 1

	   * - Name
	     - Type
	     - Description
	   * - ``id``
	     - ``string``
	     - Internal id of the printer profile
	   * - ``name``
	     - ``string``
	     - Human readable name of the printer profile
	   * - ``model``
	     - ``string``
	     - Printer model
	   * - ``color``
	     - ``string``
	     - Color to associate with the printer profile
	   * - ``volume``
	     - ``dict``
	     - Information about the print volume
	   * - ``volume.width``
	     - ``float``
	     - Width of the print volume (X axis)
	   * - ``volume.depth``
	     - ``float``
	     - Depth of the print volume (Y axis)
	   * - ``volume.height``
	     - ``float``
	     - Height of the print volume (Z axis)
	   * - ``volume.formFactor``
	     - ``string``
	     - Form factor of the print bed, either ``rectangular`` or ``circular``
	   * - ``volume.origin``
	     - ``string``
	     - Location of gcode origin in the print volume, either ``lowerleft`` or ``center``
	   * - ``heatedBed``
	     - ``bool``
	     - Whether the printer has a heated bed (``True``) or not (``False``)
	   * - ``extruder``
	     - ``dict``
	     - Information about the printer's extruders
	   * - ``extruder.count``
	     - ``int``
	     - How many extruders the printer has (default 1)
	   * - ``extruder.offsets``
	     - ``list`` of ``tuple``s
	     - Extruder offsets relative to first extruder, list of (x, y) tuples, first is always (0,0)
	   * - ``extruder.nozzleDiameter``
	     - ``float``
	     - Diameter of the printer nozzle
	   * - ``axes``
	     - ``dict``
	     - Information about the printer axes
	   * - ``axes.x``
	     - ``dict``
	     - Information about the printer's X axis
	   * - ``axes.x.speed``
	     - ``float``
	     - Speed of the X axis in mm/s
	   * - ``axes.x.inverted``
	     - ``bool``
	     - Whether a positive value change moves the nozzle away from the print bed's origin (False, default) or towards it (True)
	   * - ``axes.y``
	     - ``dict``
	     - Information about the printer's Y axis
	   * - ``axes.y.speed``
	     - ``float``
	     - Speed of the Y axis in mm/s
	   * - ``axes.y.inverted``
	     - ``bool``
	     - Whether a positive value change moves the nozzle away from the print bed's origin (False, default) or towards it (True)
	   * - ``axes.z``
	     - ``dict``
	     - Information about the printer's Z axis
	   * - ``axes.z.speed``
	     - ``float``
	     - Speed of the Z axis in mm/s
	   * - ``axes.z.inverted``
	     - ``bool``
	     - Whether a positive value change moves the nozzle away from the print bed (False, default) or towards it (True)
	   * - ``axes.e``
	     - ``dict``
	     - Information about the printer's E axis
	   * - ``axes.e.speed``
	     - ``float``
	     - Speed of the E axis in mm/s
	   * - ``axes.e.inverted``
	     - ``bool``
	     - Whether a positive value change extrudes (False, default) or retracts (True) filament
	"""

	#(repr(s),repr(a), repr(l), repr(x),repr(y),repr(z), repr(b), repr(i), repr(e), repr(r), repr(p), repr(w)))
	
	COMMAND_MACHINE_TYPE_M913 = staticmethod(lambda s, a, l, x, y, z, b, i, e, r, p, w, d: "M913 S%f A%f L%f X%f Y%f Z%f B%f I%f E%f R%f P%f W%f D%f" % \
	                                        (s, a, l, x, y, z, b, i, e, r, p, w, d))	
	COMMAND_Maximum_area_unit_M520 = staticmethod(lambda x, y, z: "M520 X%f Y%f Z%f" %(x,y,z))
	COMMAND_Has_bed_M908 = staticmethod(lambda s, r, g: "M908 S%f R%f G%f" % (s, r, g))
	COMMAND_Finish_sending_M910 = "M910"
	COMMAND_Axis_invert_M510 = staticmethod(lambda x, y, z, e: "M510 X%f Y%f Z%f E%f" %(x,y,z,e))
	COMMAND_Maximum_feedrates_M203 = staticmethod(lambda x, y, z, e: "M203 X%f Y%f Z%f E%f" %(x,y,z,e))	
	COMMAND_Acceleration_M204 = staticmethod(lambda s, f: "M204 S%f F%f " %(s, f) )
	#COMMAND_DELTA_ARGS_M665 = staticmethod(lambda l, r, s, z: "M665 L%f R%f S%f Z%f" % (l, r, s, z))
	COMMAND_DELTA_ARGS_M666 = staticmethod(lambda d, r, s, h, a, b, c, i, j, k, p, x, y, z: "M666 D%f R%f S%f H%f A%f B%f C%f I%f J%f K%f P%f X%f Y%f Z%f" % (d, r, s, h, a,b,c,i,j,k,p,x,y,z))
	#COMMAND_SERVO_ANGLE_M914 = staticmethod(lambda s,e : "M914 S%f E%f" %(s,e))
	COMMAND_SERVO_ANGLE_M914 = staticmethod(lambda s,e,a,b,c,d,x,f,g,h,i,j,k,l: "M914 S%f E%f A%f B%f C%f D%f X%f F%f G%f H%f I%f J%f K%f L%f" %(s,e,a,b,c,d,x,f,g,h,i,j,k,l))		
	COMMAND_TEMPETURE_PID_M301 = staticmethod(lambda t, p, i, d, s, b, w: "M301 T%f P%f I%f D%f S%f B%f W%f" % \
	                                                (t, p, i, d, s, b, w))
	COMMAND_Steps_per_unit_M92 = staticmethod(lambda x, y, z, e, a, b: "M92 X%f Y%f Z%f E%f A%f B%f" % (x, y, z, e, a, b))
	COMMAND_Stepper_current_M906 = staticmethod(lambda x, y, z, e, b, w, u: "M906 X%f Y%f Z%f E%f B%f W%f U%f" % (x, y, z, e, b, w, u))
	COMMAND_Stepper_mircostep_M909 = staticmethod(lambda x, y, z, e, b, w: "M909 X%f Y%f Z%f E%f B%f W%f"% (x, y, z, e, b, w))
	COMMAND_Home_offset_M206_T0 = staticmethod(lambda s, t, x, y, z: "M206 S%f T%f X%f Y%f Z%f "% (s, t, x, y, z))
	COMMAND_Retract_length_M207 = staticmethod(lambda s, f, z: "M207 S%f F%f Z%f" %(s, f, z) )
	COMMAND_Retract_recover_length_M208 = staticmethod(lambda s, f: "M208 S%f F%f" %(s,f) )
	COMMAND_Homing_feedrate_M210 = staticmethod(lambda x, y, z, e: "M210 X%f Y%f Z%f E%f" % (x, y, z, e) )
	COMMAND_Maximum_acceleration_M201 = staticmethod(lambda x, y, z, e: "M201 X%f Y%f Z%f E%f" % (x, y, z, e) )
	COMMAND_Advanced_variables_M205 = staticmethod(lambda s, f, x, z, e: "M205 S%f F%f X%f Z%f E%f" % (s, f, x, z, e) )
	COMMAND_DYNAMIC_CURRENT_M911 = staticmethod(lambda s: "M911 S%f" % s)
	COMMAND_BBP1_EXTENT_INTERFACE_M916 = staticmethod(lambda s,t, w, l, r, x, y, z: "M916 S%f T%f W%f L%f R%f X%f Y%f Z%f" %(s,t, w, l, r, x, y, z))
	
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
			origin = BedOrigin.LOWERLEFT
		),
		heatedBed = False,
		extruder=dict(
			count = 1,
			offsets = [
				(0, 0)
			],
			nozzleDiameter = 0.4
		),
		axes=dict(
			x = dict(speed=500, inverted=True),
			y = dict(speed=500, inverted=False),
			z = dict(speed=5, inverted=True),
			e = dict(speed=25, inverted=False)
		),
	        machineType = MachineType.XYZ,
	        delta_args = dict(
	                diagonal_rod = 250.0, 
	                print_radius = 175.0,
	                print_available_radius = 100.0,
	                z_home_pos  = 33.0,
	                segments_per_second = 200.0,
	        ),	        
	        maxHeatPwmHotend = 80, 
                maxHeatPwmBed = 40,
	        
	        maxDangerousThermistor = 280, 
		maxDangerousThermocouple	= 1100, 
	        extendInterface = 1, 
                thermocouple_max6675 = 3,	        
                thermocouple_ad597 = 0,	
	        measure_ext1 = 1,
	        measure_ext2 = 2,
	        measure_ext3 = 3,
	        
	        dynamicCurrent = False,
	        autoLeveling = False,
	        endstop_angles_extend = 40,
	        endstop_angles_retract = 0,
	        zRaiseBeforeProbing = 70,
	        zRaiseBetweenProbing = 5,
	        probeDevice = "Servo",
	        endstop_offset = dict(
	                x = -25,
	                y = -29,
	                z = -12.35,
	                ),		        
	        probe_grid = dict(
	                left = 15,
	                right = 100,	                
	                front = 20,
	                back = 100,	                
	                point = 5,
	                ),
	        delta_tower = dict(
	                a = 0,
	                b = 0,	                
	                c = 0,
	                i = 0,	                
	                j = 0,
	                k = 0,
	                ),
	        delta_endstop = dict(
	                x = 0,
	                y = 0,	                
	                z = 0,	                
	                ),	        
	        delta_deploy_retract = dict(
	                deployStart = dict(x=20.0, y=96, z=30),
	                deployEnd =   dict(x=5.0, y=96, z=30.0),	                
	                retractStart = dict(x=49, y=84, z=20.0),
	                retractEnd =   dict(x=49, y=84, z=1.0),   
	                ),
	        pids = dict(
	                t0  = dict(p=10.0, i=0.5, d=0.0),
	                t1  = dict(p=10.0, i=0.5, d=0.0),
	                t2  = dict(p=10.0, i=0.5, d=0.0),
	                bed = dict(p=10.0, i=0.5, d=0.0),
	                ),
	        stepsPerUnit = dict(
	                x = 157.4804,
	                y = 157.4804,
	                z = 2133.33,
	                e0 = 304,
	                e1 = 304,
	                e2 = 304,
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
	                t2 = 450,
	                u = 450,
	                ),
	        stepperMircostep = dict(
	                x = 32,
	                y = 32,
	                z = 32,
	                t0 = 32,
	                t1 = 32,
	                t2 = 32,
	                ),
	        retractLength = dict(
	                length = 3,
	                feedrate = 45,
	                zlift = 0,
	                ),
	        retractRecoverLength = dict(
	                length = 0,
	                feedrate = 8,	                        
	                ),	        
	        homingFeedrates = dict(
	                x = 3000,
	                y = 3000,
	                z = 200,
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
	                minimumfeedrate = 1,
	                mintravelfeedrate = 1,
	                maxXYJerk = 60,
	                maxZJerk = 10,
	                maxEJerk = 10,
	        )	        	        
	)

	def __init__(self):
		self._current = None
		self._folder = settings().getBaseFolder("printerProfiles")
		self._logger = logging.getLogger(__name__)

	def select(self, identifier):
		if identifier is None or not self.exists(identifier):
			self._current = self.get_default()
			return False
		else:
			self._current = self.get(identifier)
			return True

	def deselect(self):
		self._current = None

	def get_all(self):
		return self._load_all()

	def get(self, identifier):
		try:
			if identifier == "_default":
				return self._load_default()
			elif self.exists(identifier):
				return self._load_from_path(self._get_profile_path(identifier))
			else:
				return None
		except InvalidProfileError:
			return None

	def remove(self, identifier):
		if identifier == "_default":
			return False
		if self._current is not None and self._current["id"] == identifier:
			return False
		return self._remove_from_path(self._get_profile_path(identifier))
	
	#lkj start 
	def __send_all_update_epprom(self, profile):
		print("__send_all_update_epprom, profile=%s" % repr(profile))
		cmds = []
		
		if "machineType" in profile:
			machineType = profile["machineType"]
			m_type_val={"XYZ":0, "Delta":1, "CoreXY":2}
			probeDeviceType = "Servo"
			probeDeviceTypeVal={"Proximity":0, "Servo":1, "MinZPin":2,  "FSR":3}			
			autoLeveling = False
			endstop_offset_x = -25
			endstop_offset_y = -29
			endstop_offset_z = -12.35
			zRaiseBeforeProbing = 70
			zRaiseBetweenProbing = 5
			left = 15
			right = 100
			front = 20
			back  = 100
			point = 2			
		
			print("machine Type:%d" % m_type_val[machineType])
			if "autoLeveling" in profile:
				autoLeveling = float(profile["autoLeveling"])					
				if "probeDevice" in profile:
					probeDeviceType = profile["probeDevice"]
					print("probeDeviceType:%d" % probeDeviceTypeVal[probeDeviceType])					
				endstop_offset_x = float(profile["endstop_offset"]["x"])
				endstop_offset_y = float(profile["endstop_offset"]["y"])
				endstop_offset_z = float(profile["endstop_offset"]["z"])				
				zRaiseBeforeProbing = float(profile["zRaiseBeforeProbing"])
				zRaiseBetweenProbing = float(profile["zRaiseBetweenProbing"])
				'''
							probe_point_1_x = profile["probe_point_1"]["x"]
							probe_point_1_y = profile["probe_point_1"]["y"]
							probe_point_2_x = profile["probe_point_2"]["x"]
							probe_point_2_y = profile["probe_point_2"]["y"]				
							probe_point_3_x = profile["probe_point_3"]["x"]
							probe_point_3_y = profile["probe_point_3"]["y"]	
							'''
				left = float(profile["probe_grid"]["left"])				
				right = float(profile["probe_grid"]["right"])				
				front = float(profile["probe_grid"]["front"])				
				back = float(profile["probe_grid"]["back"])				
				point = float(profile["probe_grid"]["point"])				
			cmds.append(self.__class__.COMMAND_MACHINE_TYPE_M913(m_type_val[machineType], 
						                             autoLeveling, probeDeviceTypeVal[probeDeviceType],
						                             endstop_offset_x,endstop_offset_y,endstop_offset_z,zRaiseBeforeProbing,          
						                             left, right, front, back, point, zRaiseBetweenProbing))
			
		print("lkj x1")
		if "delta_args" in profile:
			diagonal_rod = 0.1
			print_radius = 0.1 
			print_available_radius = 0.1
			segments_per_second = 0.1
			z_home_pos =  0.1
			diagonal_rod = float(profile["delta_args"]["diagonal_rod"])
			print_radius = float(profile["delta_args"]["print_radius"])
			print_available_radius = float(profile["delta_args"]["print_available_radius"])
			segments_per_second = float(profile["delta_args"]["segments_per_second"])
			z_home_pos = float(profile["delta_args"]["z_home_pos"])			
			delta_a = float(profile["delta_tower"]["a"])
			delta_b = float(profile["delta_tower"]["b"])
			delta_c = float(profile["delta_tower"]["c"])
			delta_i = float(profile["delta_tower"]["i"])
			delta_j = float(profile["delta_tower"]["j"])
			delta_k = float(profile["delta_tower"]["k"])
			
			endstop_x = float(profile["delta_endstop"]["x"])
			endstop_y = float(profile["delta_endstop"]["y"])
			endstop_z = float(profile["delta_endstop"]["z"])
			#cmds.append(self.__class__.COMMAND_DELTA_ARGS_M665(diagonal_rod, print_radius, segments_per_second, z_home_pos))	
			cmds.append(self.__class__.COMMAND_DELTA_ARGS_M666(diagonal_rod, print_radius, segments_per_second, z_home_pos, 
			                                                   delta_a, delta_b, delta_c, delta_i, delta_j, delta_k, print_available_radius, \
			                                                   endstop_x, endstop_y, endstop_z))		
		print("lkj x2")
		if "volume" in profile:
			x = float(profile["volume"]["width"])
			y = float(profile["volume"]["depth"])
			z = float(profile["volume"]["height"])
			cmds.append(self.__class__.COMMAND_Maximum_area_unit_M520(x,y,z))	
		print("lkj x3")	
		if "heatedBed" in profile:
			hasBed = 1
			maxDangerousThermistor = 280
			maxDangerousThermocouple = 1100
			
			hasBed = float(profile["heatedBed"])			
			if "maxDangerousThermistor" in profile:
				maxDangerousThermistor = float(profile["maxDangerousThermistor"])	
			if "maxDangerousThermocouple" in profile:
				maxDangerousThermocouple = float(profile["maxDangerousThermocouple"])			
			cmds.append(self.__class__.COMMAND_Has_bed_M908(hasBed, maxDangerousThermistor, maxDangerousThermocouple))	
		print("lkj x4")
		if "axes" in profile:
			x = float(profile["axes"]["x"]["inverted"])
			y = float(profile["axes"]["y"]["inverted"])
			z = float(profile["axes"]["z"]["inverted"])
			e = float(profile["axes"]["e"]["inverted"])
			cmds.append(self.__class__.COMMAND_Axis_invert_M510(x,y,z,e))	
		
			speed_x = float(profile["axes"]["x"]["speed"])
			speed_y = float(profile["axes"]["y"]["speed"])
			speed_z = float(profile["axes"]["z"]["speed"])
			speed_e = float(profile["axes"]["e"]["speed"])
			cmds.append(self.__class__.COMMAND_Maximum_feedrates_M203(speed_x,speed_y,speed_z,speed_e))				
		
		if "extruder" in profile:
			offsets = profile["extruder"]["offsets"]
			#print("lkj offsets:%s" %(str(offsets)))			
			s = profile["extruder"]["count"]			
			t = 0
			#x,y,z = 0.0,0.0,0.0
			for offset in offsets:				
				x = offset[0]
				y = offset[1]
				z = 0
				print("lkj x:%s, y:%s, z:%s" %(str(x),str(y),str(z)))
				cmds.append(self.__class__.COMMAND_Home_offset_M206_T0(s,t,x,y,z))
				t += 1				
		''' '''	
		
		print("lkj 0");
		if "stepsPerUnit" in profile:
			x = float(profile["stepsPerUnit"]["x"])
			y = float(profile["stepsPerUnit"]["y"])
			z = float(profile["stepsPerUnit"]["z"])
			e = float(profile["stepsPerUnit"]["e0"])
			e1 = float(profile["stepsPerUnit"]["e1"])
			e2 = float(profile["stepsPerUnit"]["e2"])
			cmds.append(self.__class__.COMMAND_Steps_per_unit_M92(x,y,z,e,e1,e2))			
		print("lkj 1");
		if "stepperCurrent" in profile:
			x = float(profile["stepperCurrent"]["x"])
			y = float(profile["stepperCurrent"]["y"])
			z = float(profile["stepperCurrent"]["z"])
			t0 = float(profile["stepperCurrent"]["t0"])
			t1 = float(profile["stepperCurrent"]["t1"])
			t2 = float(profile["stepperCurrent"]["t2"])
			u = float(profile["stepperCurrent"]["u"])
			cmds.append(self.__class__.COMMAND_Stepper_current_M906(x,y,z,t0,t1,t2,u))
		print("lkj 2");	
		if "stepperMircostep" in profile:
			x = float(profile["stepperMircostep"]["x"])
			y = float(profile["stepperMircostep"]["y"])
			z = float(profile["stepperMircostep"]["z"])
			t0 = float(profile["stepperMircostep"]["t0"])
			t1 = float(profile["stepperMircostep"]["t1"])
			t2 = float(profile["stepperMircostep"]["t2"])
			cmds.append(self.__class__.COMMAND_Stepper_mircostep_M909(x,y,z,t0,t1,t2))
			'''
			if "homingDirection" in profile:
				x = profile["homingDirection"]["x"]
				y = profile["homingDirection"]["y"]
				z = profile["homingDirection"]["z"]
				cmds.append(self.__class__.COMMAND_Homing_direction_M525(x,y,z))

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
	
			if "endstopUseSoftware" in profile:
				minVal = profile["endstopUseSoftware"]["minVal"]
				maxVal = profile["endstopUseSoftware"]["maxVal"]
				cmds.append(self.__class__.COMMAND_Use_software_endstop_M522(minVal,maxVal))
			'''
		print("lkj 3");	
		if "retractLength" in profile:
			length = float(profile["retractLength"]["length"])
			feedrate = float(profile["retractLength"]["feedrate"])
			zlift = float(profile["retractLength"]["zlift"])
			cmds.append(self.__class__.COMMAND_Retract_length_M207(length,feedrate,zlift))
		print("lkj 4");	
		if "retractRecoverLength" in profile:
			length = float(profile["retractRecoverLength"]["length"])
			feedrate = float(profile["retractRecoverLength"]["feedrate"])
			cmds.append(self.__class__.COMMAND_Retract_recover_length_M208(length,feedrate))			
		print("lkj 5");	
		if "homingFeedrates" in profile:
			x = float(profile["homingFeedrates"]["x"])
			y = float(profile["homingFeedrates"]["y"])
			z = float(profile["homingFeedrates"]["z"])
			e = float(profile["homingFeedrates"]["e"])
			cmds.append(self.__class__.COMMAND_Homing_feedrate_M210(x,y,z,e))
		print("lkj 6");	
		if "accelerationMaximum" in profile:
			x = float(profile["accelerationMaximum"]["x"])
			y = float(profile["accelerationMaximum"]["y"])
			z = float(profile["accelerationMaximum"]["z"])
			e = float(profile["accelerationMaximum"]["e"])
			cmds.append(self.__class__.COMMAND_Maximum_acceleration_M201(x,y,z,e))
		print("lkj 7");	
		if "accelerationMoveRetract" in profile:
			move = float(profile["accelerationMoveRetract"]["move"])
			retract = float(profile["accelerationMoveRetract"]["retract"])
			cmds.append(self.__class__.COMMAND_Acceleration_M204(move,retract))
		print("lkj 8");	
		if "advancedVariables" in profile:
			minimumfeedrate = float(profile["advancedVariables"]["minimumfeedrate"])
			mintravelfeedrate = float(profile["advancedVariables"]["mintravelfeedrate"])
			maxXYJerk = float(profile["advancedVariables"]["maxXYJerk"])
			maxZJerk = float(profile["advancedVariables"]["maxZJerk"])
			maxEJerk = float(profile["advancedVariables"]["maxEJerk"])
			cmds.append(self.__class__.COMMAND_Advanced_variables_M205(minimumfeedrate, mintravelfeedrate,maxXYJerk,maxZJerk,maxEJerk))						
		print("lkj 9");	
		if "dynamicCurrent" in profile:				
			dynamicCurrent = float(profile["dynamicCurrent"])
			cmds.append(self.__class__.COMMAND_DYNAMIC_CURRENT_M911(dynamicCurrent))	
		print("lkj 10");	
		if "extendInterface" in profile:				
			extendInterface = float(profile["extendInterface"])
			thermocouple_max6675 = 0
			thermocouple_ad597 = 0		
			if "thermocouple_max6675" in profile:				
				thermocouple_max6675 = float(profile["thermocouple_max6675"])
			if "thermocouple_ad597" in profile:				
				thermocouple_ad597 = float(profile["thermocouple_ad597"])				
	
			max_heat_pwm_hotend = float(profile["maxHeatPwmHotend"])
			max_heat_pwm_bed = float(profile["maxHeatPwmBed"]	  )	
			
			measure_ext1 = 1
			measure_ext2 = 2
			measure_ext3 = 3
			if "measure_ext1" in profile:				
				measure_ext1 = float(profile["measure_ext1"])
				measure_ext2 = float(profile["measure_ext2"])
				measure_ext3 = float(profile["measure_ext3"])			
			cmds.append(self.__class__.COMMAND_BBP1_EXTENT_INTERFACE_M916(extendInterface, thermocouple_max6675, thermocouple_ad597, max_heat_pwm_hotend, max_heat_pwm_bed
			                        ,measure_ext1, measure_ext2, measure_ext3))
		print("lkj 11");	
		if "endstop_angles_extend" in profile:
			endstop_angles_extend = float(profile["endstop_angles_extend"])
			endstop_angles_retract = float(profile["endstop_angles_retract"])
			
			deployStart = profile["delta_deploy_retract"]["deployStart"]
			deployEnd = profile["delta_deploy_retract"]["deployEnd"]
			retractStart = profile["delta_deploy_retract"]["retractStart"]
			retractEnd = profile["delta_deploy_retract"]["retractEnd"]
					
			#cmds.append(self.__class__.COMMAND_SERVO_ANGLE_M914(endstop_angles_extend, endstop_angles_retract))			
			cmds.append(self.__class__.COMMAND_SERVO_ANGLE_M914(endstop_angles_extend, endstop_angles_retract
			                                                    ,float(deployStart['x']), float(deployStart['y']), float(deployStart['z']) 
			                                                    ,float(deployEnd['x']), float(deployEnd['y']), float(deployEnd['z'])
			                                                    ,float(retractStart['x']), float(retractStart['y']), float(retractStart['z'])
			                                                    ,float(retractEnd['x']), float(retractEnd['y']),float(retractEnd['z'])
			                                                    ))		
		print("lkj 12");
		if "pids" in profile:
			pids = []
			pid0 = profile["pids"]["t0"]
			pid1 = profile["pids"]["t1"]
			pid2 = profile["pids"]["t2"]
			pidbed = profile["pids"]["bed"]
			pids.append(pid0)
			pids.append(pid1)
			pids.append(pid2)
			pids.append(pidbed)
			print("pidbed:%s" %(str(pids)))
			t = 0
			for pid in pids:
				p,i,d,factor,offset,limit = float(pid["p"]),float(pid["i"]),float(pid["d"]), 0, 0, 0
				cmds.append(self.__class__.COMMAND_TEMPETURE_PID_M301(t,p,i,d,0, 0,0))
				t += 1
				
		cmds.append(self.__class__.COMMAND_Finish_sending_M910)
		print("lkj get cmds=%s" % repr(cmds))

		return cmds		

	def sendPreferenctParameter(self, inProfile):		
		from octoprint.server import printer
		if printer.is_operational():
			cmds = self.__send_all_update_epprom(inProfile)
			printer.commands(cmds)
			#cmd_eeprom = GcodeCommand("M500")
			#printer.command(cmd_eeprom)				
		print("lkj sendPreferenctParameter")	
		''''''
		return
	
	def saveToEEPROM(self):		
		from octoprint.server import printer
		if printer.is_operational():
			#cmd_eeprom = GcodeCommand("M500")
			cmd_eeprom = []
			cmd_eeprom.append("M500")
			printer.commands(cmd_eeprom)
	#lkj end 
	
	def save(self, profile, allow_overwrite=False, make_default=False):
		if "id" in profile:
			identifier = profile["id"]
		elif "name" in profile:
			identifier = profile["name"]
		else:
			raise InvalidProfileError("profile must contain either id or name")

		identifier = self._sanitize(identifier)
		profile["id"] = identifier
		profile = dict_sanitize(profile, self.__class__.default)

		if identifier == "_default":
			default_profile = dict_merge(self._load_default(), profile)
			if not self._ensure_valid_profile(default_profile):
				raise InvalidProfileError()

			settings().set(["printerProfiles", "defaultProfile"], default_profile, defaults=dict(printerProfiles=dict(defaultProfile=self.__class__.default)))
			settings().save()
		else:
			self._save_to_path(self._get_profile_path(identifier), profile, allow_overwrite=allow_overwrite)

			if make_default:
				settings().set(["printerProfiles", "default"], identifier)
				
		print("lkj save 2")
		self.sendPreferenctParameter(profile)
		print("lkj save 3")
		self.saveToEEPROM()				
		print("lkj save 4")
		if self._current is not None and self._current["id"] == identifier:
			self.select(identifier)
		return self.get(identifier)

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
			try:
				if identifier == "_default":
					profile = self._load_default()
				else:
					profile = self._load_from_path(path)
			except InvalidProfileError:
				continue

			if profile is None:
				continue

			results[identifier] = dict_merge(self._load_default(), profile)
		return results

	def _load_all_identifiers(self):
		results = dict(_default=None)
		for entry in os.listdir(self._folder):
			if is_hidden_path(entry) or not entry.endswith(".profile") or entry == "_default.profile":
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

		if self._migrate_profile(profile):
			try:
				self._save_to_path(path, profile, allow_overwrite=True)
			except:
				self._logger.exception("Tried to save profile to {path} after migrating it while loading, ran into exception".format(path=path))

		profile = self._ensure_valid_profile(profile)

		if not profile:
			self._logger.warn("Invalid profile: %s" % path)
			raise InvalidProfileError()
		return profile

	def _save_to_path(self, path, profile, allow_overwrite=False):
		validated_profile = self._ensure_valid_profile(profile)
		if not validated_profile:
			raise InvalidProfileError()

		if os.path.exists(path) and not allow_overwrite:
			raise SaveError("Profile %s already exists and not allowed to overwrite" % profile["id"])

		from octoprint.util import atomic_write
		import yaml
		try:
			with atomic_write(path, "wb") as f:
				yaml.safe_dump(profile, f, default_flow_style=False, indent="  ", allow_unicode=True)
		except Exception as e:
			self._logger.exception("Error while trying to save profile %s" % profile["id"])
			raise SaveError("Cannot save profile %s: %s" % (profile["id"], str(e)))

	def _remove_from_path(self, path):
		try:
			os.remove(path)
			return True
		except:
			return False

	def _load_default(self):
		default_overrides = settings().get(["printerProfiles", "defaultProfile"])
		profile = self._ensure_valid_profile(dict_merge(copy.deepcopy(self.__class__.default), default_overrides))
		if not profile:
			self._logger.warn("Invalid default profile after applying overrides")
			return copy.deepcopy(self.__class__.default)
		return profile

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

	def _migrate_profile(self, profile):
		# make sure profile format is up to date
		ret = False
		
		if "measure_ext1" not in profile:  #lkj
			profile["measure_ext1"] = "1"
			profile["measure_ext2"] = "2"
			profile["measure_ext3"] = "3"	
			ret = True
			
		
					
		if "volume" in profile and "formFactor" in profile["volume"] and not "origin" in profile["volume"]:
			profile["volume"]["origin"] = BedOrigin.CENTER if profile["volume"]["formFactor"] == BedTypes.CIRCULAR else BedOrigin.LOWERLEFT
			ret = True
			#return True
			
		if "volume" in profile:  #lkj
			if "formFactor" in  profile["volume"] and "origin" in  profile["volume"] and "machineType" in profile:
				if "Delta" in profile["machineType"]:
					profile["volume"]["formFactor"] = "circular"
					profile["volume"]["origin"] = "center"	
					ret = True
		return ret

	def _ensure_valid_profile(self, profile):
		# ensure all keys are present
		if not dict_contains_keys(self.default, profile):
			self._logger.warn("Profile invalid, missing keys. Expected: {expected!r}. Actual: {actual!r}".format(expected=self.default.keys(), actual=profile.keys()))
			return False

		# conversion helper
		def convert_value(profile, path, converter):
			value = profile
			for part in path[:-1]:
				if not isinstance(value, dict) or not part in value:
					raise RuntimeError("%s is not contained in profile" % ".".join(path))
				value = value[part]

			if not isinstance(value, dict) or not path[-1] in value:
				raise RuntimeError("%s is not contained in profile" % ".".join(path))

			value[path[-1]] = converter(value[path[-1]])

		# convert ints
		for path in (("extruder", "count"), ("axes", "x", "speed"), ("axes", "y", "speed"), ("axes", "z", "speed")):
			try:
				convert_value(profile, path, int)
			except Exception as e:
				self._logger.warn("Profile has invalid value for path {path!r}: {msg}".format(path=".".join(path), msg=str(e)))
				return False

		# convert floats
		for path in (("volume", "width"), ("volume", "depth"), ("volume", "height"), ("extruder", "nozzleDiameter")):
			try:
				convert_value(profile, path, float)
			except Exception as e:
				self._logger.warn("Profile has invalid value for path {path!r}: {msg}".format(path=".".join(path), msg=str(e)))
				return False

		# convert booleans
		for path in (("axes", "x", "inverted"), ("axes", "y", "inverted"), ("axes", "z", "inverted")):
			try:
				convert_value(profile, path, bool)
			except Exception as e:
				self._logger.warn("Profile has invalid value for path {path!r}: {msg}".format(path=".".join(path), msg=str(e)))
				return False

		# validate form factor
		if not profile["volume"]["formFactor"] in BedTypes.values():
			self._logger.warn("Profile has invalid value volume.formFactor: {formFactor}".format(formFactor=profile["volume"]["formFactor"]))
			return False

		# validate origin type
		if not profile["volume"]["origin"] in BedOrigin.values():
			self._logger.warn("Profile has invalid value in volume.origin: {origin}".format(origin=profile["volume"]["origin"]))
			return False

		# ensure origin and form factor combination is legal
		if profile["volume"]["formFactor"] == BedTypes.CIRCULAR and not profile["volume"]["origin"] == BedOrigin.CENTER:
			profile["volume"]["origin"] = BedOrigin.CENTER

		# validate offsets
		offsets = []
		for offset in profile["extruder"]["offsets"]:
			if not len(offset) == 2:
				self._logger.warn("Profile has an invalid extruder.offsets entry: {entry!r}".format(entry=offset))
				return False
			x_offset, y_offset = offset
			try:
				offsets.append((float(x_offset), float(y_offset)))
			except:
				self._logger.warn("Profile has an extruder.offsets entry with non-float values: {entry!r}".format(entry=offset))
				return False
		profile["extruder"]["offsets"] = offsets

		return profile

