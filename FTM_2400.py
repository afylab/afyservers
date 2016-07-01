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
name = FTM Deposition Monitor
version = 1.0
description = FTM Deposition Monitor Controller

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

#TIMEOUT = Value(0.011,'s') 
# This server does not use timeout because the device doesn't implement stadard message termination. 
BAUD    = 19200
BYTESIZE = 8
STOPBITS = 1
PARITY = 0

class FTMWrapper(DeviceWrapper):

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
        #p.timeout(TIMEOUT)
        #No timeout means checks for stored characters then immediately stops waiting. 
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


class FTMServer(DeviceServer):
    name             = 'FTM_Server'
    deviceName       = 'FTM 2400 Deposition Controller'
    deviceWrapper    = FTMWrapper

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
        yield reg.cd(['', 'Servers', 'FTM 2400', 'Links'], True)
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
        
    @setting(100,command='s',returns='s')    
    def format_command(self,c,command):
        """For given input, formats the command as expected by the FTM-2400"""
        command = '!' + chr(len(command)+34) + command
        crc_val = self.calcCRC(c,command)
        command = command + chr(self.crc1(c,crc_val)) + chr(self.crc2(c,crc_val))
        return command
    
    @setting(101,str='s',returns='i')    
    def calcCRC(self,c,str):
        """For given outgoing string, calculates the appropriate crc value ignoring the first character,
        which should simply be the sync character (in this case '!') """
        crc = 0    
        length = 1 + ord(str[1]) - 34    
        if length > 0:
            crc = 0x3fff        
            for jx in range(1,length+1):
                crc = crc ^ ord(str[jx])            
                for ix in range(0,8):
                    tmpCRC = crc
                    crc = crc>>1
                    if tmpCRC & 0x1 == 1:
                        crc = crc ^ 0x2001                
                crc = crc & 0x3fff    
        return crc
    
    @setting(102,crc='i',returns='i') 
    def crc2(self,c,crc):
        """From the CRC value, compute the number associated with the appropriate ASCII character
        that goes second."""
        val = (((crc >> 7)& 0x7f) + 34)
        return val
    
    @setting(103,crc='i',returns='i') 
    def crc1(self,c,crc):
        """From the CRC value, compute the number associated with the appropriate ASCII character
        that goes first."""
        val = ((crc & 0x7f)+34)
        return val
        
    @setting(104,ans = 's',returns = 'b')
    def check_ans(self,c,ans):
        """Checks that the returned answer indicates a successful communication and is complete"""
        try: 
            if ans[2] != 'A':
                if ans[2] == 'C':
                    print 'Invalid Command'
                elif ans[2] == 'D':
                    print 'Problem with data in command'
                return False
        except IndexError:
            print 'Message status character not yet arrived'
            return False
            
        try:
            crc_val = self.calcCRC_in(c,ans[:-2])
            if chr(self.crc1(c,crc_val)) + chr(self.crc2(c,crc_val))== ans[-2:]:
                return True
            else:    
                print 'CRC did not match expected form. Error in data.'
                return False
        except IndexError:
            print 'Entire string not yet arrived'
            return False
        

            
    @setting(105,str='s',returns='i')    
    def calcCRC_in(self,c,str):
        """For given incoming string, calculates the appropriate crc value ignoring the first character,
        which should simply be the sync character (in this case '!') """
        crc = 0    
        length = 1 + ord(str[1]) - 35    
        if length > 0:
            crc = 0x3fff        
            for jx in range(1,length+1):
                crc = crc ^ ord(str[jx])            
                for ix in range(0,8):
                    tmpCRC = crc
                    crc = crc>>1
                    if tmpCRC & 0x1 == 1:
                        crc = crc ^ 0x2001                
                crc = crc & 0x3fff    
        return crc
        
    @setting(106,returns = 's')
    def read(self,c):
        """This piece of equipment doesn't use carriage returns, so the serial port cannot recognize
        the end of a message. The timeout parameter is set to be very short (~1 ms) and this function
        loops until the message from the FTM monitor has completely arrived."""
        dev=self.selectedDevice(c)
        ans = ''
        while True:
            temp_ans = yield dev.read()
            ans = ans + temp_ans
            print ans
            if self.check_ans(c,ans):
                print 'Returning ans'
                returnValue(ans[3:-2])
                break

                # !0AMON Ver 4.13Uw
        
                        
    @setting(200,returns='s')
    def get_ver(self,c):
        """Queries the @ command and returns the response. Usage is get_ver()"""
        dev=self.selectedDevice(c)
        command = self.format_command(c,'@')
        yield dev.write(command)
        ans = yield self.read(c)
        returnValue(ans)
            
    @setting(201,film = 'i', returns='s')
    def get_film_parameters(self,c, film):
        """Queries the L command and returns the response. Usage is get_rate()"""
        dev=self.selectedDevice(c)
        command = self.format_command(c,'A'+str(film)+'?')
        yield dev.write(command)
        ans = yield self.read(c)
        returnValue(ans)
            
    @setting(202,film = 'i',film_name = 's',density = 'v[]',tool = 'i',
                    zfactor = 'v[]', thickness = 'v[]', thickness_setpoint = 'v[]',
                    time_setpoint = 'i', sensor = 'i',returns='s')
    def set_film_parameters(self,c, film, film_name, density, tool, 
                zfactor, thickness, thickness_setpoint, time_setpoint, sensor):
        """Queries the L command and returns the response. Usage is get_rate()"""
        dev=self.selectedDevice(c)
        command = self.format_command(c,'A'+str(film)+film_name + ' ' + str(density) 
                + ' ' + str(tool) + ' ' + str(zfactor) + ' ' + str(thickness) + ' ' +
                str(thickness_setpoint) + ' '+ str(time_setpoint) + ' ' + str(sensor))
        yield dev.write(command)
        ans = yield self.read(c)
        returnValue(ans)
            
    @setting(203,returns='s')
    def get_sys1_parameters(self,c, film):
        """Queries the L command and returns the response. Usage is get_rate()"""
        dev=self.selectedDevice(c)
        command = self.format_command(c,'B?')
        yield dev.write(command)
        ans = yield self.read(c)
        returnValue(ans)
            
    # Add set sys1 parameters if necessary eventually. Didn't seem necessary.         
    # @setting(204,returns='s')
    # def set_sys1_parameters(self,c, film):
        # """Queries the L command and returns the response. Usage is get_rate()"""
        # dev=self.selectedDevice(c)
        # command = self.format_command(c,'B')
        # yield dev.write(command)
        # ans = yield dev.read()
        
        # if self.check_ans(c,ans):
            # returnValue(ans[3:-2])
            
    @setting(205,returns='s')
    def get_sys2_parameters(self,c):
        """Queries the L command and returns the response. Usage is get_rate()"""
        dev=self.selectedDevice(c)
        command = self.format_command(c,'C?')
        yield dev.write(command)
        ans = yield self.read(c)
        returnValue(ans)
            
    @setting(206,min_freq = 'v[]', max_freq = 'v[]', min_rate = 'v[]', max_rate = 'v[]',
            min_thick = 'v[]', max_thick = 'v[]', etch_mode = 'i', returns='s')
    def set_sys2_parameters(self,c,min_freq,max_freq,min_rate,max_rate,min_thick,
                max_thick,etch_mode):
        """Queries the L command and returns the response. Usage is get_rate()"""
        dev=self.selectedDevice(c)
        command = self.format_command(c,'C' + ' ' + str(min_freq) + ' ' + str(max_freq) + ' ' + 
            str(min_rate) + ' ' + str(max_rate) + ' ' + str(min_thick) + ' ' + str(max_thick) + 
            ' ' + str(etch_mode))
        
        yield dev.write(command)
        ans = yield self.read(c)
        returnValue(ans)
            
    @setting(207,film = 'i',returns='s')
    def set_film(self,c, film):
        """Queries the L command and returns the response. Usage is get_rate()"""
        dev=self.selectedDevice(c)
        command = self.format_command(c,'D'+str(film))
        yield dev.write(command)
        ans = yield self.read(c)
        returnValue(ans)
            
    @setting(208,returns='s')
    def get_num_channels(self,c):
        """Queries the L command and returns the response. Usage is get_rate()"""
        dev=self.selectedDevice(c)
        command = self.format_command(c,'J')
        yield dev.write(command)
        ans = yield self.read(c)
        returnValue(ans)
            
    @setting(209,sensor = 'i',returns='s')
    def get_sensor_rate(self,c,sensor):
        """Queries the L command and returns the response. Usage is get_rate()"""
        dev=self.selectedDevice(c)
        command = self.format_command(c,'L'+str(sensor)+'?')
        yield dev.write(command)
        ans = yield self.read(c)
        returnValue(ans)
            
    @setting(210,returns='s')
    def get_avg_rate(self,c,sensor):
        """Queries the L command and returns the response. Usage is get_rate()"""
        dev=self.selectedDevice(c)
        command = self.format_command(c,'M')
        yield dev.write(command)
        ans = yield self.read(c)
        returnValue(ans)

    @setting(211,sensor = 'i',returns='s')
    def get_sensor_thickness(self,c,sensor):
        """Queries the L command and returns the response. Usage is get_rate()"""
        dev=self.selectedDevice(c)
        command = self.format_command(c,'N'+str(sensor)+'?')
        yield dev.write(command)
        ans = yield self.read(c)
        returnValue(ans)      

    @setting(212,returns='s')
    def get_avg_thickness(self,c):
        """Queries the L command and returns the response. Usage is get_rate()"""
        dev=self.selectedDevice(c)
        command = self.format_command(c,'O')
        yield dev.write(command)
        ans = yield self.read(c)
        returnValue(ans)  

    @setting(213,sensor = 'i',returns='s')
    def get_sensor_freq(self,c,sensor):
        """Queries the L command and returns the response. Usage is get_rate()"""
        dev=self.selectedDevice(c)
        command = self.format_command(c,'P'+str(sensor))
        yield dev.write(command)
        ans = yield self.read(c)
        returnValue(ans)    

    @setting(214,sensor = 'i', returns='s')
    def get_sensor_life(self,c,sensor):
        """Queries the L command and returns the response. Usage is get_rate()"""
        dev=self.selectedDevice(c)
        command = self.format_command(c,'R'+str(sensor))
        yield dev.write(command)
        ans = yield self.read(c)
        returnValue(ans)  

    @setting(215,returns='s')
    def zero_rates_thickness(self,c):
        """Queries the L command and returns the response. Usage is get_rate()"""
        dev=self.selectedDevice(c)
        command = self.format_command(c,'S')
        yield dev.write(command)
        ans = yield self.read(c)
        returnValue(ans)
            
    @setting(216,returns='s')
    def zero_time(self,c):
        """Queries the L command and returns the response. Usage is get_rate()"""
        dev=self.selectedDevice(c)
        command = self.format_command(c,'T')
        yield dev.write(command)
        ans = yield self.read(c)
        returnValue(ans)
            
    @setting(217,returns='s')
    def get_shutter_status(self,c):
        """Queries the L command and returns the response. Usage is get_rate()"""
        dev=self.selectedDevice(c)
        command = self.format_command(c,'U?')
        yield dev.write(command)
        ans = yield self.read(c)
        returnValue(ans)
    
    @setting(218,returns='s')
    def set_shutter_open(self,c):
        """Queries the L command and returns the response. Usage is get_rate()"""
        dev=self.selectedDevice(c)
        command = self.format_command(c,'U1')
        yield dev.write(command)
        ans = yield self.read(c)
        returnValue(ans)
    
    @setting(219,returns='s')
    def set_shutter_close(self,c):
        """Queries the L command and returns the response. Usage is get_rate()"""
        dev=self.selectedDevice(c)
        command = self.format_command(c,'U0')
        yield dev.write(command)
        ans = yield self.read(c)
        returnValue(ans)
            
    @setting(220,returns='s')
    def get_all_sensor_data(self,c):
        """Queries the L command and returns the response. Usage is get_rate()"""
        dev=self.selectedDevice(c)
        command = self.format_command(c,'W')
        yield dev.write(command)
        ans = yield self.read(c)
        returnValue(ans) 
            
    @setting(221,returns='s')
    def power_up_status(self,c):
        """Queries the L command and returns the response. Usage is get_rate()"""
        dev=self.selectedDevice(c)
        command = self.format_command(c,'Y')
        yield dev.write(command)
        ans = yield self.read(c)
        returnValue(ans)
            
    @setting(222,returns='s')
    def set_default_parameters(self,c):
        """Queries the L command and returns the response. Usage is get_rate()"""
        dev=self.selectedDevice(c)
        command = self.format_command(c,'Z')
        yield dev.write(command)
        ans = yield self.read(c)
        returnValue(ans)
            
__server__ = FTMServer()
if __name__ == '__main__':
    from labrad import util
    util.runServer(__server__)
