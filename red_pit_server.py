
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
version = 0.1
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
import time
import matplotlib.pyplot as plot



class RedPitWrapper(GPIBDeviceWrapper):

    @inlineCallbacks
    def sweep(self,n,Vs,Ve,nV,fs,fe,nf,dt):
        dV=float((Ve-Vs)/nV)
        df=float((fe-fs)/nf)
        Vnow=Vs
        j=1
        if fs==fe:
            while Vnow<=Ve:
                yield self.func_gen(n, 'SIN', fs, Vnow)
                print j,Vnow,fnow 
                time.sleep(dt)
                Vnow=Vnow+dV
                j=j+1
                time.sleep(dt)
            print 'Voltage Sweep Done'
        elif Vs==Ve:
            fnow=fs
            i=0
            while fnow<=fe:
                yield self.func_gen(n, 'SIN', fnow, Vs)
                print j,Vs,fnow
                i=i+1
                time.sleep(dt)
            print 'Frequency Sweep Done'
        else:
            while Vnow<=Ve:
                fnow=fs
                i=0
                while fnow<=fe:
                    yield self.func_gen(n, 'SIN', fnow, Vnow)
                    fnow=fnow+df
                    print j,Vnow,fnow
                    i=i+1
                    time.sleep(dt)    
                print 'Sweep at %fV done' %Vnow
                Vnow=Vnow+dV
                j=j+1
                time.sleep(dt)
            print 'Sweep Done'

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

    

     # @inlineCallbacks
     # def acquire(self,c,n,rate,dec,Ns):
     #    yield self.write('ACQ%(in)i:DEC %(dec)i;SRAT %(srat)s;DEC?;SRAT?' %{'in':n,'dec':dec,'srat':rate,'form':form,'units':units})
     #    ans = yield self.read()
     #    print '(Decimation,Samplerate): ', ans

        #insert math here that figures out how long to run ACQ start before calling ACQ end at a given sample rate to get enough samples for Ns
        #when done and data has been pulled from buffer, need to reset buffer to clear the parameters (happens on reboot also). 
        #Can check buffer size spec sheet to figure out max buffer that you can take.

    @inlineCallbacks
    def query(self,phrase):  # for debug
        yield self.write(phrase)
        ans = yield self.read()
        print ans 

    # @inlineCallbacks
    # def aquire():

    @inlineCallbacks
    def buffersize(self,n):
        yield self.write('ACQ:SOUR%i:DATA?' %n)
        buffer_raw = yield self.read() #returns string
        buffer_raw = buffer_raw.replace('REDPITAYA,INSTR2014,0,01-02','')
        buffer_raw = buffer_raw.strip('{}\n\r').replace("  ","").split(',')
        self.size=len(list(map(float,buffer_raw)))
        print 'Length buffered sample list: ', self.size
    
    @inlineCallbacks
    def plot_buffer(self,n,m):
        yield self.write('ACQ:START;TRIG NOW')
        while 1:
            yield self.write('ACQ:TRIG:STAT?')
            resp = yield self.read()
            if resp == 'TD':
                break
        yield self.write('ACQ:SOUR%(n)i:DATA:STA:N? 0, %(m)i' %{'n':n,'m':m})
        buffer_raw = yield self.read() #returns string
        buffer_raw = buffer_raw.replace('REDPITAYA,INSTR2014,0,01-02','')
        buffer_raw = buffer_raw.strip('{}\n\r').replace("  ","").split(',')
        data=list(map(float,buffer_raw))
        plot.plot(data)
        plot.ylabel('Voltage on input %i' %n)
        plot.show()

    @inlineCallbacks
    def read_cons(self): #for debug
        resp = yield self.read()
        print 'Red Pitaya: ', resp

    @inlineCallbacks
    def write_cons(self,msg): #for debug
        yield self.write(msg)

    @inlineCallbacks
    def acquire(self,n,Ns):
        data=''
        samplenumber=0
        delay=16384
        start_time=time.time()
        while samplenumber < Ns:
            yield self.write('ACQ:START;TRIG NOW')
            yield self.write('ACQ:SOUR%i:DATA:STA:N? 0, 16384' %n)
            buffer_raw = yield self.read() #returns string
            data=data+buffer_raw
            samplenumber=samplenumber+delay
            
        print 'process time: ', time.time() - start_time
        data = data.replace('REDPITAYA,INSTR2014,0,01-02','')
        data = data.replace('TD','').replace('}{', ',')
        print 'RED,TD replaced'
        data = data.strip('{}\n\r').replace("  ","").split(',')
        print 'datalist made'
        print 'data:', data
        data = list(map(float,data))
        print 'datalength', len(data)
        print data

        plot.plot(data)
        plot.ylabel('Voltage on input %i' %n)
        plot.show()

    @inlineCallbacks
    def acq_dec(self,dec):
        yield self.write('ACQ:DEC %i' %dec)
        yield self.write('ACQ:DEC?')
        ans = yield self.read()
        print 'Decimation factor set to: ', ans




