$(function() {
    function PrinterProfilesViewModel() {
        var self = this;

        self._cleanProfile = function() {
            return {
                id: "",
                name: "",
                model: "",
                color: "default",
                volume: {
                    formFactor: "rectangular",
                    width: 200,
                    depth: 200,
                    height: 200,
                    origin: "lowerleft"
                },
                heatedBed: false,
                axes: {
                    x: {speed: 500, inverted: false},
                    y: {speed: 500, inverted: false},
                    z: {speed: 5, inverted: false},
                    e: {speed: 25, inverted: false}
                },
                extruder: {
                    count: 1,
                    offsets: [
                        [0,0]
                    ],
                    nozzleDiameter: 0.4
                },
                //lkj start 
                machineType: "XYZ",
                delta_args: {
                    diagonal_rod: 250.0,  
                    print_radius: 175.0,
                    z_home_pos: 33.0,
                    segments_per_second: 200.0,
		    print_available_radius: 100,
                },
                maxHeatPwmHotend:80,
                maxHeatPwmBed:40,
		
	        maxDangerousThermistor:280,
	        maxDangerousThermocouple:1100,
		
                extendInterface: 1,            
                thermocouple_max6675: 3,
                thermocouple_ad597: 0,
		measure_ext1:1,
		measure_ext2:2,
		measure_ext3:3,
		
                dynamicCurrent: false,
                autoLeveling: false,
                endstop_angles_extend: 40,
                endstop_angles_retract: 0,
                endstop_offset: {x: -25,y: -29,z: -12.35, },	
                zRaiseBeforeProbing: 70,
	        zRaiseBetweenProbing: 5,
                probe_point_1: {x: 15,y: 100,},	        
                probe_point_2: {x: 15,y: 20,   },	
                probe_point_3: {x: 100, y: 20,  },	    
                probe_grid: {left: 15,
                            right: 100,	                
                            front: 20,
                            back:100,	                
                            point:2, },
                probeDevice: "Servo",
		delta_tower: {
			a: 0,
			b: 0,
			c: 0,
			i: 0,
			j: 0,
			k: 0,
		},
		delta_endstop: {
			x: 0,
			y: 0,
			z: 0,			
		},
                delta_deploy_retract: {
                        deployStart: {x:20.0, y:96, z:30.0},
                        deployEnd:   {x:5.0, y:96, z:30.0},
		        retractStart: {x:49.0, y:84, z:20.0},
                        retractEnd:    {x:49, y:84, z:1.0},
                },
		pids: {
			t0: {p:10.0, i:0.5, d:0.0, limit:10.0, factor:0.033, offset:40.0},
			t1: {p:10.0, i:0.5, d:0.0, limit:10.0, factor:0.033, offset:40.0},
		       t2: {p:10.0, i:0.5, d:0.0, limit:10.0, factor:0.033, offset:40.0},
			bed:{p:10.0, i:0.5, d:0.0, limit:10.0, factor:0.033, offset:40.0},
		},
                stepsPerUnit:{
                    x:157.4804,
                    y:157.4804,
                    z:2133.33,
                    e0:304,
		    e1:304,
		    e2:304
                },
                homingDirection:{
                    x: false,
                    y: false,
                    z: false
                },
                stepperCurrent:{    
                    x:  800,
                    y:  800,
                    z:  450,
                    t0: 450,
		    t1: 450,
		    t2: 450,
		    u: 450,
                },
                stepperMircostep:{
                    x: 32,
                    y: 32,
                    z: 32,
                    t0: 32,
		    t1: 32,
		    t2: 32,
                },
                retractLength:{
                      length: 3,
                      feedrate: 45,
                      zlift: 0
                },
                retractRecoverLength:{
                      length:0,
                      feedrate:8
                },	        
                homingFeedrates:{
                        x: 3000,
                        y: 3000,
                        z: 200,
                        e: 0
                },
                accelerationMaximum:{
                        x: 9000,
                        y: 9000,
                        z: 100,
                        e: 10000	                        
                },
                accelerationMoveRetract:{
                        move: 4000,
                        retract: 3000
                },
                advancedVariables:{
                        minimumfeedrate: 1,
                        mintravelfeedrate: 1,
                        maxXYJerk: 60,
                        maxZJerk: 10,
                        maxEJerk: 10
                }
                //lkj end
            }
        };

        self.requestInProgress = ko.observable(false);

        self.profiles = new ItemListHelper(
            "printerProfiles",
            {
                "name": function(a, b) {
                    // sorts ascending
                    if (a["name"].toLocaleLowerCase() < b["name"].toLocaleLowerCase()) return -1;
                    if (a["name"].toLocaleLowerCase() > b["name"].toLocaleLowerCase()) return 1;
                    return 0;
                }
            },
            {},
            "name",
            [],
            [],
            10
        );
        self.defaultProfile = ko.observable();
        self.currentProfile = ko.observable();

        self.currentProfileData = ko.observable(ko.mapping.fromJS(self._cleanProfile()));

        self.editorNew = ko.observable(false);

        self.editorName = ko.observable();
        self.editorColor = ko.observable();
        self.editorIdentifier = ko.observable();
        self.editorIdentifierPlaceholder = ko.observable();
        self.editorModel = ko.observable();

        self.editorVolumeWidth = ko.observable();
        self.editorVolumeDepth = ko.observable();
        self.editorVolumeHeight = ko.observable();
        self.editorVolumeFormFactor = ko.observable();
        self.editorVolumeOrigin = ko.observable();

        self.editorVolumeFormFactor.subscribe(function(value) {
            if (value == "circular") {
                self.editorVolumeOrigin("center");
            }
        });

        self.editorHeatedBed = ko.observable();

        self.editorNozzleDiameter = ko.observable();
        self.editorExtruders = ko.observable();
        self.editorExtruderOffsets = ko.observableArray();

        self.editorAxisXSpeed = ko.observable();
        self.editorAxisYSpeed = ko.observable();
        self.editorAxisZSpeed = ko.observable();
        self.editorAxisESpeed = ko.observable();

        self.editorAxisXInverted = ko.observable(false);
        self.editorAxisYInverted = ko.observable(false);
        self.editorAxisZInverted = ko.observable(false);
        self.editorAxisEInverted = ko.observable(false);
        
        //lkj start
        self.editorMachineType = ko.observable();	
	self.editorMachineType.subscribe(function(value) {
	    if (value == "Delta") {
		self.editorVolumeFormFactor("circular");
		self.editorVolumeOrigin("center");
	    } else {
		self.editorVolumeFormFactor("rectangular");
		self.editorVolumeOrigin("lowerleft");
	    }
	});	
	
        self.isVisibleDeltaForm = function() {
            var a = self.editorMachineType();
               if(a == "Delta"){
                 return true;
               }
               return false;
        };
	self.isVisibleDeltaDeployRetract = function() {
	    var a = self.editorProbeDevice();
	       if(a == "MinZPin"){
		 return true;
	       }
	       return false;
	};
	
	self.isVisibleDeviceOffset = function() {
	    var a = self.editorProbeDevice();
	       if(a == "FSR"){
		 return false;
	       }
	       return true;
	};
	
	
	self.isVisibleProximity = function() {
	    var machineType = self.editorMachineType();
	    var a = self.editorProbeDevice();
	       if( (a == "Proximity" || a == "Servo")  && machineType != "Delta"){
		 return true;
	       }
	       return false;
	};
	
	self.isVisibleAutoLevelingForm = function() {
	   return self.editorAutoLeveling();
	}; 
	
	self.isVisibleServoEnable = function() {
	       var machineType = self.editorMachineType();
	       var a = self.editorProbeDevice();
	       if(a == "Servo" && machineType != "Delta"){
		 return true;
	       }
	       return false;
	};
	    
        self.editordelta_diagonal_rod = ko.observable();
        self.editordelta_print_radius = ko.observable();
        self.editordelta_z_home_pos = ko.observable();
        self.editordelta_segments_per_second = ko.observable();
	self.editordelta_print_available_radius = ko.observable();
        
        self.editorExtendInterface = ko.observable();
        self.editorThermocoupleMax6675 = ko.observable();
        self.editorThermocoupleAd597 = ko.observable();
	
	self.editorMeasureExt1 = ko.observable();
	self.editorMeasureExt2 = ko.observable();
	self.editorMeasureExt3 = ko.observable();
    
        self.editorMaxHeatPwmHotend = ko.observable();
        self.editorMaxHeatPwmBed = ko.observable();
	
        self.editorMaxDangerousThermistor = ko.observable();
        self.editorMaxDangerousThermocouple = ko.observable();
        
        self.editorStepsPerUnitX = ko.observable();
        self.editorStepsPerUnitY = ko.observable();
        self.editorStepsPerUnitZ = ko.observable();
        self.editorStepsPerUnitE0 = ko.observable();
	self.editorStepsPerUnitE1 = ko.observable();
	self.editorStepsPerUnitE2 = ko.observable();
        
        self.editorHomingDirectionX = ko.observable();
        self.editorHomingDirectionY = ko.observable();
        self.editorHomingDirectionZ = ko.observable();
        
        self.editorStepperCurrentX = ko.observable();
        self.editorStepperCurrentY = ko.observable();
        self.editorStepperCurrentZ = ko.observable();
        self.editorStepperCurrentT0 = ko.observable();
	self.editorStepperCurrentT1 = ko.observable();
	self.editorStepperCurrentT2 = ko.observable();
	self.editorStepperCurrentUSR = ko.observable();
    
        self.editorStepperMircostepX = ko.observable();
        self.editorStepperMircostepY = ko.observable();
        self.editorStepperMircostepZ = ko.observable();
        self.editorStepperMircostepT0 = ko.observable();
	self.editorStepperMircostepT1 = ko.observable();
	self.editorStepperMircostepT2 = ko.observable();
        
        self.editorRetractLengthLen = ko.observable();
        self.editorRetractLengthFeedrate = ko.observable();
        self.editorRetractLengthZlift = ko.observable();
    
        self.editorRetractRecoverLength = ko.observable();
        self.editorRetractRecoverfeedrate = ko.observable();
        
        self.editorHomingFeedratesX = ko.observable();
        self.editorHomingFeedratesY = ko.observable();
        self.editorHomingFeedratesZ = ko.observable();
        self.editorHomingFeedratesE = ko.observable();
        
        self.editorAccelerationMaximumX = ko.observable();
        self.editorAccelerationMaximumY = ko.observable();
        self.editorAccelerationMaximumZ = ko.observable();
        self.editorAccelerationMaximumE = ko.observable();
    
        self.editorAccelerationMoveRetractMove = ko.observable();
        self.editorAccelerationMoveRetractRetract = ko.observable();
    
        self.editorAdvancedVariablesMinimumfeedrate = ko.observable();
        self.editorAdvancedVariablesMintravelfeedrate = ko.observable();
        self.editorAdvancedVariablesMaxXYJerk = ko.observable();
        self.editorAdvancedVariablesMaxZJerk = ko.observable();
        self.editorAdvancedVariablesMaxEJerk = ko.observable();
        
        self.editorProbeDevice = ko.observable();
        
        self.editorDynamicCurrent = ko.observable();
        self.editorAutoLeveling = ko.observable();

        self.editorEndstopAnglesExtend = ko.observable();
        self.editorEndstopAnglesRetract = ko.observable();
        self.editorZRaiseBeforeProbing = ko.observable();
	self.editorZRaiseBetweenProbing = ko.observable();	
        self.editorEndstopOffsetX = ko.observable();
        self.editorEndstopOffsetY = ko.observable();
        self.editorEndstopOffsetZ = ko.observable();
    
        self.editorProbeGridLeft = ko.observable();   
        self.editorProbeGridRight = ko.observable();   
        self.editorProbeGridFront = ko.observable();   
        self.editorProbeGridBack = ko.observable();   
        self.editorProbeGridPoint = ko.observable();   
	
	self.editorDeltaEndstopX = ko.observable(); 
	self.editorDeltaEndstopY = ko.observable(); 
	self.editorDeltaEndstopZ = ko.observable(); 
	
	self.editorDeltaTowerA = ko.observable(); 
	self.editorDeltaTowerB = ko.observable(); 
	self.editorDeltaTowerC = ko.observable(); 
	self.editorDeltaTowerI = ko.observable(); 
	self.editorDeltaTowerJ = ko.observable(); 
	self.editorDeltaTowerK = ko.observable(); 	
            
        self.editorPidsT0P = ko.observable();
        self.editorPidsT0I = ko.observable();
        self.editorPidsT0D = ko.observable();
        self.editorPidsT1P = ko.observable();
        self.editorPidsT1I = ko.observable();
        self.editorPidsT1D = ko.observable(); 
	self.editorPidsT2P = ko.observable();
	self.editorPidsT2I = ko.observable();
	self.editorPidsT2D = ko.observable(); 
        self.editorPidsBedP = ko.observable();
        self.editorPidsBedI = ko.observable();
        self.editorPidsBedD = ko.observable();
	
     self.editorDeltaDeployStartX = ko.observable();
     self.editorDeltaDeployStartY = ko.observable();
     self.editorDeltaDeployStartZ = ko.observable();     
     self.editorDeltaDeployEndX = ko.observable();
     self.editorDeltaDeployEndY = ko.observable();
     self.editorDeltaDeployEndZ = ko.observable();
     
     self.editorDeltaRetractStartX = ko.observable();
     self.editorDeltaRetractStartY = ko.observable();
     self.editorDeltaRetractStartZ = ko.observable();     
     self.editorDeltaRetractEndX = ko.observable();
     self.editorDeltaRetractEndY = ko.observable();
     self.editorDeltaRetractEndZ = ko.observable();
     
	    
	self.availableExtendInterface = ko.observable([
	    {key: "1", name: gettext("Dual Z")},
	    {key: "2", name: gettext("Dual Extruder")},
	]);
	self.availableThermocouple1Connection = ko.observable([
	    {key: "1", name: gettext("Ext1")},
	    {key: "2", name: gettext("Ext2")},
	    {key: "3", name: gettext("Ext3")},
	]);
	self.availableThermocouple2Connection = ko.observable([
	    {key: "0", name: gettext("None")},
	    {key: "1", name: gettext("Ext1")},
	    {key: "2", name: gettext("Ext2")},
	    {key: "3", name: gettext("Ext3")},
	]);
	self.availableMeasureTemperature = ko.observable([
	    {key: "1", name: gettext("THERMISTOR_1")},
	    {key: "2", name: gettext("THERMISTOR_2")},
	    {key: "3", name: gettext("EXT3_MAX6675")},
	    {key: "4", name: gettext("EXT4_AD597")},
	]);
	
	self.availableStepperMircoStep = ko.observable([
	    {key: "1", name: gettext("1")},
	    {key: "2", name: gettext("2")},
	    {key: "4", name: gettext("4")},
	    {key: "8", name: gettext("8")},
	    {key: "16", name: gettext("16")},
	    {key: "32", name: gettext("32")}
	]);
    
        //lkj end 
        
        self.availableColors = ko.observable([
            {key: "default", name: gettext("default")},
            {key: "red", name: gettext("red")},
            {key: "orange", name: gettext("orange")},
            {key: "yellow", name: gettext("yellow")},
            {key: "green", name: gettext("green")},
            {key: "blue", name: gettext("blue")},
            {key: "black", name: gettext("black")}
        ]);

        self.availableOrigins = ko.computed(function() {
            var formFactor = self.editorVolumeFormFactor();

            var possibleOrigins = {
                "lowerleft": gettext("Lower Left"),
                "center": gettext("Center")
            };

            var keys = [];
            if (formFactor == "rectangular") {
                keys = ["lowerleft", "center"];
            } else if (formFactor == "circular") {
                keys = ["center"];
            }

            var result = [];
            _.each(keys, function(key) {
               result.push({key: key, name: possibleOrigins[key]});
            });
            return result;
        });

        self.koEditorExtruderOffsets = ko.computed(function() {
            var extruderOffsets = self.editorExtruderOffsets();
            var numExtruders = self.editorExtruders();
            if (!numExtruders) {
                numExtruders = 1;
            }

            if (numExtruders - 1 > extruderOffsets.length) {
                for (var i = extruderOffsets.length; i < numExtruders; i++) {
                    extruderOffsets[i] = {
                        idx: i + 1,
                        x: ko.observable(0),
                        y: ko.observable(0)
                    }
                }
                self.editorExtruderOffsets(extruderOffsets);
            }

            return extruderOffsets.slice(0, numExtruders - 1);
        });

        self.editorNameInvalid = ko.computed(function() {
            return !self.editorName();
        });

        self.editorIdentifierInvalid = ko.computed(function() {
            var identifier = self.editorIdentifier();
            var placeholder = self.editorIdentifierPlaceholder();
            var data = identifier;
            if (!identifier) {
                data = placeholder;
            }

            var validCharacters = (data && (data == self._sanitize(data)));

            var existingProfile = self.profiles.getItem(function(item) {return item.id == data});
            return !data || !validCharacters || (self.editorNew() && existingProfile != undefined);
        });

        self.editorIdentifierInvalidText = ko.computed(function() {
            if (!self.editorIdentifierInvalid()) {
                return "";
            }

            if (!self.editorIdentifier() && !self.editorIdentifierPlaceholder()) {
                return gettext("Identifier must be set");
            } else if (self.editorIdentifier() != self._sanitize(self.editorIdentifier())) {
                return gettext("Invalid characters, only a-z, A-Z, 0-9, -, ., _, ( and ) are allowed")
            } else {
                return gettext("A profile with such an identifier already exists");
            }
        });

        self.enableEditorSubmitButton = ko.computed(function() {
            return !self.editorNameInvalid() && !self.editorIdentifierInvalid() && !self.requestInProgress();
        });

        self.editorName.subscribe(function() {
            self.editorIdentifierPlaceholder(self._sanitize(self.editorName()).toLowerCase());
        });

        self.makeDefault = function(data) {
            var profile = {
                id: data.id,
                default: true
            };

            self.updateProfile(profile);
        };

        self.requestData = function() {
            $.ajax({
                url: API_BASEURL + "printerprofiles",
                type: "GET",
                dataType: "json",
                success: self.fromResponse
            })
        };

        self.fromResponse = function(data) {
            var items = [];
            var defaultProfile = undefined;
            var currentProfile = undefined;
            var currentProfileData = undefined;
            _.each(data.profiles, function(entry) {
                if (entry.default) {
                    defaultProfile = entry.id;
                }
                if (entry.current) {
                    currentProfile = entry.id;
                    currentProfileData = ko.mapping.fromJS(entry, self.currentProfileData);
                }
                entry["isdefault"] = ko.observable(entry.default);
                entry["iscurrent"] = ko.observable(entry.current);
                items.push(entry);
            });
            self.profiles.updateItems(items);
            self.defaultProfile(defaultProfile);
            self.currentProfile(currentProfile);
            self.currentProfileData(currentProfileData);
        };

        self.addProfile = function(callback) {
            var profile = self._editorData();
            self.requestInProgress(true);
            $.ajax({
                url: API_BASEURL + "printerprofiles",
                type: "POST",
                dataType: "json",
                contentType: "application/json; charset=UTF-8",
                data: JSON.stringify({profile: profile}),
                success: function() {
                    self.requestInProgress(false);
                    if (callback !== undefined) {
                        callback();
                    }
                    self.requestData();
                },
                error: function() {
                    self.requestInProgress(false);
                    var text = gettext("There was unexpected error while saving the printer profile, please consult the logs.");
                    new PNotify({title: gettext("Saving failed"), text: text, type: "error", hide: false});
                }
            });
        };

        self.removeProfile = function(data) {
            self.requestInProgress(true);
            $.ajax({
                url: data.resource,
                type: "DELETE",
                dataType: "json",
                success: function() {
                    self.requestInProgress(false);
                    self.requestData();
                },
                error: function() {
                    self.requestInProgress(false);
                    var text = gettext("There was unexpected error while removing the printer profile, please consult the logs.");
                    new PNotify({title: gettext("Saving failed"), text: text, type: "error", hide: false});
                }
            })
        };

        self.updateProfile = function(profile, callback) {
            if (profile == undefined) {
                profile = self._editorData();
            }

            self.requestInProgress(true);

            $.ajax({
                url: API_BASEURL + "printerprofiles/" + profile.id,
                type: "PATCH",
                dataType: "json",
                contentType: "application/json; charset=UTF-8",
                data: JSON.stringify({profile: profile}),
                success: function() {
                    self.requestInProgress(false);
                    if (callback !== undefined) {
                        callback();
                    }
                    self.requestData();
                },
                error: function() {
                    self.requestInProgress(false);
                    var text = gettext("There was unexpected error while updating the printer profile, please consult the logs.");
                    new PNotify({title: gettext("Saving failed"), text: text, type: "error", hide: false});
                }
            });
        };

        self.showEditProfileDialog = function(data) {
            var add = false;
            if (data == undefined) {
                data = self._cleanProfile();
                add = true;
            }

            self.editorNew(add);

            self.editorIdentifier(data.id);
            self.editorName(data.name);
            self.editorColor(data.color);
            self.editorModel(data.model);

            self.editorVolumeWidth(data.volume.width);
            self.editorVolumeDepth(data.volume.depth);
            self.editorVolumeHeight(data.volume.height);
            self.editorVolumeFormFactor(data.volume.formFactor);
            self.editorVolumeOrigin(data.volume.origin);

            self.editorHeatedBed(data.heatedBed);

            self.editorNozzleDiameter(data.extruder.nozzleDiameter);
            self.editorExtruders(data.extruder.count);
            var offsets = [];
            if (data.extruder.count > 1) {
                _.each(_.slice(data.extruder.offsets, 1), function(offset, index) {
                    offsets.push({
                        idx: index + 1,
                        x: ko.observable(offset[0]),
                        y: ko.observable(offset[1])
                    });
                });
            }
            self.editorExtruderOffsets(offsets);

            self.editorAxisXSpeed(data.axes.x.speed);
            self.editorAxisXInverted(data.axes.x.inverted);
            self.editorAxisYSpeed(data.axes.y.speed);
            self.editorAxisYInverted(data.axes.y.inverted);
            self.editorAxisZSpeed(data.axes.z.speed);
            self.editorAxisZInverted(data.axes.z.inverted);
            self.editorAxisESpeed(data.axes.e.speed);
            self.editorAxisEInverted(data.axes.e.inverted);
            //lkj start 
            self.editorMachineType(data.machineType);            
            self.editordelta_diagonal_rod(data.delta_args.diagonal_rod);
            self.editordelta_print_radius(data.delta_args.print_radius);
            self.editordelta_z_home_pos(data.delta_args.z_home_pos);
            self.editordelta_segments_per_second(data.delta_args.segments_per_second);
	    self.editordelta_print_available_radius(data.delta_args.print_available_radius);
	    
            
	    self.editorMaxHeatPwmHotend(data.maxHeatPwmHotend);
	    self.editorMaxHeatPwmBed(data.maxHeatPwmBed);
	    
    	    self.editorMaxDangerousThermistor(data.maxDangerousThermistor);
	    self.editorMaxDangerousThermocouple(data.maxDangerousThermocouple);
	    
	    self.editorExtendInterface(data.extendInterface);
	    self.editorThermocoupleMax6675(data.thermocouple_max6675);
	    self.editorThermocoupleAd597(data.thermocouple_ad597);
	    
    	    self.editorMeasureExt1(data.measure_ext1);
	    self.editorMeasureExt2(data.measure_ext2);
    	    self.editorMeasureExt3(data.measure_ext3);
	    
	    self.editorStepsPerUnitX(data.stepsPerUnit.x);
	    self.editorStepsPerUnitY(data.stepsPerUnit.y);
	    self.editorStepsPerUnitZ(data.stepsPerUnit.z);
	    self.editorStepsPerUnitE0(data.stepsPerUnit.e0);
	    self.editorStepsPerUnitE1(data.stepsPerUnit.e1);
	    self.editorStepsPerUnitE2(data.stepsPerUnit.e2);
	    self.editorHomingDirectionX(data.homingDirection.x);
	    self.editorHomingDirectionY(data.homingDirection.y);
	    self.editorHomingDirectionZ(data.homingDirection.z);
	    
	    self.editorStepperCurrentX(data.stepperCurrent.x);
	    self.editorStepperCurrentY(data.stepperCurrent.y);
	    self.editorStepperCurrentZ(data.stepperCurrent.z);
	    self.editorStepperCurrentT0(data.stepperCurrent.t0);
	    self.editorStepperCurrentT1(data.stepperCurrent.t1);
	    self.editorStepperCurrentT2(data.stepperCurrent.t2);
	    self.editorStepperCurrentUSR(data.stepperCurrent.u);
    
	    self.editorStepperMircostepX(data.stepperMircostep.x);
	    self.editorStepperMircostepY(data.stepperMircostep.y);
	    self.editorStepperMircostepZ(data.stepperMircostep.z);
	    self.editorStepperMircostepT0(data.stepperMircostep.t0);
	    self.editorStepperMircostepT1(data.stepperMircostep.t1);
	    self.editorStepperMircostepT2(data.stepperMircostep.t2);
	    self.editorRetractLengthLen(data.retractLength.length);
	    self.editorRetractLengthFeedrate(data.retractLength.feedrate);
	    self.editorRetractLengthZlift(data.retractLength.zlift);
    
	    self.editorRetractRecoverLength(data.retractRecoverLength.length);
	    self.editorRetractRecoverfeedrate(data.retractRecoverLength.feedrate);
    
	    self.editorHomingFeedratesX(data.homingFeedrates.x);
	    self.editorHomingFeedratesY(data.homingFeedrates.y);
	    self.editorHomingFeedratesZ(data.homingFeedrates.z);
	    self.editorHomingFeedratesE(data.homingFeedrates.e);
    
	    self.editorAccelerationMaximumX(data.accelerationMaximum.x);
	    self.editorAccelerationMaximumY(data.accelerationMaximum.y);
	    self.editorAccelerationMaximumZ(data.accelerationMaximum.z);
	    self.editorAccelerationMaximumE(data.accelerationMaximum.e);
    
	    self.editorAccelerationMoveRetractMove(data.accelerationMoveRetract.move);
	    self.editorAccelerationMoveRetractRetract(data.accelerationMoveRetract.retract);
	    self.editorAdvancedVariablesMinimumfeedrate(data.advancedVariables.minimumfeedrate);
	    self.editorAdvancedVariablesMintravelfeedrate(data.advancedVariables.mintravelfeedrate);
	    self.editorAdvancedVariablesMaxXYJerk(data.advancedVariables.maxXYJerk);
	    self.editorAdvancedVariablesMaxZJerk(data.advancedVariables.maxZJerk);
	    self.editorAdvancedVariablesMaxEJerk(data.advancedVariables.maxEJerk);
	    
	    self.editorProbeDevice(data.probeDevice);
	    self.editorAutoLeveling(data.autoLeveling);
	    self.editorEndstopAnglesExtend(data.endstop_angles_extend);
	    self.editorEndstopAnglesRetract(data.endstop_angles_retract);
	    self.editorZRaiseBeforeProbing(data.zRaiseBeforeProbing);
	    self.editorZRaiseBetweenProbing(data.zRaiseBetweenProbing);
	    self.editorEndstopOffsetX(data.endstop_offset.x);
	    self.editorEndstopOffsetY(data.endstop_offset.y);
	    self.editorEndstopOffsetZ(data.endstop_offset.z);	    
	    self.editorProbeGridLeft(data.probe_grid.left);
	    self.editorProbeGridRight(data.probe_grid.right);
	    self.editorProbeGridFront(data.probe_grid.front);
	    self.editorProbeGridBack(data.probe_grid.back);
	    self.editorProbeGridPoint(data.probe_grid.point);
	    self.editorDynamicCurrent(data.dynamicCurrent);
	    
	    self.editorDeltaEndstopX(data.delta_endstop.x);
	    self.editorDeltaEndstopY(data.delta_endstop.y);
	    self.editorDeltaEndstopZ(data.delta_endstop.z);
	    
	    self.editorDeltaTowerA(data.delta_tower.a);
	    self.editorDeltaTowerB(data.delta_tower.b);
	    self.editorDeltaTowerC(data.delta_tower.c);
	    self.editorDeltaTowerI(data.delta_tower.i);
	    self.editorDeltaTowerJ(data.delta_tower.j);
	    self.editorDeltaTowerK(data.delta_tower.k);
	    

	    self.editorPidsT0P(data.pids.t0.p);
	    self.editorPidsT0I(data.pids.t0.i);
	    self.editorPidsT0D(data.pids.t0.d);	

	    self.editorPidsT1P(data.pids.t1.p);
	    self.editorPidsT1I(data.pids.t1.i);
	    self.editorPidsT1D(data.pids.t1.d);   
	    self.editorPidsT2P(data.pids.t2.p);
	    self.editorPidsT2I(data.pids.t2.i);
	    self.editorPidsT2D(data.pids.t2.d); 
	    self.editorPidsBedP(data.pids.bed.p);
	    self.editorPidsBedI(data.pids.bed.i);
	    self.editorPidsBedD(data.pids.bed.d);	
	    
	    self.editorDeltaDeployStartX(data.delta_deploy_retract.deployStart.x);
	    self.editorDeltaDeployStartY(data.delta_deploy_retract.deployStart.y);
	    self.editorDeltaDeployStartZ(data.delta_deploy_retract.deployStart.z);	    
	    self.editorDeltaDeployEndX(data.delta_deploy_retract.deployEnd.x);
	    self.editorDeltaDeployEndY(data.delta_deploy_retract.deployEnd.y);
	    self.editorDeltaDeployEndZ(data.delta_deploy_retract.deployEnd.z);
	    
	    self.editorDeltaRetractStartX(data.delta_deploy_retract.retractStart.x);
	    self.editorDeltaRetractStartY(data.delta_deploy_retract.retractStart.y);
	    self.editorDeltaRetractStartZ(data.delta_deploy_retract.retractStart.z);	    
	    self.editorDeltaRetractEndX(data.delta_deploy_retract.retractEnd.x);
	    self.editorDeltaRetractEndY(data.delta_deploy_retract.retractEnd.y);
	    self.editorDeltaRetractEndZ(data.delta_deploy_retract.retractEnd.z);
	    
           //lkj end 
            var editDialog = $("#settings_printerProfiles_editDialog");
            var confirmButton = $("button.btn-confirm", editDialog);
            var dialogTitle = $("h3.modal-title", editDialog);

            dialogTitle.text(add ? gettext("Add Printer Profile") : _.sprintf(gettext("Edit Printer Profile \"%(name)s\""), {name: data.name}));
            confirmButton.unbind("click");
            confirmButton.bind("click", function() {
                if (self.enableEditorSubmitButton()) {
                    self.confirmEditProfile(add);
                }
            });
            editDialog.modal("show");
        };

        self.confirmEditProfile = function(add) {
            var callback = function() {
                $("#settings_printerProfiles_editDialog").modal("hide");
            };

            if (add) {
                self.addProfile(callback);
            } else {
		if(self.editorThermocoupleAd597() == self.editorThermocoupleMax6675() && self.editorThermocoupleAd597() != 0){
		   alert("Error, Thermocouple1 equal Thermocouple2 !!!!")	    
		} else 
		    self.updateProfile(undefined, callback);
            }
        };

        self._editorData = function() {
            var identifier = self.editorIdentifier();
            if (!identifier) {
                identifier = self.editorIdentifierPlaceholder();
            }
            var profile = {
                id: identifier,
                name: self.editorName(),
                color: self.editorColor(),
                model: self.editorModel(),
                volume: {
                    width: parseFloat(self.editorVolumeWidth()),
                    depth: parseFloat(self.editorVolumeDepth()),
                    height: parseFloat(self.editorVolumeHeight()),
                    formFactor: self.editorVolumeFormFactor(),
                    origin: self.editorVolumeOrigin()
                },
                heatedBed: self.editorHeatedBed(),
                extruder: {
                    count: parseInt(self.editorExtruders()),
                    offsets: [
                        [0.0, 0.0]
                    ],
                    nozzleDiameter: parseFloat(self.editorNozzleDiameter())
                },
                axes: {
                    x: {
                        speed: parseInt(self.editorAxisXSpeed()),
                        inverted: self.editorAxisXInverted()
                    },
                    y: {
                        speed: parseInt(self.editorAxisYSpeed()),
                        inverted: self.editorAxisYInverted()
                    },
                    z: {
                        speed: parseInt(self.editorAxisZSpeed()),
                        inverted: self.editorAxisZInverted()
                    },
                    e: {
                        speed: parseInt(self.editorAxisESpeed()),
                        inverted: self.editorAxisEInverted()
                    }
                },
                machineType: self.editorMachineType(),
                delta_args: {
                    diagonal_rod: self.editordelta_diagonal_rod(),
                    print_radius: self.editordelta_print_radius(),
		    print_available_radius: self.editordelta_print_available_radius(),
                    z_home_pos: self.editordelta_z_home_pos(),
                    segments_per_second: self.editordelta_segments_per_second()
                },
		maxHeatPwmHotend: self.editorMaxHeatPwmHotend(),
		maxHeatPwmBed: self.editorMaxHeatPwmBed(),
		maxDangerousThermistor: self.editorMaxDangerousThermistor(),
		maxDangerousThermocouple: self.editorMaxDangerousThermocouple(), 
		extendInterface: self.editorExtendInterface(),
		thermocouple_ad597: self.editorThermocoupleAd597(),
		thermocouple_max6675: self.editorThermocoupleMax6675(),
		measure_ext1: self.editorMeasureExt1(),
		measure_ext2: self.editorMeasureExt2(),
		measure_ext3: self.editorMeasureExt3(),
		
		dynamicCurrent: self.editorDynamicCurrent(),
		probeDevice:  self.editorProbeDevice(),
		autoLeveling: self.editorAutoLeveling(),
		endstop_angles_extend: self.editorEndstopAnglesExtend(),
		endstop_angles_retract: self.editorEndstopAnglesRetract(),
		zRaiseBeforeProbing: self.editorZRaiseBeforeProbing(),
		zRaiseBetweenProbing: self.editorZRaiseBetweenProbing(),
		endstop_offset: {x: self.editorEndstopOffsetX(),
			       y: self.editorEndstopOffsetY(),
			       z: self.editorEndstopOffsetZ()
		},
		probe_grid: {
		    left:   self.editorProbeGridLeft(),
		    right:  self.editorProbeGridRight(),
		    front:  self.editorProbeGridFront(),
		    back:   self.editorProbeGridBack(),
		    point:  self.editorProbeGridPoint(),
		},
		delta_tower: {
		    a:  self.editorDeltaTowerA(),
		    b:  self.editorDeltaTowerB(),
		    c:  self.editorDeltaTowerC(),
		    i:  self.editorDeltaTowerI(),
		    j:  self.editorDeltaTowerJ(),
		    k:  self.editorDeltaTowerK(),
		},
		delta_endstop: {
		    x:  self.editorDeltaEndstopX(),
		    y:  self.editorDeltaEndstopY(),
		    z:  self.editorDeltaEndstopZ(),
		},
		delta_deploy_retract:{
		    deployStart:{
			x:self.editorDeltaDeployStartX(),
			y:self.editorDeltaDeployStartY(),
			z:self.editorDeltaDeployStartZ()
		    },
		    deployEnd:{
			x:self.editorDeltaDeployEndX(),
			y:self.editorDeltaDeployEndY(),
			z:self.editorDeltaDeployEndZ()
		    },
		    retractStart:{
			x:self.editorDeltaRetractStartX(),
			y:self.editorDeltaRetractStartY(),
			z:self.editorDeltaRetractStartZ()
		    },
		    retractEnd:{
			x:self.editorDeltaRetractEndX(),
			y:self.editorDeltaRetractEndY(),
			z:self.editorDeltaRetractEndZ()
		    }
		},
		pids:{
		    t0:{
			p:self.editorPidsT0P(),
			i:self.editorPidsT0I(),
			d:self.editorPidsT0D()
		    },
		    t1:{
			p:self.editorPidsT1P(),
			i:self.editorPidsT1I(),
			d:self.editorPidsT1D()
		    },
		    t2:{
			p:self.editorPidsT2P(),
			i:self.editorPidsT2I(),
			d:self.editorPidsT2D()
		    },
		    bed:{
			p:self.editorPidsBedP(),
			i:self.editorPidsBedI(),
			d:self.editorPidsBedD()
		    }
		},
		stepsPerUnit: {
		    x: self.editorStepsPerUnitX(),
		    y: self.editorStepsPerUnitY(),
		    z: self.editorStepsPerUnitZ(),
		    e0: self.editorStepsPerUnitE0(),
		    e1: self.editorStepsPerUnitE1(),
		    e2: self.editorStepsPerUnitE2()
		},
		homingDirection:{
		    x: self.editorHomingDirectionX(),
		    y: self.editorHomingDirectionY(),
		    z: self.editorHomingDirectionZ()
		},	    
		stepperCurrent:{    
		    x:  self.editorStepperCurrentX(),
		    y:  self.editorStepperCurrentY(),
		    z:  self.editorStepperCurrentZ(),
		    t0: self.editorStepperCurrentT0(),
		    t1: self.editorStepperCurrentT1(),
		    t2: self.editorStepperCurrentT2(),
		    u:  self.editorStepperCurrentUSR(),
		},
		stepperMircostep:{
		    x:  self.editorStepperMircostepX(),
		    y:  self.editorStepperMircostepY(),
		    z:  self.editorStepperMircostepZ(),
		    t0: self.editorStepperMircostepT0(),
		    t1: self.editorStepperMircostepT1(),
		    t2: self.editorStepperMircostepT2(),
		},
		retractLength:{
		      length:   self.editorRetractLengthLen(),
		      feedrate: self.editorRetractLengthFeedrate(),
		      zlift:    self.editorRetractLengthZlift()
		},
		retractRecoverLength:{
		      length:   self.editorRetractRecoverLength(),
		      feedrate: self.editorRetractRecoverfeedrate()	                        
		},	        
		homingFeedrates:{
			x: self.editorHomingFeedratesX(),
			y: self.editorHomingFeedratesY(),
			z: self.editorHomingFeedratesZ(),
			e: self.editorHomingFeedratesE()
		},
		accelerationMaximum:{
			x: self.editorAccelerationMaximumX(),
			y: self.editorAccelerationMaximumY(),
			z: self.editorAccelerationMaximumZ(),
			e: self.editorAccelerationMaximumE()	                        
		},
		accelerationMoveRetract:{
			move:    self.editorAccelerationMoveRetractMove(),
			retract: self.editorAccelerationMoveRetractRetract()
		},
		advancedVariables: {
			minimumfeedrate:   self.editorAdvancedVariablesMinimumfeedrate(),
			mintravelfeedrate: self.editorAdvancedVariablesMintravelfeedrate(),
			maxXYJerk:       self.editorAdvancedVariablesMaxXYJerk(),
			maxZJerk:        self.editorAdvancedVariablesMaxZJerk(),
			maxEJerk:        self.editorAdvancedVariablesMaxEJerk()
		},
            };
            if (self.editorExtruders() > 1) {
                for (var i = 0; i < self.editorExtruders() - 1; i++) {
                    var offset = [0.0, 0.0];
                    if (i < self.editorExtruderOffsets().length) {
                        try {
                            offset = [parseFloat(self.editorExtruderOffsets()[i]["x"]()), parseFloat(self.editorExtruderOffsets()[i]["y"]())];
                        } catch (exc) {
                            log.error("Invalid offset in profile", identifier, "for extruder", i+1, ":", self.editorExtruderOffsets()[i]["x"], ",", self.editorExtruderOffsets()[i]["y"]);
                        }
                    }
                    profile.extruder.offsets.push(offset);
                }
            }

            return profile;
        };

        self._sanitize = function(name) {
            return name.replace(/[^a-zA-Z0-9\-_\.\(\) ]/g, "").replace(/ /g, "_");
        };

        self.onSettingsShown = self.requestData;
        self.onStartup = self.requestData;
    }

    OCTOPRINT_VIEWMODELS.push([
        PrinterProfilesViewModel,
        [],
        []
    ]);
});
