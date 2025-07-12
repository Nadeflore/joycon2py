from bleak import BleakScanner, BleakClient, BleakGATTCharacteristic
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData
import bluetooth
import asyncio
import logging
import sys
from utils import to_hex, decodeu, convert_mac_string_to_value
from controller import Controller, ControllerInputData
from discoverer import find_pairing_or_paired_device

logging.basicConfig()
logging.getLogger().setLevel(logging.INFO)
logger = logging.getLogger(__name__)

async def readDescriptors(client):
    for service in client.services:
        logger.info("[Service] %s", service)

        for char in service.characteristics:
            if "read" in char.properties:
                try:
                    value = await client.read_gatt_char(char.uuid)
                    extra = f", Value: {value}"
                except Exception as e:
                    extra = f", Error: {e}"
            else:
                extra = ""

            if "write-without-response" in char.properties:
                extra += f", Max write w/o rsp size: {char.max_write_without_response_size}"

            logger.info(
                "  [Characteristic] %s (%s)%s",
                char,
                ",".join(char.properties),
                extra,
            )

            for descriptor in char.descriptors:
                try:
                    value = await client.read_gatt_descriptor(descriptor.handle)
                    logger.info("    [Descriptor] %s, Value: %r", descriptor, value)
                except Exception as e:
                    logger.error("    [Descriptor] %s, Error: %s", descriptor, e)

async def main():
    host_mac = bluetooth.read_local_bdaddr()[0] 
    try:
        device = await find_pairing_or_paired_device()
        controller = await Controller.create_from_device(device)

        # await controller.pair(host_mac)

        await controller.set_leds(1)
        # await controller.enableFeatures(0xFF)

        read = await controller.read_memory(0x4F, 0x00013000)
        print(f"read {len(read)} bytes : {to_hex(read)}")

        def callback(inputData: ControllerInputData, controller: Controller):
            print_there(0,0,inputData)

        await controller.set_input_report_callback(callback)

        # for i in range(1,9):
        #     await controller.set_leds(i)
        #     await controller.play_vibration_preset(i)
        #     await asyncio.sleep(2)

        await asyncio.sleep(100000)
    finally:
        if controller:
            await controller.disconnect()



        

def print_there(x, y, text):
     sys.stdout.write("\x1b7\x1b[%d;%df%s\x1b8" % (x, y, text))
     sys.stdout.flush()

if __name__ == "__main__":
    asyncio.run(main())