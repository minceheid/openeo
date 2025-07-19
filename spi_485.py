#!/usr/bin/env python3

#################################################################################
import time
import spidev
import RPi.GPIO as GPIO
import logging

_LOGGER = logging.getLogger(__name__)

class SPI_RS485(object):

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

        while (recv_delay is not None) and (time.monotonic() - enter_timestamp < recv_delay):
            bytesWaiting=int(self._register_get(self.REG_RXLVL))

            if (bytesWaiting>0):
                rxbuffer = [0x80] + [0x00] * bytesWaiting
                data += bytes(self.spi.xfer2(rxbuffer)[1:])
                OverrunError = int(self._register_get(self.REG_LSR)) & self.BIT_OVERRUN
                if (OverrunError!=0):
                    _LOGGER.debug("rx - Overrun error")
                    print("Warning - RS485 overrun")
            else:
                time.sleep(0.001)

        return bytes(data)



def main():
    # Just some tests
    rs485=SPI_RS485()
    rs485.tx("+15C")
    result=rs485.rx(recv_delay=3)
    print("result:"+str(result))
    #rs485.tx("+0000082EA0009B")
    #result=rs485.rx()
    #print("result:"+str(result))

#main()