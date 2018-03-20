# Copyright []
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
#
#This grabs the latest temperatures from the log file on the Z:/drive, it is
# very specific to the Bluefors dilfridge
#

"""
### BEGIN NODE INFO
[info]
name = temperature_BF
version = 1.0
description = Grabbing temperature from a log file on the Z drive
[startup]
cmdline = %PYTHON% %FILE%
timeout = 20
[shutdown]
message = 987654321
timeout = 20
### END NODE INFO
"""

import platform
# global serial_server_name
# serial_server_name = platform.node() + '_serial_server'

from labrad.server import setting
from labrad.devices import DeviceServer,DeviceWrapper
from twisted.internet.defer import inlineCallbacks, returnValue
import labrad.units as units
from labrad.types import Value
import numpy as np
import os, fnmatch, datetime, time, shutil

CH = ['CH1','CH2','CH3','CH5','CH6','CH9']
NAMES = ['50 K Stage','4 K Stage','Magnet','Still','Mixing Chamber','Probe']
LOG_DIR =  'Z:\Fridge Logs\BLUEFORS T\\'

class serverInfo(object):
    def __init__(self):
        self.deviceName = 'Temperature_BF'
        self.serverName = "temperature_BF"
        self.fnames = {}


    def getDeviceName(self,comPort):
        return "temperature_BF"


class TemperatureBFWrapper(DeviceWrapper):

    @inlineCallbacks
    def connect(self, server, port):
        """Connect to a device."""
        os.chdir(LOG_DIR)

    def shutdown(self):
        """Disconnect from the serial port when we shut down."""
        pass


class TemperatureBFServer(DeviceServer):
    name = 'temperature_BF'
    deviceName = 'Temperature_BF'
    deviceWrapper = TemperatureBFWrapper


    @setting(100)
    def connect(self,c,server,port):
        dev=self.selectedDevice(c)
        yield dev.connect(server,port)

    @setting(101)
    def update_dir(self,c):
        os.chdir(LOG_DIR)
        curr_dir = os.listdir('.')[-1]
        os.chdir(curr_dir)
        files = os.listdir('.')

        fnames = {}

        for fi in files:
            for fn in CH:
                if fnmatch.fnmatch(fi,fn+' T*'):
                    fnames[fn] = fi
        self.fnames = fnames

    @setting(102, returns='*v[]')
    def get_latest(self,c):
        self.update_dir(self)
        files = os.listdir('.')
        Ts = np.zeros(len(CH))
        t = '0'
        for i in range(len(CH)):
            key = CH[i]
            if self.fnames.has_key(key):
                fi = open(self.fnames[key],'r')
                ln = fi.readlines()[-1]
                T = yield self.grab_Ts(c,ln)
                Ts[i]= T
        yield Ts
        returnValue(Ts)

    @setting(103,line='s',returns='*v')
    def grab_Ts(self,c,line):
        vals = line.strip().split(",");

        date = vals[0]
        tm = vals[1]
        T = float(vals[2])
        dt = datetime.datetime.strptime(date+','+tm,'%d-%m-%y,%X')
        t = dt.strftime('%Y-%m-%d %H:%M:%S.%f')
        return T

    @setting(104,returns='v[]')
    def probe(self,c):
        Ts = yield self.get_latest(c)
        T = Ts[-1]
        yield T
        returnValue(T)

    @setting(105,returns='v[]')
    def mc(self,c):
        Ts = yield self.get_latest(c)
        T = Ts[-2]
        yield T
        returnValue(T)



__server__ = TemperatureBFServer()

if __name__ == '__main__':
    from labrad import util
    util.runServer(__server__)
