#!/usr/bin/env python3

"""
Smart Card calibration information
for a 100A/0.333V CT clamp

    # MID meter 2A and 100A (approx)
    irms_min = 2.8785
    irms_n = 122.9345
    i_min = 2.294
    i_n = 98.038

    IRMSOS 79638.249651
    IGAIN -0.202518
    Register IRMSOS 79638 (00013716)
    Register IGAIN -1698847 (0fe613e1)

    # MID meter 5A and 65A (approx)
    irms_min = 6.7528
    irms_n = 80.8848
    i_min = 5.391
    i_n = 64.470

    IRMSOS 189532.608451
    IGAIN -0.202940
    Register IRMSOS 189532 (0002e45c)
    Register IGAIN -1702388 (0fe6060c)

    recommending the latter set
    With these values Amp registers are in 10 x mA
    i.e. 1A has an integer value of 10,000
"""

import time
import spidev
import RPi.GPIO as GPIO

import logging

# logging for use in this module
_LOGGER = logging.getLogger(__name__)

# SPI lines (BCM definitions)

SMART_CARD_A_PINS = {
    "SCK": 18,  # pin 12
    "MISO": 24,  # pin 18
    "MOSI": 23,  # pin 16
    "NSS": 25,  # pin 22
    "IRQ0": 20,  # pin 38
    "NRESET": 22,  # pin 15
    "CF1": 27,  # pin 13
    "PM1": 17,  # pin 11
}



# ------------------------------------------------------------------------------
class SPI_EM_IC(object):
    # Registers
    STATUS1 = 0xE503
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
    pinmap = {
        "SCK": 11,  # pin 23
        "MISO": 9,  # pin 21
        "MOSI": 10,  # pin 19
        "NSS": 7,  # pin 26
        "IRQ0": 20,  # pin 38
        "NRESET": 22,  # pin 15
        "CF1": 27,  # pin 13
        "PM1": 17,  # pin 11
    }
    def __init__(self):
        self.IRQ0 = self.pinmap["IRQ0"]
        self.NRESET = self.pinmap["NRESET"]
        self.CF1 = self.pinmap["CF1"]
        self.PM1 = self.pinmap["PM1"]
        self.spi = None
        self.configure_pins()
        self.reset()
        self.configure_spi()
        self.enable_spi()

    def configure_pins(self):
        # inputs
        GPIO.setup(self.IRQ0, GPIO.IN)

        # outputs
        for pin in (self.NRESET, self.PM1):
            GPIO.setup(pin, GPIO.OUT)

    def reset(self):
        GPIO.output(self.PM1, GPIO.LOW)
        GPIO.output(self.NRESET, GPIO.HIGH)
        time.sleep(0.001)
        GPIO.output(self.NRESET, GPIO.LOW)
        time.sleep(0.001)
        GPIO.output(self.NRESET, GPIO.HIGH)
        time.sleep(0.02)

    def configure_spi(self):
        self.spi = spidev.SpiDev()
        self.spi.open(0, 1)
        self.spi.max_speed_hz = 1000000
        self.spi.mode = 0b11

    def enable_spi(self):
        for i in range(3):
            self.spi.xfer2([0x00])
            time.sleep(0.001)

    def reg_get(self, register, size=4):
        # register always a two byte address
        assert size >= 1 and size <= 4

        #construct packet
        data = [1, register >> 8, register & 0xFF]
        data += [0] * size
        #print("data:",data)
        #send/recieve
        rx = self.spi.xfer2(data)[3:]
        result = 0
        for i in rx:
            result <<= 8
            result += i
        return result

    def reg_set(self, register, value, size=4):
        assert size >= 1 and size <= 4
        # Reverse the byte order of the value
        reverse = 0
        for i in range(size):
            reverse <<= 8
            reverse += value & 0xFF
            value >>= 8

        # construct packet
        data = [0, register >> 8, register & 0xFF]
        for i in range(size):
            data += [reverse & 0xFF]
            reverse >>= 8

        # send
        self.spi.xfer2(data)

    def configure(self):

        RMSOS = 0x0002E45C
        GAIN = 0x0FE6060C

        cfg = (
            (SPI_EM_IC.CFMODE, 0x0E88, 2),
            (SPI_EM_IC.CONFIG, 0, 2),
            (SPI_EM_IC.HPFDIS, 0, 4),
            (SPI_EM_IC.GAIN, 0, 2),
            (SPI_EM_IC.AIGAIN, GAIN, 4),
            (SPI_EM_IC.BIGAIN, GAIN, 4),
            (SPI_EM_IC.CIGAIN, GAIN, 4),
            (SPI_EM_IC.AIRMSOS, RMSOS, 4),
            (SPI_EM_IC.BIRMSOS, RMSOS, 4),
            (SPI_EM_IC.CIRMSOS, RMSOS, 4),
        )
        self.reg_set(self.RUN, 0, 2)

        # configure IC
        for reg, val, s in cfg:
            self.reg_set(reg, val, s)

        # update DSP pipeline
        self.reg_set(*cfg[-1])
        self.reg_set(*cfg[-1])

        # check
        for reg, val, s in cfg:
            res = self.reg_get(reg, s)
            if res != val:
                _LOGGER.error("Problem setting EM IC register 0x%04x" % reg)

        self.reg_set(self.RUN, 1,2)


# ------------------------------------------------------------------------------
def main():  # pragma: no cover

    GPIO.setmode(GPIO.BCM)
    sum = 0
    n = 0

    try:
        spi = SPI_EM_IC()

        spi.configure()

        time.sleep(2)
        print("ADE7858 version = %d" % spi.reg_get(spi.VERSION,1))
        while n<10:
            line1 = spi.reg_get(spi.AIRMS,4)
            line2 = spi.reg_get(spi.BIRMS,4)
            line3 = spi.reg_get(spi.CIRMS,4)

            print("%d\t%d\t%d" % (line1, line2, line3))
            sum += line2
            n += 1
    finally:
        GPIO.cleanup()
        print("avg = %f" % (sum / n))


# ------------------------------------------------------------------------------
if __name__ == "__main__":
    main()  # pragma: no cover
