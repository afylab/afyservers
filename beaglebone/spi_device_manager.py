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
    Manages autodetection and identification of SPI devices.

    The device manager listens for "SPI Device Connect" and
    "SPI Device Disconnect" messages coming from SPI bus servers.
    It attempts to identify the connected devices and forward the
    messages on to servers interested in particular devices.
    """
    name = 'SPI Device Manager'

    @inlineCallbacks
    def initServer(self):
        """Initialize the server after connecting to LabRAD."""
        self.knownDevices = {} # maps (server, channel) to (name, idn)
        self.deviceServers = {} # maps device name to list of interested servers.
                                # each interested server is {'target':<>,'context':<>,'messageID':<>}
        self.identLock = DeferredLock()

        # named messages are sent with source ID first, which we ignore
        connect_func = lambda c, (s, payload): self.spi_device_connect(*payload)
        disconnect_func = lambda c, (s, payload): self.spi_device_disconnect(*payload)
        mgr = self.client.manager
        self._cxn.addListener(connect_func, source=mgr.ID, ID=10)
        self._cxn.addListener(disconnect_func, source=mgr.ID, ID=11)
        yield mgr.subscribe_to_named_message('SPI Device Connect', 10, True)
        yield mgr.subscribe_to_named_message('SPI Device Disconnect', 11, True)

        # do an initial scan of the available GPIB devices
        yield self.refreshDeviceLists()

    @inlineCallbacks
    def refreshDeviceLists(self):
        """Ask all SPI bus servers for their available SPI devices."""
        servers = [s for n, s in self.client.servers.items()
                     if (('SPI Bus' in n) or ('spi_bus' in n)) and \
                        (('List Devices' in s.settings) or \
                         ('list_devices' in s.settings))]
        serverNames = [s.name for s in servers]
        print 'Pinging servers:', serverNames
        resp = yield DeferredList([s.list_devices() for s in servers])
        for serverName, (success, addrs) in zip(serverNames, resp):
            if not success:
                print 'Failed to get device list for:', serverName
            else:
                print 'Server %s has devices: %s' % (serverName, addrs)
                for addr in addrs:
                    self.spi_device_connect(serverName, addr)

    @inlineCallbacks
    def spi_device_connect(self, spiBusServer, channel):
        """Handle messages when devices connect."""
        print 'Device Connect:', spiBusServer, channel
        if (spiBusServer, channel) in self.knownDevices:
            return
        device, idnResult = yield self.lookupDeviceName(spiBusServer, channel)
        if device == UNKNOWN:
            device = yield self.identifyDevice(spiBusServer, channel, idnResult)
        self.knownDevices[spiBusServer, channel] = (device, idnResult)
        # forward message if someone cares about this device
        if device in self.deviceServers:
            self.notifyServers(device, spiBusServer, channel, True)

    def spi_device_disconnect(self, server, channel):
        """Handle messages when devices connect."""
        print 'Device Disconnect:', server, channel
        if (server, channel) not in self.knownDevices:
            return
        device, idnResult = self.knownDevices[server, channel]
        del self.knownDevices[server, channel]
        # forward message if someone cares about this device
        if device in self.deviceServers:
            self.notifyServers(device, server, channel, False)

__server__ = SPIDeviceManager()

if __name__ == '__main__':
    from labrad import util
    util.runServer(__server__)
