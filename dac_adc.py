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
name = DAC-ADC
version = 0.1
description = DAC-ADC Box server: AD5764-AD7734
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
import numpy as np
import time

TIMEOUT = Value(5,'s')
BAUD    = 115200

def twoByteToInt(DB1,DB2): # This gives a 16 bit integer (between +/- 2^16)
  return 256*DB1 + DB2

def map2(x, in_min, in_max, out_min, out_max):
  return (x - in_min) * (out_max - out_min) / (in_max - in_min) + out_min;


class DAC_ADCWrapper(DeviceWrapper):
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
    def readByte(self,count):
        p=self.packet()
        p.read(count)
        ans=yield p.send()
        returnValue(ans.read)

    @inlineCallbacks
    def timeout(self, time):
        yield p.self.packet().timeout(time)

    @inlineCallbacks
    def query(self, code):
        """ Write, then read. """
        p = self.packet()
        p.write_line(code)
        p.read_line()
        ans = yield p.send()
        returnValue(ans.read_line)
        


class DAC_ADCServer(DeviceServer):
    name = 'DAC-ADC'
    deviceName = 'Arduino DAC-ADC'
    deviceWrapper = DAC_ADCWrapper

    channels = [0,1,2,3]

    sPrefix = 703000
    sigInputRead         = Signal(sPrefix+0,'signal__input_read'         , '*s') #
    sigOutputSet         = Signal(sPrefix+1,'signal__output_set'         , '*s') #
    sigRamp1Started      = Signal(sPrefix+2,'signal__ramp_1_started'     , '*s') #
    sigRamp2Started      = Signal(sPrefix+3,'signal__ramp_2_started'     , '*s') #
    sigConvTimeSet       = Signal(sPrefix+4,'signal__conversion_time_set', '*s') #
    sigBufferRampStarted = Signal(sPrefix+5,'signal__buffer_ramp_started', '*s') #

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
        yield reg.cd(['', 'Servers', 'dac_adc', 'Links'], True)
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
            devName = '%s (%s)' % (serServer, port)
            devs += [(devName, (server, port))]

       # devs += [(0,(3,4))]
        returnValue(devs)

    
    @setting(100)
    def connect(self,c,server,port):
        dev=self.selectedDevice(c)
        yield dev.connect(server,port)

    @setting(103,port='i',voltage='v',returns='s')
    def set_voltage(self,c,port,voltage):
        """
        SET sets a voltage to a channel and returns the channel and the voltage it set.
        """
        if not (port in range(4)):
            returnValue("Error: invalid port number.")
            return
        if (voltage > 10) or (voltage < -10):
            returnValue("Error: invalid voltage. It must be between -10 and 10.")
            return
        dev=self.selectedDevice(c)
        yield dev.write("SET,%i,%f\r"%(port,voltage))
        ans = yield dev.read()
        voltage=ans.lower().partition(' to ')[2][:-1]
        self.sigOutputSet([str(port),voltage])
        returnValue(ans)


    @setting(104,port='i',returns='v[]')
    def read_voltage(self,c,port):
        """
        GET_ADC returns the voltage read by an input channel. Do not confuse with GET_DAC; GET_DAC has not been implemented yet.
        """
        dev=self.selectedDevice(c)
        if not (port in range(4)):
            returnValue("Error: invalid port number.")
            return
        yield dev.write("GET_ADC,%i\r"%port)
        ans = yield dev.read()
        self.sigInputRead([str(port),str(ans)])
        returnValue(float(ans))

    @setting(105,port='i',ivoltage='v',fvoltage='v',steps='i',delay='i',returns='s')
    def ramp1(self,c,port,ivoltage,fvoltage,steps,delay):
        """
        RAMP1 ramps one channel from an initial voltage to a final voltage within an specified number steps and a delay (microseconds) between steps. 
        When the execution finishes, it returns "RAMP_FINISHED".
        """
        dev=self.selectedDevice(c)
        yield dev.write("RAMP1,%i,%f,%f,%i,%i\r"%(port,ivoltage,fvoltage,steps,delay))
        self.sigRamp1Started([str(port),str(ivoltage),str(fvoltage),str(steps),str(delay)])
        ans = yield dev.read()
        returnValue(ans)

    @setting(106,port1='i',port2='i',ivoltage1='v',ivoltage2='v',fvoltage1='v',fvoltage2='v',steps='i',delay='i',returns='s')
    def ramp2(self,c,port1,port2,ivoltage1,ivoltage2,fvoltage1,fvoltage2,steps,delay):
        """
        RAMP2 ramps one channel from an initial voltage to a final voltage within an specified number steps and a delay (microseconds) between steps. The # of steps is the total number of steps, not the number of steps per channel. 
        When the execution finishes, it returns "RAMP_FINISHED".
        """
        dev=self.selectedDevice(c)
        yield dev.write("RAMP2,%i,%i,%f,%f,%f,%f,%i,%i\r"%(port1,port2,ivoltage1,ivoltage2,fvoltage1,fvoltage2,steps,delay))
        self.sigRamp2Started([str(port1),str(port2),str(ivoltage1),str(ivoltage2),str(fvoltage1),str(fvoltage2),str(steps),str(delay)])
        ans = yield dev.read()
        returnValue(ans)

    @setting(107,dacPorts='s', adcPorts='s', ivoltages='s', fvoltages='s', steps='i',delay='v[]',nReadings='i',returns='b')#(*v[],*v[])')
    def buffer_ramp(self,c,dacPorts,adcPorts,ivoltages,fvoltages,steps,delay,nReadings=1):
        """
        BUFFER_RAMP ramps the specified output channels from the initial voltages to the final voltages and reads the specified input channels in a synchronized manner. 
        It does it within an specified number steps and a delay (microseconds) between the update of the last output channel and the reading of the first input channel.
        """
        dev=self.selectedDevice(c)
        yield dev.write("BUFFER_RAMP,%s,%s,%s,%s,%i,%i,%i\r"%(dacPorts,adcPorts,ivoltages,fvoltages,steps,delay,nReadings))
        self.sigBufferRampStarted([dacPorts,adcPorts,ivoltages,fvoltages,str(steps),str(delay),str(nReadings)])
        returnValue(True)
        

    @setting(1919, steps ='i')#, returns = '(*v[], *v[])' )
    def serial_poll(self, c, steps):
        dev=self.selectedDevice(c)
        ch1=[]
        ch2=[]
        i = 0
        data = yield dev.readByte(steps*4)
        data = list(data)

        while i<steps*4:

            b1=int(data[i].encode('hex'),16)
            b2=int(data[i+1].encode('hex'),16)
            b3=int(data[i+2].encode('hex'),16)
            b4=int(data[i+3].encode('hex'),16)

            decimal1 = twoByteToInt(b1,b2)
            decimal2 = twoByteToInt(b3,b4)

            voltage1 = map2(decimal1,0,65536,-10.0,10.0)
            voltage2 = map2(decimal2,0,65536,-10.0,10.0)

            ch1.append(voltage1)
            ch2.append(voltage2)

            i+=4
            # print x

        ch1_array = np.asarray((map(float,ch1)))
        ch2_array = np.asarray((map(float,ch2)))

        ans=np.hstack((ch1_array,ch2_array))

        yield dev.read()

        returnValue((ch1_array,ch2_array))
        returnValue((ch1, ch2))


    # @setting(108,channel='i',returns='*v[]')
    # def get_buffer(self,c,channel):
    #     """

    #     """
    #     dev=self.selectedDevice(c)
    #     yield dev.write("GET_BUFFER,%i\r"%  channel)
    #     ans = yield dev.read()
    #     if ans == None or ans == "":
    #         returnValue(ans)
    #     ans_list = ans.split(",")
    #     ans_array = np.array((map(float,ans_list)))
    #     returnValue(ans_array)


    @setting(109,channel='i',time='v[]',returns='v[]')
    def set_conversionTime(self,c,channel,time):
        """
        CONVERT_TIME sets the conversion time for the ADC. The conversion time is the time the ADC takes to convert the analog signal to a digital signal. 
        Keep in mind that the smaller the conversion time, the more noise your measurements will have. Maximum conversion time: 2686 microseconds. Minimum conversion time: 82 microseconds.
        """
        if not (channel in self.channels):
            returnValue("Error: invalid channel. Must be in 0,1,2,3")
        if not (82 <= time <= 2686):
            returnValue("Error: invalid conversion time. Must adhere to (82 <= t <= 2686) (t is in microseconds)")
        dev=self.selectedDevice(c)
        yield dev.write("CONVERT_TIME,%i,%f\r"%(channel,time))
        ans = yield dev.read()
        self.sigConvTimeSet([str(channel),str(ans)])
        returnValue(float(ans))


    @setting(110,returns='s')
    def id(self,c):
        """
        IDN? returns the string "DAC-ADC_AD5764-AD7734".
        """
        dev=self.selectedDevice(c)
        yield dev.write("*IDN?\r")
        time.sleep(1)
        ans = yield dev.read()
        returnValue(ans)

    @setting(111,returns='s')
    def ready(self,c):
        """
        RDY? returns the string "READY" when the DAC-ADC is ready for a new operation.
        """
        dev=self.selectedDevice(c)
        yield dev.write("*RDY?\r")
        ans = yield dev.read()
        returnValue(ans)
        
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
    
    @setting(9005,time='v[s]')
    def timeout(self,c,time):
        dev=self.selectedDevice(c)
        yield dev.timeout(time)

    @setting(9100)
    def send_read_requests(self,c):
        dev = self.selectedDevice(c)
        for port in [0,1,2,3]:
            yield dev.write("GET_ADC,%i\r"%port)
            ans = yield dev.read()
            self.sigInputRead([str(port),str(ans)])

    # GET_DAC hasn't been added to the DAC ADC code yet
    # @setting(9101)
    # def send_get_dac_requests(self,c):
    #     yield


__server__ = DAC_ADCServer()

if __name__ == '__main__':
    from labrad import util
    util.runServer(__server__)
