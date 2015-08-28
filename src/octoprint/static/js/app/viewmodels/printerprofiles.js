function PrinterProfilesViewModel() {
    var self = this;    
    self._cleanProfile = function() {
        return {
            id: "",
            name: "",
            model: "",
            color: "default",	 
	    extendInterface: "1",
	    thermocouple:"3",
            //maxSpeed: 300,
            volume: {
                formFactor: "rectangular",
                width: 200,
                depth: 200,
                height: 200
            },
            heatedBed: false,
	    dynamicCurrent: false,
	    machineType: "XYZ",
	    pids: {
		    t0: {p:10.0, i:0.5, d:0.0, limit:10.0, factor:0.033, offset:40.0},
		    t1: {p:10.0, i:0.5, d:0.0, limit:10.0, factor:0.033, offset:40.0},
		    bed:{p:10.0, i:0.5, d:0.0, limit:10.0, factor:0.033, offset:40.0},
	    },
	    
	    delta_args: {
		    diagonal_rod: 250.0,  
		    print_radius: 175.0,
		    z_home_pos: 33.0,
		    segments_per_second: 18.0,
	    },	      
	    
            axes: {
                x: {speed: 500, inverted: false},
                y: {speed: 500, inverted: false},
                z: {speed: 5, inverted: false},
                e: {speed: 25, inverted: false}
            },
            extruder: {
                count: 1,
                offsets: [
                    {x:0.0, y:0.0,  z:0.0}
                ],
                nozzleDiameter: 0.4
            },
	   cmdPrintStart:[
		    {cmd:"M80"},	                
		    {cmd:"G28 X0 Y0"},
		    {cmd:"G28 Z0"},
		    {cmd:"G1 Z15.0 F6000"},
		    {cmd:"M140 S60.0"},
		    {cmd:"M104 T0 S200.0"},
		    {cmd:"M109 T0 S200.0"},
		    {cmd:"M190 S60.0"}
		],
	    cmdPrintStop:[			
		    {cmd:"M84"}
		],
            stepsPerUnit:{
                x:157.4804,
                y:157.4804,
                z:2133.33,
                e:304
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
	        t1: 450
	    },
	    stepperMircostep:{
		x: 32,
		y: 32,
		z: 32,
		t0: 32,
		t1: 32	                        
	    },
	    endstopInvert:{
	        x: false,
	        y: false,
	        z: false
	    },
	    endstopMinimumInput:{
	         x: true,
	         y: true,
	         z: true
	    },
	    endstopMaxmumInput:{
	          x: true,
	          y: true,
	          z: true	                        
	    },
	    endstopUseSoftware:{
		  minVal: false,
		  maxVal: true
	    },
	    retractLength:{
		  length: 3,
		  feedrate: 25,
		  zlift: 0
	    },
	    retractRecoverLength:{
		  length:2,
		  feedrate:20
	    },	        
	    homingFeedrates:{
	            x: 3000,
		    y: 3000,
		    z: 120,
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
		    minimumfeedrate: 0,
		    mintravelfeedrate: 0,
		    maxXYJerk: 100,
		    maxZJerk: 0.4,
		    maxEJerk: 5.0
	    }
        }
    };

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
        5
    );
    self.defaultProfile = ko.observable();
    self.currentProfile = ko.observable();

    self.currentProfileData = ko.observable(ko.mapping.fromJS(self._cleanProfile()));

    self.editorNew = ko.observable(false);

    self.editorName = ko.observable();
    self.editorColor = ko.observable();
    
    self.editorExtendInterface = ko.observable();
    self.editorThermocouple = ko.observable();

    //lkj 
    //self.editorMaxSpeed = ko.observable();
    self.editorIdentifier = ko.observable();
    self.editorModel = ko.observable();
    
    self.editorCmdPrintStart = ko.observableArray([]);
    self.addCmdPrintStart = function() {
	self.editorCmdPrintStart.push({cmd: "M110"})
    };
    self.removeCmdPrintStart = function(cmd) {
	self.editorCmdPrintStart.remove(cmd);
    };
    
    self.editorCmdPrintStop = ko.observableArray([]);
    self.addCmdPrintStop = function() {
	self.editorCmdPrintStop.push({cmd: "M105"})
    };
    self.removeCmdPrintStop = function(cmd) {
	self.editorCmdPrintStop.remove(cmd);
    };
    //lkj
    self.editorStepsPerUnitX = ko.observable();
    self.editorStepsPerUnitY = ko.observable();
    self.editorStepsPerUnitZ = ko.observable();
    self.editorStepsPerUnitE = ko.observable();
    
    self.editorHomingDirectionX = ko.observable();
    self.editorHomingDirectionY = ko.observable();
    self.editorHomingDirectionZ = ko.observable();
    
    self.editorStepperCurrentX = ko.observable();
    self.editorStepperCurrentY = ko.observable();
    self.editorStepperCurrentZ = ko.observable();
    self.editorStepperCurrentT0 = ko.observable();
    self.editorStepperCurrentT1 = ko.observable();

    self.editorStepperMircostepX = ko.observable();
    self.editorStepperMircostepY = ko.observable();
    self.editorStepperMircostepZ = ko.observable();
    self.editorStepperMircostepT0 = ko.observable();
    self.editorStepperMircostepT1 = ko.observable();
    
    self.editorEndstopInvertX = ko.observable();
    self.editorEndstopInvertY = ko.observable();
    self.editorEndstopInvertZ = ko.observable();
    
    self.editorEndstopMinimumInputX = ko.observable();
    self.editorEndstopMinimumInputY = ko.observable();
    self.editorEndstopMinimumInputZ = ko.observable();

    self.editorEndstopMaxmumInputX = ko.observable();
    self.editorEndstopMaxmumInputY = ko.observable();
    self.editorEndstopMaxmumInputZ = ko.observable();


    self.editorEndstopUseSoftwareMin = ko.observable();
    self.editorEndstopUseSoftwareMax = ko.observable();

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


    //end lkj

    self.editorVolumeWidth = ko.observable();
    self.editorVolumeDepth = ko.observable();
    self.editorVolumeHeight = ko.observable();
    self.editorVolumeFormFactor = ko.observable();
    
    self.editorMachineType = ko.observable();
	
    self.editordelta_diagonal_rod = ko.observable();
    self.editordelta_print_radius = ko.observable();
    self.editordelta_z_home_pos = ko.observable();
    self.editordelta_segments_per_second = ko.observable();

    

    self.editorHeatedBed = ko.observable();
    self.editorDynamicCurrent = ko.observable();
    

    self.editorNozzleDiameter = ko.observable();
    self.editorExtruders = ko.observable();
    self.editorExtruderOffsets = ko.observableArray([]);

    self.editorAxisXSpeed = ko.observable();
    self.editorAxisYSpeed = ko.observable();
    self.editorAxisZSpeed = ko.observable();
    self.editorAxisESpeed = ko.observable();

    self.editorAxisXInverted = ko.observable();
    self.editorAxisYInverted = ko.observable();
    self.editorAxisZInverted = ko.observable();
    self.editorAxisEInverted = ko.observable();
    
    self.editorPidsT0P = ko.observable();
    self.editorPidsT0I = ko.observable();
    self.editorPidsT0D = ko.observable();
    self.editorPidsT0Limit = ko.observable();
    self.editorPidsT0Factor = ko.observable();
    self.editorPidsT0Offset = ko.observable();

    
    self.editorPidsT1P = ko.observable();
    self.editorPidsT1I = ko.observable();
    self.editorPidsT1D = ko.observable();
    self.editorPidsT1Limit = ko.observable();
    self.editorPidsT1Factor = ko.observable();
    self.editorPidsT1Offset = ko.observable();
    
    self.editorPidsBedP = ko.observable();
    self.editorPidsBedI = ko.observable();
    self.editorPidsBedD = ko.observable();
    self.editorPidsBedLimit = ko.observable();
    self.editorPidsBedFactor = ko.observable();
    self.editorPidsBedOffset = ko.observable();

    self.availableColors = ko.observable([
        {key: "default", name: gettext("default")},
        {key: "red", name: gettext("red")},
        {key: "orange", name: gettext("orange")},
        {key: "yellow", name: gettext("yellow")},
        {key: "green", name: gettext("green")},
        {key: "blue", name: gettext("blue")},
        {key: "black", name: gettext("black")}
    ]);
    
    self.availableExtendInterface = ko.observable([
	{key: "1", name: gettext("Dual Z")},
	{key: "2", name: gettext("Dual Extruder")},
    ]);
    self.availableThermocoupleConnection = ko.observable([
	{key: "1", name: gettext("Ext1")},
	{key: "2", name: gettext("Ext2")},
	{key: "3", name: gettext("Ext3")},
    ]);
    
    self.availableStepperMircoStep = ko.observable([
	{key: "1", name: gettext("1")},
	{key: "2", name: gettext("2")},
	{key: "4", name: gettext("4")},
	{key: "8", name: gettext("8")},
	{key: "16", name: gettext("16")},
	{key: "32", name: gettext("32")}
    ]);

    self._printer_extruderOffsets = ko.observableArray([]);
    self.printer_extruderOffsets = ko.computed({
        read: function() {
            var extruderOffsets = self._printer_extruderOffsets();
            var result = [];
            for (var i = 0; i < extruderOffsets.length; i++) {
                result[i] = {
                    x: parseFloat(extruderOffsets[i].x()),
                    y: parseFloat(extruderOffsets[i].y()),
		    z: parseFloat(extruderOffsets[i].z())
                }   
            }
            return result;
        },      
        write: function(value) {
            var result = [];
            if (value && Array.isArray(value)) {
                for (var i = 0; i < value.length; i++) {
                    result[i] = {
                        x: ko.observable(value[i].x),
                        y: ko.observable(value[i].y),
			z: ko.observable(value[i].z)
                    }
                }
            }
            self._printer_extruderOffsets(result);
        },
        owner: self
    });

    self.koEditorExtruderOffsets = ko.computed(function() {
        var extruderOffsets = self._printer_extruderOffsets();
        var numExtruders = self.editorExtruders();
        if (!numExtruders) {
            numExtruders = 1;
        }

        if (numExtruders > extruderOffsets.length) {
            for (var i = extruderOffsets.length; i < numExtruders; i++) {
                extruderOffsets[i] = {
                    x: ko.observable(0),
                    y: ko.observable(0),
		    z: ko.observable(0)
                }
            }
            self._printer_extruderOffsets(extruderOffsets);
        }

        return extruderOffsets.slice(0, numExtruders);
    });

    self.makeDefault = function(data) {
        var profile = {
            id: data.id,
            default: true
        };

        self.updateProfile(profile);
    };
    
     self.isVisibleDeltaForm = function() {
	var a = self.editorMachineType();
	   if(a == "Delta"){
	     return true;
	   }
	   return false;
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
        $.ajax({
            url: API_BASEURL + "printerprofiles",
            type: "POST",
            dataType: "json",
            contentType: "application/json; charset=UTF-8",
            data: JSON.stringify({profile: profile}),
            success: function() {
                if (callback !== undefined) {
                    callback();
                }
                self.requestData();
            }
        });
    };

    self.removeProfile = function(data) {
        $.ajax({
            url: data.resource,
            type: "DELETE",
            dataType: "json",
            success: self.requestData
        })
    };

    self.updateProfile = function(profile, callback) {
        if (profile == undefined) {
            profile = self._editorData();
        }

        $.ajax({
            url: API_BASEURL + "printerprofiles/" + profile.id,
            type: "PATCH",
            dataType: "json",
            contentType: "application/json; charset=UTF-8",
            data: JSON.stringify({profile: profile}),
            success: function() {
                if (callback !== undefined) {
                    callback();
                }
                self.requestData();
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
	
	self.editorExtendInterface(data.extendInterface);
	self.editorThermocouple(data.thermocouple);

        //lkj 
        //self.editorMaxSpeed(data.maxSpeed);
        self.editorModel(data.model);		
	self.editorCmdPrintStart(data.cmdPrintStart);
	self.editorCmdPrintStop(data.cmdPrintStop);
        //lkj
        self.editorStepsPerUnitX(data.stepsPerUnit.x);
        self.editorStepsPerUnitY(data.stepsPerUnit.y);
        self.editorStepsPerUnitZ(data.stepsPerUnit.z);
        self.editorStepsPerUnitE(data.stepsPerUnit.e);
        
        self.editorHomingDirectionX(data.homingDirection.x);
        self.editorHomingDirectionY(data.homingDirection.y);
        self.editorHomingDirectionZ(data.homingDirection.z);
	
	self.editorStepperCurrentX(data.stepperCurrent.x);
	self.editorStepperCurrentY(data.stepperCurrent.y);
	self.editorStepperCurrentZ(data.stepperCurrent.z);
	self.editorStepperCurrentT0(data.stepperCurrent.t1);
	self.editorStepperCurrentT1(data.stepperCurrent.t0);

	self.editorStepperMircostepX(data.stepperMircostep.x);
	self.editorStepperMircostepY(data.stepperMircostep.y);
	self.editorStepperMircostepZ(data.stepperMircostep.z);
	self.editorStepperMircostepT0(data.stepperMircostep.t1);
	self.editorStepperMircostepT1(data.stepperMircostep.t0);
	
	self.editorEndstopInvertX(data.endstopInvert.x);
	self.editorEndstopInvertY(data.endstopInvert.y);
	self.editorEndstopInvertZ(data.endstopInvert.z);
	
	self.editorEndstopMinimumInputX(data.endstopMinimumInput.x);
	self.editorEndstopMinimumInputY(data.endstopMinimumInput.y);
	self.editorEndstopMinimumInputZ(data.endstopMinimumInput.z);

	self.editorEndstopMaxmumInputX(data.endstopMaxmumInput.x);
	self.editorEndstopMaxmumInputY(data.endstopMaxmumInput.y);
	self.editorEndstopMaxmumInputZ(data.endstopMaxmumInput.z);


	self.editorEndstopUseSoftwareMin(data.endstopUseSoftware.minVal);
	self.editorEndstopUseSoftwareMax(data.endstopUseSoftware.maxVal);

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

        //lkj end

        self.editorVolumeWidth(data.volume.width);
        self.editorVolumeDepth(data.volume.depth);
        self.editorVolumeHeight(data.volume.height);
        self.editorVolumeFormFactor(data.volume.formFactor);
	
        self.editorMachineType(data.machineType);

        self.editordelta_diagonal_rod(data.delta_args.diagonal_rod);
	self.editordelta_print_radius(data.delta_args.print_radius);
	self.editordelta_z_home_pos(data.delta_args.z_home_pos);
	self.editordelta_segments_per_second(data.delta_args.segments_per_second);

        self.editorHeatedBed(data.heatedBed);

	self.editorDynamicCurrent(data.dynamicCurrent);
        self.editorNozzleDiameter(data.extruder.nozzleDiameter);
        self.editorExtruders(data.extruder.count);
        //lkj var offsets = [];
        //_.each(data.extruder.offsets, function(offset) {
        //    offsets.push({
        //        x: ko.observable(offset[0]),
        //        y: ko.observable(offset[1])
        //    });
        //});
        //self.editorExtruderOffsets(offsets);
	self.printer_extruderOffsets(data.extruder.offsets);

        self.editorAxisXSpeed(data.axes.x.speed);
        self.editorAxisXInverted(data.axes.x.inverted);
        self.editorAxisYSpeed(data.axes.y.speed);
        self.editorAxisYInverted(data.axes.y.inverted);
        self.editorAxisZSpeed(data.axes.z.speed);
        self.editorAxisZInverted(data.axes.z.inverted);
        self.editorAxisESpeed(data.axes.e.speed);
        self.editorAxisEInverted(data.axes.e.inverted);

	self.editorAxisXInverted(data.axes.x.inverted);
	self.editorAxisYSpeed(data.axes.y.speed);
	self.editorAxisYInverted(data.axes.y.inverted);
	self.editorAxisZSpeed(data.axes.z.speed);
	self.editorAxisZInverted(data.axes.z.inverted);
	self.editorAxisESpeed(data.axes.e.speed);
	self.editorAxisEInverted(data.axes.e.inverted);
	
	self.editorPidsT0P(data.pids.t0.p);
	self.editorPidsT0I(data.pids.t0.i);
	self.editorPidsT0D(data.pids.t0.d);
	self.editorPidsT0Limit(data.pids.t0.limit);
	self.editorPidsT0Factor(data.pids.t0.factor);
	self.editorPidsT0Offset(data.pids.t0.offset);
	
	self.editorPidsT1P(data.pids.t1.p);
	self.editorPidsT1I(data.pids.t1.i);
	self.editorPidsT1D(data.pids.t1.d);
	self.editorPidsT1Limit(data.pids.t1.limit);
	self.editorPidsT1Factor(data.pids.t1.factor);
	self.editorPidsT1Offset(data.pids.t1.offset);

	self.editorPidsBedP(data.pids.bed.p);
	self.editorPidsBedI(data.pids.bed.i);
	self.editorPidsBedD(data.pids.bed.d);
	self.editorPidsBedLimit(data.pids.bed.limit);
	self.editorPidsBedFactor(data.pids.bed.factor);
	self.editorPidsBedOffset(data.pids.bed.offset);	

        var editDialog = $("#settings_printerProfiles_editDialog");
        var confirmButton = $("button.btn-confirm", editDialog);
        var dialogTitle = $("h3.modal-title", editDialog);

	/*
	var editAddCmdPrintStart = $("AddCmdPrintStart", editDialog);
	editAddCmdPrintStart.unbind("click");
	editAddCmdPrintStart.bind("click", function() {
	    alert("Failed, please check!");
	    self.addCmdPrintStart();
	});*/
	
        dialogTitle.text(add ? gettext("Add Printer Profile") : _.sprintf(gettext("Edit Printer Profile \"%(name)s\""), {name: data.name}));
        confirmButton.unbind("click");
        confirmButton.bind("click", function() {
            self.confirmEditProfile(add);
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
            self.updateProfile(undefined, callback);
        }
    };

    self._editorData = function() {
        var profile = {
            id: self.editorIdentifier(),
            name: self.editorName(),
            color: self.editorColor(),
	    extendInterface: self.editorExtendInterface(),
	    thermocouple: self.editorThermocouple(),
	    
            //lkj 
            //maxSpeed:self.editorMaxSpeed(),
            model: self.editorModel(),	    
            volume: {
                width: self.editorVolumeWidth(),
                depth: self.editorVolumeDepth(),
                height: self.editorVolumeHeight(),
                formFactor: self.editorVolumeFormFactor()
            },
	    
	    machineType: self.editorMachineType(),
	    
	    delta_args: {
		diagonal_rod: self.editordelta_diagonal_rod(),
		print_radius: self.editordelta_print_radius(),
		z_home_pos: self.editordelta_z_home_pos(),
		segments_per_second: self.editordelta_segments_per_second()
	    },
	    
	    dynamicCurrent: self.editorDynamicCurrent(),
            heatedBed: self.editorHeatedBed(),
            extruder: {
                count: self.editorExtruders(),
                offsets: self.printer_extruderOffsets(),
                nozzleDiameter: self.editorNozzleDiameter()
            },
            axes: {
                x: {
                    speed: self.editorAxisXSpeed(),
                    inverted: self.editorAxisXInverted()
                },
                y: {
                    speed: self.editorAxisYSpeed(),
                    inverted: self.editorAxisYInverted()
                },
                z: {
                    speed: self.editorAxisZSpeed(),
                    inverted: self.editorAxisZInverted()
                },
                //lkj
                e: { 
                    speed: self.editorAxisESpeed(),
                    inverted: self.editorAxisEInverted()
                }
            },
	    
	    pids:{
		t0:{
		    p:self.editorPidsT0P(),
		    i:self.editorPidsT0I(),
		    d:self.editorPidsT0D(),
		    limit:self.editorPidsT0Limit(),
		    factor:self.editorPidsT0Factor(),
		    offset:self.editorPidsT0Offset()
		},
		t1:{
		    p:self.editorPidsT1P(),
		    i:self.editorPidsT1I(),
		    d:self.editorPidsT1D(),
		    limit:self.editorPidsT1Limit(),
		    factor:self.editorPidsT1Factor(),
		    offset:self.editorPidsT1Offset()
		},
		bed:{
		    p:self.editorPidsBedP(),
		    i:self.editorPidsBedI(),
		    d:self.editorPidsBedD(),
		    limit:self.editorPidsBedLimit(),
		    factor:self.editorPidsBedFactor(),
		    offset:self.editorPidsBedOffset()
		}
	    },	    	    
	    
            //lkj
	    cmdPrintStart: self.editorCmdPrintStart(),
	    cmdPrintStop: self.editorCmdPrintStop(),
            stepsPerUnit: {
                x: self.editorStepsPerUnitX(),
                y: self.editorStepsPerUnitY(),
                z: self.editorStepsPerUnitZ(),
                e: self.editorStepsPerUnitE()
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
	        t1: self.editorStepperCurrentT1()
	    },
	    stepperMircostep:{
		x:  self.editorStepperMircostepX(),
		y:  self.editorStepperMircostepY(),
		z:  self.editorStepperMircostepZ(),
		t0: self.editorStepperMircostepT0(),
		t1: self.editorStepperMircostepT1()	                        
	    },
	    endstopInvert:{
	        x: self.editorEndstopInvertX(),
	        y: self.editorEndstopInvertY(),
	        z: self.editorEndstopInvertZ()
	    },
	    endstopMinimumInput:{
	         x: self.editorEndstopMinimumInputX(),
	         y: self.editorEndstopMinimumInputY(),
	         z: self.editorEndstopMinimumInputZ()
	    },
	    endstopMaxmumInput:{
	          x: self.editorEndstopMaxmumInputX(),
	          y: self.editorEndstopMaxmumInputY(),
	          z: self.editorEndstopMaxmumInputZ()	                        
	    },
	    endstopUseSoftware:{
		  minVal: self.editorEndstopUseSoftwareMin(),
		  maxVal: self.editorEndstopUseSoftwareMax()
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
	    advancedVariables:{
		    minimumfeedrate:   self.editorAdvancedVariablesMinimumfeedrate(),
		    mintravelfeedrate: self.editorAdvancedVariablesMintravelfeedrate(),
		    maxXYJerk:       self.editorAdvancedVariablesMaxXYJerk(),
		    maxZJerk:        self.editorAdvancedVariablesMaxZJerk(),
		    maxEJerk:        self.editorAdvancedVariablesMaxEJerk()
	    }
            //lkj end
        };

        if (self.editorExtruders() >= 1) {
            for (var i = 1; i < self.editorExtruders(); i++) {
                var offset = [0.0, 0.0, 0.0];
                if (i < self.editorExtruderOffsets().length) {
                    offset = [parseFloat(self.editorExtruderOffsets()[i]["x"]()), parseFloat(self.editorExtruderOffsets()[i]["y"]()), parseFloat(self.editorExtruderOffsets()[i]["z"]())];
                }
                profile.extruder.offsets.push(offset);
            }
        }

        return profile;
    };

    self.onSettingsShown = self.requestData;
    self.onStartup = self.requestData;
}