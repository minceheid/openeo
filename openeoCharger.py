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
from EO_comms.HomeHub import HomeHub
from EO_comms.MiniPro2 import MiniPro2
import globalState

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
        response = self.rs485.rx(recv_delay=0.5)
        if not response:
            _LOGGER.info("Response from serial was empty - possible serial overrun")
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
            #  If the address is stil None, try again to talk to the main board
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
            duty=int(requested_limit*(1/0.062))

        # Construct and send instruction packet.  Duty cycle must be uppercase.
        packet="+"+self.EO_COMMAND["SET_LIMIT"]+self.my_address+f'{duty:03X}'
        result = self.sendSerialCommand(packet)

        if result is None: #and self.using_spi:
            # try again
            result = self.sendSerialCommand(packet)

        if result is not None:
            # Perhaps stupidly, we've already stripped off the prefix, which puts the positions
            # for slicing the result string out by one, so let's put that prefix back on..
            result="!"+result
            # More values in the response that we may wish to inspect in due course
            self.version = result[1:3]
            self.current_switch_setting = result[3]
            self.control_pilot_voltage = result[4:7]
            self.charge_duty = result[7:10]
            self.plug_present_voltage = result[10:13]
            self.live_voltage = result[13:16]
            self.neutral_voltage = result[16:19]
            self.daylight_detection = result[19:22]
            self.mains_frequency = result[22:25]
            self.charger_state = result[25:27]
            self.relay_state = result[27]
            self.plug_state = result[28]
            self.HUB_duty_limit = result[29:32]
            self.charge_duty_timer = result[32:36]
            self.station_uptime = result[36:40]
            self.charge_time = result[40:44]
            self.state_of_mains = result[44:46]
            self.cp_line_state = result[46]
            self.station_ID = result[47]
            self.random_value = result[48:50]
            self.max_current = result[50:53]
            self.persistant_ID = result[53:61]
            self.watchdog_current = result[61:64]
            self.watchdog_time = result[64:67]
            self.p1_current = round(int(result[67:70], 16) / 10, 2)
            self.p2_current = round(int(result[70:73], 16) / 10, 2)
            self.p3_current = round(int(result[73:76], 16) / 10, 2)
            self.eco_7_switch = result[76]
            self.checksum = result[77:79]

            ct=self.rs485.get_ct_readings()
            self.current_site=ct["site"]
            self.current_vehicle=ct["vehicle"]
            self.current_solar=ct["solar"]

            # CT Calibration

            if "loadmanagement" in globalState.stateDict["_moduleDict"]:
                lm_config=globalState.stateDict["_moduleDict"]["loadmanagement"].pluginConfig
                ct_calibration_site=lm_config.get("ct_calibration_site",None)
                ct_calibration_vehicle=lm_config.get("ct_calibration_vehicle",None)
                ct_calibration_solar=lm_config.get("ct_calibration_solar",None)

                if ct_calibration_site is not None:
                    self.current_site=self.current_site*ct_calibration_site
                if ct_calibration_vehicle is not None:
                    self.current_vehicle=self.current_site*ct_calibration_vehicle
                if ct_calibration_solar is not None:
                    self.current_solar=self.current_site*ct_calibration_solar



            # Inject simulated values, for testing purposes
            if "loadmanagement" in globalState.stateDict["_moduleDict"]:
                simulate_ct_site=globalState.stateDict["_moduleDict"]["loadmanagement"].pluginConfig.get("simulate_ct_site",0)

                if simulate_ct_site>0:
                    self.current_site=simulate_ct_site

                simulate_ct_solar=globalState.stateDict["_moduleDict"]["loadmanagement"].pluginConfig.get("simulate_ct_solar",0)
                if simulate_ct_solar>0:
                    self.current_solar=simulate_ct_solar

            return True
        
        return None





    #################################################################################
    # Constructor methods
    def __init__(self):

        # Check hardware type, and initialise the correct object class for communications
        # At this time there is only two hardware types that we are supporting, so this
        # is easy, but extensible, if we find more.
        if MiniPro2.identify_hardware():
            self.rs485=MiniPro2()
        else:
            self.rs485=HomeHub()

        GPIO.setmode(GPIO.BCM)
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