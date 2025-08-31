import RPi.GPIO as GPIO
import time

TEMP_FAM = 18  # GPIO pin connected to the fan

GPIO.setmode(GPIO.BCM)
GPIO.setup(TEMP_FAM, GPIO.OUT)

print("Fan Turning On for 5 seconds")
GPIO.output(TEMP_FAM, True)  # Turn fan on
time.sleep(5)
print("Fan Turning Off")
GPIO.output(TEMP_FAM, False)  # Turn fan off

GPIO.cleanup()
