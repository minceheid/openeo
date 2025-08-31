#!/usr/bin/env python3

#################################################################################
import time,re,spidev,logging
import RPi.GPIO as GPIO
import globalState
from EO_comms.HomeHub import HomeHub

_LOGGER = logging.getLogger(__name__)

# The MiniPro3 Comms Library inherits from the HomeHub Comms library
# Very little code is shared between them at this point, but maintining the relationship between the
# classes appears to be a reasonable thing to do
class MiniPro2(HomeHub):


    # GPIO chip reset line (BCM definition)
    NRESET = 16

    # Registers for serial comms
    REG_DLL = 0
    REG_DLH = 1
    REG_EFR = 2
    REG_FCR_IIR = 2
    REG_LCR = 3
    REG_MCR = 4
    REG_LSR = 5 # Line Status Register - Bit 1 is responsible for overrun error existance. 
                # This error usually occurs when the data are read from the port slower than they are received. 
                # If you don't read the incoming bytes fast enough the last byte can be overwritten with the byte which was received last, 
                # in this case the last byte may be lost which will cause overrun error.
    REG_RXLVL = 9 # RX Level / Number of bytes awaiting to be read
    REG_EFCR = 15

    spi = None
    # bits
    BIT_OVERRUN = 0x02

    @classmethod
    def identify_hardware(self):
        revision = "0000"
        with open("/proc/cpuinfo", "r") as myfile:
            for line in myfile:
                    m=re.search(r"^Revision.+: (.+)$",line)
                    if m:
                        revision=m.group(1)
        #print("Identifying: CPU revision", revision)
        return revision in["900092","900093","9000c1","902120"]


    def _register_set(self,reg, val):
        reg <<= 3
        self.spi.xfer2([reg, val])

    def _register_get(self,reg):
        reg <<= 3
        reg |= 0x80
        res = self.spi.xfer2([reg, 0x00])
        return res[1]

    def __init__(self):
        # Setup GPIO
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.NRESET, GPIO.OUT)
        GPIO.output(self.NRESET, GPIO.LOW)
        time.sleep(0.001)
        GPIO.output(self.NRESET, GPIO.HIGH)

        # Open SPI
        self.spi = spidev.SpiDev()
        self.spi.open(0, 0)
        self.spi.max_speed_hz = 1000000

        self._register_set(self.REG_LCR, 0x80)
        self._register_set(self.REG_DLL, 1)
        self._register_set(self.REG_DLH, 0)
        self._register_set(self.REG_LCR, 0xBF)
        self._register_set(self.REG_EFR, 0)
        self._register_set(self.REG_LCR, 0x03)
        self._register_set(self.REG_FCR_IIR, 0x07)
        self._register_set(self.REG_EFCR, 0x30)
        _LOGGER.debug("EO COMMS - HomeHub initialised")

        # Create an object for communicating with the energy monitor
        # IC over SPI 0,1
        self.ct=CtSpiClass()


    def tx(self,command):
        self._register_set(self.REG_FCR_IIR, 0x07)
        data = [0]
        for c in command.encode("ascii"):
            data.append(int(c))

        data.append(int(13))
        self.spi.xfer2(data)
    
    def rx(self, recv_delay=3):
        data=b""
        enter_timestamp = time.monotonic()

        overrun=0
        while (recv_delay is not None) and (time.monotonic() - enter_timestamp < recv_delay):
            bytesWaiting=int(self._register_get(self.REG_RXLVL))

            if (bytesWaiting>0):
                rxbuffer = [0x80] + [0x00] * bytesWaiting
                data += bytes(self.spi.xfer2(rxbuffer)[1:])
                OverrunError = int(self._register_get(self.REG_LSR)) & self.BIT_OVERRUN
                if (OverrunError!=0):
                    _LOGGER.debug("rx - Overrun error")
                    print("Warning - RS485 overrun")
                    overrun=overrun+1
            else:
                time.sleep(0.001)

        if overrun>0:
            globalState.stateDict["eo_serial_errors"]=globalState.stateDict["eo_serial_errors"]+1
            return None
        else:
             return bytes(data)

    def get_ct_readings(self):
        """
        Retrieves CT readings.
        """

        return({ 
                "site":     self.ct.reg_get(self.ct.AIRMS,4)/10000,
                "vehicle":  self.ct.reg_get(self.ct.BIRMS,4)/10000,
                "solar":    self.ct.reg_get(self.ct.CIRMS,4)/10000})


    def test(self):
        # Just some tests
        def generateChecksum(text):
            checksum = 0
            for byte in text.encode("ascii"):
                checksum += byte
            return "%02X" % (checksum & 0xFF)

        comms=MiniPro2()
        comms.tx("+15C")
        result=comms.rx(recv_delay=3)

        if result:
            address=result[1:-3].decode("ascii")
            print("address: "+str(address))

            loop=0
            while loop<5:
                amps_requested=32*(loop%2)
                duty=round(amps_requested*(1/0.06))
                packet="+0"+address+f'{duty:03X}'
                packet=packet+generateChecksum(packet)

                comms.tx(packet) 
                result = comms.rx(0.6)
                
                voltage = round(int(result[13:16], 16) / 3.78580786, 1) # divisor is an estimate, based on voltmeter readings
                amps_set = round(int(result[29:32],16)/(1/0.06))
                p1_current = round(int(result[67:70],16)/(1/0.06),1)
                p2_current = round(int(result[70:73],16)/(1/0.06),1)
                p3_current = round(int(result[73:76],16)/(1/0.06),1)
                
                # Get CT readings
                ct=self.get_ct_readings()
   
                print(f"Voltage:{voltage:>7}V | Amps Requested: {amps_requested:>2}A | Amps Set: {amps_set:>2}A | site:{ct['site']:>5.1f}A | vehicle:{ct['vehicle']:>5.1f}A | solar:{ct['solar']:>5.1f}A")
                loop=loop+1
                time.sleep(5)
        else:
                print("No response")

