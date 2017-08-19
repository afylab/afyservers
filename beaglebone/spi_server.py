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


from labrad.server import LabradServer
from labrad import util
from labrad.errors import DeviceNotSelectedError
import labrad.units as units
from twisted.internet.defer import inlineCallbacks


"""
### BEGIN NODE INFO
[info]
name = SPI Bus
version = 0.1
description = TODO
instancename = %LABRADNODE% SPI Bus

[startup]
cmdline = %PYTHON% %FILE%
timeout = 20

[shutdown]
message = 987654321
timeout = 20
### END NODE INFO
"""


class SPIBusServer(LabradServer):
    """Provides direct access to GPIB-enabled devices."""
    name = '%LABRADNODE% SPI Bus'

__server__ = SPIBusServer()

if __name__ == '__main__':
    util.runServer(__server__)
