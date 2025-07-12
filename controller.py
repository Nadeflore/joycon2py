from bleak import BleakScanner, BleakClient, BleakGATTCharacteristic
from bleak.backends.device import BLEDevice
import asyncio
import logging
import bluetooth
from dataclasses import dataclass
from utils import to_hex, decodeu, decodes, convert_mac_string_to_value

logging.basicConfig()
logging.getLogger().setLevel(logging.INFO)
logger = logging.getLogger(__name__)

# Controller identification info
NINTENDO_VENDOR_ID = 0x057e
JOYCON2_RIGHT_PID = 0x2066
JOYCON2_LEFT_PID = 0x2067
PRO_CONTROLLER2_PID = 0x2069
NSO_GAMECUBE_CONTROLLER_PID =  0x2073

CONTROLER_NAMES = {
    JOYCON2_RIGHT_PID: "Joy-con 2 (Right)",
    JOYCON2_LEFT_PID: "Joy-con 2 (Left)",
    PRO_CONTROLLER2_PID: "Pro Controller 2",
    NSO_GAMECUBE_CONTROLLER_PID: "NSO Gamecube Controller"
}

# BLE GATT Characteristics UUID
INPUT_REPORT_UUID = "ab7de9be-89fe-49ad-828f-118f09df7fd2"
COMMAND_WRITE_UUID = "649d4ac9-8eb7-4e6c-af44-1ea54fe5f005"
COMMAND_RESPONSE_UUID = "c765a961-d9d8-4d36-a20a-5315b111836a"

# Commands and subcommands
COMMAND_LEDS = 0x09
SUBCOMMAND_LEDS_SET_PLAYER = 0x07

COMMAND_VIBRATION = 0x0A
SUBCOMMAND_VIBRATION_PLAY_PRESET = 0x02

COMMAND_MEMORY = 0x02
SUBCOMMAND_MEMORY_READ = 0x04

COMMAND_PAIR = 0x15
SUBCOMMAND_PAIR_SET_MAC = 0x01
SUBCOMMAND_PAIR_LTK1 = 0x04
SUBCOMMAND_PAIR_LTK2 = 0x02
SUBCOMMAND_PAIR_FINISH = 0x03

COMMAND_FEATURE = 0x0c
SUBCOMMAND_FEATURE_INIT = 0x02
SUBCOMMAND_FEATURE_ENABLE = 0x04

FEATURE_MOTION = 0x04
FEATURE_MOUSE = 0x10
FEATURE_MAGNOMETER = 0x80

# Addresses in controller memory
ADDRESS_CONTROLLER_INFO = 0x00013000

#Repoduce switch led patterns for up to 8 players https://en-americas-support.nintendo.com/app/answers/detail/a_id/22424
LED_PATTERN = {
    1: 0x01,
    2: 0x03,
    3: 0x07,
    4: 0x0F,
    5: 0x09,
    6: 0x05,
    7: 0x0D,
    8: 0x06,
}


