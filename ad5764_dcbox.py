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
name = DCBOX Arduino
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

global blacklisted_ports
blacklisted_ports = ['COM1','COM8']

from labrad.server import setting
from labrad.devices import DeviceServer,DeviceWrapper
from twisted.internet.defer import inlineCallbacks, returnValue
import labrad.units as units
from labrad.types import Value

TIMEOUT = Value(5,'s')
BAUD    = 115200

class AD5764DcboxWrapper(DeviceWrapper):
    channels = [0,1,2,3,4,5,6,7]

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

    @inlineCallbacks
    def set_voltage(self,channel,voltage):
        if channel not in self.channels:
            print("ERROR: invalid channel")
            raise
        if abs(voltage)>10.0:
            print("ERROR: invalid voltage. Must be between -10.0 and 10.0")
            raise
        yield self.packet().write("SET,%i,%f\r"%(channel,voltage)).send()
        p=self.packet()
        p.read_line()
        ans = yield p.send()
        returnValue(ans.read_line)
        


class AD5764DcboxServer(DeviceServer):
    name = 'ad5764_dcbox'
    deviceName = 'Arduino Dcbox'
    deviceWrapper = AD5764DcboxWrapper

    channels = [0,1,2,3,4,5,6,7]


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
        #yield reg.cd(['','Servers','DACBOX','COM'],True)
        #self.port = yield reg.get('port') # Port# for DCBOX
        self.serialLinks = {} # {'dcbox':['majorana_serial_server',self.port]}
        print('SERVERS:',self.client.servers.keys())
    
    @inlineCallbacks
    def findDevices(self):
        server = self.client['majorana_serial_server']
        ports = yield server.list_serial_ports()

        devs = []
        self.voltages = []
        global blacklisted_ports
        for port in ports:
            if not (port in blacklisted_ports):
                devs.append(('dcbox (%s)'%port,(server,port)))
                self.voltages.append([port]+['unknown' for pos in range(8)])
        returnValue(devs)

    
    @setting(100)
    def connect(self,c,server,port):
        dev=self.selectedDevice(c)
        yield dev.connect(server,port)

    @setting(200,port='i',voltage='v',returns='s')
    def set_voltage(self,c,port,voltage):
        #print(dir(c))
        if not (port in range(8)):
            returnValue("Error: invalid port number.")
            return
        if (voltage > 10) or (voltage < -10):
            returnValue("Error: invalid voltage. It must be between -10 and 10.")
            return
        dev=self.selectedDevice(c)
        ans=yield dev.set_voltage(port,voltage)

        # port+1 since the first entry is the COM number
        self.voltages[c['device']][port+1] = str(voltage)
        
        returnValue(ans)

    @setting(8999)
    def get_voltages(self,c):
        ret = yield self.voltages
        returnValue(ret)
        
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

    
__server__ = AD5764DcboxServer()

if __name__ == '__main__':
    from labrad import util
    util.runServer(__server__)













