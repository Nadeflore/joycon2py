"""A class used to find switch 2 controllers via Bluetooth
"""
from bleak import BleakScanner, BleakClient, BleakGATTCharacteristic
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData
import asyncio
import logging
import bluetooth
import yaml
from utils import to_hex, convert_mac_string_to_value, decodeu
from controller import Controller, ControllerInputData, NINTENDO_VENDOR_ID, CONTROLER_NAMES
from virtual_controller import VirtualController
from config import CONFIG

NINTENDO_BLUETOOTH_MANUFACTURER_ID = 0x0553

async def find_pairing_or_paired_device():
    host_mac_value = convert_mac_string_to_value(bluetooth.read_local_bdaddr()[0])
    def filter(device: BLEDevice, advertising_data: AdvertisementData):
        nintendo_manufacturer_data = advertising_data.manufacturer_data.get(NINTENDO_BLUETOOTH_MANUFACTURER_ID)
        if nintendo_manufacturer_data:
            vendor_id = int.from_bytes(nintendo_manufacturer_data[3:5], byteorder='little')
            product_id = int.from_bytes(nintendo_manufacturer_data[5:7], byteorder='little')
            reconnect_mac = int.from_bytes(nintendo_manufacturer_data[10:16], byteorder='little')

            if vendor_id == NINTENDO_VENDOR_ID and product_id in CONTROLER_NAMES:
                if reconnect_mac == 0:
                    # Connect to device attempting to pair
                    print(f"Found pairing controller {device.address} {CONTROLER_NAMES[product_id]}")
                    return True
                if reconnect_mac == host_mac_value:
                    # Connect to device already paired to this bluetooth adapter
                    print(f"Found already paired controller {device.address} {CONTROLER_NAMES[product_id]} ")
                    return True
  
        return False
    
    return await BleakScanner.find_device_by_filter(filter)

class Discoverer:
    def __init__(self):
        pass

async def main():
    stop_event = asyncio.Event()

    # TODO: add something that calls stop_event.set()
    previous_data = {"data": None}
    def callback(device: BLEDevice, advertising_data: AdvertisementData):
        nintendo_manufacturer_data = advertising_data.manufacturer_data.get(NINTENDO_BLUETOOTH_MANUFACTURER_ID)
        if (nintendo_manufacturer_data and nintendo_manufacturer_data != previous_data["data"]):
            vendor_id = int.from_bytes(nintendo_manufacturer_data[3:5], byteorder='little')
            product_id = int.from_bytes(nintendo_manufacturer_data[5:7], byteorder='little')
            reconnect_mac = int.from_bytes(nintendo_manufacturer_data[10:16], byteorder='little')
            if (vendor_id != NINTENDO_VENDOR_ID):
                raise Exception(f"Unexpected vendor id {vendor_id}")
            
            print(f"Device found {device} data: {to_hex(nintendo_manufacturer_data)}")
            print(f"Found {device.address} {CONTROLER_NAMES[product_id]} Attempting to {('reconnect to ' + to_hex(reconnect_mac.to_bytes(length=6))) if reconnect_mac != 0 else 'pair'}")
            previous_data["data"] = nintendo_manufacturer_data

    async with BleakScanner(callback) as scanner:
        ...
        # Important! Wait for an event to trigger stop, otherwise scanner
        # will stop immediately.
        await stop_event.wait()


async def run():
    try:
        host_mac_value = convert_mac_string_to_value(bluetooth.read_local_bdaddr()[0])
        stop_event = asyncio.Event()
        connected_mac_addresses: list[str] = []
        virtual_controllers: list[VirtualController] = []

        def disconnected_controller(controller: Controller):
            print(f"Controller disconected {controller.client.address}")
            connected_mac_addresses.remove(controller.client.address)
            for vc in virtual_controllers[:]:
                if vc.remove_controller(controller):
                    virtual_controllers.remove(vc)
                    
            print (virtual_controllers)

        async def add_controller(device: BLEDevice, paired: bool):
            controller = await Controller.create_from_device(device)
            print(f"Connected to {device.address}")
            controller.disconnected_callback = disconnected_controller
            if not paired:
                await controller.pair()
                print(f"Paired successfully to {device.address}")

            virtual_controller = None
            
            if CONFIG.combine_joycons:
                # try to find an already connected joycon to combine with
                if controller.is_joycon_left():
                    virtual_controller = next(filter(lambda vc: vc.is_single_joycon_right(), virtual_controllers), None)
                elif controller.is_joycon_right():
                    virtual_controller = next(filter(lambda vc: vc.is_single_joycon_left(), virtual_controllers), None)

            if virtual_controller is None:
                virtual_controller = VirtualController(len(virtual_controllers) + 1)
                virtual_controllers.append(virtual_controller)
            
            await virtual_controller.add_controller(controller)

            print (virtual_controllers) 

        async def callback(device: BLEDevice, advertising_data: AdvertisementData):
            if device.address in connected_mac_addresses:
                return
            nintendo_manufacturer_data = advertising_data.manufacturer_data.get(NINTENDO_BLUETOOTH_MANUFACTURER_ID)
            if nintendo_manufacturer_data:
                vendor_id = decodeu(nintendo_manufacturer_data[3:5])
                product_id = decodeu(nintendo_manufacturer_data[5:7])
                reconnect_mac = decodeu(nintendo_manufacturer_data[10:16])
                if vendor_id == NINTENDO_VENDOR_ID and product_id in CONTROLER_NAMES:
                    if reconnect_mac == 0:
                        print(f"Found pairing device {CONTROLER_NAMES[product_id]} {device.address}")
                        connected_mac_addresses.append(device.address)
                        await add_controller(device, False)
                    elif reconnect_mac == host_mac_value:
                        print(f"Found already paired device {CONTROLER_NAMES[product_id]} {device.address}")
                        connected_mac_addresses.append(device.address)
                        await add_controller(device, True)

        async with BleakScanner(callback) as scanner:
            ...
            # Important! Wait for an event to trigger stop, otherwise scanner
            # will stop immediately.
            await stop_event.wait()
    finally:
        for vc in virtual_controllers:
            for controller in vc.controllers:
                await controller.disconnect()

if __name__ == "__main__":
    asyncio.run(run())