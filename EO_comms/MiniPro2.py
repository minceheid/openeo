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
                frequency = int(result[22:25], 16)
                amps_set = round(int(result[29:32],16)/(1/0.06))
                print("Voltage: {0}V    Frequency: {1}Hz    Amps Requested: {2}A    Amps Set: {3}A".format(voltage,frequency,amps_requested,amps_set))
                loop=loop+1
                time.sleep(5)
        else:
                print("No response")
