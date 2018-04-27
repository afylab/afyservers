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
name = Amatek 7280 Lock-in amplifier
version = 1.3
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



class SR7280Wrapper(GPIBDeviceWrapper):

    #############################
    ## Signal channel settings ##
    #############################
    @inlineCallbacks
    def set_imode(self,n):
        yield self.write("IMODE %i" %n)
    @inlineCallbacks
    def get_imode(self):
        mode = yield self.query('IMODE')
        returnValue(mode)
    @inlineCallbacks
    def set_vmode(self,n):
        yield self.write("VMODE %i" %n)
    @inlineCallbacks
    def get_vmode(self):
        mode = yield self.query('VMODE')
        returnValue(mode)
    @inlineCallbacks
    def set_cp(self,n):
        yield self.write("CP %i" %n)
    @inlineCallbacks
    def get_cp(self):
        cp = yield self.query('CP')
        returnValue(cp)
    @inlineCallbacks
    def set_float(self,n):
        yield self.write("FLOAT %i" %n)
    @inlineCallbacks
    def get_float(self):
        flt = yield self.query("FLOAT")
        returnValue(flt)
    @inlineCallbacks
    def get_sens(self):
        sen = yield self.query("SEN.")
        returnValue(sen)
    @inlineCallbacks
    def get_sens_num(self):
        sen = yield self.query("SEN")
        returnValue(sen)
    @inlineCallbacks        
    def channel_set_sensitivity(self, n): #SEN
        yield self.write('SEN %i' % n)
    @inlineCallbacks
    def do_auto_sensitivity(self):
        yield self.write('AS')
    @inlineCallbacks
    def do_auto_measure(self):
        yield self.write('ASM')
    @inlineCallbacks
    def set_ac_gain(self,n):
        yield self.write("ACGAIN %i" %n)
    @inlineCallbacks
    def get_ac_gain(self):
        gain = yield self.query("ACGAIN")
        returnValue(gain)
    @inlineCallbacks
    def set_is_acgain_automatic(self,n):
        yield self.write("AUTOMATIC %i" %n)
    @inlineCallbacks
    def get_is_acgain_automatic(self):
        is_auto = yield self.query("AUTOMATIC")
        returnValue(is_auto)
    @inlineCallbacks
    def set_line_frequency_filter(self,n1,n2):
        yield self.write("LF %i %i" %(n1,n2))
    @inlineCallbacks
    def get_line_frequency_filter(self):
        lf = yield self.query("LF")
        returnValue(lf)

    #######################
    ## Reference channel ##
    #######################
    @inlineCallbacks
    def read_freq(self,flt):
        suf = '.' if flt else ''
        frq = yield self.query("FRQ%s"%suf)
        returnValue(frq)

    ####################
    ## Output channel ##
    ####################
    @inlineCallbacks
    def read_x(self,float_mode=False):
        suffix = '.' if float_mode else ''
        x_out = yield self.query("X%s" %suffix)
        returnValue(x_out)
    @inlineCallbacks
    def read_y(self,float_mode=False):
        suffix = '.' if float_mode else ''
        y_out = yield self.query("Y%s" %suffix)
        returnValue(y_out)
    @inlineCallbacks
    def read_mag(self,flt):
        suf = '.' if flt else ''
        mag = yield self.query("MAG%s"%suf)
        returnValue(mag)
    @inlineCallbacks
    def read_phase(self,flt):
        suf = '.' if flt else ''
        pha = yield self.query("PHA%s"%suf)
        returnValue(pha)
        
    # overload
    @inlineCallbacks
    def get_overload(self):
        ovld = yield self.query("N")
        returnValue(int(ovld))

    # auxiliary inputs
    @inlineCallbacks
    def read_adc(self,n):
        value = yield self.query("ADC.%i"%n)
        returnValue(value)

