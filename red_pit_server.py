
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
name = Red Pitaya microprocessor
version = 0.2
description = 
[startup]
cmdline = %PYTHON% %FILE%
timeout = 20
[shutdown]
message = 987654321
timeout = 20
### END NODE INFO
"""


from labrad.server import setting
from labrad.gpib import GPIBManagedServer, GPIBDeviceWrapper
from twisted.internet.defer import inlineCallbacks, returnValue
import labrad.units as units
from labrad.types import Value
import numpy as np
import time
import matplotlib.pyplot as plot



class RedPitWrapper(GPIBDeviceWrapper):

    @inlineCallbacks
    def func_gen(self,n,Type,freq,Vpp):
        yield self.write('OUTPUT%(out)i:STATE ON;:SOUR%(out)i:VOLT %(Vpp)f;FUNC %(func)s ;FREQ:FIX %(freq)f' %{'out':n ,'Vpp':Vpp, 'func':Type, 'freq':freq})

    @inlineCallbacks
    def set_func(self,n,Type):
         yield self.write('SOUR%(out)i:FUNC %(func)s' %{'out':n ,'func':Type,})

    @inlineCallbacks
    def set_phase(self,n,Phase,Voff):
        yield self.write('SOUR%(out)i:PHAS %(Phase)f;VOLT:OFFS %(Voff)f' %{'out':n ,'Phase':Phase ,'Voff':Voff })

    @inlineCallbacks    
    def reset(self):
        yield self.write('GEN:RST')

    @inlineCallbacks
    def set_volt(self,n,Vpp):
        yield self.write('OUTPUT%(out)i:STATE ON;:SOUR%(out)i:VOLT %(Vpp)f' %{'out':n ,'Vpp':Vpp})

    @inlineCallbacks
    def query(self,phrase):  # for debug
        yield self.write(phrase)
        ans = yield self.read()
        returnValue(ans)

    @inlineCallbacks
    def read_cons(self): #for debug
        cons_resp = yield self.read()
        returnValue(cons_resp) 

    @inlineCallbacks
    def write_cons(self,msg): #for debug
        yield self.write(msg)

    @inlineCallbacks
    def acquire(self,n,Ns):
        data=''
        fullbuffer=16384
        if fullbuffer<=Ns:
            while fullbuffer<=Ns:
                yield self.write('ACQ:START;TRIG NOW')
                yield self.write('ACQ:SOUR%i:DATA:STA:N? 0, 16384' %n)
                buffer_raw = yield self.read() #returns string
                data=data+buffer_raw
                Ns=Ns-fullbuffer
            if Ns!=0:
                yield self.write('ACQ:START;TRIG NOW')
                yield self.write('ACQ:SOUR%(out)i:DATA:STA:N? 0, %(Ns)i' %{'out':n, 'Ns':Ns})
                buffer_raw = yield self.read() #returns string of nested floats
                data=data+buffer_raw
        else:
            yield self.write('ACQ:START;TRIG NOW')
            yield self.write('ACQ:SOUR%(out)i:DATA:STA:N? 0, %(Ns)i' %{'out':n, 'Ns':Ns})
            buffer_raw = yield self.read() #returns string of nested floats
            data=data+buffer_raw
        data = data.replace('REDPITAYA,INSTR2014,0,01-02','') #maybe unnecessary
        data = data.replace('TD','').replace('}{', ',') #merge multiple buffers into one dataset
        data = data.strip('{}\n\r').replace("  ","").split(',') #make string into list of floats
        data = list(map(float,data))
        returnValue(data)

    @inlineCallbacks
    def acq_dec(self,dec):
        yield self.write('ACQ:DEC %i' %dec)
        yield self.write('ACQ:DEC?')
        decimate = yield self.read()
        returnValue(decimate)


class RedPitServer(GPIBManagedServer):
    name = 'red_pit'
    deviceName = 'REDPITAYA INSTR2014'
    deviceWrapper = RedPitWrapper
    deviceIdentFunc = 'identify_device'

    @setting(9988, server='s', address='s')
    def identify_device(self, c, server, address):
        """
        Identifies red pitaya instruments to GPIB server.
        """
        print 'identifying:', server, address
        try:
            s = self.client[server]
            p = s.packet()
            p.address(address)
            p.write_termination('\r\n')
            p.read_termination('\r\n')
            p.write('*IDN?')
            p.read()
            ans = yield p.send()
            resp = ans.read
            print 'got ident response:', resp
            if resp == 'REDPITAYA,INSTR2014,0,01-02':
                returnValue((self.deviceName,address))
        except Exception, e:
            print 'failed:', e
            raise

    @setting(101,n='i',Type='s', freq='v',V='v')
    def func_gen(self, c ,n, Type, freq, V):
        """
        :param n: sma output number
        :param Type: type of output function, 'sin' Sine, 'tri' Triangle, 'sqr' Square
        :param freq: output frequency up to 50 MHz.
        :param V: output voltage amplitude, up to 1V.
        :return: Sets desired function output on specied sma output
        """
        dev=self.selectedDevice(c)
        Type=Type.lower()
        V=float(abs(V))
        types=['sin','tri','sqr']

        if (0<=V and V<= 1 and 0<=freq and freq<= 50000000):    
            try:
                if Type=='sin':
                    Type='SINE'
                if Type=='tri':
                    Type='TRIANGLE'
                if Type=='sqr':
                    Type='SQUARE'
            except Exception:
                print 'Error: function type not recognized, try (sin, tri, sqr)'
                raise
            yield dev.func_gen(n,Type,freq, V)
        else:
            print 'Voltage or frequency not in range 0<=V<=1, 0<=freq<=50 MHz'
            raise
           
    @setting(103)        
    def reset(self, c):
        """Sets sma outputs to default settings, with frequecy=1kHz, voltage=1V, all outputs in OFF state"""
        dev=self.selectedDevice(c)
        yield dev.reset()

    @setting(104, n='i',Phase='v', Voff='v')
    def set_phase(self,c,n,Phase,Voff):
        """
        :param n: sma output number
        :param Phase: sets 0 to 360 degrees phase offset
        :param Voff: sets DC voltage offset 0<=Voff<=1 (can clip output)
        :return: sets a phase or DC offest on a given output
        """
        dev=self.selectedDevice(c)
        Voff=float(abs(Voff))
        if (0<=Voff and Voff<= 1):
            yield dev.set_phase(n,Phase,Voff) 
        else:
            print 'Voltage or frequency not in range 0<=V<=1'
            raise
          

    @setting(105, n='i',Type='s')
    def set_func(self,c,n,Type):
        """
        :param n: sma output number
        :param Type: type of output function, 'sin' Sine, 'tri' Triangle, 'sqr' Square
        :return: changes function type on a given sma output
        """
        dev=self.selectedDevice(c)
        try:
            if Type=='sin':
                Type='SINE'
                pass
            if Type=='tri':
                Type='TRIANGLE'
                pass
            if Type=='sqr':
                Type='SQUARE'
                pass
        except Exception:
            print 'Error: function type not recognized, try (sin, tri, sqr)'
            raise
        yield dev.set_func(n,Type)

    @setting(106,n='i',V='v')
    def set_volt(self,c,n,V):
        """
        :param n: sma output number
        :param V: output voltage, up to 1V.
        :return: changes voltage amplitude on a given sma output.
        """
        dev=self.selectedDevice(c)
        V=float(abs(V))
        if V>1:
            print 'Voltage or frequency not in range 0<=V<=1'
            raise
        else:
            yield dev.set_volt(n,V)

    @setting(107,phrase='s')
    def query(self,c,phrase):
        """
        Used to send SCPI string like *IDN? to connected redpitaya device and return device response.
        """
        dev=self.selectedDevice(c)
        ans=yield dev.query(phrase)
        returnValue(ans)
        #also prints to server
        print ans

    @setting(110)
    def read_cons(self,c):
        """
        Reads out what is on the red pitaya console.
        """
        dev=self.selectedDevice(c)
        cons_resp=yield dev.read_cons()
        returnValue(cons_resp)

    @setting(111,msg='s')
    def write_cons(self,c,msg):
        """
        Sends raw message string to the red pitaya console.
        """
        dev=self.selectedDevice(c)
        yield dev.write_cons(msg)

    @setting(112,n='i',Ns='i', returns='*v')
    def acquire(self,c,n,Ns):
        """
        :param n: sma output number
        :param Ns: number of data samples to be taken on the output.
        :return: returns voltage sample data taken at the current sampling rate.
        :rtype: time ordered list of float objects.
        """
        dev=self.selectedDevice(c)
        data=yield dev.acquire(n,Ns)
        returnValue(data)

    @setting(113,dec='i')
    def acq_dec(self,c,dec):
        """
        :param dec: Sets decimation, i.e. downsampling factor 1/dec. dec=[1,8,64,1024,8192,65536]
        :returns: Sets and then returns the decimation factor.
        """
        decimation=[1,8,64,1024,8192,65536]
        if dec in decimation:
            dev=self.selectedDevice(c)
            decimate=yield dev.acq_dec(dec)
            returnValue(decimate)
            print 'Decimation factor set to: ', decimate
        else:
            print 'Error: Not an allowed decimation factor. Allowed: dec = 1,8,64,1024,8192,65536.'


__server__ = RedPitServer()

if __name__ == '__main__':
    from labrad import util
    util.runServer(__server__)

