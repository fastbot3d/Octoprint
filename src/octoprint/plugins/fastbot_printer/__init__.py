# coding=utf-8
from __future__ import absolute_import

__author__ = "Gina Häußge <osd@foosel.net>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'
__copyright__ = "Copyright (C) 2015 The OctoPrint Project - Released under terms of the AGPLv3 License"

import octoprint.plugin
from . import fastbot

class FastbotPrinterPlugin(octoprint.plugin.SettingsPlugin):

    def fastbot_printer_factory(self, comm_instance, port, baudrate, read_timeout):
        #if not port == "socket":
        #    return None
        print("get fastbotPrinter 0")
        '''
        if not self._settings.global_get_boolean(["devel", "virtualPrinter", "enabled"]):
            return None
        '''
        
        serial_obj = fastbot.FastbotPrinter(read_timeout=float(read_timeout))
        print("get fastbotPrinter 1")
        return serial_obj

__plugin_name__ = "Fastbot Printer"
__plugin_author__ = "Luokj"
__plugin_homepage__ = "http://www.fastbot3d.com"
__plugin_license__ = "AGPLv3"
__plugin_description__ = "Fastbot Printer for BBP Board"

def __plugin_load__():
    plugin = FastbotPrinterPlugin()

    global __plugin_implementation__
    __plugin_implementation__ = plugin

    global __plugin_hooks__
    __plugin_hooks__ = {
        "octoprint.comm.transport.serial.factory": plugin.fastbot_printer_factory
    }
