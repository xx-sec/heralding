# Copyright (C) 2016 Johnny Vestergaard <jkv@unixcluster.dk>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import logging

import zmq.green as zmq
from gevent import Greenlet
import gevent
import gevent.lock

import heralding.misc
from heralding.misc.socket_names import SocketNames

logger = logging.getLogger(__name__)


class ReportingRelay(Greenlet):
    _incommingLogQueue = None
    _incommingLogQueueLock = gevent.lock.BoundedSemaphore()

    def __init__(self):
        Greenlet.__init__(self)

        # we are singleton
        ReportingRelay._incommingLogQueueLock.acquire()
        assert ReportingRelay._incommingLogQueue is None
        ReportingRelay._incommingLogQueue = gevent.queue.Queue()
        ReportingRelay._incommingLogQueueLock.release()

        self.enabled = True

        context = heralding.misc.zmq_context
        self.internalReportingPublisher = context.socket(zmq.PUB)


    @staticmethod
    def queueLogData(data):
        assert ReportingRelay._incommingLogQueue is not None
        ReportingRelay._incommingLogQueue.put(data)

    def _run(self):
        context = heralding.misc.zmq_context

        self.internalReportingPublisher.bind(SocketNames.INTERNAL_REPORTING.value)

        while self.enabled:
            try:
                data  = ReportingRelay._incommingLogQueue.get(timeout=0.5)
                self.internalReportingPublisher.send_pyobj(data)
            except gevent.queue.Empty:
                pass

        self.internalReportingPublisher.close()

        # None is also used to signal we are all done
        ReportingRelay._incommingLogQueueLock.acquire()
        ReportingRelay._incommingLogQueue = None
        ReportingRelay._incommingLogQueueLock.release()

    def stop(self):
        self.enabled = False
        while True:
                try:
                    ReportingRelay._incommingLogQueueLock.acquire()
                    if ReportingRelay._incommingLogQueue is not None:
                        gevent.sleep(0.1)
                    else:
                        break
                finally:
                    ReportingRelay._incommingLogQueueLock.release()
                    gevent.sleep()