class SR7280Server(GPIBManagedServer):
    name = 'sr_7280_lockin'
    deviceName = '7280 DSP Lock-In'
    deviceIdentFunc = 'identify_device'
    deviceWrapper = SR7280Wrapper

    @setting(9001, server='s', address='s')
    def identify_device(self, c, server, address):
        print 'identifying:', server, address
        try:
            s = self.client[server]
            p = s.packet()
            p.address(address)
            p.write('ID\n')
            p.read()
            ans = yield p.send()
            resp = ans.read
            print 'got ident response:', resp
            if resp == '7280':
                returnValue(self.deviceName)
        except Exception, e:
            print 'failed:', e
            raise

    ##############################
    ## Signal channel functions ## Settings in this block have ID in range 100 -> 199
    ##############################
    @setting(101, n=['i'],returns=[])
    def set_imode(self,c,n=1):
        if not (n in [0,1,2,3]):
            print("Invalid Imode setting")
            raise
        dev = self.selectedDevice(c)
        yield dev.set_imode(n)
    @setting(102,returns='i')
    def get_imode(self,c):
        dev = self.selectedDevice(c)
        imode = yield dev.get_imode()
        returnValue(int(imode))

    @setting(103,'set_voltage_input_mode',n=['i'],returns=[])
    def set_vmode(self,c,n=1):
        if not (n in [0,1,2,3]):
            print("Invalid Vmode setting")
            raise
        dev = self.selectedDevice(c)
        yield dev.set_vmode(n)
    @setting(104,'get_voltage_input_mode',returns='i')
    def get_vmode(self,c):
        dev = self.selectedDevice(c)
        vmode = yield dev.get_vmode()
        returnValue(int(vmode))

    @setting(105,'set_coupling_mode',n=['i'],returns=[])
    def set_cp(self,c,n=1):
        if not (n in [0,1]):
            print("Invalid CP setting")
            raise
        dev = self.selectedDevice(c)
        yield dev.set_cp(n)
    @setting(106,'get_coupling_mode',returns='i')
    def get_cp(self,c):
        dev = self.selectedDevice(c)
        cp = yield dev.get_cp()
        returnValue(int(cp))

    # Get/set FLOAT setting: whether or not the input is shielded by a 1 kilo-ohm resistor
    # 1 (default): shielded by resistor, 0: ground
    @setting(107,'set_ground_float',n=['i'],returns=[])
    def set_float(self,c,n):
        if not (n in [0,1]):
            print("Invalid Float setting")
            raise
        dev = self.selectedDevice(c)
        yield dev.set_float(n)
    @setting(108,'get_ground_float',returns='i')
    def get_float(self,c):
        dev = self.selectedDevice(c)
        flt = yield dev.get_float()
        returnValue(int(flt))

    @setting(109, n=['i'], returns=[])
    def set_sensitivity(self,c,n=3):
        if not (n in range(3,28)):
            print("Invalid sensitivity setting")
            raise
        dev = self.selectedDevice(c)
        yield dev.channel_set_sensitivity(n)
    @setting(110,returns=['v[V]','v[A]'])
    def get_sensitivity(self,c):
        dev = self.selectedDevice(c)
        sens = yield dev.get_sens()
        mode = yield dev.get_imode()
        ans = float(sens) * units.V if mode=='0' else float(sens) * units.A # Units are volts only in mode 0
        returnValue(ans)
    @setting(111,returns='i')
    def get_sensitivity_number(self,c):
        dev = self.selectedDevice(c)
        sen = yield dev.get_sens_num()
        returnValue(int(sen))
    @setting(112,returns=[])
    def do_auto_sensitivity(self,c):
        dev = self.selectedDevice(c)
        yield dev.do_auto_sensitivity()
    @setting(113,returns=[])
    def do_auto_measure(self,c):
        dev = self.selectedDevice(c)
        yield dev.do_auto_measure()
    @setting(114,n=['i'],returns=[])
    def set_ac_gain(self,c,n):
        if not (n in range(11)):
            print("Invalid AC range setting")
            raise
        dev = self.selectedDevice(c)
        yield dev.set_ac_gain(n)
    @setting(115,returns='i')
    def get_ac_gain(self,c):
        dev = self.selectedDevice(c)
        gain = yield dev.get_ac_gain()
        returnValue(int(gain))
    @setting(116,n=['i'],returns=[])
    def set_is_acgain_automatic(self,c,n):
        if not (n in [0,1]):
            print("Invalid AC Gain automatic setting")
            raise
        dev = self.selectedDevice(c)
        yield dev.set_is_acgain_automatic(n)
    @setting(117,returns='i')
    def get_is_acgain_automatic(self,c):
        dev = self.selectedDevice(c)
        is_auto =yield  dev.get_is_acgain_automatic()
        returnValue(int(is_auto))
    @setting(118,n1=['i'],n2=['i'],returns=[])
    def set_line_frequency_filter(self,c,n1,n2):
        if not (n1 in [0,1,2,3] and n2 in [0,1]):
            print("Invalid line filter setting")
            raise
        dev = self.selectedDevice(c)
        yield dev.set_line_frequency_filter(n1,n2)
    @setting(119,returns='*i')
    def get_line_frequency_filter(self,c):
        dev = self.selectedDevice(c)
        nf = yield dev.get_line_frequency_filter()
        returnValue([int(nf[0]),int(nf[2])])

    #################################
    ## Reference channel functions ##
    #################################
    @setting(200,float_mode='b',returns=[])
    def read_freq(self,c,float_mode=True):
        dev = self.selectedDevice(c)
        frq = yield dev.read_freq(float_mode)
        ans = float(frq) if float_mode else int(frq)
        returnValue(ans)

    #############################
    ## Output channel commands ##
    #############################
    @setting(501,float_mode='b',returns=['i','v[A]','v[V]'])
    def read_x(self,c,float_mode=True):
        dev = self.selectedDevice(c)
        x_out = yield dev.read_x(float_mode)
        if not float_mode:
            returnValue(int(x_out))
        else:
            mode = yield dev.get_imode()
            if mode=='0':returnValue(units.V * float(x_out))
            else:returnValue(units.A * float(x_out))
    @setting(502,float_mode='b',returns=['i','v[A]','v[V]'])
    def read_y(self,c,float_mode=True):
        dev = self.selectedDevice(c)
        y_out = yield dev.read_y(float_mode)
        if not float_mode:
            returnValue(int(y_out))
        else:
            mode = yield dev.get_imode()
            if mode=='0':returnValue(units.V * float(y_out))
            else:returnValue(units.A * float(y_out))
    @setting(503,float_mode='b',returns=['v','i'])
    def read_phase(self,c,float_mode=True):
        dev=self.selectedDevice(c)
        phs=yield dev.read_phase(float_mode)
        val=float(phs) if float_mode else int(phs)
        returnValue(val)
    @setting(504,float_mode='b',returns=['i','v[A]','v[V]'])
    def read_magnitude(self,c,float_mode=True):
        dev = self.selectedDevice(c)
        mag = yield dev.read_mag(float_mode)
        if not float_mode:
            returnValue(int(mag))
        else:
            mode = yield dev.get_imode()
            if mode=='0':returnValue(units.V * float(mag))
            else:returnValue(units.A * float(mag))

    @setting(666,l=['s','*s'],i1='i',i2='i',f1='v',returns=['i','*i','v','*v'])
    def testfunc(self,c,l,i1,i2=4,f1=0.2):
        dev=self.selectedDevice(c)
        yield 0
        returnValue(i1)

    #############################
    ## Auxiliary input channel ##
    #############################
    @setting(800,n='i',returns='v')
    def read_adc(self,c,n):
        dev = self.selectedDevice(c)
        value = yield dev.read_adc(n)
        returnValue(float(value))
    @setting(801,returns='v')
    def read_adc_1(self,c):
        dev = self.selectedDevice(c)
        value = yield dev.read_adc(1)
        returnValue(float(value))
    @setting(802,returns='v')
    def read_adc_2(self,c):
        dev = self.selectedDevice(c)
        value = yield dev.read_adc(2)
        returnValue(float(value))
    @setting(803,returns='v')
    def read_adc_3(self,c):
        dev = self.selectedDevice(c)
        value = yield dev.read_adc(3)
        returnValue(float(value))
    @setting(804,returns='v')
    def read_adc_4(self,c):
        dev = self.selectedDevice(c)
        value = yield dev.read_adc(4)
        returnValue(float(value))

    #################################
    ## Computer Interfaces Channel ##
    #################################
    @setting(1000,returns='i')
    def get_overload(self,c):
        dev=self.selectedDevice(c)
        overload = yield dev.get_overload()
        returnValue(overload)
    
__server__ = SR7280Server()

if __name__ == '__main__':
    from labrad import util
    util.runServer(__server__)
