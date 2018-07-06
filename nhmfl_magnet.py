# Copyright [2017 Sasha Zibrov]
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
name = NHMFL Resistive Magnet
version = 0.1
description = Resistive Magnet power supply control

[startup]
cmdline = %PYTHON% %FILE%
timeout = 20

[shutdown]
message = 987654321
timeout = 20
### END NODE INFO
"""

from labrad.server import setting, Signal
from labrad.devices import DeviceServer, DeviceWrapper
from twisted.internet.defer import inlineCallbacks, returnValue
import labrad.units as units
from labrad.types import Value
import time



def current2field(current):
    field = 0.90418 * current - 6.07e-7 * current**3  # for cell 12
    return field


def field2current(field):
    current = 1.10612 * field + 8.02e-7 * field**3
    return current



class serverInfo(object):
    def __init__(self):
        self.deviceName = 'NHMFL Resistive Magnet'
        self.serverName = "nhmfl_rmag"

    def getDeviceName(self,comPort):
        return "%s (%s)"%(self.serverName, comPort)

class nhmflResistiveMagnetWrapper(DeviceWrapper):
    @inlineCallbacks
    def connect(self, server, port):
        """Connect to a device"""
        print("Connecting to '%s' on port '%s'"%(server.name,port))
        self.server = server
        self.ctx    = server.context()
        self.port   = port

        p = self.packet()
        p.open(port)
        print("opened on port '%s'"%port)

        self.baud = 115200  #updated from 9600
        self.timeout = Value(2,'s')
        self.parity = 'E'
        self.data_bits = 7
        self.stop_bits = 1

        p.baudrate(self.baud) # set BAUDRATE
        p.read()                  # clear buffer
        p.timeout(self.timeout)   # sets timeout
        p.parity(self.parity)
        p.bytesize(self.data_bits)
        p.stopbits(self.stop_bits)

        print("Connected.")
        yield p.send()

    def packet(self):
        """Create a packet in our private context"""
        return self.server.packet(context=self.ctx)

    def shutdown(self):
        """Disconnect from the serial port when we shut down"""
        return self.packet().close().send()

    @inlineCallbacks
    def status(self):
        yield self.packet().write("s").send()
        p = self.packet()
        p.read_line()
        ans = yield p.send()
        returnValue(ans.read_line)

    @inlineCallbacks
    def limits(self):
        yield self.packet().write("l").send()
        p = self.packet()
        p.read_line()
        ans = yield p.send()
        returnValue(ans.read_line)

    @inlineCallbacks
    def pause(self):
        yield self.packet().write("p").send()

    @inlineCallbacks
    def unpause(self):
        yield self.packet().write("u").send()

    @inlineCallbacks
    def fastramp(self):
        yield self.packet().write("f").send()

    @inlineCallbacks
    def setpoint(self, current):
        '''
        sets the setpoint in kA
        '''
        yield self.packet().write("c{}\n".format(current)).send()

    @inlineCallbacks
    def ramprate(self, rate):
        '''
        sets the ramp rate in A/s
        '''
        yield self.packet().write("r{}\n".format(rate)).send()


class nhmflResistiveMagnetServer(DeviceServer):
    info          = serverInfo()
    name          = info.serverName
    deviceName    = info.deviceName
    deviceWrapper = nhmflResistiveMagnetWrapper

    @inlineCallbacks
    def initServer(self):
        print("Server <%s> of type <%s>"%(self.name,self.deviceName))
        self.reg = self.client.registry()
        yield self.loadConfigInfo()
        print(self.serialLinks)
        yield DeviceServer.initServer(self)

    @inlineCallbacks
    def loadConfigInfo(self):
        """Loads port/device info from the registry"""
        yield self.reg.cd(['','Servers',self.name,'Links'],True)
        dirs,keys = yield self.reg.dir()
        print("Found devices: %s"%(keys,))
        p   = self.reg.packet()
        for k in keys:p.get(k,key=k)
        ans = yield p.send()
        self.serialLinks = dict((k, ans[k]) for k in keys)

    @inlineCallbacks
    def findDevices(self):
        """Gets list of devices whose ports are active (available devices.)"""
        devs=[]
        for name,(serialServer,port) in self.serialLinks.items():
            if serialServer not in self.client.servers:
                print("Error: serial server (%s) not found. Device '%s' on port '%s' not active."%(serialServer,name,port))
                continue
            ports = yield self.client[serialServer].list_serial_ports()
            if port not in ports:
                continue
            devs += [(self.info.getDeviceName(port),(self.client[serialServer],port))]
        returnValue(devs)

    @setting(100)
    def connect(self,c,server,port):
        dev=self.selectedDevice(c)
        yield dev.connect(server, port)


    @setting(101, returns='*ivv')
    def status(self, c):
        dev = self.selectedDevice(c)
        ans = yield dev.status()
        ans = str(ans)
        statusbyte = int(ord(ans[1]))
        tmp = str(ans)[2:-1].split(",")
        field = current2field(float(tmp[0]))
        statusbits = []
        for i in xrange(7):
            statusbits.append((statusbyte >> i) & 1)

        if len(tmp) == 2:
            update = float(tmp[1])
        else:
            update = 0.0
        returnValue((statusbits, field, update))


    @setting(202, field='v', returns='')
    def setpoint(self, c, field):
        '''
        Set the current setpoint based on field, kA
        '''
        dev = self.selectedDevice(c)
        current = field2current(field)
        ans = yield dev.setpoint(current)

    @setting(203, rate='v', returns='')
    def rate(self, c, rate):
        '''
        Set ramp rate in A/s
        '''
        dev = self.selectedDevice(c)
        yield dev.ramprate(rate)

    @setting(204, returns='*v')
    def limits(self, c):
        dev = self.selectedDevice(c)
        ans = yield dev.limits()
        ans = str(ans).split(',')
        returnValue(ans)

    @setting(205, returns='')
    def pause(self, c):
        dev = self.selectedDevice(c)
        yield dev.pause()

    @setting(206, returns='')
    def unpause(self, c):
        dev = self.selectedDevice(c)
        yield dev.unpause()

    @setting(207, field ='v', ramprate='v', returns='b')
    def goto(self, c, field, ramprate=None):
        dev = self.selectedDevice(c)
        yield self.unpause(c)
        time.sleep(0.1)
        if ramprate is not None:
            yield self.rate(c, ramprate)
        yield self.setpoint(c, field)
        time.sleep(0.5)
        ramping = True
        while ramping:
            statusbits, field, upd = yield self.status(c)
            ramping = (statusbits[2] or statusbits[3])==False
            time.sleep(1)
        returnValue(True)

    @setting(301, returns='b')
    def isramping(self, c):
        dev = self.selectedDevice(c)
        statusbits = (yield self.status(c))[0]
        isramp = False
        if (statusbits[2]==1) or (statusbits[3]==1):
            isramp = True
        returnValue(isramp)




__server__ = nhmflResistiveMagnetServer()

if __name__ == '__main__':
    from labrad import util
    util.runServer(__server__)
