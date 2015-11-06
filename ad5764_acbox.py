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
name = ACBOX Arduino
version = 1.0
description = ACBOX control

[startup]
cmdline = %PYTHON% %FILE%
timeout = 20

[shutdown]
message = 987654321
timeout = 20
### END NODE INFO
"""

def labrad_format(string):
	"""Converts to all lower case, and converts '-' to '_'"""
	return (string.lower()).replace('-','_')

import platform
global serial_server_name
serial_server_name = labrad_format(platform.node()) + '_serial_server'

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
BAUD    = 19200

class AD5764AcboxWrapper(DeviceWrapper):

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
        """Write a data value to the ACBOX"""
        yield self.packet().write(code).send()

    @inlineCallbacks
    def read(self):
        """Read a response line from the ACBOX"""
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


class AD5764AcboxServer(DeviceServer):
    name             = 'ad5764_acbox'
    deviceName       = 'Arduino Acbox'
    deviceWrapper    = AD5764AcboxWrapper
    clock_multiplier = 5

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
        from labrad.wrappers import connectAsync
        cxn=yield connectAsync()
        reg=cxn.registry
        context = yield cxn.context()
        self.serialLinks = {}
        print('SERVERS:',self.client.servers.keys())
    
    @inlineCallbacks
    def findDevices(self):
        server  = self.client.servers[serial_server_name]
        manager = self.client.serial_device_manager
        ports = yield manager.list_ad5764_acbox_devices()

        devs = []
        self.voltages = []
        for port in ports:
            devs.append(('acbox (%s)'%port[0],(server,port[0])))
            self.voltages.append([port[0]]+['unknown' for pos in range(6)])
            # entries of voltages[i] are [port, x1, y1, x2, y2, frequency, phase]
        returnValue(devs)

    @setting(100)
    def connect(self,c,server,port):
        dev=self.selectedDevice(c)
        yield dev.connect(server,port)

    @setting(201,clock_multiplier='i',returns='s' )
    def initialize(self,c,clock_multiplier=5):
        """Initializes the device. Usage: initialize(clock_multiplier)"""
        yield
        self.clock_multiplier = clock_multiplier
        if (clock_multiplier < 4) or (clock_multiplier > 20):
            returnValue("Error: clock multiplier must be bewteen 4 and 20.")
        dev=self.selectedDevice(c)
        yield dev.write("NOP\r") # clear input buffer
        yield dev.read()         # clear output buffer
        yield dev.write("INIT,%i\r"%clock_multiplier);
        ans = yield dev.read()
        returnValue(ans)

    @setting(202,channel='s',value='v',returns='s')
    def set_channel_voltage(self,c,channel,value):
        """Sets the voltage for a channel. Usage is set_channel_voltage(channel, fraction_of_full_scale)
Channel must be "X1" "Y1" "X2" or "Y2" and the value must be from 0 to 1"""
        yield
        if not (0<=value<=1):
            returnValue("Error: magnitude value must be from 0 to 1 (inclusive.)")
        if not (channel in ['X1','X2','Y1','Y2']):
            returnValue("Error: channel must be either \"X1\" \"Y1\" \"X2\" or \"Y2\"")
        dev=self.selectedDevice(c)
        yield dev.write("SET,%s,%f\r"%(channel,value))
        ans = yield dev.read()
        
        yield dev.write("UPD\r") # updates boards automatically
        upd = yield dev.read()   # on changing any relevant setting
        
        self.voltages[c['device']][port_to_int[channel] + 1] = ans.partition(' to ')[2]
        
        returnValue(ans)

    @setting(203,offset='v',returns='s')
    def set_phase(self,c,offset):
        """Sets the phase offset between the boards (1 and 2.) Usage is set_phase(offset_in_degrees)
The offset is taken modulo 360."""
        offset = offset%360.0
        dev=self.selectedDevice(c)
        yield dev.write("PHS,1,%f\r"%offset)
        yield dev.write("PHS,2,0\r")
        ans1=yield dev.read()
        ans2=yield dev.read()
        
        yield dev.write("UPD\r") # updates boards automatically
        upd = yield dev.read()   # on changing any relevant setting

        self.voltages[c['device']][6] = ans1.partition(' to ')[2]

        returnValue(ans1)

    @setting(204,frequency='v',returns='s')
    def set_frequency(self,c,frequency):
        """Sets the frequency of the two boards. Usage is set_frequency(frequency_in_Hz)
