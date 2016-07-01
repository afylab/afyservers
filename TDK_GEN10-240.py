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
name = Power Supply Server
version = 1.0
description = Controller for Evaporator Valves and Relays

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

class PowerSupplyWrapper(DeviceWrapper):

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
        p.timeout(None)
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


class PowerSupplyServer(DeviceServer):
    name             = 'Power_supply_server'
    deviceName       = 'TDK Power Supply'
    deviceWrapper    = PowerSupplyWrapper
    
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
        #THIS STILL NEEDS TO BE ADDED TO THE REGISTRY
        yield reg.cd(['', 'Servers', 'Power Supply', 'Links'], True)
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

    
    @setting(304,out = 's',returns='s')
    def switch(self,c,out):
        """Switches the output on or off."""
        dev=self.selectedDevice(c)
        yield dev.write("OUT " + out + "\r\n")
        ans = yield dev.read()
        returnValue(ans)

    @setting(305,returns='s')
    def onoff(self,c):
        """Returns the output on/off status."""
        dev=self.selectedDevice(c)
        yield dev.write("OUT?" + "\r\n")
        ans = yield dev.read()
        returnValue(ans)

    @setting(306,returns='s')
    def iden(self,c):
        """Returns the power supply model identification."""
        dev=self.selectedDevice(c)
        yield dev.write("IDN?" + "\r\n")
        ans = yield dev.read()
        returnValue(ans)

    @setting(307,volts = 's',returns='s')
    def volt_set(self,c,volts):
        """Sets the output voltage value in Volts."""
        dev=self.selectedDevice(c)
        yield dev.write("PV " + volts + "\r\n")
        ans = yield dev.read()
        returnValue(ans)

    @setting(308,returns='s')
    def volt_read(self,c):
        """Reads the output voltage setting."""
        dev=self.selectedDevice(c)
        yield dev.write("PV?" + "\r\n")
        ans = yield dev.read()
        returnValue(ans)

    @setting(309,returns='s')
    def act_volt(self,c):
        """Returns the actual voltage output."""
        dev=self.selectedDevice(c)
        yield dev.write("MV?" + "\r\n")
        ans = yield dev.read()
        returnValue(ans)

    @setting(310,current = 's',returns='s')
    def cur_set(self,c,current):
        """Sets the output current value in Amperes."""
        dev=self.selectedDevice(c)
        yield dev.write("PC " + current + "\r\n")
        ans = yield dev.read()
        returnValue(ans)

    @setting(311,returns='s')
    def cur_read(self,c):
        """Reads the output current setting."""
        dev=self.selectedDevice(c)
        yield dev.write("PC?" + "\r\n")
        ans = yield dev.read()
        returnValue(ans)

    @setting(312,returns='s')
    def act_cur(self,c):
        """Returns the actual current output."""
        dev=self.selectedDevice(c)
        yield dev.write("MC?" + "\r\n")
        ans = yield dev.read()
        returnValue(ans)

    @setting(313,adr = 's', returns='s')
    def adr(self,adr,c):
        """Address to access the power supply."""
        dev=self.selectedDevice(c)
        yield dev.write("ADR " + adr + "\r\n")
        ans = yield dev.read()
        returnValue(ans)

    @setting(314,returns='s')
    def clear(self,c):
        """Clear status."""
        dev=self.selectedDevice(c)
        yield dev.write("CLS" + "\r\n")
        ans = yield dev.read()
        returnValue(ans)

    @setting(315,rmt = 's', returns='s')
    def rmt_set(self,rmt,c):
        """Sets the power supply to local or remote mode. Send LOC for local mode, REM for remote, and LLO for local lockout."""
        dev=self.selectedDevice(c)
        yield dev.write("RMT " +rmt+ "\r\n")
        ans = yield dev.read()
        returnValue(ans)

    @setting(316,returns='s')
    def rmt_read(self,c):
        """Returns the remote mode setting."""
        dev=self.selectedDevice(c)
        yield dev.write("RMT?" + "\r\n")
        ans = yield dev.read()
        returnValue(ans)

    @setting(317,fld = 's',returns='s')
    def fld_set(self,fld,c):
        """Turns foldback protection on or off. Send 1 for on or 0 for off."""
        dev=self.selectedDevice(c)
        yield dev.write("FLD " +fld+ "\r\n")
        ans = yield dev.read()
        returnValue(ans)

    @setting(318,returns='s')
    def fld_read(self,c):
        """Returns the foldback protection status."""
        dev=self.selectedDevice(c)
        yield dev.write("FLD?" + "\r\n")
        ans = yield dev.read()
        returnValue(ans)

    @setting(319,ovp = 's',returns='s')
    def ovp_set(self,ovp,c):
        """Sets the over-voltage protection level."""
        dev=self.selectedDevice(c)
        yield dev.write("OVP " + ovp +  "\r\n")
        ans = yield dev.read()
        returnValue(ans)

    @setting(320,returns='s')
    def ovp_read(self,c):
        """Returns the over-voltage protection setting."""
        dev=self.selectedDevice(c)
        yield dev.write("OVP?" + "\r\n")
        ans = yield dev.read()
        returnValue(ans)

    @setting(321,fbd = 's',returns='s')
    def fbd_set(self,fbd,c):
        """Adds the inputted number of seconds to the fold back delay."""
        dev=self.selectedDevice(c)
        yield dev.write("FBD "+fbd + "\r\n")
        ans = yield dev.read()
        returnValue(ans)

    @setting(322,returns='s')
    def fbd_read(self,c):
        """Reads the number of seconds added to the fold back delay."""
        dev=self.selectedDevice(c)
        yield dev.write("FBD?"+ "\r\n")
        ans = yield dev.read()
        returnValue(ans)

    @setting(323,returns='s')
    def fbd_rst(self,c):
        """Resets the fold back delay to zero."""
        dev=self.selectedDevice(c)
        yield dev.write("FBDRST"+ "\r\n")
        ans = yield dev.read()
        returnValue(ans)

    @setting(324,uvl = 's',returns='s')
    def uvl_set(self,uvl,c):
        """Sets the under voltage limit."""
        dev=self.selectedDevice(c)
        yield dev.write("UVL "+ uvl + "\r\n")
        ans = yield dev.read()
        returnValue(ans)

    @setting(325,returns='s')
    def uvl_read(self,c):
        """Reads the under voltage limit."""
        dev=self.selectedDevice(c)
        yield dev.write("UVL?"+ "\r\n")
        ans = yield dev.read()
        returnValue(ans)

    @setting(326,ast = 's',returns='s')
    def ast_set(self,ast,c):
        """Turns auto-restart mode on or off. Input 1 to turn on or 0 to turn off."""
        dev=self.selectedDevice(c)
        yield dev.write("AST "+ast+ "\r\n")
        ans = yield dev.read()
        returnValue(ans)

    @setting(327,returns='s')
    def fbd_read(self,c):
        """Reads the auto restart status."""
        dev=self.selectedDevice(c)
        yield dev.write("AST?"+ "\r\n")
        ans = yield dev.read()
        returnValue(ans)

    @setting(328,returns='s')
    def sav(self,c):
        """Saves the present settings."""
        dev=self.selectedDevice(c)
        yield dev.write("SAV"+ "\r\n")
        ans = yield dev.read()
        returnValue(ans)

    @setting(329,returns='s')
    def rcl(self,c):
        """Recalls the setting from either the last power-down or the last SAV command."""
        dev=self.selectedDevice(c)
        yield dev.write("RCL"+ "\r\n")
        ans = yield dev.read()
        returnValue(ans)

    @setting(330,returns='s')
    def mode(self,c):
        """Returns the power supply operation mode. If the supply is ON it will reutrn either CV or CC (constant voltage/current). If the supply is OFF it will return OFF."""
        dev=self.selectedDevice(c)
        yield dev.write("MODE?"+ "\r\n")
        ans = yield dev.read()
        returnValue(ans)
        
__server__ = PowerSupplyServer()
if __name__ == '__main__':
    from labrad import util
    util.runServer(__server__)