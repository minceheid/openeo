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

SMART_CARD_B_PINS = {
    "SCK": 11,  # pin 23
    "MISO": 9,  # pin 21
    "MOSI": 10,  # pin 19
    "NSS": 7,  # pin 26
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

    def __init__(self, pinmap=SMART_CARD_B_PINS):
        self.IRQ0 = pinmap["IRQ0"]
        self.NRESET = pinmap["NRESET"]
        self.CF1 = pinmap["CF1"]
        self.PM1 = pinmap["PM1"]
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

    def reg_get(self, reg, s=4):
        assert s >= 1 and s <= 4
        data = [1, reg >> 8, reg & 0xFF]
        data += [0] * s
        rx = self.spi.xfer2(data)[3:]
        res = 0
        for i in rx:
            res <<= 8
            res += i
        return res

    def reg_set(self, reg, val, s=4):
        assert s >= 1 and s <= 4
        rev = 0
        for i in range(s):
            rev <<= 8
            rev += val & 0xFF
            val >>= 8

        data = [0, reg >> 8, reg & 0xFF]
        for i in range(s):
            data += [rev & 0xFF]
            rev >>= 8

        self.spi.xfer2(data)

    def reg32_get(self, reg):
        return self.reg_get(reg, 4)

    def reg16_get(self, reg):
        return self.reg_get(reg, 2)

    def reg8_get(self, reg):
        return self.reg_get(reg, 1)

    def reg32_set(self, reg, val):
        self.reg_set(reg, val, 4)

    def reg16_set(self, reg, val):
        self.reg_set(reg, val, 2)

    def reg8_set(self, reg, val):
        self.reg_set(reg, val, 1)

    def stop_dsp(self):
        self.reg16_set(self.RUN, 0)

    def start_dsp(self):
        self.reg16_set(self.RUN, 1)

    def configure(self, cfg):
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


# ------------------------------------------------------------------------------
class SPI_EM_IC_NSS(SPI_EM_IC):  # pragma: no cover
    # same as SPI_EM_IC but manually manages the NSS pin

    def __init__(self, pinmap=SMART_CARD_B_PINS, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.NSS = pinmap["NSS"]

    def configure_pins(self):
        super().configure_pins()
        GPIO.setup(self.NSS, GPIO.OUT)

    def reset(self):
        GPIO.output(self.NSS, GPIO.HIGH)
        super().reset()

    def configure_spi(self):
        super().configure_spi()
        self.spi.no_cs = True

    def enable_spi(self):
        for i in range(3):
            GPIO.output(self.NSS, GPIO.LOW)
            time.sleep(0.001)
            GPIO.output(self.NSS, GPIO.HIGH)
            time.sleep(0.001)

    def reg_get(self, *args, **kwargs):
        GPIO.output(self.NSS, GPIO.LOW)
        res = super().reg_get(*args, **kwargs)
        GPIO.output(self.NSS, GPIO.HIGH)
        return res

    def reg_set(self, *args, **kwargs):
        GPIO.output(self.NSS, GPIO.LOW)
        super().reg_set(*args, **kwargs)
        GPIO.output(self.NSS, GPIO.HIGH)


# ------------------------------------------------------------------------------
class GPIO_EM_IC(object):  # pragma: no cover
    # Registers
    STATUS1 = 0xE503
    RUN = 0xE228
    CFMODE = 0xE610
    CONFIG = 0xE618
    HPFDIS = 0x43B6
    GAIN = 0xE60F

    AIGAIN = 0x4380
    BIGAIN = 0x4382
    CIGAIN = 0x4384

    AIRMSOS = 0x4387
    BIRMSOS = 0x4389
    CIRMSOS = 0x438B

    AIRMS = 0x43C0
    BIRMS = 0x43C2
    CIRMS = 0x43C4

    def __init__(self, pinmap=SMART_CARD_A_PINS):
        self.IRQ0 = pinmap["IRQ0"]
        self.NSS = pinmap["NSS"]
        self.MISO = pinmap["MISO"]
        self.MOSI = pinmap["MOSI"]
        self.NRESET = pinmap["NRESET"]
        self.CF1 = pinmap["CF1"]
        self.SCK = pinmap["SCK"]
        self.PM1 = pinmap["PM1"]

        self.configure_pins()
        self.reset()
        self.enable_spi()

    def configure_pins(self):
        # inputs
        for pin in (self.IRQ0, self.MISO, self.CF1):
            GPIO.setup(pin, GPIO.IN)

        # outputs
        for pin in (self.NSS, self.MOSI, self.NRESET, self.SCK, self.PM1):
            GPIO.setup(pin, GPIO.OUT)

    def reset(self):
        GPIO.output(self.NSS, GPIO.HIGH)
        GPIO.output(self.SCK, GPIO.HIGH)

        GPIO.output(self.PM1, GPIO.LOW)
        GPIO.output(self.NRESET, GPIO.HIGH)
        time.sleep(0.001)
        GPIO.output(self.NRESET, GPIO.LOW)
        time.sleep(0.001)
        GPIO.output(self.NRESET, GPIO.HIGH)
        time.sleep(0.02)

    def enable_spi(self):
        for i in range(3):
            GPIO.output(self.NSS, GPIO.LOW)
            time.sleep(0.001)
            GPIO.output(self.NSS, GPIO.HIGH)
            time.sleep(0.001)

    def reg_get(self, reg, s=4):
        assert s >= 1 and s <= 4
        res = 0
        GPIO.output(self.NSS, GPIO.LOW)
        self._tx_byte(1)
        self._tx_byte(reg >> 8)
        self._tx_byte(reg & 0xFF)
        for i in range(s):
            res <<= 8
            res += self._rx_byte()
        GPIO.output(self.NSS, GPIO.HIGH)
        return res

    def reg_set(self, reg, val, s=4):
        assert s >= 1 and s <= 4
        rev = 0
        for i in range(s):
            rev <<= 8
            rev += val & 0xFF
            val >>= 8
        GPIO.output(self.NSS, GPIO.LOW)
        self._tx_byte(0)
        self._tx_byte(reg >> 8)
        self._tx_byte(reg & 0xFF)
        for i in range(s):
            self._tx_byte(rev & 0xFF)
            rev >>= 8
        GPIO.output(self.NSS, GPIO.HIGH)

    def reg32_get(self, reg):
        return self.reg_get(reg, 4)

    def reg16_get(self, reg):
        return self.reg_get(reg, 2)

    def reg8_get(self, reg):
        return self.reg_get(reg, 1)

    def reg32_set(self, reg, val):
        self.reg_set(reg, val, 4)

    def reg16_set(self, reg, val):
        self.reg_set(reg, val, 2)

    def reg8_set(self, reg, val):
        self.reg_set(reg, val, 1)

    def stop_dsp(self):
        self.reg16_set(self.RUN, 0)

    def start_dsp(self):
        self.reg16_set(self.RUN, 1)

    def configure(self, cfg):
        # configure IC
        for reg, val, s in cfg:
            self.reg_set(reg, val, s)

        # update DSP pipeline
        self.reg_set(*cfg[-1])

        # check
        for reg, val, s in cfg:
            res = self.reg_get(reg, s)
            if res != val:
                _LOGGER.error("Problem setting EM IC register 0x%04x" % reg)

    def _tx_byte(self, b):
        for i in range(8):
            GPIO.output(self.SCK, GPIO.LOW)
            if b & 0x80:
                GPIO.output(self.MOSI, GPIO.HIGH)
            else:
                GPIO.output(self.MOSI, GPIO.LOW)
            GPIO.output(self.SCK, GPIO.HIGH)
            b <<= 1

    def _rx_byte(self):
        GPIO.output(self.MOSI, GPIO.LOW)
        b = 0
        for i in range(8):
            GPIO.output(self.SCK, GPIO.LOW)
            if GPIO.input(self.MISO):
                b |= 1
            GPIO.output(self.SCK, GPIO.HIGH)
            b <<= 1
        return b >> 1


# ------------------------------------------------------------------------------
def main():  # pragma: no cover
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

    GPIO.setmode(GPIO.BCM)
    sum = 0
    n = 0

    try:
        spi = SPI_EM_IC(SMART_CARD_B_PINS)
        # spi = GPIO_EM_IC(SMART_CARD_B_PINS)

        spi.stop_dsp()
        spi.configure(cfg)
        spi.start_dsp()

        time.sleep(2)
        print("ADE7858 version = %d" % spi.reg8_get(spi.VERSION))
        while True:
            line1 = spi.reg32_get(spi.AIRMS)
            line2 = spi.reg32_get(spi.BIRMS)
            line3 = spi.reg32_get(spi.CIRMS)

            print("%d\t%d\t%d" % (line1, line2, line3))
            sum += line2
            n += 1
    finally:
        GPIO.cleanup()
        print("avg = %f" % (sum / n))


# ------------------------------------------------------------------------------
if __name__ == "__main__":
    main()  # pragma: no cover