Frequency must be at least 1, and full scale, which is 20MHz * clock_multiplier
where clock_multiplier is the multiplier set with the initialize function."""
        dev=self.selectedDevice(c)

        yield
        if frequency <= 0:
            returnValue("Error: frequency cannot be zero (or less.)")
        if frequency > (self.clock_multiplier * 20000000):
            returnValue("Error: frequency cannot exceed 20MHz * clock_multiplier, where clock_multiplier is the multiplier set with the initialize function. (currently %i)"%self.clock_multiplier)            

        yield dev.write("FRQ,%f\r"%frequency)
        ans = yield dev.read()
        
        yield dev.write("UPD\r") # updates boards automatically
        upd = yield dev.read()   # on changing any relevant setting

        self.voltages[c['device']][5] = ans.partition(' to ')[2]

        returnValue(ans)

    @setting(205,returns='s')
    def identify(self,c):
        """Queries the *IDN? command and returns the response. Usage is identify()"""
        dev=self.selectedDevice(c)
        yield dev.write("*IDN?\r")
        ans = yield dev.read()
        returnValue(ans)

    @setting(206,returns='s')
    def get_is_ready(self,c):
        """Queries the *RDY? command and returns the response. Usage is get_is_ready()"""
        dev=self.selectedDevice(c)
        yield dev.write("*RDY?\r")
        ans = yield dev.read()
        returnValue(ans)

    @setting(207,returns='s')
    def reset(self,c):
        """Performs a master reset. Usage is reset()
Once this is called, initialize must be called again before the device outputs a signal."""
        dev=self.selectedDevice(c)
        yield dev.write("MR\r")
        ans = yield dev.read()
        returnValue(ans)

    @setting(208,returns='s')
    def update_boards(self,c):
        """Signals the boards to update. Usage is update_boards()
This shouldn't be necessary, (the device should do this automatically) but
if the boards aren't responding to changes, try calling this function."""
        dev=self.selectedDevice(c)
        yield dev.write("UPD\r")
        ans = yield dev.read()
        returnValue(ans)

    @setting(209,channel='s',returns=['v','s'])
    def get_channel_voltage(self,c,channel):
        """Queries the device for the voltage on a specific channel. Usage is get_channel_voltage(channel)
Channel must be either "X1" "Y1" "X2" or "Y2\""""
        if not (channel in ["X1","X2","Y1","Y2"]):
                yield
                returnValue("Error: invalid channel. It must be either \"X1\" \"Y1\" \"X2\" or \"Y2\"")
        dev=self.selectedDevice(c)
        yield dev.write("GET,%s\r"%channel)
        ans = yield dev.read()
        if ans.startswith("ER"):
            returnValue(ans)
        else:
            ret = yield float(ans)
            returnValue(ret)

    @setting(210,returns='v')
    def get_phase(self,c):
        """Queries the device fot the phase offset. Usage is get_phase()"""
        dev=self.selectedDevice(c)
        yield dev.write("PHS?\r")
        ans=yield dev.read()
        returnValue(float(ans))

    @setting(211,returns='v')
    def get_frequency(self,c):
        """Queries the device for the frequency setting. Usage is get_frequency()"""
        dev=self.selectedDevice(c)
        yield dev.write("FRQ?\r")
        ans = yield dev.read()
        returnValue(float(ans))

    @setting(8998)
    def read_settings(self,c):
        """Causes the server to query the device for its current settings. Usage is read_settings()
It's only necessary to call this once on startup, as the server keeps track of the changes made."""
        dev=self.selectedDevice(c)
        for n in range(4):
            yield dev.write("GET,%s\r"%int_to_port[n])
            ans = yield dev.read()
            self.voltages[c['device']][n+1] = str(ans)
            
        yield dev.write("FRQ?\r")
        frq = yield dev.read()
        self.voltages[c['device']][5]=str(frq)+' HZ'
        
        yield dev.write("PHS?\r")
        phs = yield dev.read()
        self.voltages[c['device']][6]=str(phs)

    @setting(8999,returns='**s')
    def get_settings(self,c):
        """Returns the settings for all active devices. Usage is get_settings()
Yields a list of form [[port,X1_voltage,Y1_voltage,X2_voltage,Y2_voltage,frequency,phase], ... ]"""
        ret = yield self.voltages
        returnValue(ret)
        
        
        






__server__ = AD5764AcboxServer()
if __name__ == '__main__':
    from labrad import util
    util.runServer(__server__)
