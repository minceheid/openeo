#################################################################################
"""
OpenEO Charger: Class to abstract Charger Operations
Making use of the spi_485 module for serial comms with the controller board
within the EO hardware, this class astracts all operations, including discovering
the serial number of the EO controller board and setting the maximum charging rate. 

"""
#################################################################################
import logging
import RPi.GPIO as GPIO
from spi_485 import SPI_RS485

# logging for use in this module
_LOGGER = logging.getLogger(__name__)

#################################################################################
class openeoChargerClass:

    #################################################################################
    # A place to store the charger address
    my_address = None
    
    # Set if we're connected
    connected = False

    #################################################################################
    # Reference Data

    CHARGER_STATES = {
        0: "start",
        1: "settle-time",
        2: "test-incoming-mains",
        3: "mains-fault-start",
        4: "mains-fault",
        5: "idle-start",
        6: "idle",
        7: "plug-present-start",
        8: "plug-present",
        9: "car-connected-start",
        10: "car-connected",
        11: "charging-start",
        12: "charging",
        13: "charge-complete-start",
        14: "charge-complete",
        15: "charge-suspended-start",
        16: "charge-suspended",
        18: "charge-unknown-state"
    }

    EO_COMMAND = {
        "SET_LIMIT": "0",
        "DISCOVER": "1"
    }

    #################################################################################
    # Object Methods

    def generateChecksum(self, text):
        checksum = 0
        for byte in text.encode("ascii"):
            checksum += byte
        return "%02X" % (checksum & 0xFF)

    def checkCheckSum(self, text):
        checksum1 = int(text[-3:-1], 16)
        checksum2 = int(self.generateChecksum(text[:-3]), 16)
        return checksum1 == checksum2

    def sendSerialCommand(self, packet = ""):
        """
        Sends a serial command to the contoller, adding a checksum. Recieves response,
        checks the checksum, then strips the checksum off and returns the result
        """
        packet=packet+self.generateChecksum(packet)
        self.rs485.tx(packet)
        response = self.rs485.rx(recv_delay=3)
        if not response:
            _LOGGER.info("Response from serial was empty")
            return None
        try:
            response = response.decode("ascii")
        except UnicodeDecodeError:
            _LOGGER.error("Could not decode serial response")
            return None
        return response[1:-3]

    def set_amp_limit(self, requested_limit):
        """
        Set the amp limit by sending the appropriate PWM value to the controller
        """
        if self.my_address == None:
            #  If the address is stilL None, try again to talk to the main board
            self.connect()
            if self.my_address == None:
                _LOGGER.error("No comms with main board, cannot change current limit!")
                return

        if (not isinstance(requested_limit,(int)) or (requested_limit>32) or (requested_limit<0)):
            _LOGGER.warning("Requested Amp Limit out of bounds (0>=x>=32): %d" % requested_limit)
            return None

        # Calcualte duty cycle
        duty=0
        if requested_limit>=6:
            duty=round(requested_limit*(1/0.06))

        # Construct and send instruction packet
        packet="+"+self.EO_COMMAND["SET_LIMIT"]+self.my_address+f'{duty:03x}'
        result = self.sendSerialCommand(packet)

        if result is None: #and self.using_spi:
            # try again
            result = self.sendSerialCommand(packet)
        return result

    #################################################################################
    # Constructor methods
    def __init__(self):
        _LOGGER.debug("Initialising SPI/RS485")
        GPIO.setmode(GPIO.BCM)
        self.rs485 = SPI_RS485()
        self.connect()

    def connect(self):
        """
        Charger discovery - send command and retrieve the serial number of
        the connected controller board.  `connected` is True (and return result is True)
        if connection is successful.
        """
        _LOGGER.debug("Trying to connect to controller")
        
        self.my_address = self.sendSerialCommand("+"+ self.EO_COMMAND["DISCOVER"] +"5C")
        _LOGGER.debug("my_address set to '%s'" % str(self.my_address))
        
        if self.my_address == None or len(self.my_address) == 0:
            _LOGGER.error("couldn't communicate with controller board")
            self.connected = False
        else:
            self.connected = True
        
        return self.connected