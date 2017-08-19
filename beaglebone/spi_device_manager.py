# Copyright (C) 2017 Carlos Kometter
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

from twisted.internet.defer import DeferredList, DeferredLock
from twisted.internet.reactor import callLater

from labrad.server import (LabradServer, setting,
                           inlineCallbacks, returnValue)
from labrad.units import Unit,Value

"""
### BEGIN NODE INFO
[info]
name = SPI Device Manager
version = 0.1
description = TODO

[startup]
cmdline = %PYTHON% %FILE%
timeout = 20

[shutdown]
message = 987654321
timeout = 5
### END NODE INFO
"""

class SPIDeviceManager(LabradServer):
    """
    TODO
    """
    name = 'SPI Device Manager'

__server__ = SPIDeviceManager()

if __name__ == '__main__':
    from labrad import util
    util.runServer(__server__)
