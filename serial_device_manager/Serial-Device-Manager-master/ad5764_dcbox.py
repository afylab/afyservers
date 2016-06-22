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
name = Arduino DC box
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
serial_server_name = (platform.node()+'_serial_server').lower().replace(' ','_').replace('-','_')





from labrad.server import setting
from labrad.devices import DeviceServer,DeviceWrapper
from twisted.internet.defer import inlineCallbacks, returnValue
import labrad.units as units
from labrad.types import Value
TIMEOUT = Value(5,'s')
BAUD    = 115200


# this is the server name under which devices of this type are stored in the registry.
global serverNameAD5764_DCBOX; serverNameAD5764_DCBOX = "ad5764_dcbox"

class arduinoDCBoxWrapper(DeviceWrapper):

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

        p.baudrate(BAUD)   # set BAUDRATE
        p.read()           # clear buffer
        p.timeout(TIMEOUT) # sets timeout

        print("Connected.")
        yield p.send()

    def packet(self):
        """Create a packet in our private context"""
        return self.server.packet(context=self.ctx)

    def shutdown(self):
        """Disconnect from the serial port when we shut down"""
        return self.packet().close().send()

    @inlineCallbacks
    def write(self, code):
        """Write a data value to the DCBOX"""
        yield self.packet().write(code).send()

    @inlineCallbacks
    def read(self):
        """Read a response line from the DCBOX"""
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
        if channel not in range(8):
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

