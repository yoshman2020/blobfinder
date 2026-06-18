# camera/sentech_camera.py

import logging

import cv2
import numpy as np

try:
    import stapipy as st
except ImportError:
    st = None

from .base import CameraBase

logger = logging.getLogger(__name__)

# Image scale when displaying using OpenCV.
DISPLAY_RESIZE_FACTOR = 0.3


class SentechCamera(CameraBase):

    # Feature names
    GAIN = "Gain"
    GAIN_RAW = "GainRaw"

    EXPOSURE_TIME = "ExposureTime"
    EXPOSURE_TIME_RAW = "ExposureTimeRaw"  # Custom

    @classmethod
    def initialize(cls):
        pass

    @classmethod
    def shutdown(cls):
        pass

    @classmethod
    def discover(cls):
        if st is None:
            return []
        cameras = []
        st.initialize()  # type: ignore
        system_st = st.create_system()  # type: ignore
        while True:
            try:
                dev = system_st.create_first_device()
                cameras.append(
                    {
                        "type": "sentech",
                        "serial": dev.info.serial_number,
                        "name": f"Sentech {dev.info.display_name}",
                    }
                )
                break
            except Exception:
                break
        return cameras

    def __init__(self):
        self.st_device = None
        self.width = 0
        self.height = 0

    def open(self, serial: str) -> bool:
        st.initialize()  # type: ignore
        system = st.create_system()  # type: ignore
        while True:
            dev = system.create_first_device()
            if dev.info.serial_number == serial:
                self.st_device = dev

                # Create a datastream object for handling image stream data.
                self.st_datastream = self.st_device.create_datastream()

                # Start the image acquisition of the host (local machine) side.
                self.st_datastream.start_acquisition()

                # Start the image acquisition of the camera side.
                self.st_device.acquisition_start()

                # Get device nodemap to access the device settings.
                self.remote_nodemap = self.st_device.remote_port.nodemap

                return True

    def close(self):
        if self.st_device is None:
            return

        # Stop the image acquisition of the camera side
        self.st_device.acquisition_stop()

        # Stop the image acquisition of the host side
        self.st_datastream.stop_acquisition()

        self.st_device = None

    def read(self) -> tuple[bool, np.ndarray | None]:
        if not self.st_device or not self.st_datastream.is_grabbing:
            return False, None

        # Create a localized variable st_buffer using 'with'
        # Warning: if st_buffer is in a global scope, st_buffer must be
        #          assign to None to allow Garbage Collector release the buffer
        #          properly.
        with self.st_datastream.retrieve_buffer() as st_buffer:
            # Check if the acquired data contains image data.
            if not st_buffer.info.is_image_present:
                logger.error("Image data does not exist.")
                return False, None

            # Create an image object.
            st_image = st_buffer.get_image()
            self.width = st_image.width
            self.height = st_image.height

            # Display the information of the acquired image data.
            # print(
            #     "BlockID={0} Size={1} x {2} First Byte={3}".format(
            #         st_buffer.info.frame_id,
            #         st_image.width,
            #         st_image.height,
            #         st_image.get_image_data()[0],
            #     )
            # )

            # Check the pixelformat of the input image.
            pixel_format = st_image.pixel_format
            pixel_format_info = st.get_pixel_format_info(pixel_format)  # type: ignore

            # Only mono or bayer is processed.
            if not (pixel_format_info.is_mono or pixel_format_info.is_bayer):
                logger.info("Only mono or bayer is processed.")
                return False, None

            # Get raw image data.
            data = st_image.get_image_data()

            # Perform pixel value scaling if each pixel component is
            # larger than 8bit. Example: 10bit Bayer/Mono, 12bit, etc.
            if pixel_format_info.each_component_total_bit_count > 8:
                nparr = np.frombuffer(data, np.uint16)
                division = pow(
                    2, pixel_format_info.each_component_valid_bit_count - 8
                )
                nparr = (nparr / division).astype("uint8")
            else:
                nparr = np.frombuffer(data, np.uint8)

            # Process image for display.
            nparr = nparr.reshape(st_image.height, st_image.width, 1)

            # Perform color conversion for Bayer.
            if pixel_format_info.is_bayer:
                bayer_type = pixel_format_info.get_pixel_color_filter()
                if bayer_type == st.EStPixelColorFilter.BayerRG:  # type: ignore
                    nparr = cv2.cvtColor(nparr, cv2.COLOR_BAYER_RG2RGB)
                elif bayer_type == st.EStPixelColorFilter.BayerGR:  # type: ignore
                    nparr = cv2.cvtColor(nparr, cv2.COLOR_BAYER_GR2RGB)
                elif bayer_type == st.EStPixelColorFilter.BayerGB:  # type: ignore
                    nparr = cv2.cvtColor(nparr, cv2.COLOR_BAYER_GB2RGB)
                elif bayer_type == st.EStPixelColorFilter.BayerBG:  # type: ignore
                    nparr = cv2.cvtColor(nparr, cv2.COLOR_BAYER_BG2RGB)
            return True, nparr

    def get_setting(self, node_name) -> float | None:
        node = self.remote_nodemap.get_node(node_name)
        if node.principal_interface_type == st.EGCInterfaceType.IFloat:  # type: ignore
            node_value = st.PyIFloat(node)  # type: ignore
        elif node.principal_interface_type == st.EGCInterfaceType.IInteger:  # type: ignore
            node_value = st.PyIInteger(node)  # type: ignore
        else:
            return None
        return float(node_value.value)  # type: ignore

    def get_param(self, name) -> float | None:
        try:
            match name:
                case "width":
                    return float(self.width)
                case "height":
                    return float(self.height)
                case "fps":
                    return self.get_setting("AcquisitionFrameRate")
                case "gain":
                    if self.remote_nodemap.get_node(self.GAIN):
                        return self.get_setting(self.GAIN)
                    return self.get_setting(self.EXPOSURE_TIME_RAW)
                case "exposure":
                    if self.remote_nodemap.get_node(self.EXPOSURE_TIME):
                        return self.get_setting(self.EXPOSURE_TIME)
                    return self.get_setting(self.EXPOSURE_TIME_RAW)
            return None

        except Exception as e:
            logger.error(f"get_param error: {e}")
            return None

    def edit_setting(self, node_name, new_value):
        """
        Edit setting which has numeric type.

        :param node_name: Node name.
        :param value: New value.
        """
        node = self.remote_nodemap.get_node(node_name)
        if not node.is_writable:
            return
        if node.principal_interface_type == st.EGCInterfaceType.IFloat:  # type: ignore
            node_value = st.PyIFloat(node)  # type: ignore
            new_numeric_value = float(new_value)
        elif node.principal_interface_type == st.EGCInterfaceType.IInteger:  # type: ignore
            node_value = st.PyIInteger(node)  # type: ignore
            new_numeric_value = int(new_value)
        elif node.principal_interface_type == st.EGCInterfaceType.IEnumeration:  # type: ignore
            # Cast to PyIEnumeration from PyNode
            enum_node = st.PyIEnumeration(node)  # type: ignore
            enum_entries = enum_node.entries
            for index in range(len(enum_entries)):
                enum_entry = enum_entries[index]
                if (
                    enum_entry.is_available
                    and enum_entry.display_name == new_value
                ):
                    enum_node.set_int_value(enum_entry.value)
                    return
        else:
            return
        if node_value.min <= new_numeric_value <= node_value.max:  # type: ignore
            node_value.value = new_numeric_value  # type: ignore
            return

    def set_param(self, name, value) -> bool:
        try:
            match name:
                case "width":
                    return False
                case "height":
                    return False
                case "fps":
                    return False
                case "gain":
                    if self.remote_nodemap.get_node(self.GAIN):
                        self.edit_setting(self.GAIN, value)
                    self.edit_setting(self.EXPOSURE_TIME_RAW, value)
                    return True
                case "exposure":
                    # モードを露光時間に
                    self.edit_setting("ExposureMode", "Timed")
                    # 自動をOFFに
                    self.edit_setting("ExposureAuto", "Off")
                    if self.remote_nodemap.get_node(self.EXPOSURE_TIME):
                        self.edit_setting(self.EXPOSURE_TIME, value)
                    self.edit_setting(self.EXPOSURE_TIME_RAW, value)
                    return True
            return False

        except Exception as e:
            logger.error(f"set_param error: {e}")
            return False