class RedPitServer(GPIBManagedServer):
    name = 'red_pit'
    deviceName = 'REDPITAYA INSTR2014'
    deviceWrapper = RedPitWrapper
    deviceIdentFunc = 'identify_device'

    @setting(9988, server='s', address='s')
    def identify_device(self, c, server, address):
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
                returnValue(self.deviceName)
        except Exception, e:
            print 'failed:', e
            raise

    @setting(101,n='i',Type='s', freq='v',Vpp='v')
    def func_gen(self, c ,n, Type, freq, Vpp):
        """Set board outputs sma 1 & 2 like a function generator.
        func_gen(n, Type, freq , Vpp)
        n=output 1 or 2
        Type= 'sin' Sine, 'tri' Triangle, 'sqr' Square
        freq= 0Hz --> 62.5 MHz
        Vpp= 0V --> 1V
        """
        dev=self.selectedDevice(c)
        Type=Type.lower()
        Vpp=float(abs(Vpp))
        types=['sin','tri','sqr']
        if not (Vpp <= 1):
            print 'Vpp not in range 0<Vpp<=1'
            raise    
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
        yield dev.func_gen(n,Type,freq, Vpp)

    @setting(102,n='i',Vs='v',Ve='v',nV='i',fs='v',fe='v',nf='i',dt='v')
    def sweep(self,c,n,Vs,Ve,nV,fs,fe,nf,dt):
        """Sweeps voltage and/or frequency on board sma outputs 1 & 2.
        sweepv(n,Vs,Ve,nV,fs,fe,nf,dt)
        n= output 1 or 2
        Vs=Start amplitude, 0 to 1 V
        Ve=end amplitude, 0 to 1 V
        nV=# voltage increments, max res ~ .0.00013 V per nV
        fs=frequency start 0Hz --> 62.5 MHz
        fe=frequency end 0Hz --> 62.5 MHz
        nf=# freq increments
        dt=time increments, sec

        If fs=fe, then will sweep voltage only.
        If Vs=Ve, then will sweep frequency only. 
        """
        dev=self.selectedDevice(c)
        if not (0 < nf <1) or (0 < nV <1) or (0 < dt): 
            print "Error: invalid choice of increments"
            raise
        elif not (0 < fs <= freqmax) or (0 < fe <= freqmax):
            print "Error: invalid frequency endpoints. Must be 0-62.5 MHz"
            raise
        elif not (0 < Vs <=1) or (0 < Ve <=1):
            print "Error: invalid voltage endpoints. Must be 0-1V"
            raise
        elif (Vs==Ve) and (fs==fe):
            print "Error: sweep endpoints are not different."
        else:
            yield dev.sweep(n,Vs,Ve,nV,fs,fe,nf,dt)
           
    @setting(103)        
    def reset(self, c):
        """Sets sma outputs to default settings, with frequecy=1kHz, voltage=1V, all outputs in OFF state"""
        dev=self.selectedDevice(c)
        yield dev.reset()

    @setting(104, n='i',Phase='v', Voff='v')
    def set_phase(self,c,n,Phase,Voff):
        """Sets phase and voltage offset on a given sma output.
        set_phase(n,Phase,Voff)
        n=output#  1 or 2
        Phase= 0 to 360 degrees
        Voff= DC offset 0-->1V
        """
        dev=self.selectedDevice(c)
        Voff=abs(Voff)
        yield dev.set_phase(n,Phase,Voff)   

    @setting(105, n='i',Type='s')
    def set_func(self,c,n,Type):
        """Sets functional form of output on sma output 1 or 2
        set_func(n,Type)
        n=output#  1 or 2
        Type= 'sin' Sine, 'tri' Triangle, 'sqr' Square
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

    @setting(106,n='i',Vpp='v')
    def set_volt(self,c,n,Vpp):
        """Sets Voltage amplitude on sma outputs
        set_volt(n,Vpp)
        n=output#  1 or 2
        Vpp= 0V --> 1V
        """
        dev=self.selectedDevice(c)
        Vpp=float(abs(Vpp))
        if Vpp>1:
            print 'Error: out of voltage range 0V --> 1V'
            raise
        else:
            yield dev.set_volt(n,Vpp)

    @setting(107,phrase='s')
    def query(self,c,phrase):
        """Sends SCPI string like *IDN? to connected redpitaya device and displays device response"""
        dev=self.selectedDevice(c)
        yield dev.query(phrase)

    @setting(108,n='i')
    def buffersize(self,c,n):
        """Provides the length of the list of buffered samples stored on a specified sma input.
        buffer(n)
        n= input#  1 or 2
        """
        dev=self.selectedDevice(c)
        yield dev.buffersize(n)
    
    @setting(109,n='i',m='i')
    def plot_buffer(self,c,n,m):
        """Returns plot of data up to mth stored sample on the nth buffer."""
        dev=self.selectedDevice(c)
        yield dev.plot_buffer(n,m)

    @setting(110)
    def read_cons(self,c):
        """Reads out what is on the red pitaya console"""
        dev=self.selectedDevice(c)
        yield dev.read_cons()

    @setting(111,msg='s')
    def write_cons(self,c,msg):
        """Sends  message string to the red pitaya console"""
        dev=self.selectedDevice(c)
        yield dev.write_cons(msg)

    @setting(112,n='i',Ns='i')
    def acquire(self,c,n,Ns):
        """Takes in a specified number of data samples on a given input channel, with specified sampling rate, number of decimals, and units. This data is stored in the buffer of the input channel used.
        acquire(n,Ns)
        n = input#  1 or 2
        Ns = Number of samples that will be taken. Currently, device is commanded to read samples from the very first recorded in the buffer, up to the Ns endpoint. 
        
        Default sampling rate is 125MHz, with decimation of 1. Change rate with acq_dec function.
        The returned data is by default of type 'float'. Supported types are:'FLOAT', 'ASCII', so left to the user to pass manually.
        The default units of returned data is volts. Supported types are:'Supported types are:'VOLTS', 'RAW', so left to the user to pass manually. """

        dev=self.selectedDevice(c)
        yield dev.acquire(n,Ns)

    @setting(113,dec='i')
    def acq_dec(self,c,dec):
        """Sets decimation, i.e. integer downsampling factor. Ex: if dec=8, will only record the 8th sample taken at the sampling frequency. Allowed: dec = 1,8,64,1024,8192,65536. """
        dev=self.selectedDevice(c)
        yield dev.acq_dec(dec)

__server__ = RedPitServer()

if __name__ == '__main__':
    from labrad import util
    util.runServer(__server__)