class Controller:
    def __init__(self, device: BLEDevice):
        self.device = device
        self.client = None
        self.controller_info = None
        self.response_future = None
        self.input_report_callback = None
        self.disconnected_callback = None

    def __repr__(self):
        return f"{CONTROLER_NAMES[self.controller_info.product_id]} : {self.device.address}"

    async def connect(self):
        if (self.client is not None):
            raise Exception("Already connected")
        
        def disconnected_callback(client: BleakClient):
            if (self.disconnected_callback is not None):
                self.disconnected_callback(self)
        
        self.client = BleakClient(self.device, disconnected_callback=disconnected_callback)
        await self.client.connect()
        logger.info(f"Connected to {self.device.address}")

        # Needed to get response from commands
        self.response_future = None
        def command_response_callback(sender: BleakGATTCharacteristic, data: bytearray):
            if self.response_future:
                self.response_future.set_result(data)
        await self.client.start_notify(COMMAND_RESPONSE_UUID, command_response_callback)

        # Read controller info
        self.controller_info = await self.read_controller_info()
        print(f"Succesfully initialized {self.device.address} : {self.controller_info}")

    @classmethod
    async def create_from_device(cls, device: BLEDevice):
        controller = cls(device)
        await controller.connect()
        return controller
    
    @classmethod
    async def create_from_mac_address(cls, mac_address):
        device = await BleakScanner.find_device_by_address(mac_address)
        return await cls.create_from_device(device)
        
    async def disconnect(self):
        if self.client and self.client.is_connected:
            await self.client.disconnect()


    ### Commands ###

    async def write_command(self, command_id: int, subcommand_id: int, command_data = b''):
        """Generic write command method"""
        command_buffer = command_id.to_bytes() + b"\x91\x01" + subcommand_id.to_bytes() + b"\x00" + len(command_data).to_bytes() + b"\x00\x00" + command_data
        logger.info(f"Req {to_hex(command_buffer)}")

        self.response_future = asyncio.get_running_loop().create_future()
        
        await self.client.write_gatt_char(COMMAND_WRITE_UUID, command_buffer)
        response_buffer = await self.response_future
        logger.info(f"Resp {to_hex(response_buffer)}")
        if len(response_buffer) < 8 or response_buffer[0] != command_id or response_buffer[1] != 0x01:
            raise Exception(f"Unexpected response : {response_buffer}")

        return response_buffer[8:]
    
    async def set_leds(self, player_number: int):
        """Set the player indicator led to the specified <player_number>"""
        if player_number > 8:
            player_number = 8

        # crash if less than 4 bytes of data, even though only one byte seems significant
        data = LED_PATTERN[player_number].to_bytes().ljust(4, b'\0')
        await self.write_command(COMMAND_LEDS, SUBCOMMAND_LEDS_SET_PLAYER, data)

    async def play_vibration_preset(self, preset_id: int):
        """Play one of the vibration preset <preset_id>: 1-7"""
        # crash if less than 4 bytes of data, even though only one byte seems significant
        await self.write_command(COMMAND_VIBRATION, SUBCOMMAND_VIBRATION_PLAY_PRESET, preset_id.to_bytes().ljust(4, b'\0'))

    async def read_memory(self, length: int, address: int):
        """Returns the requested <length> bytes of data located at <address>"""
        if length > 0x4F:
            raise Exception("Maximum read size is 0x4F bytes")
        data = await self.write_command(COMMAND_MEMORY, SUBCOMMAND_MEMORY_READ, length.to_bytes() + b'\x7e\0\0' + address.to_bytes(length=4,byteorder='little'))
        # Ensure the response is the data we requested
        if (data[0] != length or decodeu(data[4:8]) != address):
            raise Exception(f"Unexpected response from read commmand : {data}")
        return data[8:]

    async def read_controller_info(self):
        info = await self.read_memory(0x40, ADDRESS_CONTROLLER_INFO)
        return ControllerInfo(info)

    async def enableFeatures(self, feature_flags: int):
        """Enable or disable features according to <feature_flags>"""
        await self.write_command(COMMAND_FEATURE, SUBCOMMAND_FEATURE_INIT, feature_flags.to_bytes().ljust(4, b'\0'))
        await self.write_command(COMMAND_FEATURE, SUBCOMMAND_FEATURE_ENABLE, feature_flags.to_bytes().ljust(4, b'\0'))

    async def pair(self):
        """Pair this controller with the local bluetooth adapter"""
        mac_value = convert_mac_string_to_value(bluetooth.read_local_bdaddr()[0])
        # Real Switch2 actually sends 2 different mac addreses (switch 2 has 2 bluetooth adapter ?)
        await self.write_command(COMMAND_PAIR, SUBCOMMAND_PAIR_SET_MAC,b"\x00\x02" +  mac_value.to_bytes(6, 'little') + mac_value.to_bytes(6, 'little'))
        ltk1 = bytes([0x00, 0xea, 0xbd, 0x47, 0x13, 0x89, 0x35, 0x42, 0xc6, 0x79, 0xee, 0x07, 0xf2, 0x53, 0x2c, 0x6c, 0x31])
        await self.write_command(COMMAND_PAIR, SUBCOMMAND_PAIR_LTK1, ltk1)
        ltk2 = bytes([0x00, 0x40, 0xb0, 0x8a, 0x5f, 0xcd, 0x1f, 0x9b, 0x41, 0x12, 0x5c, 0xac, 0xc6, 0x3f, 0x38, 0xa0, 0x73])
        await self.write_command(COMMAND_PAIR, SUBCOMMAND_PAIR_LTK2, ltk2)
        await self.write_command(COMMAND_PAIR, SUBCOMMAND_PAIR_FINISH, b'\0')
    
    ### Callbacks ###

    async def set_input_report_callback(self, callback):
        if self.input_report_callback is None:
            # Enable notifiy if not done already
            def input_report_callback(sender, data):
                if self.input_report_callback is not None:
                    self.input_report_callback(ControllerInputData(data), self)
            await self.client.start_notify(INPUT_REPORT_UUID, input_report_callback)

        self.input_report_callback = callback

    ### Controller info

    def is_joycon_right(self):
        return self.controller_info.product_id == JOYCON2_RIGHT_PID

    def is_joycon_left(self):
        return self.controller_info.product_id == JOYCON2_LEFT_PID


