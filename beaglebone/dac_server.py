# Copyright (C) 2017 Carlos Kometter & James Ehrets II
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
name = DAC Server
version = 0.1
description = TODO
[startup]
cmdline = %PYTHON% %FILE%
timeout = 20
[shutdown]
message = 987654321
timeout = 20
### END NODE INFO
"""

from labrad import util
from labrad.server import setting
from labrad.devices import DeviceWrapper
from labrad.gpib import ManagedDeviceServer
from twisted.internet.defer import inlineCallbacks, returnValue

class AD5791Wrapper(DeviceWrapper):
    '''TODO'''
    pass


class DACServer(ManagedDeviceServer):
    """TODO"""
    name = 'DAC Server'
    deviceManager = 'SPI Device Manager'
    deviceWrappers = {"AD5791": AD5791Wrapper}

    @setting(1, parameter1='s', parameter2='s')
    def function(self, c, parameter1, parameter2):
        '''TODO'''
        pass

__server__ = DACServer()

if __name__ == '__main__':
    util.runServer(__server__)
