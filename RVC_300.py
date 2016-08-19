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

"""
### BEGIN NODE INFO
[info]
name = RVC Server
version = 1.0
description = RVC Pressure Gauge and Leak Valve Controller

[startup]
cmdline = %PYTHON% %FILE%
timeout = 20

[shutdown]
message = 987654321
timeout = 20
### END NODE INFO
"""

import platform
global serial_server_name
serial_server_name = (platform.node() + '_serial_server').replace('-','_').lower()

global port_to_int,int_to_port
port_to_int = {'X1':0,'Y1':1,'X2':2,'Y2':3}
int_to_port = ['X1','Y1','X2','Y2']

from labrad.server import setting
from labrad.devices import DeviceServer,DeviceWrapper
from twisted.internet.defer import inlineCallbacks, returnValue
import labrad.units as units
from labrad.types import Value
import time

TIMEOUT = Value(5,'s')
BAUD    = 9600
BYTESIZE = 8
STOPBITS = 1
PARITY = 0

class RVCWrapper(DeviceWrapper):

    @inlineCallbacks
    def connect(self, server, port):
        """Connect to a device."""
        print 'connecting to "%s" on port "%s"...' % (server.name, port),
        self.server = server
        self.ctx = server.context()
        self.port = port
        p = self.packet()
        p.open(port)
        p.baudrate(BAUD)
        p.bytesize(BYTESIZE)
        p.stopbits(STOPBITS)
        p.setParity = PARITY
        p.read()  # clear out the read buffer
        p.timeout(TIMEOUT)
        print(" CONNECTED ")
        yield p.send()
        
    def packet(self):
        """Create a packet in our private context"""
        return self.server.packet(context=self.ctx)

    def shutdown(self):
        """Disconnect from the serial port when we shut down"""
        return self.packet().close().send()

    @inlineCallbacks
    def write(self, code):
        """Write a data value to the device"""
        yield self.packet().write(code).send()

    @inlineCallbacks
    def read(self):
        """Read a response line from the device"""
        p=self.packet()
        p.read_line()
        ans=yield p.send()
        returnValue(ans.read_line)

    @inlineCallbacks
    def query(self, code):
        """ Write, then read. """
        p = self.packet()
        p.write_line(code)
        p.read_line()
        ans = yield p.send()
        returnValue(ans.read_line)