class arduinoDCBoxServer(DeviceServer):
    name          = 'ad5764_dcbox'
    deviceName    = 'Arduino DC box'
    deviceWrapper = arduinoDCBoxWrapper
    voltages      = {}

    def trackVoltage(self,device,ports,value):
        if not (device in self.voltages.keys()):
            self.voltages.update([[device,['unknown' for port in range(8)]]])
        for port in ports:
            self.voltages[device][port] = value

    @inlineCallbacks
    def initServer(self):
        print 'Loading config from registry...',
        self.reg = self.client.registry()
        yield self.loadConfigInfo()
        print 'Finished.'
        print("Serial links found: %s"%str(self.serialLinks))
        yield DeviceServer.initServer(self)

    @inlineCallbacks
    def loadConfigInfo(self):
        """Loads port/device info from the registry"""

        reg = self.reg
        yield reg.cd(['', 'Servers', serverNameAD5764_DCBOX, 'Links'], True)
        dirs, keys = yield reg.dir()
        p = reg.packet()
        print " created packet"
        print "printing all the keys",keys
        for k in keys:
            print "k=",k
            p.get(k, key=k)
            
        ans = yield p.send()
        #print "ans=",ans
        self.serialLinks = dict((k, ans[k]) for k in keys)

    @inlineCallbacks
    def findDevices(self):
        """Gets list of devices whose ports are active (available devices.)"""
        devs = []

        for name, (serialServer, port) in self.serialLinks.items():
            if serialServer not in self.client.servers:
                print("Error: serial server (%s) not found. Device '%s' on port '%s' not active."%(serialServer,name,port))
                continue

            print('\n')
            ports = yield self.client[serialServer].list_serial_ports()
            print("Trying device %s on server %s with port %s"%(name,serialServer,port))
            if port not in ports:
                print("Device %s on server %s with port %s not available: port %s is not active."%(name,serialServer,port,port))
                continue

            devName = '%s (%s)'%(self.name,port)
            devs += [(devName, (self.client[serialServer],port))]
            #self.voltages.update([[devName,['unknown' for p in range(8)]]])

        returnValue(devs)

    @setting(100)                      # internal function
    def connect(self,c,server,port):   # for connecting to
        dev=self.selectedDevice(c)     # devices.
        yield dev.connect(server,port) # 

    @setting(200,port='i',voltage='v',returns='s')                                # setting 200
    def set_voltage(self,c,port,voltage):                                         # Set voltage
        """Sets the voltage of one port. set_voltage(port,voltage)"""             # 
        if not (port in range(8)):                                                # Sets the voltage of one porton the currently selected DCBOX device.
            returnValue("Error: invalid port. Port must be from 0 to 7.")         # input  : (voltage, port)
            return                                                                # voltage: float or int in range [-10,10] in Volts
        if (voltage > 10) or (voltage < -10):                                     # port   : int in range [0,7], corresponding to the port numbers on the front of the DCBOX.
            returnValue("Error: invalid voltage. It must be between -10 and 10.") # 
            return                                                                # 
        dev=self.selectedDevice(c)                                                # 
        ans=yield dev.set_voltage(port,voltage)                                   # 
        yield self.trackVoltage(c['device'],[port],str(round(voltage,4)))         # 
        returnValue(ans)                                                          # 

    @setting(300,voltage='v',returns='s')                                         # setting 300
    def set_all(self,c,voltage):                                                  # Set all
        """Sets the voltage of all ports. set_all(voltage)"""                     # 
        if (voltage > 10) or (voltage < -10):                                     # Sets the voltage for all ports on the currently selected DCBOX device.
            returnValue("Error: invalid voltage. It must be between -10 and 10.") # input (voltage): float or int in range[-10,10] in Volts.
            return                                                                # 
        dev  = self.selectedDevice(c)                                             # 
        resp = []                                                                 # 
        for port in range(8):                                                     # 
            ans = yield dev.set_voltage(port,voltage)                             #
            resp.append(ans)                                                      #
        yield self.trackVoltage(c['device'],range(8),str(round(voltage,4)))       #
        returnValue("All PORTS %s"%resp[0][6:])                                   #

    @setting(400)
    def read_voltages(self,c):
        """Queries the DC box for the voltages set on all ports and updates internal tracker"""
        dev = self.selectedDevice(c)
        yield dev.write("NOP\r\n") # clear
        yield dev.read()           # buffer
        for port in range(8):
            yield dev.write("GET_DAC,%i\r\n"%port)
            ans = yield dev.read()
            self.trackVoltage(c['device'],[port],ans)


    @setting(500,returns='*s')                       # Returns list of voltages for currently selected device
    def get_voltages(self,c):                        # [port_0_voltage, port_1_voltage, ... , port_7_voltage]
        try:                                         #
            ret = yield self.voltages[c['device']]   #
        except:                                      #
            ret = ['unknown' for p in range(8)]      #
            self.trackVoltage(c['device'],[],0.0)    # 
        returnValue(self.voltages[c['device']])      # 

    @setting(501,port='i',returns='s')                   # Returns the voltage on port number 'port' on currently selected device
    def get_voltage(self,c,port):                        # 
        try:                                             # 
            val = yield self.voltages[c['device']][port] # 
        except:                                          #
            val = 'unknown'                              #
            self.trackVoltage(c['device'],[],0.0)        #
        returnValue(val)                                 #

    @setting(600,returns='s')              # Low level commands
    def read(self,c):                      # reads output directly from DCBOX com
        dev = self.selectedDevice(c)       # 
        ret = yield dev.read()             # These 3 (600,601,602) commands shouldn't be used unless necessary
        returnValue(ret)                   # For instance, if there is new functionality in the DCBOX for which there aren't specific settings in this server.

    @setting(601,phrase='s')               # Writes a string to the DCBOX com
    def write(self,c,phrase):              # 
        dev = self.selectedDevice(c)       # 
        yield dev.write(phrase)            # 

    @setting(602,phrase='s',returns='s')   # Writes a string to the DCBOX com, then reads the reply
    def query(self,c,phrase):              # 
        dev=self.selectedDevice(c)         # 
        yield dev.write(phrase)            # 
        ret = yield dev.read()             # 
        returnValue(ret)                   # 

    @setting(9000)          # Here for testing stuff
    def test_do_nothing(self,c): # Surprisingly, this function
        yield True          # does nothing at all

    @setting(9001,returns='v')    # Here for testing stuff
    def test_return_zero(self,c): # This function returns zero
        resp = yield 0.0          #
        returnValue(resp)         #

    @setting(9002,inp='v')             # Also here for testing
    def test_accept_float(self,c,inp): # Accepts float input
        yield True                     # But does nothing





__server__ = arduinoDCBoxServer()

if __name__ == '__main__':
    from labrad import util
    util.runServer(__server__)