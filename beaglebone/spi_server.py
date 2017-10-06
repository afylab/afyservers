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


from labrad.server import LabradServer, setting
from labrad import util
from labrad.errors import DeviceNotSelectedError
import labrad.units as units
from twisted.internet.defer import inlineCallbacks
from twisted.internet.reactor import callLater
from bbio import *
from bbio.platform.beaglebone.spi import SPIBus


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

SPI = SPI1

class Slot(object):
    """
    Slots
    """
    def __init__(self, address=None, type=None):
        self.address = address
        self.type = type
        self.buscs = self.set_bus()
        self.chipselects = self.set_chipselects()

    def set_buscs(self):
        if self.type == None:
            return None
        #TODO

    def set_chipselects(self):
        if self.address == None or self.type == None:
            return dict()
        #TODO


class SPIBusServer(LabradServer):
    """Provides direct access to SPI-enabled devices."""
    name = '%LABRADNODE% SPI Bus'

    def initServer(self):
        # start refreshing only after we have started serving
        # this ensures that we are added to the list of available
        # servers before we start sending messages
        self.devices = {}
        callLater(0.1, self.startRefreshing)

    def startRefreshing(self):
        """Start periodically refreshing the list of devices.
        The start call returns a deferred which we save for later.
        When the refresh loop is shutdown, we will wait for this
        deferred to fire to indicate that it has terminated.
        """
        self.refreshDevices()

    def refreshDevices(self):
        """
        Refresh the list of known devices on this bus.
        """
        try:
            slots = self.detectDevices()
            addresses = [int(key) for key in slots]
            additions = set(addresses) - set(self.devices.keys())
            deletions = set(self.devices.keys()) - set(addresses)
            for addr in additions:
                try:
                    dev = slots[addr]
                    self.devices[addr] = dev
                    self.sendDeviceMessage('SPI Device Connect', addr)
                except Exception, e:
                    print 'Failed to add ' + addr + ':' + str(e)
            for addr in deletions:
                del self.devices[addr]
                self.sendDeviceMessage('SPI Device Disconnect', addr)
        except Exception, e:
            print 'Problem while refreshing devices: ', str(e)

    def detectDevices(self):
        """
        Query each slot for connected devices and returns a dictionary {addresses -> Slots}.
        """
        #TODO

    def sendDeviceMessage(self, msg, addr):
        print msg + ': ' + addr
        self.client.manager.send_named_message(msg, (self.name, addr))

    def getDevice(self, c):
        if 'addr' not in c:
            raise DeviceNotSelectedError("No SPI address selected")
        if c['addr'] not in self.devices:
            raise Exception('Could not find device ' + c['addr'])
        dev = self.devices[c['addr']]
        return dev

    @setting(0, addr='s', returns='s')
    def address(self, c, addr=None):
        """Get or set the GPIB address for this context.
        To get the addresses of available devices,
        use the list_devices function.
        """
        if addr is not None:
            c['addr'] = addr
        return c['addr']

    @setting(1, data='*i', returns='*i')
    def transfer(self, c, data):
        dev = self.getDevice(c)
        resp = SPI.transfer(dev.buscs, data)
        return resp

    @setting(20, returns='*s')
    def list_devices(self, c):
        """Get a list of devices on this bus."""
        return sorted(self.devices.keys())

    @setting(21)
    def refresh_devices(self, c):
        """Manually refresh devices"""
        self.refreshDevices()

__server__ = SPIBusServer()

if __name__ == '__main__':
    SPI.begin()
    util.runServer(__server__)
