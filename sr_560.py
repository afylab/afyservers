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
name = SR560 Low-Noise Preamplifier
version = 1.0
description =
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
serial_server_name = platform.node() + '_serial_server'

from labrad.server import setting
from labrad.devices import DeviceServer,DeviceWrapper
from twisted.internet.defer import inlineCallbacks, returnValue
import labrad.units as units
from labrad.types import Value

TIMEOUT = Value(5,'s')
BAUD    = 9600

class SR560Wrapper(DeviceWrapper):

    @inlineCallbacks
    def connect(self, server, port):
        """Connect to a device."""
        print 'connecting to "%s" on port "%s"...' % (server.name, port),
        self.server = server
        self.ctx = server.context()
        self.port = port
        p = self.packet()
        p.open(port)
        print 'opened on port "%s"' %self.port
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
        

class SR560Server(DeviceServer):
    name = 'sr560_preamp'
    deviceName = 'SR560 Preamplifier'
    deviceWrapper = SR560Wrapper

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
        # reg = self.client.registry
        # p = reg.packet()
        # p.cd(['', 'Servers', 'Heat Switch'], True)
        # p.get('Serial Links', '*(ss)', key='links')
        # ans = yield p.send()
        # self.serialLinks = ans['links']
        reg = self.reg
        yield reg.cd(['', 'Servers', 'SR560 Preamp', 'Links'], True)
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
        # for name, port in self.serialLinks:
        # if name not in self.client.servers:
        # continue
        # server = self.client[name]
        # ports = yield server.list_serial_ports()
        # if port not in ports:
        # continue
        # devName = '%s - %s' % (name, port)
        # devs += [(devName, (server, port))]
        # returnValue(devs)
        for name, (serServer, port) in self.serialLinks.items():
            if serServer not in self.client.servers:
                continue
            server = self.client[serServer]
            print server
            print port
            ports = yield server.list_serial_ports()
            print ports
            if port not in ports:
                continue
            devName = '%s - %s' % (serServer, port)
            devs += [(devName, (server, port))]

       # devs += [(0,(3,4))]
        returnValue(devs)
    
    @setting(100)
    def connect(self,c,server,port):
        dev=self.selectedDevice(c)
        yield dev.connect(server,port)

    #Operates Amplifier Blanking
    @setting(201, e='i')
    def blank(self,c,e):
        dev=self.selectedDevice(c)
        yield dev.write("BLINK %i\r\n"%e)

    @setting(202, coupling='i')
    def set_inputCoupling(self,c,coupling):
        dev=self.selectedDevice(c)
        yield dev.write("CPLG%i\r\n"%coupling)

    @setting(203, reserve='i')
    def set_dynamicReserve(self,c,reserve):
        dev=self.selectedDevice(c)
        yield dev.write("DYNR %i\r\n"%reserve)

    @setting(204, mode='i')
    def set_filterMode(self,c,mode):
        dev=self.selectedDevice(c)
        yield dev.write("FLTM %i\r\n"%mode)

    @setting(205,gain='i')
    def set_gain(self,c,gain):
        dev=self.selectedDevice(c)
        yield dev.write("GAIN %i\r\n"%gain)

    # highpass filter frequency
    @setting(206, frequency='v')
    def set_hFilterFrequency(self,c,frequency):    
        dev=self.selectedDevice(c)
        yield dev.write("HFRQ%i\r\n"%frequency)

    @setting(207, sense='i')
    def set_signalSense(self,c,sense):
        dev=self.selectedDevice(c)
        yield dev.write("INVT %i\r\n"%sense)

    @setting(208)
    def listen_all(self,c):
        dev=self.selectedDevice(c)
        yield dev.write("LALL\r\n")

    # lowpass filter frequency
    @setting(209, frequency='v')
    def set_lFilterFrequency(self,c,frequency):
        dev=self.selectedDevice(c)
        yield dev.write("LFRQ %i\r\n"%frequency)

    #resets overload for 1/2 second
    @setting(210)
    def reset_overload(self,c):
        dev=self.selectedDevice(c)
        yield dev.write("ROLD\r\n")

    @setting(211, source='i')
    def set_inputSource(self,c,source):
        dev=self.selectedDevice(c)
        yield dev.write("SRCE %i\r\n"%source)

    @setting(212, status='i')
    def set_vernierGainStatus(self,c,status):
        dev=self.selectedDevice(c)
        yield dev.write("UCAL %i\r\n"%status)

    @setting(213, gain='i')
    def set_vernierGain(self,c,gain):
        dev=self.selectedDevice(c)
        yield dev.write("UGGN %i\r\n"%gain)

    @setting(214)
    def unlisten(self,c):
        dev=self.selectedDevice(c)
        yield dev.write("UNLS\r\n")

    @setting(215)
    def reset(self,c):
        dev=self.selectedDevice(c)
        yield dev.write("*RST\r\n")
        
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

    
__server__ = SR560Server()

if __name__ == '__main__':
    from labrad import util
    util.runServer(__server__)