# ------------------------------------------------------------------------------
class CtSpiClass(object):
    # Registers
    #STATUS1 = 0xE503
    RUN = 0xE228
    CFMODE = 0xE610
    CONFIG = 0xE618
    HPFDIS = 0x43B6
    GAIN = 0xE60F
    VERSION = 0xE707

    AIGAIN = 0x4380
    BIGAIN = 0x4382
    CIGAIN = 0x4384

    AIRMSOS = 0x4387
    BIRMSOS = 0x4389
    CIRMSOS = 0x438B

    AIRMS = 0x43C0
    BIRMS = 0x43C2
    CIRMS = 0x43C4

    def __init__(self):
        self.IRQ0 = 20 
        self.NRESET = 22
        self.PM1 = 17
        self.spi = None

        # Set up GPIO Pins
        GPIO.setup(self.IRQ0, GPIO.IN)
        GPIO.setup(self.NRESET, GPIO.OUT)
        GPIO.setup(self.PM1, GPIO.OUT)

        # Reset
        GPIO.output(self.PM1, GPIO.LOW)
        GPIO.output(self.NRESET, GPIO.HIGH)
        time.sleep(0.001)
        GPIO.output(self.NRESET, GPIO.LOW)
        time.sleep(0.001)
        GPIO.output(self.NRESET, GPIO.HIGH)
        time.sleep(0.02)

        # Configure and Enable SPI
        self.spi = spidev.SpiDev()
        self.spi.open(0, 1)
        self.spi.max_speed_hz = 1000000
        self.spi.mode = 0b11

        # Enable SPI with three calls to xfer2()
        for i in range(3):
            self.spi.xfer2([0x00])
            time.sleep(0.001)

        self.configure()


    def configure(self):

        RMSOS = 0x0002E45C
        GAIN = 0x0FE6060C

        cfg = (
            (CtSpiClass.CFMODE, 0x0E88, 2),
            (CtSpiClass.CONFIG, 0, 2),
            (CtSpiClass.HPFDIS, 0, 4),
            (CtSpiClass.GAIN, 0, 2),
            (CtSpiClass.AIGAIN, GAIN, 4),
            (CtSpiClass.BIGAIN, GAIN, 4),
            (CtSpiClass.CIGAIN, GAIN, 4),
            (CtSpiClass.AIRMSOS, RMSOS, 4),
            (CtSpiClass.BIRMSOS, RMSOS, 4),
            (CtSpiClass.CIRMSOS, RMSOS, 4),
        )
        self.reg_set(self.RUN, 0, 2)

        # configure IC by setting all cfg settings
        for reg, val, s in cfg:
            self.reg_set(reg, val, s)

        # update DSP pipeline
        self.reg_set(*cfg[-1])
        self.reg_set(*cfg[-1])

        #validate that all settings were made
        for reg, val, s in cfg:
            res = self.reg_get(reg, s)
            if res != val:
                _LOGGER.error("Problem setting EM IC register 0x%04x" % reg)

        self.reg_set(self.RUN, 1,2)

    def reg_get(self, register, size=4):
        # register always a two byte address
        assert size >= 1 and size <= 4

        #construct packet
        data = [1]
        data += list(register.to_bytes(2,"big"))
        data += [0] * size

        #send/recieve
        rx = self.spi.xfer2(data)[3:]
        return(int.from_bytes(rx,"big",signed=False))

    def reg_set(self, register, value, size=4):
        assert size >= 1 and size <= 4

        # construct packet
        data = [0]
        data += list(register.to_bytes(2,"big"))
        data += list(value.to_bytes(size,"big"))

        # send
        self.spi.xfer2(data)