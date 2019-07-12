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
name = LS155 Server
version = 1.0
description = Communicates with the Lock in, which has built in PLL / PID methods.  

[startup]
cmdline = %PYTHON% %FILE%
timeout = 20

[shutdown]
message = 987654321
timeout = 20
### END NODE INFO
"""

#This is a LabRAD server for the LakeShore 155 function generator. Original version written by Khari Stinson, 2019-07-12

from labrad.server import LabradServer, setting
from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.internet import reactor, defer
import labrad.units as units
from labrad.types import Value
import time
import numpy as np
import sys
import glob
import serial
from lakeshore import PrecisionSource #This is the driver for the LakeShore 155
import lakeshore
import re

class LS155Server(LabradServer):
    name = "LS155 Server"    # Will be labrad name of server
 
#------------------------------------------------------------------------------------------------------------------------------------------#
    """
    The following section of code has initializing and general lock in commands that can be useful in multiple contexts. 
    """

    def initServer(self):  # Do initialization here
        self.dev_ID = 'No device selected'
        self.device_list =[]
        print "Server initialization complete"
    
    @setting(100, 'Detect Devices', returns = '')
    def detect_devices(self,c):
        """Update self.device_list with the serial number of each LakeShore 155 Precision I/V Source
        found on a serial port."""
        if sys.platform.startswith('win'):
            ports = ['COM%s' % (i + 1) for i in range(256)]
        elif sys.platform.startswith('linux') or sys.platform.startswith('cygwin'):
            # this excludes your current terminal "/dev/tty"
            ports = glob.glob('/dev/tty[A-Za-z]*')
        elif sys.platform.startswith('darwin'):
            ports = glob.glob('/dev/tty.*')
        else:
            raise EnvironmentError('Unsupported platform (not win, linux, cygwin, or darwin)')
        result = []
        for port in ports:
            try:
                s = serial.Serial(port)
                s.close()
                this_instrument = PrecisionSource(com_port=port)#Check the current port for a LakeShore 155
                serial_num = this_instrument.query('*IDN?')#Get its ID e.g. 'LSCI,155-AC,LSA22C0,1.2.2018110102'
                serial_num = re.sub('.*?,.*?,', '', serial_num) #Cut out the first two commas and anything preceding them e.g. 'LSA22C0,1.2.2018110102'
                serial_num = re.sub(',.*', '', serial_num) #Cut out the first remaining comma and anything following it e.g. 'LSA22C0'
                result.append(serial_num)#If a precision source is found, add its serial number to the list
            except (OSError, serial.SerialException, lakeshore.xip_instrument.XIPInstrumentException):#If the port does not exist or does not have a 155, move on
                pass
        self.device_list = result
                
    @setting(101, 'List Devices', returns=['*(ws)'])
    def list_devices(self, c):
        """Returns the list of devices. If none have been detected (either because detect_devices has not yet
        been run, or because of a bad connection), this will return an empty array. This is the format required for a DeviceServer
        which this server has not yet transitioned to."""
        names = self.device_list
        length = len(self.device_list)
        IDs = range(0,length)
        return zip(IDs, names)
            
    @setting(102, 'Select Device', key=[': Select first device', 's: Select device by name', 'w: Select device by ID'], returns=['s: Name of the selected device'])
    def select_device(self, c, key = None):
        """Set self.dev_ID to the serial number of a specific LakeShore 155 so that commands are sent to it.
        If no input is given, default to the first thing in self.device_list"""
        if key is None:
            self.dev_ID = self.device_list[0]
        elif isinstance(key, str):
            if key in self.device_list:
                self.dev_ID = key
            else:
                print "Provided device key is not in the list of possible devices."
        else: 
            try:
                self.dev_ID = self.device_list[key]
            except:
                print "Provided device key is not in the list of possible devices."
            
        return self.dev_ID
       
    '''@setting(103,settings = '*s', returns = '')
    def set_settings(self, c, settings):
        """Simultaneously set all the settings described in the settings input. Settings should be a 
            list of string and input tuples, where the string provides the node information and the
            input is the required input. For example: 
            setting =   [['/%s/demods/*/enable' % self.dev=ID, 0],
                        ['/%s/demods/*/trigger' % self.dev=ID, 0],
                        ['/%s/sigouts/*/enables/*' % self.dev=ID, 0],
                        ['/%s/scopes/*/enable' % self.dev=ID, 0]]
            This function allows changing multiple settings quickly, however it requires knowledge 
            of the node names. Every setting that can be set through this function can also be 
            set through other functions."""
        #Use the above as an example for documentation. The stuff in the triple-quotes will show up in the cmd terminal
        yield daq.set(settings)'''

#------------------------------------------------------------------------------------------------------------------------------------------#
    """
    Additional functions that may be useful for programming the server. 
    """

    def sleep(self,secs):
        """Asynchronous compatible sleep command. Sleeps for given time in seconds, but allows
        other operations to be done elsewhere while paused."""
        d = defer.Deferred()
        reactor.callLater(secs,d.callback,'Sleeping')
        return d
    
    """
    Functions for controlling the LakeShore 155 Precision I/V Source
    """
       
    @setting(0,given_command=['s: Command to be sent to the selected LakeShore 155'],returns='')
    def command(self, c, given_command):
        """Sends an arbitrary command to the selected LakeShore 155.
        See available commands in chapter 4 of the manual
        https://www.lakeshore.com/docs/default-source/product-downloads/manuals/155manual.pdf?sfvrsn=45a2216f_1"""
        this_instrument = PrecisionSource(serial_number=self.dev_ID)
        this_instrument.command(given_command)
            
    @setting(1,given_query='s: Query to be sent to the selected LakeShore 155',returns='s: Response to the query')
    def query(self, c, given_query):
        """Sends an arbitrary query to the selected LakeShore 155 and returns the query response.
        See available queries in chapter 4 of the manual
        https://www.lakeshore.com/docs/default-source/product-downloads/manuals/155manual.pdf?sfvrsn=45a2216f_1"""
        this_instrument = PrecisionSource(serial_number=self.dev_ID)
        return this_instrument.query(given_query)
    
    @setting(2,returns='')
    def reset_device(self, c):
        """Resets the volatile memory of the selected LakeShore 155 to the power-up settings."""
        this_instrument = PrecisionSource(serial_number=self.dev_ID)
        this_instrument.command('*RST')

    @setting(200,onoff=['s','v'],returns='')
    def set_output(self, c, onoff):
        """Turns on/off the output of the selected LakeShore 155 Precision I/V Source. Use 0 for off, 1 for on."""
        this_instrument = PrecisionSource(serial_number=self.dev_ID)
        this_instrument.command('OUTPUT '+str(onoff))
        
    @setting(201,returns='i')
    def get_output(self, c):
        """Checks whether the signal output of the selected LakeShore 155 Precision I/V Source is on or off. Returns 0 if off, 1 if on."""
        this_instrument = PrecisionSource(serial_number=self.dev_ID)
        return int(this_instrument.query('OUTPUT?'))
    
    @setting(292,terminals='s:FRONt, REAR',returns='')
    def set_term(self, c, terminals):
        """Controls whether this LakeShore 155 will send its signal through the front or rear terminals."""
        this_instrument = PrecisionSource(serial_number=self.dev_ID)
        this_instrument.command('ROUTe:TERMinals '+terminals)
        
    @setting(293,returns='s')
    def get_term(self, c):
        """Checks which set of terminals are active on this LakeShore 155"""
        this_instrument = PrecisionSource(serial_number=self.dev_ID)
        return this_instrument.query('ROUTe:TERMinals?')
            
    @setting(203,mode='s:VOLTage, CURRent',returns='')
    def set_mode(self, c, mode):
        """Sets this LakeShore 155 to either VOLTAGE or CURRENT mode."""
        this_instrument = PrecisionSource(serial_number=self.dev_ID)       
        this_instrument.command('SOURCE:FUNCTION:MODE '+mode)
        
    @setting(204,returns='s')
    def get_mode(self, c):
        """Checks whether this LakeShore 155 is on VOLTAGE or CURRENT mode."""
        this_instrument = PrecisionSource(serial_number=self.dev_ID)       
        return this_instrument.query('SOURCE:FUNCTION:MODE?')
    
    @setting(205,shape='s:DC, SINusiod',returns='')
    def set_shape(self, c, shape):
        """Sets the shape of the function generated by this LakeShore 155 to either direct current or sinusoid."""
        this_instrument = PrecisionSource(serial_number=self.dev_ID)       
        this_instrument.command('SOURCE:FUNCTION:shape '+shape)
        
    @setting(206,returns='s')
    def get_shape(self, c):
        """Checks whether the function generated by this LakeShore 155 is DC or sinusoidal."""
        this_instrument = PrecisionSource(serial_number=self.dev_ID)       
        return this_instrument.query('SOURCE:FUNCTION:shape?')

    @setting(207,freq=['s','v'],returns='')
    def set_freq(self, c, freq):
        """Sets the function's frequency on the selected LakeShore 155. Ranges from 100 mHz to 100 kHz. Must be entered in Hz."""
        this_instrument = PrecisionSource(serial_number=self.dev_ID)       
        this_instrument.command('SOURCE:frequency '+str(freq)) #Convert freq to a string in case it was entered as an int, long, or float
        
    @setting(208,returns='v')
    def get_freq(self, c):
        """Returns the current freqency setting on this LakeShore 155. Note that frequency is defined, but unused if shape is set to DC.
        Given in hertz as a float."""
        this_instrument = PrecisionSource(serial_number=self.dev_ID)       
        return float(this_instrument.query('SOURCE:frequency?'))
    
    @setting(209,volt=['s','v'],returns='')
    def set_volt(self, c, volt):
        """Sets the amplitude for the signal produced by this LakeShore 155 when in voltage mode.
        Ranges from -100 V to 100 V for DC, 0 V to 100 V for AC. Must be entered in volts."""
        this_instrument = PrecisionSource(serial_number=self.dev_ID)
        this_instrument.command('SOURCE:voltage '+str(volt)) #Convert volt to a string in case it was entered as an int, long, or float
        
    @setting(210,returns='v')
    def get_volt(self, c):
        """Returns the voltage setting of this LakeShore 155. Given in volts as a float."""
        this_instrument = PrecisionSource(serial_number=self.dev_ID)       
        return float(this_instrument.query('SOURCE:voltage?'))
    
    @setting(211,offs=['s','v'],returns='')
    def set_volt_offs(self, c, offs):
        """Sets the offset from 0V for AC voltage on the selected LakeShore 155.
        Ranges from -100 V to 100 V. Must be entered in volts."""
        this_instrument = PrecisionSource(serial_number=self.dev_ID)
        this_instrument.command('SOURCE:VOLTAGE:offset '+str(offs)) #Convert offs to a string in case it was entered as an int, long, or float
        
    @setting(212,returns='v')
    def get_volt_offs(self, c):
        """Returns the offset from 0V for AC voltage on the selected LakeShore 155. Given in volts as a float."""
        this_instrument = PrecisionSource(serial_number=self.dev_ID)       
        return float(this_instrument.query('SOURCE:VOLTAGE:offset?'))
    
    @setting(213,rang=['s','v'],returns='')
    def set_volt_rang(self, c, rang):
        """Sets the voltage output full scale range of this LakeShore 155 in volts.
        Setting a manual range will disable autorange. Available ranges: 0.01 V, 0.1 V, 1 V, 10 V, 100 V. Must be entered in volts."""
        this_instrument = PrecisionSource(serial_number=self.dev_ID)
        this_instrument.command('SOURce:VOLTage:RANGe '+str(rang))
        
    @setting(214,returns='v')
    def get_volt_rang(self, c):
        """Returns the voltage output full scale range of this LakeShore 155. Does not indicate whether autorange is on or off. Given in volts as a float."""
        this_instrument = PrecisionSource(serial_number=self.dev_ID)       
        return float(this_instrument.query('SOURce:VOLTage:RANGe?'))

    @setting(215,auto=['s','v'],returns='')
    def set_volt_rang_auto(self, c, auto):
        """Enables or disables automatic selection of the voltage range. When on, the 155 will
        select a range based on the voltage level setting to maximize the signal to noise ratio.
        Use 0 to disable, 1 to enable."""
        this_instrument = PrecisionSource(serial_number=self.dev_ID)
        this_instrument.command('SOURce:VOLTage:RANGe:AUTO '+str(auto))
        
    @setting(216,returns='i')
    def get_volt_rang_auto(self, c):
        """Checks whether automatic selection of the voltage range is enabled or disabled
        on the selected LakeShore 155. Returns 0 if disabled, 1 if enabled."""
        this_instrument = PrecisionSource(serial_number=self.dev_ID)
        return int(this_instrument.query('SOURce:VOLTage:RANGe:AUTO?'))
    
    @setting(217,limit=['s','v'],returns='')
    def set_volt_lim(self, c, limit):
        """Sets the output limit for voltage for this LakeShore 155.
        This feature prevents the user from entering a voltage output value too high, either
        from the front panel or by remote interface, thus potentially preventing damage to a
        load. This setting does not apply any limits in hardware. The output limit can be set
        between 0 V and 100 V. In AC mode, the combined amplitude and offset cannot
        exceed this value. The output limit is an absolute value, applicable to both positive
        and negative output levels. """
        this_instrument = PrecisionSource(serial_number=self.dev_ID)
        this_instrument.command('SOURce:VOLTage:LIMit '+str(limit))
        
    @setting(218,returns='v')
    def get_volt_lim(self, c):
        """Returns the output limit for voltage for the selected LakeShore 155. Given in volts as a float."""
        this_instrument = PrecisionSource(serial_number=self.dev_ID)       
        return float(this_instrument.query('SOURce:VOLTage:LIMit?'))

    @setting(219,curr=['s','v'],returns='')
    def set_curr(self, c, curr):
        """Sets the amplitude for the signal produced by this LakeShore 155 when in current mode.
        Ranges from -0.1 A to 0.1 A for DC, 0 A to 0.1 A for AC. Must be entered in amps."""
        this_instrument = PrecisionSource(serial_number=self.dev_ID)
        this_instrument.command('SOURce:CURRent '+str(curr)) #Convert curr to a string in case it was entered as an int, long, or float
        
    @setting(220,returns='v')
    def get_curr(self, c):
        """Returns the current setting of this LakeShore 155. Given in amps as a float."""
        this_instrument = PrecisionSource(serial_number=self.dev_ID)       
        return float(this_instrument.query('SOURce:CURRent?'))
    
    @setting(221,offs=['s','v'],returns='')
    def set_curr_offs(self, c, offs):
        """Sets the offset from 0 amps for AC current on the selected LakeShore 155. Ranges from -0.1 A to 0.1 A. Must be entered in amps."""
        this_instrument = PrecisionSource(serial_number=self.dev_ID)
        this_instrument.command('SOURCE:CURRent:offset '+str(offs)) #Convert offs to a string in case it was entered as an int, long, or float
        
    @setting(222,returns='v')
    def get_curr_offs(self, c):
        """Returns the offset from 0 amps for AC current on the selected LakeShore 155. Given in amps as a float."""
        this_instrument = PrecisionSource(serial_number=self.dev_ID)       
        return float(this_instrument.query('SOURCE:CURRent:offset?'))
    
    @setting(223,rang=['s','v'],returns='')
    def set_curr_rang(self, c, rang):
        """Sets the current output full scale range of this LakeShore 155 in amps.  Setting a manual range will disable autorange. Available ranges: 1 uA, 10 uA, 100 uA, 1 mA, 10 mA, 100 mA. Must be entered in amps."""
        this_instrument = PrecisionSource(serial_number=self.dev_ID)
        this_instrument.command('SOURce:CURRent:RANGe '+str(rang))
        
    @setting(224,returns='v')
    def get_curr_rang(self, c):
        """Returns the current output full scale range of this LakeShore 155. Does not indicate whether autorange is on or off. Given in amps as a float."""
        this_instrument = PrecisionSource(serial_number=self.dev_ID)       
        return float(this_instrument.query('SOURce:CURRent:RANGe?'))
    
    @setting(225,auto=['s','v'],returns='')
    def set_curr_rang_auto(self, c, auto):
        """Enables or disables automatic selection of the current range. When on, the 155 will
        select a range based on the current level setting to maximize the signal to noise ratio.
        Use 0 to disable, 1 to enable."""
        this_instrument = PrecisionSource(serial_number=self.dev_ID)
        this_instrument.command('SOURce:CURRent:RANGe:AUTO '+str(auto))
        
    @setting(226,returns='i')
    def get_curr_rang_auto(self, c):
        """Checks whether automatic selection of the voltage range is enabled or disabled
        on the selected LakeShore 155. Returns 0 if disabled, 1 if enabled."""
        this_instrument = PrecisionSource(serial_number=self.dev_ID)
        return int(this_instrument.query('SOURce:CURRent:RANGe:AUTO?'))
    
    @setting(227,limit=['s','v'],returns='')
    def set_curr_lim(self, c, limit):
        """Sets the output limit for current for this LakeShore 155.
        This feature prevents the user from entering a current output value too high, either
        from the front panel or by remote interface, thus potentially preventing damage to a
        load. This setting does not apply any limits in hardware. The output limit can be set
        between 0 A and 0.1 A. In AC mode, the combined amplitude and offset cannot
        exceed this value. The output limit is an absolute value, applicable to both positive
        and negative output levels."""
        this_instrument = PrecisionSource(serial_number=self.dev_ID)
        this_instrument.command('SOURce:CURRent:LIMit '+str(limit))
        
    @setting(228,returns='v')
    def get_curr_lim(self, c):
        """Returns the output limit for current for the selected LakeShore 155. Given in amps as a float."""
        this_instrument = PrecisionSource(serial_number=self.dev_ID)       
        return float(this_instrument.query('SOURce:CURRent:LIMit?'))    
    
    
    

__server__ = LS155Server()
  
if __name__ == '__main__':
    from labrad import util
    util.runServer(__server__)