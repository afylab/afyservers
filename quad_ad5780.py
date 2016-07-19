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
name = Arduino DCBOX QUAD AD5780 server
version = 1.1
description = Arduino DCBOX QUAD AD5780 control

[startup]
cmdline = %PYTHON% %FILE%
timeout = 20

[shutdown]
message = 987654321
timeout = 20
### END NODE INFO
"""

from labrad.server import setting, Signal
from labrad.devices import DeviceServer,DeviceWrapper
from twisted.internet.defer import inlineCallbacks, returnValue
import labrad.units as units
from labrad.types import Value

class serverInfo(object):
    def __init__(self):
        self.deviceName = "Arduino QUAD DC Box"
        self.serverName = "dcbox_quad_ad5780"

    def getDeviceName(self,comPort):
        return "%s (%s)"%(self.serverName,comPort)

class QuadAD5780DcboxWrapper(DeviceWrapper):

    @inlineCallbacks
    def connect(self, server, port):
        """Connect to a device."""
        print 'connecting to "%s" on port "%s"...' % (server.name, port),
        self.server = server
        self.ctx = server.context()
        self.port = port
        p = self.packet()
        TIMEOUT = Value(5,'s')
        BAUD    = 115200
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
    def do_init(self):
        yield self.packet().write("INITIALIZE\r").send()
        p=self.packet()
        ans = yield p.send()

        done = False # wait for "INITIALIZATION COMPLETE"
        while not done:
            p=self.packet()
            p.read_line()
            resp=yield p.send()
            #print("resp %s"%resp.read_line)
            if resp.read_line == "INITIALIZATION COMPLETE":
                done = True

        returnValue(resp.read_line)

    @inlineCallbacks
    def identify(self):
        yield self.packet().write("*IDN?\r").send()
        p=self.packet()
        p.read_line()
        ans = yield p.send()
        returnValue(ans.read_line)

    @inlineCallbacks
    def get_is_ready(self):
        yield self.packet().write("*RDY?\r").send()
        p=self.packet()
        p.read_line()
        ans = yield p.send()
        returnValue(ans.read_line)

    @inlineCallbacks
    def set_voltage(self,port,value):
        yield self.packet().write("SET,%i,%f\r"%(port,value)).send()
        p=self.packet()
        p.read_line()
        ans = yield p.send()
        returnValue(ans.read_line)

    @inlineCallbacks
    def get_voltage(self,port):
        yield self.packet().write("GET_DAC,%i\r"%port).send()
        p=self.packet()
        p.read_line()
        ans = yield p.send()
        returnValue(ans.read_line)

    @inlineCallbacks
    def ramp1(self,port,ivoltage,fvoltage,steps,delay):
        yield self.packet().write("RAMP1,%i,%f,%f,%i,%i\r"%(port,ivoltage,fvoltage,steps,delay)).send()
        p=self.packet()
        p.read_line()
        ans = yield p.send()
        returnValue(ans.read_line)

    @inlineCallbacks
    def ramp2(self,port1,port2,ivoltage1,ivoltage2,fvoltage1,fvoltage2,steps,delay):
        yield self.packet().write("RAMP2,%i,%i,%f,%f,%f,%f,%i,%i\r"%(port1,port2,ivoltage1,ivoltage2,fvoltage1,fvoltage2,steps,delay))
        p=self.packet()
        p.read_line()
        ans = yield p.send()
        returnValue(ans.read_line)

    @inlineCallbacks
    def clearOutput(self):
        p=self.packet()
        p.read()
        ans = yield p.send()
        returnValue(ans.read)


class QuadAD5764DcboxServer(DeviceServer):
    info          = serverInfo()
    name          = info.serverName
    deviceName    = info.deviceName
    deviceWrapper = QuadAD5780DcboxWrapper

    # signals (server prefix 702000)
    sPrefix = 702000
    sigChannelVoltageChanged = Signal(sPrefix+0,'signal__channel_voltage_changed','*s')
    sigInitDone              = Signal(sPrefix+1,'signal__init_done','s')
    sigRamp1Started          = Signal(sPrefix+2,'signal__ramp_1_started','*s')
    sigRamp2Started          = Signal(sPrefix+3,'signal__ramp_2_started','*s')

    ports = [0,1,2,3]

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
        devs = []
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
        yield dev.connect(server,port)



    @setting(102)
    def initialize(self,c):
        dev=self.selectedDevice(c)
        dev.clearOutput()
        ans = yield dev.do_init()
        self.sigInitDone(ans)

        # read new voltages & send signals post-init. Should all be zero.
        for port in self.ports:
            ans=yield dev.get_voltage(port)
            self.sigChannelVoltageChanged([str(port),str(ans)])

    @setting(103,port='i',voltage='v',returns='s')
    def set_voltage(self,c,port,voltage):
        #print(dir(c))
        if not (port in self.ports):
            returnValue("Error: invalid port. It must be 0,1,2, or 3")
        if (voltage > 10) or (voltage < -10):
            returnValue("Error: invalid voltage. It must be between -10 and 10.")
        dev=self.selectedDevice(c)
        dev.clearOutput()
        ans = yield dev.set_voltage(port,voltage)
        self.sigChannelVoltageChanged([str(port),ans.partition(' TO ')[2][:-1]])
        returnValue(ans)

    @setting(104,port='i',returns='s')
    def get_voltage(self,c,port):
        if not (port in self.ports):
            returnValue("Error: invalid port. It must be 0,1,2, or 3")
        dev = self.selectedDevice(c)
        dev.clearOutput()
        ans = yield dev.get_voltage(port)
        returnValue(ans)

    @setting(105,port='i',ivoltage='v',fvoltage='v',steps='i',delay='i',returns='s')
    def ramp1(self,c,port,ivoltage,fvoltage,steps,delay):

        if not (port in self.ports):
            returnValue("Error: invalid port. It must be 0,1,2, or 3")
        if (ivoltage>10) or (ivoltage<-10):
            returnValue("Error: invalid ivoltage. It must be between -10 and 10.")
        if (fvoltage>10) or (fvoltage<-10):
            returnValue("Error: invalid fvoltage. It must be between -10 and 10.")
        if steps<1:
            returnValue("Error: invalid steps value. It must be at least 1.")
        if delay <= 0:
            returnValue("Error: invalid delay value. It must be greater than zero.")

        dev = self.selectedDevice(c)
        dev.clearOutput()
        ans = yield dev.ramp1(port,ivoltage,fvoltage,steps,delay)
        self.sigRamp1Started([str(port),str(ivoltage),str(fvoltage),str(steps),str(delay)])
        returnValue(ans)

    @setting(106,port1='i',port2='i',ivoltage1='v',ivoltage2='v',fvoltage1='v',fvoltage2='v',steps='i',delay='i',returns='s')
    def ramp2(self,c,port1,port2,ivoltage1,ivoltage2,fvoltage1,fvoltage2,steps,delay):
        if not (port1 in self.ports):
            returnValue("Error: invalid port1. It must be 0,1,2, or 3")
        if (ivoltage1>10) or (ivoltage1<-10):
            returnValue("Error: invalid ivoltage1. It must be between -10 and 10.")
        if (fvoltage1>10) or (fvoltage1<-10):
            returnValue("Error: invalid fvoltage1. It must be between -10 and 10.")
        if not (port2 in self.ports):
            returnValue("Error: invalid port2. It must be 0,1,2, or 3")
        if (ivoltage2>10) or (ivoltage2<-10):
            returnValue("Error: invalid ivoltage2. It must be between -10 and 10.")
        if (fvoltage2>10) or (fvoltage2<-10):
            returnValue("Error: invalid fvoltage2. It must be between -10 and 10.")
        if steps<1:
            returnValue("Error: invalid steps value. It must be at least 1.")
        if delay <= 0:
            returnValue("Error: invalid delay value. It must be greater than zero.")

        dev = self.selectedDevice(c)
        dev.clearOutput()
        ans = yield dev.ramp2(port1,port2,ivoltage1,ivoltage2,fvoltage1,fvoltage2,steps,delay)
        self.sigRamp2Started([str(port1),str(port2),str(ivoltage1),str(ivoltage2),str(fvoltage1),str(fvoltage2),str(steps),str(delay)])
        returnValue(ans)

    @setting(107,returns='s')
    def id(self,c):
        dev = self.selectedDevice(c)
        dev.clearOutput()
        ans = yield dev.identify()
        returnValue(ans)

    @setting(108,returns='s')
    def ready(self,c):
        dev = self.selectedDevice(c)
        dev.clearOutput()
        ans = yield dev.get_is_ready()
        returnValue(ans)

    @setting(600)
    def send_voltage_signals(self,c):
        dev = self.selectedDevice(c)
        dev.clearOutput()
        for port in self.ports:
            ans=yield dev.get_voltage(port)
            #print(ans)
            self.sigChannelVoltageChanged([str(port),str(ans)])
        
    @setting(9001,v='v')
    def do_nothing(self,c,v):
        pass

    
__server__ = QuadAD5764DcboxServer()

if __name__ == '__main__':
    from labrad import util
    util.runServer(__server__)













