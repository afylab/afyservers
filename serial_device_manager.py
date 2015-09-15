# Copyright (C) 2015  Brunel Odegard
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""
### BEGIN NODE INFO
[info]
name = Serial Device Manager
version = 1.0.0
description = Detect / identify Arduino devices

[startup]
cmdline = %PYTHON% %FILE%
timeout = 20

[shutdown]
message = 987654321
timeout = 5
### END NODE INFO
"""

global blacklisted_ports
blacklisted_ports = [1]

from time import sleep
import time

from labrad import types as T
from labrad.errors import Error
from labrad.server import LabradServer, setting
from twisted.internet import reactor, threads
from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.internet.task import deferLater
from serial import Serial
from serial.serialutil import SerialException


class SerialDeviceManager(LabradServer):
    """Identifies devices on a computer's serial (COM) ports."""
    name = 'serial_device_manager'
    def initServer(self):
        self.findPorts()
        self.identifyPorts()

    def findPorts(self):
        self.serialPorts=[]
        for port in range(1,33):
            if port not in blacklisted_ports:
                try:
                    ser=Serial('\\\\.\\COM%d'%port)
                    ser.close()
                    self.serialPorts.append("COM%i"%port)
                    print("Found active port: COM%i"%port)
                except:
                    pass
        if len(self.serialPorts):
            print("Found serial ports: ")
            print(self.serialPorts)
        else:print("No serial ports found.")

    def identifyPorts(self):
        self.portTypes = []
        baudrates = [115200,19200,] # If devices with other baudrates are added, add the baudrates to this list
        for port in self.serialPorts:
            print("Identifying port %s..."%port)
            ser = Serial('\\\\.\\%s'%port)
            ser.setTimeout(1)

            success=False
            for rate in baudrates:
                ser.setBaudrate(rate)
                ser.write('NOP\r');ser.readline() # clear buffer
                ser.write('*IDN?\r');idn = ser.readline()
                if not(idn == ''):
                    print("Port %s responded to *IDN? command with string %s and baudrate %i"%(port,idn,rate))
                    self.portTypes.append([port,idn,str(rate)])
                    success=True
                    break
            if not success:print("Port %s did not respond to any known identification commands."%port)
                
        print(self.portTypes)
            

    @setting(1,returns='*s')
    def list_serial_ports(self,c):
        ret = yield self.serialPorts
        returnValue(ret)

    @setting(2,returns='**s')
    def list_devices(self,c):
        ret = yield self.portTypes
        returnValue(ret)

    @setting(3,returns=[])
    def reload_ports(self,c):
        '''Searches for ports and identifies them (again.)'''
        self.findPorts()
        self.identifyPorts()
        yield

    @setting(100,returns='**s')
    def list_ad5764_dcbox_devices(self,c):
        ad5764_dcbox_devices = yield []
        for device in self.portTypes:
            if device[1].startswith('DCBOX_DUAL_AD5764'):
                ad5764_dcbox_devices.append(device)
        returnValue(ad5764_dcbox_devices)

    @setting(101,returns='**s')
    def list_ad5764_acbox_devices(self,c):
        ad5764_acbox_devices = yield []
        for device in self.portTypes:
            if device[1].startswith('ACBOX_DUAL_AD5764'):
                ad5764_acbox_devices.append(device)
        returnValue(ad5764_acbox_devices)

    ################################################################################
    ## as more device types are made, add them here as list_(device_name)_devices ##
    ################################################################################
        

    













__server__ = SerialDeviceManager()

if __name__ == '__main__':
    from labrad import util

    util.runServer(__server__)
