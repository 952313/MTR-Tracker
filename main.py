from api import getTrains
from time import sleep
from TWLcore import mainloop
while True:
    trains = getTrains("TWL")
    mainloop(trains)
    sleep(10)