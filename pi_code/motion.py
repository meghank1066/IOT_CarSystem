import time
import threading

try:
    from gpiozero import MotionSensor, LED
    gpio_available = True
except ImportError:
    gpio_available = False
    MotionSensor = None
    LED = None

if gpio_available:
    green_led = LED(17)
    pir = MotionSensor(4)
    green_led.off()
else:
    green_led = None
    pir = None

motion_status = "clear"

def start_motion_monitor(pubnub, log_motion_event):
    def monitor():
        global motion_status
        if not gpio_available:
            print("Skipping motion monitoring — GPIO not available.")
            return

        while True:
            pir.wait_for_motion()
            motion_status = "detected"
            green_led.on()
            print("Motion Detected")
            pubnub.publish().channel("iot_channel").message({"motion": motion_status}).sync()
            log_motion_event(motion_status)

            pir.wait_for_no_motion()
            motion_status = "clear"
            green_led.off()
            print("Motion Stopped")
            pubnub.publish().channel("iot_channel").message({"motion": motion_status}).sync()
            log_motion_event(motion_status)
            time.sleep(0.1)

    thread = threading.Thread(target=monitor, daemon=True)
    thread.start()




#og code
# from gpiozero import LED
# from gpiozero import MotionSensor

# green_led = LED(17)
# pir = MotionSensor(4)
# green_led.off()

# while True:
#     pir.wait_for_motion()
#     print("Motion Detected")
#     green_led.on()
#     pir.wait_for_no_motion()
#     green_led.off()
#     print("Motion Stopped")