class RVCServer(DeviceServer):
    name             = 'RVC_Server'
    deviceName       = 'RVC 300 Pressure Controller'
    deviceWrapper    = RVCWrapper

    @inlineCallbacks
    def initServer(self):
        print 'loading config info...',
        self.reg = self.client.registry()
        yield self.loadConfigInfo()
        print 'done.'
        print self.serialLinks
        yield DeviceServer.initServer(self)

    @inlineCallbacks
    def loadConfigInfo(self):
        reg = self.reg
        yield reg.cd(['', 'Servers', 'RVC 300', 'Links'], True)
        dirs, keys = yield reg.dir()
        p = reg.packet()
        print "Created packet"
        print "printing all the keys",keys
        for k in keys:
            print "k=",k
            p.get(k, key=k)            
        ans = yield p.send()
        print "ans=",ans
        self.serialLinks = dict((k, ans[k]) for k in keys)
    
    @inlineCallbacks
    def findDevices(self):
        devs = []
        for name, (serServer, port) in self.serialLinks.items():
            if serServer not in self.client.servers:
                print serServer
                print self.client.servers
                continue
            server = self.client[serServer]
            ports = yield server.list_serial_ports()
            if port not in ports:
                continue
            devName = '%s - %s' % (serServer, port)
            devs += [(devName, (server, port))]
        returnValue(devs)
                        
    @setting(205,returns='s')
    def get_ver(self,c):
        """Queries the VER? command and returns the response. Usage is get_ver()"""
        dev=self.selectedDevice(c)
        yield dev.write("VER?\r\n")
        ans = yield dev.read()
        returnValue(ans)

    @setting(206,returns='s')
    def get_nom_prs(self,c):
        """Queries the PRS? command and returns the response. Response is nominal pressure. Usage is get_nom_prs()"""
        dev=self.selectedDevice(c)
        yield dev.write("PRS?\r\n")
        ans = yield dev.read()
        returnValue(ans)
        
    @setting(207,nom_prs='s',returns='s')
    def set_nom_prs(self,c,nom_prs):
        """Queries the PRS=x.xxEsxx command and returns the response. Input requires string 
        of the form x.xxEsxx, where x are digits and s is either + or -. Usage is set_nom_prs('1.00E+01')"""
        dev=self.selectedDevice(c)
        yield dev.write("PRS=" + nom_prs + "\r\n")
        ans = yield dev.read()
        returnValue(ans)
        
    @setting(208,returns='s')
    def get_nom_flo(self,c):
        """Queries the PRS? command and returns the response. Response is nominal pressure. Usage is get_nom_flo()"""
        dev=self.selectedDevice(c)
        yield dev.write("FLO?\r\n")
        ans = yield dev.read()
        returnValue(ans)
        
    @setting(209,nom_flo='s',returns='s')
    def set_nom_flo(self,c,nom_flo):
        """Queries the FLO=xxx.x command and returns the response. Input requires string 
        of the form xxx.x, where x are digits. This sets flow to a percentage. Usage is set_nom_flo('012.5')"""
        dev=self.selectedDevice(c)
        yield dev.write("FLO=" + nom_flo + "\r\n")
        ans = yield dev.read()
        returnValue(ans)
        
    @setting(210,returns='*s')
    def close_valve(self,c):
        """Queries the PRS=5.01E-09 and FLO=0000.0 commands and returns the responses. Sets nominal pressure to minimum and 
        sets nominal flow to 0, closing the valve in either pressure or flow mode. Usage close_valve()"""
        dev=self.selectedDevice(c)
        yield dev.write("FLO=000.0\r\n")
        ans1 = yield dev.read()
        yield dev.write("PRS=5.01E-09\r\n")
        ans2 = yield dev.read()
        returnValue([ans1, ans2])
        
    @setting(211,returns='s')
    def get_mode(self,c):
        """Queries the MOD? command and returns the response. Usage get_mode()"""
        dev=self.selectedDevice(c)
        yield dev.write("MOD?\r\n")
        ans = yield dev.read()
        returnValue(ans)

    @setting(212,returns='s')
    def set_mode_prs(self,c):
        """Queries the MOD=P command and returns the response. Usage set_mode_prs()"""
        dev=self.selectedDevice(c)
        yield dev.write("MOD=P\r\n")
        ans = yield dev.read()
        returnValue(ans)
        
    @setting(213,returns='s')
    def set_mode_flo(self,c):
        """Queries the MOD=F command and returns the response. Usage set_mode_flo()"""
        dev=self.selectedDevice(c)
        yield dev.write("MOD=F\r\n")
        ans = yield dev.read()
        returnValue(ans)
        
    @setting(214,returns='s')
    def keys_lock(self,c):
        """Queries the TAS=D command and returns the response. Disables usage of keys on RVC screen. Usage keys_lock()"""
        dev=self.selectedDevice(c)
        yield dev.write("TAS=D\r\n")
        ans = yield dev.read()
        returnValue(ans)
    
    @setting(215,returns='s')
    def keys_enable(self,c):
        """Queries the TAS=E command and returns the response. Enables usage of keys on RVC screen. Usage keys_enable()"""
        dev=self.selectedDevice(c)
        yield dev.write("TAS=E\r\n")
        ans = yield dev.read()
        returnValue(ans)
      
    @setting(216,returns='s')
    def get_prs(self,c):
        """Queries the PRI? command and returns the response. Gets current pressure. Usage get_prs()"""
        dev=self.selectedDevice(c)
        yield dev.write("PRI?\r\n")
        ans = yield dev.read()
        returnValue(ans)
        
    @setting(217,returns='s')
    def get_unit(self,c):
        """Queries the UNT? command and returns the response. Gets measurement unit. Usage get_unit()"""
        dev=self.selectedDevice(c)
        yield dev.write("UNT?\r\n")
        ans = yield dev.read()
        returnValue(ans)
        
__server__ = RVCServer()
if __name__ == '__main__':
    from labrad import util
    util.runServer(__server__)
