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
name = DCBOX QUAD AD5780
version = 1.0
description = DCBOX control

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
serial_server_name = (platform.node() + "_serial_server").replace("-","_").replace(' ','_').lower()

from labrad.server import setting
from labrad.devices import DeviceServer,DeviceWrapper
from twisted.internet.defer import inlineCallbacks, returnValue
import labrad.units as units
from labrad.types import Value

TIMEOUT = Value(5,'s')
BAUD    = 115200

global serverNameQUAD_AD5780; serverNameQUAD_AD5780 = 'ad5780_dcbox'

class QuadAD5780DcboxWrapper(DeviceWrapper):
    channels = [0,1,2,3]

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
        """Create a packet in our private context."""
        return self.server.packet(context=self.ctx)

    def shutdown(self):
        """Disconnect from the serial port when we shut down."""
        return self.packet().close().send()

    @inlineCallbacks
    def write(self, code):
        """Write a data value to the heat switch."""
        yield self.packet().write(code).send()

    @inlineCallbacks
    def read(self):
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
        


class QuadAD5764DcboxServer(DeviceServer):
    name          = serverNameQUAD_AD5780
    deviceName    = 'Arduino Dcbox'
    deviceWrapper = QuadAD5780DcboxWrapper

    channels = [0,1,2,3]


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
        """Load configuration information from the registry."""

        reg = self.reg
        yield reg.cd(['', 'Servers', serverNameQUAD_AD5780, 'Links'], True)
        dirs, keys = yield reg.dir()
        p = reg.packet()
        print " created packet"
        print "printing all the keys",keys
        for k in keys:
            print "k=",k
            p.get(k, key=k)
            
        ans = yield p.send()
        print "ans=",ans
        self.serialLinks = dict((k, ans[k]) for k in keys)


    @inlineCallbacks
    def findDevices(self):
        """Find available devices from list stored in the registry."""
        devs = []
        self.voltages = []
        dev_number = 0

        for name, (serialServer, port) in self.serialLinks.items():
            if serialServer not in self.client.servers:
                print("Error: serial server (%s) not found. Device '%s' on port '%s' not active."%(serialServer,name,port))
                continue

            ports = yield self.client[serialServer].list_serial_ports()
            print("Trying device %s on server %s with port %s"%(name,serialServer,port))
            if port not in ports:
                print("Device %s on server %s with port %s not available: port %s is not active."%(name,serialServer,port,port))
                continue
            print("Device %s with port %s on server %s succesfully connected"%(name,port,serialServer))

            devName = '%s (%s)' % (self.name, port)
            devs += [(devName, (self.client[serialServer], port))]
            self.voltages.append([port]+['unknown' for pos in range(4)])
            dev_number += 1

       # devs += [(0,(3,4))]
        returnValue(devs)

    
    @setting(100)
    def connect(self,c,server,port):
        dev=self.selectedDevice(c)
        yield dev.connect(server,port)

    @setting(102)
    def initialize(self,c):
        dev=self.selectedDevice(c)
        yield dev.write("INITIALIZE\r")

    @setting(103,port='i',voltage='v',returns='s')
    def set_voltage(self,c,port,voltage):
        #print(dir(c))
        if not (port in range(4)):
            returnValue("Error: invalid port number.")
            return
        if (voltage > 10) or (voltage < -10):
            returnValue("Error: invalid voltage. It must be between -10 and 10.")
            return
        dev=self.selectedDevice(c)
        yield dev.write("SET,%i,%f\r"%(port,voltage))
        ans = yield dev.read()
        returnValue(ans)


    @setting(104,port='i',returns='s')
    def get_voltage(self,c,port):
        dev=self.selectedDevice(c)
        if not (port in range(4)):
            returnValue("Error: invalid port number.")
            return
        yield dev.write("GET_DAC,%i\r"%port)
        ans = yield dev.read()
        returnValue(ans)

    @setting(105,port='i',ivoltage='v',fvoltage='v',steps='i',delay='i',returns='s')
    def ramp1(self,c,port,ivoltage,fvoltage,steps,delay):
        dev=self.selectedDevice(c)
        yield dev.write("RAMP1,%i,%f,%f,%i,%i\r"%(port,ivoltage,fvoltage,steps,delay))
        ans = yield dev.read()
        returnValue(ans)

    @setting(106,port1='i',port2='i',ivoltage1='v',ivoltage2='v',fvoltage1='v',fvoltage2='v',steps='i',delay='i',returns='s')
    def ramp2(self,c,port1,port2,ivoltage1,ivoltage2,fvoltage1,fvoltage2,steps,delay):
        dev=self.selectedDevice(c)
        yield dev.write("RAMP2,%i,%i,%f,%f,%f,%f,%i,%i\r"%(port1,port2,ivoltage1,ivoltage2,fvoltage1,fvoltage2,steps,delay))
        ans = yield dev.read()
        returnValue(ans)

    @setting(107,returns='s')
    def id(self,c):
        dev=self.selectedDevice(c)
        yield dev.write("*IDN?\r")
        ans = yield dev.read()
        returnValue(ans)

    @setting(108,returns='s')
    def ready(self,c):
        dev=self.selectedDevice(c)
        yield dev.write("*RDY?\r")
        ans = yield dev.read()
        returnValue(ans)
        
    @setting(9001,v='v')
    def do_nothing(self,c,v):
        pass
    @setting(9002)
    def read(self,c):
        dev=self.selectedDevice(c)
        ret=yield dev.read()
        returnValue(ret)
    @setting(9003)
    def write(self,c,phrase):
        dev=self.selectedDevice(c)
        yield dev.write(phrase)
    @setting(9004)
    def query(self,c,phrase):
        dev=self.selectedDevice(c)
        yield dev.write(phrase)
        ret = yield dev.read()
        returnValue(ret)

    
__server__ = QuadAD5764DcboxServer()

if __name__ == '__main__':
    from labrad import util
    util.runServer(__server__)













