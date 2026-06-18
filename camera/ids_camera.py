try:
    from ids_peak import ids_peak, ids_peak_ipl_extension
except ImportError:
    ids_peak = None

import logging

from numpy import ndarray

from .base import CameraBase

logger = logging.getLogger(__name__)


class IDSCamera(CameraBase):

    _initialized = False

    PARAMS = {
        "width": "Width",
        "height": "Height",
        "fps": "AcquisitionFrameRate",
        "gain": "Gain",
        "exposure": "ExposureTime",
        "brightness": "Brightness",
    }

    @classmethod
    def initialize(cls):
        if ids_peak is None:
            return
        if not cls._initialized:
            ids_peak.Library.Initialize()
            cls._initialized = True

    @classmethod
    def shutdown(cls):
        if ids_peak is None:
            return
        if cls._initialized:
            ids_peak.Library.Close()
            cls._initialized = False

    @classmethod
    def discover(cls):
        if ids_peak is None:
            return []
        cameras = []
        dm = ids_peak.DeviceManager.Instance()
        dm.Update()

        for dev in dm.Devices():
            cameras.append(
                {
                    "type": "ids",
                    "serial": dev.SerialNumber(),
                    "name": f"IDS {dev.ModelName()}",
                }
            )
        return cameras

    def __init__(self):
        self.device = None
        self.setup()

    def setup(self):
        if ids_peak is None:
            raise RuntimeError("ids_peak is not installed")
        try:
            # Create a DeviceManager object
            self.device_manager = ids_peak.DeviceManager.Instance()

            # The returned callback object needs to be stored in a variable and
            # needs to live as long as the class that would call it,
            # so as long as the device manager in this case
            # If the callback gets garbage collected it deregisters itself
            device_found_callback = self.device_manager.DeviceFoundCallback(
                lambda found_device: logger.info(
                    "Found-Device-Callback: Key={}".format(found_device.Key()),
                )
            )
            device_found_callback_handle = (
                self.device_manager.RegisterDeviceFoundCallback(
                    device_found_callback
                )
            )

            # Update the DeviceManager
            self.device_manager.Update()
            # The callback can also be unregistered explicitly using the returned
            # handle
            self.device_manager.UnregisterDeviceFoundCallback(
                device_found_callback_handle
            )

            # Exit program if no device was found
            if not self.device_manager.Devices():
                logger.info("No device found.")
        except Exception as e:
            logger.error(f"Exception: {e}")

    def open(self, serial: str) -> bool:
        if ids_peak is None:
            return False
        try:
            for dev in self.device_manager.Devices():
                if dev.SerialNumber() == serial:
                    # Open device
                    self.device = dev.OpenDevice(
                        ids_peak.DeviceAccessType_Control
                    )

                    # Nodemap for accessing GenICam nodes
                    self.remote_nodemap = self.device.RemoteDevice().NodeMaps()[
                        0
                    ]

                    # Load default camera settings
                    self.remote_nodemap.FindNode(
                        "UserSetSelector"
                    ).SetCurrentEntry(  # type: ignore
                        "Default"
                    )
                    self.remote_nodemap.FindNode("UserSetLoad").Execute()  # type: ignore
                    self.remote_nodemap.FindNode("UserSetLoad").WaitUntilDone()  # type: ignore

                    # Open first data stream
                    self.data_stream = self.device.DataStreams()[
                        0
                    ].OpenDataStream()
                    # Buffer size
                    self.payload_size = self.remote_nodemap.FindNode(
                        "PayloadSize"
                    ).Value()  # type: ignore

                    # Minimum number of required buffers
                    self.buffer_count_max = (
                        self.data_stream.NumBuffersAnnouncedMinRequired()
                    )

                    # Allocate buffers and add them to the pool
                    for buffer_count in range(self.buffer_count_max):
                        # Let the TL allocate the buffers
                        buffer = self.data_stream.AllocAndAnnounceBuffer(
                            self.payload_size  # type: ignore
                        )
                        # Put the buffer in the pool
                        self.data_stream.QueueBuffer(buffer)

                    # Lock writeable nodes during acquisition
                    self.remote_nodemap.FindNode("TLParamsLocked").SetValue(1)  # type: ignore

                    logger.info("Starting acquisition...")
                    self.data_stream.StartAcquisition()
                    self.remote_nodemap.FindNode("AcquisitionStart").Execute()  # type: ignore
                    self.remote_nodemap.FindNode(
                        "AcquisitionStart"
                    ).WaitUntilDone()  # type: ignore

                    return True
        except Exception as e:
            logger.error(f"Exception: {e}")
        return False

    def close(self):
        if ids_peak is None:
            return
        logger.info("Stopping acquisition...")
        try:
            self.remote_nodemap.FindNode("AcquisitionStop").Execute()  # type: ignore
            self.remote_nodemap.FindNode("AcquisitionStop").WaitUntilDone()  # type: ignore

            self.data_stream.StopAcquisition(
                ids_peak.AcquisitionStopMode_Default
            )

            # In case another thread is waiting on WaitForFinishedBuffer
            # you can interrupt it using:
            # data_stream.KillWait()

            # Remove buffers from any associated queue
            self.data_stream.Flush(ids_peak.DataStreamFlushMode_DiscardAll)

            for buffer in self.data_stream.AnnouncedBuffers():
                # Remove buffer from the transport layer
                self.data_stream.RevokeBuffer(buffer)

            # Unlock writeable nodes again
            self.remote_nodemap.FindNode("TLParamsLocked").SetValue(0)  # type: ignore

        except Exception as e:
            logger.error(f"Exception: {e}")
        finally:
            self.device = None

    def read(self) -> tuple[bool, ndarray | None]:
        try:
            # Wait for finished/filled buffer event
            buffer = self.data_stream.WaitForFinishedBuffer(1000)  # type: ignore
            img = ids_peak_ipl_extension.BufferToImage(buffer)  # type: ignore

            # Do something with `img` here ...

            # Put the buffer back in the pool, so it can be filled again
            # NOTE: If you want to use `img` beyond this point, you have
            #       to make a copy, since `img` still uses the underlying
            #       buffer's memory.
            self.data_stream.QueueBuffer(buffer)
            return True, img.get_numpy()
        except Exception as e:
            logger.error(f"Exception: {e}")
            return False, None

    def get_param(self, name) -> float | None:
        try:
            if self.device is None:
                return None

            node_name = self.PARAMS.get(name)
            if node_name is None:
                return None

            node = self.remote_nodemap.FindNode(node_name)

            val = node.Value()  # type: ignore
            return float(val)

        except Exception as e:
            logger.error(f"get_param error: {e}")
            return None

    def set_param(self, name, value) -> bool:
        try:
            if self.device is None:
                return False

            node_name = self.PARAMS.get(name)
            if node_name is None:
                return False

            node = self.remote_nodemap.FindNode(node_name)
            node.SetValue(value)  # type: ignore
            return True

        except Exception as e:
            logger.error(f"set_param error: {e}")
            return False