@dataclass
class ControllerInputData:
    """Class for representing the input data received from controller."""
    raw_data: bytes
    time: int
    buttons: int
    left_stick: tuple[int, int]
    right_stick_x: tuple[int, int]
    mouse_coords: tuple[int, int]
    mouse_roughness: int
    mouse_distance: int
    magnometer: tuple[int, int, int]
    battery_voltage: int
    battery_current: int
    temperature: int
    accelerometer: tuple[int, int, int]
    gyroscope: tuple[int, int, int]


    def __init__(self, data: bytes):
        self.raw_data = data
        self.time = decodeu(data[0:4])
        self.buttons = decodeu(data[4:8])
        # 2 Unknown bytes data[8:10]
        self.left_stick = get_stick_xy(decodeu(data[10:13]))
        self.right_stick = get_stick_xy(decodeu(data[13:16]))
        self.mouse_coords = decodeu(data[16:18]), decodeu(data[18:20])
        self.mouse_roughness = decodeu(data[20:22])
        self.mouse_distance = decodeu(data[22:24])
        # 1 Unknown byte data[24:25]
        self.magnometer = decodes(data[25:27]), decodes(data[27:29]), decodes(data[29:31])
        self.battery_voltage = decodeu(data[31:33]) / 1000
        self.battery_current = decodeu(data[33:35]) / 100
        # 11 Unknown byte data[35:46]
        self.temperature = 25 + decodeu(data[46:48]) / 127
        self.accelerometer = decodes(data[48:50]), decodes(data[50:52]), decodes(data[52:54])
        self.gyroscope = decodes(data[54:56]), decodes(data[56:58]), decodes(data[58:60])



    BUTTONS = {
        "Y":     0x00000001,
        "X":     0x00000002,
        "B":     0x00000004,
        "A":     0x00000008,
        "SR_R":  0x00000010,
        "SL_R":  0x00000020,
        "R":     0x00000040,
        "ZR":    0x00000080,
        "MINUS": 0x00000100,
        "PLUS":  0x00000200,
        "R_STK": 0x00000400,
        "L_STK": 0x00000800,
        "HOME":  0x00001000,
        "CAPT":  0x00002000,
        "C":     0x00004000,
        # unused 0x00008000,
        "DOWN":  0x00010000,
        "UP":    0x00020000,
        "RIGHT": 0x00040000,
        "LEFT":  0x00080000,
        "SR_L":  0x00100000,
        "SL_L":  0x00200000,
        "L":     0x00400000,
        "ZL":    0x00800000,
    }

    def __str__(self):
        return f"""raw data : {to_hex(self.raw_data)}
time: {self.time}             
buttons_raw: {to_hex(self.buttons.to_bytes(length=4))}   
buttons: {", ".join([k for k,v in self.BUTTONS.items() if v & self.buttons])}                                                             
left_stick: {'{0: <5}'.format(self.left_stick[0])}, {'{0: <5}'.format(self.left_stick[1])}          
right_stick: {'{0: <5}'.format(self.right_stick[0])}, {'{0: <5}'.format(self.right_stick[1])}             
mouse (x,y,rugosity,distance): {'{0: <5}'.format(self.mouse_coords[0])}, {'{0: <5}'.format(self.mouse_coords[1])}, {'{0: <5}'.format(self.mouse_roughness)}, {'{0: <5}'.format(self.mouse_distance)}               
magnometer (x,y,z): {'{0: <5}'.format(self.magnometer[0])}, {'{0: <5}'.format(self.magnometer[1])}, {'{0: <5}'.format(self.magnometer[2])}            
battery voltage (V): {self.battery_voltage}
battery current(mA): {self.battery_current}           
temperature(°C): {self.temperature}      
accelerometer (x,y,z): {'{0: <5}'.format(self.accelerometer[0])}, {'{0: <5}'.format(self.accelerometer[1])}, {'{0: <5}'.format(self.accelerometer[2])}            
gyroscope (x,y,z): {'{0: <5}'.format(self.gyroscope[0])}, {'{0: <5}'.format(self.gyroscope[1])}, {'{0: <5}'.format(self.gyroscope[2])}            
        """
    
def get_stick_xy(value: int):
    x = value & 0xFFF
    y = value >> 12

    return x - 2047, y - 2047

@dataclass
class ControllerInfo:
    serial_number: str
    vendor_id: int
    product_id: int
    color1: bytes
    color2: bytes
    color3: bytes
    color4: bytes

    def __init__(self, data: bytes):
        self.serial_number = data[2:16].decode()
        self.vendor_id = decodeu(data[18:20])
        self.product_id = decodeu(data[20:22])
        self.color1 = data[25:28]
        self.color2 = data[28:31]
        self.color3 = data[31:34]
        self.color4 = data[34:37]
